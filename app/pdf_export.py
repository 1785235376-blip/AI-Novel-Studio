"""Deterministic, local-first PDF manuscript export.

The export queue keeps binary exporters behind a small ``bytes`` boundary.  This
module is the PDF implementation for that boundary.  It deliberately has no
provider or network dependency: all text is rendered locally with ReportLab and
the font is selected from an application-provided font, a configured path, or a
Windows CJK font.  When no embeddable font is available, ReportLab's standard
``STSong-Light`` CID font is used as a compatibility fallback so a desktop
installation can still produce a readable PDF; callers can opt into strict
embedded-font mode for release validation.

The application-provided font path is intentionally optional.  A release build
may place an OFL-licensed Noto Sans SC TTF under ``assets/fonts`` (or set
``AI_NOVEL_STUDIO_PDF_FONT``) without changing this API.  The generated PDF
never records the source path, environment variables, or credentials.
"""

from __future__ import annotations

import html
import io
import os
import sys
import threading
from pathlib import Path
from typing import Iterable, Mapping


class PDFExportError(RuntimeError):
    """A safe, user-facing PDF export failure.

    ``code`` is stable for the API/error UI while ``details`` contains only
    non-sensitive diagnostics (never a local path or provider credential).
    """

    def __init__(self, code: str, message: str, *, details: Mapping[str, object] | None = None):
        self.code = str(code)
        self.details = dict(details or {})
        super().__init__(str(message))


_FONT_LOCK = threading.RLock()
_REGISTERED_FONTS: dict[str, tuple[str, bool]] = {}


def _clean_text(value: object) -> str:
    """Remove XML-invalid controls while preserving normal manuscript text."""

    text = str(value or "")
    return "".join(
        char
        for char in text
        if char in "\t\n\r" or (ord(char) >= 0x20 and not 0xD800 <= ord(char) <= 0xDFFF)
    )


def _font_candidates() -> list[Path]:
    """Return deterministic font candidates, strongest choice first."""

    candidates: list[Path] = []
    configured = os.environ.get("AI_NOVEL_STUDIO_PDF_FONT", "").strip()
    if configured:
        candidates.append(Path(configured))

    module_root = Path(__file__).resolve().parent
    project_root = module_root.parent
    # A release package can ship an OFL font at any of these stable locations.
    for relative in (
        "assets/fonts/NotoSansSC-Regular.ttf",
        "assets/fonts/NotoSansSC[wght].ttf",
        "app/assets/fonts/NotoSansSC-Regular.ttf",
        "Runtime/Fonts/NotoSansSC-Regular.ttf",
        "Fonts/NotoSansSC-Regular.ttf",
    ):
        candidates.append(project_root / relative)

    # Windows ships one of these fonts on common Chinese and multilingual
    # installations.  They are used only when an application font is absent;
    # a release build should prefer the bundled OFL font above.
    if sys.platform == "win32":
        windows_fonts = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
        for name in ("msyh.ttf", "msyh.ttc", "simsun.ttc", "simhei.ttf", "Deng.ttf"):
            candidates.append(windows_fonts / name)

    # Keep order while removing duplicates and non-files at call time.
    seen: set[str] = set()
    result: list[Path] = []
    for path in candidates:
        key = os.path.normcase(str(path))
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def _register_cjk_font() -> tuple[str, bool]:
    """Register an embeddable CJK font, or return the CID fallback.

    The function is lazy so importing the backend remains possible in minimal
    environments.  ReportLab's ``TTFont`` embeds the used glyph subset and
    creates a ToUnicode map, preserving Chinese search/copy behavior.
    """

    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError as exc:  # pragma: no cover - exercised in slim installs
        raise PDFExportError(
            "PDF_RENDERER_UNAVAILABLE",
            "PDF 导出组件未安装，请安装应用的 PDF 运行依赖",
            details={"dependency": "reportlab"},
        ) from exc

    with _FONT_LOCK:
        for index, path in enumerate(_font_candidates()):
            if not path.is_file():
                continue
            # Do not expose the path in the PDF or error payload.  The index
            # and suffix are sufficient to keep a stable in-process name.
            key = os.path.normcase(str(path))
            cached = _REGISTERED_FONTS.get(key)
            if cached:
                return cached
            name = f"ANS_CJK_{index}"
            try:
                # TTC files use the first face (regular).  ``TTFont`` supports
                # both TTF and TTC and embeds the selected glyph subset.
                pdfmetrics.registerFont(TTFont(name, str(path), subfontIndex=0))
                _REGISTERED_FONTS[key] = (name, True)
                return name, True
            except Exception:
                # A malformed/unsupported optional font must not turn into a
                # 500 with implementation details.  Try the next candidate.
                continue

        try:
            # Standard PDF CJK font.  It is not embedded, but is understood by
            # Acrobat, Edge, and the Windows PDF stack and avoids tofu boxes on
            # machines where an optional bundled font is not yet present.
            pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
        except Exception as exc:  # pragma: no cover - ReportLab invariant
            raise PDFExportError(
                "PDF_FONT_UNAVAILABLE",
                "没有可用的中文字体，无法生成 PDF",
                details={"font_mode": "none"},
            ) from exc
        _REGISTERED_FONTS["__cid_fallback__"] = ("STSong-Light", False)
        return "STSong-Light", False


