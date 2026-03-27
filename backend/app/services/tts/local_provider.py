import subprocess
from pathlib import Path

from app.core.config import get_settings
from app.services.tts.base import BaseTTSProvider

settings = get_settings()


class LocalTTSProvider(BaseTTSProvider):
    def synthesize(self, text: str, output_path: Path) -> Path:
        # Local fallback: generate silent audio placeholder with FFmpeg.
        # Replace with Azure/Google/ElevenLabs provider for real TTS in production.
        duration = max(3, min(300, len(text.split()) // 2))
        cmd = [
            settings.ffmpeg_bin,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"anullsrc=r=44100:cl=stereo",
            "-t",
            str(duration),
            "-q:a",
            "9",
            "-acodec",
            "libmp3lame",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return output_path