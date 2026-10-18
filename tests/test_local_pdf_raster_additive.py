"""Actual pinned Poppler plus original OCR seam; not Research PDF admission."""
from hashlib import sha256
from pathlib import Path
from threading import Event
import pytest
from app.local_pdf_raster import LocalPDFPageRasterizer
from app.model_runtime import ModelRuntimeError
from app.vision_ocr_runtime import VisionOCRRequest
from test_local_tesseract_ocr_additive import native, install
from test_vision_ocr_runtime_additive import rig

PDF = Path(__file__).parent / 'fixtures/native_pdf_page_smoke.pdf'

@pytest.fixture
def raster():
    binary = Path('/usr/bin/pdftoppm')
    if not binary.is_file(): pytest.skip('Installed pinned Poppler fixture is unavailable')
    return LocalPDFPageRasterizer(executable=binary, executable_sha256=sha256(binary.read_bytes()).hexdigest())


def render(raster, **changes):
    data = PDF.read_bytes()
    values = {'source_digest': sha256(data).hexdigest(), 'page': 2,
        'expected_route_digest': raster.route_snapshot()['admission_digest'], 'guard': lambda: None}
    values.update(changes)
    return raster.render(data, **values)


def test_real_image_only_pdf_pages_are_distinct_bounded_pngs(raster, tmp_path):
    before = PDF.read_bytes()
    first, second = render(raster, page=1), render(raster, page=2)
    assert first.image_digest != second.image_digest
    assert second.source_digest == sha256(before).hexdigest() and second.page == 2
    assert 0 < second.width <= 2048 and 0 < second.height <= 2048
    assert second.content.startswith(b'\x89PNG\r\n\x1a\n') and len(second.content) <= 4 * 1024 * 1024
    assert second.image_digest == sha256(second.content).hexdigest()
    assert PDF.read_bytes() == before
    (tmp_path / 'page-2.png').write_bytes(second.content)


def test_real_pdf_page_can_feed_original_pinned_ocr_without_new_job_owner(rig, native, raster):
    runtime, _ = rig; install(runtime, native); page = render(raster)
    request = VisionOCRRequest(provider_id='native-ocr', model_id='eng', content=page.content, media_type='image/png',
        language='eng', source_digest=page.image_digest,
        route_digest=runtime.vision_ocr_node.binding('native-ocr', 'eng')['route_digest'], request_id='pdf-page-smoke', dispatch_guard=lambda: None)
    result = runtime.vision_ocr_node.execute(request)
    assert 'PAGE 2' in result.text and 'EVIDENCE 123' in result.text
    assert result.receipt['review_required'] is True and result.receipt['model_quality'] == 'NOT_RUN'
    assert result.receipt['automatic_canon'] is False


def test_constructing_and_pin_inspection_never_launches(raster, monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process, 'run_alignment_process', lambda *a, **k: pytest.fail('unexpected execution'))
    route = raster.route_snapshot()
    LocalPDFPageRasterizer(executable=raster.executable, executable_sha256=raster.executable_sha256)
    assert 'executable' not in route and route['maximum_side'] == 2048


@pytest.mark.parametrize('field,value', [('page', True), ('page', 0), ('page', 1001), ('source_digest', 'a' * 64), ('expected_route_digest', 'a' * 64)])
def test_bad_input_or_unreviewed_renderer_never_launches(raster, monkeypatch, field, value):
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process, 'run_alignment_process', lambda *a, **k: pytest.fail('unexpected execution'))
    with pytest.raises(ModelRuntimeError): render(raster, **{field: value})


def test_revoked_source_cancel_and_changed_program_fail_before_execution(raster, monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process, 'run_alignment_process', lambda *a, **k: pytest.fail('unexpected execution'))
    def denied(): raise PermissionError('synthetic authority revoked')
    with pytest.raises(PermissionError): render(raster, guard=denied)
    cancelled = Event(); cancelled.set()
    with pytest.raises(ModelRuntimeError): render(raster, cancellation=cancelled)
    digest = raster.route_snapshot()['admission_digest']; raster.executable_sha256 = 'b' * 64
    with pytest.raises(ModelRuntimeError): raster.render(PDF.read_bytes(), source_digest=sha256(PDF.read_bytes()).hexdigest(), page=1, expected_route_digest=digest, guard=lambda: None)


def test_missing_page_and_native_timeout_fail_closed(raster, monkeypatch):
    with pytest.raises(ModelRuntimeError): render(raster, page=3)
    import app.experimental.subtitle_alignment_native as process
    def timeout(*args, **kwargs): raise ValueError('PROCESSING_ALIGNMENT_NATIVE_TIMEOUT')
    monkeypatch.setattr(process, 'run_alignment_process', timeout)
    with pytest.raises(ModelRuntimeError) as failure: render(raster)
    assert 'TIMEOUT' in str(failure.value.code)
