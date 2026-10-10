"""Pure screenplay EPUB projection; no API, persistence or layout acceptance.

Run through scripts/run_v2_checks.py for the repository's isolated test profile.
"""
import copy
import hashlib
import io
import json
from uuid import NAMESPACE_URL, uuid5
from xml.etree import ElementTree as ET
from zipfile import ZIP_STORED, ZipFile

import pytest

from app import export_formats, industry_export_formats
from app.creative import screenplay_export


NS = {
    "container": "urn:oasis:names:tc:opendocument:xmlns:container",
    "opf": "http://www.idpf.org/2007/opf",
    "dc": "http://purl.org/dc/elements/1.1/",
    "html": "http://www.w3.org/1999/xhtml",
    "epub": "http://www.idpf.org/2007/ops",
}
DIGEST = "d" * 64


def row():
    return {
        "id": "creative-epub", "novel_id": "novel-epub", "version": 3,
        "mode": "SCREENPLAY", "status": "DRAFT", "title": '夜航 & <晨光> "é" 🎬',
        "source_evidence": {"chapter-a": {"version": 2, "digest": "c" * 64}},
        "source_documents": {"document-a": {"version": 1, "digest": "a" * 64}},
        "scenes": [
            {"id": "scene-z", "sequence": 20, "heading": "ext. 港口 & <夜> - night",
             "location": "旧港码头", "time": "午夜之后", "emotion": "克制",
             "action": "  风穿过码头。\r\n\r\n继续。\t  ",
             "dialogue": [
                 {"speaker": "旅人 & Élodie", "text": '  别忘记 <这座城>。\n\n下一句。  ',
                  "delivery": "轻声 & 犹豫"},
                 {"speaker": "守夜人", "text": "我记得。", "delivery": "(点头)"},
             ]},
            {"id": "scene-a", "sequence": 10, "heading": "第二场：归途",
             "location": "", "time": "", "emotion": "", "action": "天色渐明。",
             "dialogue": []},
        ],
    }


def parts(result):
    with ZipFile(io.BytesIO(result["content"])) as archive:
        assert archive.testzip() is None
        return {name: ET.fromstring(archive.read(name)) for name in archive.namelist()
                if name != "mimetype"}


def paragraphs(section):
    return [node.text or "" for node in section.findall("html:p", NS)]


def test_epub_container_manifest_spine_and_navigation_resolve_to_saved_scene_order():
    source = row()
    before = copy.deepcopy(source)
    result = screenplay_export.render(source, DIGEST, "epub")
    with ZipFile(io.BytesIO(result["content"])) as archive:
        entries = archive.infolist()
        assert len(entries) == len({entry.filename for entry in entries}) == 5
        assert entries[0].filename == "mimetype" and entries[0].header_offset == 0
        assert entries[0].compress_type == ZIP_STORED and entries[0].extra == b""
        assert archive.read("mimetype") == b"application/epub+zip"
        assert set(archive.namelist()) == {
            "mimetype", "META-INF/container.xml", "OEBPS/content.opf",
            "OEBPS/nav.xhtml", "OEBPS/content.xhtml",
        }
        assert all(not entry.flag_bits & 1 for entry in entries)
    documents = parts(result)
    rootfile = documents["META-INF/container.xml"].find("container:rootfiles/container:rootfile", NS)
    assert rootfile.attrib == {
        "full-path": "OEBPS/content.opf", "media-type": "application/oebps-package+xml",
    }
    package = documents[rootfile.attrib["full-path"]]
    assert package.attrib["version"] == "3.0"
    assert package.attrib["unique-identifier"] == "pub-id"
    assert package.find("opf:metadata/dc:title", NS).text == source["title"]
    identifier = package.find("opf:metadata/dc:identifier", NS)
    expected_id = uuid5(NAMESPACE_URL, "ai-novel-studio:epub:novel-epub:creative-epub:v3")
    assert identifier.attrib["id"] == "pub-id" and identifier.text == f"urn:uuid:{expected_id}"
    assert package.find("opf:metadata/opf:meta[@property='dcterms:modified']", NS).text.endswith("Z")
    manifest = {item.attrib["id"]: item.attrib for item in package.findall("opf:manifest/opf:item", NS)}
    assert manifest == {
        "nav": {"id": "nav", "href": "nav.xhtml", "media-type": "application/xhtml+xml", "properties": "nav"},
        "content": {"id": "content", "href": "content.xhtml", "media-type": "application/xhtml+xml"},
    }
    # The existing encoder has one spine document, with one section per scene.
    assert [item.attrib["idref"] for item in package.findall("opf:spine/opf:itemref", NS)] == ["content"]
    content = documents["OEBPS/content.xhtml"]
    sections = content.findall("html:body/html:section", NS)
    assert [section.attrib["id"] for section in sections] == ["chapter-1", "chapter-2"]
    assert [section.find("html:h2", NS).text for section in sections] == [scene["heading"] for scene in source["scenes"]]
    nav = documents["OEBPS/nav.xhtml"].find("html:body/html:nav", NS)
    assert nav.attrib[f"{{{NS['epub']}}}type"] == "toc"
    links = nav.findall("html:ol/html:li/html:a", NS)
    for link, section in zip(links, sections, strict=True):
        path, fragment = link.attrib["href"].split("#")
        assert "OEBPS/" + path in documents
        assert fragment == section.attrib["id"]
        assert link.text == section.find("html:h2", NS).text
    assert result["media_type"] == "application/epub+zip"
    assert result["filename"] == "creative-creative-epub-v3.epub"
    assert result["format"] == "epub" and result["document_id"] == source["id"]
    assert result["document_version"] == 3 and result["document_digest"] == DIGEST
    assert result["sha256"] == hashlib.sha256(result["content"]).hexdigest()
    assert source == before


