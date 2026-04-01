"""Tests for the HuggingFace image provider."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.images.huggingface_provider import (
    HuggingFaceImageProvider,
    _FALLBACK_MODELS,
    _FALLBACK_PROVIDERS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(
    token: str = "test-token",
    model: str = "black-forest-labs/FLUX.1-schnell",
    provider: str = "hf-inference",
) -> HuggingFaceImageProvider:
    return HuggingFaceImageProvider(api_token=token, model=model, provider=provider)


def _make_fake_image():
    """Return a mock PIL Image that can be saved."""
    fake_image = MagicMock()
    fake_image.save = MagicMock()
    return fake_image


# ---------------------------------------------------------------------------
# Tests: provider construction / configuration
# ---------------------------------------------------------------------------

def test_provider_stores_token_model_and_provider():
    token = "hf_secret_token"
    model = "black-forest-labs/FLUX.1-schnell"
    provider = "fal-ai"
    p = HuggingFaceImageProvider(api_token=token, model=model, provider=provider)
    assert p.api_token == token
    assert p.model == model
    assert p.provider == provider


def test_provider_default_provider_is_hf_inference():
    p = HuggingFaceImageProvider(api_token="tok", model="some/model")
    assert p.provider == "hf-inference"


def test_fallback_models_include_expected_models():
    """Verify the fallback model chain contains known working models."""
    assert "black-forest-labs/FLUX.1-schnell" in _FALLBACK_MODELS
    assert "stabilityai/stable-diffusion-xl-base-1.0" in _FALLBACK_MODELS
    assert "ByteDance/SDXL-Lightning" in _FALLBACK_MODELS
    assert "CompVis/stable-diffusion-v1-4" in _FALLBACK_MODELS


def test_fallback_providers_include_expected_providers():
    """Verify the fallback provider chain contains known providers."""
    assert "hf-inference" in _FALLBACK_PROVIDERS
    assert "fal-ai" in _FALLBACK_PROVIDERS
    assert "replicate" in _FALLBACK_PROVIDERS


def test_cinematic_prompt_is_prepended(tmp_path: Path):
    """The provider must prepend the cinematic prefix before sending to the API."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"

    captured_prompts: list = []

    def fake_text_to_image(prompt, model):  # noqa: ANN001
        captured_prompts.append(prompt)
        return _make_fake_image()

    mock_client = MagicMock()
    mock_client.text_to_image = fake_text_to_image

    with patch("huggingface_hub.InferenceClient", return_value=mock_client):
        provider.generate_image("space nebula", output_path)

    assert len(captured_prompts) == 1
    assert "cinematic" in captured_prompts[0]
    assert "space nebula" in captured_prompts[0]


# ---------------------------------------------------------------------------
# Tests: success path
# ---------------------------------------------------------------------------

def test_generate_image_success(tmp_path: Path):
    """On a successful call the image is saved and the path is returned."""
    provider = _make_provider()
    output_path = tmp_path / "scene.png"

    fake_image = _make_fake_image()
    mock_client = MagicMock()
    mock_client.text_to_image.return_value = fake_image

    with patch("huggingface_hub.InferenceClient", return_value=mock_client):
        result = provider.generate_image("a mountain", output_path)

    assert result == output_path
    fake_image.save.assert_called_once_with(str(output_path))


def test_generate_image_creates_parent_dirs(tmp_path: Path):
    """Parent directories are created if they don't exist."""
    provider = _make_provider()
    output_path = tmp_path / "nested" / "dir" / "scene.png"

    fake_image = _make_fake_image()
    mock_client = MagicMock()
    mock_client.text_to_image.return_value = fake_image

    with patch("huggingface_hub.InferenceClient", return_value=mock_client):
        result = provider.generate_image("prompt", output_path)

    assert result == output_path
    assert output_path.parent.exists()


# ---------------------------------------------------------------------------
# Tests: failure / fallback paths
# ---------------------------------------------------------------------------

def test_generate_image_returns_none_on_repeated_exception(tmp_path: Path):
    """If every attempt raises an exception for all models/providers, None is returned."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"

    mock_client = MagicMock()
    mock_client.text_to_image.side_effect = Exception("network error")

    with patch("huggingface_hub.InferenceClient", return_value=mock_client):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_falls_back_to_next_model(tmp_path: Path):
    """When the primary model fails, the provider tries the next fallback model."""
    primary_model = "black-forest-labs/FLUX.1-schnell"
    provider = _make_provider(model=primary_model)
    output_path = tmp_path / "out.png"

    fake_image = _make_fake_image()
    tried_models: list = []

    def fake_text_to_image(prompt, model):  # noqa: ANN001
        tried_models.append(model)
        if model == primary_model:
            raise Exception("model not available")
        return fake_image

    mock_client = MagicMock()
    mock_client.text_to_image = fake_text_to_image

    with patch("huggingface_hub.InferenceClient", return_value=mock_client):
        result = provider.generate_image("neon city", output_path)

    assert result == output_path
    assert primary_model in tried_models
    # A fallback model was also tried
    assert len(tried_models) >= 2


def test_generate_image_falls_back_to_next_provider(tmp_path: Path):
    """When all models fail on the primary provider, the next provider is tried."""
    provider = _make_provider(provider="hf-inference")
    output_path = tmp_path / "out.png"

    fake_image = _make_fake_image()
    tried_providers: list = []

    def fake_client_factory(provider, api_key):  # noqa: ANN001
        tried_providers.append(provider)
        mock_client = MagicMock()
        if provider == "hf-inference":
            mock_client.text_to_image.side_effect = Exception("provider down")
        else:
            mock_client.text_to_image.return_value = fake_image
        return mock_client

    with patch(
        "huggingface_hub.InferenceClient",
        side_effect=fake_client_factory,
    ):
        result = provider.generate_image("sunset", output_path)

    assert result == output_path
    assert "hf-inference" in tried_providers
    # A fallback provider was also tried
    assert len(tried_providers) >= 2


def test_generate_image_returns_none_when_all_providers_and_models_fail(tmp_path: Path):
    """If every model on every provider fails, None is returned without crashing."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"

    mock_client = MagicMock()
    mock_client.text_to_image.side_effect = Exception("410 gone")

    with patch("huggingface_hub.InferenceClient", return_value=mock_client):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_rate_limit_logged(tmp_path: Path, caplog):
    """429/rate limit errors are logged as warnings."""
    import logging  # noqa: PLC0415

    provider = _make_provider()
    output_path = tmp_path / "out.png"

    mock_client = MagicMock()
    mock_client.text_to_image.side_effect = Exception("429 rate limit exceeded")

    with caplog.at_level(logging.WARNING, logger="app.services.images.huggingface_provider"):
        with patch("huggingface_hub.InferenceClient", return_value=mock_client):
            result = provider.generate_image("anything", output_path)

    assert result is None
    assert any("rate" in r.message.lower() or "429" in r.message for r in caplog.records)


def test_generate_image_410_gone_logged(tmp_path: Path, caplog):
    """410/gone errors are logged as warnings."""
    import logging  # noqa: PLC0415

    provider = _make_provider()
    output_path = tmp_path / "out.png"

    mock_client = MagicMock()
    mock_client.text_to_image.side_effect = Exception("410 gone model removed")

    with caplog.at_level(logging.WARNING, logger="app.services.images.huggingface_provider"):
        with patch("huggingface_hub.InferenceClient", return_value=mock_client):
            result = provider.generate_image("anything", output_path)

    assert result is None
    assert any("gone" in r.message.lower() or "410" in r.message for r in caplog.records)