def pdf_font_status() -> dict[str, object]:
    """Return non-sensitive runtime capability information for diagnostics."""

    try:
        name, embedded = _register_cjk_font()
    except PDFExportError as exc:
        # The packaged Python runtime intentionally keeps optional document
        # libraries small.  The stdlib CID writer below remains available in
        # that mode, so diagnostics distinguish renderer absence from a total
        # PDF capability failure.
        if exc.code == "PDF_RENDERER_UNAVAILABLE":
            return {
                "available": True,
                "embedded": False,
                "font_family": "STSong-Light",
                "font_mode": "cid-fallback",
                "renderer": "stdlib-cid",
            }
        return {"available": False, "embedded": False, "code": exc.code}
    return {
        "available": True,
        "embedded": bool(embedded),
        "font_family": "application-cjk" if embedded else "STSong-Light",
        "font_mode": "embedded" if embedded else "cid-fallback",
        # The actual registered name is an implementation detail and is not
        # returned to the API/UI.
    }


def _pdf_hex_text(value: object) -> bytes:
    """Encode text for the PDF ``UniGB-UCS2-H`` CMap."""

    text = _clean_text(value).replace("\r\n", "\n").replace("\r", "\n")
    # The built-in Adobe GB CMap is UCS-2.  Replace astral code points with a
    # visible placeholder instead of writing an invalid odd-length string.
    text = "".join(char if ord(char) <= 0xFFFF else "□" for char in text)
    return text.encode("utf-16-be", "replace").hex().encode("ascii")


def _fallback_line_width(text: str, font_size: float) -> float:
    """Approximate mixed CJK/Latin width for the dependency-free writer."""

    width = 0.0
    for char in text:
        if char.isspace():
            width += font_size * 0.34
        elif ord(char) >= 0x3000:
            width += font_size
        elif ord(char) > 0xFF:
            width += font_size
        else:
            width += font_size * 0.55
    return width


def _fallback_wrap(text: str, max_width: float, font_size: float) -> list[str]:
    lines: list[str] = []
    for paragraph in _clean_text(text).replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for char in paragraph:
            if current and _fallback_line_width(current + char, font_size) > max_width:
                lines.append(current)
                current = char
            else:
                current += char
        if current:
            lines.append(current)
    return lines


def _build_minimal_pdf(objects: list[bytes], root_number: int, info_number: int) -> bytes:
    """Build a valid PDF-1.4 file from already encoded indirect objects."""

    # Start after the header; constructing BytesIO with initial bytes leaves
    # the cursor at offset zero and would overwrite the header on first write.
    output = io.BytesIO()
    output.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, body in enumerate(objects, 1):
        offsets.append(output.tell())
        output.write(f"{number} 0 obj\n".encode("ascii"))
        output.write(body)
        if not body.endswith(b"\n"):
            output.write(b"\n")
        output.write(b"endobj\n")
    xref = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root {root_number} 0 R /Info {info_number} 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n".encode("ascii")
    )
    return output.getvalue()


