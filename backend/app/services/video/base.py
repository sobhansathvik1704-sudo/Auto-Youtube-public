"""Abstract base class for text-to-video providers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional


class VideoProvider(ABC):
    """Generate a short video clip from a text prompt."""

    @abstractmethod
    def generate_video(self, prompt: str, duration_s: float, output_path: Path) -> Optional[Path]:
        """Generate a video clip for *prompt* of roughly *duration_s* seconds.

        Returns *output_path* on success, or ``None`` if generation failed.
        """
