import json

from sqlalchemy.orm import Session

from app.db.models.scene import Scene
from app.db.models.script import Script
from app.db.models.video_job import VideoJob


def _build_visual_prompt(subject: str, topic: str) -> str:
    """Build an image generation prompt focused on the topic and subject matter.

    Deliberately avoids scene-type labels (e.g. 'bullet', 'intro') so image
    generators produce visuals relevant to the actual content rather than
    literal interpretations of internal scene names.
    """
    return (
        f"{topic}, {subject}, "
        "high quality, dramatic lighting, 4K, cinematic, professional photography, "
        "no text, no letters, no watermarks"
    )


def _scene_type_for_index(index: int, total: int, has_code: bool = False) -> str:
    """Return the scene type for a 1-based scene index out of *total* scenes.

    Rules:
    - First scene  → ``"intro"``
    - Last scene   → ``"outro"``
    - Middle scenes → alternate ``"bullet_explainer"`` / ``"icon_compare"``.
      ``"code_card"`` is only used when *has_code* is True.
    """
    if index == 1:
        return "intro"
    if index == total:
        return "outro"
    if has_code:
        return "code_card"
    # Alternate between the two content types for visual variety
    return "bullet_explainer" if (index % 2 == 0) else "icon_compare"


def generate_scenes_from_script(db: Session, job: VideoJob, script: Script) -> list[Scene]:
    payload = json.loads(script.structured_json)
    segments = payload.get("segments", [])
    total = len(segments)

    scenes: list[Scene] = []
    current_ms = 0

    for idx, segment in enumerate(segments, start=1):
        has_code = bool(segment.get("code_snippet", "").strip())
        scene_type = _scene_type_for_index(idx, total, has_code)
        duration_ms = int(segment.get("duration_seconds", 8) * 1000)

        asset_config: dict = {
            "template": scene_type,
            "background": "gradient_blue",
            "accent": "#00E5FF",
        }
        if scene_type == "code_card":
            asset_config["code_snippet"] = segment.get("code_snippet", "")
            asset_config["code_language"] = segment.get("code_language", "")

        scene_subject = segment.get("on_screen_text") or job.topic
        scene = Scene(
            video_job_id=job.id,
            scene_index=idx,
            scene_type=scene_type,
            narration_text=segment["narration"],
            on_screen_text=segment.get("on_screen_text"),
            visual_prompt=_build_visual_prompt(scene_subject, job.topic),
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