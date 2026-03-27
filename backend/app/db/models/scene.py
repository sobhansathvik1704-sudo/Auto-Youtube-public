from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    video_job_id: Mapped[str] = mapped_column(
        ForeignKey("video_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_index: Mapped[int] = mapped_column(Integer, nullable=False)
    scene_type: Mapped[str] = mapped_column(String(100), nullable=False)
    narration_text: Mapped[str] = mapped_column(Text, nullable=False)
    on_screen_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    asset_config_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    video_job = relationship("VideoJob", back_populates="scenes")