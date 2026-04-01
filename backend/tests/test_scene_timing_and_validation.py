"""Tests for narration-synced scene timing and image validation utilities.

Covers:
- _get_audio_duration_ms() in tasks.py
- _is_valid_image() in renderer/ffmpeg.py
- scene duration update logic (constants + calculation)
"""

import struct
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers — reproduce key constants / logic from production modules without
# importing the full application stack (which requires running services).
# ---------------------------------------------------------------------------

# Mirror of production constants from tasks.py
_NARRATION_BUFFER_MS = 400
_MIN_SCENE_DURATION_MS = 2000


def _calc_scene_duration(audio_duration_ms: int, original_duration_ms: int) -> int:
    """Mirror of the duration-calculation logic in render_video_job."""
    if audio_duration_ms > 0:
        return max(_MIN_SCENE_DURATION_MS, audio_duration_ms + _NARRATION_BUFFER_MS)
    return max(_MIN_SCENE_DURATION_MS, original_duration_ms)


# ---------------------------------------------------------------------------
# Tests: duration calculation helper
# ---------------------------------------------------------------------------

class TestCalcSceneDuration:
    def test_normal_audio_adds_buffer(self):
        """Audio of 2800 ms → 2800 + 400 = 3200 ms."""
        assert _calc_scene_duration(2800, 4000) == 3200

    def test_short_audio_enforces_minimum(self):
        """Audio of 500 ms would produce 900 ms; minimum floor of 2000 ms applies."""
        assert _calc_scene_duration(500, 4000) == 2000

    def test_zero_audio_uses_original(self):
        """ffprobe failed (0 returned) → keep original duration."""
        assert _calc_scene_duration(0, 5000) == 5000

    def test_zero_audio_with_tiny_original_enforces_minimum(self):
        """ffprobe failed and original is too short → minimum floor."""
        assert _calc_scene_duration(0, 1000) == 2000

    def test_long_narration_keeps_full_duration(self):
        """Long narration of 8000 ms → 8400 ms (buffer respected)."""
        assert _calc_scene_duration(8000, 4000) == 8400

    def test_exactly_at_minimum_boundary(self):
        """Audio that produces exactly the minimum → minimum returned."""
        # 1600 + 400 = 2000 == minimum
        assert _calc_scene_duration(1600, 4000) == 2000

    def test_one_ms_above_minimum(self):
        """Audio that produces 2001 ms → 2001 (above floor)."""
        assert _calc_scene_duration(1601, 4000) == 2001


# ---------------------------------------------------------------------------
# Tests: _get_audio_duration_ms (unit tests using subprocess mock)
# ---------------------------------------------------------------------------

class TestGetAudioDurationMs:
    """Validate _get_audio_duration_ms without calling real ffprobe."""

    def _import_fn(self):
        from app.services.jobs.tasks import _get_audio_duration_ms
        return _get_audio_duration_ms

    def test_returns_duration_in_ms(self, tmp_path):
        fn = self._import_fn()
        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"\x00" * 64)

        mock_result = MagicMock()
        mock_result.stdout = "3.5\n"
        with patch("subprocess.run", return_value=mock_result):
            result = fn(fake_audio)
        assert result == 3500

    def test_returns_zero_on_subprocess_error(self, tmp_path):
        fn = self._import_fn()
        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"\x00" * 64)

        with patch("subprocess.run", side_effect=FileNotFoundError("ffprobe not found")):
            result = fn(fake_audio)
        assert result == 0

    def test_returns_zero_on_empty_output(self, tmp_path):
        fn = self._import_fn()
        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"\x00" * 64)

        mock_result = MagicMock()
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = fn(fake_audio)
        assert result == 0

    def test_returns_zero_on_non_numeric_output(self, tmp_path):
        fn = self._import_fn()
        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"\x00" * 64)

        mock_result = MagicMock()
        mock_result.stdout = "N/A\n"
        with patch("subprocess.run", return_value=mock_result):
            result = fn(fake_audio)
        assert result == 0

    def test_rounds_fractional_seconds(self, tmp_path):
        fn = self._import_fn()
        fake_audio = tmp_path / "test.mp3"
        fake_audio.write_bytes(b"\x00" * 64)

        mock_result = MagicMock()
        mock_result.stdout = "1.999\n"
        with patch("subprocess.run", return_value=mock_result):
            result = fn(fake_audio)
        # int(1.999 * 1000) == 1999
        assert result == 1999


# ---------------------------------------------------------------------------
# Tests: _is_valid_image
# ---------------------------------------------------------------------------

def _make_minimal_valid_png(path: Path) -> None:
    """Write a valid PNG large enough to pass the _MIN_IMAGE_BYTES size check.

    Uses a noisy (random-pixel) 100×100 RGB image so that PNG compression
    cannot shrink it below the 2048-byte minimum validated by _is_valid_image.
    """
    import random
    from PIL import Image as PILImage
    import io
    img = PILImage.new("RGB", (100, 100))
    pixels = [
        (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        for _ in range(100 * 100)
    ]
    img.putdata(pixels)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    path.write_bytes(buf.getvalue())


class TestIsValidImage:
    def _import_fn(self):
        from app.services.renderer.ffmpeg import _is_valid_image
        return _is_valid_image

    def test_valid_png_returns_true(self, tmp_path):
        fn = self._import_fn()
        p = tmp_path / "valid.png"
        _make_minimal_valid_png(p)
        assert fn(p) is True

    def test_missing_file_returns_false(self, tmp_path):
        fn = self._import_fn()
        p = tmp_path / "nonexistent.png"
        assert fn(p) is False

    def test_empty_file_returns_false(self, tmp_path):
        fn = self._import_fn()
        p = tmp_path / "empty.png"
        p.write_bytes(b"")
        assert fn(p) is False

    def test_tiny_file_returns_false(self, tmp_path):
        fn = self._import_fn()
        p = tmp_path / "tiny.png"
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # < 2048 bytes
        assert fn(p) is False

    def test_html_error_response_returns_false(self, tmp_path):
        fn = self._import_fn()
        p = tmp_path / "error.png"
        # Simulate an HTTP error page saved as an image file
        html = b"<html><body>404 Not Found</body></html>" * 60  # > 2048 bytes
        p.write_bytes(html)
        assert fn(p) is False

    def test_truncated_png_returns_false(self, tmp_path):
        fn = self._import_fn()
        p = tmp_path / "truncated.png"
        # Write PNG header but not a valid image
        p.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 3000)
        assert fn(p) is False
