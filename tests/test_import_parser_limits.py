"""Independent regression coverage for bounded binary-import decoders.

``app.import_parsers`` accepts author-supplied Word/PDF bytes through the legacy
import route. The archive, its XML part, and PDF extraction are bounded before
parsing so a crafted import cannot expand without limit or declare XML entities.
The newer research-extraction importer already enforces equivalent limits; this
suite binds them to the legacy decoder path.

All archives and PDFs are synthetic in-memory bytes. No real document or native
tool is used.
"""
from __future__ import annotations

import io
import sys
import zipfile
from types import SimpleNamespace

import pytest

from app import import_parsers


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def _docx_bytes(document_xml: bytes, extra_members: tuple[tuple[str, bytes], ...] = ()) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", document_xml)
        for name, payload in extra_members:
            archive.writestr(name, payload)
    return buffer.getvalue()


def _document_xml(text: str = "第一章") -> bytes:
    return (
        f'<w:document xmlns:w="{WORD_NS}"><w:body>'
        f'<w:p><w:r><w:t>{text}</w:t></w:r></w:p>'
        f"</w:body></w:document>"
    ).encode("utf-8")


def test_docx_still_decodes_an_ordinary_document():
    assert import_parsers.docx_to_text(_docx_bytes(_document_xml())) == "第一章"


def test_docx_member_count_is_bounded(monkeypatch):
    monkeypatch.setattr(import_parsers, "MAX_DOCX_ARCHIVE_MEMBERS", 2)
    raw = _docx_bytes(_document_xml(), (("word/extra1.xml", b"<x/>"), ("word/extra2.xml", b"<x/>")))
    with pytest.raises(ValueError, match="invalid Word document"):
        import_parsers.docx_to_text(raw)


def test_docx_member_size_is_bounded(monkeypatch):
    monkeypatch.setattr(import_parsers, "MAX_DOCX_MEMBER_BYTES", 1024)
    with pytest.raises(ValueError, match="invalid Word document"):
        import_parsers.docx_to_text(_docx_bytes(_document_xml("正文" * 1000)))


def test_docx_total_size_is_bounded(monkeypatch):
    monkeypatch.setattr(import_parsers, "MAX_DOCX_TOTAL_BYTES", 100)
    with pytest.raises(ValueError, match="invalid Word document"):
        import_parsers.docx_to_text(_docx_bytes(_document_xml(), (("word/extra.xml", b"<x/>" * 30),)))


def test_docx_compression_ratio_is_bounded(monkeypatch):
    monkeypatch.setattr(import_parsers, "MAX_DOCX_COMPRESSION_RATIO", 2)
    with pytest.raises(ValueError, match="invalid Word document"):
        import_parsers.docx_to_text(_docx_bytes(b"0" * 50000))


def test_docx_compressed_input_is_bounded(monkeypatch):
    monkeypatch.setattr(import_parsers, "MAX_DOCX_COMPRESSED_BYTES", 10)
    with pytest.raises(ValueError, match="invalid Word document"):
        import_parsers.docx_to_text(b"x" * 20)


def test_docx_dtd_or_entity_declarations_are_refused():
    xml = b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">]><root>&lol;</root>'
    with pytest.raises(ValueError, match="invalid Word document XML"):
        import_parsers.docx_to_text(_docx_bytes(xml))


def test_docx_requires_the_document_part():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/other.xml", b"<x/>")
    with pytest.raises(ValueError, match="invalid Word document"):
        import_parsers.docx_to_text(buffer.getvalue())


class _FakePage:
    def __init__(self, text: str):
        self.text = text

    def extract_text(self):
        return self.text


class _FakeReader:
    pages: list[_FakePage] = []

    def __init__(self, _stream):
        pass


def _install_fake_pdf(monkeypatch, pages: list[_FakePage]) -> None:
    reader = type("FakeReader", (_FakeReader,), {"pages": pages})
    monkeypatch.setitem(sys.modules, "pypdf", SimpleNamespace(PdfReader=reader))


def test_pdf_still_decodes_an_ordinary_document(monkeypatch):
    _install_fake_pdf(monkeypatch, [_FakePage("Chapter 1"), _FakePage("Body")])
    assert import_parsers.pdf_to_text(b"%PDF-1.4 synthetic") == "Chapter 1\nBody"


def test_pdf_page_count_is_bounded(monkeypatch):
    _install_fake_pdf(monkeypatch, [_FakePage("a")] * 3)
    monkeypatch.setattr(import_parsers, "MAX_PDF_PAGES", 2)
    with pytest.raises(ValueError, match="invalid PDF document"):
        import_parsers.pdf_to_text(b"%PDF-1.4 synthetic")


def test_pdf_extracted_text_is_bounded(monkeypatch):
    _install_fake_pdf(monkeypatch, [_FakePage("x" * 100)])
    monkeypatch.setattr(import_parsers, "MAX_PDF_TEXT_CHARS", 10)
    with pytest.raises(ValueError, match="invalid PDF document"):
        import_parsers.pdf_to_text(b"%PDF-1.4 synthetic")


def test_pdf_input_size_is_bounded(monkeypatch):
    monkeypatch.setattr(import_parsers, "MAX_PDF_BYTES", 16)
    with pytest.raises(ValueError, match="invalid PDF document"):
        import_parsers.pdf_to_text(b"%PDF-1.4 " + b"x" * 32)


def test_pdf_requires_the_pdf_signature():
    with pytest.raises(ValueError, match="invalid PDF document"):
        import_parsers.pdf_to_text(b"not a pdf")
