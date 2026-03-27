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
        duration_ms = int(segment.get("duration_seconds", 8) * 1000)
        scene = Scene(
            video_job_id=job.id,
            scene_index=idx,
            scene_type=_scene_type_for_index(idx),
            narration_text=segment["narration"],
            on_screen_text=segment.get("on_screen_text"),
            visual_prompt=f"Tech/coding explainer scene for {job.topic}, style={_scene_type_for_index(idx)}",
            asset_config_json=json.dumps(
                {
                    "template": _scene_type_for_index(idx),
                    "background": "gradient_blue",
                    "accent": "#00E5FF",
                },
                ensure_ascii=False,
            ),
            duration_ms=duration_ms,
            start_ms=current_ms,
            end_ms=current_ms + duration_ms,
        )
        db.add(scene)
        db.flush()
        scenes.append(scene)
        current_ms += duration_ms

    return scenes