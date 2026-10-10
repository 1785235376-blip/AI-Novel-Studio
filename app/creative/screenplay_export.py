"""Read-only projection of a Creative screenplay into existing industry formats.

CreativeService remains the document/version owner. This adapter creates neither
a legacy screenplay record nor an asset, job, or model invocation.
"""
from __future__ import annotations

import copy
import hashlib

from .. import industry_export_formats as industry

FORMATS = {
    "fountain": ("text/x-fountain", "fountain"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "markdown": ("text/markdown", "md"),
}
MAX_EXPORT_BYTES = 8_000_000


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
                "markdown": industry.screenplay_to_markdown}[format]
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
