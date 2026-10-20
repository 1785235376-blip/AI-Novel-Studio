"""Strict sidecar conversion; the original timeline remains the only editor.

No transcription, timing inference, media probe, filesystem or styling. All
cue text is validated again by the original closed timeline normalizer.
"""
from __future__ import annotations

import copy
import re

MAX_SIDECAR_BYTES = 192000


def parse_subtitle_cues(content, format):
    """Pure bounded lexical parser; each owner still validates its cue semantics."""
    if format not in {"SRT", "VTT"} or not isinstance(content, str):
        raise ValueError("STUDIO_SUBTITLE_FORMAT_INVALID")
    try:
        if len(content.encode("utf-8")) > MAX_SIDECAR_BYTES:
            raise ValueError("STUDIO_SUBTITLE_BYTE_LIMIT")
    except UnicodeEncodeError:
        raise ValueError("STUDIO_SUBTITLE_UTF8_REQUIRED") from None
    text = content.removeprefix("\ufeff").replace("\r\n", "\n")
    if "\r" in text:
        raise ValueError("STUDIO_SUBTITLE_LINE_ENDINGS_INVALID")
    if format == "VTT":
        if not text.startswith("WEBVTT\n\n"):
            raise ValueError("STUDIO_SUBTITLE_VTT_PLAIN_HEADER_REQUIRED")
        text = text[8:]
    blocks = text.strip("\n").split("\n\n") if text.strip("\n") else []
    if not 1 <= len(blocks) <= 500:
        raise ValueError("STUDIO_SUBTITLE_CUE_LIMIT")
    separator = r"," if format == "SRT" else r"\."
    stamp = rf"(\d{{2,6}}):([0-5]\d):([0-5]\d){separator}(\d{{3}})"
    pattern = re.compile(rf"{stamp} --> {stamp}")
    cues = []
    for index, block in enumerate(blocks, 1):
        lines = block.split("\n")
        # VTT identifiers are optional; our exports use numbered identifiers.
        if format == "VTT" and lines and pattern.fullmatch(lines[0]):
            timing = 0
        else:
            if len(lines) < 3 or lines[0] != str(index):
                raise ValueError("STUDIO_SUBTITLE_NUMBERED_CUES_REQUIRED")
            timing = 1
        match = pattern.fullmatch(lines[timing])
        if not match or len(lines) <= timing + 1:
            raise ValueError("STUDIO_SUBTITLE_PLAIN_TIMING_REQUIRED")
        values = list(map(int, match.groups()))
        def milliseconds(offset):
            h, m, s, ms = values[offset:offset + 4]
            return ((h * 60 + m) * 60 + s) * 1000 + ms
        cues.append({"start_ms": milliseconds(0), "end_ms": milliseconds(4), "text": "\n".join(lines[timing + 1:])})
    return cues


def import_subtitles(timeline, content, format):
    from .studio_timeline_render import normalize_studio_timeline
    cues = parse_subtitle_cues(content, format)
    result = copy.deepcopy(timeline)
    result["captions"] = cues
    return normalize_studio_timeline(result)


def export_subtitles(timeline, format):
    from .studio_timeline_render import normalize_studio_timeline
    if format not in {"SRT", "VTT"}:
        raise ValueError("STUDIO_SUBTITLE_FORMAT_INVALID")
    row = normalize_studio_timeline(timeline)
    def stamp(ms):
        hours, rest = divmod(ms, 3600000)
        minutes, rest = divmod(rest, 60000)
        seconds, millis = divmod(rest, 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}{',' if format == 'SRT' else '.'}{millis:03d}"
    blocks = [f"{index}\n{stamp(cue['start_ms'])} --> {stamp(cue['end_ms'])}\n{cue['text']}"
              for index, cue in enumerate(row["captions"], 1)]
    content = (("WEBVTT\n\n" if format == "VTT" else "") + "\n\n".join(blocks) + ("\n" if blocks else "")).encode("utf-8")
    if len(content) > MAX_SIDECAR_BYTES:
        raise ValueError("STUDIO_SUBTITLE_BYTE_LIMIT")
    return content
