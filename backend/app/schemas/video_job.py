from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class VideoJobCreate(BaseModel):
    project_id: str
    topic: str = Field(min_length=3, max_length=500)
    category: str = Field(default="tech", max_length=100)
    audience_level: str = Field(default="beginner", max_length=50)
    language_mode: str = Field(default="te-en", max_length=20)
    video_format: str = Field(default="short", max_length=20)
    duration_seconds: int = Field(default=60, ge=15, le=3600)


class VideoJobRead(ORMBase):
    id: str
    project_id: str
    topic: str
    category: str
    audience_level: str
    language_mode: str
    video_format: str
    duration_seconds: int
    status: str
    error_message: str | None
    render_storage_key: str | None
    metadata_json: str | None
    youtube_video_id: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class JobEventRead(ORMBase):
    id: str
    video_job_id: str
    step_name: str
    status: str
    message: str | None
    created_at: datetime


class VideoJobStatusResponse(BaseModel):
    job: VideoJobRead
    events: list[JobEventRead]


class YouTubeUploadResponse(BaseModel):
    job_id: str
    task_id: str
    message: str