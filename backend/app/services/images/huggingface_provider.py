import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


class HuggingFaceImageProvider:
    """Generate cinematic images via the HuggingFace Inference API (free tier)."""

    def __init__(self, api_token: str, model: str = "stabilityai/stable-diffusion-xl-base-1.0") -> None:
        self.api_token = api_token
        self.model = model
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"
        self.headers = {"Authorization": f"Bearer {api_token}"}

    def generate_image(self, prompt: str, output_path: Path) -> Path | None:
        """Generate a cinematic image from *prompt*.

        Returns the local *output_path* on success, or ``None`` if all
        attempts fail so the caller can fall through to the next provider.
        """
        cinematic_prompt = (
            f"cinematic, dramatic lighting, 4K, film still, professional photography, {prompt}"
        )

        for attempt in range(3):
            try:
                resp = httpx.post(
                    self.api_url,
                    headers=self.headers,
                    json={
                        "inputs": cinematic_prompt,
                        "parameters": {"width": 1280, "height": 720},
                    },
                    timeout=60,
                )

                if resp.status_code == 503:
                    # Model is loading (cold start) — wait and retry
                    try:
                        wait = resp.json().get("estimated_time", 20)
                    except Exception:
                        wait = 20
                    wait = min(float(wait), 30)
                    logger.info(
                        "HuggingFace model loading, waiting %.0fs (attempt %d)…",
                        wait,
                        attempt + 1,
                    )
                    time.sleep(wait)
                    continue

                if resp.status_code == 429:
                    # Rate-limited — exponential back-off
                    wait = 2 ** attempt
                    logger.warning(
                        "HuggingFace rate limit (429) on attempt %d, retrying in %ds…",
                        attempt + 1,
                        wait,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(resp.content)
                logger.info(
                    "Generated AI image for prompt: %.50s… → %s", prompt, output_path
                )
                return output_path

            except Exception as exc:
                logger.warning(
                    "HuggingFace image generation attempt %d failed: %s", attempt + 1, exc
                )
                if attempt < 2:
                    time.sleep(2 ** attempt)

        logger.warning(
            "HuggingFace image generation failed after 3 attempts for prompt: %.50s…", prompt
        )
        return None
