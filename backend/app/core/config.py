from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "YouTube AI MVP"
    app_env: str = "development"
    debug: bool = True
    api_v1_prefix: str = "/api"

    secret_key: str
    access_token_expire_minutes: int = 60 * 24 * 7
    algorithm: str = "HS256"

    postgres_host: str = "db"
    postgres_port: int = 5432
    postgres_db: str = "youtube_ai"
    postgres_user: str = "youtube_ai"
    postgres_password: str = "youtube_ai"

    redis_url: str = "redis://redis:6379/0"
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    database_url: str
    cors_origins: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    artifacts_dir: str = "/tmp/youtube_ai_artifacts"
    storage_backend: str = "local"

    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_s3_bucket_name: str | None = None
    aws_region: str = "us-east-1"

    llm_provider: str = "local"
    llm_model: str = "local-fallback"
    openai_api_key: str | None = None
    openai_model_name: str = "gpt-4o"

    tts_provider: str = "local"
    tts_voice: str = "te-en-default"

    video_render_fps: int = 30
    short_video_width: int = 1080
    short_video_height: int = 1920
    long_video_width: int = 1920
    long_video_height: int = 1080

    ffmpeg_bin: str = "ffmpeg"
    ffprobe_bin: str = "ffprobe"

    code_snippet_font: str = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    code_snippet_font_size: int = 20

    youtube_client_secrets_file: str = "client_secrets.json"
    youtube_token_file: str = "youtube_token.json"

    # Avatar / Faceless Video
    avatar_provider: str = "static"  # "static" or "did"
    did_api_key: str = ""
    did_avatar_image_url: str = "https://create-images-results.d-id.com/DefaultPresenters/Noelle_f/image.jpeg"
    did_voice_provider: str = "microsoft"  # "microsoft" or "amazon"
    did_voice_id: str = "en-US-JennyNeural"  # Microsoft Azure voice
    thumbnail_provider: str = "pillow"  # "pillow" or "dalle"
    pexels_api_key: str = ""
    image_provider: str = "gradient"  # "huggingface", "pexels", or "gradient"
    hf_api_token: str = ""  # HuggingFace API token (free)
    hf_image_model: str = "stabilityai/stable-diffusion-xl-base-1.0"

    model_config = SettingsConfigDict(
        env_file=".env.example",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            import json
            return json.loads(value)
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()