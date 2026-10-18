"""Native PDF model seam: real synthetic PDF smoke, explicit receipt boundaries."""
from dataclasses import fields
from types import SimpleNamespace
from hashlib import sha256
from threading import Event
import pytest
from app.local_pdf_ocr import LocalPDFOCRProvider
from app.model_runtime import ModelRuntimeError
from app.vision_ocr_runtime import PDFPageOCRRequest, VisionOCRRequest
from test_local_pdf_raster_additive import PDF, raster
from test_local_tesseract_ocr_additive import native, install, make_request
from test_vision_ocr_runtime_additive import rig


@pytest.fixture
def pdf_provider(native, raster):
    return LocalPDFOCRProvider(image_provider=native, rasterizer=raster)


def request(runtime, **changes):
    content = PDF.read_bytes()
    values = dict(provider_id='native-ocr', model_id='eng', content=content,
        media_type='application/pdf', language='eng', source_digest=sha256(content).hexdigest(),
        route_digest=runtime.vision_ocr_node.binding('native-ocr', 'eng')['route_digest'],
        request_id='original-pdf-page-smoke', page=2, dispatch_guard=lambda: None)
    values.update(changes)
    return PDFPageOCRRequest(**values)


def test_real_original_node_preserves_pdf_page_and_derived_image_identity(rig, pdf_provider):
    runtime, _ = rig; install(runtime, pdf_provider)
    original = PDF.read_bytes(); result = runtime.vision_ocr_node.execute(request(runtime))
    assert 'PAGE 2' in result.text and 'EVIDENCE 123' in result.text
    receipt = result.receipt
    assert receipt['source_digest'] == receipt['input_sha256'] == sha256(original).hexdigest()
    assert receipt['source_page'] == 2 and receipt['rendered_image_sha256'] != receipt['source_digest']
    assert receipt['renderer_digest'] == pdf_provider.rasterizer.route_snapshot()['admission_digest']
    assert receipt['review_required'] is True and receipt['automatic_canon'] is False
    assert receipt['model_quality'] == 'NOT_RUN' and receipt['execution_node_uuid']
    assert PDF.read_bytes() == original


def test_old_image_route_and_request_cannot_silently_accept_pdf(rig, native, pdf_provider, monkeypatch):
    runtime, _ = rig; install(runtime, native)
    with pytest.raises(ModelRuntimeError): runtime.vision_ocr_node.execute(request(runtime))
    with pytest.raises(ModelRuntimeError): VisionOCRRequest(**{f.name: getattr(request(runtime), f.name) for f in fields(PDFPageOCRRequest) if f.name != 'page'})


def test_pdf_route_rejects_image_request_without_calling_renderer(rig, pdf_provider, monkeypatch):
    runtime, _ = rig; install(runtime, pdf_provider)
    monkeypatch.setattr(pdf_provider.rasterizer, 'render', lambda *a, **k: pytest.fail('unexpected render'))
    with pytest.raises(ModelRuntimeError): runtime.vision_ocr_node.execute(make_request(runtime))


@pytest.mark.parametrize('changes', [{'page': True}, {'page': 0}, {'page': 1001}, {'media_type': 'image/png'},
    {'content': b'not pdf'}, {'source_digest': 'a'*64}, {'cancellation': object()}])
def test_pdf_envelope_rejects_invalid_or_unbound_input(rig, pdf_provider, changes):
    runtime, _ = rig; install(runtime, pdf_provider)
    with pytest.raises(ModelRuntimeError): request(runtime, **changes)


def test_cancel_and_authority_revocation_prevent_native_work(rig, pdf_provider, monkeypatch):
    runtime, _ = rig; install(runtime, pdf_provider)
    monkeypatch.setattr(pdf_provider.rasterizer, 'render', lambda *a, **k: pytest.fail('unexpected render'))
    cancelled = Event(); cancelled.set()
    with pytest.raises(ModelRuntimeError): runtime.vision_ocr_node.execute(request(runtime, cancellation=cancelled))
    def deny(): raise PermissionError('synthetic revoked')
    with pytest.raises(PermissionError): runtime.vision_ocr_node.execute(request(runtime, dispatch_guard=deny))


def test_revocation_between_raster_and_ocr_discards_page(rig, pdf_provider, monkeypatch):
    runtime, _ = rig; install(runtime, pdf_provider); revoked = False
    original = pdf_provider.rasterizer.render
    def render(*args, **kwargs):
        nonlocal revoked
        value = original(*args, **kwargs); revoked = True; return value
    def guard():
        if revoked: raise PermissionError('synthetic revoked')
    monkeypatch.setattr(pdf_provider.rasterizer, 'render', render)
    monkeypatch.setattr(pdf_provider.image_provider, 'recognize_image', lambda *a, **k: pytest.fail('unexpected OCR'))
    with pytest.raises(PermissionError): runtime.vision_ocr_node.execute(request(runtime, dispatch_guard=guard))


@pytest.mark.parametrize('change', [{'source_page': 1}, {'source_page': True}, {'rendered_image_sha256': 'bad'},
    {'renderer_digest': 'c'*64}, {'source_digest': 'c'*64}, {'private_path': '/not/allowed'}])
def test_original_node_rejects_wrong_or_extra_pdf_receipts(rig, pdf_provider, monkeypatch, change):
    runtime, _ = rig; install(runtime, pdf_provider)
    from app.vision_ocr_runtime import VisionOCRResponse
    def response(value):
        text = 'SYNTHETIC receipt validation only'
        receipt = dict(model_called=True, source_digest=value.source_digest, input_sha256=value.source_digest,
            route_digest=value.route_digest, language=value.language, text_sha256=sha256(text.encode()).hexdigest(),
            source_page=value.page, rendered_image_sha256='b'*64,
            renderer_digest=pdf_provider.rasterizer.route_snapshot()['admission_digest'])
        return VisionOCRResponse(value.provider_id, value.model_id, text, {**receipt, **change})
    monkeypatch.setattr(pdf_provider, 'recognize_pdf_page', response)
    with pytest.raises(ModelRuntimeError): runtime.vision_ocr_node.execute(request(runtime))


def test_pdf_provider_has_distinct_explicit_broker_admission(rig, pdf_provider):
    from app.experimental.native_ocr_broker import candidates
    runtime, _ = rig; install(runtime, pdf_provider)
    host = SimpleNamespace(generation_runtime=runtime, provider_registry=runtime.providers, model_registry=runtime.models)
    rows = candidates(host)
    assert len(rows) == 1 and rows[0]['identity']['source_kind'] == 'PDF'
    assert rows[0]['identity']['pdf_adapter_hash'] and rows[0]['identity']['raster_adapter_hash']
    assert rows[0]['identity']['native_ocr_binding']['route']['schema'] == 'local-vision-ocr-pdf-native-admission/1'
