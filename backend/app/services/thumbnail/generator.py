"""Thumbnail generation service supporting DALL-E 3 and Pillow backends.

Set ``THUMBNAIL_PROVIDER=dalle`` to use DALL-E 3 (requires OpenAI credits).
The default ``pillow`` provider creates visually appealing thumbnails locally
with gradient backgrounds, bold title text, and design elements.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Gradient colour palettes keyed by video category
_CATEGORY_GRADIENTS: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
    "education": ((63, 94, 251), (252, 70, 107)),
    "technology": ((17, 153, 142), (56, 239, 125)),
    "entertainment": ((252, 74, 26), (247, 183, 51)),
    "gaming": ((114, 9, 183), (247, 37, 133)),
    "science": ((0, 176, 155), (150, 201, 61)),
    "business": ((30, 60, 114), (42, 82, 152)),
    "health": ((83, 203, 241), (0, 128, 255)),
    "default": ((106, 17, 203), (37, 117, 252)),
}

_FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _load_font(size: int):
    """Return a PIL font, falling back to the built-in default."""
    from PIL import ImageFont

    try:
        return ImageFont.truetype(_FONT_PATH, size)
    except (IOError, OSError):
        return ImageFont.load_default()


def _wrap_text(draw, text: str, font, max_width: int) -> list[str]:
    """Wrap *text* into lines that fit within *max_width* pixels."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


class PillowThumbnailGenerator:
    """Create a 1280×720 thumbnail locally with Pillow."""

    def generate(self, topic: str, output_path: Path, category: str = "default") -> Path:
        from PIL import Image, ImageDraw

        W, H = 1280, 720
        img = Image.new("RGB", (W, H))
        draw = ImageDraw.Draw(img)

        # --- Gradient background ---
        cat_key = category.lower() if category.lower() in _CATEGORY_GRADIENTS else "default"
        c_start, c_end = _CATEGORY_GRADIENTS[cat_key]
        for x in range(W):
            t = x / (W - 1)
            r = int(c_start[0] + (c_end[0] - c_start[0]) * t)
            g = int(c_start[1] + (c_end[1] - c_start[1]) * t)
            b = int(c_start[2] + (c_end[2] - c_start[2]) * t)
            draw.line([(x, 0), (x, H)], fill=(r, g, b))

        # --- Bottom vignette (dark fade for text contrast) ---
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ov_draw = ImageDraw.Draw(overlay)
        fade_start = H // 2
        for y in range(fade_start, H):
            alpha = int(200 * (y - fade_start) / (H - fade_start))
            ov_draw.line([(0, y), (W, y)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        # --- Decorative concentric rings (top-right) ---
        # Use solid-but-muted white so the rings show on any gradient without
        # alpha errors (the image is in RGB mode at this point).
        cx, cy = W - 140, 140
        for r in range(60, 180, 25):
            draw.ellipse(
                [(cx - r, cy - r), (cx + r, cy + r)],
                outline=(200, 200, 200),
                width=2,
            )

        # --- Play-button triangle ---
        ps = 36
        triangle = [
            (cx - ps // 2, cy - int(ps * 0.6)),
            (cx - ps // 2, cy + int(ps * 0.6)),
            (cx + int(ps * 0.8), cy),
        ]
        draw.polygon(triangle, fill=(255, 255, 255))

        # --- Title text ---
        title_font = _load_font(68)
        lines = _wrap_text(draw, topic, title_font, W - 120)[:3]
        line_h = 84
        y = H - 50 - len(lines) * line_h
        for line in lines:
            # Drop shadow (dark grey, RGB-safe — no alpha channel in RGB mode)
            draw.text((62, y + 3), line, font=title_font, fill=(30, 30, 30))
            draw.text((60, y), line, font=title_font, fill=(255, 255, 255))
            y += line_h

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "JPEG", quality=92)
        return output_path


class DalleThumbnailGenerator:
    """Generate a thumbnail using DALL-E 3, then overlay the title with Pillow."""

    def generate(self, topic: str, output_path: Path, category: str = "default") -> Path:
        from openai import OpenAI
        import httpx

        client = OpenAI()
        prompt = (
            f"YouTube thumbnail for a video about '{topic}'. "
            "Bold, colorful, eye-catching, modern design. "
            "No text in the image. Clean background with relevant imagery. "
            "Professional, high contrast, vibrant colors. 1280x720 aspect ratio."
        )
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",  # closest supported 16:9 size
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        img_data = httpx.get(image_url, timeout=30).content

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(img_data)
        return output_path


def _overlay_title(image_path: Path, title: str, output_path: Path) -> Path:
    """Overlay large bold title text on an existing image using a dark bottom bar."""
    from PIL import Image, ImageDraw

    img = Image.open(image_path).convert("RGB")
    W, H = img.size

    draw = ImageDraw.Draw(img)
    font = _load_font(60)
    lines = _wrap_text(draw, title, font, W - 100)[:3]

    bar_height = len(lines) * 76 + 44
    bar = Image.new("RGBA", (W, bar_height), (0, 0, 0, 160))
    img.paste(bar, (0, H - bar_height), bar)

    draw = ImageDraw.Draw(img)
    y = H - bar_height + 22
    for line in lines:
        draw.text((42, y + 2), line, font=font, fill=(0, 0, 0))
        draw.text((40, y), line, font=font, fill=(255, 255, 255))
        y += 76

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "JPEG", quality=92)
    return output_path


def generate_thumbnail(
    topic: str,
    output_path: Path,
    category: str = "default",
    provider: str = "pillow",
) -> Path:
    """Generate a YouTube thumbnail and save it to *output_path*.

    Args:
        topic: Video topic used for image generation and text overlay.
        output_path: Destination path for the JPEG thumbnail.
        category: Video category used to pick the Pillow gradient palette.
        provider: ``"pillow"`` (default, free) or ``"dalle"`` (requires credits).

    Returns:
        The resolved path where the thumbnail was saved.
    """
    if provider == "dalle":
        generator: DalleThumbnailGenerator | PillowThumbnailGenerator = DalleThumbnailGenerator()
        # Save raw DALL-E image, then overlay title text
        base_path = output_path.with_stem(output_path.stem + "_base")
        generator.generate(topic, base_path, category)
        return _overlay_title(base_path, topic, output_path)

    generator = PillowThumbnailGenerator()
    return generator.generate(topic, output_path, category)
