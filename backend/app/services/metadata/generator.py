import json

from app.db.models.script import Script
from app.db.models.video_job import VideoJob


def build_youtube_metadata(job: VideoJob, script: Script, seo_metadata: dict | None = None) -> str:
    """Build the YouTube metadata JSON string for the given job and script.

    When *seo_metadata* is provided (from :class:`~app.services.seo.generator.SEOGenerator`)
    its title, description, tags, hashtags and category_id take precedence over the
    defaults.  All SEO fields are stored in the returned payload so they can be
    retrieved later via the ``/seo`` API endpoint.
    """
    if seo_metadata:
        payload = {
            "title": seo_metadata.get("title", script.title),
            "description": seo_metadata.get("description", script.hook),
            "tags": seo_metadata.get("tags", [job.topic, job.category]),
            "hashtags": seo_metadata.get("hashtags", []),
            "category_id": seo_metadata.get("category_id", 28),
        }
    else:
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
            "hashtags": [],
            "category_id": 28,
        }
    return json.dumps(payload, ensure_ascii=False)