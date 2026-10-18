"""Pinned local OCR adapter checks, with one real installed-tool smoke case."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from threading import Event
import io

import pytest
from PIL import Image, ImageDraw, ImageFont
from app.local_tesseract_ocr import LocalTesseractOCRProvider
from app.model_runtime import ModelRuntimeError, RuntimeErrorCode, ProviderDescriptor, ModelDescriptor, Modality
from app.vision_ocr_runtime import VisionOCRRequest
from test_vision_ocr_runtime_additive import rig


def image_bytes():
    image=Image.new('RGB',(700,100),'white')
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',40)
    ImageDraw.Draw(image).text((15,15),'STUDIO OCR 123',font=font,fill='black')
    result=io.BytesIO();image.save(result,format='PNG');return result.getvalue()


@pytest.fixture
def native():
    executable=Path('/usr/bin/tesseract');model=Path('/usr/share/tesseract-ocr/5/tessdata/eng.traineddata')
    if not executable.is_file() or not model.is_file():pytest.skip('Pinned installed Tesseract English fixture is unavailable')
    return LocalTesseractOCRProvider(provider_id='native-ocr',model_id='eng',executable=executable,
        executable_sha256=sha256(executable.read_bytes()).hexdigest(),traineddata=model,
        model_sha256=sha256(model.read_bytes()).hexdigest(),language='eng')


def install(runtime,provider):
    runtime.providers.register(ProviderDescriptor('native-ocr','Installed OCR fixture','local',frozenset({Modality.VISION}),True,True),provider)
    runtime.models.register(ModelDescriptor('eng','native-ocr','English fixture',Modality.VISION,frozenset({'OCR'})))


def make_request(runtime,**extra):
    content=image_bytes()
    values=dict(provider_id='native-ocr',model_id='eng',content=content,media_type='image/png',language='eng',
        source_digest=sha256(content).hexdigest(),route_digest=runtime.vision_ocr_node.binding('native-ocr','eng')['route_digest'],
        request_id='real-installed-ocr-fixture',dispatch_guard=lambda:None)
    values.update(extra);return VisionOCRRequest(**values)


def test_real_installed_tesseract_recognizes_generated_english_image(rig,native):
    runtime,_=rig;install(runtime,native)
    result=runtime.vision_ocr_node.execute(make_request(runtime))
    assert result.text=='STUDIO OCR 123'
    assert result.receipt['model_called'] is True
    assert result.receipt['review_required'] is True and result.receipt['automatic_canon'] is False
    assert result.receipt['model_quality']=='NOT_RUN'  # one fixture is not general quality acceptance
    assert result.receipt['model_sha256']==native.model_sha256


def test_native_construction_and_binding_never_start_a_process(rig,native,monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process,'run_alignment_process',lambda *a,**k:pytest.fail('unexpected native process'))
    runtime,_=rig;install(runtime,native)
    route=runtime.vision_ocr_node.binding('native-ocr','eng')['route']
    assert route['schema']=='local-vision-ocr-native-admission/1'
    assert 'endpoint' not in route and 'executable' not in route


def test_cancelled_request_never_starts_process(rig,native,monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process,'run_alignment_process',lambda *a,**k:pytest.fail('unexpected native process'))
    runtime,_=rig;install(runtime,native);cancel=Event();cancel.set()
    with pytest.raises(ModelRuntimeError) as error:runtime.vision_ocr_node.execute(make_request(runtime,cancellation=cancel))
    assert error.value.code==RuntimeErrorCode.CANCELLED


@pytest.mark.parametrize('case',['invalid','wrong-mime','large-dimensions'])
def test_invalid_images_never_reach_native_process(rig,native,monkeypatch,case):
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process,'run_alignment_process',lambda *a,**k:pytest.fail('unexpected native process'))
    runtime,_=rig;install(runtime,native)
    content=image_bytes();media='image/png'
    if case=='invalid':content=b'not image'
    elif case=='wrong-mime':media='image/jpeg'
    else:
        output=io.BytesIO();Image.new('RGB',(8193,1)).save(output,format='PNG');content=output.getvalue()
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(make_request(runtime,
        content=content,source_digest=sha256(content).hexdigest(),media_type=media))


def test_route_pin_changed_and_unsupported_language_fail_before_start(rig,native,monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    monkeypatch.setattr(process,'run_alignment_process',lambda *a,**k:pytest.fail('unexpected native process'))
    runtime,_=rig;install(runtime,native)
    with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(make_request(runtime,language='zho'))
    original=make_request(runtime);native.model_sha256='0'*64
    with pytest.raises(ValueError,match='FILE_CHANGED'):runtime.vision_ocr_node.execute(original)


def test_output_cap_and_invalid_utf8_are_not_returned(rig,native,monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    runtime,_=rig;install(runtime,native)
    for output in [b'x'*262145,b'\xff',b'',b'\x00bad']:
        def fake(*a,**kwargs):kwargs['stdout_path'].write_bytes(output)
        monkeypatch.setattr(process,'run_alignment_process',fake)
        with pytest.raises(ModelRuntimeError):runtime.vision_ocr_node.execute(make_request(runtime))


def test_authority_changed_after_native_result_is_not_returned(rig,native,monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    runtime,_=rig;install(runtime,native);revoked=False
    def guard():
        if revoked:raise PermissionError('revoked')
    def fake(*a,**kwargs):
        nonlocal revoked
        kwargs['stdout_path'].write_bytes(b'not publishable');revoked=True
    monkeypatch.setattr(process,'run_alignment_process',fake)
    with pytest.raises(PermissionError):runtime.vision_ocr_node.execute(make_request(runtime,dispatch_guard=guard))


def test_transparent_input_is_composited_on_white_and_not_mutated(rig,native,monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    runtime,_=rig;install(runtime,native)
    output=io.BytesIO();Image.new('RGBA',(10,10),(0,0,0,0)).save(output,format='PNG');content=output.getvalue()
    def fake(command,**kwargs):
        with Image.open(kwargs['cwd']/'input.png') as normalized:
            assert normalized.mode=='RGB' and normalized.getpixel((0,0))==(255,255,255)
        kwargs['stdout_path'].write_bytes(b'SYNTHETIC normalization test only')
    monkeypatch.setattr(process,'run_alignment_process',fake)
    result=runtime.vision_ocr_node.execute(make_request(runtime,content=content,source_digest=sha256(content).hexdigest()))
    assert result.receipt['input_sha256']==sha256(content).hexdigest()


def test_native_process_failures_and_timeouts_are_safe_errors(rig,native,monkeypatch):
    import app.experimental.subtitle_alignment_native as process
    runtime,_=rig;install(runtime,native)
    for problem,code in [(ValueError('PROCESSING_ALIGNMENT_NATIVE_TIMEOUT'),RuntimeErrorCode.TIMEOUT),
                         (OSError('private local path'),RuntimeErrorCode.PROVIDER_UNAVAILABLE)]:
        def fake(*a,**kwargs):raise problem
        monkeypatch.setattr(process,'run_alignment_process',fake)
        with pytest.raises(ModelRuntimeError) as error:runtime.vision_ocr_node.execute(make_request(runtime))
        assert error.value.code==code and 'private local path' not in str(error.value)
