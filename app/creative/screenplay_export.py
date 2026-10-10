"""Read-only projection of a Creative screenplay into existing document formats.

CreativeService remains the document/version owner. This adapter creates neither
a legacy screenplay record nor an asset, job, or model invocation.
"""
from __future__ import annotations

import copy
import hashlib
import json

from .. import industry_export_formats as industry

FORMATS = {
    "fountain": ("text/x-fountain", "fountain"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "markdown": ("text/markdown", "md"),
    "epub": ("application/epub+zip", "epub"),
}
MAX_EXPORT_BYTES = 8_000_000


def _require_epub_xml_text(value: object) -> None:
    """Reject unrepresentable text before the shared encoder can clean it."""
    if isinstance(value, str):
        if any(not (char in "\t\n\r" or 0x20 <= ord(char) <= 0xD7FF
                    or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF)
               for char in value):
            raise ValueError("CREATIVE_SCREENPLAY_EPUB_TEXT_UNREPRESENTABLE")
    elif isinstance(value, dict):
        for key, child in value.items():
            _require_epub_xml_text(key)
            _require_epub_xml_text(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _require_epub_xml_text(child)


def _screenplay_to_epub(snapshot: dict, *, title: str, novel_id: str,
                        snapshot_id: str, source_versions: dict) -> bytes:
    """Project scenes to navigable sections in the original EPUB encoder.

    This is reflowable text, not professional screenplay pagination. Each
    saved scene keeps its own heading/TOC entry in one shared spine document.
    Body whitespace is retained; the original encoder normalizes line endings
    to paragraphs and trims headings. Structured metadata remains in JSON.
    """
    chapters = []
    for scene in snapshot["scenes"]:
        blocks = []
        if scene.get("emotion"):
            blocks.append(f'情绪：{scene["emotion"]}')
        if scene["action"]:
            blocks.append(scene["action"])
        for line in scene["dialogue"]:
            dialogue = [line["character"]]
            if delivery := line["parenthetical"]:
                dialogue.append(delivery if delivery.startswith("(") and delivery.endswith(")")
                                else f"({delivery})")
            dialogue.append(line["text"])
            blocks.append("\n".join(dialogue))
        chapters.append({"title": scene["heading"], "content": "\n\n".join(blocks)})
    # Validate raw allowlisted provenance too: JSON escaping must not turn
    # invalid controls into an apparently successful, altered text export.
    _require_epub_xml_text([title, novel_id, snapshot_id, source_versions, chapters])
    provenance = "\n".join([
        "Exported-By: AI Novel Studio",
        f"Novel-ID: {novel_id}",
        f"Snapshot-ID: {snapshot_id}",
        "Source-Versions: " + json.dumps(source_versions, ensure_ascii=False, sort_keys=True),
    ])
    # Keep one section per scene; a separate metadata chapter would shift the
    # scene navigation. The first scene carries the existing provenance only.
    chapters[0]["content"] = provenance + "\n\n" + chapters[0]["content"]
    from ..export_formats import novel_to_epub
    return novel_to_epub(title, chapters, identifier=f"{novel_id}:{snapshot_id}")


def render(row: dict, digest: str, format: str) -> dict:
    if format not in FORMATS:
        raise ValueError("CREATIVE_SCREENPLAY_EXPORT_FORMAT_INVALID")
    if row.get("mode") != "SCREENPLAY":
        raise ValueError("CREATIVE_SCREENPLAY_EXPORT_MODE_REQUIRED")
    if not row.get("scenes"):
        raise ValueError("CREATIVE_SCREENPLAY_EXPORT_SCENES_REQUIRED")
    scenes = []
    for source in row["scenes"]:
        scene = copy.deepcopy(source)
        # An authored slugline can differ from the separately edited context.
        # Keep those fields visible instead of relying on the legacy heading
        # normalizer, which intentionally favors an authored slugline.
        context = [f'{label}：{source[key]}' for key, label in (("location", "地点"), ("time", "时间"))
                   if source.get(key)]
        if context:
            scene["action"] = "\n".join(context) + "\n\n" + source["action"]
        # The two existing owners deliberately use different field names.
        scene["dialogue"] = [{"character": line["speaker"], "text": line["text"],
                              "parenthetical": line.get("delivery", "")}
                             for line in source["dialogue"]]
        scenes.append(scene)
    snapshot = {"id": row["id"], "title": row["title"], "status": row["status"],
                "revision": row["version"], "scenes": scenes}
    provenance = {"creative_document_id": row["id"], "creative_document_version": row["version"],
                  "creative_document_digest": digest, "source_chapters": row["source_evidence"],
                  "source_documents": row.get("source_documents", {}),
                  "projection": "screenplay text; complete structured metadata remains in JSON export"}
    renderer = {"fountain": industry.screenplay_to_fountain_bytes,
                "docx": industry.screenplay_to_docx,
                "markdown": industry.screenplay_to_markdown,
                "epub": _screenplay_to_epub}[format]
    content = renderer(snapshot, title=row["title"], novel_id=row["novel_id"],
                       snapshot_id=f'{row["id"]}:v{row["version"]}', source_versions=provenance)
    if isinstance(content, str):
        content = content.encode("utf-8")
    if not content or len(content) > MAX_EXPORT_BYTES:
        raise ValueError("CREATIVE_SCREENPLAY_EXPORT_CAPACITY")
    media_type, extension = FORMATS[format]
    return {"content": content, "media_type": media_type, "format": format,
            "filename": f'creative-{row["id"]}-v{row["version"]}.{extension}',
            "document_id": row["id"], "document_version": row["version"],
            "document_digest": digest, "sha256": hashlib.sha256(content).hexdigest()}
