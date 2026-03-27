from app.core.config import get_settings
from app.services.tts.base import BaseTTSProvider
from app.services.tts.local_provider import LocalTTSProvider

settings = get_settings()


def get_tts_provider() -> BaseTTSProvider:
    if settings.tts_provider == "local":
        return LocalTTSProvider()
    return LocalTTSProvider()