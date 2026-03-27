from datetime import datetime

from app.schemas.common import ORMBase


class ArtifactRead(ORMBase):
    id: str
    video_job_id: str
    scene_id: str | None
    asset_type: str
    provider: str | None
    storage_key: str
    metadata_json: str
    created_at: datetime