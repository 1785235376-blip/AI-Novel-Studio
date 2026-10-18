"""Explicit hash-pinned host setup; startup never runs OCR."""
from hashlib import sha256
from pathlib import Path
import os
import subprocess
import sys
import pytest
from app.runtime import Runtime
from app.stable_identity import StableIdentityStore
from app.experimental.native_ocr_broker import candidates

FIELDS=('LOCAL_OCR_EXECUTABLE','LOCAL_OCR_EXECUTABLE_SHA256','LOCAL_OCR_TRAINEDDATA','LOCAL_OCR_MODEL_SHA256','LOCAL_OCR_LANGUAGE')


def configure(monkeypatch):
    tool=Path('/usr/bin/tesseract');model=Path('/usr/share/tesseract-ocr/5/tessdata/eng.traineddata')
    if not tool.is_file() or not model.is_file():pytest.skip('Installed pinned OCR fixture unavailable')
    for key,value in zip(FIELDS,[str(tool),sha256(tool.read_bytes()).hexdigest(),str(model),sha256(model.read_bytes()).hexdigest(),'eng']):
        monkeypatch.setenv(key,value)


def test_host_explicit_configuration_registers_without_running(tmp_path,monkeypatch):
    configure(monkeypatch)
    from app.local_tesseract_ocr import LocalTesseractOCRProvider
    monkeypatch.setattr(LocalTesseractOCRProvider,'recognize_image',lambda *args:pytest.fail('Startup inference forbidden'))
    runtime=Runtime(StableIdentityStore(tmp_path/'host.json'))
    rows=candidates(runtime)
    assert len(rows)==1 and rows[0]['provider_id']=='local-tesseract-ocr'
    assert rows[0]['synthetic'] is False and rows[0]['model_id']=='eng'


def test_host_default_empty_and_incomplete_configuration_rejected(tmp_path,monkeypatch):
    for key in FIELDS:monkeypatch.delenv(key,raising=False)
    assert candidates(Runtime(StableIdentityStore(tmp_path/'empty.json')))==[]
    monkeypatch.setenv(FIELDS[-1],'eng')
    with pytest.raises(ValueError,match='COMPLETE_HOST_CONFIGURATION_REQUIRED'):
        Runtime(StableIdentityStore(tmp_path/'incomplete.json'))


def test_host_bad_executable_pin_is_rejected(tmp_path,monkeypatch):
    configure(monkeypatch);monkeypatch.setenv('LOCAL_OCR_EXECUTABLE_SHA256','0'*64)
    with pytest.raises((ValueError,RuntimeError)):
        Runtime(StableIdentityStore(tmp_path/'bad.json'))


@pytest.mark.parametrize("native",[False,True])
def test_real_application_composition_reuses_original_owners(tmp_path,monkeypatch,native):
    if native:configure(monkeypatch)
    env=dict(os.environ,NOVEL_DATA_PATH=str(tmp_path/'data'),PYTHONDONTWRITEBYTECODE='1')
    if not native:
        for key in FIELDS:env.pop(key,None)
    result=subprocess.run([sys.executable,'-c',
        'from app.experimental.api import research_native_ocr, research_library_service, model_broker_service, legacy_api; '
        'assert research_native_ocr.research is research_library_service; '
        'assert research_native_ocr.broker is model_broker_service; '
        'assert research_native_ocr.manager is legacy_api.jobs; '
        f'assert len(model_broker_service.candidates(local_ocr_only=True))=={int(native)}; print("ORIGINAL_OWNERS_READY")'],
        env=env,capture_output=True,text=True,timeout=30)
    assert result.returncode==0,result.stdout+result.stderr
    assert 'ORIGINAL_OWNERS_READY' in result.stdout


def test_native_status_exposes_only_selectable_route_fields(tmp_path,monkeypatch):
    configure(monkeypatch)
    from app.experimental.research_native_ocr import NativeResearchOCRCoordinator
    from app.experimental.research_ocr_execution import FLAGS
    from app.experimental.flags import runtime_dependencies
    required=set(FLAGS)
    while True:
        expanded=required|{d for f in required for d in runtime_dependencies()[f]}
        if expanded==required:break
        required=expanded
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(sorted(required)))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','false')
    runtime=Runtime(StableIdentityStore(tmp_path/'status.json'))
    from types import SimpleNamespace
    coordinator=object.__new__(NativeResearchOCRCoordinator)
    coordinator.broker=SimpleNamespace(candidates=lambda **kwargs:candidates(runtime))
    status=coordinator.status()
    assert status['status']=='CONFIGURED'
    assert set(status['routes'][0])=={'provider_id','model_id','display_name','languages'}
    assert status['routes'][0]['languages']==['eng']
    assert 'traineddata' not in str(status) and '/usr/' not in str(status)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    assert coordinator.status()['routes']==[]
