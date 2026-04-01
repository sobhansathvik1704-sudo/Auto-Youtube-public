import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Fallback chain: try each model in order until one succeeds.
_FALLBACK_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "stabilityai/stable-diffusion-xl-base-1.0",
    "ByteDance/SDXL-Lightning",
    "CompVis/stable-diffusion-v1-4",
]

# Fallback chain: try each provider in order until one succeeds.
_FALLBACK_PROVIDERS = [
    "hf-inference",
    "fal-ai",
    "replicate",
]


class HuggingFaceImageProvider:
    """Generate images via HuggingFace Inference Providers (new API)."""

    def __init__(
        self,
        api_token: str,
        model: str = "black-forest-labs/FLUX.1-schnell",
        provider: str = "hf-inference",
    ) -> None:
        self.api_token = api_token
        self.model = model
        self.provider = provider

    def generate_image(self, prompt: str, output_path: Path) -> Optional[Path]:
        """Generate a cinematic image. Returns output_path on success, None on failure."""
        cinematic_prompt = (
            f"cinematic, dramatic lighting, 4K, film still, professional photography, {prompt}"
        )

        models_to_try = [self.model] + [m for m in _FALLBACK_MODELS if m != self.model]
        providers_to_try = [self.provider] + [p for p in _FALLBACK_PROVIDERS if p != self.provider]

        for provider in providers_to_try:
            for model in models_to_try:
                result = self._try_generate(provider, model, cinematic_prompt, output_path, prompt)
                if result is not None:
                    return result

        logger.warning(
            "HuggingFace image generation failed for all models and providers for prompt: %.50s…",
            prompt,
        )
        return None

    def _try_generate(
        self, provider: str, model: str, cinematic_prompt: str, output_path: Path, original_prompt: str
    ) -> Optional[Path]:
        try:
            from huggingface_hub import InferenceClient  # noqa: PLC0415

            client = InferenceClient(provider=provider, api_key=self.api_token)

            logger.info(
                "Trying HuggingFace image generation: provider=%r model=%r prompt=%.50s…",
                provider, model, original_prompt,
            )

            image = client.text_to_image(
                cinematic_prompt,
                model=model,
            )

            output_path.parent.mkdir(parents=True, exist_ok=True)
            image.save(str(output_path))

            logger.info(
                "Generated AI image via provider=%r model=%r for prompt: %.50s… → %s",
                provider, model, original_prompt, output_path,
            )
            return output_path

        except Exception as exc:
            error_str = str(exc).lower()
            if "404" in error_str or "not found" in error_str or "not available" in error_str:
                logger.debug(
                    "Model %r not available on provider %r: %s", model, provider, exc
                )
            elif "429" in error_str or "rate" in error_str:
                logger.warning(
                    "Rate limited on provider=%r model=%r: %s", provider, model, exc
                )
            elif "410" in error_str or "gone" in error_str:
                logger.warning(
                    "Model %r is gone on provider %r: %s", model, provider, exc
                )
            else:
                logger.warning(
                    "HuggingFace error provider=%r model=%r: %s", provider, model, exc
                )
            return None
