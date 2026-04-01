"""Replicate text-to-video provider.

Uses the ``minimax/video-01`` model on Replicate to generate short anime-style
video clips from text prompts.  Falls back gracefully when the API is
unavailable or the token is not configured.
"""

import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from app.services.video.base import VideoProvider

logger = logging.getLogger(__name__)

# Anime-style keywords appended to every prompt.
_ANIME_SUFFIX = (
    "high quality anime, studio ghibli style, animated, vibrant colors, "
    "smooth motion, cinematic"
)

# Replicate model used for text-to-video generation.
_MODEL_VERSION = "minimax/video-01"

# Maximum time to wait for the prediction to complete.
_POLL_TIMEOUT_S = 300
_POLL_INTERVAL_S = 5


class ReplicateVideoProvider(VideoProvider):
    """Generate short video clips via the Replicate API."""

    def __init__(self, api_token: str) -> None:
        self.api_token = api_token

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_video(self, prompt: str, duration_s: float, output_path: Path) -> Optional[Path]:
        """Generate an anime-style video for *prompt*.

        *duration_s* is a hint; the model generates a fixed-length clip
        (typically 5–6 s) so callers should trim/loop as needed.

        Returns *output_path* on success, ``None`` on failure.
        """
        anime_prompt = f"{prompt}, {_ANIME_SUFFIX}"
        logger.info("Replicate video generation: %.80s…", anime_prompt)

        try:
            prediction_url = self._create_prediction(anime_prompt)
            if prediction_url is None:
                return None

            video_url = self._wait_for_completion(prediction_url)
            if video_url is None:
                return None

            return self._download_video(video_url, output_path)
        except (httpx.HTTPError, httpx.RequestError, OSError, ValueError) as exc:
            logger.warning("Replicate video generation failed: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _create_prediction(self, prompt: str) -> Optional[str]:
        """Submit a prediction request and return its status URL."""
        payload = {
            "model": _MODEL_VERSION,
            "input": {"prompt": prompt},
        }
        with httpx.Client(timeout=60) as client:
            resp = client.post(
                "https://api.replicate.com/v1/predictions",
                json=payload,
                headers=self._auth_headers(),
            )
        if resp.status_code not in (200, 201):
            logger.warning(
                "Replicate prediction creation failed (HTTP %d): %s",
                resp.status_code,
                resp.text[:200],
            )
            return None
        data = resp.json()
        return data.get("urls", {}).get("get")

    def _wait_for_completion(self, status_url: str) -> Optional[str]:
        """Poll *status_url* until the prediction succeeds or fails."""
        deadline = time.monotonic() + _POLL_TIMEOUT_S
        with httpx.Client(timeout=30) as client:
            while time.monotonic() < deadline:
                resp = client.get(status_url, headers=self._auth_headers())
                if resp.status_code != 200:
                    logger.warning(
                        "Replicate poll failed (HTTP %d)", resp.status_code
                    )
                    return None
                data = resp.json()
                status = data.get("status")
                if status == "succeeded":
                    output = data.get("output")
                    # output may be a string URL or a list of URLs
                    if isinstance(output, list):
                        return output[0] if output else None
                    return output
                if status in ("failed", "canceled"):
                    logger.warning(
                        "Replicate prediction %s: %s",
                        status,
                        data.get("error", "unknown error"),
                    )
                    return None
                time.sleep(_POLL_INTERVAL_S)
        logger.warning("Replicate prediction timed out after %ds", _POLL_TIMEOUT_S)
        return None

    def _download_video(self, url: str, output_path: Path) -> Optional[Path]:
        """Download the video at *url* to *output_path*."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=120) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    logger.warning(
                        "Replicate video download failed (HTTP %d)", resp.status_code
                    )
                    return None
                with output_path.open("wb") as fh:
                    for chunk in resp.iter_bytes(chunk_size=8192):
                        fh.write(chunk)
        logger.info("Replicate video saved to %s", output_path)
        return output_path

    def _auth_headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_token}"}
