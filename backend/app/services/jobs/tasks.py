from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import subprocess

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.db.models.asset import Asset
from app.db.models.job_event import JobEvent
from app.db.models.project import Project
from app.db.models.scene import Scene
from app.db.models.schedule import Schedule
from app.db.models.script import Script
from app.db.models.video_job import VideoJob
from app.services.ai.tts import TTSClient
from app.services.artifacts.local_storage import LocalArtifactStorage  # noqa: F401 – kept for backwards compat
from app.services.llm.script_generator import generate_and_store_script
from app.services.storage import StorageService
from app.services.metadata.generator import build_youtube_metadata
from app.services.renderer.ffmpeg import render_video
from app.services.subtitles.generator import generate_srt_content

logger = logging.getLogger(__name__)


@celery_app.task(name="app.services.jobs.tasks.upload_to_youtube", bind=True, max_retries=2)
def upload_to_youtube(self, job_id: str) -> dict:
    """Celery task: upload the rendered video for *job_id* to YouTube.

    Reads the rendered ``final.mp4`` and ``youtube.json`` metadata produced
    by the generation pipeline, then uploads the video via the YouTube Data
    API v3 and stores the returned video ID on the :class:`VideoJob` record.

    Returns a dict with ``{"youtube_video_id": "<id>"}``.
    """
    from app.services.youtube import YouTubeUploader

    db = SessionLocal()
    storage = StorageService()
    try:
        job = db.get(VideoJob, job_id)
        if not job:
            logger.error("Video job %s not found", job_id)
            raise ValueError(f"Video job {job_id} not found")

        if not job.render_storage_key:
            raise RuntimeError("Video has not been rendered yet (render_storage_key is missing)")

        # Resolve the video file to a local path (download from S3 if needed).
        if storage.is_s3:
            import botocore.exceptions  # noqa: PLC0415
            import tempfile  # noqa: PLC0415

            tmp_dir = Path(tempfile.mkdtemp(prefix="yt_upload_"))
            video_path = tmp_dir / "final.mp4"
            storage.download_file(job.render_storage_key, video_path)

            # Derive the S3 metadata key: replace "renders/final.mp4" with
            # "metadata/youtube.json" within the same job prefix.
            render_key = job.render_storage_key
            parts = render_key.rsplit("/renders/", 1)
            if len(parts) != 2:
                raise RuntimeError(
                    f"Cannot derive metadata key from render_storage_key: {render_key!r}"
                )
            metadata_key = parts[0] + "/metadata/youtube.json"
            metadata_path: Path | None = tmp_dir / "youtube.json"
            try:
                storage.download_file(metadata_key, metadata_path)
            except botocore.exceptions.ClientError:
                logger.warning(
                    "Metadata not found in S3 for job %s (key: %s); proceeding without it",
                    job_id,
                    metadata_key,
                )
                metadata_path = None
        else:
            video_path = Path(job.render_storage_key)
            metadata_path = video_path.parent.parent / "metadata" / "youtube.json"

        add_job_event(db, job.id, "youtube_upload", "started", "YouTube upload started")
        db.commit()

        uploader = YouTubeUploader()

        metadata: dict = {}
        if metadata_path is not None and metadata_path.exists():
            metadata = uploader.read_metadata(metadata_path)

        title = metadata.get("title") or job.topic
        description = metadata.get("description") or ""
        tags = metadata.get("tags") or []

        video_id = uploader.upload(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
        )

        job.youtube_video_id = video_id
        db.add(job)
        add_job_event(
            db, job.id, "youtube_upload", "completed",
            f"Uploaded to YouTube: https://youtu.be/{video_id}"
        )
        db.commit()

        logger.info("YouTube upload completed for job %s – video ID: %s", job_id, video_id)
        return {"youtube_video_id": video_id}

    except Exception as exc:
        db.rollback()
        job = db.get(VideoJob, job_id)

        # Determine whether we should retry or fail immediately.
        should_retry = True
        error_msg = str(exc)

        try:
            from googleapiclient.errors import HttpError  # noqa: PLC0415
            if isinstance(exc, HttpError):
                status_code = exc.resp.status
                if status_code == 401:
                    should_retry = False
                    error_msg = (
                        "YouTube authentication failed (401). "
                        "Please re-authenticate and refresh youtube_token.json."
                    )
                elif status_code == 403:
                    should_retry = False
                    error_msg = (
                        "YouTube API quota exceeded or access forbidden (403). "
                        "Check your API quota in Google Cloud Console."
                    )
                # 5xx errors: retry as usual (should_retry stays True)
        except ImportError:
            pass

        if job:
            if not should_retry:
                set_job_status(db, job, "failed", error_message=error_msg)
            add_job_event(db, job.id, "youtube_upload", "failed", f"YouTube upload failed: {error_msg}")
            db.commit()

        logger.exception("YouTube upload failed for job %s", job_id)

        if not should_retry:
            return  # Do not retry auth/quota failures

        raise self.retry(exc=exc, countdown=10)
    finally:
        db.close()


