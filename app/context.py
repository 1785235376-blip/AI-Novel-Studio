from __future__ import annotations

import json
from pathlib import Path

from .privacy import cloud_safe_context, normalize_privacy


def _read(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def build_context(data_root: Path, novel_id: str, chapter: int, instruction: str, cloud: bool = False) -> dict:
    root = data_root / "novels" / novel_id
    sources = {name: _read(root / filename, default) for name, filename, default in (
        ("novel", "novel.json", {}), ("characters", "characters/characters.json", []),
        ("locations", "locations/locations.json", []), ("story_state", "story_state.json", {}),
        ("secrets", "secrets.json", []), ("foreshadowing", "foreshadowing.json", []),
        ("summaries", "summaries/index.json", []), ("style_profile", "style/profile.json", {}),
    )}
    return build_context_from_sources(sources, novel_id, chapter, instruction, cloud)


def build_context_from_sources(sources: dict, novel_id: str, chapter: int, instruction: str, cloud: bool = False) -> dict:
    meta = sources.get("novel", {})
    state = sources.get("story_state", {})
    relevant_names = {str(x) for x in state.get("active_characters", [])}
    selected = [c for c in sources.get("characters", [])
                if c.get("id") in relevant_names or c.get("name", "\x00") in instruction]
    locations = sources.get("locations", [])
    foreshadowing = [f for f in sources.get("foreshadowing", []) if f.get("status") == "OPEN"]
    secrets = [s for s in sources.get("secrets", [])
               if chapter < s.get("earliest_reveal_chapter", 10**9) or s.get("status") == "ACTIVE"]
    summaries = sources.get("summaries", [])[-3:]
    style = sources.get("style_profile", {})
    long_summary = meta.get("long_term_summary", "")
    omitted: list[str] = []
    if cloud:
        def safe(records):
            accepted, denied = cloud_safe_context(records)
            omitted.extend(denied)
            return accepted
        selected, locations, foreshadowing, secrets, summaries = (
            safe(records) for records in (selected, locations, foreshadowing, secrets, summaries)
        )
        # Derived state/summaries may contain copied protected prose. Without an
        # explicit policy for that material, retain only structural chapter data.
        state_records = safe([state]) if state else []
        state = state_records[0] if state_records else {}
        style_records = safe([style]) if style else []
        style = style_records[0] if style_records else {}
        if normalize_privacy(meta.get("privacy_level")) != "CLOUD_ALLOWED":
            long_summary = ""
    return {
        "novel": meta.get("title", novel_id), "novel_id": novel_id,
        "volume": state.get("volume", 1), "chapter": chapter, "chapter_goal": instruction,
        "pov": state.get("pov"), "story_time": state.get("story_time"),
        "characters": selected, "relationships": state.get("relationships", []),
        "locations": locations, "current_story_state": state,
        "active_foreshadowing": foreshadowing, "forbidden_secrets": secrets,
        "privacy_omissions": list(dict.fromkeys(omitted)),
        "recent_chapter_summary": summaries, "long_term_summary": long_summary,
        "style_profile": style, "must_include": [],
        "must_not_include": ["未经批准改变 Canon", "提前揭露受保护秘密"],
    }
