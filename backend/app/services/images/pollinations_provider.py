"""Pollinations.ai image provider – free, no API key required."""

import logging
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Pollinations.ai public image-generation endpoint (no auth required).
_POLLINATIONS_BASE_URL = "https://image.pollinations.ai/prompt"

# Default model: "flux" produces high-quality cinematic results.
_DEFAULT_MODEL = "flux"

# Request timeout in seconds (image generation can be slow).
_TIMEOUT_S = 90

# Retry configuration for 429 / timeout errors.
_MAX_RETRIES = 4  # up to 4 retries (5 total attempts)
_RETRY_BASE_DELAY_S = 3.0  # initial back-off delay; doubles each attempt

# Minimum gap between consecutive requests to avoid overwhelming the API.
_INTER_REQUEST_DELAY_S = 3.0

# Module-level state protected by a lock for thread-safe inter-request pacing.
_rate_limit_lock = threading.Lock()
_last_request_time: float = 0.0


class PollinationsImageProvider:
    """Generate images via Pollinations.ai – completely free, no API key needed.

    The service accepts a URL-encoded text prompt and returns a PNG/JPEG image.
    API reference: https://image.pollinations.ai/
    """

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        self.model = model

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        width: int = 1920,
        height: int = 1080,
    ) -> Optional[Path]:
        """Generate an image from *prompt* and save it to *output_path*.

        Returns *output_path* on success, or ``None`` on failure.

        Retries up to *_MAX_RETRIES* times with exponential back-off on
        HTTP 429 (rate-limit) and timeout errors to handle transient
        Pollinations API failures gracefully.
        """
        global _last_request_time

        cinematic_prompt = (
            f"cinematic, dramatic lighting, 4K, film still, professional photography, {prompt}"
        )
        encoded = urllib.parse.quote(cinematic_prompt)
        url = (
            f"{_POLLINATIONS_BASE_URL}/{encoded}"
            f"?width={width}&height={height}&nologo=true&model={self.model}&seed=-1"
        )

        logger.info(
            "Generating Pollinations image (model=%r) for prompt: %.50s…", self.model, prompt
        )

        # Enforce a minimum gap between consecutive requests (thread-safe).
        with _rate_limit_lock:
            elapsed = time.monotonic() - _last_request_time
            if elapsed < _INTER_REQUEST_DELAY_S:
                time.sleep(_INTER_REQUEST_DELAY_S - elapsed)
            _last_request_time = time.monotonic()

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES + 1):
            if attempt > 0:
                delay = _RETRY_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.info(
                    "Retrying Pollinations image (attempt %d/%d) in %.1fs for prompt %.50s…",
                    attempt,
                    _MAX_RETRIES,
                    delay,
                    prompt,
                )
                time.sleep(delay)

            try:
                resp = httpx.get(url, timeout=_TIMEOUT_S, follow_redirects=True)
                resp.raise_for_status()
            except httpx.TimeoutException as exc:
                logger.warning(
                    "Pollinations image generation timed out for prompt %.50s… (attempt %d/%d): %s",
                    prompt,
                    attempt + 1,
                    _MAX_RETRIES + 1,
                    exc,
                )
                last_exc = exc
                continue
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429:
                    logger.warning(
                        "Pollinations returned HTTP 429 for prompt %.50s… (attempt %d/%d): %s",
                        prompt,
                        attempt + 1,
                        _MAX_RETRIES + 1,
                        exc,
                    )
                    last_exc = exc
                    continue
                logger.warning(
                    "Pollinations returned HTTP %s for prompt %.50s…: %s",
                    exc.response.status_code,
                    prompt,
                    exc,
                )
                return None
            except httpx.RequestError as exc:
                logger.warning(
                    "Pollinations request error for prompt %.50s…: %s", prompt, exc
                )
                return None

            if not resp.content:
                logger.warning("Pollinations returned empty response for prompt %.50s…", prompt)
                return None

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(resp.content)
            logger.info(
                "Pollinations image saved for prompt %.50s… → %s", prompt, output_path
            )
            return output_path

        # All attempts exhausted.
        logger.warning(
            "Pollinations image generation failed after %d attempts for prompt %.50s…: %s",
            _MAX_RETRIES + 1,
            prompt,
            last_exc,
        )
        return None
