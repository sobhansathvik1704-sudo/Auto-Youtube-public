from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, get_database
from app.db.models.job_event import JobEvent
from app.db.models.project import Project
from app.db.models.user import User
from app.db.models.video_job import VideoJob
from app.schemas.video_job import (
    JobEventRead,
    VideoJobCreate,
    VideoJobDownloadResponse,
    VideoJobRead,
    VideoJobStatusResponse,
    YouTubeUploadResponse,
)
from app.services.jobs.pipeline import enqueue_video_job

router = APIRouter(prefix="/video-jobs", tags=["video-jobs"])


@router.post("", response_model=VideoJobRead, status_code=status.HTTP_201_CREATED)
def create_video_job(
    payload: VideoJobCreate,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> VideoJobRead:
    project = db.scalar(
        select(Project).where(Project.id == payload.project_id, Project.user_id == current_user.id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    job = VideoJob(
        project_id=payload.project_id,
        topic=payload.topic,
        category=payload.category,
        audience_level=payload.audience_level,
        language_mode=payload.language_mode,
        video_format=payload.video_format,
        duration_seconds=payload.duration_seconds,
        avatar_mode=payload.avatar_mode,
        status="queued",
    )
    db.add(job)
    db.flush()

    event = JobEvent(
        video_job_id=job.id,
        step_name="job_created",
        status="queued",
        message="Video job queued for processing",
    )
    db.add(event)
    db.commit()
    db.refresh(job)

    enqueue_video_job(job.id)
    return VideoJobRead.model_validate(job)


@router.get("", response_model=list[VideoJobRead])
def list_video_jobs(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> list[VideoJobRead]:
    jobs = db.scalars(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(Project.user_id == current_user.id)
        .order_by(VideoJob.created_at.desc())
    ).all()
    return [VideoJobRead.model_validate(job) for job in jobs]


@router.get("/{job_id}", response_model=VideoJobRead)
def get_video_job(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> VideoJobRead:
    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    return VideoJobRead.model_validate(job)


@router.get("/{job_id}/status", response_model=VideoJobStatusResponse)
def get_video_job_status(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> VideoJobStatusResponse:
    job = db.scalar(
        select(VideoJob)
        .options(selectinload(VideoJob.events))
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    events = sorted(job.events, key=lambda item: item.created_at)
    return VideoJobStatusResponse(
        job=VideoJobRead.model_validate(job),
        events=[JobEventRead.model_validate(event) for event in events],
    )


@router.get("/{job_id}/download", response_model=VideoJobDownloadResponse)
def get_video_download_url(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> VideoJobDownloadResponse:
    """Return a download URL for the rendered video.

    When the storage backend is S3 this generates a time-limited presigned
    URL (valid for 1 hour).  For the local backend ``download_url`` is
    ``None`` and ``storage_key`` contains the absolute path on the server.
    """
    from app.services.storage import StorageService

    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    if job.status != "completed" or not job.render_storage_key:
        raise HTTPException(
            status_code=400,
            detail="Video is not available yet. Wait until the job status is 'completed'.",
        )

    storage = StorageService()
    download_url = storage.get_presigned_url(job.render_storage_key)
    return VideoJobDownloadResponse(
        job_id=job_id,
        storage_key=job.render_storage_key,
        download_url=download_url,
    )


@router.get("/{job_id}/download/file")
def download_video_file(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Stream the rendered video file directly from local storage."""
    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")
    if job.status != "completed" or not job.render_storage_key:
        raise HTTPException(status_code=400, detail="Video not ready yet")

    file_path = Path(job.render_storage_key).resolve()
    # Guard against path traversal: ensure the resolved path is within the expected storage root
    from app.core.config import get_settings
    storage_root = Path(get_settings().artifacts_dir).resolve()
    if not str(file_path).startswith(str(storage_root)):
        raise HTTPException(status_code=403, detail="Access denied")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Video file not found on disk")

    filename = f"{job.topic.replace(' ', '_')}_video.mp4" if job.topic else "video.mp4"
    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename,
    )


@router.post("/{job_id}/upload", response_model=YouTubeUploadResponse)
def upload_video_to_youtube(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> YouTubeUploadResponse:
    """Trigger an asynchronous YouTube upload for the specified video job.

    The job must be in ``completed`` status (i.e. the video has been rendered)
    before calling this endpoint.  The upload is handled by a background Celery
    task so the response returns immediately.
    """
    from app.services.jobs.tasks import upload_to_youtube

    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    if job.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Video job is not ready for upload (current status: {job.status}). "
                   "Wait until the job status is 'completed'.",
        )

    if not job.render_storage_key:
        raise HTTPException(status_code=400, detail="Rendered video file is not available yet.")

    result = upload_to_youtube.delay(job_id)
    return YouTubeUploadResponse(
        job_id=job_id,
        task_id=result.id,
        message="YouTube upload has been queued. The video will be uploaded in the background.",
    )