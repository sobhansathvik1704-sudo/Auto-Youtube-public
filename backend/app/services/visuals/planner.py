import json

from sqlalchemy.orm import Session

from app.db.models.scene import Scene
from app.db.models.script import Script
from app.db.models.video_job import VideoJob


def _build_visual_prompt(segment: dict, topic: str) -> str:
    """Build an image generation prompt for a segment.

    Prefers the segment's ``visual_concept`` field (set by the LLM) over a
    generic fallback so that each scene gets a distinct, concept-driven image
    rather than the same vague cyber-aesthetic every time.
    """
    visual_concept = (segment.get("visual_concept") or "").strip()
    if visual_concept:
        # Use the LLM-provided visual concept as the primary description
        return (
            f"{visual_concept}, "
            "photorealistic, high quality, dramatic lighting, 4K, cinematic, "
            "no text, no letters, no watermarks"
        )

    # Fallback: derive from on_screen_text / topic
    subject = (segment.get("on_screen_text") or "").strip() or topic
    return (
        f"{topic}, {subject}, "
        "high quality, dramatic lighting, 4K, cinematic, professional photography, "
        "no text, no letters, no watermarks"
    )


def _scene_type_for_segment(idx: int, total: int, purpose: str, has_code: bool = False) -> str:
    """Return the scene type for a 1-based segment index out of *total*.

    Shorts-format purposes (``hook``, ``beat``, ``takeaway``) are mapped
    directly.  Legacy purpose values (``intro``, ``explanation``, ``outro``,
    etc.) fall back to the old alternating scheme so existing content is
    unaffected.
    """
    if has_code:
        return "code_card"

    purpose_lower = (purpose or "").lower()

    # Shorts-format mapping
    if purpose_lower == "hook":
        return "hook"
    if purpose_lower == "takeaway":
        return "takeaway"
    if purpose_lower == "beat":
        return "beat"

    # Legacy fallback (intro / outro / explanation / comparison / …)
    if idx == 1:
        return "intro"
    if idx == total:
        return "outro"
    return "bullet_explainer" if (idx % 2 == 0) else "icon_compare"


def generate_scenes_from_script(db: Session, job: VideoJob, script: Script) -> list[Scene]:
    payload = json.loads(script.structured_json)
    segments = payload.get("segments", [])
    total = len(segments)

    scenes: list[Scene] = []
    current_ms = 0

    for idx, segment in enumerate(segments, start=1):
        has_code = bool(segment.get("code_snippet", "").strip())
        purpose = segment.get("purpose", "beat")
        scene_type = _scene_type_for_segment(idx, total, purpose, has_code)
        # Default 4 s per segment matches the Shorts-format target (2–5 s beats).
        # Legacy scripts that omit duration_seconds will use this 4 s default.
        duration_ms = int(segment.get("duration_seconds", 4) * 1000)

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
            visual_prompt=_build_visual_prompt(segment, job.topic),
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