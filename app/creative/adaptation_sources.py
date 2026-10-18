"""Bounded ordered source data for the existing Creative adaptation owner.

No context discovery, provider execution or separate manuscript authority lives
here. Snapshots project original saved chapters through the native Author source
shape and are compared again by the owning service at every use.
"""
from copy import deepcopy

from ..author_context_sources import NativeAuthorSources
from ..author_request import chapter_digest
from ..source_privacy import effective_source_privacy
from .proposals import digest

MAX_SOURCES = 16
MAX_SOURCE_CHARACTERS = 8000
MAX_TOTAL_CHARACTERS = 32000


def is_ordered(row):
    return row.get("source_mode") == "ORDERED_CHAPTERS"


def chapter_ids(row):
    return [source["chapter_id"] for source in row["sources"]] if is_ordered(row) else [row["chapter_id"]]


def ordered_fields(row):
    return {"sources": deepcopy(row["sources"]), "ordered_sources_digest": row["ordered_sources_digest"]} if is_ordered(row) else {}


def snapshot(chapter, ordinal, scope):
    text = str(chapter.get("content") or "")
    if not text.strip() or len(text) > MAX_SOURCE_CHARACTERS:
        raise ValueError("ADAPTATION_ORDERED_SOURCE_LIMIT")
    if chapter.get("is_archived") or chapter.get("branch_id") != scope.get("branch_id"):
        raise ValueError("ADAPTATION_ORDERED_SOURCE_UNAVAILABLE")
    native = NativeAuthorSources._record("CHAPTER", chapter, text,
        privacy=effective_source_privacy(chapter, scope.get("branch_id")),
        evidence={"chapter_id": chapter["id"], "chapter_version": chapter["version"]})
    item = {**{key: deepcopy(native[key]) for key in ("kind", "id", "version", "label", "source_digest", "citation", "evidence", "privacy_level")},
        "text": text, "layer": "AUTHOR_REFERENCE", "untrusted_data": True,
        "instructions_allowed": False, "truncated": False, "truncation_reason": None}
    return {"ordinal": ordinal, "chapter_id": chapter["id"], "source_version": chapter["version"],
        "source_digest": chapter_digest(chapter), "selected_text": text, "selection_digest": digest(text),
        "native_source_digest": native["source_digest"], "native_item": item}


def validate_snapshots(sources, ordered_digest):
    from .adaptation_models import AdaptationSourceSnapshot
    if not isinstance(sources, list) or not 2 <= len(sources) <= MAX_SOURCES:
        raise ValueError("ADAPTATION_ORDERED_SOURCE_LIMIT")
    parsed = [AdaptationSourceSnapshot.model_validate(source, strict=True).model_dump() for source in sources]
    if parsed != sources or len({source["chapter_id"] for source in sources}) != len(sources):
        raise ValueError("ADAPTATION_ORDERED_SOURCE_INVALID")
    from .adaptation_receipt import validate_ordered_sources
    return validate_ordered_sources(sources, ordered_digest)


def author_sources(row):
    return [{"kind": "CHAPTER", "id": source["chapter_id"], "version": source["source_version"],
        "source_digest": source["native_source_digest"], "include": True, "max_characters": MAX_SOURCE_CHARACTERS}
        for source in row["sources"]]


def ordered_context(sources):
    return {"explicit_sources": {"items": [deepcopy(source["native_item"]) for source in sources],
        "untrusted_data": True, "instructions_allowed": False,
        "scope": "EXPLICIT_REVIEWED_ADDITIONS", "research_is_canon": False}}
