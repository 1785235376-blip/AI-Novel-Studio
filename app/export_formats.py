"""Dependency-free standard document exporters.

The desktop runtime is intentionally local-first and does not assume that a
system Office installation or a third-party document package is available.
This module therefore emits a small, standards-compliant OOXML package for
DOCX export using only the Python standard library.  It is deliberately
limited to text and chapter structure; richer templates can be added behind
the same boundary later without changing the export queue contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from typing import Iterable, Mapping
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
DCTERMS_NS = "http://purl.org/dc/terms/"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
APP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
XML_NS = "http://www.w3.org/XML/1998/namespace"
XHTML_NS = "http://www.w3.org/1999/xhtml"
EPUB_NS = "http://www.idpf.org/2007/ops"
OPF_NS = "http://www.idpf.org/2007/opf"
CONTAINER_NS = "urn:oasis:names:tc:opendocument:xmlns:container"

ET.register_namespace("w", WORD_NS)
ET.register_namespace("r", REL_NS)
ET.register_namespace("pr", PACKAGE_REL_NS)
ET.register_namespace("ct", CONTENT_TYPES_NS)
ET.register_namespace("cp", CORE_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("dcterms", DCTERMS_NS)
ET.register_namespace("xsi", XSI_NS)
ET.register_namespace("xhtml", XHTML_NS)
ET.register_namespace("epub", EPUB_NS)
ET.register_namespace("opf", OPF_NS)
ET.register_namespace("container", CONTAINER_NS)


def _q(namespace: str, name: str) -> str:
    return f"{{{namespace}}}{name}"


def _clean_text(value: object) -> str:
    """Remove XML 1.0-invalid control characters without altering prose."""
    text = str(value or "")
    return "".join(
        char
        for char in text
        if char in "\t\n\r" or (ord(char) >= 0x20 and not 0xD800 <= ord(char) <= 0xDFFF)
    )


def _text_run(parent: ET.Element, text: str) -> None:
    run = ET.SubElement(parent, _q(WORD_NS, "r"))
    node = ET.SubElement(run, _q(WORD_NS, "t"))
    if text[:1].isspace() or text[-1:].isspace():
        node.set(_q(XML_NS, "space"), "preserve")
    node.text = text


def _paragraph(parent: ET.Element, text: object = "", style: str | None = None) -> None:
    paragraph = ET.SubElement(parent, _q(WORD_NS, "p"))
    if style:
        properties = ET.SubElement(paragraph, _q(WORD_NS, "pPr"))
        paragraph_style = ET.SubElement(properties, _q(WORD_NS, "pStyle"))
        paragraph_style.set(_q(WORD_NS, "val"), style)
    lines = _clean_text(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    for index, line in enumerate(lines):
        if index:
            run = ET.SubElement(paragraph, _q(WORD_NS, "r"))
            ET.SubElement(run, _q(WORD_NS, "br"))
        if line:
            _text_run(paragraph, line)


def _styles_xml() -> bytes:
    styles = ET.Element(_q(WORD_NS, "styles"))

    normal = ET.SubElement(styles, _q(WORD_NS, "style"), {
        _q(WORD_NS, "type"): "paragraph",
        _q(WORD_NS, "default"): "1",
        _q(WORD_NS, "styleId"): "Normal",
    })
    ET.SubElement(normal, _q(WORD_NS, "name"), {_q(WORD_NS, "val"): "Normal"})
    ET.SubElement(normal, _q(WORD_NS, "qFormat"))

    title = ET.SubElement(styles, _q(WORD_NS, "style"), {
        _q(WORD_NS, "type"): "paragraph",
        _q(WORD_NS, "styleId"): "Title",
    })
    ET.SubElement(title, _q(WORD_NS, "name"), {_q(WORD_NS, "val"): "Title"})
    ET.SubElement(title, _q(WORD_NS, "basedOn"), {_q(WORD_NS, "val"): "Normal"})
    ET.SubElement(title, _q(WORD_NS, "qFormat"))
    title_properties = ET.SubElement(title, _q(WORD_NS, "pPr"))
    ET.SubElement(title_properties, _q(WORD_NS, "jc"), {_q(WORD_NS, "val"): "center"})
    title_run = ET.SubElement(title, _q(WORD_NS, "rPr"))
    ET.SubElement(title_run, _q(WORD_NS, "b"))
    ET.SubElement(title_run, _q(WORD_NS, "sz"), {_q(WORD_NS, "val"): "32"})

    heading = ET.SubElement(styles, _q(WORD_NS, "style"), {
        _q(WORD_NS, "type"): "paragraph",
        _q(WORD_NS, "styleId"): "Heading1",
    })
    ET.SubElement(heading, _q(WORD_NS, "name"), {_q(WORD_NS, "val"): "heading 1"})
    ET.SubElement(heading, _q(WORD_NS, "basedOn"), {_q(WORD_NS, "val"): "Normal"})
    ET.SubElement(heading, _q(WORD_NS, "qFormat"))
    heading_run = ET.SubElement(heading, _q(WORD_NS, "rPr"))
    ET.SubElement(heading_run, _q(WORD_NS, "b"))
    ET.SubElement(heading_run, _q(WORD_NS, "sz"), {_q(WORD_NS, "val"): "28"})
    return ET.tostring(styles, encoding="utf-8", xml_declaration=True)


def _document_xml(title: object, chapters: Iterable[Mapping[str, object]]) -> bytes:
    document = ET.Element(_q(WORD_NS, "document"))
    body = ET.SubElement(document, _q(WORD_NS, "body"))
    clean_title = _clean_text(title).strip()
    if clean_title:
        _paragraph(body, clean_title, "Title")

    for chapter in chapters:
        if not isinstance(chapter, Mapping):
            continue
        chapter_title = _clean_text(chapter.get("title", "")).strip()
        if chapter_title:
            _paragraph(body, chapter_title, "Heading1")
        content = _clean_text(chapter.get("content", ""))
        # Keep blank lines as blank paragraphs so the exported manuscript does
        # not collapse intentional paragraph spacing.
        for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            _paragraph(body, line)

    section = ET.SubElement(body, _q(WORD_NS, "sectPr"))
    ET.SubElement(section, _q(WORD_NS, "pgSz"), {
        _q(WORD_NS, "w"): "11906",
        _q(WORD_NS, "h"): "16838",
    })
    ET.SubElement(section, _q(WORD_NS, "pgMar"), {
        _q(WORD_NS, "top"): "1440",
        _q(WORD_NS, "right"): "1440",
        _q(WORD_NS, "bottom"): "1440",
        _q(WORD_NS, "left"): "1440",
        _q(WORD_NS, "header"): "708",
        _q(WORD_NS, "footer"): "708",
        _q(WORD_NS, "gutter"): "0",
    })
    return ET.tostring(document, encoding="utf-8", xml_declaration=True)


def _content_types_xml() -> bytes:
    root = ET.Element(_q(CONTENT_TYPES_NS, "Types"))
    ET.SubElement(root, _q(CONTENT_TYPES_NS, "Default"), {
        "Extension": "rels",
        "ContentType": "application/vnd.openxmlformats-package.relationships+xml",
    })
    ET.SubElement(root, _q(CONTENT_TYPES_NS, "Default"), {
        "Extension": "xml",
        "ContentType": "application/xml",
    })
    ET.SubElement(root, _q(CONTENT_TYPES_NS, "Override"), {
        "PartName": "/word/document.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    })
    ET.SubElement(root, _q(CONTENT_TYPES_NS, "Override"), {
        "PartName": "/word/styles.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
    })
    ET.SubElement(root, _q(CONTENT_TYPES_NS, "Override"), {
        "PartName": "/docProps/core.xml",
        "ContentType": "application/vnd.openxmlformats-package.core-properties+xml",
    })
    ET.SubElement(root, _q(CONTENT_TYPES_NS, "Override"), {
        "PartName": "/docProps/app.xml",
        "ContentType": "application/vnd.openxmlformats-officedocument.extended-properties+xml",
    })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _package_relationships_xml() -> bytes:
    root = ET.Element(_q(PACKAGE_REL_NS, "Relationships"))
    ET.SubElement(root, _q(PACKAGE_REL_NS, "Relationship"), {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
        "Target": "word/document.xml",
    })
    ET.SubElement(root, _q(PACKAGE_REL_NS, "Relationship"), {
        "Id": "rId2",
        "Type": "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
        "Target": "docProps/core.xml",
    })
    ET.SubElement(root, _q(PACKAGE_REL_NS, "Relationship"), {
        "Id": "rId3",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties",
        "Target": "docProps/app.xml",
    })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _document_relationships_xml() -> bytes:
    root = ET.Element(_q(PACKAGE_REL_NS, "Relationships"))
    ET.SubElement(root, _q(PACKAGE_REL_NS, "Relationship"), {
        "Id": "rId1",
        "Type": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles",
        "Target": "styles.xml",
    })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _core_properties_xml(title: object) -> bytes:
    root = ET.Element(_q(CORE_NS, "coreProperties"))
    ET.SubElement(root, _q(DC_NS, "title")).text = _clean_text(title).strip()
    ET.SubElement(root, _q(DC_NS, "creator")).text = "AI Novel Studio"
    ET.SubElement(root, _q(CORE_NS, "lastModifiedBy")).text = "AI Novel Studio"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _app_properties_xml() -> bytes:
    root = ET.Element(_q(APP_NS, "Properties"))
    ET.SubElement(root, _q(APP_NS, "Application")).text = "AI Novel Studio"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def novel_to_docx(title: object, chapters: Iterable[Mapping[str, object]]) -> bytes:
    """Create a readable, standards-compliant DOCX manuscript in memory."""
    files = {
        "[Content_Types].xml": _content_types_xml(),
        "_rels/.rels": _package_relationships_xml(),
        "word/document.xml": _document_xml(title, chapters),
        "word/styles.xml": _styles_xml(),
        "word/_rels/document.xml.rels": _document_relationships_xml(),
        "docProps/core.xml": _core_properties_xml(title),
        "docProps/app.xml": _app_properties_xml(),
    }
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for path, content in files.items():
            archive.writestr(path, content)
    return output.getvalue()


def _xhtml_head(parent: ET.Element, title: str) -> None:
    head = ET.SubElement(parent, _q(XHTML_NS, "head"))
    ET.SubElement(head, _q(XHTML_NS, "meta"), {"charset": "utf-8"})
    ET.SubElement(head, _q(XHTML_NS, "title")).text = title


def _xhtml_body(parent: ET.Element, title: str, chapters: list[Mapping[str, object]]) -> None:
    body = ET.SubElement(parent, _q(XHTML_NS, "body"))
    if title:
        ET.SubElement(body, _q(XHTML_NS, "h1")).text = title
    for index, chapter in enumerate(chapters, 1):
        section = ET.SubElement(body, _q(XHTML_NS, "section"), {"id": f"chapter-{index}"})
        chapter_title = _clean_text(chapter.get("title", "")).strip()
        if chapter_title:
            ET.SubElement(section, _q(XHTML_NS, "h2")).text = chapter_title
        content = _clean_text(chapter.get("content", ""))
        for line in content.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            ET.SubElement(section, _q(XHTML_NS, "p")).text = line


def _epub_content_xhtml(title: object, chapters: list[Mapping[str, object]]) -> bytes:
    clean_title = _clean_text(title).strip() or "AI Novel Studio"
    root = ET.Element(_q(XHTML_NS, "html"), {
        _q(XML_NS, "lang"): "zh-CN",
    })
    _xhtml_head(root, clean_title)
    _xhtml_body(root, clean_title, chapters)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _epub_nav_xhtml(title: object, chapters: list[Mapping[str, object]]) -> bytes:
    clean_title = _clean_text(title).strip() or "AI Novel Studio"
    root = ET.Element(_q(XHTML_NS, "html"), {
        _q(XML_NS, "lang"): "zh-CN",
    })
    _xhtml_head(root, clean_title)
    body = ET.SubElement(root, _q(XHTML_NS, "body"))
    nav = ET.SubElement(body, _q(XHTML_NS, "nav"), {
        _q(EPUB_NS, "type"): "toc",
        "id": "toc",
    })
    ET.SubElement(nav, _q(XHTML_NS, "h1")).text = "目录"
    ordered = ET.SubElement(nav, _q(XHTML_NS, "ol"))
    for index, chapter in enumerate(chapters, 1):
        item = ET.SubElement(ordered, _q(XHTML_NS, "li"))
        link = ET.SubElement(item, _q(XHTML_NS, "a"), {"href": f"content.xhtml#chapter-{index}"})
        link.text = _clean_text(chapter.get("title", "")).strip() or f"第{index}章"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _epub_container_xml() -> bytes:
    root = ET.Element(_q(CONTAINER_NS, "container"), {"version": "1.0"})
    rootfiles = ET.SubElement(root, _q(CONTAINER_NS, "rootfiles"))
    ET.SubElement(rootfiles, _q(CONTAINER_NS, "rootfile"), {
        "full-path": "OEBPS/content.opf",
        "media-type": "application/oebps-package+xml",
    })
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _epub_package_xml(title: object, chapters: list[Mapping[str, object]], identifier: object) -> bytes:
    clean_title = _clean_text(title).strip() or "AI Novel Studio"
    stable_id = uuid5(NAMESPACE_URL, f"ai-novel-studio:epub:{_clean_text(identifier)}")
    root = ET.Element(_q(OPF_NS, "package"), {
        "version": "3.0",
        "unique-identifier": "pub-id",
        "prefix": "dcterms: http://purl.org/dc/terms/",
    })
    metadata = ET.SubElement(root, _q(OPF_NS, "metadata"))
    ET.SubElement(metadata, _q(DC_NS, "identifier"), {"id": "pub-id"}).text = f"urn:uuid:{stable_id}"
    ET.SubElement(metadata, _q(DC_NS, "title")).text = clean_title
    ET.SubElement(metadata, _q(DC_NS, "language")).text = "zh-CN"
    ET.SubElement(metadata, _q(OPF_NS, "meta"), {
        "property": "dcterms:modified",
    }).text = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    manifest = ET.SubElement(root, _q(OPF_NS, "manifest"))
    ET.SubElement(manifest, _q(OPF_NS, "item"), {
        "id": "nav",
        "href": "nav.xhtml",
        "media-type": "application/xhtml+xml",
        "properties": "nav",
    })
    ET.SubElement(manifest, _q(OPF_NS, "item"), {
        "id": "content",
        "href": "content.xhtml",
        "media-type": "application/xhtml+xml",
    })
    spine = ET.SubElement(root, _q(OPF_NS, "spine"))
    ET.SubElement(spine, _q(OPF_NS, "itemref"), {"idref": "content"})
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def novel_to_epub(title: object, chapters: Iterable[Mapping[str, object]], identifier: object = "") -> bytes:
    """Create a minimal EPUB 3 package with a navigable chapter document."""
    normalized = [chapter for chapter in chapters if isinstance(chapter, Mapping)]
    files = [
        ("META-INF/container.xml", _epub_container_xml()),
        ("OEBPS/content.opf", _epub_package_xml(title, normalized, identifier)),
        ("OEBPS/nav.xhtml", _epub_nav_xhtml(title, normalized)),
        ("OEBPS/content.xhtml", _epub_content_xhtml(title, normalized)),
    ]
    output = BytesIO()
    with ZipFile(output, "w") as archive:
        # EPUB requires the mimetype entry to be first, uncompressed, and
        # contain exactly this ASCII token.
        archive.writestr("mimetype", b"application/epub+zip", compress_type=ZIP_STORED)
        for path, content in files:
            archive.writestr(path, content, compress_type=ZIP_DEFLATED)
    return output.getvalue()
