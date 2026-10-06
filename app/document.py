"""Original rich-document authority and explicit, non-mutating text projections.

Markdown is a readable derived view, never a lossless storage/selection format.
``plain_text`` matches Editor.textBetween with one newline per text block and
hardBreak. Its offsets are Unicode codepoints; ProseMirror offsets are UTF-16
node positions and must continue through the original selection mapper.
"""
from __future__ import annotations

from copy import deepcopy
import re
import warnings


class DocumentProjectionError(ValueError):
    """The document cannot be projected without silently discarding a node."""
    code = "DOCUMENT_PROJECTION_UNSUPPORTED"


_TEXT_BLOCKS = frozenset({"paragraph", "heading", "codeBlock"})
_CONTAINERS = frozenset({"doc", "blockquote", "bulletList", "orderedList", "listItem"})
# These reference atoms and additional marks predate A43 in the original
# portable/relink/project-fork document contract. They must remain storable.
_MEDIA = frozenset({"image", "audio", "video"})
_LEAVES = frozenset({"text", "hardBreak", "horizontalRule"}) | _MEDIA
_MARKS = frozenset({"bold", "italic", "strike", "code", "underline", "subscript", "superscript"})


class DocumentProjectionWarning(UserWarning):
    """A coordinate-only view deliberately excludes known non-text media."""


def _media_placeholder(node: dict) -> str:
    # A text export must disclose its binary omission and preserve descriptive
    # text. Never dereference an asset or expose its internal identifier here.
    values = [f"[{node['type']} media not embedded]"]
    attrs = node.get("attrs") or {}
    for key in ("title", "alt"):
        if isinstance(attrs.get(key), str):
            values.append(attrs[key])
    return "\n".join(values)


def _has_media(doc: dict) -> bool:
    pending = [doc]
    while pending:
        node = pending.pop()
        if node["type"] in _MEDIA:
            return True
        pending.extend(node.get("content", []))
    return False


def markdown_to_document(markdown:str)->dict:
    # This legacy text import is intentionally not used for rich duplication.
    nodes=[]
    for block in re.split(r"\n\s*\n",markdown.strip()):
        if not block: continue
        match=re.match(r"^(#{1,6})\s+(.*)$",block,re.S)
        if match: nodes.append({"type":"heading","attrs":{"level":len(match.group(1))},"content":[{"type":"text","text":match.group(2).strip()}]}); continue
        if block.startswith("```"):
            lines=block.splitlines(); nodes.append({"type":"codeBlock","attrs":{"language":lines[0][3:] or None},"content":[{"type":"text","text":"\n".join(lines[1:-1])}]}); continue
        nodes.append({"type":"paragraph","content":[{"type":"text","text":block.replace("\n","\n")}]})
    return {"type":"doc","content":nodes}


def validate_document(doc: dict) -> None:
    """Reject unsupported content explicitly; never rewrite the source JSON.

    Attributes (including paragraph locks) stay in the authoritative document.
    Style-only attributes can be omitted by text renderers; text, nodes and marks
    cannot disappear silently. Diagnostics name only schema types, never prose.
    """
    if not isinstance(doc, dict) or doc.get("type") != "doc":
        raise DocumentProjectionError("unsupported document root")
    pending = [doc]
    while pending:
        node = pending.pop()
        if not isinstance(node, dict) or node.get("type") not in _TEXT_BLOCKS | _CONTAINERS | _LEAVES:
            raise DocumentProjectionError("unsupported document node")
        kind = node["type"]
        children = node.get("content", [])
        if not isinstance(children, list) or not all(isinstance(child, dict) for child in children):
            raise DocumentProjectionError("unsupported document content")
        if kind in _LEAVES and children:
            raise DocumentProjectionError("unsupported leaf content")
        if kind == "text" and not isinstance(node.get("text"), str):
            raise DocumentProjectionError("unsupported document text")
        if kind != "text" and "text" in node:
            raise DocumentProjectionError("unsupported text outside a text node")
        attrs = node.get("attrs") or {}
        if not isinstance(attrs, dict):
            raise DocumentProjectionError("unsupported document attributes")
        if kind in _MEDIA:
            allowed = {"asset_id", "title"} | ({"alt"} if kind == "image" else set())
            asset_id = attrs.get("asset_id")
            if (set(attrs) - allowed or not isinstance(asset_id, str)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,239}", asset_id) is None):
                raise DocumentProjectionError("unsupported media reference or attributes")
            if any(value is not None and (not isinstance(value, str) or len(value) > 200)
                   for key, value in attrs.items() if key != "asset_id"):
                raise DocumentProjectionError("unsupported media descriptive text")
        if kind == "heading" and (type(attrs.get("level", 1)) is not int or not 1 <= attrs.get("level", 1) <= 6):
            raise DocumentProjectionError("unsupported heading level")
        if kind == "orderedList" and type(attrs.get("start", 1)) is not int:
            raise DocumentProjectionError("unsupported ordered list start")
        if kind == "codeBlock" and not isinstance(attrs.get("language") or "", str):
            raise DocumentProjectionError("unsupported code language")
        marks = node.get("marks", [])
        if not isinstance(marks, list) or any(not isinstance(mark, dict) or mark.get("type") not in _MARKS for mark in marks):
            raise DocumentProjectionError("unsupported document mark")
        if kind in _TEXT_BLOCKS and any(child.get("type") not in {"text", "hardBreak"} for child in children):
            raise DocumentProjectionError("unsupported inline document node")
        if kind in _CONTAINERS and any(child.get("type") in {"text", "hardBreak", "doc"} for child in children):
            raise DocumentProjectionError("unsupported block document node")
        if kind in {"bulletList", "orderedList"} and any(child.get("type") != "listItem" for child in children):
            raise DocumentProjectionError("unsupported list child")
        pending.extend(children)


