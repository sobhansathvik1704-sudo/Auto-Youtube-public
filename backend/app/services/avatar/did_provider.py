import logging
import time
from pathlib import Path

import httpx

from app.core.config import get_settings
from app.services.avatar.base import BaseAvatarProvider

logger = logging.getLogger(__name__)


class DIDProvider(BaseAvatarProvider):
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.did_api_key
        self.avatar_url = settings.did_avatar_image_url
        self.voice_provider = settings.did_voice_provider
        self.voice_id = settings.did_voice_id
        self.base_url = "https://api.d-id.com"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate_scene_video(
        self,
        scene_text: str,
        scene_index: int,
        duration_hint_ms: int,
        output_path: Path,
    ) -> Path:
        logger.info("D-ID: creating talk for scene %d", scene_index)

        payload = {
            "source_url": self.avatar_url,
            "script": {
                "type": "text",
                "input": scene_text,
                "provider": {
                    "type": self.voice_provider,
                    "voice_id": self.voice_id,
                },
            },
            "config": {"stitch": True},
        }

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.base_url}/talks", json=payload, headers=self.headers
            )
            resp.raise_for_status()
            talk_id = resp.json()["id"]
            logger.info("D-ID: talk created id=%s for scene %d", talk_id, scene_index)

            # Poll for completion — check immediately then sleep 2s between retries (max 120s)
            for attempt in range(60):
                status_resp = client.get(
                    f"{self.base_url}/talks/{talk_id}", headers=self.headers
                )

                # Handle rate-limit with exponential back-off
                if status_resp.status_code == 429:
                    wait = 2 ** min(attempt, 5)
                    logger.warning(
                        "D-ID: rate-limited (429) for scene %d; retrying in %ds",
                        scene_index,
                        wait,
                    )
                    time.sleep(wait)
                    continue

                status_resp.raise_for_status()
                data = status_resp.json()
                status = data.get("status")

                if status == "done":
                    video_url = data["result_url"]
                    logger.info(
                        "D-ID: talk done for scene %d, downloading from %s",
                        scene_index,
                        video_url,
                    )
                    video_resp = client.get(video_url)
                    video_resp.raise_for_status()
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(video_resp.content)
                    logger.info(
                        "D-ID: scene %d saved to %s", scene_index, output_path
                    )
                    return output_path
                elif status == "error":
                    error_detail = data.get("error", "unknown")
                    raise RuntimeError(
                        f"D-ID talk generation failed for scene {scene_index}: {error_detail}"
                    )

                logger.debug(
                    "D-ID: scene %d status=%s (attempt %d/60)", scene_index, status, attempt + 1
                )
                time.sleep(2)

            raise TimeoutError(
                f"D-ID talk generation timed out after 120s for scene {scene_index}"
            )
