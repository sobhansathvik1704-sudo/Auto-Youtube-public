"""Tests for the Replicate text-to-video provider."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import httpx
import pytest

from app.services.videos.replicate_provider import (
    ReplicateVideoProvider,
    _ANIME_SUFFIX,
    _API_BASE,
    _MIN_VIDEO_BYTES,
    _POLL_TIMEOUT_S,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(
    token: str = "r8_test_token",
    model: str = "minimax/video-01",
    anime_style: bool = True,
) -> ReplicateVideoProvider:
    return ReplicateVideoProvider(api_token=token, model=model, anime_style=anime_style)


def _make_response(json_data: dict | None = None, status_code: int = 200) -> MagicMock:
    """Return a mock httpx.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data or {}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: construction
# ---------------------------------------------------------------------------

def test_provider_stores_token_model_and_anime_style():
    p = ReplicateVideoProvider(api_token="tok", model="owner/model", anime_style=False)
    assert p.api_token == "tok"
    assert p.model == "owner/model"
    assert p.anime_style is False


def test_provider_default_model_is_minimax():
    p = ReplicateVideoProvider(api_token="tok")
    assert p.model == "minimax/video-01"


def test_provider_default_anime_style_is_true():
    p = ReplicateVideoProvider(api_token="tok")
    assert p.anime_style is True


# ---------------------------------------------------------------------------
# Tests: _create_prediction
# ---------------------------------------------------------------------------

def test_create_prediction_uses_models_endpoint_for_unversioned_model():
    """For 'owner/name' models, the /models/{owner}/{name}/predictions endpoint is used."""
    provider = _make_provider(model="minimax/video-01")
    fake_resp = _make_response({
        "urls": {"get": "https://api.replicate.com/v1/predictions/abc123"},
    })
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = fake_resp

        result = provider._create_prediction("a rainy night in tokyo")

    assert result == "https://api.replicate.com/v1/predictions/abc123"
    post_url = mock_client.post.call_args[0][0]
    assert "/models/minimax/video-01/predictions" in post_url


def test_create_prediction_uses_predictions_endpoint_for_versioned_model():
    """For 'owner/name:sha' models, the /predictions endpoint is used and version is set."""
    provider = _make_provider(model="stability-ai/stable-video-diffusion:abc123def456")
    fake_resp = _make_response({
        "urls": {"get": "https://api.replicate.com/v1/predictions/xyz"},
    })
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = fake_resp

        result = provider._create_prediction("a calm forest")

    assert result == "https://api.replicate.com/v1/predictions/xyz"
    post_url = mock_client.post.call_args[0][0]
    assert post_url == f"{_API_BASE}/predictions"
    payload = mock_client.post.call_args[1]["json"]
    assert payload["version"] == "abc123def456"


def test_create_prediction_raises_if_no_polling_url():
    provider = _make_provider()
    fake_resp = _make_response({"id": "123"})  # no "urls" or "url" key
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.post.return_value = fake_resp

        with pytest.raises(ValueError, match="missing polling URL"):
            provider._create_prediction("some prompt")

# ---------------------------------------------------------------------------
# Tests: _poll_prediction
# ---------------------------------------------------------------------------

def test_poll_prediction_returns_url_on_success():
    provider = _make_provider()
    success_resp = _make_response({
        "status": "succeeded",
        "output": "https://cdn.replicate.com/video.mp4",
    })
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = success_resp

        result = provider._poll_prediction("https://api.replicate.com/v1/predictions/abc")

    assert result == "https://cdn.replicate.com/video.mp4"


def test_poll_prediction_returns_first_url_when_output_is_list():
    provider = _make_provider()
    success_resp = _make_response({
        "status": "succeeded",
        "output": ["https://cdn.replicate.com/video.mp4", "https://cdn.replicate.com/other.mp4"],
    })
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = success_resp

        result = provider._poll_prediction("https://api.replicate.com/v1/predictions/abc")

    assert result == "https://cdn.replicate.com/video.mp4"


def test_poll_prediction_returns_none_on_failed_status():
    provider = _make_provider()
    failed_resp = _make_response({"status": "failed", "error": "out of memory"})
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = failed_resp

        result = provider._poll_prediction("https://api.replicate.com/v1/predictions/abc")

    assert result is None


