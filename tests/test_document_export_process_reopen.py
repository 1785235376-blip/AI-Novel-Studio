"""Real File-backed document exports survive artifact faults and restart.

Only synthetic manuscript data and artifacts created below tmp_path are used.
The original HTTP assembly, repositories and export queue remain unpatched.
"""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import time
import xml.etree.ElementTree as ET
import zipfile

from pypdf import PdfReader
import pytest

from test_studio_process_reopen_v2 import original_application


pytestmark = pytest.mark.file_backend_only

TITLE = "合成小说 Synthetic Manuscript"
CHAPTER = "第一章 Spring"
PARAGRAPHS = ("春夜有风。", "Synthetic body 123.")


def _ok(response, status):
    assert response.status_code == status, response.text
    return response


def _completed(client, job_id):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        job = _ok(client.get(f"/api/exports/{job_id}"), 200).json()
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            assert job["status"] == "succeeded", job
            return job
        time.sleep(0.05)  # Poll for the real queue; this does not arrange a race.
    pytest.fail("export did not finish")


def _document_text(format, content):
    if format == "docx":
        with zipfile.ZipFile(BytesIO(content)) as archive:
            assert archive.testzip() is None
            return "".join(ET.fromstring(archive.read("word/document.xml")).itertext())
    reader = PdfReader(BytesIO(content), strict=True)
    assert len(reader.pages) >= 1
    return "\n".join(page.extract_text() for page in reader.pages)


@pytest.mark.parametrize("format", ["docx", "pdf"])
def test_original_document_export_content_artifact_recovery_and_restart(tmp_path, format, monkeypatch):
    # Do not let a caller's custom font path or strict release gate determine
    # whether this isolated, portable content test can start.
    monkeypatch.delenv("AI_NOVEL_STUDIO_PDF_FONT", raising=False)
    monkeypatch.delenv("AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT", raising=False)
    root = Path(__file__).resolve().parents[1]
    run = tmp_path / "document-export"
    run.mkdir()
    config = run / "providers.json"
    config.write_text("{}", encoding="utf-8")

    with original_application(root, run, config, "first-backend.log") as client:
        novel = _ok(client.post("/api/novels", json={"title": TITLE}), 201).json()
        nid = novel["id"]
        _ok(client.post(f"/api/novels/{nid}/chapters", json={
            "title": CHAPTER, "content": "\n\n".join(PARAGRAPHS),
        }), 201)
        job = _ok(client.post("/api/exports", params={"novel_id": nid},
                              json={"format": format}), 202).json()
        job_id = job["id"]
        _completed(client, job_id)
        download = f"/api/exports/{job_id}/download"
        content = _ok(client.get(download), 200).content
        text = _document_text(format, content)
        for expected in (TITLE, CHAPTER, *PARAGRAPHS):
            assert expected in text

        digest = sha256(content).hexdigest()
        artifacts = [p for p in (run / "data").rglob("*.artifact")
                     if sha256(p.read_bytes()).hexdigest() == digest]
        assert len(artifacts) == 1
        artifact = artifacts[0]
        try:
            # Corrupt only this newly generated synthetic artifact.  A corrupt
            # file must not silently fall back to the embedded queue result.
            artifact.write_bytes(bytes([content[0] ^ 1]) + content[1:])
            rejected = _ok(client.get(download), 500)
            assert rejected.json()["detail"]["code"] == "EXPORT_RESULT_INVALID"
            artifact.write_bytes(content)
            assert _ok(client.get(download), 200).content == content

            # The owner intentionally permits recovery from a missing file via
            # the bounded result saved in the queue record.
            artifact.unlink()
            assert _ok(client.get(download), 200).content == content
        finally:
            artifact.write_bytes(content)

    with original_application(root, run, config, "restarted-backend.log") as client:
        reopened = _ok(client.get(download), 200).content
        assert sha256(reopened).hexdigest() == digest
        assert reopened == content
