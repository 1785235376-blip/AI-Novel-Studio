"""Strict sidecar conversion; the original timeline remains the only editor.

No transcription, timing inference, media probe, filesystem or styling. All
cue text is validated again by the original closed timeline normalizer.
"""
from __future__ import annotations

import copy
from html.entities import html5
import re

MAX_SIDECAR_BYTES = 192000

# WebVTT consumes HTML character references in the data state. Decode once;
# the original timeline owner still rejects styling, markup and controls.
_VTT_REFERENCE_PATTERN = re.compile(r"&(?:\#(?:[xX][0-9a-fA-F]+|[0-9]+);?|[A-Za-z][A-Za-z0-9]*;?)")
_VTT_MAX_REFERENCE_NAME = max(map(len, html5))
_HTML_C1_REPLACEMENTS = {
    0x80: 0x20AC, 0x82: 0x201A, 0x83: 0x0192, 0x84: 0x201E,
    0x85: 0x2026, 0x86: 0x2020, 0x87: 0x2021, 0x88: 0x02C6,
    0x89: 0x2030, 0x8A: 0x0160, 0x8B: 0x2039, 0x8C: 0x0152,
    0x8E: 0x017D, 0x91: 0x2018, 0x92: 0x2019, 0x93: 0x201C,
    0x94: 0x201D, 0x95: 0x2022, 0x96: 0x2013, 0x97: 0x2014,
    0x98: 0x02DC, 0x99: 0x2122, 0x9A: 0x0161, 0x9B: 0x203A,
    0x9C: 0x0153, 0x9E: 0x017E, 0x9F: 0x0178,
}


def _decode_vtt_reference(match):
    reference = match[0][1:]
    if not reference.startswith("#"):
        # Longest matching name; the table includes the legacy names allowed
        # without a semicolon. Unknown suffixes remain literal data.
        for length in range(min(len(reference), _VTT_MAX_REFERENCE_NAME), 0, -1):
            name = reference[:length]
            if name in html5:
                return html5[name] + reference[length:]
        return match[0]
    digits = reference[1:].removesuffix(";")
    base = 10
    if digits.startswith(("x", "X")):
        base, digits = 16, digits[1:]
    codepoint = 0
    # Saturation avoids Python's large-integer limit and unbounded arithmetic;
    # the lexical match has already consumed the complete reference.
    for digit in digits:
        codepoint = codepoint * base + int(digit, base)
        if codepoint > 0x10FFFF:
            return "\ufffd"
    if codepoint == 0 or 0xD800 <= codepoint <= 0xDFFF:
        return "\ufffd"
    # Unlike html.unescape, retain other controls and noncharacters. HTML
    # reports a parse error but emits them; our existing owner validates them.
    return chr(_HTML_C1_REPLACEMENTS.get(codepoint, codepoint))


def decode_vtt_text(text):
    """Decode one WebVTT text token without reinterpreting decoded ampersands."""
    return _VTT_REFERENCE_PATTERN.sub(_decode_vtt_reference, text)


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
        cue_text = "\n".join(lines[timing + 1:])
        if format == "VTT":
            cue_text = decode_vtt_text(cue_text)
        cues.append({"start_ms": milliseconds(0), "end_ms": milliseconds(4), "text": cue_text})
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
    def cue_text(cue):
        # The owner forbids markup; escape literal ampersands for external
        # WebVTT consumers without changing SRT's existing contract.
        return cue["text"].replace("&", "&amp;") if format == "VTT" else cue["text"]
    blocks = [f"{index}\n{stamp(cue['start_ms'])} --> {stamp(cue['end_ms'])}\n{cue_text(cue)}"
              for index, cue in enumerate(row["captions"], 1)]
    content = (("WEBVTT\n\n" if format == "VTT" else "") + "\n\n".join(blocks) + ("\n" if blocks else "")).encode("utf-8")
    if len(content) > MAX_SIDECAR_BYTES:
        raise ValueError("STUDIO_SUBTITLE_BYTE_LIMIT")
    return content
