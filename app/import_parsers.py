"""Dependency-light decoders for binary project imports."""
from __future__ import annotations
import base64, binascii, io, re, zipfile
from xml.etree import ElementTree

def decode_base64(value: str) -> bytes:
    try: return base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc: raise ValueError("invalid base64 import content") from exc

def docx_to_text(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive: xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile, OSError) as exc: raise ValueError("invalid Word document") from exc
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
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError: PdfReader = None
    if PdfReader is not None:
        try: return "\n".join((page.extract_text() or "") for page in PdfReader(io.BytesIO(raw)).pages).strip()
        except Exception as exc: raise ValueError("unable to extract PDF text") from exc
    chunks=re.findall(rb"\(([^()]*)\)\s*Tj",raw); text="\n".join(x.decode("latin-1",errors="replace") for x in chunks).strip()
    if not text: raise ValueError("PDF text extraction requires the optional pypdf dependency")
    return text
