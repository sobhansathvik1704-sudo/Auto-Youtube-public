from abc import ABC, abstractmethod
from pathlib import Path


class BaseAvatarProvider(ABC):
    @abstractmethod
    def generate_scene_video(
        self,
        scene_text: str,
        scene_index: int,
        duration_hint_ms: int,
        output_path: Path,
    ) -> Path:
        """Generate a video clip for a single scene. Returns path to the .mp4 clip."""
        ...
