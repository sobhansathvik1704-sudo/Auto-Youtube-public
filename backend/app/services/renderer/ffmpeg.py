import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.asset import Asset
from app.db.models.scene import Scene
from app.db.models.video_job import VideoJob
from app.services.renderer.timeline import resolve_dimensions
from app.utils.fs import ensure_dir

settings = get_settings()


def _font(size: int):
    try:
        return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size=size)
    except Exception:
        return ImageFont.load_default()


def create_scene_image(scene: Scene, width: int, height: int, output_path: Path) -> Path:
    image = Image.new("RGB", (width, height), color=(12, 24, 48))
    draw = ImageDraw.Draw(image)

    title_font = _font(56 if height >= 1000 else 42)
    body_font = _font(36 if height >= 1000 else 28)

    draw.rectangle([(0, 0), (width, 160)], fill=(0, 120, 255))
    draw.text((60, 50), scene.scene_type.replace("_", " ").title(), fill="white", font=title_font)

    text = scene.on_screen_text or scene.narration_text
    draw.multiline_text((60, 260), text, fill=(255, 255, 255), font=body_font, spacing=12)

    image.save(output_path)
    return output_path


def render_video(
    db: Session,
    job: VideoJob,
    scenes: list[Scene],
    audio_path: Path,
    subtitles_path: Path,
    output_path: Path,
) -> Path:
    width, height = resolve_dimensions(job)
    scene_dir = ensure_dir(output_path.parent / "scene_frames")

    concat_file = output_path.parent / "concat.txt"
    image_paths: list[Path] = []

    with concat_file.open("w", encoding="utf-8") as handle:
        for scene in scenes:
            scene_image = scene_dir / f"{scene.scene_index:03d}.png"
            create_scene_image(scene, width, height, scene_image)
            image_paths.append(scene_image)

            handle.write(f"file '{scene_image.as_posix()}'\n")
            handle.write(f"duration {scene.duration_ms / 1000:.3f}\n")

    if image_paths:
        handle = concat_file.open("a", encoding="utf-8")
        handle.write(f"file '{image_paths[-1].as_posix()}'\n")
        handle.close()

    subtitle_filter = f"subtitles={subtitles_path.as_posix()}"

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-i",
        str(audio_path),
        "-vf",
        subtitle_filter,
        "-r",
        str(settings.video_render_fps),
        "-pix_fmt",
        "yuv420p",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-shortest",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)

    asset = Asset(
        video_job_id=job.id,
        scene_id=None,
        asset_type="render_output",
        provider="ffmpeg",
        storage_key=str(output_path),
        metadata_json=json.dumps({"format": "mp4", "width": width, "height": height}),
    )
    db.add(asset)
    db.flush()

    return output_path