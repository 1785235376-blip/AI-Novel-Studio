"""Real local synthetic file parsers and transport policy; no external fetches."""
import io
import json
import socket
import subprocess
import zipfile
from types import SimpleNamespace

import pytest
from PIL import Image
from pypdf import PdfWriter
from reportlab.pdfgen.canvas import Canvas

from app.experimental import research_extract as extract


def docx(text='Tidal gates open at dawn.', extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', '<Types/>')
        archive.writestr('word/document.xml', f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
        for path, data in extra or []: archive.writestr(path, data)
    return stream.getvalue()


@pytest.mark.parametrize('filename', ['source.txt', 'source.md'])
def test_utf8_exact_unicode_paragraphs_and_untrusted_markup(filename):
    text = '海港😀\n\n<script>alert(1)</script> ![](http://127.0.0.1/private)'
    result = extract.extract_document(filename, text.encode())
    assert [row['text'] for row in result['paragraphs']] == text.split('\n\n')
    assert result['paragraphs'][1]['paragraph'] == 2 and result['paragraphs'][1]['page'] is None


def test_actual_docx_uses_paragraph_citations_ignores_external_relationships():
    result = extract.extract_document('source.docx', docx(extra=[('word/_rels/document.xml.rels', '<Relationships><Relationship Target="http://127.0.0.1/private" TargetMode="External"/></Relationships>')]))
    assert result['paragraphs'] == [{'paragraph': 1, 'page': None, 'text': 'Tidal gates open at dawn.'}]


@pytest.mark.parametrize('path', ['../escape', '/absolute', 'C:/file', 'a\\b'])
def test_docx_archive_paths_failclosed(path):
    with pytest.raises(ValueError, match='ARCHIVE_PATH'): extract.extract_document('bad.docx', docx(extra=[(path, 'malicious')]))


def test_docx_entities_symlinks_bombs_and_corruption_rejected():
    for xml in ['<!DOCTYPE foo [<!ENTITY bar SYSTEM "file:///etc/passwd">]><foo>&bar;</foo>', '<!DOCTYPE foo [<!ENTITY bar "x">]><foo>&bar;</foo>']:
        with pytest.raises(ValueError, match='XML_ENTITY'): extract.extract_document('bad.docx', docx(extra=[('custom.xml', xml)]))
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        member = zipfile.ZipInfo('link'); member.external_attr = (0o120777 << 16)
        archive.writestr(member, '/etc/passwd')
    with pytest.raises(ValueError, match='ARCHIVE_PATH'): extract.extract_document('bad.docx', stream.getvalue())
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w', compression=zipfile.ZIP_DEFLATED) as archive: archive.writestr('bomb', 'x' * 100_000)
    with pytest.raises(ValueError, match='ARCHIVE_RATIO'): extract.extract_document('bad.docx', stream.getvalue())
    with pytest.raises(ValueError): extract.extract_document('bad.docx', b'not an archive')


def test_real_pdf_page_text_and_scanned_blank_not_understood():
    stream = io.BytesIO(); pdf = Canvas(stream); pdf.drawString(72, 700, 'Synthetic tidal source.'); pdf.showPage(); pdf.drawString(72, 700, 'Second page.'); pdf.save()
    result = extract.extract_document('source.pdf', stream.getvalue())
    assert result['paragraphs'][0]['page'] == 1 and result['paragraphs'][1]['page'] == 2
    assert 'Synthetic tidal source.' in result['paragraphs'][0]['text']
    writer = PdfWriter(); writer.add_blank_page(100, 100); stream = io.BytesIO(); writer.write(stream)
    result = extract.extract_document('scan.pdf', stream.getvalue())
    assert result['extraction_status'] == 'OCR_NOT_CONFIGURED' and result['paragraphs'] == []


def test_encrypted_or_malformed_pdf_rejected():
    writer = PdfWriter(); writer.add_blank_page(100, 100); writer.encrypt('synthetic'); stream = io.BytesIO(); writer.write(stream)
    with pytest.raises(ValueError, match='PDF_PARSE_FAILED'): extract.extract_document('encrypted.pdf', stream.getvalue())
    with pytest.raises(ValueError): extract.extract_document('bad.pdf', b'%PDF-invalid')


def test_real_image_preserved_without_ocr_claim():
    stream = io.BytesIO(); Image.new('RGB', (16, 16), 'blue').save(stream, 'PNG')
    result = extract.extract_document('source.png', stream.getvalue())
    assert result['extraction_status'] == 'OCR_NOT_CONFIGURED' and result['paragraphs'] == []
    with pytest.raises(ValueError, match='INVALID_IMAGE'): extract.extract_document('source.png', b'not image')


@pytest.mark.parametrize('name,data', [('../source.txt', b'a'), ('bad.exe', b'a'), ('zero.txt', b''), ('bad.txt', b'\x00'), ('bad.txt', b'\xff'), ('bad.txt', b'x' * (extract.MAX_BYTES + 1))])
def test_file_limits_names_and_types(name, data):
    with pytest.raises(ValueError): extract.extract_document(name, data)


def test_text_extraction_total_bounds():
    with pytest.raises(ValueError, match='EXTRACT_LIMIT'): extract.extract_document('big.txt', b'x' * 1_000_001)


@pytest.mark.parametrize('url', ['file:///etc/passwd', 'https://user:secret@example.org', 'https://example.org:8443', 'http://example.org/#frag', 'http://example.org/\r\nX-Test:bad'])
def test_web_malformed_url_no_connection(url, monkeypatch):
    monkeypatch.setattr(extract.socket, 'getaddrinfo', lambda *args, **kwargs: pytest.fail('invalid URL must precede DNS'))
    with pytest.raises(ValueError): extract._public_target(url)


@pytest.mark.parametrize('address', ['127.0.0.1', '10.1.2.3', '169.254.169.254', '::1', 'fc00::1', '0.0.0.0', '::ffff:127.0.0.1'])
def test_ssrf_blocks_private_literal_dns_or_redirect(address, monkeypatch):
    monkeypatch.setattr(extract.socket, 'getaddrinfo', lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (address, 443))])
    with pytest.raises(ValueError, match='PRIVATE_NETWORK'): extract._public_target('https://source.example')


