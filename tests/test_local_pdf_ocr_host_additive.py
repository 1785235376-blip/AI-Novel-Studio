"""Explicit PDF host setup does not infer or install tools."""
from hashlib import sha256
from pathlib import Path
import pytest
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from app.experimental.native_ocr_broker import candidates
from test_local_ocr_host_bootstrap_additive import configure, FIELDS


def test_explicit_pdf_host_adds_distinct_route_without_execution(tmp_path, monkeypatch):
    configure(monkeypatch)
    tool=Path('/usr/bin/pdftoppm')
    if not tool.is_file(): pytest.skip('Installed Poppler fixture unavailable')
    monkeypatch.setenv('LOCAL_PDF_RENDER_EXECUTABLE',str(tool))
    monkeypatch.setenv('LOCAL_PDF_RENDER_EXECUTABLE_SHA256',sha256(tool.read_bytes()).hexdigest())
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process,'run_alignment_process',lambda *a,**k:pytest.fail('startup execution'))
    runtime=Runtime(StableIdentityStore(tmp_path/'host.json'))
    rows=candidates(runtime)
    assert {row['provider_id'] for row in rows}=={'local-tesseract-ocr','local-pdf-tesseract-ocr'}
    pdf=next(row for row in rows if row['provider_id']=='local-pdf-tesseract-ocr')
    assert pdf['identity']['source_kind']=='PDF' and pdf['synthetic'] is False


def test_incomplete_pdf_host_never_silently_registers(tmp_path,monkeypatch):
    for key in FIELDS:monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv('LOCAL_PDF_RENDER_EXECUTABLE','/usr/bin/pdftoppm')
    monkeypatch.delenv('LOCAL_PDF_RENDER_EXECUTABLE_SHA256',raising=False)
    with pytest.raises(ValueError,match='COMPLETE_HOST_CONFIGURATION_REQUIRED'):
        Runtime(StableIdentityStore(tmp_path/'incomplete.json'))
