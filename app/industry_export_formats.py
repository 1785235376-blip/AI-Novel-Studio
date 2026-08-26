"""Industry-oriented screenplay, shot-list and storyboard exporters.

The application deliberately keeps the backend dependency-free.  This module
therefore produces interoperable text/CSV/OOXML/ZIP artifacts using only the
Python standard library.  It is separate from :mod:`app.export_formats` so
the small novel DOCX/EPUB writers and the optional PDF writer can evolve
independently.

The public functions accept a serialisable screenplay snapshot.  They never
call a model and never include credentials.  Resource bytes are supplied by a
caller-owned loader (normally ``AssetLibraryService``); the snapshot itself
contains metadata only.  Missing resources are represented in the manifest
and can be made fatal with ``resource_policy='require_all'``.
"""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import re
from datetime import datetime, timezone
from io import BytesIO
from pathlib import PurePosixPath
from typing import Any, Callable, Iterable, Mapping
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


INDUSTRY_SCHEMA_VERSION = 1
RESOURCE_POLICIES = frozenset({"allow_missing", "require_all"})


class IndustryExportError(ValueError):
    """Base error carrying a stable API error code and structured details."""

    code = "EXPORT_INDUSTRY_ERROR"

    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None):
        self.details = dict(details or {})
        super().__init__(message)


class IndustryExportValidationError(IndustryExportError):
    code = "EXPORT_SCHEMA_INVALID"


class IndustryExportResourceError(IndustryExportError):
    code = "EXPORT_RESOURCES_MISSING"


def _clean_text(value: object) -> str:
    """Return safe Unicode text while removing XML-invalid controls."""

    text = str(value or "")
    return "".join(
        char
        for char in text
        if char in "\t\n\r" or (ord(char) >= 0x20 and not 0xD800 <= ord(char) <= 0xDFFF)
    )


