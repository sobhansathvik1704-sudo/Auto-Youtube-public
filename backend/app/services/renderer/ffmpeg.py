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
    # Shorts-format types
    "hook": ((10, 10, 40), (60, 0, 100)),               # very dark → deep purple
    "beat": ((5, 15, 45), (10, 50, 90)),                 # near-black navy → dark blue
    "takeaway": ((0, 40, 50), (0, 100, 70)),             # dark teal → emerald
    # Legacy types (kept for backward compatibility)
    "intro": ((15, 32, 120), (100, 20, 160)),            # blue → purple
    "outro": ((100, 20, 140), (200, 40, 100)),           # purple → pink
    "content": ((10, 60, 120), (20, 130, 160)),          # dark blue → teal
    "title_card": ((20, 60, 150), (80, 20, 180)),        # royal blue → deep purple
    "code_card": ((10, 40, 30), (20, 120, 60)),          # dark green → bright green
    "bullet_explainer": ((30, 80, 160), (10, 160, 180)), # cobalt → cyan
    "icon_compare": ((120, 30, 60), (200, 80, 20)),      # crimson → amber
}

# Accent / text colours for Shorts scene types
_HOOK_TEXT_COLOR: tuple[int, int, int, int] = (255, 220, 50, 255)      # bright yellow
_HOOK_ACCENT_COLOR: tuple[int, int, int, int] = (255, 200, 50, 200)    # warm yellow
_BEAT_TEXT_COLOR: tuple[int, int, int, int] = (255, 255, 255, 255)     # white
_BEAT_ACCENT_COLOR: tuple[int, int, int, int] = (0, 200, 255, 180)     # cyan
_TAKEAWAY_TEXT_COLOR: tuple[int, int, int, int] = (80, 255, 160, 255)  # emerald green
_TAKEAWAY_ACCENT_COLOR: tuple[int, int, int, int] = (0, 230, 120, 230) # bright green
_DEFAULT_GRADIENT = ((30, 60, 130), (20, 130, 160))  # visible blue → teal


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


