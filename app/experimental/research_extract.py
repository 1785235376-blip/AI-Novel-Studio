"""Bounded local extraction and explicit public-web acquisition. Contents are data.

No shell, remote images, browser, credentials, automatic fetch, OCR or model calls.
PDF parsing runs in a bounded child process; pypdf is a declared local dependency.
"""
from __future__ import annotations

import hashlib
import base64
import http.client
import ipaddress
import io
import json
import re
import socket
import ssl
import subprocess
import sys
import time
import zipfile
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

MAX_BYTES = 4 * 1024 * 1024
MAX_TEXT = 1_000_000
MAX_PARAGRAPHS = 5000
MAX_PAGES = 1000


def _paragraphs(pages):
    rows, size = [], 0
    for page, text in pages:
        for part in re.split(r'\n\s*\n', text.replace('\r\n', '\n').replace('\r', '\n')):
            part = part.strip()
            if not part: continue
            # A paragraph is bounded for citation display and retrieval too.
            for start in range(0, len(part), 8000):
                chunk = part[start:start + 8000]
                size += len(chunk)
                if size > MAX_TEXT or len(rows) >= MAX_PARAGRAPHS:
                    raise ValueError('RESEARCH_EXTRACT_LIMIT')
                rows.append({'paragraph': len(rows) + 1, 'page': page, 'text': chunk})
    return rows


def _docx(content):
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            members = archive.infolist()
            if len(members) > 1000: raise ValueError('RESEARCH_ARCHIVE_LIMIT')
            total = 0
            names = set()
            for member in members:
                path = PurePosixPath(member.filename)
                if (member.filename in names or member.filename.startswith(('/', '\\')) or '\\' in member.filename
                    or '..' in path.parts or ':' in member.filename or (member.external_attr >> 16) & 0o170000 == 0o120000):
                    raise ValueError('RESEARCH_ARCHIVE_PATH')
                names.add(member.filename)
                total += member.file_size
                if total > 12 * 1024 * 1024 or member.file_size > 8 * 1024 * 1024 or member.flag_bits & 1:
                    raise ValueError('RESEARCH_ARCHIVE_LIMIT')
                if member.file_size > max(4096, member.compress_size * 100): raise ValueError('RESEARCH_ARCHIVE_RATIO')
                if member.filename.endswith(('.xml', '.rels')):
                    xml = archive.read(member)
                    # DTD/entity declarations and relationships never authorize IO.
                    if b'\x00' in xml or re.search(br'<!\s*(?:DOCTYPE|ENTITY)', xml, re.I): raise ValueError('RESEARCH_XML_ENTITY')
            if '[Content_Types].xml' not in names or 'word/document.xml' not in names:
                raise ValueError('RESEARCH_INVALID_DOCX')
            xml = archive.read('word/document.xml')
            root = ElementTree.fromstring(xml)
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            paragraphs = []
            for paragraph in root.iter(ns + 'p'):
                text = ''.join((node.text or '') if node.tag == ns + 't' else '\t' if node.tag == ns + 'tab' else '\n' if node.tag == ns + 'br' else '' for node in paragraph.iter())
                if text.strip(): paragraphs.append(text)
            return _paragraphs([(None, '\n\n'.join(paragraphs))])
    except (zipfile.BadZipFile, KeyError, ElementTree.ParseError, RuntimeError) as exc:
        raise ValueError('RESEARCH_INVALID_DOCX') from exc


_PDF_SCRIPT = r'''
import io,json,sys
try:
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(384*1024*1024,384*1024*1024))
 resource.setrlimit(resource.RLIMIT_CPU,(5,5))
except ImportError: pass
from pypdf import PdfReader
reader=PdfReader(io.BytesIO(sys.stdin.buffer.read(4194305)),strict=True)
if reader.is_encrypted: raise ValueError('encrypted PDF')
if len(reader.pages)>1000: raise ValueError('page limit')
result=[]; total=0
for index,page in enumerate(reader.pages):
 content=page.get_contents()
 if content is not None and len(content.get_data())>8000000: raise ValueError('page stream limit')
 text=page.extract_text() or ''; total+=len(text)
 if total>1000000: raise ValueError('text limit')
 result.append([index+1,text])
print(json.dumps(result,ensure_ascii=True))
'''


def _pdf(content):
    import importlib.util
    if importlib.util.find_spec('pypdf') is None:
        raise ValueError('RESEARCH_PDF_PARSER_NOT_CONFIGURED')
    try:
        result = subprocess.run([sys.executable, '-I', '-c', _PDF_SCRIPT], input=content,
                                capture_output=True, timeout=8, check=False)
        if result.returncode != 0 or len(result.stdout) > 8_000_000:
            raise ValueError('RESEARCH_PDF_PARSE_FAILED')
        pages = json.loads(result.stdout)
        return _paragraphs(pages), [page for page, text in pages if not text.strip()]
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
        raise ValueError('RESEARCH_PDF_PARSE_FAILED') from exc


