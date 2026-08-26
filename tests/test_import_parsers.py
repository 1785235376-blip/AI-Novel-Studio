import base64
import io
import zipfile

import pytest

from app.import_parsers import decode_base64, docx_to_text, pdf_to_text


def test_docx_parser_extracts_paragraphs_and_tabs():
    xml = '''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>第一章</w:t></w:r></w:p><w:p><w:r><w:t>正文</w:t><w:tab/><w:t>续写</w:t></w:r></w:p></w:body></w:document>'''.encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", xml)
    assert docx_to_text(output.getvalue()) == "第一章\n正文\t续写"


def test_pdf_fallback_extracts_simple_literal_text():
    assert pdf_to_text(b"%PDF-1.4 (Chapter 1) Tj (Body) Tj") == "Chapter 1\nBody"


def test_binary_import_requires_valid_base64_and_supported_payload():
    with pytest.raises(ValueError, match="base64"):
        decode_base64("not base64")
