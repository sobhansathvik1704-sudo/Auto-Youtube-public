from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_database
from app.db.models.project import Project
from app.db.models.user import User
from app.db.models.video_job import VideoJob
from app.schemas.analytics import ChannelStats, DailyAnalyticsRow, VideoStats
from app.services.youtube_analytics import YouTubeAnalyticsService, load_youtube_credentials

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_service() -> YouTubeAnalyticsService:
    credentials = load_youtube_credentials()
    if not credentials:
        raise HTTPException(
            status_code=400,
            detail=(
                "YouTube credentials are not configured or have expired. "
                "Please re-authenticate with the required scopes "
                "(youtube.readonly and yt-analytics.readonly)."
            ),
        )
    return YouTubeAnalyticsService(credentials)


@router.get("/channel", response_model=ChannelStats)
def get_channel_analytics(
    current_user: User = Depends(get_current_user),
) -> ChannelStats:
    """Return channel-level statistics (subscribers, total views, video count)."""
    service = _get_service()
    try:
        data = service.get_channel_stats()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"YouTube API error: {exc}"
        ) from exc
    return ChannelStats(**data)


@router.get("/videos", response_model=list[VideoStats])
def get_video_analytics(
    db: Session = Depends(get_database),
    current_user: User = Depends(get_current_user),
) -> list[VideoStats]:
    """Return per-video statistics for all uploaded videos belonging to this user."""
    jobs = db.scalars(
        select(VideoJob)
        .join(Project)
        .where(
            Project.user_id == current_user.id,
            VideoJob.youtube_video_id.isnot(None),
        )
    ).all()

    video_ids = [j.youtube_video_id for j in jobs]
    if not video_ids:
        return []

    service = _get_service()
    try:
        data = service.get_video_stats(video_ids)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"YouTube API error: {exc}"
        ) from exc
    return [VideoStats(**item) for item in data]


@router.get("/daily", response_model=list[DailyAnalyticsRow])
def get_daily_analytics(
    days: int = Query(default=30, ge=1, le=90),
    current_user: User = Depends(get_current_user),
) -> list[DailyAnalyticsRow]:
    """Return daily channel metrics (views, watch time, subscribers) for the last N days."""
    service = _get_service()
    try:
        rows = service.get_channel_analytics(days=days)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail=f"YouTube Analytics API error: {exc}"
        ) from exc

    result = []
    for row in rows:
        # API returns: [date, views, estimatedMinutesWatched, subscribersGained, subscribersLost]
        if len(row) >= 5:
            result.append(
                DailyAnalyticsRow(
                    date=row[0],
                    views=int(row[1]),
                    estimated_minutes_watched=int(row[2]),
                    subscribers_gained=int(row[3]),
                    subscribers_lost=int(row[4]),
                )
            )
    return result