def _inline_text(node: dict, *, media_placeholders: bool = False) -> str:
    if node["type"] in _MEDIA:
        return _media_placeholder(node) if media_placeholders else ""
    if node["type"] == "text":
        return node["text"]
    if node["type"] == "hardBreak":
        return "\n"
    return "".join(_inline_text(child, media_placeholders=media_placeholders) for child in node.get("content", []))


def _text_blocks(node: dict, *, media_placeholders: bool = False):
    if node["type"] in _TEXT_BLOCKS:
        yield _inline_text(node, media_placeholders=media_placeholders)
    elif node["type"] in _MEDIA and media_placeholders:
        yield _media_placeholder(node)
    else:
        for child in node.get("content", []):
            yield from _text_blocks(child, media_placeholders=media_placeholders)


def plain_text(doc: dict, *, media_placeholders: bool = False) -> str:
    """Editor/search/Interop text: no syntax, codepoint offsets, no final LF.

    Nested block containers do not add separators of their own. Empty text
    blocks do; a horizontalRule has no text. Marks add no characters. Known
    media atoms have no editor-coordinate text; warn instead of silently
    treating that view as a full export. Exporters request visible placeholders
    and descriptive metadata explicitly, never using them as editor offsets.
    """
    validate_document(doc)
    if not media_placeholders and _has_media(doc):
        warnings.warn("Editor coordinate projection excludes non-text media; export projection retains media descriptions and omission markers.",
                      DocumentProjectionWarning, stacklevel=2)
    return "\n".join(_text_blocks(doc, media_placeholders=media_placeholders))


def _markdown_inline(node: dict) -> str:
    # Retain the legacy inline-text contract: marks remain losslessly in JSON,
    # but do not inject syntax into saved-source strings or text coordinates.
    return _inline_text(node)


def _markdown_block(node: dict) -> str:
    kind = node["type"]
    attrs = node.get("attrs") or {}
    if kind == "heading":
        return "#" * attrs.get("level", 1) + " " + _inline_text(node)
    if kind == "paragraph":
        return _markdown_inline(node)
    if kind == "codeBlock":
        value = _inline_text(node)
        fence = "`" * max(3, max((len(m.group()) + 1 for m in re.finditer(r"`+", value)), default=0))
        return fence + (attrs.get("language") or "") + "\n" + value + "\n" + fence
    if kind == "horizontalRule":
        return "---"
    if kind in _MEDIA:
        return _media_placeholder(node)
    if kind in {"bulletList", "orderedList"}:
        items = []
        for index, child in enumerate(node.get("content", []), attrs.get("start", 1)):
            marker = f"{index}. " if kind == "orderedList" else "- "
            lines = _markdown_block(child).split("\n")
            items.append(marker + lines[0] + "".join("\n" + " " * len(marker) + line for line in lines[1:]))
        return "\n".join(items)
    content = "\n\n".join(_markdown_block(child) for child in node.get("content", []))
    if kind == "blockquote":
        return "\n".join("> " + line if line else ">" for line in content.split("\n"))
    return content


def document_to_markdown(doc: dict) -> str:
    """Readable full-text projection; structured JSON remains authoritative."""
    validate_document(doc)
    if not doc.get("content"):
        return ""
    return _markdown_block(doc) + "\n\n"


def clone_document_with_title(doc: dict, title: str) -> dict:
    """Deep-copy the manuscript, replacing only its leading chapter-title H1."""
    validate_document(doc)
    result = deepcopy(doc)
    nodes = result.setdefault("content", [])
    heading = {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": title}]}
    if nodes and nodes[0].get("type") == "heading" and (nodes[0].get("attrs") or {}).get("level", 1) == 1:
        original_text = next((node for node in nodes[0].get("content", []) if node["type"] == "text"), {})
        if original_text.get("marks"):
            heading["content"][0]["marks"] = deepcopy(original_text["marks"])
        heading = {**nodes[0], "content": heading["content"]}
        nodes[0] = heading
    else:
        nodes.insert(0, heading)
    return result


def chapter_body_text(chapter, *, markdown: bool = False) -> str:
    """Render a chapter once, omitting only an exact redundant leading title.

    Exporters add a chapter heading separately. A legacy content-only snapshot
    remains usable; a present structured document always wins over stale text.
    Unknown structured nodes raise instead of falling back to a lossy cache.
    """
    document = chapter.get("document")
    if document is None:
        return str(chapter.get("content") or "")
    validate_document(document)
    nodes = document.get("content", [])
    if (nodes and nodes[0]["type"] == "heading" and (nodes[0].get("attrs") or {}).get("level", 1) == 1
        and _inline_text(nodes[0]) == str(chapter.get("title") or "")):
        document = {**document, "content": nodes[1:]}
    return document_to_markdown(document) if markdown else plain_text(document, media_placeholders=True)
