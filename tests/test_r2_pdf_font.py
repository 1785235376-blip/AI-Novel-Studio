import importlib.util
from pathlib import Path
import os
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_pdf_font", ROOT / "scripts" / "prepare_pdf_font.py")
font = importlib.util.module_from_spec(spec)
spec.loader.exec_module(font)


def test_font_manifest_is_pinned_and_license_is_complete():
    import hashlib
    assert len(font.REVISION) == 40
    assert all(font.REVISION in url for url, _ in font.FILES.values())
    license = (ROOT / "assets/fonts/OFL.txt").read_bytes()
    assert hashlib.sha256(license).hexdigest() == font.FILES["OFL.txt"][1]
    assert b"SIL OPEN FONT LICENSE Version 1.1" in license


def test_invalid_download_does_not_create_font(monkeypatch, tmp_path):
    import io
    monkeypatch.setattr(font, "urlopen", lambda *args, **kwargs: io.BytesIO(b"bad response"))
    with pytest.raises(ValueError, match="integrity"):
        font.prepare(tmp_path)
    assert not (tmp_path / "NotoSansSC-Regular.ttf").exists()


def test_existing_modified_font_is_not_overwritten(tmp_path):
    p = tmp_path / "NotoSansSC-Variable.ttf"
    p.write_bytes(b"user file")
    with pytest.raises(ValueError, match="integrity"):
        font.prepare(tmp_path)
    assert p.read_bytes() == b"user file"


def test_pinned_cjk_font_embeds_in_real_pdf_when_prepared(monkeypatch):
    path = os.environ.get("R2_TEST_FONT_FILE")
    if not path:
        pytest.skip("NOT_RUN: pinned build font not prepared; CI font gate supplies it")
    from app.pdf_export import novel_to_pdf, pdf_font_status
    font.verify_font(Path(path).read_bytes())
    monkeypatch.setenv("AI_NOVEL_STUDIO_PDF_FONT", path)
    assert pdf_font_status()["embedded"] is True
    output = novel_to_pdf("中文字体验收", [{"title": "第一章", "content": "春江潮水连海平。测试中文与 English 123。"}], require_embedded_font=True)
    assert output.startswith(b"%PDF-") and b"/FontFile2" in output and b"/ToUnicode" in output
