from app.core.config import get_settings
from app.db.models.video_job import VideoJob

settings = get_settings()


def resolve_dimensions(job: VideoJob) -> tuple[int, int]:
    if job.video_format == "short":
        return settings.short_video_width, settings.short_video_height
    return settings.long_video_width, settings.long_video_height