from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_database
from app.db.models.project import Project
from app.db.models.scene import Scene
from app.db.models.script import Script
from app.db.models.user import User
from app.db.models.video_job import VideoJob
from app.schemas.scene import SceneRead, SceneUpdate
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


@router.patch("/{job_id}/scenes/{scene_id}", response_model=SceneRead)
def update_scene(
    job_id: str,
    scene_id: str,
    payload: SceneUpdate,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> SceneRead:
    """Update editable fields of a scene during the review step.

    Only the fields present in the request body are updated.  The job must
    belong to the authenticated user and must be in ``awaiting_approval``
    status — edits are only meaningful before rendering starts.
    """
    job = db.scalar(
        select(VideoJob)
        .join(Project, Project.id == VideoJob.project_id)
        .where(VideoJob.id == job_id, Project.user_id == current_user.id)
    )
    if not job:
        raise HTTPException(status_code=404, detail="Video job not found")

    if job.status != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Scene edits are only allowed when the job is awaiting approval "
                f"(current status: {job.status})."
            ),
        )

    scene = db.scalar(
        select(Scene).where(Scene.id == scene_id, Scene.video_job_id == job_id)
    )
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(scene, field, value)

    db.add(scene)
    db.commit()
    db.refresh(scene)
    return SceneRead.model_validate(scene)