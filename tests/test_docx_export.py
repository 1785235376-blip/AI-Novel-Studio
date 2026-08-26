import base64
import io
import time
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from xml.etree import ElementTree as ET

from app.export_formats import novel_to_docx, novel_to_epub
from app.services.export_job_service import ExportJobService
from app.services.novel_service import NovelService


def _wait_for_success(service: ExportJobService, job_id: str) -> dict:
    current = service.get(job_id)
    for _ in range(200):
        if current["status"] == "succeeded":
            return current
        time.sleep(0.01)
        current = service.get(job_id)
    assert current["status"] == "succeeded"
    return current


def test_stdlib_docx_export_is_a_valid_ooxml_package_with_chapter_text():
    raw = novel_to_docx("示例小说", [{"title": "第一章", "content": "开场\n\n正文"}])
    assert raw.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert archive.testzip() is None
        names = set(archive.namelist())
        assert {
            "[Content_Types].xml",
            "_rels/.rels",
            "word/document.xml",
            "word/styles.xml",
        } <= names
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in names)
        document = ET.fromstring(archive.read("word/document.xml"))
        text = "".join(document.itertext())
        assert "示例小说" in text and "第一章" in text and "开场" in text and "正文" in text


def test_novel_service_docx_export_and_queue_download_binary_payload():
    novels = type("Novels", (), {"get": lambda self, novel_id: {"id": novel_id, "title": "书"}})()
    chapters = type("Chapters", (), {"list": lambda self, _novel_id: [{"title": "第一章", "content": "正文"}]})()
    novel_service = NovelService(novels, chapters)
    exported = novel_service.export("novel-a", "docx")
    assert exported["format"] == "docx"
    assert exported["content_encoding"] == "base64"
    assert base64.b64decode(exported["content_base64"], validate=True).startswith(b"PK")

    with TemporaryDirectory() as root:
        service = ExportJobService(Path(root), lambda *_: exported)
        try:
            job = service.create("novel-a", "docx")
            _wait_for_success(service, job["id"])
            payload = service.download(job["id"])
            assert payload["filename"] == "novel-a.docx"
            assert payload["media_type"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            with zipfile.ZipFile(io.BytesIO(payload["content"])) as archive:
                assert archive.testzip() is None
                assert "word/document.xml" in archive.namelist()
        finally:
            service._pool.shutdown(wait=True)


def test_stdlib_epub_export_has_required_container_navigation_and_text():
    raw = novel_to_epub("示例电子书", [{"title": "第一章", "content": "开场\n正文"}], "novel-a")
    assert raw.startswith(b"PK")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        assert entries[0].filename == "mimetype"
        assert entries[0].compress_type == zipfile.ZIP_STORED
        assert archive.read("mimetype") == b"application/epub+zip"
        assert {
            "META-INF/container.xml",
            "OEBPS/content.opf",
            "OEBPS/nav.xhtml",
            "OEBPS/content.xhtml",
        } <= set(archive.namelist())
        assert all(not name.startswith("/") and ".." not in Path(name).parts for name in archive.namelist())
        container = ET.fromstring(archive.read("META-INF/container.xml"))
        assert any(node.attrib.get("full-path") == "OEBPS/content.opf" for node in container.iter())
        package = ET.fromstring(archive.read("OEBPS/content.opf"))
        assert package.attrib.get("unique-identifier") == "pub-id"
        assert "dcterms:" in package.attrib.get("prefix", "")
        nav = ET.fromstring(archive.read("OEBPS/nav.xhtml"))
        content = ET.fromstring(archive.read("OEBPS/content.xhtml"))
        nav_text = "".join(nav.itertext())
        content_text = "".join(content.itertext())
        assert "第一章" in nav_text and "第一章" in content_text and "正文" in content_text
