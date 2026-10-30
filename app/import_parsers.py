"""Dependency-light decoders for binary project imports.

Imported bytes are untrusted: the archive and its XML/PDF content are bounded
before parsing so a crafted manuscript cannot expand without limit. These are
the same limits the newer research-extraction importer already enforces; this
legacy decoder path is kept for the older import formats.
"""
from __future__ import annotations
import base64, binascii, io, re, zipfile
from xml.etree import ElementTree

MAX_DOCX_COMPRESSED_BYTES = 64 * 1024 * 1024
MAX_DOCX_ARCHIVE_MEMBERS = 512
MAX_DOCX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_DOCX_TOTAL_BYTES = 32 * 1024 * 1024
MAX_DOCX_COMPRESSION_RATIO = 100
MAX_PDF_BYTES = 64 * 1024 * 1024
MAX_PDF_PAGES = 1000
MAX_PDF_TEXT_CHARS = 4 * 1024 * 1024
_XML_DECLARATION = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)", re.I)


def decode_base64(value: str) -> bytes:
    try: return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc: raise ValueError("invalid base64 import content") from exc

def _read_word_document_xml(raw: bytes) -> bytes:
    """Read the document part only after bounding the whole archive."""
    if len(raw) > MAX_DOCX_COMPRESSED_BYTES:
        raise ValueError("invalid Word document")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            members = archive.infolist()
            if len(members) > MAX_DOCX_ARCHIVE_MEMBERS:
                raise ValueError("invalid Word document")
            total = 0
            for member in members:
                total += member.file_size
                if (member.file_size > MAX_DOCX_MEMBER_BYTES
                        or total > MAX_DOCX_TOTAL_BYTES
                        or member.flag_bits & 1
                        or member.file_size > max(4096, member.compress_size * MAX_DOCX_COMPRESSION_RATIO)):
                    raise ValueError("invalid Word document")
            xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile, OSError) as exc:
        raise ValueError("invalid Word document") from exc
    if len(xml) > MAX_DOCX_MEMBER_BYTES or b"\x00" in xml or _XML_DECLARATION.search(xml):
        # A WordprocessingML document never needs DTD/entity declarations. The
        # standard parser bounds expansion, but an import never authorizes one.
        raise ValueError("invalid Word document XML")
    return xml

def docx_to_text(raw: bytes) -> str:
    xml = _read_word_document_xml(raw)
    try: root = ElementTree.fromstring(xml)
    except ElementTree.ParseError as exc: raise ValueError("invalid Word document XML") from exc
    paragraphs=[]
    for paragraph in root.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"):
        parts=[]
        for node in paragraph.iter():
            if node.tag.endswith("}t") and node.text: parts.append(node.text)
            elif node.tag.endswith("}tab"): parts.append("\t")
            elif node.tag.endswith("}br"): parts.append("\n")
        text="".join(parts).strip()
        if text: paragraphs.append(text)
    return "\n".join(paragraphs)

def pdf_to_text(raw: bytes) -> str:
    if not raw.startswith(b"%PDF-"): raise ValueError("invalid PDF document")
    if len(raw) > MAX_PDF_BYTES: raise ValueError("invalid PDF document")
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError: PdfReader = None
    if PdfReader is not None:
        try:
            reader = PdfReader(io.BytesIO(raw))
            pages = list(reader.pages)
        except Exception as exc: raise ValueError("unable to extract PDF text") from exc
        if len(pages) > MAX_PDF_PAGES:
            raise ValueError("invalid PDF document")
        parts=[]; total=0
        for page in pages:
            try: text = page.extract_text() or ""
            except Exception as exc: raise ValueError("unable to extract PDF text") from exc
            total += len(text)
            if total > MAX_PDF_TEXT_CHARS: raise ValueError("invalid PDF document")
            parts.append(text)
        return "\n".join(parts).strip()
    chunks=re.findall(rb"\(([^()]*)\)\s*Tj",raw[:MAX_PDF_BYTES]); text="\n".join(x.decode("latin-1",errors="replace") for x in chunks).strip()
    if len(text) > MAX_PDF_TEXT_CHARS: raise ValueError("invalid PDF document")
    if not text: raise ValueError("PDF text extraction requires the optional pypdf dependency")
    return text
