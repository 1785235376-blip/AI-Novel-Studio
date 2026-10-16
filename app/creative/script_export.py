"""Bounded neutral Script projections through the existing text/DOCX encoders."""
from __future__ import annotations

import hashlib

from ..export_formats import novel_to_docx

FORMATS = {
    "txt": ("text/plain", "txt"),
    "markdown": ("text/markdown", "md"),
    "docx": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
}
MAX_EXPORT_BYTES = 8_000_000


def render(row: dict, digest: str, format: str) -> dict:
    if format not in FORMATS:
        raise ValueError("CREATIVE_SCRIPT_EXPORT_FORMAT_INVALID")
    if row.get("mode") != "SCRIPT" or not row.get("script"):
        raise ValueError("CREATIVE_SCRIPT_EXPORT_MODE_REQUIRED")
    body = row["script"]["body"]
    if format == "docx":
        # The original general DOCX encoder filters XML-invalid controls.
        # Reject them before encoding rather than silently dropping authored text.
        if any(ord(char) < 0x20 and char not in "\t\n\r" or 0xD800 <= ord(char) <= 0xDFFF or ord(char) in {0xFFFE, 0xFFFF}
               for char in row["title"] + body):
            raise ValueError("CREATIVE_SCRIPT_DOCX_TEXT_UNREPRESENTABLE")
        content = novel_to_docx(row["title"], [{"title": "", "content": body}])
    else:
        # Authored Markdown is not rendered inside the app; both text downloads
        # preserve the exact body bytes, with identity carried by HTTP receipts.
        content = body.encode("utf-8")
    if not content or len(content) > MAX_EXPORT_BYTES:
        raise ValueError("CREATIVE_SCRIPT_EXPORT_CAPACITY")
    media_type, extension = FORMATS[format]
    return {"content": content, "media_type": media_type, "format": format,
            "filename": f'creative-{row["id"]}-v{row["version"]}.{extension}',
            "document_id": row["id"], "document_version": row["version"],
            "document_digest": digest, "sha256": hashlib.sha256(content).hexdigest()}