def test_poll_prediction_returns_none_on_canceled_status():
    provider = _make_provider()
    canceled_resp = _make_response({"status": "canceled"})
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.return_value = canceled_resp

        result = provider._poll_prediction("https://api.replicate.com/v1/predictions/abc")

    assert result is None


def test_poll_prediction_retries_on_processing_then_succeeds():
    provider = _make_provider()
    processing_resp = _make_response({"status": "processing"})
    success_resp = _make_response({
        "status": "succeeded",
        "output": "https://cdn.replicate.com/video.mp4",
    })
    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.get.side_effect = [processing_resp, success_resp]

        with patch("time.sleep"):  # speed up test
            result = provider._poll_prediction("https://api.replicate.com/v1/predictions/abc")

    assert result == "https://cdn.replicate.com/video.mp4"
    assert mock_client.get.call_count == 2


# ---------------------------------------------------------------------------
# Tests: generate_video (integration)
# ---------------------------------------------------------------------------

def test_generate_video_appends_anime_suffix_when_anime_style_true(tmp_path):
    provider = _make_provider(anime_style=True)
    prompt = "a serene mountain scene"

    with patch.object(provider, "_create_prediction", return_value="http://poll") as mock_create:
        with patch.object(provider, "_poll_prediction", return_value=None):
            provider.generate_video(prompt, tmp_path / "out.mp4")

    used_prompt = mock_create.call_args[0][0]
    assert _ANIME_SUFFIX in used_prompt
    assert prompt in used_prompt


def test_generate_video_does_not_append_suffix_when_anime_style_false(tmp_path):
    provider = _make_provider(anime_style=False)
    prompt = "a serene mountain scene"

    with patch.object(provider, "_create_prediction", return_value="http://poll") as mock_create:
        with patch.object(provider, "_poll_prediction", return_value=None):
            provider.generate_video(prompt, tmp_path / "out.mp4")

    used_prompt = mock_create.call_args[0][0]
    assert _ANIME_SUFFIX not in used_prompt
    assert used_prompt == prompt


def test_generate_video_returns_none_when_poll_returns_no_url(tmp_path):
    provider = _make_provider()
    with patch.object(provider, "_create_prediction", return_value="http://poll"):
        with patch.object(provider, "_poll_prediction", return_value=None):
            result = provider.generate_video("some prompt", tmp_path / "out.mp4")

    assert result is None


def test_generate_video_returns_none_on_exception(tmp_path):
    provider = _make_provider()
    with patch.object(provider, "_create_prediction", side_effect=RuntimeError("network error")):
        result = provider.generate_video("some prompt", tmp_path / "out.mp4")

    assert result is None


def test_generate_video_downloads_and_returns_path_on_success(tmp_path):
    provider = _make_provider()
    out_path = tmp_path / "out.mp4"

    with patch.object(provider, "_create_prediction", return_value="http://poll"):
        with patch.object(provider, "_poll_prediction", return_value="http://video.mp4"):
            with patch.object(
                provider, "_download_video", return_value=out_path
            ) as mock_dl:
                result = provider.generate_video("cool scene", out_path)

    mock_dl.assert_called_once_with("http://video.mp4", out_path)
    assert result == out_path


# ---------------------------------------------------------------------------
# Tests: _download_video
# ---------------------------------------------------------------------------

def test_download_video_saves_file_and_returns_path(tmp_path):
    provider = _make_provider()
    out_path = tmp_path / "video.mp4"
    fake_content = b"0" * (_MIN_VIDEO_BYTES + 100)

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_bytes.return_value = [fake_content]
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.stream.return_value = mock_response

        result = provider._download_video("https://cdn.example.com/video.mp4", out_path)

    assert result == out_path
    assert out_path.exists()
    assert out_path.stat().st_size >= _MIN_VIDEO_BYTES


def test_download_video_returns_none_for_tiny_file(tmp_path):
    provider = _make_provider()
    out_path = tmp_path / "video.mp4"
    tiny_content = b"x" * 10  # much smaller than _MIN_VIDEO_BYTES

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.iter_bytes.return_value = [tiny_content]
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("httpx.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value.__enter__.return_value
        mock_client.stream.return_value = mock_response

        result = provider._download_video("https://cdn.example.com/video.mp4", out_path)

    assert result is None
    assert not out_path.exists()
