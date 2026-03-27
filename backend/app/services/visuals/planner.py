import json

from sqlalchemy.orm import Session

from app.db.models.scene import Scene
from app.db.models.script import Script
from app.db.models.video_job import VideoJob


def _scene_type_for_index(index: int) -> str:
    if index == 1:
        return "title_card"
    if index % 3 == 0:
        return "code_card"
    if index % 2 == 0:
        return "bullet_explainer"
    return "icon_compare"


def generate_scenes_from_script(db: Session, job: VideoJob, script: Script) -> list[Scene]:
    payload = json.loads(script.structured_json)
    segments = payload.get("segments", [])

    scenes: list[Scene] = []
    current_ms = 0

    for idx, segment in enumerate(segments, start=1):
        scene_type = _scene_type_for_index(idx)
        duration_ms = int(segment.get("duration_seconds", 8) * 1000)

        asset_config: dict = {
            "template": scene_type,
            "background": "gradient_blue",
            "accent": "#00E5FF",
        }
        if scene_type == "code_card":
            asset_config["code_snippet"] = segment.get("code_snippet", "")
            asset_config["code_language"] = segment.get("code_language", "")

        scene = Scene(
            video_job_id=job.id,
            scene_index=idx,
            scene_type=scene_type,
            narration_text=segment["narration"],
            on_screen_text=segment.get("on_screen_text"),
            visual_prompt=f"Tech/coding explainer scene for {job.topic}, style={scene_type}",
            asset_config_json=json.dumps(asset_config, ensure_ascii=False),
            duration_ms=duration_ms,
            start_ms=current_ms,
            end_ms=current_ms + duration_ms,
        )
        db.add(scene)
        db.flush()
        scenes.append(scene)
        current_ms += duration_ms

    return scenes