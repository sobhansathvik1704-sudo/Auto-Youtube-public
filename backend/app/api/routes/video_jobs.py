from fastapi import APIRouter, Depends, HTTPException, status
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
    VideoJobRead,
    VideoJobStatusResponse,
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