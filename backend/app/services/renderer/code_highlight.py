"""
Code snippet highlighting renderer using Pygments + Pillow.

Renders syntax-highlighted code blocks onto a Pillow Image with an
IDE-like visual style (Monokai-inspired dark theme).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pygments import lex
from pygments.lexers import get_lexer_by_name, TextLexer
from pygments.token import Token
from pygments.util import ClassNotFound

from app.core.config import get_settings

settings = get_settings()

# ---------------------------------------------------------------------------
# Colour palette (Monokai-inspired)
# ---------------------------------------------------------------------------
BG_COLOR = (30, 30, 30)
EDITOR_BG = (39, 40, 34)
TITLE_BAR_BG = (50, 50, 50)
GUTTER_BG = (45, 45, 45)
GUTTER_FG = (100, 100, 100)
LINE_NUMBER_FG = (90, 90, 90)
DEFAULT_FG = (248, 248, 242)  # Monokai default text

# Window control dot colours (macOS style)
DOT_RED = (255, 95, 86)
DOT_YELLOW = (255, 189, 46)
DOT_GREEN = (39, 201, 63)

# Token → colour mapping (Monokai subset)
TOKEN_COLORS: dict[type, tuple[int, int, int]] = {
    Token.Keyword: (249, 38, 114),
    Token.Keyword.Constant: (102, 217, 239),
    Token.Keyword.Declaration: (249, 38, 114),
    Token.Keyword.Namespace: (249, 38, 114),
    Token.Keyword.Type: (102, 217, 239),
    Token.Name.Builtin: (102, 217, 239),
    Token.Name.Class: (166, 226, 46),
    Token.Name.Decorator: (166, 226, 46),
    Token.Name.Exception: (166, 226, 46),
    Token.Name.Function: (166, 226, 46),
    Token.Literal.String: (230, 219, 116),
    Token.Literal.String.Doc: (117, 113, 94),
    Token.Literal.Number: (174, 129, 255),
    Token.Comment: (117, 113, 94),
    Token.Comment.Single: (117, 113, 94),
    Token.Comment.Multiline: (117, 113, 94),
    Token.Operator: (249, 38, 114),
    Token.Punctuation: (248, 248, 242),
}


def _resolve_token_color(ttype) -> tuple[int, int, int]:
    """Walk up the token hierarchy to find the nearest colour mapping."""
    while ttype is not Token:
        if ttype in TOKEN_COLORS:
            return TOKEN_COLORS[ttype]
        ttype = ttype.parent
    return DEFAULT_FG


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(settings.code_snippet_font, size=size)
    except Exception:
        return ImageFont.load_default()


def _get_lexer(language: str):
    """Return a Pygments lexer, falling back to plain-text if unknown."""
    if not language:
        return TextLexer()
    try:
        return get_lexer_by_name(language.lower(), stripall=True)
    except ClassNotFound:
        return TextLexer()


def _tokenize(code: str, language: str) -> list[tuple[tuple[int, int, int], str]]:
    """Return a flat list of (rgb_color, text) pairs for the code."""
    lexer = _get_lexer(language)
    result: list[tuple[tuple[int, int, int], str]] = []
    for ttype, value in lex(code, lexer):
        color = _resolve_token_color(ttype)
        result.append((color, value))
    return result


# Window control dot spacing / title font adjustment constants
_DOT_GAP_FACTOR = 3       # multiplied by dot_r to give spacing between dots
_TITLE_FONT_REDUCTION = 4  # points smaller than body font for title bar label

def render_code_scene_image(
    code: str,
    language: str,
    title: str,
    width: int,
    height: int,
    output_path: Path,
) -> Path:
    """
    Render a syntax-highlighted code block onto a Pillow image and save it.

    Parameters
    ----------
    code:
        The raw code string to display.
    language:
        Pygments language identifier (e.g. ``"python"``, ``"javascript"``).
    title:
        Label shown in the title bar (e.g. ``"example.py"``).
    width, height:
        Image dimensions in pixels.
    output_path:
        Destination ``.png`` file path.

    Returns
    -------
    Path
        The saved image path (same as *output_path*).
    """
    font_size = settings.code_snippet_font_size
    font = _load_font(font_size)

    # Measure character dimensions using a sample character
    sample_bbox = font.getbbox("W")
    char_w = sample_bbox[2] - sample_bbox[0]
    char_h = sample_bbox[3] - sample_bbox[1]
    line_h = int(char_h * 1.5)

    # Layout constants
    title_bar_h = max(48, int(height * 0.04))
    padding_x = max(20, int(width * 0.02))
    padding_y = max(12, int(height * 0.01))
    gutter_w = padding_x + char_w * 4  # room for 4-digit line numbers

    # Create image
    img = Image.new("RGB", (width, height), color=BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Outer rounded-ish border (just a slightly lighter bg rectangle)
    border_pad = max(16, int(min(width, height) * 0.015))
    draw.rectangle(
        [(border_pad, border_pad), (width - border_pad, height - border_pad)],
        fill=EDITOR_BG,
    )

    # Title bar
    title_bar_top = border_pad
    title_bar_bottom = border_pad + title_bar_h
    draw.rectangle(
        [(border_pad, title_bar_top), (width - border_pad, title_bar_bottom)],
        fill=TITLE_BAR_BG,
    )

    # Window control dots
    dot_r = max(7, int(title_bar_h * 0.22))
    dot_y = (title_bar_top + title_bar_bottom) // 2
    dot_x_start = border_pad + 18
    for color, offset in [(DOT_RED, 0), (DOT_YELLOW, dot_r * _DOT_GAP_FACTOR), (DOT_GREEN, dot_r * _DOT_GAP_FACTOR * 2)]:
        cx = dot_x_start + offset
        draw.ellipse(
            [(cx - dot_r, dot_y - dot_r), (cx + dot_r, dot_y + dot_r)],
            fill=color,
        )

    # Title text (language/filename label)
    title_label = title or (language.capitalize() if language else "Code")
    title_font = _load_font(max(14, font_size - _TITLE_FONT_REDUCTION))
    title_x = dot_x_start + dot_r * 10
    title_text_bbox = title_font.getbbox(title_label)
    title_text_h = title_text_bbox[3] - title_text_bbox[1]
    draw.text(
        (title_x, dot_y - title_text_h // 2),
        title_label,
        fill=(200, 200, 200),
        font=title_font,
    )

    # Code area boundaries
    code_area_top = title_bar_bottom + padding_y
    code_area_bottom = height - border_pad - padding_y
    code_area_left = border_pad
    code_area_right = width - border_pad

    # Gutter background
    draw.rectangle(
        [(code_area_left, code_area_top), (code_area_left + gutter_w, code_area_bottom)],
        fill=GUTTER_BG,
    )

    # Tokenise code
    if not code or not code.strip():
        code = "# (no code snippet provided)"

    tokens = _tokenize(code.rstrip(), language)

    # Split tokens into lines preserving token colors
    lines: list[list[tuple[tuple[int, int, int], str]]] = [[]]
    for color, text in tokens:
        parts = text.split("\n")
        for i, part in enumerate(parts):
            if part:
                lines[-1].append((color, part))
            if i < len(parts) - 1:
                lines.append([])

    # How many lines fit?
    available_height = code_area_bottom - code_area_top
    max_lines = max(1, available_height // line_h)
    truncated = len(lines) > max_lines
    visible_lines = lines[:max_lines]
    if truncated:
        visible_lines[-1] = [(GUTTER_FG, "... (truncated)")]

    # Render each line
    text_x_start = code_area_left + gutter_w + padding_x
    max_text_width = code_area_right - text_x_start - padding_x

    for line_no, line_tokens in enumerate(visible_lines, start=1):
        y = code_area_top + (line_no - 1) * line_h

        # Line number in gutter
        lineno_str = str(line_no)
        lineno_bbox = font.getbbox(lineno_str)
        lineno_w = lineno_bbox[2] - lineno_bbox[0]
        draw.text(
            (code_area_left + gutter_w - padding_x // 2 - lineno_w, y),
            lineno_str,
            fill=LINE_NUMBER_FG,
            font=font,
        )

        # Tokens on this line (clip to available width)
        x = text_x_start
        for color, text in line_tokens:
            if x >= code_area_right - padding_x:
                break
            bbox = font.getbbox(text)
            tw = bbox[2] - bbox[0]
            # If token would overflow, clip it
            if x + tw > code_area_right - padding_x:
                # Render as much as fits
                for clip in range(len(text), 0, -1):
                    clipped = text[:clip] + "…"
                    cb = font.getbbox(clipped)
                    if x + (cb[2] - cb[0]) <= code_area_right - padding_x:
                        draw.text((x, y), clipped, fill=color, font=font)
                        break
                break
            draw.text((x, y), text, fill=color, font=font)
            x += tw

    img.save(output_path)
    return output_path
