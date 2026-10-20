"""Explicit author markers, not semantic inference, for reviewable world/plot drafts."""
from __future__ import annotations

import re

from .source_privacy import content_digest

_RULE = re.compile(r"(?im)^[ \t]*(?:世界规则|能力规则|规则|World rule|Ability rule)[ \t]*[:：][ \t]*(?P<value>[^\r\n]{1,4000})\r?$")
_PLOT = re.compile(r"(?im)^[ \t]*(?P<label>第一幕|第二幕|第三幕|核心冲突|冲突|高潮|结局|Act 1|Act 2|Act 3|Conflict|Climax|Ending)[ \t]*[:：][ \t]*(?P<value>[^\r\n]{1,4000})\r?$")
_FIELDS = {"第一幕": "act1", "第二幕": "act2", "第三幕": "act3", "核心冲突": "conflict", "冲突": "conflict", "高潮": "climax", "结局": "ending", "act 1": "act1", "act 2": "act2", "act 3": "act3", "conflict": "conflict", "climax": "climax", "ending": "ending"}


def extract_explicit_planning(chapters, kind):
    """Return complete drafts only; incomplete/ambiguous plot markers are findings."""
    candidates, findings = [], []
    for chapter in chapters:
        text = str(chapter.get("content") or "")
        if len(text) > 2_000_000:
            raise ValueError("chapter exceeds extraction limit")
        def evidence(match):
            return {"chapter_id": chapter["id"], "chapter_version": chapter["version"],
                    "content_sha256": content_digest(chapter), "start": match.start("value"),
                    "end": match.end("value"), "quote": match.group("value")}
        if kind == "ABILITY":
            seen = set()
            for match in _RULE.finditer(text):
                value = match.group("value").strip()
                if not value or value in seen:
                    continue
                seen.add(value)
                candidates.append({"record": {"kind": "ABILITY", "title": value[:200], "description": value, "rules": [value]}, "evidence": [evidence(match)]})
                if len(candidates) > 100:
                    raise ValueError("too many explicit candidates; review fewer source chapters")
        elif kind == "PLOT":
            fields, anchors, duplicate = {}, [], set()
            for match in _PLOT.finditer(text):
                field = _FIELDS[match.group("label").lower()]
                if field in fields:
                    duplicate.add(field)
                fields[field] = match.group("value").strip()
                if len(anchors) < 12:
                    anchors.append(evidence(match))
            missing = sorted(set(_FIELDS.values()) - {key for key, value in fields.items() if value})
            if fields and (missing or duplicate):
                findings.append({"chapter_id": chapter["id"], "code": "PLOT_MARKERS_INCOMPLETE" if missing else "PLOT_MARKERS_AMBIGUOUS", "missing_fields": missing, "duplicate_fields": sorted(duplicate), "fields": fields, "evidence": anchors})
            elif fields:
                candidates.append({"record": {"kind": "PLOT", "title": str(chapter.get("title") or "三幕结构")[:200], "acts": [fields["act1"], fields["act2"], fields["act3"]], **{key: fields[key] for key in ("conflict", "climax", "ending")}}, "evidence": anchors})
    if len(candidates) > 100:
        raise ValueError("too many explicit candidates; review fewer source chapters")
    return candidates, findings
