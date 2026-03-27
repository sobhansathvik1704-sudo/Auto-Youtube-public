import json

from app.db.models.script import Script
from app.db.models.video_job import VideoJob


def build_youtube_metadata(job: VideoJob, script: Script) -> str:
    payload = {
        "title": script.title,
        "description": (
            f"{script.hook}\n\n"
            f"Topic: {job.topic}\n"
            f"Category: {job.category}\n"
            f"Audience: {job.audience_level}\n"
            "Language: Telugu + English\n\n"
            "Follow for more coding and tech videos."
        ),
        "tags": [
            job.topic,
            job.category,
            "telugu tech",
            "coding telugu",
            "tech shorts",
            "programming telugu",
        ],
    }
    return json.dumps(payload, ensure_ascii=False)