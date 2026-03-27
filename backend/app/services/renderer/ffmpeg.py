import json
import logging
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models.asset import Asset
from app.db.models.scene import Scene
from app.db.models.video_job import VideoJob
from app.services.renderer.code_highlight import render_code_scene_image
from app.services.renderer.timeline import resolve_dimensions
from app.utils.fs import ensure_dir

logger = logging.getLogger(__name__)

settings = get_settings()

# Gradient colour schemes per scene type: (top-left colour, bottom-right colour)
_GRADIENT_SCHEMES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "intro": ((15, 32, 120), (100, 20, 160)),       # blue → purple
    "outro": ((100, 20, 140), (200, 40, 100)),       # purple → pink
    "content": ((10, 30, 80), (10, 100, 120)),       # dark blue → teal
}
_DEFAULT_GRADIENT = ((12, 24, 60), (20, 80, 100))


def _font(size: int, bold: bool = True):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _draw_gradient_background(image: Image.Image, color_top: tuple, color_bottom: tuple) -> None:
    """Fill *image* with a vertical linear gradient from color_top to color_bottom."""
    width, height = image.size
    draw = ImageDraw.Draw(image)
    for y in range(height):
        t = y / max(height - 1, 1)
        r = int(color_top[0] + (color_bottom[0] - color_top[0]) * t)
        g = int(color_top[1] + (color_bottom[1] - color_top[1]) * t)
        b = int(color_top[2] + (color_bottom[2] - color_top[2]) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, bbox: tuple, radius: int, fill: tuple) -> None:
    """Draw a filled rounded rectangle on *draw*."""
    x0, y0, x1, y1 = bbox
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill)


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    """Wrap *text* so that each line fits within *max_width* pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        bbox = font.getbbox(candidate)
        if bbox[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


_MIN_KEYWORD_LENGTH = 4  # skip words shorter than this when building a Pexels query
_MAX_KEYWORDS = 4       # maximum number of keywords extracted per scene


def _extract_search_query(scene: Scene) -> str:
    """Return a short keyword query derived from the scene content."""
    text = scene.on_screen_text or scene.narration_text or ""
    words = text.split()
    keywords = [w for w in words if len(w) > _MIN_KEYWORD_LENGTH][: _MAX_KEYWORDS]
    return " ".join(keywords) if keywords else (scene.scene_type or "nature")


def _fetch_pexels_background(scene: Scene, output_path: Path) -> Path | None:
    """Download a Pexels stock photo for the scene if Pexels is configured.

    Returns the downloaded image path, or ``None`` when Pexels is not
    enabled, the API key is missing, or the request fails.
    """
    if settings.image_provider != "pexels" or not settings.pexels_api_key:
        return None

    from app.services.images.pexels import PexelsImageProvider  # noqa: PLC0415

    provider = PexelsImageProvider(settings.pexels_api_key)
    query = _extract_search_query(scene)
    return provider.search_and_download(query, output_path)


def _open_and_fit_image(src_path: Path, width: int, height: int) -> Image.Image:
    """Open *src_path* and resize/crop it to fill exactly *width* × *height*."""
    img = Image.open(src_path).convert("RGB")
    src_w, src_h = img.size
    scale = max(width / src_w, height / src_h)
    new_w = int(src_w * scale)
    new_h = int(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - width) // 2
    top = (new_h - height) // 2
    img = img.crop((left, top, left + width, top + height))
    return img


def create_scene_image(
    scene: Scene,
    width: int,
    height: int,
    output_path: Path,
    total_scenes: int = 0,
) -> Path:
    if scene.scene_type == "code_card":
        asset_config = {}
        if scene.asset_config_json:
            try:
                asset_config = json.loads(scene.asset_config_json)
            except (json.JSONDecodeError, ValueError):
                asset_config = {}

        code_snippet = asset_config.get("code_snippet", "")
        code_language = asset_config.get("code_language", "")

        if code_snippet:
            title = f"{code_language or 'Code'} snippet"
            return render_code_scene_image(
                code=code_snippet,
                language=code_language,
                title=title,
                width=width,
                height=height,
                output_path=output_path,
            )

    # --- Background: try Pexels first, fall back to gradient ---
    scene_type_key = scene.scene_type.lower() if scene.scene_type else ""

    pexels_tmp = output_path.with_suffix(".pexels.jpg")
    pexels_path = _fetch_pexels_background(scene, pexels_tmp)

    if pexels_path is not None:
        try:
            image = _open_and_fit_image(pexels_path, width, height)
        except Exception as exc:
            logger.warning("Failed to open Pexels image %s: %s — using gradient", pexels_path, exc)
            pexels_path = None

    if pexels_path is None:
        color_top, color_bottom = _GRADIENT_SCHEMES.get(scene_type_key, _DEFAULT_GRADIENT)
        image = Image.new("RGB", (width, height))
        _draw_gradient_background(image, color_top, color_bottom)

    # Overlay layer for semi-transparent elements (RGBA composite).
    # When using a Pexels stock photo apply a full-frame dark veil first so that
    # text is always legible regardless of image content.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    if pexels_path is not None:
        ov_draw.rectangle([0, 0, width, height], fill=(0, 0, 0, 140))

    scale = height / 1080  # normalise to 1080p
    padding = int(80 * scale)
    title_font_size = int(60 * scale)
    body_font_size = int(34 * scale)
    small_font_size = int(24 * scale)

    title_font = _font(title_font_size, bold=True)
    body_font = _font(body_font_size, bold=False)
    small_font = _font(small_font_size, bold=False)

    scene_label = scene.scene_type.replace("_", " ").title()
    body_text = scene.on_screen_text or scene.narration_text or ""

    if scene_type_key == "intro":
        # Centred large title layout
        card_x0, card_y0 = int(width * 0.08), int(height * 0.2)
        card_x1, card_y1 = int(width * 0.92), int(height * 0.8)
        _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, card_y1), radius=24, fill=(0, 0, 0, 160))

        # Title label
        label_bbox = title_font.getbbox(scene_label)
        label_w = label_bbox[2] - label_bbox[0]
        label_x = (width - label_w) // 2
        label_y = card_y0 + int(40 * scale)
        ov_draw.text((label_x, label_y), scene_label, fill=(255, 220, 100, 255), font=title_font)

        # Divider line
        div_y = label_y + label_bbox[3] + int(20 * scale)
        ov_draw.line([(card_x0 + 40, div_y), (card_x1 - 40, div_y)], fill=(255, 255, 255, 100), width=2)

        # Body text centred
        inner_w = card_x1 - card_x0 - padding * 2
        lines = _wrap_text(body_text, body_font, inner_w)
        total_h = len(lines) * (body_font_size + int(14 * scale))
        text_y = div_y + int(30 * scale) + ((card_y1 - div_y - int(30 * scale)) - total_h) // 2
        for line in lines:
            lb = body_font.getbbox(line)
            lx = card_x0 + (card_x1 - card_x0 - (lb[2] - lb[0])) // 2
            ov_draw.text((lx, text_y), line, fill=(255, 255, 255, 245), font=body_font)
            text_y += body_font_size + int(14 * scale)

    elif scene_type_key == "outro":
        # Call-to-action style layout
        card_x0, card_y0 = int(width * 0.06), int(height * 0.15)
        card_x1, card_y1 = int(width * 0.94), int(height * 0.85)
        _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, card_y1), radius=24, fill=(0, 0, 0, 150))

        # Accent bar at top of card
        ov_draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y0 + int(8 * scale)],
                                   radius=4, fill=(255, 80, 150, 220))

        label_bbox = title_font.getbbox(scene_label)
        label_w = label_bbox[2] - label_bbox[0]
        label_x = (width - label_w) // 2
        label_y = card_y0 + int(50 * scale)
        ov_draw.text((label_x, label_y), scene_label, fill=(255, 160, 200, 255), font=title_font)

        inner_w = card_x1 - card_x0 - padding * 2
        lines = _wrap_text(body_text, body_font, inner_w)
        text_y = label_y + label_bbox[3] + int(40 * scale)
        for line in lines:
            lb = body_font.getbbox(line)
            lx = card_x0 + (card_x1 - card_x0 - (lb[2] - lb[0])) // 2
            ov_draw.text((lx, text_y), line, fill=(255, 255, 255, 245), font=body_font)
            text_y += body_font_size + int(14 * scale)

    else:
        # Card-based layout for content scenes
        card_x0, card_y0 = int(width * 0.05), int(height * 0.1)
        card_x1, card_y1 = int(width * 0.95), int(height * 0.9)
        _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, card_y1), radius=20, fill=(0, 0, 0, 140))

        # Header strip
        header_y1 = card_y0 + int(90 * scale)
        _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, header_y1), radius=20, fill=(0, 100, 200, 180))

        label_bbox = title_font.getbbox(scene_label)
        label_y = card_y0 + (int(90 * scale) - (label_bbox[3] - label_bbox[1])) // 2
        ov_draw.text((card_x0 + padding, label_y), scene_label, fill=(255, 255, 255, 255), font=title_font)

        # Body text left-aligned
        inner_w = card_x1 - card_x0 - padding * 2
        lines = _wrap_text(body_text, body_font, inner_w)
        text_y = header_y1 + int(40 * scale)
        for line in lines:
            ov_draw.text((card_x0 + padding, text_y), line, fill=(220, 235, 255, 245), font=body_font)
            text_y += body_font_size + int(14 * scale)

        # Subtle border around card
        ov_draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1],
                                   radius=20, outline=(255, 255, 255, 50), width=2)

    # --- Scene number indicator (top-right corner) ---
    if total_scenes > 0:
        indicator = f"{scene.scene_index + 1}/{total_scenes}"
    else:
        indicator = str(scene.scene_index + 1)
    ind_bbox = small_font.getbbox(indicator)
    ind_w = ind_bbox[2] - ind_bbox[0]
    ind_h = ind_bbox[3] - ind_bbox[1]
    ind_pad = int(12 * scale)
    ind_x = width - ind_w - ind_pad * 3
    ind_y = ind_pad * 2
    _draw_rounded_rect(ov_draw, (ind_x - ind_pad, ind_y - ind_pad // 2,
                                  ind_x + ind_w + ind_pad, ind_y + ind_h + ind_pad // 2),
                       radius=8, fill=(0, 0, 0, 140))
    ov_draw.text((ind_x, ind_y), indicator, fill=(200, 220, 255, 220), font=small_font)

    # Composite overlay onto background
    image = image.convert("RGBA")
    image = Image.alpha_composite(image, overlay)
    image = image.convert("RGB")

    image.save(output_path)
    return output_path


def _build_fade_filter(scenes: list[Scene]) -> str:
    """Build a vf filter string that adds 0.3s fade-out at scene end and fade-in at scene start."""
    fade_duration = 0.3
    parts: list[str] = []
    offset = 0.0
    for scene in scenes:
        duration = scene.duration_ms / 1000.0
        parts.append(f"fade=t=in:st={offset:.3f}:d={fade_duration}")
        # fade-out near end of this scene
        fade_out_start = offset + duration - fade_duration
        if fade_out_start > offset:
            parts.append(f"fade=t=out:st={fade_out_start:.3f}:d={fade_duration}")
        offset += duration
    return ",".join(parts)


def _concat_avatar_clips(
    scene_clips: list[Path],
    subtitles_path: Path,
    audio_path: Path,
    output_path: Path,
) -> None:
    """Concatenate D-ID avatar video clips, overlay subtitles, and mix in TTS audio."""
    settings = get_settings()
    concat_file = output_path.parent / "avatar_concat.txt"
    with concat_file.open("w", encoding="utf-8") as fh:
        for clip in scene_clips:
            fh.write(f"file '{clip.as_posix()}'\n")

    subtitle_filter = (
        f"subtitles={subtitles_path.as_posix()}"
        ":force_style='FontName=DejaVu Sans,FontSize=22,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "Outline=2,Shadow=1,BackColour=&H80000000,"
        "BorderStyle=4,MarginV=30'"
    )

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-i", str(audio_path),
        "-vf", subtitle_filter,
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]
    logger.debug("FFmpeg avatar concat command: %s", cmd)
    subprocess.run(cmd, check=True, capture_output=True)


def render_video(
    db: Session,
    job: VideoJob,
    scenes: list[Scene],
    audio_path: Path,
    subtitles_path: Path,
    output_path: Path,
) -> Path:
    from app.services.avatar.factory import get_avatar_provider
    from app.services.avatar.did_provider import DIDProvider

    width, height = resolve_dimensions(job)

    # Per-job avatar_mode takes precedence; fall back to global settings
    job_avatar_mode = getattr(job, "avatar_mode", None) or settings.avatar_provider
    avatar = get_avatar_provider(mode=job_avatar_mode)
    use_did = isinstance(avatar, DIDProvider)

    if use_did and isinstance(avatar, DIDProvider):
        # --- D-ID avatar path ---
        clips_dir = ensure_dir(output_path.parent / "avatar_clips")
        scene_clips: list[Path] = []

        for scene in scenes:
            clip_path = clips_dir / f"scene_{scene.scene_index:03d}.mp4"
            narration = scene.narration_text or scene.on_screen_text or ""
            try:
                logger.info(
                    "Generating D-ID avatar clip for scene %d", scene.scene_index
                )
                avatar.generate_scene_video(
                    scene_text=narration,
                    scene_index=scene.scene_index,
                    duration_hint_ms=scene.duration_ms,
                    output_path=clip_path,
                )
                scene_clips.append(clip_path)
            except Exception as exc:
                logger.warning(
                    "D-ID failed for scene %d (%s); falling back to static slide",
                    scene.scene_index,
                    exc,
                )
                # Fallback: generate a static image clip for this scene
                scene_dir = ensure_dir(output_path.parent / "scene_frames")
                scene_image = scene_dir / f"{scene.scene_index:03d}.png"
                create_scene_image(scene, width, height, scene_image, total_scenes=len(scenes))
                from app.services.avatar.static_provider import StaticAvatarProvider
                StaticAvatarProvider.image_to_clip(
                    image_path=scene_image,
                    duration_s=scene.duration_ms / 1000.0,
                    output_path=clip_path,
                )
                scene_clips.append(clip_path)

        _concat_avatar_clips(scene_clips, subtitles_path, audio_path, output_path)

    else:
        # --- Static slide path (default) ---
        scene_dir = ensure_dir(output_path.parent / "scene_frames")

        total_scenes = len(scenes)
        concat_file = output_path.parent / "concat.txt"
        image_paths: list[Path] = []

        with concat_file.open("w", encoding="utf-8") as handle:
            for scene in scenes:
                scene_image = scene_dir / f"{scene.scene_index:03d}.png"
                create_scene_image(scene, width, height, scene_image, total_scenes=total_scenes)
                image_paths.append(scene_image)

                handle.write(f"file '{scene_image.as_posix()}'\n")
                handle.write(f"duration {scene.duration_ms / 1000:.3f}\n")

        if image_paths:
            handle = concat_file.open("a", encoding="utf-8")
            handle.write(f"file '{image_paths[-1].as_posix()}'\n")
            handle.close()

        # Build subtitle filter with ASS-style force_style for better appearance
        subtitle_filter = (
            f"subtitles={subtitles_path.as_posix()}"
            ":force_style='FontName=DejaVu Sans,FontSize=22,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
            "Outline=2,Shadow=1,BackColour=&H80000000,"
            "BorderStyle=4,MarginV=30'"
        )

        # Add per-scene fade-in/fade-out transitions
        fade_filter = _build_fade_filter(scenes)
        vf_filter = f"{fade_filter},{subtitle_filter}" if fade_filter else subtitle_filter

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
            vf_filter,
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