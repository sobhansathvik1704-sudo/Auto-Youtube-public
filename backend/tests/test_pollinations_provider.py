"""Tests for the Pollinations.ai image provider."""

from pathlib import Path
from unittest.mock import MagicMock, call, patch

import httpx
import pytest

import app.services.images.pollinations_provider as _mod
from app.services.images.pollinations_provider import (
    PollinationsImageProvider,
    _MAX_RETRIES,
    _POLLINATIONS_BASE_URL,
)


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
        with patch("time.sleep"):
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
        with patch("time.sleep"):
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
        with patch("time.sleep"):
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
        with patch("time.sleep"):
            result = provider.generate_image("a beach", output_path)

    assert result == output_path
    assert output_path.read_bytes() == b"image-data"


def test_generate_image_creates_parent_dirs(tmp_path: Path):
    """Parent directories are created if they don't already exist."""
    provider = _make_provider()
    output_path = tmp_path / "nested" / "dir" / "scene.jpg"

    with patch("httpx.get", return_value=_make_fake_response(b"img")):
        with patch("time.sleep"):
            result = provider.generate_image("sunset", output_path)

    assert result == output_path
    assert output_path.parent.exists()


# ---------------------------------------------------------------------------
# Tests: failure paths
# ---------------------------------------------------------------------------

def test_generate_image_returns_none_on_http_error(tmp_path: Path):
    """HTTP error responses (raise_for_status) result in None."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    mock_resp = MagicMock()
    mock_resp.content = b"error"
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=mock_resp
    )

    with patch("httpx.get", return_value=mock_resp):
        with patch("time.sleep"):
            result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_returns_none_on_timeout(tmp_path: Path):
    """Timeout errors result in None after all retries (not propagated to caller)."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
        with patch("time.sleep"):
            result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_returns_none_on_request_error(tmp_path: Path):
    """Network request errors result in None."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with patch("httpx.get", side_effect=httpx.RequestError("connection refused")):
        with patch("time.sleep"):
            result = provider.generate_image("anything", output_path)

    assert result is None
    assert not output_path.exists()


def test_generate_image_returns_none_on_empty_response(tmp_path: Path):
    """An empty response body (no image data) results in None."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with patch("httpx.get", return_value=_make_fake_response(content=b"")):
        with patch("time.sleep"):
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
            with patch("time.sleep"):
                provider.generate_image("forest", output_path)

    assert any("pollinations" in r.message.lower() for r in caplog.records)


def test_generate_image_logs_warning_on_timeout(tmp_path: Path, caplog):
    """Timeout errors are logged as warnings."""
    import logging

    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    with caplog.at_level(logging.WARNING, logger="app.services.images.pollinations_provider"):
        with patch("httpx.get", side_effect=httpx.TimeoutException("timed out")):
            with patch("time.sleep"):
                provider.generate_image("anything", output_path)

    assert any("timed out" in r.message.lower() or "timeout" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# Tests: retry / exponential back-off
# ---------------------------------------------------------------------------

def test_retries_on_429(tmp_path: Path):
    """HTTP 429 triggers retries; success on a later attempt returns the path."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    # Build a 429 side-effect followed by a successful response.
    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=mock_429
    )

    success_resp = _make_fake_response(b"img-data")

    with patch("httpx.get", side_effect=[mock_429, success_resp]):
        with patch("time.sleep"):
            result = provider.generate_image("forest", output_path)

    assert result == output_path
    assert output_path.read_bytes() == b"img-data"


def test_retries_on_timeout(tmp_path: Path):
    """Timeout triggers retries; success on a later attempt returns the path."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    success_resp = _make_fake_response(b"img-bytes")

    with patch(
        "httpx.get",
        side_effect=[httpx.TimeoutException("timed out"), success_resp],
    ):
        with patch("time.sleep"):
            result = provider.generate_image("ocean", output_path)

    assert result == output_path


def test_exhausted_retries_returns_none(tmp_path: Path):
    """When all retry attempts are exhausted, None is returned."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    mock_429 = MagicMock()
    mock_429.status_code = 429
    mock_429.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429", request=MagicMock(), response=mock_429
    )

    # Return 429 for every attempt (_MAX_RETRIES + 1 total).
    with patch("httpx.get", return_value=mock_429):
        with patch("time.sleep"):
            result = provider.generate_image("desert", output_path)

    assert result is None
    assert not output_path.exists()


def test_non_429_http_error_does_not_retry(tmp_path: Path):
    """Non-429 HTTP errors (e.g. 500) are NOT retried – return None immediately."""
    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    mock_500 = MagicMock()
    mock_500.status_code = 500
    mock_500.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=MagicMock(), response=mock_500
    )

    with patch("httpx.get", return_value=mock_500) as mock_get:
        with patch("time.sleep"):
            result = provider.generate_image("anything", output_path)

    assert result is None
    # Only one attempt – no retries.
    assert mock_get.call_count == 1


def test_inter_request_delay_is_applied(tmp_path: Path):
    """A mandatory inter-request delay is applied when requests come too close together."""
    import app.services.images.pollinations_provider as mod

    provider = _make_provider()
    output_path = tmp_path / "out.jpg"

    # Freeze monotonic time so elapsed = 0 (i.e., last request was "just now").
    frozen_time = 1000.0
    with patch.object(mod, "_last_request_time", frozen_time):
        with patch("time.monotonic", return_value=frozen_time):
            with patch("time.sleep") as mock_sleep:
                with patch("httpx.get", return_value=_make_fake_response(b"img")):
                    provider.generate_image("city", output_path)

    # sleep should have been called at least once for the inter-request gap.
    assert mock_sleep.called