def test_epub_preserves_unicode_literal_text_and_body_whitespace_without_remote_media():
    source = row()
    literal = '<script src="https://example.invalid/private.js">alert(1)</script> & [[literal]]'
    source["scenes"][1]["action"] = literal
    content = parts(screenplay_export.render(source, DIGEST, "epub"))["OEBPS/content.xhtml"]
    sections = content.findall("html:body/html:section", NS)
    first = paragraphs(sections[0])
    assert first[4:] == [
        "", "情绪：克制", "", "地点：旧港码头", "时间：午夜之后", "",
        "  风穿过码头。", "", "继续。\t  ", "", "旅人 & Élodie", "(轻声 & 犹豫)",
        "  别忘记 <这座城>。", "", "下一句。  ", "", "守夜人", "(点头)", "我记得。",
    ]
    assert paragraphs(sections[1]) == [literal]
    assert content.find("html:body/html:h1", NS).text == source["title"]
    assert content.find("html:head/html:title", NS).text == source["title"]
    assert all(node.tag.rsplit("}", 1)[-1] not in {"script", "img", "audio", "video", "iframe", "link"}
               for node in content.iter())
    assert all("src" not in node.attrib and "href" not in node.attrib for node in content.iter())


def test_epub_embeds_only_existing_allowlisted_provenance_and_uses_original_encoder(monkeypatch):
    source = row()
    private = "private-model-request-and-proposal-receipt"
    source.update(history=[private], generation_provenance={"request": private}, proposal_receipt=private)
    source["scenes"][0]["director_notes"] = [{"note": private}]
    original = export_formats.novel_to_epub
    calls = []

    def encode(title, chapters, identifier=""):
        calls.append((title, copy.deepcopy(chapters), identifier))
        return original(title, chapters, identifier)

    monkeypatch.setattr(export_formats, "novel_to_epub", encode)
    result = screenplay_export.render(source, DIGEST, "epub")
    assert len(calls) == 1
    title, chapters, identifier = calls[0]
    assert title == source["title"] and identifier == "novel-epub:creative-epub:v3"
    assert len(chapters) == len(source["scenes"])
    first = chapters[0]["content"].split("\n")
    assert first[:3] == ["Exported-By: AI Novel Studio", "Novel-ID: novel-epub", "Snapshot-ID: creative-epub:v3"]
    assert json.loads(first[3].removeprefix("Source-Versions: ")) == {
        "creative_document_id": source["id"], "creative_document_version": 3,
        "creative_document_digest": DIGEST, "source_chapters": source["source_evidence"],
        "source_documents": source["source_documents"],
        "projection": "screenplay text; complete structured metadata remains in JSON export",
    }
    assert private not in "\n".join(parts(result)["OEBPS/content.xhtml"].itertext())


def test_epub_retains_heading_only_scenes_and_does_not_invent_action():
    source = row()
    for scene in source["scenes"]:
        scene.update(action="", dialogue=[], location="", time="", emotion="")
    source.pop("source_documents")
    content = parts(screenplay_export.render(source, DIGEST, "epub"))["OEBPS/content.xhtml"]
    sections = content.findall("html:body/html:section", NS)
    assert len(sections) == 2
    assert paragraphs(sections[0])[4:] == ["", ""]
    assert paragraphs(sections[1]) == [""]
    assert "暂无" not in "".join(content.itertext())


@pytest.mark.parametrize("change,error", [
    ({"scenes": []}, "CREATIVE_SCREENPLAY_EXPORT_SCENES_REQUIRED"),
    ({"mode": "SCRIPT"}, "CREATIVE_SCREENPLAY_EXPORT_MODE_REQUIRED"),
    ({"mode": "DIRECTOR"}, "CREATIVE_SCREENPLAY_EXPORT_MODE_REQUIRED"),
])
def test_epub_reuses_existing_mode_and_nonempty_screenplay_guards(change, error):
    source = row()
    source.update(change)
    before = copy.deepcopy(source)
    with pytest.raises(ValueError, match=f"^{error}$"):
        screenplay_export.render(source, DIGEST, "epub")
    assert source == before


