from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_database
from app.db.models.project import Project
from app.db.models.user import User
from app.schemas.project import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    project = Project(
        user_id=current_user.id,
        name=payload.name,
        niche=payload.niche,
        primary_language=payload.primary_language,
        secondary_language=payload.secondary_language,
        default_format=payload.default_format,
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectRead.model_validate(project)


@router.get("", response_model=list[ProjectRead])
def list_projects(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> list[ProjectRead]:
    projects = db.scalars(
        select(Project)
        .where(Project.user_id == current_user.id)
        .order_by(Project.created_at.desc())
    ).all()
    return [ProjectRead.model_validate(project) for project in projects]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectRead.model_validate(project)


@router.put("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ProjectRead:
    project = db.scalar(
        select(Project).where(Project.id == project_id, Project.user_id == current_user.id)
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)

    db.add(project)
    db.commit()
    db.refresh(project)
    return ProjectRead.model_validate(project)