def _draw_text_with_shadow(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple,
    shadow_offset: int = 2,
    shadow_fill: tuple = (0, 0, 0, 200),
) -> None:
    """Draw *text* at *xy* with a drop-shadow for better readability on photo backgrounds."""
    sx, sy = xy
    # Draw shadow first (slightly offset)
    draw.text((sx + shadow_offset, sy + shadow_offset), text, fill=shadow_fill, font=font)
    # Draw the main text on top
    draw.text(xy, text, fill=fill, font=font)


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
        # No code snippet available — fall through to standard card layout below

    # --- Background: try HuggingFace AI first, then Pexels, then Pollinations, then gradient ---
    scene_type_key = scene.scene_type.lower() if scene.scene_type else ""
    visual_prompt = scene.visual_prompt or scene.on_screen_text or scene.narration_text or scene.scene_type or ""

    # 1. HuggingFace AI image
    ai_image_path: Path | None = None
    if settings.image_provider == "huggingface" and settings.hf_api_token:
        from app.services.images.huggingface_provider import HuggingFaceImageProvider  # noqa: PLC0415

        hf_provider = HuggingFaceImageProvider(
            api_token=settings.hf_api_token,
            model=settings.hf_image_model,
            provider=settings.hf_inference_provider,
        )
        ai_tmp = output_path.with_suffix(".ai.png")
        ai_image_path = hf_provider.generate_image(visual_prompt, ai_tmp)
        if ai_image_path is not None:
            try:
                image = _open_and_fit_image(ai_image_path, width, height)
            except Exception as exc:
                logger.warning(
                    "Failed to open AI image %s: %s — trying next provider", ai_image_path, exc
                )
                ai_image_path = None

    # 2. Pexels stock photo (when HuggingFace is not used or failed)
    pexels_path: Path | None = None
    if ai_image_path is None and settings.image_provider == "pexels":
        pexels_tmp = output_path.with_suffix(".pexels.jpg")
        pexels_path = _fetch_pexels_background(scene, pexels_tmp)

        if pexels_path is not None:
            try:
                image = _open_and_fit_image(pexels_path, width, height)
            except Exception as exc:
                logger.warning("Failed to open Pexels image %s: %s — using gradient", pexels_path, exc)
                pexels_path = None

    # 3. Pollinations.ai (free, no API key required) – used when provider is
    #    "pollinations", or as automatic fallback when HuggingFace/Pexels fail.
    pollinations_path: Path | None = None
    if ai_image_path is None and pexels_path is None and settings.image_provider in ("pollinations", "huggingface", "pexels"):
        from app.services.images.pollinations_provider import PollinationsImageProvider  # noqa: PLC0415

        poll_provider = PollinationsImageProvider(
            model=getattr(settings, "pollinations_model", "flux"),
        )
        poll_tmp = output_path.with_suffix(".pollinations.jpg")
        pollinations_path = poll_provider.generate_image(visual_prompt, poll_tmp, width=width, height=height)
        if pollinations_path is not None:
            try:
                image = _open_and_fit_image(pollinations_path, width, height)
            except Exception as exc:
                logger.warning(
                    "Failed to open Pollinations image %s: %s — using gradient", pollinations_path, exc
                )
                pollinations_path = None

    # 4. Gradient fallback
    if ai_image_path is None and pexels_path is None and pollinations_path is None:
        color_top, color_bottom = _GRADIENT_SCHEMES.get(scene_type_key, _DEFAULT_GRADIENT)
        image = Image.new("RGB", (width, height))
        _draw_gradient_background(image, color_top, color_bottom)

    # Overlay layer for semi-transparent elements (RGBA composite).
    # Use a lighter (less opaque) card when a photo background is present so the
    # AI/Pexels/Pollinations image shows through clearly behind the text card.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    has_photo_bg = ai_image_path is not None or pexels_path is not None or pollinations_path is not None
    # Photo backgrounds: semi-transparent card (alpha=160) lets the image show through.
    # Plain gradient backgrounds: more opaque card (alpha=180) for maximum contrast.
    card_alpha = 160 if has_photo_bg else 180

    scale = min(width, height) / 1080  # normalise to shorter dimension
    padding = int(80 * scale)
    title_font_size = min(int(56 * scale), 68)
    body_font_size = min(int(32 * scale), 42)
    small_font_size = min(int(22 * scale), 30)

    title_font = _font(title_font_size, bold=True)
    body_font = _font(body_font_size, bold=False)
    small_font = _font(small_font_size, bold=False)

    scene_label = scene.scene_type.replace("_", " ").title()
    body_text = scene.on_screen_text or scene.narration_text or ""

    is_portrait = height > width

    # -----------------------------------------------------------------------
    # Local text normalisation helper (lowercase + strip punctuation +
    # collapse whitespace).  Keeps deduplication robust against minor
    # differences in casing, punctuation, or spacing.
    # -----------------------------------------------------------------------
    def _norm(t: str) -> str:
        lowered = t.lower()
        alphanum = "".join(ch if ch.isalnum() or ch == " " else " " for ch in lowered)
        return " ".join(alphanum.split())

    norm_label = _norm(scene_label)
    norm_body = _norm(body_text)

    # Never render internal scene-type labels (Intro, Outro, Bullet Explainer,
    # Icon Compare, etc.) to end users.  These labels are only used internally
    # for template selection and should not appear as visible video text.
    show_header = False

    # --- Shorts-format scene types: hook, beat, takeaway ---
    # These use a card-free design with large text directly on the background,
    # optimised for mobile readability and fast visual pacing.

    if scene_type_key == "hook":
        # HOOK: Bold centred question/statement in the middle of the screen.
        # No card — text sits directly on the AI background with a strong shadow.
        hook_font_size = min(int(72 * scale), 90)
        hook_font = _font(hook_font_size, bold=True)

        # Dark scrim across the whole frame so text pops on any background
        scrim = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        scrim_draw = ImageDraw.Draw(scrim)
        scrim_draw.rectangle([0, 0, width, height], fill=(0, 0, 0, 120))
        image = image.convert("RGBA")
        image = Image.alpha_composite(image, scrim)

        inner_w = int(width * 0.88)
        lines = _wrap_text(body_text, hook_font, inner_w)
        line_h = hook_font_size + int(18 * scale)
        total_h = len(lines) * line_h
        # Centre vertically in the upper 60% of the frame
        area_top = int(height * 0.20)
        area_bottom = int(height * 0.70)
        text_y = area_top + max(0, ((area_bottom - area_top) - total_h) // 2)
        for line in lines:
            lb = hook_font.getbbox(line)
            lx = (width - (lb[2] - lb[0])) // 2
            _draw_text_with_shadow(ov_draw, (lx, text_y), line,
                                   font=hook_font, fill=_HOOK_TEXT_COLOR,
                                   shadow_offset=4, shadow_fill=(0, 0, 0, 220))
            text_y += line_h

        # Thin accent bar at the very bottom of text block
        bar_y = text_y + int(8 * scale)
        bar_x0 = int(width * 0.25)
        bar_x1 = int(width * 0.75)
        ov_draw.rounded_rectangle([bar_x0, bar_y, bar_x1, bar_y + int(5 * scale)],
                                   radius=3, fill=_HOOK_ACCENT_COLOR)

    elif scene_type_key == "beat":
        # BEAT: Short phrase in large bold font placed in the lower third.
        # Mobile-safe zone. No card — clean text with shadow over AI background.
        beat_font_size = min(int(64 * scale), 80)
        beat_font = _font(beat_font_size, bold=True)

        inner_w = int(width * 0.90)
        lines = _wrap_text(body_text, beat_font, inner_w)
        line_h = beat_font_size + int(14 * scale)
        total_h = len(lines) * line_h

        # Place in the lower third (portrait: 58–85%)
        if is_portrait:
            zone_top = int(height * 0.58)
            zone_bottom = int(height * 0.88)
        else:
            zone_top = int(height * 0.55)
            zone_bottom = int(height * 0.90)

        # Semi-transparent pill behind the text block for readability
        pill_pad_x = int(28 * scale)
        pill_pad_y = int(18 * scale)
        pill_x0 = int(width * 0.05)
        pill_x1 = int(width * 0.95)
        pill_y0 = zone_top - pill_pad_y
        pill_y1 = zone_top + total_h + pill_pad_y
        _draw_rounded_rect(ov_draw, (pill_x0, pill_y0, pill_x1, pill_y1),
                           radius=18, fill=(0, 0, 0, 175))

        text_y = zone_top
        for line in lines:
            lb = beat_font.getbbox(line)
            lx = (width - (lb[2] - lb[0])) // 2
            _draw_text_with_shadow(ov_draw, (lx, text_y), line,
                                   font=beat_font, fill=_BEAT_TEXT_COLOR,
                                   shadow_offset=3, shadow_fill=(0, 0, 0, 200))
            text_y += line_h

        # Thin coloured accent bar above text pill
        bar_x0 = int(width * 0.30)
        bar_x1 = int(width * 0.70)
        bar_y = pill_y0 - int(8 * scale)
        ov_draw.rounded_rectangle([bar_x0, bar_y, bar_x1, bar_y + int(4 * scale)],
                                   radius=2, fill=_BEAT_ACCENT_COLOR)

    elif scene_type_key == "takeaway":
        # TAKEAWAY: Centred insight phrase with a distinct accent treatment.
        # Acts as the memorable conclusion — uses a bright accent colour.
        take_font_size = min(int(68 * scale), 84)
        take_font = _font(take_font_size, bold=True)

        # Scrim for contrast
        scrim2 = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        scrim2_draw = ImageDraw.Draw(scrim2)
        scrim2_draw.rectangle([0, 0, width, height], fill=(0, 0, 0, 100))
        image = image.convert("RGBA")
        image = Image.alpha_composite(image, scrim2)

        inner_w = int(width * 0.88)
        lines = _wrap_text(body_text, take_font, inner_w)
        line_h = take_font_size + int(16 * scale)
        total_h = len(lines) * line_h

        if is_portrait:
            area_top, area_bottom = int(height * 0.25), int(height * 0.75)
        else:
            area_top, area_bottom = int(height * 0.20), int(height * 0.80)

        text_y = area_top + max(0, ((area_bottom - area_top) - total_h) // 2)

        # Pill background
        pill_x0 = int(width * 0.04)
        pill_x1 = int(width * 0.96)
        pill_y0 = text_y - int(20 * scale)
        pill_y1 = text_y + total_h + int(20 * scale)
        _draw_rounded_rect(ov_draw, (pill_x0, pill_y0, pill_x1, pill_y1),
                           radius=20, fill=(0, 0, 0, 160))

        # Accent bar at top of pill
        ov_draw.rounded_rectangle([pill_x0, pill_y0, pill_x1, pill_y0 + int(6 * scale)],
                                   radius=4, fill=_TAKEAWAY_ACCENT_COLOR)

        for line in lines:
            lb = take_font.getbbox(line)
            lx = (width - (lb[2] - lb[0])) // 2
            _draw_text_with_shadow(ov_draw, (lx, text_y), line,
                                   font=take_font, fill=_TAKEAWAY_TEXT_COLOR,
                                   shadow_offset=3, shadow_fill=(0, 0, 0, 210))
            text_y += line_h

    elif scene_type_key == "intro":
        # Centred large title layout
        if is_portrait:
            card_x0, card_y0 = int(width * 0.04), int(height * 0.35)
            card_x1, card_y1 = int(width * 0.96), int(height * 0.90)
        else:
            card_x0, card_y0 = int(width * 0.08), int(height * 0.2)
            card_x1, card_y1 = int(width * 0.92), int(height * 0.8)
        _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, card_y1), radius=24, fill=(0, 0, 0, card_alpha))
        # Accent gradient bar at top
        ov_draw.rounded_rectangle(
            [card_x0, card_y0, card_x1, card_y0 + int(6 * scale)],
            radius=4, fill=(100, 160, 255, 220),
        )

        if show_header:
            # Title label — omitted when it would duplicate the body text
            label_bbox = title_font.getbbox(scene_label)
            label_w = label_bbox[2] - label_bbox[0]
            label_x = (width - label_w) // 2
            label_y = card_y0 + int(40 * scale)
            _draw_text_with_shadow(ov_draw, (label_x, label_y), scene_label,
                                   font=title_font, fill=(255, 220, 100, 255))

            # Divider line
            div_y = label_y + label_bbox[3] + int(20 * scale)
            ov_draw.line([(card_x0 + 40, div_y), (card_x1 - 40, div_y)], fill=(255, 255, 255, 120), width=2)
            body_top_intro = div_y + int(30 * scale)
        else:
            body_top_intro = card_y0 + int(40 * scale)

        # Body text centred
        inner_w = card_x1 - card_x0 - padding * 2
        lines = _wrap_text(body_text, body_font, inner_w)
        line_h = body_font_size + int(16 * scale)
        total_h = len(lines) * line_h
        text_y = body_top_intro + max(0, ((card_y1 - body_top_intro) - total_h) // 2)
        for line in lines:
            lb = body_font.getbbox(line)
            lx = card_x0 + (card_x1 - card_x0 - (lb[2] - lb[0])) // 2
            _draw_text_with_shadow(ov_draw, (lx, text_y), line, font=body_font, fill=(255, 255, 255, 245))
            text_y += line_h

    elif scene_type_key == "outro":
        # Call-to-action style layout
        if is_portrait:
            card_x0, card_y0 = int(width * 0.04), int(height * 0.35)
            card_x1, card_y1 = int(width * 0.96), int(height * 0.90)
        else:
            card_x0, card_y0 = int(width * 0.06), int(height * 0.15)
            card_x1, card_y1 = int(width * 0.94), int(height * 0.85)
        _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, card_y1), radius=24, fill=(0, 0, 0, card_alpha))

        # Accent bar at top of card
        ov_draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y0 + int(8 * scale)],
                                   radius=4, fill=(255, 80, 150, 220))

        if show_header:
            # Scene-type label — omitted when it would duplicate the body text
            label_bbox = title_font.getbbox(scene_label)
            label_w = label_bbox[2] - label_bbox[0]
            label_x = (width - label_w) // 2
            label_y = card_y0 + int(50 * scale)
            _draw_text_with_shadow(ov_draw, (label_x, label_y), scene_label,
                                   font=title_font, fill=(255, 160, 200, 255))
            body_top_outro = label_y + label_bbox[3] + int(40 * scale)
        else:
            body_top_outro = card_y0 + int(50 * scale)

        inner_w = card_x1 - card_x0 - padding * 2
        lines = _wrap_text(body_text, body_font, inner_w)
        line_h = body_font_size + int(16 * scale)
        text_y = body_top_outro
        for line in lines:
            lb = body_font.getbbox(line)
            lx = card_x0 + (card_x1 - card_x0 - (lb[2] - lb[0])) // 2
            _draw_text_with_shadow(ov_draw, (lx, text_y), line, font=body_font, fill=(255, 255, 255, 245))
            text_y += line_h

    else:
        # Card-based layout for content scenes (portrait: 45–93% of frame height)
        if is_portrait:
            card_x0, card_y0 = int(width * 0.04), int(height * 0.45)
            card_x1, card_y1 = int(width * 0.96), int(height * 0.93)
        else:
            card_x0, card_y0 = int(width * 0.05), int(height * 0.1)
            card_x1, card_y1 = int(width * 0.95), int(height * 0.9)
        _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, card_y1), radius=20, fill=(0, 0, 0, card_alpha))

        if show_header:
            # Header strip — one label badge, shown only when distinct from body
            header_y1 = card_y0 + int(90 * scale)
            _draw_rounded_rect(ov_draw, (card_x0, card_y0, card_x1, header_y1), radius=20, fill=(0, 100, 200, 200))

            # Truncate scene label to fit within the header
            max_label_w = card_x1 - card_x0 - padding * 2
            label_text = scene_label
            while title_font.getbbox(label_text)[2] > max_label_w and len(label_text) > 3:
                label_text = label_text[:-4] + "…"

            label_bbox = title_font.getbbox(label_text)
            label_y = card_y0 + (int(90 * scale) - (label_bbox[3] - label_bbox[1])) // 2
            _draw_text_with_shadow(ov_draw, (card_x0 + padding, label_y), label_text,
                                   font=title_font, fill=(255, 255, 255, 255))

            body_top = header_y1
        else:
            body_top = card_y0

        # Single primary text block — no hero/duplicate block beneath it
        inner_w = card_x1 - card_x0 - padding * 2
        lines = _wrap_text(body_text, body_font, inner_w)
        line_h = body_font_size + int(16 * scale)
        text_y = body_top + int(40 * scale)
        for line in lines:
            _draw_text_with_shadow(ov_draw, (card_x0 + padding, text_y), line,
                                   font=body_font, fill=(220, 240, 255, 245))
            text_y += line_h

        # Subtle border around card
        ov_draw.rounded_rectangle([card_x0, card_y0, card_x1, card_y1],
                                   radius=20, outline=(255, 255, 255, 70), width=2)

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