def extract_document(filename: str, content: bytes):
    if (not filename or len(filename) > 240 or '/' in filename or '\\' in filename
        or any(ord(c) < 32 for c in filename) or filename in {'.', '..'}):
        raise ValueError('RESEARCH_FILENAME_INVALID')
    if not content or len(content) > MAX_BYTES: raise ValueError('RESEARCH_FILE_LIMIT')
    suffix = PurePosixPath(filename).suffix.lower()
    warnings, unread_pages = [], []
    if suffix in {'.txt', '.md'}:
        try: text = content.decode('utf-8-sig')
        except UnicodeDecodeError as exc: raise ValueError('RESEARCH_UTF8_REQUIRED') from exc
        if '\x00' in text: raise ValueError('RESEARCH_TEXT_NUL')
        rows, fmt, status = _paragraphs([(None, text)]), suffix[1:].upper(), 'TEXT_EXTRACTED'
    elif suffix == '.docx':
        rows, fmt, status = _docx(content), 'DOCX', 'TEXT_EXTRACTED'
        warnings.append('DOCX pagination depends on layout; citations use paragraph numbers.')
    elif suffix == '.pdf':
        if not content.startswith(b'%PDF-'): raise ValueError('RESEARCH_INVALID_PDF')
        rows, unread_pages = _pdf(content)
        fmt, status = 'PDF', 'TEXT_EXTRACTED' if rows else 'OCR_NOT_CONFIGURED'
        if unread_pages: warnings.append(f'{len(unread_pages)} pages contain no extracted text; OCR is not configured. Images are not understood.')
    elif suffix in {'.png', '.jpg', '.jpeg', '.webp'}:
        # Pillow is already used by the host's image processing dependency.
        try:
            from PIL import Image
            with Image.open(io.BytesIO(content)) as image:
                if image.format not in {'PNG', 'JPEG', 'WEBP'} or image.width * image.height > 40_000_000:
                    raise ValueError('RESEARCH_IMAGE_LIMIT')
                image.verify()
        except Exception as exc:
            raise ValueError('RESEARCH_INVALID_IMAGE') from exc
        rows, fmt, status = [], 'IMAGE', 'OCR_NOT_CONFIGURED'
        unread_pages = [1]
        warnings.append('Image preserved as a source. OCR and visual understanding are not configured.')
    else: raise ValueError('RESEARCH_UNSUPPORTED_FILE_TYPE')
    if not rows and status == 'TEXT_EXTRACTED': status = 'NO_TEXT'
    return {'format': fmt, 'paragraphs': rows, 'extraction_status': status, 'warnings': warnings,
            'content_sha256': hashlib.sha256(content).hexdigest(), 'unread_pages': unread_pages}


class _PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.hidden = [], 0
    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'template', 'iframe', 'svg', 'head', 'object'}: self.hidden += 1
        if not self.hidden and tag in {'p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'article', 'section'}: self.parts.append('\n\n')
    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'template', 'iframe', 'svg', 'head', 'object'}: self.hidden = max(0, self.hidden - 1)
        if not self.hidden and tag in {'p', 'div', 'li', 'h1', 'h2', 'h3', 'article', 'section'}: self.parts.append('\n\n')
    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def _public_target(url):
    parsed = urlsplit(url)
    if (parsed.scheme not in {'https', 'http'} or not parsed.hostname or parsed.username or parsed.password
        or parsed.fragment or len(url) > 2000 or any(ord(c) <= 32 for c in url)):
        raise ValueError('RESEARCH_WEB_URL_INVALID')
    try: port = parsed.port or (443 if parsed.scheme == 'https' else 80)
    except ValueError as exc: raise ValueError('RESEARCH_WEB_URL_INVALID') from exc
    if port != (443 if parsed.scheme == 'https' else 80): raise ValueError('RESEARCH_WEB_PORT_BLOCKED')
    try:
        addresses = sorted({entry[4][0] for entry in socket.getaddrinfo(parsed.hostname, port, type=socket.SOCK_STREAM)})
    except OSError as exc: raise ValueError('RESEARCH_WEB_DNS_FAILED') from exc
    if not addresses or any(not ipaddress.ip_address(address).is_global for address in addresses):
        raise ValueError('RESEARCH_WEB_PRIVATE_NETWORK_BLOCKED')
    return parsed, port, addresses[0]