def _text(value: object, *, default: str = "") -> str:
    return _clean_text(value).strip() or default


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: object) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _number(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _duration(value: object, default: float = 5.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number


def _dialogue_rows(value: object, path: str, issues: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, raw in enumerate(_as_list(value)):
        if isinstance(raw, str):
            character, text = "角色", _text(raw)
            parenthetical = ""
        else:
            row = _mapping(raw)
            character = _text(row.get("character") or row.get("speaker") or row.get("name"), default="角色")
            text = _text(row.get("text") if row.get("text") is not None else row.get("content"))
            parenthetical = _text(row.get("parenthetical") or row.get("direction"))
        if not text:
            issues.append({"path": f"{path}[{index}].text", "message": "对白文本不能为空"})
            continue
        rows.append({"character": character, "text": text, "parenthetical": parenthetical})
    return rows


def _scene_heading(scene: Mapping[str, Any]) -> str:
    raw = _text(scene.get("heading") or scene.get("slugline"))
    # Preserve an explicitly authored industry slugline.
    if re.match(r"^(?:INT|EXT|I/E|INT\./EXT)\.?\s+", raw, flags=re.IGNORECASE):
        return raw.upper() if raw.isascii() else raw
    location = _text(scene.get("location"), default="未设定地点")
    time = _text(scene.get("time"), default="未设定时间")
    label = raw or location
    if time and time not in label:
        label = f"{label} - {time}"
    return f"INT./EXT. {label}"


def _character_name(value: object) -> str:
    name = _text(value, default="角色")
    # Fountain uses uppercase character cues.  Uppercasing ASCII keeps the
    # convention without damaging Chinese names.
    return name.upper() if name.isascii() else name


def _asset_reference_ids(node: object) -> list[str]:
    """Collect explicit asset references only; prose is never scanned."""

    refs: set[str] = set()
    reference_keys = {
        "asset_id",
        "reference_asset_id",
        "source_asset_id",
        "target_asset_id",
        "asset_ids",
        "reference_asset_ids",
        "asset_refs",
        "reference_assets",
    }

    def visit(value: object) -> None:
        if isinstance(value, Mapping):
            for key, child in value.items():
                lowered = str(key).lower()
                if lowered in reference_keys:
                    if isinstance(child, str) and child.strip():
                        refs.add(child.strip())
                    elif isinstance(child, (list, tuple, set)):
                        for item in child:
                            if isinstance(item, str) and item.strip():
                                refs.add(item.strip())
                            elif isinstance(item, Mapping):
                                visit(item)
                visit(child)
        elif isinstance(value, (list, tuple)):
            for item in value:
                visit(item)

    visit(node)
    return sorted(refs)


def normalize_screenplay(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
) -> dict[str, Any]:
    """Normalize and validate one screenplay snapshot.

    The service historically stored a permissive JSON shape.  This adapter
    keeps that data readable while enforcing the cross-reference and bounded
    fields required by an industry export.  The returned structure is safe to
    hand to every exporter in this module.
    """

    source = _mapping(screenplay)
    issues: list[dict[str, str]] = []
    scenes_raw = _as_list(source.get("scenes"))
    if not scenes_raw:
        raise IndustryExportValidationError(
            "screenplay export requires at least one scene",
            details={"issues": [{"path": "scenes", "message": "至少需要一个场景"}]},
        )

    scenes: list[dict[str, Any]] = []
    scene_ids: set[str] = set()
    for index, raw in enumerate(scenes_raw, 1):
        row = _mapping(raw)
        scene_id = _text(row.get("id"), default=f"scene-{index:03d}")
        if scene_id in scene_ids:
            issues.append({"path": f"scenes[{index - 1}].id", "message": "场景 ID 重复"})
        scene_ids.add(scene_id)
        action = _text(row.get("action") or row.get("description"))
        dialogue = _dialogue_rows(row.get("dialogue"), f"scenes[{index - 1}].dialogue", issues)
        characters = [_text(item) for item in _as_list(row.get("characters")) if _text(item)]
        scenes.append(
            {
                "id": scene_id,
                "sequence": _number(row.get("sequence"), index),
                "source_chapter_id": _text(row.get("source_chapter_id") or row.get("chapter_id")),
                "source_version": row.get("source_version"),
                "heading": _scene_heading(row),
                "raw_heading": _text(row.get("heading") or row.get("slugline")),
                "time": _text(row.get("time"), default="未设定时间"),
                "location": _text(row.get("location"), default="未设定地点"),
                "characters": characters,
                "action": action,
                "dialogue": dialogue,
                "emotion": _text(row.get("emotion")),
                "status": _text(row.get("status"), default="DRAFT"),
                "asset_ids": _asset_reference_ids(row),
            }
        )

    shots: list[dict[str, Any]] = []
    shot_ids: set[str] = set()
    shot_numbers: set[int] = set()
    for index, raw in enumerate(_as_list(source.get("shots")), 1):
        row = _mapping(raw)
        shot_id = _text(row.get("id"), default=f"shot-{index:03d}")
        number = _number(row.get("number"), index)
        if shot_id in shot_ids:
            issues.append({"path": f"shots[{index - 1}].id", "message": "镜头 ID 重复"})
        if number in shot_numbers:
            issues.append({"path": f"shots[{index - 1}].number", "message": "镜号重复"})
        shot_ids.add(shot_id)
        shot_numbers.add(number)
        scene_id = _text(row.get("scene_id"))
        if scene_id and scene_id not in scene_ids:
            issues.append({"path": f"shots[{index - 1}].scene_id", "message": "镜头引用了不存在的场景"})
        duration = _duration(row.get("duration_seconds") if row.get("duration_seconds") is not None else row.get("duration"))
        if duration <= 0 or duration > 3600:
            issues.append({"path": f"shots[{index - 1}].duration_seconds", "message": "时长必须大于 0 且不超过 3600 秒"})
            duration = max(0.1, min(3600.0, duration if duration > 0 else 5.0))
        shots.append(
            {
                "id": shot_id,
                "number": number,
                "scene_id": scene_id,
                "source_chapter_id": _text(row.get("source_chapter_id") or row.get("chapter_id")),
                "shot_size": _text(row.get("shot_size") or row.get("size"), default="MEDIUM"),
                "camera_angle": _text(row.get("camera_angle") or row.get("angle"), default="EYE_LEVEL"),
                "camera_motion": _text(row.get("camera_motion") or row.get("movement"), default="STATIC"),
                "subject_position": _text(row.get("subject_position") or row.get("subject")),
                "action": _text(row.get("action")),
                "dialogue": _dialogue_rows(row.get("dialogue"), f"shots[{index - 1}].dialogue", issues),
                "sound_effect": _text(row.get("sound_effect") or row.get("sound")),
                "duration_seconds": duration,
                "transition": _text(row.get("transition")),
                "notes": _text(row.get("notes") or row.get("note")),
                "asset_ids": _asset_reference_ids(row),
            }
        )

    cards: list[dict[str, Any]] = []
    card_ids: set[str] = set()
    for index, raw in enumerate(_as_list(source.get("storyboard")), 1):
        row = _mapping(raw)
        card_id = _text(row.get("id"), default=f"card-{index:03d}")
        shot_id = _text(row.get("shot_id"))
        if card_id in card_ids:
            issues.append({"path": f"storyboard[{index - 1}].id", "message": "分镜卡 ID 重复"})
        if shot_id and shot_id not in shot_ids:
            issues.append({"path": f"storyboard[{index - 1}].shot_id", "message": "分镜卡引用了不存在的镜头"})
        card_ids.add(card_id)
        cards.append(
            {
                "id": card_id,
                "number": _number(row.get("number"), index),
                "shot_id": shot_id,
                "scene_id": _text(row.get("scene_id")),
                "source_chapter_id": _text(row.get("source_chapter_id") or row.get("chapter_id")),
                "frame_prompt": _text(row.get("frame_prompt") or row.get("visual_description") or row.get("description")),
                "composition": _text(row.get("composition") or row.get("framing")),
                "color": _text(row.get("color") or row.get("palette")),
                "camera": _text(row.get("camera") or row.get("camera_motion")),
                "notes": _text(row.get("notes") or row.get("note")),
                "asset_ids": _asset_reference_ids(row),
            }
        )

    transitions: list[dict[str, Any]] = []
    for index, raw in enumerate(_as_list(source.get("transitions")), 1):
        row = _mapping(raw)
        from_id = _text(row.get("from_shot_id") or row.get("source_shot_id"))
        to_id = _text(row.get("to_shot_id") or row.get("target_shot_id"))
        for field, value in (("from_shot_id", from_id), ("to_shot_id", to_id)):
            if value and value not in shot_ids:
                issues.append({"path": f"transitions[{index - 1}].{field}", "message": "转场引用了不存在的镜头"})
        transitions.append(
            {
                "id": _text(row.get("id"), default=f"transition-{index:03d}"),
                "from_shot_id": from_id,
                "to_shot_id": to_id,
                "type": _text(row.get("type") or row.get("transition_type"), default="CUT"),
                "duration_seconds": max(0.0, min(3600.0, _duration(row.get("duration_seconds"), 0.0))),
                "camera_motion": _text(row.get("camera_motion")),
                "emotional_reason": _text(row.get("emotional_reason") or row.get("note")),
            }
        )

    if issues:
        raise IndustryExportValidationError("影视导出数据校验失败", details={"issues": issues})

    normalized = {
        "schema_version": INDUSTRY_SCHEMA_VERSION,
        "novel_id": _text(novel_id),
        "id": _text(source.get("id")),
        "title": _text(source.get("title"), default=_text(title, default="未命名剧本")),
        "status": _text(source.get("status"), default="DRAFT"),
        "revision": _number(source.get("revision"), 1),
        "shot_revision": _number(source.get("shot_revision"), 1),
        "storyboard_revision": _number(source.get("storyboard_revision"), 1),
        "source_updated_at": _text(source.get("updated_at")),
        "scenes": scenes,
        "shots": shots,
        "storyboard": cards,
        "transitions": transitions,
    }
    normalized["asset_ids"] = sorted(
        set(_asset_reference_ids(normalized))
        | {item for row in scenes + shots + cards for item in row.get("asset_ids", [])}
    )
    return normalized


def normalize_resource_manifest(
    manifest: Mapping[str, Any] | object,
    references: Iterable[str],
) -> dict[str, Any]:
    """Normalize snapshot resource metadata and expose deterministic statuses."""

    raw = _mapping(manifest)
    available = {
        _text(item.get("id")): dict(item)
        for item in _as_list(raw.get("available"))
        if isinstance(item, Mapping) and _text(item.get("id"))
    }
    missing = {
        _text(item.get("id")): dict(item)
        for item in _as_list(raw.get("missing"))
        if isinstance(item, Mapping) and _text(item.get("id"))
    }
    records: list[dict[str, Any]] = []
    for asset_id in sorted({str(item).strip() for item in references if str(item).strip()}):
        if asset_id in missing:
            record = dict(missing[asset_id])
            record.update({"id": asset_id, "status": "MISSING"})
        elif asset_id in available:
            record = dict(available[asset_id])
            record.update({"id": asset_id, "status": "AVAILABLE"})
        else:
            record = {"id": asset_id, "status": "MISSING", "reason": "asset not listed in snapshot"}
        records.append(record)
    # Preserve explicitly listed resources even if a legacy snapshot did not
    # expose an asset reference in the screenplay JSON.
    for asset_id, item in sorted(available.items()):
        if asset_id not in {row["id"] for row in records}:
            record = dict(item)
            record.update({"id": asset_id, "status": "AVAILABLE", "unreferenced": True})
            records.append(record)
    missing_rows = [row for row in records if row.get("status") != "AVAILABLE"]
    return {
        "schema_version": INDUSTRY_SCHEMA_VERSION,
        "referenced": [row["id"] for row in records if not row.get("unreferenced")],
        "available": [row for row in records if row.get("status") == "AVAILABLE"],
        "missing": missing_rows,
        "missing_count": len(missing_rows),
    }


def _loader_get(loader: object, asset_id: str) -> Mapping[str, Any]:
    getter = getattr(loader, "get", None)
    if not callable(getter):
        raise FileNotFoundError(asset_id)
    value = getter(asset_id)
    if not isinstance(value, Mapping):
        raise FileNotFoundError(asset_id)
    return value


def _loader_content(loader: object, asset_id: str) -> bytes:
    reader = getattr(loader, "content", None)
    if not callable(reader):
        raise FileNotFoundError(asset_id)
    value = reader(asset_id)
    if not isinstance(value, (bytes, bytearray, memoryview)):
        raise ValueError("asset content is not binary")
    return bytes(value)


def resolve_resources(
    manifest: Mapping[str, Any] | object,
    *,
    references: Iterable[str],
    loader: object | None = None,
    novel_id: object = "",
    resource_policy: str = "allow_missing",
) -> dict[str, Any]:
    """Resolve asset metadata/bytes without allowing path traversal.

    ``loader`` is intentionally duck-typed so tests and future repositories can
    provide the same ``get(id)``/``content(id)`` contract.  Bytes are returned
    only to the in-memory package builder and are never persisted in snapshots.
    """

    policy = _text(resource_policy, default="allow_missing").lower()
    if policy not in RESOURCE_POLICIES:
        raise IndustryExportValidationError(
            "invalid resource policy",
            details={"resource_policy": policy, "allowed": sorted(RESOURCE_POLICIES)},
        )
    normalized = normalize_resource_manifest(manifest, references)
    records: list[dict[str, Any]] = []
    binaries: dict[str, bytes] = {}
    for record in normalized["available"] + normalized["missing"]:
        item = dict(record)
        asset_id = _text(item.get("id"))
        if item.get("status") != "AVAILABLE":
            records.append(item)
            continue
        if loader is None:
            item["packaged"] = False
            item["reason"] = "asset metadata available; binary loader not configured"
            records.append(item)
            continue
        try:
            metadata = dict(_loader_get(loader, asset_id))
            owner = _text(metadata.get("novel_id"))
            if owner and _text(novel_id) and owner != _text(novel_id):
                raise PermissionError("asset belongs to another project")
            content = _loader_content(loader, asset_id)
            expected = _text(metadata.get("sha256") or item.get("sha256"))
            actual = hashlib.sha256(content).hexdigest()
            if expected and expected.lower() != actual:
                raise ValueError("asset checksum mismatch")
            item.update(
                {
                    "filename": metadata.get("filename") or item.get("filename"),
                    "media_type": metadata.get("media_type") or item.get("media_type"),
                    "size": len(content),
                    "sha256": actual,
                    "packaged": True,
                }
            )
            binaries[asset_id] = content
        except (FileNotFoundError, OSError, PermissionError, ValueError) as exc:
            item.update({"status": "MISSING", "packaged": False, "reason": str(exc) or "asset unavailable"})
        records.append(item)
    missing = [row for row in records if row.get("status") != "AVAILABLE" or not row.get("packaged", False)]
    if policy == "require_all" and missing:
        raise IndustryExportResourceError(
            "影视导出缺少可用资源",
            details={"missing": missing, "missing_count": len(missing), "resource_policy": policy},
        )
    return {
        "schema_version": INDUSTRY_SCHEMA_VERSION,
        "referenced": normalized["referenced"],
        "available": [row for row in records if row.get("status") == "AVAILABLE" and row.get("packaged") is not False],
        "missing": missing,
        "missing_count": len(missing),
        "binaries": binaries,
    }


def _resource_status_text(resources: Mapping[str, Any]) -> str:
    missing = _as_list(resources.get("missing"))
    available = _as_list(resources.get("available"))
    return f"available={len(available)}; missing={len(missing)}"


def _metadata_lines(
    *,
    title: str,
    novel_id: object,
    snapshot_id: object,
    source_versions: object,
    resources: Mapping[str, Any],
) -> list[str]:
    return [
        f"Project: {_text(title, default='Untitled')}",
        "Exported-By: AI Novel Studio",
        "Industry-Schema: 1",
        f"Novel-ID: {_text(novel_id)}",
        f"Snapshot-ID: {_text(snapshot_id, default='not-recorded')}",
        f"Source-Versions: {_text(source_versions, default='not-recorded')}",
        f"Resources: {_resource_status_text(resources)}",
    ]


def screenplay_to_fountain(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    snapshot_id: object = "",
    source_versions: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_policy: str = "allow_missing",
) -> str:
    """Render a Fountain 1.1-compatible screenplay text document."""

    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = normalize_resource_manifest(resource_manifest, normalized["asset_ids"])
    if _text(resource_policy).lower() == "require_all" and resources["missing_count"]:
        raise IndustryExportResourceError(
            "影视剧本引用了缺失资源",
            details={"missing": resources["missing"], "missing_count": resources["missing_count"]},
        )
    lines = [
        f"Title: {normalized['title']}",
        "Credit: Written by",
        "Author: AI Novel Studio",
        "Format: Fountain 1.1",
        *_metadata_lines(
            title=normalized["title"],
            novel_id=novel_id,
            snapshot_id=snapshot_id,
            source_versions=source_versions,
            resources=resources,
        ),
        "",
    ]
    for scene in normalized["scenes"]:
        lines.extend([scene["heading"], ""])
        if scene["emotion"]:
            lines.extend([f"[[情绪：{scene['emotion']}]]", ""])
        action = scene["action"] or "[暂无动作描述]"
        lines.extend([action, ""])
        for dialogue in scene["dialogue"]:
            lines.append(_character_name(dialogue["character"]))
            if dialogue["parenthetical"]:
                parenthetical = dialogue["parenthetical"]
                if not parenthetical.startswith("("):
                    parenthetical = f"({parenthetical})"
                lines.append(parenthetical)
            lines.extend([dialogue["text"], ""])
    # Fountain transitions are conventionally right aligned with a leading >.
    if normalized["transitions"]:
        lines.extend(["", "/* TRANSITIONS */"])
        for transition in normalized["transitions"]:
            lines.append(
                f"> {transition['type']}: {transition['from_shot_id']} -> {transition['to_shot_id']}"
            )
            if transition["emotional_reason"]:
                lines.append(f"/* {transition['emotional_reason']} */")
    return "\n".join(lines).rstrip() + "\n"


def screenplay_to_fountain_bytes(*args: Any, **kwargs: Any) -> bytes:
    return screenplay_to_fountain(*args, **kwargs).encode("utf-8")


def screenplay_to_markdown(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    snapshot_id: object = "",
    source_versions: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_policy: str = "allow_missing",
) -> str:
    """Readable compatibility preview retaining all standard screenplay data."""

    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = normalize_resource_manifest(resource_manifest, normalized["asset_ids"])
    if _text(resource_policy).lower() == "require_all" and resources["missing_count"]:
        raise IndustryExportResourceError(
            "影视剧本引用了缺失资源",
            details={"missing": resources["missing"], "missing_count": resources["missing_count"]},
        )
    lines = [f"# {normalized['title']}", "", "## 导出元数据", ""]
    for line in _metadata_lines(
        title=normalized["title"],
        novel_id=novel_id,
        snapshot_id=snapshot_id,
        source_versions=source_versions,
        resources=resources,
    ):
        lines.append(f"- {line}")
    lines.extend(["", "## 场景", ""])
    for scene in normalized["scenes"]:
        lines.extend([f"### {scene['heading']}", "", f"- 场景 ID：{scene['id']}", f"- 时间：{scene['time']}", f"- 地点：{scene['location']}", ""])
        if scene["emotion"]:
            lines.extend([f"**情绪：** {scene['emotion']}", ""])
        lines.extend([scene["action"] or "（暂无动作描述）", ""])
        for dialogue in scene["dialogue"]:
            lines.append(f"**{dialogue['character']}**：{dialogue['text']}")
            if dialogue["parenthetical"]:
                lines.append(f">（{dialogue['parenthetical']}）")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


# OOXML namespace constants are local to this module to keep the optional PDF
# writer and the legacy manuscript writer independent.
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PR = "http://schemas.openxmlformats.org/package/2006/relationships"
_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_DC = "http://purl.org/dc/elements/1.1/"
_APP = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
_XML = "http://www.w3.org/XML/1998/namespace"

for _prefix, _namespace in {
    "w": _W,
    "r": _R,
    "pr": _PR,
    "ct": _CT,
    "cp": _CP,
    "dc": _DC,
}.items():
    ET.register_namespace(_prefix, _namespace)


def _q(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _w_run(parent: ET.Element, text: object, *, bold: bool = False, italic: bool = False, size: int | None = None) -> None:
    run = ET.SubElement(parent, _q(_W, "r"))
    if bold or italic or size:
        props = ET.SubElement(run, _q(_W, "rPr"))
        if bold:
            ET.SubElement(props, _q(_W, "b"))
        if italic:
            ET.SubElement(props, _q(_W, "i"))
        if size:
            ET.SubElement(props, _q(_W, "sz"), {_q(_W, "val"): str(size)})
    node = ET.SubElement(run, _q(_W, "t"))
    value = _clean_text(text)
    if value[:1].isspace() or value[-1:].isspace():
        node.set(_q(_XML, "space"), "preserve")
    node.text = value


def _w_paragraph(
    parent: ET.Element,
    text: object = "",
    *,
    style: str = "Normal",
    left: int | None = None,
    right: int | None = None,
    align: str | None = None,
    before: int | None = None,
    after: int | None = None,
    keep_next: bool = False,
    bold: bool = False,
    italic: bool = False,
    size: int | None = None,
) -> ET.Element:
    paragraph = ET.SubElement(parent, _q(_W, "p"))
    props = ET.SubElement(paragraph, _q(_W, "pPr"))
    if style:
        ET.SubElement(props, _q(_W, "pStyle"), {_q(_W, "val"): style})
    if left is not None or right is not None:
        attrs: dict[str, str] = {}
        if left is not None:
            attrs[_q(_W, "left")] = str(left)
        if right is not None:
            attrs[_q(_W, "right")] = str(right)
        ET.SubElement(props, _q(_W, "ind"), attrs)
    if align:
        ET.SubElement(props, _q(_W, "jc"), {_q(_W, "val"): align})
    if before is not None or after is not None:
        spacing: dict[str, str] = {}
        if before is not None:
            spacing[_q(_W, "before")] = str(before)
        if after is not None:
            spacing[_q(_W, "after")] = str(after)
        ET.SubElement(props, _q(_W, "spacing"), spacing)
    if keep_next:
        ET.SubElement(props, _q(_W, "keepNext"))
    for index, line in enumerate(_clean_text(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")):
        if index:
            ET.SubElement(ET.SubElement(paragraph, _q(_W, "r")), _q(_W, "br"))
        if line:
            _w_run(paragraph, line, bold=bold, italic=italic, size=size)
    return paragraph


def _screenplay_styles_xml() -> bytes:
    styles = ET.Element(_q(_W, "styles"))
    defaults = ET.SubElement(styles, _q(_W, "docDefaults"))
    rpr_default = ET.SubElement(ET.SubElement(defaults, _q(_W, "rPrDefault")), _q(_W, "rPr"))
    ET.SubElement(rpr_default, _q(_W, "rFonts"), {_q(_W, "ascii"): "Arial", _q(_W, "hAnsi"): "Arial", _q(_W, "eastAsia"): "Microsoft YaHei"})
    ET.SubElement(rpr_default, _q(_W, "sz"), {_q(_W, "val"): "24"})
    definitions = [
        ("Normal", "Normal", 0, 0, False, "left"),
        ("ScreenplayTitle", "Screenplay Title", 0, 240, True, "center"),
        ("ScreenplayMeta", "Screenplay Metadata", 0, 80, False, "left"),
        ("ScreenplayScene", "Scene Heading", 240, 120, True, "left"),
        ("ScreenplayAction", "Action", 0, 120, False, "left"),
        ("ScreenplayCharacter", "Character", 360, 0, True, "left"),
        ("ScreenplayParenthetical", "Parenthetical", 240, 0, False, "left"),
        ("ScreenplayDialogue", "Dialogue", 240, 120, False, "left"),
        ("ScreenplayTransition", "Transition", 360, 120, True, "right"),
        ("ScreenplayAppendix", "Export Manifest", 0, 80, False, "left"),
    ]
    for style_id, name, before, after, bold, align in definitions:
        style = ET.SubElement(styles, _q(_W, "style"), {_q(_W, "type"): "paragraph", _q(_W, "styleId"): style_id})
        ET.SubElement(style, _q(_W, "name"), {_q(_W, "val"): name})
        if style_id != "Normal":
            ET.SubElement(style, _q(_W, "basedOn"), {_q(_W, "val"): "Normal"})
        ET.SubElement(style, _q(_W, "qFormat"))
        ppr = ET.SubElement(style, _q(_W, "pPr"))
        ET.SubElement(ppr, _q(_W, "jc"), {_q(_W, "val"): align})
        if before or after:
            ET.SubElement(ppr, _q(_W, "spacing"), {_q(_W, "before"): str(before), _q(_W, "after"): str(after)})
        rpr = ET.SubElement(style, _q(_W, "rPr"))
        if bold:
            ET.SubElement(rpr, _q(_W, "b"))
        if style_id == "ScreenplayTitle":
            ET.SubElement(rpr, _q(_W, "sz"), {_q(_W, "val"): "32"})
        elif style_id in {"ScreenplayMeta", "ScreenplayAppendix"}:
            ET.SubElement(rpr, _q(_W, "sz"), {_q(_W, "val"): "18"})
        else:
            ET.SubElement(rpr, _q(_W, "sz"), {_q(_W, "val"): "24"})
    return ET.tostring(styles, encoding="utf-8", xml_declaration=True)


def _docx_package(files: Mapping[str, bytes]) -> bytes:
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


def _screenplay_docx_document(
    normalized: Mapping[str, Any],
    *,
    novel_id: object,
    snapshot_id: object,
    source_versions: object,
    resources: Mapping[str, Any],
) -> bytes:
    document = ET.Element(_q(_W, "document"))
    body = ET.SubElement(document, _q(_W, "body"))
    _w_paragraph(body, normalized["title"], style="ScreenplayTitle", keep_next=True)
    metadata = _metadata_lines(
        title=normalized["title"],
        novel_id=novel_id,
        snapshot_id=snapshot_id,
        source_versions=source_versions,
        resources=resources,
    )
    for line in metadata:
        _w_paragraph(body, line, style="ScreenplayMeta")
    _w_paragraph(body, "", style="ScreenplayMeta", after=180)
    for scene in normalized["scenes"]:
        _w_paragraph(body, scene["heading"], style="ScreenplayScene", keep_next=True)
        if scene["emotion"]:
            _w_paragraph(body, f"情绪：{scene['emotion']}", style="ScreenplayMeta", italic=True)
        _w_paragraph(body, scene["action"] or "暂无动作描述", style="ScreenplayAction")
        for dialogue in scene["dialogue"]:
            _w_paragraph(body, _character_name(dialogue["character"]), style="ScreenplayCharacter", keep_next=True)
            if dialogue["parenthetical"]:
                parenthetical = dialogue["parenthetical"]
                if not parenthetical.startswith("("):
                    parenthetical = f"({parenthetical})"
                _w_paragraph(body, parenthetical, style="ScreenplayParenthetical", keep_next=True)
            _w_paragraph(body, dialogue["text"], style="ScreenplayDialogue")
    for transition in normalized["transitions"]:
        _w_paragraph(body, f"> {transition['type']}: {transition['from_shot_id']} -> {transition['to_shot_id']}", style="ScreenplayTransition")
    # A manifest appendix makes resource omissions visible in Word even when
    # the user does not inspect the asynchronous job metadata.
    _w_paragraph(body, "导出资源清单", style="ScreenplayScene", keep_next=True)
    for row in resources.get("available", []):
        _w_paragraph(body, f"AVAILABLE · {row.get('id')} · {row.get('filename') or 'unnamed'}", style="ScreenplayAppendix")
    for row in resources.get("missing", []):
        _w_paragraph(body, f"MISSING · {row.get('id')} · {row.get('reason') or 'unavailable'}", style="ScreenplayAppendix")
    section = ET.SubElement(body, _q(_W, "sectPr"))
    ET.SubElement(section, _q(_W, "pgSz"), {_q(_W, "w"): "12240", _q(_W, "h"): "15840"})  # US Letter
    ET.SubElement(section, _q(_W, "pgMar"), {_q(_W, "top"): "1440", _q(_W, "right"): "1440", _q(_W, "bottom"): "1440", _q(_W, "left"): "1440", _q(_W, "header"): "720", _q(_W, "footer"): "720", _q(_W, "gutter"): "0"})
    return ET.tostring(document, encoding="utf-8", xml_declaration=True)


def screenplay_to_docx(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    snapshot_id: object = "",
    source_versions: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_policy: str = "allow_missing",
) -> bytes:
    """Create an industry-oriented screenplay DOCX with explicit layout."""

    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = normalize_resource_manifest(resource_manifest, normalized["asset_ids"])
    if _text(resource_policy).lower() == "require_all" and resources["missing_count"]:
        raise IndustryExportResourceError("影视剧本引用了缺失资源", details={"missing": resources["missing"], "missing_count": resources["missing_count"]})
    document = _screenplay_docx_document(
        normalized,
        novel_id=novel_id,
        snapshot_id=snapshot_id,
        source_versions=source_versions,
        resources=resources,
    )
    core = ET.Element(_q(_CP, "coreProperties"))
    ET.SubElement(core, _q(_DC, "title")).text = normalized["title"]
    ET.SubElement(core, _q(_DC, "creator")).text = "AI Novel Studio"
    ET.SubElement(core, _q(_CP, "lastModifiedBy")).text = "AI Novel Studio"
    app = ET.Element(_q(_APP, "Properties"))
    ET.SubElement(app, _q(_APP, "Application")).text = "AI Novel Studio"
    content_types = ET.Element(_q(_CT, "Types"))
    ET.SubElement(content_types, _q(_CT, "Default"), {"Extension": "rels", "ContentType": "application/vnd.openxmlformats-package.relationships+xml"})
    ET.SubElement(content_types, _q(_CT, "Default"), {"Extension": "xml", "ContentType": "application/xml"})
    ET.SubElement(content_types, _q(_CT, "Override"), {"PartName": "/word/document.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"})
    ET.SubElement(content_types, _q(_CT, "Override"), {"PartName": "/word/styles.xml", "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"})
    ET.SubElement(content_types, _q(_CT, "Override"), {"PartName": "/docProps/core.xml", "ContentType": "application/vnd.openxmlformats-package.core-properties+xml"})
    ET.SubElement(content_types, _q(_CT, "Override"), {"PartName": "/docProps/app.xml", "ContentType": "application/vnd.openxmlformats-officedocument.extended-properties+xml"})
    package_rels = ET.Element(_q(_PR, "Relationships"))
    ET.SubElement(package_rels, _q(_PR, "Relationship"), {"Id": "rId1", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument", "Target": "word/document.xml"})
    ET.SubElement(package_rels, _q(_PR, "Relationship"), {"Id": "rId2", "Type": "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties", "Target": "docProps/core.xml"})
    ET.SubElement(package_rels, _q(_PR, "Relationship"), {"Id": "rId3", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties", "Target": "docProps/app.xml"})
    document_rels = ET.Element(_q(_PR, "Relationships"))
    ET.SubElement(document_rels, _q(_PR, "Relationship"), {"Id": "rId1", "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles", "Target": "styles.xml"})
    return _docx_package(
        {
            "[Content_Types].xml": ET.tostring(content_types, encoding="utf-8", xml_declaration=True),
            "_rels/.rels": ET.tostring(package_rels, encoding="utf-8", xml_declaration=True),
            "word/document.xml": document,
            "word/styles.xml": _screenplay_styles_xml(),
            "word/_rels/document.xml.rels": ET.tostring(document_rels, encoding="utf-8", xml_declaration=True),
            "docProps/core.xml": ET.tostring(core, encoding="utf-8", xml_declaration=True),
            "docProps/app.xml": ET.tostring(app, encoding="utf-8", xml_declaration=True),
        }
    )


def _dialogue_csv(dialogue: Iterable[Mapping[str, Any]]) -> str:
    return " / ".join(f"{row.get('character', '角色')}: {row.get('text', '')}" for row in dialogue)


def shot_list_rows(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
) -> list[list[Any]]:
    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    scene_by_id = {scene["id"]: scene for scene in normalized["scenes"]}
    transitions_by_from = {row["from_shot_id"]: row for row in normalized["transitions"]}
    header = [
        "镜号",
        "场景",
        "景别",
        "角度",
        "运动",
        "主体位置",
        "动作",
        "时长",
        "对白",
        "音效",
        "来源章节",
        "镜头备注",
        "转场",
        "资源引用",
    ]
    rows: list[list[Any]] = [header]
    for shot in normalized["shots"]:
        scene = scene_by_id.get(shot["scene_id"], {})
        transition = transitions_by_from.get(shot["id"], {})
        rows.append(
            [
                shot["number"],
                scene.get("heading") or shot["scene_id"],
                shot["shot_size"],
                shot["camera_angle"],
                shot["camera_motion"],
                shot["subject_position"],
                shot["action"],
                shot["duration_seconds"],
                _dialogue_csv(shot["dialogue"]),
                shot["sound_effect"],
                shot["source_chapter_id"] or scene.get("source_chapter_id", ""),
                shot["notes"],
                transition.get("type") or shot["transition"],
                ";".join(shot["asset_ids"]),
            ]
        )
    return rows


def shot_list_to_csv(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_policy: str = "allow_missing",
) -> bytes:
    """Create an Excel-friendly RFC 4180 CSV with comprehensive shot fields."""

    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = normalize_resource_manifest(resource_manifest, normalized["asset_ids"])
    if _text(resource_policy).lower() == "require_all" and resources["missing_count"]:
        raise IndustryExportResourceError("镜头表引用了缺失资源", details={"missing": resources["missing"], "missing_count": resources["missing_count"]})
    output = io.StringIO(newline="")
    writer = csv.writer(output, dialect="excel", lineterminator="\r\n")
    writer.writerows(shot_list_rows(normalized, title=title, novel_id=novel_id))
    # UTF-8 BOM is intentional: Excel on a clean Windows machine recognises
    # Chinese column names without a manual encoding choice.
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _storyboard_html(
    normalized: Mapping[str, Any],
    *,
    novel_id: object,
    snapshot_id: object,
    source_versions: object,
    resources: Mapping[str, Any],
    resource_paths: Mapping[str, str] | None = None,
) -> str:
    resource_paths = resource_paths or {}
    scene_by_id = {scene["id"]: scene for scene in normalized["scenes"]}
    shot_by_id = {shot["id"]: shot for shot in normalized["shots"]}
    cards = normalized["storyboard"]
    body: list[str] = []
    for card in cards:
        shot = shot_by_id.get(card["shot_id"], {})
        scene = scene_by_id.get(card["scene_id"] or shot.get("scene_id"), {})
        body.append('<article class="card">')
        body.append(f"<h2>镜头 {html.escape(str(card['number']))}</h2>")
        body.append(f"<p class=meta>{html.escape(scene.get('heading') or shot.get('scene_id', '未设定场景'))} · {html.escape(str(shot.get('shot_size', '')))} · {html.escape(str(shot.get('duration_seconds', '')))} 秒</p>")
        body.append(f"<p><strong>画面：</strong>{html.escape(card['frame_prompt'] or '暂无画面描述')}</p>")
        body.append(f"<p><strong>构图：</strong>{html.escape(card['composition'] or '暂无构图说明')}</p>")
        body.append(f"<p><strong>色彩：</strong>{html.escape(card['color'] or '暂无色彩说明')}</p>")
        for asset_id in card["asset_ids"]:
            path = resource_paths.get(asset_id)
            record = next((row for row in resources.get("available", []) + resources.get("missing", []) if row.get("id") == asset_id), {})
            if path and str(record.get("media_type", "")).startswith("image/"):
                body.append(f'<img class="reference" src="{html.escape(path, quote=True)}" alt="{html.escape(str(record.get("filename") or asset_id), quote=True)}">')
            elif record.get("status") != "AVAILABLE" or not record.get("packaged", True):
                body.append(f"<p class=missing>资源缺失：{html.escape(asset_id)} — {html.escape(str(record.get('reason') or 'unavailable'))}</p>")
            else:
                body.append(f"<p class=meta>参考资源：{html.escape(asset_id)}</p>")
        body.append("</article>")
    if not cards:
        body.append('<p class="missing">尚未生成分镜卡。</p>')
    missing = "；".join(f"{row.get('id')}: {row.get('reason', 'unavailable')}" for row in resources.get("missing", [])) or "无"
    metadata = "<br>".join(html.escape(line) for line in _metadata_lines(title=normalized["title"], novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resources=resources))
    return """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>分镜表 - {title}</title><style>
body{{font-family:"Microsoft YaHei",Arial,sans-serif;margin:32px;color:#1f2937;background:#f7f8fa}}
h1{{margin:0 0 8px}} .meta{{color:#64748b;font-size:13px}} .missing{{color:#b42318;background:#fff1f0;border:1px solid #f5c2c0;padding:8px;border-radius:4px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:16px;margin-top:24px}}
.card{{background:#fff;border:1px solid #d7dce3;border-radius:6px;padding:16px;break-inside:avoid}}
.card h2{{margin:0 0 4px;font-size:18px}} .card p{{line-height:1.55}} .reference{{display:block;max-width:100%;max-height:300px;object-fit:contain;margin-top:10px;border:1px solid #e5e7eb}}
.summary{{background:#fff;border:1px solid #d7dce3;padding:12px;border-radius:6px;white-space:normal}}
</style></head><body><h1>分镜表：{title}</h1><div class="summary">{metadata}<br>缺失资源：{missing}</div><main class="grid">{body}</main></body></html>""".format(
        title=html.escape(normalized["title"], quote=True), metadata=metadata, missing=html.escape(missing), body="".join(body)
    )


def _zip_write_deterministic(archive: ZipFile, path: str, content: bytes) -> None:
    info = ZipInfo(str(PurePosixPath(path)))
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, content)


def _package_manifest(
    *,
    package_type: str,
    normalized: Mapping[str, Any],
    novel_id: object,
    snapshot_id: object,
    source_versions: object,
    resources: Mapping[str, Any],
    files: Iterable[str],
) -> bytes:
    payload = {
        "schema_version": INDUSTRY_SCHEMA_VERSION,
        "package_type": package_type,
        "format_version": "1.0",
        "project": {"novel_id": _text(novel_id), "title": normalized["title"]},
        "source": {
            "snapshot_id": _text(snapshot_id),
            "source_versions": source_versions,
            "screenplay_id": normalized.get("id"),
            "screenplay_revision": normalized.get("revision"),
            "shot_revision": normalized.get("shot_revision"),
            "storyboard_revision": normalized.get("storyboard_revision"),
        },
        "resources": {
            "referenced": resources.get("referenced", []),
            "available": resources.get("available", []),
            "missing": resources.get("missing", []),
            "missing_count": resources.get("missing_count", 0),
        },
        "files": sorted(str(item) for item in files),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")


def storyboard_to_package(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    snapshot_id: object = "",
    source_versions: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_loader: object | None = None,
    resource_policy: str = "allow_missing",
) -> bytes:
    """Create a portable storyboard ZIP with HTML, CSV, Fountain and assets."""

    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = resolve_resources(resource_manifest, references=normalized["asset_ids"], loader=resource_loader, novel_id=novel_id, resource_policy=resource_policy)
    resource_paths: dict[str, str] = {}
    files: dict[str, bytes] = {}
    for index, row in enumerate(resources.get("available", []), 1):
        asset_id = _text(row.get("id"))
        if asset_id not in resources.get("binaries", {}):
            continue
        filename = _text(row.get("filename"), default=f"asset-{index:03d}.bin")
        filename = re.sub(r"[\\/\x00-\x1f\x7f]", "_", filename).strip(" .") or f"asset-{index:03d}.bin"
        path = f"resources/{index:03d}-{filename[:180]}"
        resource_paths[asset_id] = path
        files[path] = resources["binaries"][asset_id]
        row["package_path"] = path
    files["storyboard.html"] = _storyboard_html(normalized, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resources=resources, resource_paths=resource_paths).encode("utf-8")
    files["shots.csv"] = shot_list_to_csv(normalized, title=title, novel_id=novel_id, resource_manifest=resources, resource_policy="allow_missing")
    files["screenplay.fountain"] = screenplay_to_fountain(normalized, title=title, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resource_manifest=resources, resource_policy="allow_missing").encode("utf-8")
    files["manifest.json"] = _package_manifest(package_type="storyboard", normalized=normalized, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resources=resources, files=[*files.keys(), "manifest.json"])
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(files):
            _zip_write_deterministic(archive, path, files[path])
    return output.getvalue()


def screenplay_to_package(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    snapshot_id: object = "",
    source_versions: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_loader: object | None = None,
    resource_policy: str = "allow_missing",
) -> bytes:
    """Create a screenplay package containing Fountain and industry DOCX."""

    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = resolve_resources(resource_manifest, references=normalized["asset_ids"], loader=resource_loader, novel_id=novel_id, resource_policy=resource_policy)
    files: dict[str, bytes] = {
        "screenplay.fountain": screenplay_to_fountain(normalized, title=title, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resource_manifest=resources, resource_policy="allow_missing").encode("utf-8"),
        "screenplay.docx": screenplay_to_docx(normalized, title=title, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resource_manifest=resources, resource_policy="allow_missing"),
    }
    for index, row in enumerate(resources.get("available", []), 1):
        asset_id = _text(row.get("id"))
        content = resources.get("binaries", {}).get(asset_id)
        if content is None:
            continue
        filename = re.sub(r"[\\/\x00-\x1f\x7f]", "_", _text(row.get("filename"), default=f"asset-{index:03d}.bin")).strip(" .") or f"asset-{index:03d}.bin"
        row["package_path"] = f"resources/{index:03d}-{filename[:180]}"
        files[row["package_path"]] = content
    files["manifest.json"] = _package_manifest(package_type="screenplay", normalized=normalized, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resources=resources, files=[*files.keys(), "manifest.json"])
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(files):
            _zip_write_deterministic(archive, path, files[path])
    return output.getvalue()


def shot_list_to_package(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    snapshot_id: object = "",
    source_versions: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_loader: object | None = None,
    resource_policy: str = "allow_missing",
) -> bytes:
    """Create a shot-list ZIP with Excel-friendly CSV and manifest."""

    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = resolve_resources(resource_manifest, references=normalized["asset_ids"], loader=resource_loader, novel_id=novel_id, resource_policy=resource_policy)
    files = {
        "shot-list.csv": shot_list_to_csv(normalized, title=title, novel_id=novel_id, resource_manifest=resources, resource_policy="allow_missing"),
    }
    files["manifest.json"] = _package_manifest(package_type="shot-list", normalized=normalized, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resources=resources, files=[*files.keys(), "manifest.json"])
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(files):
            _zip_write_deterministic(archive, path, files[path])
    return output.getvalue()


def storyboard_to_html(
    screenplay: Mapping[str, Any] | object,
    *,
    title: object = "",
    novel_id: object = "",
    snapshot_id: object = "",
    source_versions: object = "",
    resource_manifest: Mapping[str, Any] | object = None,
    resource_policy: str = "allow_missing",
) -> bytes:
    normalized = normalize_screenplay(screenplay, title=title, novel_id=novel_id)
    resources = normalize_resource_manifest(resource_manifest, normalized["asset_ids"])
    if _text(resource_policy).lower() == "require_all" and resources["missing_count"]:
        raise IndustryExportResourceError("分镜引用了缺失资源", details={"missing": resources["missing"], "missing_count": resources["missing_count"]})
    return _storyboard_html(normalized, novel_id=novel_id, snapshot_id=snapshot_id, source_versions=source_versions, resources=resources).encode("utf-8")

