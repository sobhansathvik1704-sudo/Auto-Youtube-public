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
from app.services.seo.generator import SEOGenerator
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
        category_id = str(metadata.get("category_id", 28))

        video_id = uploader.upload(
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
        )

        job.youtube_video_id = video_id
        db.add(job)
        add_job_event(
            db, job.id, "youtube_upload", "completed",
            f"Uploaded to YouTube: https://youtu.be/{video_id}"
        )
        db.commit()

        # Upload thumbnail to YouTube (non-blocking – warn and continue on failure)
        try:
            from sqlalchemy import select as sa_select  # noqa: PLC0415

            thumbnail_asset = db.scalars(
                sa_select(Asset)
                .where(Asset.video_job_id == job_id, Asset.asset_type == "thumbnail")
                .order_by(Asset.created_at.desc())
            ).first()

            if thumbnail_asset:
                if storage.is_s3:
                    import shutil  # noqa: PLC0415
                    import tempfile  # noqa: PLC0415

                    tmp_dir = Path(tempfile.mkdtemp(prefix="yt_thumb_"))
                    try:
                        tmp_thumb = tmp_dir / "thumbnail.jpg"
                        storage.download_file(thumbnail_asset.storage_key, tmp_thumb)
                        thumb_local = tmp_thumb
                        if thumb_local.exists():
                            uploader.upload_thumbnail(video_id=video_id, thumbnail_path=thumb_local)
                            add_job_event(db, job.id, "youtube_thumbnail", "completed", "Thumbnail uploaded to YouTube")
                            db.commit()
                            logger.info("Thumbnail uploaded for YouTube video %s", video_id)
                        else:
                            logger.warning("Thumbnail file not found on disk for job %s", job_id)
                    finally:
                        shutil.rmtree(tmp_dir, ignore_errors=True)
                else:
                    thumb_local = Path(thumbnail_asset.storage_key)
                    if thumb_local.exists():
                        uploader.upload_thumbnail(video_id=video_id, thumbnail_path=thumb_local)
                        add_job_event(db, job.id, "youtube_thumbnail", "completed", "Thumbnail uploaded to YouTube")
                        db.commit()
                        logger.info("Thumbnail uploaded for YouTube video %s", video_id)
                    else:
                        logger.warning("Thumbnail file not found on disk for job %s", job_id)
            else:
                logger.info("No thumbnail asset found for job %s; skipping thumbnail upload", job_id)
        except Exception as thumb_exc:
            db.rollback()
            logger.warning(
                "YouTube thumbnail upload failed for job %s (non-fatal): %s",
                job_id,
                thumb_exc,
            )
            add_job_event(
                db, job.id, "youtube_thumbnail", "failed",
                f"Thumbnail upload failed (non-fatal): {thumb_exc}"
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


# How much extra time (ms) to add after narration ends before the next cut.
_NARRATION_BUFFER_MS = 400
# Minimum scene duration (ms) to avoid flash-cuts.
_MIN_SCENE_DURATION_MS = 2000


def _get_audio_duration_ms(audio_path: Path) -> int:
    """Return the duration of *audio_path* in milliseconds using ffprobe.

    Returns 0 when ffprobe is unavailable or the file cannot be probed.
    """
    settings = get_settings()
    # Derive the ffprobe binary from the configured ffmpeg binary path.
    ffmpeg_bin = settings.ffmpeg_bin
    ffprobe_bin = ffmpeg_bin.replace("ffmpeg", "ffprobe") if "ffmpeg" in ffmpeg_bin else "ffprobe"
    try:
        result = subprocess.run(
            [
                ffprobe_bin,
                "-v", "quiet",
                "-show_entries", "format=duration",
                "-of", "csv=p=0",
                str(audio_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        stripped = result.stdout.strip()
        if not stripped:
            return 0
        return int(float(stripped) * 1000)
    except Exception as exc:
        logger.warning("Could not measure audio duration for %s: %s", audio_path, exc)
        return 0


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
    "queued",            # Job is waiting to be picked up by a Celery worker
    "researching",       # LLM is generating the script
    "script_generated",  # Script has been saved to the database
    "planning_visuals",  # Scene objects are being created from the script
    "awaiting_approval", # Script + scenes ready; paused until user approves via POST /approve
    "generating_audio",  # TTS is synthesising voice-over audio (Step B)
    "generating_subtitles",  # SRT subtitles are being generated
    "rendering",         # FFmpeg is compositing the final video
    "packaging",         # YouTube metadata is being assembled
    "completed",         # Full pipeline finished; video is ready for download/upload
    "failed",            # An unrecoverable error occurred
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
    """Step A: Generate script and scene plan, then pause for user review.

    After this task completes the job status is set to ``awaiting_approval``.
    The user reviews the generated scenes via the frontend and calls the
    ``/approve`` endpoint to trigger :func:`render_video_job` (Step B).
    """
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

        # Generate SEO metadata immediately after script is available.
        seo_metadata: dict | None = None
        try:
            seo = SEOGenerator()
            script_summary = " ".join(
                part for part in [script.hook, script.intro] if part
            )
            seo_metadata = seo.generate_seo_metadata(
                topic=job.topic,
                script_summary=script_summary,
                category=job.category,
            )
            logger.info("SEO metadata generated for job %s", job_id)
        except Exception as seo_exc:
            logger.warning("SEO generation failed for job %s, using defaults: %s", job_id, seo_exc)

        # Persist SEO metadata on the job so it is available to render_video_job.
        if seo_metadata:
            job.metadata_json = json.dumps(seo_metadata)
            db.add(job)

        from app.services.visuals.planner import generate_scenes_from_script

        set_job_status(db, job, "planning_visuals")
        scenes = generate_scenes_from_script(db, job, script)
        add_job_event(db, job.id, "visual_planning", "completed", f"Generated {len(scenes)} scenes")
        db.commit()

        # Pause here and wait for user approval before rendering.
        set_job_status(db, job, "awaiting_approval")
        add_job_event(
            db, job.id, "approval_gate", "pending",
            f"Script and {len(scenes)} scene(s) ready for review. "
            "Approve to start audio and video rendering."
        )
        db.commit()

        logger.info("Video job %s is awaiting user approval", job_id)

    except Exception as exc:
        db.rollback()
        job = db.get(VideoJob, job_id)

        # Detect OpenAI insufficient_quota errors – do not retry these.
        should_retry = True
        error_msg = str(exc)

        try:
            import openai  # noqa: PLC0415
            if isinstance(exc, openai.RateLimitError):
                if "insufficient_quota" in error_msg or "exceeded your current quota" in error_msg:
                    should_retry = False
                    error_msg = (
                        "OpenAI API quota exhausted. "
                        "Please add credits at https://platform.openai.com/settings/organization/billing"
                    )
        except ImportError:
            pass

        if job:
            if not should_retry:
                set_job_status(db, job, "failed", error_message=error_msg)
            else:
                set_job_status(db, job, "failed", error_message=str(exc))
            add_job_event(db, job.id, "pipeline", "failed", f"Script generation failed: {error_msg}")
            db.commit()

        logger.exception("Failed script generation for video job %s", job_id)

        if not should_retry:
            return

        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()


@celery_app.task(name="app.services.jobs.tasks.render_video_job", bind=True, max_retries=2)
def render_video_job(self, job_id: str) -> None:
    """Step B: Generate audio, subtitles, and render the final video.

    Called after the user approves the generated script via the
    ``POST /api/video-jobs/{job_id}/approve`` endpoint.
    """
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

        # Re-fetch the generated script from the database.
        script = db.scalars(
            select(Script).where(Script.video_job_id == job_id).order_by(Script.version.desc())
        ).first()
        if not script:
            raise RuntimeError("Script not found for video job — cannot render without a script")

        # Recover any previously persisted SEO metadata.
        seo_metadata: dict | None = None
        if job.metadata_json:
            try:
                seo_metadata = json.loads(job.metadata_json)
            except (ValueError, TypeError):
                pass

        scene_rows = db.scalars(
            select(Scene).where(Scene.video_job_id == job.id).order_by(Scene.scene_index.asc())
        ).all()
        if not scene_rows:
            raise RuntimeError("No scenes found for video job — cannot render without scenes")

        set_job_status(db, job, "generating_audio")
        add_job_event(db, job.id, "tts", "started", "Audio generation started")
        db.commit()

        tts_client = TTSClient()
        audio_dir = Path(storage.job_dir(project.id, job.id)) / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        scene_audio_paths: list[Path] = []
        for scene in scene_rows:
            scene_audio_path = audio_dir / f"scene_{scene.scene_index:03d}.mp3"
            tts_client.synthesize_speech(
                text=scene.narration_text,
                language=job.language_mode,
                output_path=scene_audio_path,
            )
            scene_audio_paths.append(scene_audio_path)

        # --- Sync scene durations to actual TTS audio lengths ---------------
        # Measure each per-scene audio file and update duration_ms so that the
        # video renderer keeps each slide on screen for exactly as long as the
        # narration plays (plus a small breathing-room buffer).
        updated_start_ms = 0
        for scene, audio_path in zip(scene_rows, scene_audio_paths):
            audio_duration_ms = _get_audio_duration_ms(audio_path)
            if audio_duration_ms > 0:
                new_duration = max(
                    _MIN_SCENE_DURATION_MS,
                    audio_duration_ms + _NARRATION_BUFFER_MS,
                )
            else:
                # ffprobe failed — keep original duration if it is reasonable
                new_duration = max(_MIN_SCENE_DURATION_MS, scene.duration_ms)
            scene.duration_ms = new_duration
            scene.start_ms = updated_start_ms
            scene.end_ms = updated_start_ms + new_duration
            updated_start_ms += new_duration
            db.add(scene)
        db.commit()
        logger.info(
            "Updated scene timings for job %s: %d scenes, total %d ms",
            job_id, len(scene_rows), updated_start_ms,
        )
        # --------------------------------------------------------------------

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
        render_storage_key = storage.upload_file(render_output, project.id, job.id, "renders/final.mp4")
        job.render_storage_key = render_storage_key
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

        # Generate thumbnail (non-blocking – pipeline completes even on failure)
        settings = get_settings()
        thumbnail_output = Path(storage.job_dir(project.id, job.id)) / "thumbnails" / "thumbnail.jpg"
        try:
            from app.services.thumbnail.generator import generate_thumbnail  # noqa: PLC0415

            thumbnail_path = generate_thumbnail(
                topic=job.topic,
                output_path=thumbnail_output,
                category=job.category or "default",
                provider=settings.thumbnail_provider,
            )
            thumbnail_storage_key = storage.upload_file(
                thumbnail_path, project.id, job.id, "thumbnails/thumbnail.jpg"
            )
            db.add(
                Asset(
                    video_job_id=job.id,
                    scene_id=None,
                    asset_type="thumbnail",
                    provider=settings.thumbnail_provider,
                    storage_key=thumbnail_storage_key,
                    metadata_json=json.dumps({"provider": settings.thumbnail_provider}),
                )
            )
            add_job_event(db, job.id, "thumbnail", "completed", "Thumbnail generated successfully")
            db.commit()
            logger.info("Thumbnail generated for job %s at %s", job_id, thumbnail_storage_key)
        except Exception as thumb_exc:
            db.rollback()
            logger.warning(
                "Thumbnail generation failed for job %s (non-fatal): %s",
                job_id,
                thumb_exc,
            )
            add_job_event(
                db, job.id, "thumbnail", "failed",
                f"Thumbnail generation failed (non-fatal): {thumb_exc}"
            )
            db.commit()

        set_job_status(db, job, "packaging")
        metadata_json = build_youtube_metadata(job, script, seo_metadata=seo_metadata)
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

        should_retry = True
        error_msg = str(exc)

        try:
            import openai  # noqa: PLC0415
            if isinstance(exc, openai.RateLimitError):
                if "insufficient_quota" in error_msg or "exceeded your current quota" in error_msg:
                    should_retry = False
                    error_msg = (
                        "OpenAI API quota exhausted. "
                        "Please add credits at https://platform.openai.com/settings/organization/billing"
                    )
        except ImportError:
            pass

        if job:
            if not should_retry:
                set_job_status(db, job, "failed", error_message=error_msg)
            else:
                set_job_status(db, job, "failed", error_message=str(exc))
            add_job_event(db, job.id, "pipeline", "failed", f"Pipeline failed: {error_msg}")
            db.commit()

        logger.exception("Failed rendering video job %s", job_id)

        if not should_retry:
            return

        raise self.retry(exc=exc, countdown=5)
    finally:
        db.close()


@celery_app.task(name="app.services.jobs.tasks.check_and_run_schedules")
def check_and_run_schedules() -> None:
    """Runs every minute via Celery Beat. Checks for due schedules and triggers video generation."""
    from app.services.jobs.pipeline import enqueue_video_job
    from app.utils.cron import calculate_next_run

    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        due_schedules = db.scalars(
            select(Schedule).where(
                Schedule.is_active,
                Schedule.next_run_at <= now,
            )
        ).all()

        for schedule in due_schedules:
            topics = json.loads(schedule.topics_json)
            topic = topics[schedule.current_topic_index % len(topics)]

            job = VideoJob(
                project_id=schedule.project_id,
                topic=topic,
                category=schedule.category,
                audience_level=schedule.audience_level,
                language_mode=schedule.language_mode,
                video_format=schedule.video_format,
                duration_seconds=schedule.duration_seconds,
                status="queued",
            )
            db.add(job)
            db.flush()

            enqueue_video_job(job.id)

            schedule.last_run_at = now
            schedule.current_topic_index = (schedule.current_topic_index + 1) % len(topics)
            schedule.total_runs += 1
            schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone_str)
            logger.info(
                "Schedule %s triggered job %s for topic %r; next run at %s",
                schedule.id,
                job.id,
                topic,
                schedule.next_run_at,
            )

        db.commit()
    except Exception:
        logger.exception("check_and_run_schedules failed")
        db.rollback()
    finally:
        db.close()