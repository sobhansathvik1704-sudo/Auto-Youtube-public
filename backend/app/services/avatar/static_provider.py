import logging
import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.services.avatar.base import BaseAvatarProvider
from app.utils.fs import ensure_dir

logger = logging.getLogger(__name__)


class StaticAvatarProvider(BaseAvatarProvider):
    """Generates a static slide image and converts it to a short MP4 clip using FFmpeg."""

    def generate_scene_video(
        self,
        scene_text: str,
        scene_index: int,
        duration_hint_ms: int,
        output_path: Path,
    ) -> Path:
        # This method is a stub; the main render_video() loop handles static slides
        # directly via create_scene_image + concat. We raise so callers know to use
        # the native pipeline instead.
        raise NotImplementedError(
            "StaticAvatarProvider does not support per-scene clip generation. "
            "Use the standard render_video() static path instead."
        )

    @staticmethod
    def image_to_clip(image_path: Path, duration_s: float, output_path: Path) -> Path:
        """Convert a static PNG image to a silent MP4 clip of the given duration."""
        settings = get_settings()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            settings.ffmpeg_bin,
            "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-t", f"{duration_s:.3f}",
            "-vf", "fps=30",
            "-pix_fmt", "yuv420p",
            "-c:v", "libx264",
            "-an",
            str(output_path),
        ]
        logger.debug("StaticAvatarProvider: converting image to clip: %s", cmd)
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path
