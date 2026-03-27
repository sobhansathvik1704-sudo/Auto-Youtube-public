from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMBase


class ProjectCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    niche: str = Field(default="tech", max_length=100)
    primary_language: str = Field(default="te", max_length=20)
    secondary_language: str | None = Field(default="en", max_length=20)
    default_format: str = Field(default="short", max_length=20)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=255)
    niche: str | None = Field(default=None, max_length=100)
    primary_language: str | None = Field(default=None, max_length=20)
    secondary_language: str | None = Field(default=None, max_length=20)
    default_format: str | None = Field(default=None, max_length=20)


class ProjectRead(ORMBase):
    id: str
    user_id: str
    name: str
    niche: str
    primary_language: str
    secondary_language: str | None
    default_format: str
    created_at: datetime
    updated_at: datetime