from app.core.config import get_settings
from app.services.avatar.base import BaseAvatarProvider


def get_avatar_provider(mode: str | None = None) -> BaseAvatarProvider:
    settings = get_settings()
    effective_mode = mode or settings.avatar_provider
    if effective_mode == "did":
        from app.services.avatar.did_provider import DIDProvider
        return DIDProvider()
    from app.services.avatar.static_provider import StaticAvatarProvider
    return StaticAvatarProvider()