def test_mixed_dns_private_answer_denied_and_public_pinned(monkeypatch):
    monkeypatch.setattr(extract.socket, 'getaddrinfo', lambda *args, **kwargs: [(2, 1, 6, '', ('8.8.8.8', 443)), (2, 1, 6, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='PRIVATE_NETWORK'): extract._public_target('https://source.example')
    monkeypatch.setattr(extract.socket, 'getaddrinfo', lambda *args, **kwargs: [(2, 1, 6, '', ('8.8.8.8', 443))])
    assert extract._public_target('https://source.example')[2] == '8.8.8.8'


def test_html_plain_text_no_script_images_or_plugin_execution(monkeypatch):
    seen = []
    def response(url, remaining):
        seen.append(url)
        return 200, {'content-type': 'text/html'}, b'<html><head><script>steal()</script></head><p>Public tide notes</p><img src="http://127.0.0.1/private"><script>run plugin</script><p>Second paragraph</p></html>'
    monkeypatch.setattr(extract, '_request_public', response)
    result = extract._fetch_webpage('https://source.example')
    assert seen == ['https://source.example']
    assert [row['text'] for row in result['paragraphs']] == ['Public tide notes', 'Second paragraph']
    assert 'script' not in json.dumps(result) and '127.0.0.1' not in json.dumps(result)


def test_redirect_and_content_type_bounds(monkeypatch):
    monkeypatch.setattr(extract, '_request_public', lambda *args: (302, {'location': '/again'}, b''))
    with pytest.raises(ValueError, match='REDIRECT_LIMIT'): extract._fetch_webpage('https://source.example')
    monkeypatch.setattr(extract, '_request_public', lambda *args: (200, {'content-type': 'application/javascript'}, b'alert(1)'))
    with pytest.raises(ValueError, match='CONTENT_TYPE'): extract._fetch_webpage('https://source.example')


def test_web_hard_timeout_includes_dns(monkeypatch):
    def timeout(*args, **kwargs): raise subprocess.TimeoutExpired('trusted-script', 12)
    monkeypatch.setattr(extract.subprocess, 'run', timeout)
    with pytest.raises(ValueError, match='WEB_TIMEOUT'): extract.fetch_webpage('https://source.example')


def test_authority_rechecked_before_redirect_dispatch(monkeypatch):
    calls, allowed = [], [True]
    def request(url, remaining):
        calls.append(url); allowed[0] = False
        return 302, {'location': 'https://next.example'}, b''
    def guard():
        if not allowed[0]: raise PermissionError('revoked')
    # The old request may finish, but the next redirect must never dispatch.
    with pytest.raises((PermissionError, ValueError)):
        extract._fetch_webpage('https://source.example', request=request, guard=guard)
    assert calls == ['https://source.example']


def test_docx_tabs_and_breaks_follow_existing_binary_decoder_convention():
    content = docx('First</w:t><w:tab/><w:t>second</w:t><w:br/><w:t>third')
    result = extract.extract_document('tabs.docx', content)
    assert result['paragraphs'][0]['text'] == 'First\tsecond\nthird'
