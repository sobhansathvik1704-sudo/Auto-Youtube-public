"""Replicate text-to-video provider.

Generates short MP4 video clips from a text prompt using the Replicate
Predictions API (https://replicate.com/docs/reference/http).  The
``replicate`` PyPI package is intentionally *not* used so that no new
runtime dependency is required; all communication is done through
``httpx`` which is already in requirements.txt.

Usage::

    provider = ReplicateVideoProvider(
        api_token="r8_...",
        model="minimax/video-01",
    )
    result = provider.generate_video("A serene anime mountain landscape", output_path)
    # result is a Path on success, or None on failure
"""

import logging
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Replicate REST API base URL
_API_BASE = "https://api.replicate.com/v1"

# How long to poll for a completed prediction before giving up (seconds)
_POLL_TIMEOUT_S = 300

# Interval between status-poll requests (seconds)
_POLL_INTERVAL_S = 5

# Minimum expected file size for a valid video (bytes)
_MIN_VIDEO_BYTES = 4096

# Appended to every prompt when anime style is requested
_ANIME_SUFFIX = (
    ", high quality masterpiece anime style, cinematic lighting, "
    "detailed backgrounds, studio ghibli aesthetic"
)


class ReplicateVideoProvider:
    """Generate short MP4 clips from text prompts via the Replicate API.

    Parameters
    ----------
    api_token:
        Your Replicate API token (``r8_…``).
    model:
        The Replicate model identifier in ``owner/name`` or
        ``owner/name:version`` format.  Defaults to ``minimax/video-01``.
    anime_style:
        When *True*, append anime-style keywords to every prompt.
    """

    def __init__(
        self,
        api_token: str,
        model: str = "minimax/video-01",
        anime_style: bool = True,
    ) -> None:
        self.api_token = api_token
        self.model = model
        self.anime_style = anime_style

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_video(
        self,
        prompt: str,
        output_path: Path,
    ) -> Optional[Path]:
        """Generate a video from *prompt* and save it to *output_path*.

        Returns *output_path* on success or ``None`` on any failure so
        that callers can fall back gracefully.
        """
        full_prompt = prompt + _ANIME_SUFFIX if self.anime_style else prompt

        logger.info(
            "Replicate video generation: model=%r prompt=%.80s…",
            self.model,
            full_prompt,
        )

        try:
            prediction_url = self._create_prediction(full_prompt)
            video_url = self._poll_prediction(prediction_url)
            if video_url is None:
                logger.warning("Replicate prediction did not return a video URL")
                return None
            return self._download_video(video_url, output_path)
        except Exception as exc:
            logger.warning("Replicate video generation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "Prefer": "wait",  # ask Replicate to hold the connection when possible
        }

    def _create_prediction(self, prompt: str) -> str:
        """POST a new prediction and return the polling URL."""
        payload: dict = {
            "input": {"prompt": prompt},
        }

        # If the model identifier contains a colon, it is pinned to a specific
        # version (owner/name:sha256) – use the /predictions endpoint.
        # Otherwise use the /models/{owner}/{name}/predictions endpoint which
        # always targets the latest deployed version.
        if ":" in self.model:
            _, version = self.model.split(":", 1)
            payload["version"] = version
            url = f"{_API_BASE}/predictions"
        else:
            owner, name = self.model.split("/", 1)
            url = f"{_API_BASE}/models/{owner}/{name}/predictions"

        with httpx.Client(timeout=60) as client:
            resp = client.post(url, json=payload, headers=self._headers())
            resp.raise_for_status()
            data = resp.json()

        # Replicate returns the polling URL in the "urls.get" field
        urls = data.get("urls", {})
        get_url = urls.get("get") or data.get("url")
        if not get_url:
            raise ValueError(f"Replicate prediction response missing polling URL: {data}")

        logger.debug("Replicate prediction created: %s", get_url)
        return get_url

    def _poll_prediction(self, prediction_url: str) -> Optional[str]:
        """Poll *prediction_url* until the prediction succeeds or times out.

        Returns the URL of the generated video, or ``None`` on failure.
        """
        deadline = time.monotonic() + _POLL_TIMEOUT_S

        with httpx.Client(timeout=30) as client:
            while time.monotonic() < deadline:
                resp = client.get(prediction_url, headers=self._headers())
                resp.raise_for_status()
                data = resp.json()

                status = data.get("status", "")
                logger.debug("Replicate prediction status: %s", status)

                if status == "succeeded":
                    output = data.get("output")
                    # output may be a URL string or a list of URLs
                    if isinstance(output, list) and output:
                        return output[0]
                    if isinstance(output, str) and output:
                        return output
                    logger.warning(
                        "Replicate prediction succeeded but output is empty: %s", data
                    )
                    return None

                if status in ("failed", "canceled"):
                    error = data.get("error", "unknown error")
                    logger.warning(
                        "Replicate prediction %s: %s", status, error
                    )
                    return None

                # Still running – wait before polling again
                time.sleep(_POLL_INTERVAL_S)

        logger.warning(
            "Replicate prediction timed out after %ds", _POLL_TIMEOUT_S
        )
        return None

    def _download_video(self, video_url: str, output_path: Path) -> Optional[Path]:
        """Download the video at *video_url* to *output_path*.

        Returns *output_path* on success, or ``None`` if the download
        produces an unexpectedly small file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with httpx.Client(timeout=120, follow_redirects=True) as client:
            with client.stream("GET", video_url) as resp:
                resp.raise_for_status()
                with output_path.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        fh.write(chunk)

        size = output_path.stat().st_size
        if size < _MIN_VIDEO_BYTES:
            logger.warning(
                "Downloaded video %s is suspiciously small (%d bytes); discarding",
                output_path,
                size,
            )
            output_path.unlink(missing_ok=True)
            return None

        logger.info("Replicate video saved to %s (%d bytes)", output_path, size)
        return output_path
