from datetime import datetime

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