def _request_public(url, remaining):
    parsed, port, address = _public_target(url)
    # DNS is never resolved again for connection; HTTPS still validates the
    # original hostname and sends SNI. No proxy, auth, cookies or decompression.
    conn = http.client.HTTPSConnection(parsed.hostname, port, timeout=min(5, remaining)) if parsed.scheme == 'https' else http.client.HTTPConnection(parsed.hostname, port, timeout=min(5, remaining))
    sock = socket.create_connection((address, port), timeout=min(5, remaining))
    try:
        if parsed.scheme == 'https': sock = ssl.create_default_context().wrap_socket(sock, server_hostname=parsed.hostname)
        conn.sock = sock
        target = parsed.path or '/'
        if parsed.query: target += '?' + parsed.query
        conn.request('GET', target, headers={'User-Agent': 'AI-Novel-Studio-Research/1', 'Accept': 'text/html,text/plain', 'Accept-Encoding': 'identity'})
        response = conn.getresponse()
        headers = dict((key.lower(), value) for key, value in response.getheaders())
        if response.status in {301, 302, 303, 307, 308}: return response.status, headers, b''
        if response.status != 200: raise ValueError('RESEARCH_WEB_ACCESS_FAILED')
        if headers.get('content-encoding', 'identity').lower() != 'identity': raise ValueError('RESEARCH_WEB_ENCODING_BLOCKED')
        if headers.get('content-type', '').split(';')[0].lower() not in {'text/html', 'text/plain'}: raise ValueError('RESEARCH_WEB_CONTENT_TYPE_BLOCKED')
        if 'content-length' in headers and int(headers['content-length']) > MAX_BYTES: raise ValueError('RESEARCH_WEB_SIZE_LIMIT')
        chunks, size, deadline = [], 0, time.monotonic() + remaining
        while True:
            left = deadline - time.monotonic()
            if left <= 0: raise ValueError('RESEARCH_WEB_TIMEOUT')
            sock.settimeout(min(2, left))
            data = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not data: break
            chunks.append(data); size += len(data)
            if size > MAX_BYTES: raise ValueError('RESEARCH_WEB_SIZE_LIMIT')
        return response.status, headers, b''.join(chunks)
    finally:
        conn.close(); sock.close()


def _fetch_webpage(url: str, *, request=None, guard=lambda: None):
    request = request or _request_public
    deadline, current = time.monotonic() + 10, url
    try:
        for redirect in range(4):
            remaining = deadline - time.monotonic()
            if remaining <= 0: raise ValueError('RESEARCH_WEB_TIMEOUT')
            guard()
            status, headers, content = request(current, remaining)
            guard()
            if status in {301, 302, 303, 307, 308}:
                if redirect == 3 or not headers.get('location'): raise ValueError('RESEARCH_WEB_REDIRECT_LIMIT')
                current = urljoin(current, headers['location']); continue
            media = headers.get('content-type', '').split(';')[0].lower()
            if media not in {'text/html', 'text/plain'} or len(content) > MAX_BYTES: raise ValueError('RESEARCH_WEB_CONTENT_TYPE_BLOCKED')
            try: text = content.decode('utf-8-sig')
            except UnicodeDecodeError as exc: raise ValueError('RESEARCH_WEB_UTF8_REQUIRED') from exc
            if media == 'text/html':
                parser = _PlainHTML(); parser.feed(text); text = ''.join(parser.parts)
            rows = _paragraphs([(None, text)])
            return {'format': 'WEB', 'paragraphs': rows, 'extraction_status': 'TEXT_EXTRACTED' if rows else 'NO_TEXT',
                    'warnings': ['Only visible text is retained. Scripts, remote images and embedded media are not loaded.'],
                    'content_sha256': hashlib.sha256(content).hexdigest(), 'final_url': current, 'content_type': media}
    except (OSError, http.client.HTTPException) as exc:
        raise ValueError('RESEARCH_WEB_UNAVAILABLE') from exc
    raise ValueError('RESEARCH_WEB_REDIRECT_LIMIT')


def fetch_webpage(url: str, *, guard=lambda: None):
    """One bounded child per hop; current authority is checked before redirects.

    The overall 10-second deadline includes DNS/TLS; a child receives only one
    explicitly selected public URL, not credentials or source contents.
    """
    def request(current, remaining):
        try:
            result = subprocess.run([sys.executable, __file__, current, str(remaining)],
                                    capture_output=True, timeout=min(12, remaining), check=False)
            if result.returncode != 0 or len(result.stdout) > 8_000_000:
                raise ValueError('RESEARCH_WEB_UNAVAILABLE')
            payload = json.loads(result.stdout)
            if 'error' in payload: raise ValueError(payload['error'])
            return payload['status'], payload['headers'], base64.b64decode(payload['content'], validate=True)
        except subprocess.TimeoutExpired as exc: raise ValueError('RESEARCH_WEB_TIMEOUT') from exc
        except (json.JSONDecodeError, OSError) as exc: raise ValueError('RESEARCH_WEB_UNAVAILABLE') from exc
    return _fetch_webpage(url, request=request, guard=guard)


if __name__ == '__main__':
    try:
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (8, 8))
        except ImportError: pass
        status, headers, content = _request_public(sys.argv[1], float(sys.argv[2]))
        print(json.dumps({'status': status, 'headers': headers, 'content': base64.b64encode(content).decode()}))
    except (ValueError, MemoryError, OSError, http.client.HTTPException):
        print(json.dumps({'error': 'RESEARCH_WEB_UNAVAILABLE'}))
