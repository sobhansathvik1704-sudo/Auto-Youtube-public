"""Tests for the Ken Burns animation in ffmpeg.py (Part 2: dynamic video animations).

Validates that _image_to_kenburns_clip:
  - Calls FFmpeg with a valid zoompan filter for each supported effect
  - Chooses a random effect when None is provided
  - Passes correct output dimensions and duration to the filter
  - Propagates FFmpeg errors to the caller
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.renderer.ffmpeg import _image_to_kenburns_clip


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_image(tmp_path: Path, name: str = "scene.png") -> Path:
    p = tmp_path / name
    p.write_bytes(b"fake-image-bytes")
    return p


def _run_clip(tmp_path: Path, effect: str | None, duration: float = 4.0,
              width: int = 1080, height: int = 1920) -> tuple[Path, list]:
    """Run _image_to_kenburns_clip with a mocked subprocess.run and return
    (result_path, ffmpeg_cmd_list)."""
    image_path = _fake_image(tmp_path)
    output_path = tmp_path / "clip.mp4"

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = _image_to_kenburns_clip(
            image_path, duration, output_path, width, height, effect=effect
        )
        cmd = mock_run.call_args[0][0]  # first positional arg (the command list)

    return result, cmd


# ---------------------------------------------------------------------------
# Tests: return value
# ---------------------------------------------------------------------------

class TestKenBurnsReturnValue:
    def test_returns_output_path(self, tmp_path: Path):
        output_path = tmp_path / "clip.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _image_to_kenburns_clip(
                _fake_image(tmp_path), 4.0, output_path, 1080, 1920, effect="zoom_in"
            )
        assert result == output_path

    def test_returns_path_object(self, tmp_path: Path):
        output_path = tmp_path / "clip.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            result = _image_to_kenburns_clip(
                _fake_image(tmp_path), 4.0, output_path, 1080, 1920, effect="zoom_out"
            )
        assert isinstance(result, Path)


# ---------------------------------------------------------------------------
# Tests: FFmpeg is invoked
# ---------------------------------------------------------------------------

class TestKenBurnsFfmpegCall:
    def test_subprocess_is_called_once(self, tmp_path: Path):
        image_path = _fake_image(tmp_path)
        output_path = tmp_path / "clip.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _image_to_kenburns_clip(image_path, 4.0, output_path, 1080, 1920, "zoom_in")
        assert mock_run.call_count == 1

    def test_subprocess_called_with_check_true(self, tmp_path: Path):
        image_path = _fake_image(tmp_path)
        output_path = tmp_path / "clip.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _image_to_kenburns_clip(image_path, 4.0, output_path, 1080, 1920, "zoom_in")
        _, kwargs = mock_run.call_args
        assert kwargs.get("check") is True

    def test_command_contains_ffmpeg(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in")
        assert any("ffmpeg" in str(part) for part in cmd)

    def test_command_contains_image_path(self, tmp_path: Path):
        image_path = _fake_image(tmp_path)
        output_path = tmp_path / "clip.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _image_to_kenburns_clip(image_path, 4.0, output_path, 1080, 1920, "zoom_in")
        cmd = mock_run.call_args[0][0]
        assert str(image_path) in cmd

    def test_command_contains_output_path(self, tmp_path: Path):
        image_path = _fake_image(tmp_path)
        output_path = tmp_path / "clip.mp4"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            _image_to_kenburns_clip(image_path, 4.0, output_path, 1080, 1920, "zoom_in")
        cmd = mock_run.call_args[0][0]
        assert str(output_path) in cmd

    def test_command_contains_vf_flag(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in")
        assert "-vf" in cmd

    def test_command_contains_duration(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in", duration=5.0)
        assert "-t" in cmd
        t_idx = cmd.index("-t")
        assert cmd[t_idx + 1] == "5.0"

    def test_command_sets_yuv420p_pixel_format(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in")
        assert "-pix_fmt" in cmd
        idx = cmd.index("-pix_fmt")
        assert cmd[idx + 1] == "yuv420p"

    def test_command_uses_libx264(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in")
        assert "-c:v" in cmd
        idx = cmd.index("-c:v")
        assert cmd[idx + 1] == "libx264"


# ---------------------------------------------------------------------------
# Tests: zoompan filter content per effect
# ---------------------------------------------------------------------------

def _get_zoompan_filter(cmd: list) -> str:
    """Extract the zoompan filter string from the FFmpeg command list."""
    vf_idx = cmd.index("-vf")
    return cmd[vf_idx + 1]


class TestKenBurnsZoomInEffect:
    def test_zoom_in_uses_zoompan_filter(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in")
        assert "zoompan" in _get_zoompan_filter(cmd)

    def test_zoom_in_increases_zoom(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in")
        zoompan = _get_zoompan_filter(cmd)
        # zoom_in adds to the zoom value (zoom+)
        assert "zoom+" in zoompan

    def test_zoom_in_includes_dimension(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_in", width=1080, height=1920)
        zoompan = _get_zoompan_filter(cmd)
        assert "1080x1920" in zoompan


class TestKenBurnsZoomOutEffect:
    def test_zoom_out_uses_zoompan_filter(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_out")
        assert "zoompan" in _get_zoompan_filter(cmd)

    def test_zoom_out_decreases_zoom(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_out")
        zoompan = _get_zoompan_filter(cmd)
        # zoom_out starts high and decreases (zoom-0.001 or max(1.001,...))
        assert "zoom-0.001" in zoompan or "max(1.001" in zoompan

    def test_zoom_out_includes_dimension(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "zoom_out", width=1080, height=1920)
        zoompan = _get_zoompan_filter(cmd)
        assert "1080x1920" in zoompan


class TestKenBurnsPanRightEffect:
    def test_pan_right_uses_zoompan_filter(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_right")
        assert "zoompan" in _get_zoompan_filter(cmd)

    def test_pan_right_has_x_expression(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_right")
        zoompan = _get_zoompan_filter(cmd)
        assert "x=" in zoompan

    def test_pan_right_moves_rightward(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_right")
        zoompan = _get_zoompan_filter(cmd)
        # Pan right increments x: x+1
        assert "x+1" in zoompan

    def test_pan_right_includes_dimension(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_right", width=1080, height=1920)
        zoompan = _get_zoompan_filter(cmd)
        assert "1080x1920" in zoompan


class TestKenBurnsPanLeftEffect:
    def test_pan_left_uses_zoompan_filter(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_left")
        assert "zoompan" in _get_zoompan_filter(cmd)

    def test_pan_left_has_x_expression(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_left")
        zoompan = _get_zoompan_filter(cmd)
        assert "x=" in zoompan

    def test_pan_left_moves_leftward(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_left")
        zoompan = _get_zoompan_filter(cmd)
        # Pan left decrements x: x-1
        assert "x-1" in zoompan

    def test_pan_left_includes_dimension(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, "pan_left", width=1080, height=1920)
        zoompan = _get_zoompan_filter(cmd)
        assert "1080x1920" in zoompan


# ---------------------------------------------------------------------------
# Tests: random effect selection (effect=None)
# ---------------------------------------------------------------------------

class TestKenBurnsRandomEffect:
    def test_none_effect_produces_valid_zoompan(self, tmp_path: Path):
        _, cmd = _run_clip(tmp_path, None)
        zoompan = _get_zoompan_filter(cmd)
        assert "zoompan" in zoompan

    def test_none_effect_produces_variety_over_many_calls(self, tmp_path: Path):
        """With many calls using effect=None, multiple different effects should appear."""
        image_path = _fake_image(tmp_path)
        output_path = tmp_path / "clip.mp4"
        seen_filters: set[str] = set()

        for _ in range(30):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                _image_to_kenburns_clip(image_path, 4.0, output_path, 1080, 1920, effect=None)
                cmd = mock_run.call_args[0][0]
                zoompan = _get_zoompan_filter(cmd)
                # Record a prefix to distinguish effects
                seen_filters.add(zoompan[:40])

        # Expect at least 2 distinct effects across 30 runs
        assert len(seen_filters) >= 2, (
            f"Expected at least 2 distinct effects in 30 runs, got: {seen_filters}"
        )


# ---------------------------------------------------------------------------
# Tests: filter dimensions match requested width/height
# ---------------------------------------------------------------------------

class TestKenBurnsDimensions:
    @pytest.mark.parametrize("width,height", [
        (1080, 1920),   # portrait (Shorts)
        (1920, 1080),   # landscape
        (720, 1280),    # smaller portrait
    ])
    def test_filter_embeds_correct_dimensions(self, tmp_path: Path, width: int, height: int):
        _, cmd = _run_clip(tmp_path, "zoom_in", width=width, height=height)
        zoompan = _get_zoompan_filter(cmd)
        assert f"{width}x{height}" in zoompan


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------

class TestKenBurnsErrorHandling:
    def test_ffmpeg_error_propagates(self, tmp_path: Path):
        """If FFmpeg exits with an error, CalledProcessError should propagate."""
        image_path = _fake_image(tmp_path)
        output_path = tmp_path / "clip.mp4"

        with patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "ffmpeg"),
        ):
            with pytest.raises(subprocess.CalledProcessError):
                _image_to_kenburns_clip(
                    image_path, 4.0, output_path, 1080, 1920, effect="zoom_in"
                )

    def test_ffmpeg_file_not_found_propagates(self, tmp_path: Path):
        """If the ffmpeg binary is not found, FileNotFoundError should propagate."""
        image_path = _fake_image(tmp_path)
        output_path = tmp_path / "clip.mp4"

        with patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found")):
            with pytest.raises(FileNotFoundError):
                _image_to_kenburns_clip(
                    image_path, 4.0, output_path, 1080, 1920, effect="zoom_in"
                )
