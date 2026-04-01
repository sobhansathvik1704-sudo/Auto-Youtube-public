"""Tests for the Replicate text-to-video provider."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from app.services.video.replicate_provider import ReplicateVideoProvider, _ANIME_SUFFIX


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(token: str = "test-token") -> ReplicateVideoProvider:
    return ReplicateVideoProvider(api_token=token)


def _status_response(status: str, output=None, error: str | None = None):
    """Return a mock httpx Response for a prediction status poll."""
    data = {"status": status}
    if output is not None:
        data["output"] = output
    if error is not None:
        data["error"] = error
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = data
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: construction
# ---------------------------------------------------------------------------

def test_provider_stores_token():
    p = _make_provider("my-secret-token")
    assert p.api_token == "my-secret-token"


# ---------------------------------------------------------------------------
# Tests: anime suffix
# ---------------------------------------------------------------------------

def test_anime_suffix_contains_ghibli():
    assert "studio ghibli" in _ANIME_SUFFIX.lower()


def test_anime_suffix_contains_anime():
    assert "anime" in _ANIME_SUFFIX.lower()


# ---------------------------------------------------------------------------
# Tests: generate_video success path
# ---------------------------------------------------------------------------

class TestGenerateVideoSuccess:
    def test_returns_output_path_on_success(self, tmp_path: Path):
        provider = _make_provider()
        out = tmp_path / "clip.mp4"

        create_resp = MagicMock()
        create_resp.status_code = 201
        create_resp.json.return_value = {"urls": {"get": "https://api.replicate.com/v1/predictions/abc"}}

        poll_resp = _status_response("succeeded", output="https://cdn.example.com/video.mp4")

        # Stub the download
        mock_iter_bytes = iter([b"fake-video-data"])
        download_resp = MagicMock()
        download_resp.status_code = 200
        download_resp.iter_bytes.return_value = mock_iter_bytes
        download_resp.__enter__ = lambda s: s
        download_resp.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = create_resp
        mock_client.get.return_value = poll_resp
        mock_client.stream.return_value = download_resp

        with patch("app.services.video.replicate_provider.httpx.Client", return_value=mock_client):
            result = provider.generate_video("a sunny meadow", 5.0, out)

        assert result == out
        assert out.exists()

    def test_prompt_includes_anime_suffix(self, tmp_path: Path):
        provider = _make_provider()
        captured_payloads = []

        create_resp = MagicMock()
        create_resp.status_code = 201
        create_resp.json.return_value = {"urls": {"get": "https://api.replicate.com/v1/predictions/xyz"}}

        poll_resp = _status_response("succeeded", output=["https://cdn.example.com/v.mp4"])

        download_resp = MagicMock()
        download_resp.status_code = 200
        download_resp.iter_bytes.return_value = iter([b"data"])
        download_resp.__enter__ = lambda s: s
        download_resp.__exit__ = MagicMock(return_value=False)

        def fake_post(url, json=None, headers=None):
            captured_payloads.append(json)
            return create_resp

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = fake_post
        mock_client.get.return_value = poll_resp
        mock_client.stream.return_value = download_resp

        with patch("app.services.video.replicate_provider.httpx.Client", return_value=mock_client):
            provider.generate_video("cherry blossoms", 4.0, tmp_path / "out.mp4")

        assert len(captured_payloads) == 1
        sent_prompt = captured_payloads[0]["input"]["prompt"]
        assert "cherry blossoms" in sent_prompt
        assert "anime" in sent_prompt.lower()

    def test_output_as_list_uses_first_url(self, tmp_path: Path):
        provider = _make_provider()
        out = tmp_path / "clip.mp4"

        create_resp = MagicMock()
        create_resp.status_code = 201
        create_resp.json.return_value = {"urls": {"get": "https://api.replicate.com/v1/predictions/abc"}}

        poll_resp = _status_response(
            "succeeded",
            output=["https://cdn.example.com/first.mp4", "https://cdn.example.com/second.mp4"],
        )

        download_resp = MagicMock()
        download_resp.status_code = 200
        download_resp.iter_bytes.return_value = iter([b"video"])
        download_resp.__enter__ = lambda s: s
        download_resp.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = create_resp
        mock_client.get.return_value = poll_resp
        mock_client.stream.return_value = download_resp

        with patch("app.services.video.replicate_provider.httpx.Client", return_value=mock_client):
            result = provider.generate_video("mountain scene", 5.0, out)

        assert result == out


# ---------------------------------------------------------------------------
# Tests: failure paths
# ---------------------------------------------------------------------------

class TestGenerateVideoFailures:
    def test_returns_none_on_prediction_creation_failure(self, tmp_path: Path):
        provider = _make_provider()

        create_resp = MagicMock()
        create_resp.status_code = 422
        create_resp.text = "Unprocessable Entity"

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = create_resp

        with patch("app.services.video.replicate_provider.httpx.Client", return_value=mock_client):
            result = provider.generate_video("test prompt", 5.0, tmp_path / "out.mp4")

        assert result is None

    def test_returns_none_on_prediction_failed_status(self, tmp_path: Path):
        provider = _make_provider()

        create_resp = MagicMock()
        create_resp.status_code = 201
        create_resp.json.return_value = {"urls": {"get": "https://api.replicate.com/v1/predictions/abc"}}

        poll_resp = _status_response("failed", error="Out of memory")

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = create_resp
        mock_client.get.return_value = poll_resp

        with patch("app.services.video.replicate_provider.httpx.Client", return_value=mock_client):
            result = provider.generate_video("test prompt", 5.0, tmp_path / "out.mp4")

        assert result is None

    def test_returns_none_on_download_http_error(self, tmp_path: Path):
        provider = _make_provider()

        create_resp = MagicMock()
        create_resp.status_code = 201
        create_resp.json.return_value = {"urls": {"get": "https://api.replicate.com/v1/predictions/abc"}}

        poll_resp = _status_response("succeeded", output="https://cdn.example.com/video.mp4")

        download_resp = MagicMock()
        download_resp.status_code = 404
        download_resp.__enter__ = lambda s: s
        download_resp.__exit__ = MagicMock(return_value=False)

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.return_value = create_resp
        mock_client.get.return_value = poll_resp
        mock_client.stream.return_value = download_resp

        with patch("app.services.video.replicate_provider.httpx.Client", return_value=mock_client):
            result = provider.generate_video("test prompt", 5.0, tmp_path / "out.mp4")

        assert result is None

    def test_returns_none_on_exception(self, tmp_path: Path):
        provider = _make_provider()

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = MagicMock(return_value=False)
        mock_client.post.side_effect = OSError("network error")

        with patch("app.services.video.replicate_provider.httpx.Client", return_value=mock_client):
            result = provider.generate_video("test prompt", 5.0, tmp_path / "out.mp4")

        assert result is None


# ---------------------------------------------------------------------------
# Tests: _get_video_provider in ffmpeg module
# ---------------------------------------------------------------------------

class TestGetVideoProvider:
    def test_returns_none_when_provider_is_none(self):
        from app.services.renderer.ffmpeg import _get_video_provider

        with patch("app.services.renderer.ffmpeg.settings") as mock_settings:
            mock_settings.video_provider = "none"
            result = _get_video_provider()

        assert result is None

    def test_returns_none_when_token_missing(self):
        from app.services.renderer.ffmpeg import _get_video_provider

        with patch("app.services.renderer.ffmpeg.settings") as mock_settings:
            mock_settings.video_provider = "replicate"
            mock_settings.replicate_api_token = ""
            result = _get_video_provider()

        assert result is None

    def test_returns_replicate_provider_when_configured(self):
        from app.services.renderer.ffmpeg import _get_video_provider

        with patch("app.services.renderer.ffmpeg.settings") as mock_settings:
            mock_settings.video_provider = "replicate"
            mock_settings.replicate_api_token = "r8_secret"
            result = _get_video_provider()

        assert isinstance(result, ReplicateVideoProvider)
        assert result.api_token == "r8_secret"
