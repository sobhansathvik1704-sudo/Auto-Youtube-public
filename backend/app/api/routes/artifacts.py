from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_database
from app.db.models.asset import Asset
from app.db.models.project import Project
from app.db.models.user import User
from app.db.models.video_job import VideoJob
from app.schemas.artifact import ArtifactRead

router = APIRouter(prefix="/video-jobs", tags=["artifacts"])


@router.get("/{job_id}/artifacts", response_model=list[ArtifactRead])
def get_artifacts(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> list[ArtifactRead]:
    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    artifacts = db.scalars(
        select(Asset).where(Asset.video_job_id == job.id).order_by(Asset.created_at.asc())
    ).all()
    return [ArtifactRead.model_validate(asset) for asset in artifacts]