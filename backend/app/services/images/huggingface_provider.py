import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

# Fallback chain: try each model in order if the previous one returns 410 Gone.
_FALLBACK_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "CompVis/stable-diffusion-v1-4",
    "stabilityai/stable-diffusion-2-1",
]


class HuggingFaceImageProvider:
    """Generate cinematic images via the HuggingFace Inference API (free tier)."""

    def __init__(self, api_token: str, model: str = "black-forest-labs/FLUX.1-schnell") -> None:
        self.api_token = api_token
        self.model = model
        self.headers = {"Authorization": f"Bearer {api_token}"}

    def _api_url(self, model: str) -> str:
        return f"https://api-inference.huggingface.co/models/{model}"

    def generate_image(self, prompt: str, output_path: Path) -> Path | None:
        """Generate a cinematic image from *prompt*.

        Returns the local *output_path* on success, or ``None`` if all
        attempts fail so the caller can fall through to the next provider.

        If the configured model returns 410 Gone (permanently removed), the
        provider automatically tries each model in ``_FALLBACK_MODELS``.
        """
        cinematic_prompt = (
            f"cinematic, dramatic lighting, 4K, film still, professional photography, {prompt}"
        )

        # Build the ordered list of models to try: configured model first,
        # then any fallback models not already in the list.
        models_to_try = [self.model] + [m for m in _FALLBACK_MODELS if m != self.model]

        for model in models_to_try:
            result = self._try_model(model, cinematic_prompt, output_path, prompt)
            if result is not None:
                return result

        logger.warning(
            "HuggingFace image generation failed for all models for prompt: %.50s…", prompt
        )
        return None

    def _try_model(
        self, model: str, cinematic_prompt: str, output_path: Path, original_prompt: str
    ) -> Path | None:
        """Try to generate an image with a single *model*.  Returns the path on
        success, ``None`` on permanent failure (410) or exhausted retries.
        """
        api_url = self._api_url(model)

        for attempt in range(3):
            try:
                resp = httpx.post(
                    api_url,
                    headers=self.headers,
                    json={
                        "inputs": cinematic_prompt,
                        "parameters": {"width": 1280, "height": 720},
                    },
                    timeout=60,
                )

                if resp.status_code == 410:
                    # Model permanently removed — skip to the next fallback
                    logger.warning(
                        "HuggingFace model %r returned 410 Gone (model removed). "
                        "Update your HF_IMAGE_MODEL setting. Trying next fallback…",
                        model,
                    )
                    return None

                if resp.status_code == 503:
                    # Model is loading (cold start) — wait and retry
                    try:
                        wait = resp.json().get("estimated_time", 20)
                    except Exception:
                        wait = 20
                    wait = min(float(wait), 30)
                    logger.info(
                        "HuggingFace model %r loading, waiting %.0fs (attempt %d)…",
                        model,
                        wait,
                        attempt + 1,
                    )
                    time.sleep(wait)
                    continue

                if resp.status_code == 429:
                    # Rate-limited — exponential back-off
                    wait = 2 ** attempt
                    logger.warning(
                        "HuggingFace rate limit (429) on model %r attempt %d, retrying in %ds…",
                        model,
                        attempt + 1,
                        wait,
                    )
                    time.sleep(wait)
                    continue

                resp.raise_for_status()

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(resp.content)
                logger.info(
                    "Generated AI image via model %r for prompt: %.50s… → %s",
                    model,
                    original_prompt,
                    output_path,
                )
                return output_path

            except Exception as exc:
                logger.warning(
                    "HuggingFace image generation model %r attempt %d failed: %s",
                    model,
                    attempt + 1,
                    exc,
                )
                if attempt < 2:
                    time.sleep(2 ** attempt)

        logger.warning(
            "HuggingFace image generation failed after 3 attempts for model %r, prompt: %.50s…",
            model,
            original_prompt,
        )
        return None