def _novel_to_pdf_cid_fallback(
    title: object,
    chapters: Iterable[Mapping[str, object]] | None,
    *,
    version: object = "",
    require_embedded_font: bool = False,
    progress_callback=None,
) -> bytes:
    """Dependency-free PDF writer for the packaged slim Python runtime.

    ``STSong-Light`` is a standard PDF CID font and therefore does not require
    shipping a proprietary system font.  A release build that promises fully
    embedded CJK glyphs should supply the OFL TTF and enable strict mode.
    """

    if require_embedded_font:
        raise PDFExportError(
            "PDF_CJK_FONT_NOT_EMBEDDED",
            "正式 PDF 导出需要可分发的嵌入式中文字体",
            details={"font_mode": "cid-fallback", "hint": "请随应用提供 OFL 授权 CJK TTF"},
        )
    clean_title = _clean_text(title).strip() or "AI Novel Studio"
    clean_version = _clean_text(version).strip()
    normalized = _normalise_chapters(chapters)
    page_width, page_height = 595.28, 841.89  # A4 points
    left, right, top, bottom = 62.36, 62.36, 62.36, 56.69
    content_width = page_width - left - right
    body_size, body_leading = 11.5, 20.0
    pages: list[bytes] = []

    def make_page(lines: list[tuple[str, float, float, str]]) -> bytes:
        stream = io.BytesIO()
        stream.write(b"q\n")
        # A light footer rule and page number are drawn by the caller's lines.
        for text, size, y, align in lines:
            encoded = _pdf_hex_text(text)
            width = _fallback_line_width(text, size)
            x = left
            if align == "center":
                x = (page_width - width) / 2
            stream.write(f"BT /F1 {size:g} Tf {x:g} {y:g} Td <".encode("ascii"))
            stream.write(encoded)
            stream.write(b"> Tj ET\n")
        stream.write(b"Q\n")
        raw = stream.getvalue()
        return f"<< /Length {len(raw)} >>\nstream\n".encode("ascii") + raw + b"endstream\n"

    # Cover page.
    cover_lines = [
        (clean_title, 25, 565, "center"),
        ("AI Novel Studio · 本地导出", 10, 505, "center"),
        ((f"版本 {clean_version}" if clean_version else f"共 {len(normalized)} 章"), 10, 470, "center"),
        (f"共 {len(normalized)} 章", 10, 415, "center"),
    ]
    pages.append(make_page(cover_lines))

    for index, chapter in enumerate(normalized, 1):
        lines: list[tuple[str, float, float, str]] = []
        y = page_height - top
        lines.append((clean_title[:48], 8.5, y, "left"))
        y -= 32
        chapter_title = chapter["title"] or f"第{index}章"
        lines.append((chapter_title, 17, y, "left"))
        y -= 38
        body_lines = _fallback_wrap(chapter["content"] or "（本章暂无正文）", content_width, body_size)
        for line in body_lines:
            if y < bottom + 22:
                # Finish the current page and continue this chapter on the
                # next; all page objects share the same CID font resource.
                pages.append(make_page(lines))
                lines = [(clean_title[:48], 8.5, page_height - top, "left")]
                y = page_height - top - 32
            if line:
                # The body is intentionally left-aligned with a small first
                # line indent for prose readability.
                lines.append((line, body_size, y, "left"))
            y -= body_leading if line else body_leading * 0.55
        lines.append((str(len(pages) + 1), 8.5, bottom - 20, "center"))
        pages.append(make_page(lines))
        if progress_callback:
            progress_callback(40 + int(index / max(1, len(normalized)) * 45), f"排版第 {index}/{len(normalized)} 章")
    if not normalized:
        pages.append(make_page([("当前项目没有可导出的章节。", body_size, page_height / 2, "center")]))

    # Object graph: catalog -> pages -> page objects -> shared Type0 font.
    objects: list[bytes] = []
    catalog_number = 1
    pages_number = 2
    font_number = 3
    info_number = 4
    first_page_number = 5
    page_numbers = [first_page_number + i * 2 for i in range(len(pages))]
    objects.append(f"<< /Type /Catalog /Pages {pages_number} 0 R >>\n".encode("ascii"))
    kids = " ".join(f"{number} 0 R" for number in page_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_numbers)} >>\n".encode("ascii"))
    objects.append(
        b"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light "
        b"/Encoding /UniGB-UCS2-H /DescendantFonts [6 0 R] >>\n"
    )
    objects.append(
        b"<< /Title <" + _pdf_hex_text(clean_title) + b"> /Author <0041 0049 0020 004E 006F 0076 0065 006C 0020 0053 0074 0075 0064 0069 006F> /Producer (AI Novel Studio) >>\n"
    )
    # Reserve each page and its content stream.  The descendant font object is
    # inserted after the page objects below and referenced by fixed number 6.
    for number, stream in zip(page_numbers, pages):
        content_number = number + 1
        objects.append(
            f"<< /Type /Page /Parent {pages_number} 0 R /MediaBox [0 0 {page_width:g} {page_height:g}] /Resources << /Font << /F1 {font_number} 0 R >> >> /Contents {content_number} 0 R >>\n".encode("ascii")
        )
        objects.append(stream)
    # The fixed descendant object is appended last; update the Type0 object to
    # point at its actual number if there are multiple pages.
    descendant_number = len(objects) + 1
    objects[font_number - 1] = (
        f"<< /Type /Font /Subtype /Type0 /BaseFont /STSong-Light /Encoding /UniGB-UCS2-H /DescendantFonts [{descendant_number} 0 R] >>\n".encode("ascii")
    )
    objects.append(
        b"<< /Type /Font /Subtype /CIDFontType0 /BaseFont /STSong-Light "
        b"/CIDSystemInfo << /Registry (Adobe) /Ordering (GB1) /Supplement 4 >> /DW 1000 >>\n"
    )
    if progress_callback:
        progress_callback(92, "PDF 文件已生成")
    return _build_minimal_pdf(objects, catalog_number, info_number)


