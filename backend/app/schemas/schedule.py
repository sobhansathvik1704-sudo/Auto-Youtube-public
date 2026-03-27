from datetime import datetime

from pydantic import BaseModel, Field


class ScheduleCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=2, max_length=255)
    cron_expression: str = Field(max_length=100)
    timezone_str: str = Field(default="UTC", max_length=50)
    topics: list[str] = Field(min_length=1)
    category: str = "tech"
    audience_level: str = "beginner"
    language_mode: str = "en"
    video_format: str = "short"
    duration_seconds: int = Field(default=60, ge=30, le=300)
    auto_upload: bool = True


class ScheduleRead(BaseModel):
    id: str
    project_id: str
    name: str
    cron_expression: str
    timezone_str: str
    topics: list[str]
    category: str
    audience_level: str
    language_mode: str
    video_format: str
    duration_seconds: int
    auto_upload: bool
    is_active: bool
    current_topic_index: int
    last_run_at: datetime | None
    next_run_at: datetime | None
    total_runs: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ScheduleUpdate(BaseModel):
    name: str | None = None
    cron_expression: str | None = None
    topics: list[str] | None = None
    is_active: bool | None = None
    auto_upload: bool | None = None
