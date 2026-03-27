import json

from sqlalchemy.orm import Session

from app.db.models.script import Script
from app.db.models.video_job import VideoJob
from app.services.llm.factory import get_llm_provider


def generate_and_store_script(db: Session, job: VideoJob) -> Script:
    provider = get_llm_provider()
    payload = provider.generate_script_payload(
        topic=job.topic,
        category=job.category,
        audience_level=job.audience_level,
        language_mode=job.language_mode,
        duration_seconds=job.duration_seconds,
    )

    script = Script(
        video_job_id=job.id,
        title=payload["title"],
        hook=payload["hook"],
        intro=payload.get("intro"),
        outro=payload.get("outro"),
        full_text=payload["full_text"],
        structured_json=json.dumps(payload, ensure_ascii=False),
        version=1,
    )
    db.add(script)
    db.flush()
    return script