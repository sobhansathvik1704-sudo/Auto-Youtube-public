"""YouTube Analytics service.

Uses the YouTube Data API v3 (channel/video stats) and YouTube Analytics API v2
(daily metrics).  Credentials are loaded from the token file configured via
``YOUTUBE_TOKEN_FILE`` in settings.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

from app.core.config import get_settings

logger = logging.getLogger(__name__)

ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

# Simple in-process cache: {cache_key: (expires_at, value)}
_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minutes


def _cached(key: str, fn):
    """Return cached value or call *fn* and cache the result for 5 minutes."""
    import time

    now = time.monotonic()
    if key in _cache:
        expires_at, value = _cache[key]
        if now < expires_at:
            return value

    value = fn()
    _cache[key] = (now + _CACHE_TTL_SECONDS, value)
    return value


def load_youtube_credentials():
    """Load OAuth2 credentials from the token file, refreshing if expired.

    Returns ``None`` if the token file does not exist or cannot be loaded.
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    settings = get_settings()
    token_path = Path(settings.youtube_token_file)

    if not token_path.exists():
        logger.warning("YouTube token file not found: %s", token_path)
        return None

    try:
        creds = Credentials.from_authorized_user_file(str(token_path), ANALYTICS_SCOPES)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load YouTube credentials: %s", exc)
        return None

    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                token_path.write_text(creds.to_json())
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to refresh YouTube credentials: %s", exc)
                return None
        else:
            return None

    return creds


class YouTubeAnalyticsService:
    """Wraps YouTube Data API v3 and YouTube Analytics API v2."""

    def __init__(self, credentials) -> None:
        from googleapiclient.discovery import build

        self.youtube = build("youtube", "v3", credentials=credentials, cache_discovery=False)
        self.analytics = build(
            "youtubeAnalytics", "v2", credentials=credentials, cache_discovery=False
        )

    # ------------------------------------------------------------------
    # Channel stats
    # ------------------------------------------------------------------

    def get_channel_stats(self) -> dict:
        """Return channel-level statistics from the YouTube Data API."""

        def _fetch():
            response = (
                self.youtube.channels()
                .list(part="statistics,snippet", mine=True)
                .execute()
            )
            items = response.get("items", [])
            if not items:
                raise ValueError("No channel found for the authenticated user.")
            channel = items[0]
            stats = channel.get("statistics", {})
            return {
                "channel_name": channel["snippet"]["title"],
                "subscriber_count": int(stats.get("subscriberCount", 0)),
                "total_views": int(stats.get("viewCount", 0)),
                "total_videos": int(stats.get("videoCount", 0)),
            }

        return _cached("channel_stats", _fetch)

    # ------------------------------------------------------------------
    # Per-video stats
    # ------------------------------------------------------------------

    def get_video_stats(self, video_ids: list[str]) -> list[dict]:
        """Return per-video statistics for the supplied YouTube video IDs."""
        if not video_ids:
            return []

        cache_key = "video_stats:" + ",".join(sorted(video_ids))

        def _fetch():
            stats = []
            # Batch in groups of 50 (YouTube API limit)
            for i in range(0, len(video_ids), 50):
                batch = video_ids[i : i + 50]
                response = (
                    self.youtube.videos()
                    .list(part="statistics,snippet", id=",".join(batch))
                    .execute()
                )
                for item in response.get("items", []):
                    s = item.get("statistics", {})
                    stats.append(
                        {
                            "video_id": item["id"],
                            "title": item["snippet"]["title"],
                            "published_at": item["snippet"]["publishedAt"],
                            "views": int(s.get("viewCount", 0)),
                            "likes": int(s.get("likeCount", 0)),
                            "comments": int(s.get("commentCount", 0)),
                        }
                    )
            return stats

        return _cached(cache_key, _fetch)

    # ------------------------------------------------------------------
    # Daily analytics
    # ------------------------------------------------------------------

    def get_channel_analytics(self, days: int = 30) -> list:
        """Return daily analytics rows for the last *days* days.

        Each row is a list: [date_str, views, estimated_minutes_watched,
        subscribers_gained, subscribers_lost].
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days - 1)
        cache_key = f"daily_analytics:{start_date}:{end_date}"

        def _fetch():
            response = (
                self.analytics.reports()
                .query(
                    ids="channel==MINE",
                    startDate=str(start_date),
                    endDate=str(end_date),
                    metrics="views,estimatedMinutesWatched,subscribersGained,subscribersLost",
                    dimensions="day",
                    sort="day",
                )
                .execute()
            )
            return response.get("rows", [])

        return _cached(cache_key, _fetch)