@pytest.mark.parametrize("char", ["\x00", "\x08", "\x0b", "\x0c", "\x1f", "\ud800", "\udfff", "\ufffe", "\uffff"])
@pytest.mark.parametrize("field", [
    "title", "id", "novel_id", "digest", "heading", "action", "location", "time", "emotion",
    "speaker", "text", "delivery", "source_value", "source_key", "document_source_value",
])
def test_epub_rejects_invalid_xml_text_before_shared_encoder_can_filter_it(monkeypatch, char, field):
    source = row()
    value = "before" + char + "after"
    digest = DIGEST
    if field in {"title", "id", "novel_id"}:
        source[field] = value
    elif field == "digest":
        digest = value
    elif field in {"speaker", "text", "delivery"}:
        source["scenes"][0]["dialogue"][0][field] = value
    elif field == "source_value":
        source["source_evidence"]["chapter-a"]["digest"] = value
    elif field == "source_key":
        source["source_evidence"][value] = source["source_evidence"].pop("chapter-a")
    elif field == "document_source_value":
        source["source_documents"]["document-a"]["digest"] = value
    else:
        source["scenes"][0][field] = value
    before = copy.deepcopy(source)

    def unexpected(*args, **kwargs):
        pytest.fail("invalid text reached the EPUB encoder")

    monkeypatch.setattr(export_formats, "novel_to_epub", unexpected)
    with pytest.raises(ValueError, match="^CREATIVE_SCREENPLAY_EPUB_TEXT_UNREPRESENTABLE$"):
        screenplay_export.render(source, digest, "epub")
    assert source == before


def test_epub_accepts_xml_unicode_boundaries_and_normalizes_only_line_endings():
    source = row()
    body = "\t  \u007f\u0085\ud7ff\ue000\ufffd\U00010000\U0010ffff  \r\n\n\rEnd  "
    source["scenes"][1]["action"] = body
    content = parts(screenplay_export.render(source, DIGEST, "epub"))["OEBPS/content.xhtml"]
    section = content.findall("html:body/html:section", NS)[1]
    assert paragraphs(section) == body.replace("\r\n", "\n").replace("\r", "\n").split("\n")


@pytest.mark.parametrize("payload,limit", [(b"", 8_000_000), (b"too big", 6)])
def test_epub_keeps_encoded_capacity_guard_and_never_mutates_input(monkeypatch, payload, limit):
    source = row()
    before = copy.deepcopy(source)
    monkeypatch.setattr(export_formats, "novel_to_epub", lambda *args, **kwargs: payload)
    monkeypatch.setattr(screenplay_export, "MAX_EXPORT_BYTES", limit)
    with pytest.raises(ValueError, match="^CREATIVE_SCREENPLAY_EXPORT_CAPACITY$"):
        screenplay_export.render(source, DIGEST, "epub")
    assert source == before


@pytest.mark.parametrize("format,encoder,mime,extension", [
    ("fountain", "screenplay_to_fountain_bytes", "text/x-fountain", "fountain"),
    ("docx", "screenplay_to_docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    ("markdown", "screenplay_to_markdown", "text/markdown", "md"),
])
def test_original_format_dispatch_snapshot_and_receipt_are_unchanged(monkeypatch, format, encoder, mime, extension):
    source = row()
    before = copy.deepcopy(source)
    original = getattr(industry_export_formats, encoder)
    captured = []

    def encode(snapshot, **kwargs):
        content = original(snapshot, **kwargs)
        captured.append((copy.deepcopy(snapshot), kwargs, content))
        return content

    monkeypatch.setattr(industry_export_formats, encoder, encode)
    monkeypatch.setattr(export_formats, "novel_to_epub", lambda *args, **kwargs: pytest.fail("old format used EPUB"))
    result = screenplay_export.render(source, DIGEST, format)
    assert len(captured) == 1
    snapshot, kwargs, content = captured[0]
    expected_scenes = copy.deepcopy(source["scenes"])
    expected_scenes[0]["action"] = "地点：旧港码头\n时间：午夜之后\n\n" + source["scenes"][0]["action"]
    for scene in expected_scenes:
        scene["dialogue"] = [{"character": line["speaker"], "text": line["text"],
                              "parenthetical": line.get("delivery", "")} for line in scene["dialogue"]]
    assert snapshot == {"id": source["id"], "title": source["title"], "status": source["status"],
                        "revision": source["version"], "scenes": expected_scenes}
    assert kwargs == {
        "title": source["title"], "novel_id": source["novel_id"], "snapshot_id": "creative-epub:v3",
        "source_versions": {
            "creative_document_id": source["id"], "creative_document_version": 3,
            "creative_document_digest": DIGEST, "source_chapters": source["source_evidence"],
            "source_documents": source["source_documents"],
            "projection": "screenplay text; complete structured metadata remains in JSON export",
        },
    }
    expected_bytes = content.encode("utf-8") if isinstance(content, str) else content
    assert result == {
        "content": expected_bytes, "media_type": mime, "format": format,
        "filename": f"creative-creative-epub-v3.{extension}", "document_id": source["id"],
        "document_version": 3, "document_digest": DIGEST,
        "sha256": hashlib.sha256(expected_bytes).hexdigest(),
    }
    assert source == before
