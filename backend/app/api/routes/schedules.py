import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_database
from app.db.models.project import Project
from app.db.models.schedule import Schedule
from app.db.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.utils.cron import calculate_next_run, cron_interval_seconds, validate_cron_expression

router = APIRouter(prefix="/schedules", tags=["schedules"])

# Minimum allowed interval between schedule runs (30 minutes)
_MIN_INTERVAL_SECONDS = 30 * 60


def _schedule_to_read(schedule: Schedule) -> ScheduleRead:
    data = schedule.__dict__.copy()
    data["topics"] = json.loads(schedule.topics_json)
    return ScheduleRead.model_validate(data)


def _validate_cron(cron_expression: str) -> None:
    if not validate_cron_expression(cron_expression):
        raise HTTPException(status_code=422, detail="Invalid cron expression")
    interval = cron_interval_seconds(cron_expression)
    if interval < _MIN_INTERVAL_SECONDS:
        raise HTTPException(
            status_code=422,
            detail="Schedule interval must be at least 30 minutes to prevent abuse",
        )


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ScheduleRead:
    project = db.scalar(
        select(Project).where(
            Project.id == payload.project_id, Project.user_id == current_user.id
        )
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    _validate_cron(payload.cron_expression)

    next_run = calculate_next_run(payload.cron_expression, payload.timezone_str)

    schedule = Schedule(
        user_id=current_user.id,
        project_id=payload.project_id,
        name=payload.name,
        cron_expression=payload.cron_expression,
        timezone_str=payload.timezone_str,
        is_active=True,
        topics_json=json.dumps(payload.topics),
        category=payload.category,
        audience_level=payload.audience_level,
        language_mode=payload.language_mode,
        video_format=payload.video_format,
        duration_seconds=payload.duration_seconds,
        auto_upload=payload.auto_upload,
        next_run_at=next_run,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return _schedule_to_read(schedule)


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> list[ScheduleRead]:
    schedules = db.scalars(
        select(Schedule)
        .where(Schedule.user_id == current_user.id)
        .order_by(Schedule.created_at.desc())
    ).all()
    return [_schedule_to_read(s) for s in schedules]


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(
    schedule_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ScheduleRead:
    schedule = db.scalar(
        select(Schedule).where(
            Schedule.id == schedule_id, Schedule.user_id == current_user.id
        )
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return _schedule_to_read(schedule)


@router.put("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: str,
    payload: ScheduleUpdate,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> ScheduleRead:
    schedule = db.scalar(
        select(Schedule).where(
            Schedule.id == schedule_id, Schedule.user_id == current_user.id
        )
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if payload.name is not None:
        schedule.name = payload.name

    if payload.cron_expression is not None:
        _validate_cron(payload.cron_expression)
        schedule.cron_expression = payload.cron_expression
        schedule.next_run_at = calculate_next_run(
            payload.cron_expression, schedule.timezone_str
        )

    if payload.topics is not None:
        if len(payload.topics) == 0:
            raise HTTPException(status_code=422, detail="topics must not be empty")
        schedule.topics_json = json.dumps(payload.topics)

    if payload.is_active is not None:
        schedule.is_active = payload.is_active

    if payload.auto_upload is not None:
        schedule.auto_upload = payload.auto_upload

    db.commit()
    db.refresh(schedule)
    return _schedule_to_read(schedule)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: str,
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> None:
    schedule = db.scalar(
        select(Schedule).where(
            Schedule.id == schedule_id, Schedule.user_id == current_user.id
        )
    )
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    db.delete(schedule)
    db.commit()
