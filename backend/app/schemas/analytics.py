from pydantic import BaseModel


class ChannelStats(BaseModel):
    channel_name: str
    subscriber_count: int
    total_views: int
    total_videos: int


class VideoStats(BaseModel):
    video_id: str
    title: str
    published_at: str
    views: int
    likes: int
    comments: int


class DailyAnalyticsRow(BaseModel):
    date: str
    views: int
    estimated_minutes_watched: int
    subscribers_gained: int
    subscribers_lost: int
