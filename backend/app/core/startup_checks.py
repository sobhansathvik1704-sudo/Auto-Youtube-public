"""Startup validation checks for the YouTube AI application.

Called from ``app.main`` on application startup to verify that all required
environment variables and credential files are present before the server
begins accepting traffic.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_SECRET_KEY_FRAGMENTS = {
    "replace-this",
    "your-secret",
    "changeme",
    "secret",
    "default",
}


def run_startup_checks() -> None:
    """Validate critical configuration and log warnings for optional items."""
    from app.core.config import get_settings  # avoid circular import at module load

    settings = get_settings()

    # ------------------------------------------------------------------ #
    # Required checks – log errors for missing critical config             #
    # ------------------------------------------------------------------ #

    # SECRET_KEY must be set and not a well-known placeholder
    secret_key_lower = settings.secret_key.lower()
    if any(fragment in secret_key_lower for fragment in _DEFAULT_SECRET_KEY_FRAGMENTS):
        logger.error(
            "SECRET_KEY looks like a placeholder value ('%s…'). "
            "Please replace it with a long random secret before deploying to production.",
            settings.secret_key[:20],
        )

    if not settings.database_url:
        logger.error("DATABASE_URL is not set. The application will fail to start.")

    # ------------------------------------------------------------------ #
    # Provider-specific checks                                             #
    # ------------------------------------------------------------------ #

    if settings.llm_provider == "openai":
        if not settings.openai_api_key:
            logger.error(
                "LLM_PROVIDER=openai but OPENAI_API_KEY is not set. "
                "Script generation will fail."
            )
        else:
            logger.info("LLM provider: OpenAI (model=%s)", settings.openai_model_name)
    else:
        logger.info("LLM provider: %s (local fallback – scripts will use placeholder content)", settings.llm_provider)

    if settings.tts_provider == "google":
        import os  # noqa: PLC0415
        creds_env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not creds_env:
            logger.warning(
                "TTS_PROVIDER=google but GOOGLE_APPLICATION_CREDENTIALS is not set. "
                "TTS synthesis will fail."
            )
        elif not Path(creds_env).exists():
            logger.warning(
                "TTS_PROVIDER=google but GOOGLE_APPLICATION_CREDENTIALS file does not exist: %s",
                creds_env,
            )
        else:
            logger.info("TTS provider: Google Cloud TTS (credentials=%s)", creds_env)
    else:
        logger.info("TTS provider: %s", settings.tts_provider)

    # ------------------------------------------------------------------ #
    # YouTube credential files (optional – warn if missing)               #
    # ------------------------------------------------------------------ #

    youtube_token = Path(settings.youtube_token_file)
    client_secrets = Path(settings.youtube_client_secrets_file)

    if not client_secrets.exists():
        logger.warning(
            "YouTube client_secrets.json not found at '%s'. "
            "YouTube upload will fail until OAuth credentials are provided.",
            client_secrets,
        )
    if not youtube_token.exists():
        logger.warning(
            "YouTube token file not found at '%s'. "
            "Run the OAuth flow once to generate it before attempting uploads.",
            youtube_token,
        )

    if client_secrets.exists() and youtube_token.exists():
        logger.info("YouTube credentials: OK (client_secrets=%s, token=%s)", client_secrets, youtube_token)

    # ------------------------------------------------------------------ #
    # Artifacts directory                                                  #
    # ------------------------------------------------------------------ #

    artifacts_dir = Path(settings.artifacts_dir)
    try:
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Artifacts directory: %s", artifacts_dir)
    except OSError as exc:
        logger.error("Cannot create artifacts directory '%s': %s", artifacts_dir, exc)

    logger.info(
        "Startup checks complete – app=%s env=%s storage=%s",
        settings.app_name,
        settings.app_env,
        settings.storage_backend,
    )