def _concatenate_audio(scene_audio_paths: list[Path], output_path: Path) -> None:
    """Concatenate multiple MP3 clips into a single output file using FFmpeg."""
    settings = get_settings()
    concat_list = output_path.parent / "concat_list.txt"
    try:
        concat_list.write_text(
            "\n".join(f"file '{p.resolve()}'" for p in scene_audio_paths)
        )
        result = subprocess.run(
            [
                settings.ffmpeg_bin,
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ],
            check=False,
            capture_output=True,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")
            logger.error("FFmpeg audio concatenation failed: %s", stderr)
            raise subprocess.CalledProcessError(result.returncode, result.args, result.stdout, result.stderr)
    finally:
        concat_list.unlink(missing_ok=True)


VALID_STATUSES = {
    "queued",
    "researching",
    "script_generated",
    "planning_visuals",
    "generating_audio",
    "generating_subtitles",
    "rendering",
    "packaging",
    "completed",
    "failed",
}


def add_job_event(db: Session, job_id: str, step_name: str, status: str, message: str) -> None:
    event = JobEvent(
        video_job_id=job_id,
        step_name=step_name,
        status=status,
        message=message,
    )
    db.add(event)


def set_job_status(db: Session, job: VideoJob, status: str, error_message: str | None = None) -> None:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status: {status}")

    job.status = status
    job.error_message = error_message
    if status == "completed":
        job.completed_at = datetime.now(timezone.utc)
    db.add(job)


@celery_app.task(name="app.services.jobs.tasks.process_video_job", bind=True, max_retries=2)
def process_video_job(self, job_id: str) -> None:
    db = SessionLocal()
    storage = StorageService()

    try:
        job = db.get(VideoJob, job_id)
        if not job:
            logger.error("Video job %s not found", job_id)
            return

        project = db.get(Project, job.project_id)
        if not project:
            raise RuntimeError("Project not found for video job")

        set_job_status(db, job, "researching")
        add_job_event(db, job.id, "research", "started", "Script generation started")
        db.commit()

        script = generate_and_store_script(db, job)
        script_path = storage.write_text(project.id, job.id, "script/script.json", script.structured_json)
        db.add(
            Asset(
                video_job_id=job.id,
                scene_id=None,
                asset_type="script_json",
                provider="local",
                storage_key=script_path,
                metadata_json=json.dumps({"version": script.version}),
            )
        )
        set_job_status(db, job, "script_generated")
        add_job_event(db, job.id, "script_generation", "completed", "Script generated successfully")
        db.commit()

        from app.services.visuals.planner import generate_scenes_from_script

        set_job_status(db, job, "planning_visuals")
        scenes = generate_scenes_from_script(db, job, script)
        add_job_event(db, job.id, "visual_planning", "completed", f"Generated {len(scenes)} scenes")
        db.commit()

        set_job_status(db, job, "generating_audio")
        tts_client = TTSClient()
        audio_dir = Path(storage.job_dir(project.id, job.id)) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        scene_audio_paths: list[Path] = []
        for scene in scenes:
            scene_audio_path = audio_dir / f"scene_{scene.scene_index:03d}.mp3"
            tts_client.synthesize_speech(
                text=scene.narration_text,
                language=job.language_mode,
                output_path=scene_audio_path,
            )
            scene_audio_paths.append(scene_audio_path)
        audio_output = audio_dir / "narration.mp3"
        _concatenate_audio(scene_audio_paths, audio_output)
        db.add(
            Asset(
                video_job_id=job.id,
                scene_id=None,
                asset_type="audio",
                provider="google_tts",
                storage_key=str(audio_output),
                metadata_json=json.dumps({"voice": "google_cloud_tts", "language_mode": job.language_mode}),
            )
        )
        add_job_event(db, job.id, "tts", "completed", "Audio generated")
        db.commit()

        set_job_status(db, job, "generating_subtitles")
        scene_rows = db.scalars(
            select(Scene).where(Scene.video_job_id == job.id).order_by(Scene.scene_index.asc())
        ).all()
        srt_content = generate_srt_content(scene_rows)
        srt_path = storage.write_text(project.id, job.id, "subtitles/subtitles.srt", srt_content)
        db.add(
            Asset(
                video_job_id=job.id,
                scene_id=None,
                asset_type="subtitles",
                provider="local",
                storage_key=srt_path,
                metadata_json=json.dumps({"format": "srt"}),
            )
        )
        add_job_event(db, job.id, "subtitles", "completed", "Subtitles generated")
        db.commit()

        set_job_status(db, job, "rendering")
        render_output = Path(storage.job_dir(project.id, job.id)) / "renders" / "final.mp4"
        render_output.parent.mkdir(parents=True, exist_ok=True)
        render_video(
            db=db,
            job=job,
            scenes=scene_rows,
            audio_path=audio_output,
            subtitles_path=Path(srt_path),
            output_path=render_output,
        )
        # Upload the rendered file to the configured storage backend and persist
        # the storage key (S3 object key or local absolute path) on the job.
        render_storage_key = storage.upload_file(render_output, project.id, job.id, "renders/final.mp4")
        job.render_storage_key = render_storage_key
        # Keep the Asset record created inside render_video in sync.
        render_asset = db.scalars(
            select(Asset)
            .where(Asset.video_job_id == job.id, Asset.asset_type == "render_output")
            .order_by(Asset.created_at.desc())
        ).first()
        if render_asset and render_asset.storage_key != render_storage_key:
            render_asset.storage_key = render_storage_key
            db.add(render_asset)
        add_job_event(db, job.id, "render", "completed", "Video rendered successfully")
        db.commit()

        set_job_status(db, job, "packaging")
        metadata_json = build_youtube_metadata(job, script)
        metadata_path = storage.write_text(project.id, job.id, "metadata/youtube.json", metadata_json)
        job.metadata_json = metadata_json
        db.add(
            Asset(
                video_job_id=job.id,
                scene_id=None,
                asset_type="metadata",
                provider="local",
                storage_key=metadata_path,
                metadata_json=json.dumps({"kind": "youtube"}),
            )
        )
        add_job_event(db, job.id, "metadata", "completed", "Metadata packaged")
        db.commit()

        set_job_status(db, job, "completed")
        add_job_event(db, job.id, "pipeline", "completed", "Full generation pipeline completed successfully")
        db.commit()

        logger.info("Completed video job %s", job_id)

    except Exception as exc:
        db.rollback()
        job = db.get(VideoJob, job_id)

        # Detect OpenAI insufficient_quota errors – do not retry these.
        should_retry = True
        error_msg = str(exc)

        try:
            import openai  # noqa: PLC0415
            if isinstance(exc, openai.RateLimitError):
                # Distinguish quota-exhausted from transient rate-limit
                if "insufficient_quota" in error_msg or "exceeded your current quota" in error_msg:
                    should_retry = False
                    error_msg = (
                        "OpenAI API quota exhausted. "
                        "Please add credits at https://platform.openai.com/settings/organization/billing"
                    )
                # Otherwise it is a transient rate limit – retry as usual
        except ImportError:
            pass

        if job:
            if not should_retry:
                set_job_status(db, job, "failed", error_message=error_msg)
            else:
                set_job_status(db, job, "failed", error_message=str(exc))
            add_job_event(db, job.id, "pipeline", "failed", f"Pipeline failed: {error_msg}")
            db.commit()

        logger.exception("Failed processing video job %s", job_id)

        if not should_retry:
            return  # Do not retry quota-exhausted failures

        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()