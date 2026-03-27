from datetime import datetime

from app.schemas.common import ORMBase


class ScriptRead(ORMBase):
    id: str
    video_job_id: str
    title: str
    hook: str
    intro: str | None
    outro: str | None
    full_text: str
    structured_json: str
    version: int
    created_at: datetime