def _image_to_kenburns_clip(
    image_path: Path,
    duration_s: float,
    output_path: Path,
    width: int,
    height: int,
    effect: str | None = None,
) -> Path:
    """Convert a static image to an animated clip with a Ken Burns zoom/pan effect.

    *effect* may be one of ``"zoom_in"``, ``"zoom_out"``, ``"pan_right"``,
    ``"pan_left"``.  When ``None`` an effect is chosen at random.
    """
    import random  # noqa: PLC0415

    if effect is None:
        effect = random.choice(["zoom_in", "zoom_out", "pan_right", "pan_left"])

    fps = settings.video_render_fps
    total_frames = max(1, int(duration_s * fps))

    if effect == "zoom_in":
        zoompan = (
            f"zoompan=z='min(zoom+0.001,1.15)'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={total_frames}:s={width}x{height}:fps={fps}"
        )
    elif effect == "zoom_out":
        zoompan = (
            f"zoompan=z='if(lte(zoom,1.0),1.15,max(1.001,zoom-0.001))'"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
            f":d={total_frames}:s={width}x{height}:fps={fps}"
        )
    elif effect == "pan_right":
        zoompan = (
            f"zoompan=z='1.1'"
            f":x='if(lte(on,1),0,min(iw/1.1-iw/zoom,x+1))'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={total_frames}:s={width}x{height}:fps={fps}"
        )
    else:  # pan_left
        zoompan = (
            f"zoompan=z='1.1'"
            f":x='if(lte(on,1),iw/1.1-iw/zoom,max(0,x-1))'"
            f":y='ih/2-(ih/zoom/2)'"
            f":d={total_frames}:s={width}x{height}:fps={fps}"
        )

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-vf", zoompan,
        "-t", str(duration_s),
        "-pix_fmt", "yuv420p",
        "-c:v", "libx264",
        str(output_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output_path


def _concat_avatar_clips(
    scene_clips: list[Path],
    audio_path: Path,
    output_path: Path,
) -> None:
    """Concatenate D-ID avatar video clips and mix in TTS audio."""
    settings = get_settings()
    concat_file = output_path.parent / "avatar_concat.txt"
    with concat_file.open("w", encoding="utf-8") as fh:
        for clip in scene_clips:
            fh.write(f"file '{clip.as_posix()}'\n")

    cmd = [
        settings.ffmpeg_bin,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-i", str(audio_path),
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

        _concat_avatar_clips(scene_clips, audio_path, output_path)

    else:
        # --- Static slide path (default) ---
        scene_dir = ensure_dir(output_path.parent / "scene_frames")
        clips_dir = ensure_dir(output_path.parent / "kenburns_clips")

        total_scenes = len(scenes)
        concat_file = output_path.parent / "concat.txt"
        scene_clips: list[Path] = []

        for scene in scenes:
            scene_image = scene_dir / f"{scene.scene_index:03d}.png"
            create_scene_image(scene, width, height, scene_image, total_scenes=total_scenes)

            clip_path = clips_dir / f"scene_{scene.scene_index:03d}.mp4"
            duration_s = scene.duration_ms / 1000.0
            try:
                _image_to_kenburns_clip(scene_image, duration_s, clip_path, width, height)
            except Exception as exc:
                logger.warning(
                    "Ken Burns clip failed for scene %d (%s); using static loop",
                    scene.scene_index,
                    exc,
                )
                # Fallback: simple looped still image via concat demuxer entry (handled below)
                clip_path = scene_image  # flag: will be handled as a still in concat
            scene_clips.append(clip_path)

        # Build concat file for the per-scene clips
        with concat_file.open("w", encoding="utf-8") as handle:
            for scene, clip in zip(scenes, scene_clips):
                if clip.suffix == ".png":
                    # Fallback still image — write as a timed entry in the concat list
                    handle.write(f"file '{clip.as_posix()}'\n")
                    handle.write(f"duration {scene.duration_ms / 1000:.3f}\n")
                else:
                    handle.write(f"file '{clip.as_posix()}'\n")

            # Repeat last entry to avoid ffmpeg concat truncation
            if scene_clips:
                last = scene_clips[-1]
                handle.write(f"file '{last.as_posix()}'\n")

        # Add per-scene fade-in/fade-out transitions when clips are still images
        has_stills = any(c.suffix == ".png" for c in scene_clips)
        vf_filter: str | None = None
        if has_stills:
            fade_filter = _build_fade_filter(scenes)
            vf_filter = fade_filter if fade_filter else None

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
        ]
        if vf_filter:
            cmd.extend(["-vf", vf_filter])
        cmd.extend([
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
        ])
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