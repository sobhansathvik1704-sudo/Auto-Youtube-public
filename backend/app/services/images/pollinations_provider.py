"""Pollinations.ai image provider – free, no API key required."""

import logging
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
        """
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

        try:
            resp = httpx.get(url, timeout=_TIMEOUT_S, follow_redirects=True)
            resp.raise_for_status()
        except httpx.TimeoutException as exc:
            logger.warning(
                "Pollinations image generation timed out for prompt %.50s…: %s", prompt, exc
            )
            return None
        except httpx.HTTPStatusError as exc:
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
