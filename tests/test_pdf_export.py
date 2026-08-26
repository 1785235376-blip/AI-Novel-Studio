from __future__ import annotations

import base64
import time
from pathlib import Path

import pytest

from app.pdf_export import PDFExportError, novel_to_pdf, pdf_font_status
from app.services.export_job_service import ExportJobService
from app.services.novel_service import NovelService


def _wait_for_success(service: ExportJobService, job_id: str) -> dict:
    current = service.get(job_id)
    for _ in range(300):
        if current["status"] == "succeeded":
            return current
        if current["status"] == "failed":
            pytest.fail(f"PDF export failed: {current.get('error')}")
        time.sleep(0.01)
        current = service.get(job_id)
    pytest.fail(f"PDF export did not finish: {current}")


def test_novel_to_pdf_is_a_valid_cjk_artifact_with_embedded_or_cid_font():
    raw = novel_to_pdf(
        "示例小说",
        [{"title": "第一章 春夜", "content": "这是中文正文。\n\n第二段包含 English 123。"}],
    )
    assert raw.startswith(b"%PDF-")
    assert b"%%EOF" in raw[-128:]
    # ReportLab emits a ToUnicode map for an embedded TrueType font.  The CID
    # fallback has a Type0/STSong resource instead; either path is a real PDF,
    # never a placeholder text file.
    assert b"/Font" in raw and (b"/ToUnicode" in raw or b"STSong-Light" in raw)
    status = pdf_font_status()
    assert status["available"] is True
    assert status["font_mode"] in {"embedded", "cid-fallback"}


def test_strict_pdf_mode_rejects_unembedded_fallback(monkeypatch):
    # Force the candidate search away from the Windows/system fonts.  This is
    # portable across CI and documents the release gate for a bundled OFL font.
    monkeypatch.setenv("AI_NOVEL_STUDIO_PDF_FONT", str(Path("Z:/missing-font.ttf")))
    monkeypatch.setenv("AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT", "1")
    if pdf_font_status()["embedded"]:
        pytest.skip("the host provides a CJK font and this environment cannot simulate a missing system font")
    with pytest.raises(PDFExportError) as error:
        novel_to_pdf("测试", [{"title": "第一章", "content": "正文"}])
    assert error.value.code == "PDF_CJK_FONT_NOT_EMBEDDED"


def test_novel_service_pdf_export_returns_downloadable_binary_payload():
    novels = type("Novels", (), {"get": lambda self, novel_id: {"id": novel_id, "title": "书"}})()
    chapters = type("Chapters", (), {"list": lambda self, _novel_id: [{"title": "第一章", "content": "正文"}]})()
    service = NovelService(novels, chapters)
    exported = service.export("novel-pdf", "pdf")
    assert exported["format"] == "pdf"
    assert exported["filename"] == "novel-pdf.pdf"
    assert exported["media_type"] == "application/pdf"
    assert base64.b64decode(exported["content_base64"], validate=True).startswith(b"%PDF-")


def test_async_pdf_export_persists_artifact_and_downloads(tmp_path: Path):
    novels = type("Novels", (), {"get": lambda self, novel_id: {"id": novel_id, "title": "书"}})()
    chapters = type("Chapters", (), {"list": lambda self, _novel_id: [{"title": "第一章", "content": "正文"}]})()
    novel_service = NovelService(novels, chapters)
    queue = ExportJobService(tmp_path, novel_service.export)
    try:
        job = queue.create("novel-pdf", "pdf", "pdf-idempotency")
        duplicate = queue.create("novel-pdf", "pdf", "pdf-idempotency")
        assert duplicate["id"] == job["id"]
        completed = _wait_for_success(queue, job["id"])
        assert completed["artifact"]["sha256"]
        payload = queue.download(job["id"])
        assert payload["filename"] == "novel-pdf.pdf"
        assert payload["media_type"] == "application/pdf"
        assert payload["content"].startswith(b"%PDF-")
    finally:
        queue._pool.shutdown(wait=True)

