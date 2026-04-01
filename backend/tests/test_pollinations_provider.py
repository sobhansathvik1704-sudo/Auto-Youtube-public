"""Tests for the Pollinations.ai image provider."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.images.pollinations_provider import PollinationsImageProvider, _POLLINATIONS_BASE_URL


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_provider(model: str = "flux") -> PollinationsImageProvider:
    return PollinationsImageProvider(model=model)


def _make_fake_response(content: bytes = b"fake-image-bytes", status_code: int = 200):
    """Return a mock httpx.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.content = content
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


# ---------------------------------------------------------------------------
# Tests: provider construction
# ---------------------------------------------------------------------------

def test_provider_default_model():
    """Default model is 'flux'."""
    p = PollinationsImageProvider()
    assert p.model == "flux"


def test_provider_custom_model():
    """Custom model is stored correctly."""
    p = PollinationsImageProvider(model="turbo")
    assert p.model == "turbo"


# ---------------------------------------------------------------------------
# Tests: URL construction
# ---------------------------------------------------------------------------

def test_generate_image_url_contains_prompt(tmp_path: Path):
    """The request URL must contain the encoded prompt."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    captured_urls: list[str] = []

    def fake_get(url, **kwargs):
        captured_urls.append(url)
        return _make_fake_response()

    with patch("httpx.get", side_effect=fake_get):
        provider.generate_image("mountain landscape", output_path)

    assert len(captured_urls) == 1
    assert "mountain" in captured_urls[0]
    assert _POLLINATIONS_BASE_URL in captured_urls[0]


def test_generate_image_url_contains_cinematic_prefix(tmp_path: Path):
    """The cinematic prefix must be included in the URL."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    captured_urls: list[str] = []

    def fake_get(url, **kwargs):
        captured_urls.append(url)
        return _make_fake_response()

    with patch("httpx.get", side_effect=fake_get):
        provider.generate_image("a forest", output_path)

    assert len(captured_urls) == 1
    assert "cinematic" in captured_urls[0].lower()


def test_generate_image_url_contains_dimensions(tmp_path: Path):
    """Width and height must appear in the URL query string."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    captured_urls: list[str] = []

    def fake_get(url, **kwargs):
        captured_urls.append(url)
        return _make_fake_response()

    with patch("httpx.get", side_effect=fake_get):
        provider.generate_image("a city", output_path, width=1920, height=1080)

    assert "width=1920" in captured_urls[0]
    assert "height=1080" in captured_urls[0]


# ---------------------------------------------------------------------------
# Tests: success path
# ---------------------------------------------------------------------------

def test_generate_image_success(tmp_path: Path):
    """On success the image bytes are written and the path is returned."""
    provider = _make_provider()
    output_path = tmp_path / "scene.jpg"

    with patch("httpx.get", return_value=_make_fake_response(b"image-data")):
        result = provider.generate_image("a beach", output_path)

    assert result == output_path
    assert output_path.read_bytes() == b"image-data"


def test_generate_image_creates_parent_dirs(tmp_path: Path):
    """Parent directories are created if they don't already exist."""
    provider = _make_provider()
    output_path = tmp_path / "nested" / "dir" / "scene.jpg"

    with patch("httpx.get", return_value=_make_fake_response(b"img")):
        result = provider.generate_image("sunset", output_path)

    assert result == output_path
    assert output_path.parent.exists()


# ---------------------------------------------------------------------------
# Tests: failure paths
# ---------------------------------------------------------------------------

def test_generate_image_returns_none_on_http_error(tmp_path: Path):
    """HTTP error responses (raise_for_status) result in None."""
    import httpx

    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    mock_resp = MagicMock()
    mock_resp.content = b"error"
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=mock_resp
    )

    with patch("httpx.get", return_value=mock_resp):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_returns_none_on_timeout(tmp_path: Path):
    """Timeout errors result in None (not an exception propagated to caller)."""
    import httpx

    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_returns_none_on_request_error(tmp_path: Path):
    """Network request errors result in None."""
    import httpx

    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with patch("httpx.get", side_effect=httpx.RequestError("connection refused")):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_returns_none_on_empty_response(tmp_path: Path):
    """An empty response body (no image data) results in None."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with patch("httpx.get", return_value=_make_fake_response(content=b"")):
        result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


# ---------------------------------------------------------------------------
# Tests: logging
# ---------------------------------------------------------------------------

def test_generate_image_logs_info_on_success(tmp_path: Path, caplog):
    """A successful generation is logged at INFO level."""
    import logging

    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with caplog.at_level(logging.INFO, logger="app.services.images.pollinations_provider"):
        with patch("httpx.get", return_value=_make_fake_response(b"img")):
            provider.generate_image("forest", output_path)

    assert any("pollinations" in r.message.lower() for r in caplog.records)


def test_generate_image_logs_warning_on_timeout(tmp_path: Path, caplog):
    """Timeout errors are logged as warnings."""
    import logging
    import httpx

    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with caplog.at_level(logging.WARNING, logger="app.services.images.pollinations_provider"):
        with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
            provider.generate_image("anything", output_path)

    assert any("timed out" in r.message.lower() or "timeout" in r.message.lower() for r in caplog.records)
