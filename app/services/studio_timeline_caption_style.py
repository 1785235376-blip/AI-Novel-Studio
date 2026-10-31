"""Closed, global VIDEO caption style; never accepts paths or filter syntax.

Font size uses libass reference units (the generated SRT default reference
canvas), not output pixels. The existing font fallback remains unchanged.
"""
from __future__ import annotations

import re


def normalize_caption_style(value):
    from .studio_timeline_render import _object, _integer
    row = _object(value, ("font_size", "primary_color", "alignment", "outline_width"),
                  ("font_size", "primary_color", "alignment", "outline_width"))
    color, alignment = row["primary_color"], row["alignment"]
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError("STUDIO_TIMELINE_CAPTION_COLOR_INVALID")
    if not isinstance(alignment, str) or alignment not in {"TOP_CENTER", "BOTTOM_CENTER"}:
        raise ValueError("STUDIO_TIMELINE_CAPTION_ALIGNMENT_INVALID")
    return {"font_size": _integer(row["font_size"], 8, 72),
            "primary_color": color.upper(), "alignment": alignment,
            "outline_width": _integer(row["outline_width"], 0, 4)}


def compile_caption_style(value):
    """Only fixed ASS keys and validated integer/hex values enter the filter."""
    row = normalize_caption_style(value)
    color = row["primary_color"][1:]
    bgr = color[4:6] + color[2:4] + color[0:2]
    # libass force_style uses its internal SSA alignment codes: 6 is
    # top-center (ASS event tag \an8 is NOT the force_style value).
    alignment = 6 if row["alignment"] == "TOP_CENTER" else 2
    return (f"FontSize={row['font_size']},PrimaryColour=&H00{bgr},"
            f"Alignment={alignment},Outline={row['outline_width']}")
