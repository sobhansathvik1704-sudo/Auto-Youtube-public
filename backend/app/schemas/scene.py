from datetime import datetime

from pydantic import BaseModel, field_validator

from app.schemas.common import ORMBase


class SceneRead(ORMBase):
    id: str
    video_job_id: str
    scene_index: int
    scene_type: str
    narration_text: str
    on_screen_text: str | None
    visual_prompt: str | None
    asset_config_json: str
    duration_ms: int
    start_ms: int
    end_ms: int
    created_at: datetime


class SceneUpdate(BaseModel):
    """Fields that a user may edit during the review step.

    All fields are optional — only the provided fields will be updated.
    ``narration_text`` must be a non-empty string when supplied (it maps to a
    NOT NULL column).  ``on_screen_text`` and ``visual_prompt`` may be set to
    ``None`` or an empty string to clear the value.
    """

    on_screen_text: str | None = None
    narration_text: str | None = None
    visual_prompt: str | None = None

    @field_validator("narration_text")
    @classmethod
    def narration_must_not_be_empty(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("narration_text must not be empty when provided")
        return v