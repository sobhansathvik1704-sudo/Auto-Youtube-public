from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_database
from app.db.models.project import Project
from app.db.models.scene import Scene
from app.db.models.script import Script
from app.db.models.user import User
from app.db.models.video_job import VideoJob
from app.schemas.scene import SceneRead
from app.schemas.script import ScriptRead

router = APIRouter(prefix="/video-jobs", tags=["scripts"])


@router.get("/{job_id}/script", response_model=ScriptRead)
def get_script(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ScriptRead:
    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    script = db.scalar(
        select(Script).where(Script.video_job_id == job.id).order_by(Script.version.desc())
    )
    if not script:
        raise HTTPException(status_code=404, detail="Script not found")

    return ScriptRead.model_validate(script)


@router.get("/{job_id}/scenes", response_model=list[SceneRead])
def get_scenes(
    job_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> list[SceneRead]:
    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    scenes = db.scalars(
        select(Scene).where(Scene.video_job_id == job.id).order_by(Scene.scene_index.asc())
    ).all()
    return [SceneRead.model_validate(scene) for scene in scenes]