def _paragraph_markup(text: object) -> str:
    """Escape manuscript text for ReportLab's small XML-like markup parser."""

    clean = _clean_text(text).replace("\r\n", "\n").replace("\r", "\n")
    # Paragraph does not treat literal newlines as line breaks consistently;
    # explicit ``br`` tags preserve intentional paragraph line boundaries.
    return "<br/>".join(html.escape(line, quote=False) for line in clean.split("\n"))


def _normalise_chapters(chapters: Iterable[Mapping[str, object]] | None) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in chapters or []:
        if not isinstance(item, Mapping):
            continue
        title = _clean_text(item.get("title", "")).strip()
        content = _clean_text(item.get("content", ""))
        result.append({"title": title, "content": content})
    return result


def novel_to_pdf(
    title: object,
    chapters: Iterable[Mapping[str, object]] | None,
    *,
    version: object = "",
    require_embedded_font: bool | None = None,
    progress_callback=None,
) -> bytes:
    """Render a manuscript to a polished A4 PDF in memory.

    ``require_embedded_font`` defaults to the environment switch
    ``AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT``.  Release validation can set
    it to ``1``; normal desktop development keeps the CID fallback available
    for older Windows profiles.  No AI provider is contacted.
    """

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfgen import canvas as canvas_module
        from reportlab.platypus import (
            BaseDocTemplate,
            Frame,
            PageTemplate,
            PageBreak,
            Paragraph,
            Spacer,
        )
    except ImportError:
        strict = require_embedded_font
        if strict is None:
            strict = os.environ.get("AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT", "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        return _novel_to_pdf_cid_fallback(
            title,
            chapters,
            version=version,
            require_embedded_font=bool(strict),
            progress_callback=progress_callback,
        )

    font_name, embedded = _register_cjk_font()
    if require_embedded_font is None:
        require_embedded_font = os.environ.get("AI_NOVEL_STUDIO_PDF_REQUIRE_EMBEDDED_FONT", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    if require_embedded_font and not embedded:
        raise PDFExportError(
            "PDF_CJK_FONT_NOT_EMBEDDED",
            "正式 PDF 导出需要可分发的嵌入式中文字体",
            details={"font_mode": "cid-fallback", "hint": "请随应用提供 OFL 授权 CJK TTF"},
        )

    clean_title = _clean_text(title).strip() or "AI Novel Studio"
    clean_version = _clean_text(version).strip()
    normalized = _normalise_chapters(chapters)

    if progress_callback:
        progress_callback(35, "准备 PDF 排版")

    page_width, page_height = A4
    left = right = 22 * mm
    top = 22 * mm
    bottom = 20 * mm
    header_height = 9 * mm
    footer_height = 8 * mm

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ANS_PDF_Title",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=25,
        leading=34,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#172033"),
        spaceAfter=11 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ANS_PDF_Subtitle",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=10,
        leading=16,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#667085"),
        spaceAfter=8 * mm,
    )
    chapter_style = ParagraphStyle(
        "ANS_PDF_Chapter",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=17,
        leading=25,
        alignment=TA_LEFT,
        textColor=colors.HexColor("#172033"),
        spaceBefore=2 * mm,
        spaceAfter=5 * mm,
        keepWithNext=True,
    )
    body_style = ParagraphStyle(
        "ANS_PDF_Body",
        parent=styles["BodyText"],
        fontName=font_name,
        fontSize=11.5,
        leading=20,
        alignment=TA_LEFT,
        firstLineIndent=23,
        textColor=colors.HexColor("#263248"),
        spaceAfter=3.2 * mm,
        splitLongWords=True,
    )
    empty_style = ParagraphStyle(
        "ANS_PDF_Empty",
        parent=body_style,
        alignment=TA_CENTER,
        firstLineIndent=0,
        textColor=colors.HexColor("#667085"),
    )

    # ``BaseDocTemplate`` gives us stable header/footer geometry while keeping
    # paragraph splitting and CJK line wrapping in ReportLab's tested engine.
    buffer = __import__("io").BytesIO()

    class _Document(BaseDocTemplate):
        def __init__(self, stream):
            super().__init__(
                stream,
                pagesize=A4,
                leftMargin=left,
                rightMargin=right,
                topMargin=top + header_height,
                bottomMargin=bottom + footer_height,
                title=clean_title,
                author="AI Novel Studio",
                subject="Novel manuscript export",
                pageCompression=1,
            )
            frame = Frame(
                left,
                bottom + footer_height,
                page_width - left - right,
                page_height - top - bottom - header_height - footer_height,
                id="manuscript",
                leftPadding=0,
                rightPadding=0,
                topPadding=0,
                bottomPadding=0,
            )
            self.addPageTemplates([PageTemplate(id="manuscript", frames=[frame], onPage=self._decorations)])

        def _decorations(self, page_canvas: canvas_module.Canvas, document):
            page = page_canvas.getPageNumber()
            page_canvas.saveState()
            if page > 1:
                page_canvas.setStrokeColor(colors.HexColor("#E6EAF0"))
                page_canvas.setLineWidth(0.5)
                page_canvas.line(left, page_height - top + 2 * mm, page_width - right, page_height - top + 2 * mm)
                page_canvas.setFont(font_name, 8.5)
                page_canvas.setFillColor(colors.HexColor("#667085"))
                page_canvas.drawString(left, page_height - top + 4 * mm, clean_title[:48])
            page_canvas.setStrokeColor(colors.HexColor("#E6EAF0"))
            page_canvas.setLineWidth(0.5)
            page_canvas.line(left, bottom - 1.5 * mm, page_width - right, bottom - 1.5 * mm)
            page_canvas.setFont(font_name, 8.5)
            page_canvas.setFillColor(colors.HexColor("#667085"))
            page_canvas.drawCentredString(page_width / 2, bottom - 6 * mm, f"{page}")
            page_canvas.restoreState()

    document = _Document(buffer)
    story = [Spacer(1, 28 * mm), Paragraph(_paragraph_markup(clean_title), title_style)]
    subtitle = "AI Novel Studio · 本地导出"
    if clean_version:
        subtitle += f" · 版本 {html.escape(clean_version, quote=False)}"
    story.append(Paragraph(subtitle, subtitle_style))
    story.append(Spacer(1, 24 * mm))
    story.append(Paragraph(f"共 {len(normalized)} 章", subtitle_style))
    story.append(PageBreak())

    if not normalized:
        story.append(Paragraph("当前项目没有可导出的章节。", empty_style))
    else:
        for index, chapter in enumerate(normalized, 1):
            chapter_title = chapter["title"] or f"第{index}章"
            story.append(Paragraph(_paragraph_markup(chapter_title), chapter_style))
            content = chapter["content"]
            lines = content.replace("\r\n", "\n").replace("\r", "\n").split("\n")
            if not any(line.strip() for line in lines):
                story.append(Paragraph("（本章暂无正文）", empty_style))
            else:
                for line in lines:
                    if line.strip():
                        story.append(Paragraph(_paragraph_markup(line), body_style))
                    else:
                        story.append(Spacer(1, 2.5 * mm))
            if index < len(normalized):
                story.append(PageBreak())
            if progress_callback:
                progress_callback(40 + int(index / max(1, len(normalized)) * 45), f"排版第 {index}/{len(normalized)} 章")

    try:
        document.build(story)
    except PDFExportError:
        raise
    except Exception as exc:
        # Do not expose ReportLab internals or any manuscript fragment in the
        # persisted queue error.  The stable code is enough for the UI.
        raise PDFExportError(
            "PDF_RENDER_FAILED",
            "PDF 排版失败，请检查章节内容后重试",
            details={"font_mode": "embedded" if embedded else "cid-fallback"},
        ) from exc

    payload = buffer.getvalue()
    if not payload.startswith(b"%PDF-") or b"%%EOF" not in payload[-64:]:
        raise PDFExportError(
            "PDF_ARTIFACT_INVALID",
            "PDF 导出结果无效，请重试",
            details={"font_mode": "embedded" if embedded else "cid-fallback"},
        )
    if progress_callback:
        progress_callback(92, "PDF 文件已生成")
    return payload
