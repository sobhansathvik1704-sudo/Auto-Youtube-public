"""Tests for the HuggingFace image provider."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.images.huggingface_provider import (
    HuggingFaceImageProvider,
    _FALLBACK_MODELS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(token: str = "test-token", model: str = "black-forest-labs/FLUX.1-schnell") -> HuggingFaceImageProvider:
    return HuggingFaceImageProvider(api_token=token, model=model)


# ---------------------------------------------------------------------------
# Tests: provider construction / configuration
# ---------------------------------------------------------------------------

def test_provider_builds_correct_api_url():
    model = "black-forest-labs/FLUX.1-schnell"
    provider = _make_provider(model=model)
    assert provider._api_url(model) == f"https://api-inference.huggingface.co/models/{model}"


def test_provider_sets_auth_header():
    token = "hf_secret_token"
    provider = _make_provider(token=token)
    assert provider.headers == {"Authorization": f"Bearer {token}"}


def test_cinematic_prompt_is_prepended(tmp_path: Path):
    """The provider must prepend the cinematic prefix before sending to the API."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"

    captured_payload: dict = {}

    def fake_post(url, **kwargs):  # noqa: ANN001, ANN003
        captured_payload.update(kwargs.get("json", {}))
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"\x89PNG\r\n"  # minimal fake PNG bytes
        resp.raise_for_status = MagicMock()
        return resp

    with patch("app.services.images.huggingface_provider.httpx.post", side_effect=fake_post):
        provider.generate_image("space nebula", output_path)

    assert "cinematic" in captured_payload["inputs"]
    assert "space nebula" in captured_payload["inputs"]


# ---------------------------------------------------------------------------
# Tests: success path
# ---------------------------------------------------------------------------

def test_generate_image_success(tmp_path: Path):
    """On a 200 response the image bytes are written and the path is returned."""
    provider = _make_provider()
    output_path = tmp_path / "scene.png"
    fake_bytes = b"FAKEIMAGE"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = fake_bytes
    mock_resp.raise_for_status = MagicMock()

    with patch("app.services.images.huggingface_provider.httpx.post", return_value=mock_resp):
        result = provider.generate_image("a mountain", output_path)

    assert result == output_path
    assert output_path.read_bytes() == fake_bytes


def test_generate_image_creates_parent_dirs(tmp_path: Path):
    """Parent directories are created if they don't exist."""
    provider = _make_provider()
    output_path = tmp_path / "nested" / "dir" / "scene.png"

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.content = b"IMG"
    mock_resp.raise_for_status = MagicMock()

    with patch("app.services.images.huggingface_provider.httpx.post", return_value=mock_resp):
        provider.generate_image("prompt", output_path)

    assert output_path.exists()


# ---------------------------------------------------------------------------
# Tests: failure / fallback paths
# ---------------------------------------------------------------------------

def test_generate_image_returns_none_on_repeated_exception(tmp_path: Path):
    """If every attempt raises an exception for all models, ``None`` is returned (no crash)."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"

    with patch(
        "app.services.images.huggingface_provider.httpx.post",
        side_effect=Exception("network error"),
    ), patch("app.services.images.huggingface_provider.time.sleep"):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_returns_none_on_http_error(tmp_path: Path):
    """A non-200 status that raises via raise_for_status should return ``None``."""
    import httpx  # noqa: PLC0415

    provider = _make_provider()
    output_path = tmp_path / "out.png"

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "Server error", request=MagicMock(), response=MagicMock()
    )

    with patch(
        "app.services.images.huggingface_provider.httpx.post", return_value=mock_resp
    ), patch("app.services.images.huggingface_provider.time.sleep"):
        result = provider.generate_image("anything", output_path)

    assert result is None


def test_generate_image_retries_on_503(tmp_path: Path):
    """503 (model loading) triggers a retry with a sleep, then succeeds."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"
    fake_bytes = b"IMG"

    loading_resp = MagicMock()
    loading_resp.status_code = 503
    loading_resp.json.return_value = {"estimated_time": 1}

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.content = fake_bytes
    ok_resp.raise_for_status = MagicMock()

    call_count = 0

    def side_effect(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        nonlocal call_count
        call_count += 1
        return loading_resp if call_count == 1 else ok_resp

    with patch(
        "app.services.images.huggingface_provider.httpx.post", side_effect=side_effect
    ), patch("app.services.images.huggingface_provider.time.sleep") as mock_sleep:
        result = provider.generate_image("prompt", output_path)

    assert result == output_path
    assert mock_sleep.called


def test_generate_image_retries_on_429(tmp_path: Path):
    """429 (rate limited) triggers exponential back-off then succeeds."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"
    fake_bytes = b"IMG"

    rate_resp = MagicMock()
    rate_resp.status_code = 429

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.content = fake_bytes
    ok_resp.raise_for_status = MagicMock()

    call_count = 0

    def side_effect(*args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        nonlocal call_count
        call_count += 1
        return rate_resp if call_count == 1 else ok_resp

    with patch(
        "app.services.images.huggingface_provider.httpx.post", side_effect=side_effect
    ), patch("app.services.images.huggingface_provider.time.sleep") as mock_sleep:
        result = provider.generate_image("prompt", output_path)

    assert result == output_path
    assert mock_sleep.called


def test_generate_image_410_falls_back_to_next_model(tmp_path: Path):
    """410 Gone on the primary model causes the provider to try the next fallback model."""
    primary_model = "black-forest-labs/FLUX.1-schnell"
    fallback_model = [m for m in _FALLBACK_MODELS if m != primary_model][0]
    provider = _make_provider(model=primary_model)
    output_path = tmp_path / "out.png"
    fake_bytes = b"IMG"

    gone_resp = MagicMock()
    gone_resp.status_code = 410

    ok_resp = MagicMock()
    ok_resp.status_code = 200
    ok_resp.content = fake_bytes
    ok_resp.raise_for_status = MagicMock()

    calls: list = []

    def side_effect(url, **kwargs):  # noqa: ANN001, ANN003
        calls.append(url)
        if primary_model in url:
            return gone_resp
        return ok_resp

    with patch("app.services.images.huggingface_provider.httpx.post", side_effect=side_effect):
        result = provider.generate_image("neon city", output_path)

    assert result == output_path
    assert output_path.read_bytes() == fake_bytes
    # Primary model was tried and rejected; at least one fallback was used
    assert any(primary_model in url for url in calls)
    assert any(fallback_model in url for url in calls)


def test_generate_image_returns_none_when_all_models_return_410(tmp_path: Path):
    """If every model returns 410 Gone, ``None`` is returned without crashing."""
    provider = _make_provider()
    output_path = tmp_path / "out.png"

    gone_resp = MagicMock()
    gone_resp.status_code = 410

    with patch("app.services.images.huggingface_provider.httpx.post", return_value=gone_resp):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()

