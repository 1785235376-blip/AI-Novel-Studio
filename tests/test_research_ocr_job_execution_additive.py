"""Trusted original JobManager seam; no public Research dispatch or broker claim."""
import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
import time
from types import SimpleNamespace
import pytest

from app.experimental.research_library import ResearchLibraryService
from app.experimental.research_vision import PreparedResearchOCRSource
from app.experimental.research_ocr_execution import FLAGS
from app.model_runtime import GenerationRuntime, ProviderRegistry, ModelRegistry, ProviderDescriptor, ModelDescriptor, Modality
from app.stable_identity import StableIdentityStore
from app.jobs import generation_content_available
from test_v2_independent_workspace import rig, png_bytes
from test_r4_research_library import payload
from test_vision_ocr_runtime_additive import Provider
from test_research_ocr_job_persistence_additive import reopen


def setup(e, monkeypatch, provider=None, content=None, *, terminal_error=False):
    from app.experimental.flags import runtime_dependencies
    required=set(FLAGS);dependencies=runtime_dependencies()
    while True:
        expanded=required|{f for flag in required for f in dependencies[flag]}
        if expanded==required:break
        required=expanded
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',','.join(sorted(required)))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE','false')
    service=ResearchLibraryService(e.raw_store,e.novels,e.chapters,historical_inspection=True)
    raw=content or png_bytes()
    row=service.import_file(e.nid,e.scope,e.actor,payload(filename='source.png',content_base64=base64.b64encode(raw).decode()),guard=lambda:None)
    source=PreparedResearchOCRSource(service,e.nid,e.scope,e.actor,row['id'],1,lambda:None)
    identities=StableIdentityStore(e.root/'ocr-runtime-identities.json');identities.get_or_create('execution_node','local')
    providers=ProviderRegistry(identities);models=ModelRegistry(identities)
    provider=provider or Provider();route=provider.route_snapshot();pid=route['provider_id'];mid=route['model_id']
    providers.register(ProviderDescriptor(pid,'Test OCR','local',frozenset({Modality.VISION}),True,True),provider)
    models.register(ModelDescriptor(mid,pid,'Test OCR',Modality.VISION,frozenset({'OCR'})))
    node=GenerationRuntime(providers,models).vision_ocr_node
    binding={key:value for key,value in source.binding.items() if key not in {'contract','access','page'}}
    binding.update(contract='RESEARCH_OCR_JOB_V1',source_kind='IMAGE',language='eng',
        route_digest=node.binding(pid,mid)['route_digest'],reviewed_preview_digest='c'*64)
    manager=reopen(e);calls=[]
    def terminal():
        calls.append('terminal')
        if terminal_error:raise OSError('synthetic settlement failure')
    job=manager._prepare_research_ocr_job(source=source,node=node,binding=binding,provider_id=pid,model_id=mid,
        deadline=(datetime.now(timezone.utc)+timedelta(seconds=60)).isoformat(),
        before_dispatch=lambda:calls.append('dispatch'),on_terminal=terminal)
    return SimpleNamespace(service=service,row=row,source=source,node=node,provider=provider,manager=manager,job=job,calls=calls)


def wait(e):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if e.job.research_ocr_execution_authority._result is not None:return
        if e.job.status in {'FAILED','CANCELLED'} and e.job.terminal_hook_status is not None:return
        time.sleep(.01)
    raise AssertionError('OCR worker did not terminate')


def test_original_job_executes_once_and_keeps_result_out_of_manuscript(rig,monkeypatch):
    e=setup(rig,monkeypatch);e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='COMPLETED' and e.calls==['dispatch','terminal'] and e.provider.calls==1
    result=e.job.research_ocr_execution_authority.result()
    assert result.text==e.job.output and not generation_content_available(e.job)
    assert e.job.chapter_id is None and e.job.graph_binding is None
    assert e.manager.persistence.get(e.job.id)['status']=='COMPLETED'
    with pytest.raises(ValueError):e.manager._start_research_ocr_job(e.job)
    with pytest.raises(ValueError,match='ALREADY_CLAIMED'):e.manager._run(e.job)
    restored=reopen(rig).get(e.job.id)
    assert restored.research_ocr_execution_authority is None and not generation_content_available(restored)
    assert rig.chapters.list(rig.nid)==[]


def test_source_revocation_during_provider_discards_output_and_settles_once(rig,monkeypatch):
    e=setup(rig,monkeypatch)
    e.provider.mutate=lambda _:e.service.transition_source(rig.nid,rig.scope,rig.actor,e.row['id'],1,'revoke',guard=lambda:None)
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='FAILED' and e.job.output=='' and e.calls==['dispatch','terminal']
    with pytest.raises((ValueError,FileNotFoundError)):e.job.research_ocr_execution_authority.result()


def test_cooperative_cancel_during_provider_keeps_no_output(rig,monkeypatch):
    e=setup(rig,monkeypatch);e.provider.mutate=lambda _:e.job.cancelled.set()
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='CANCELLED' and e.job.output=='' and e.calls==['dispatch','terminal']


def test_settlement_failure_does_not_publish_or_replay(rig,monkeypatch):
    e=setup(rig,monkeypatch,terminal_error=True)
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='FAILED' and e.job.output=='' and e.provider.calls==1
    assert e.job.terminal_hook_status=='FAILED_RECONCILIATION_REQUIRED'
    with pytest.raises(ValueError):e.job.research_ocr_execution_authority.result()


def test_changed_identity_or_different_manager_cannot_start(rig,monkeypatch):
    e=setup(rig,monkeypatch)
    with pytest.raises(ValueError):reopen(rig)._start_research_ocr_job(e.job)
    e.job.research_ocr_binding['source_version']=2
    with pytest.raises(ValueError):e.manager._start_research_ocr_job(e.job)
    assert e.provider.calls==0 and e.calls==[]


def test_revocation_after_queue_is_terminal_not_stuck(rig,monkeypatch):
    e=setup(rig,monkeypatch);original=e.manager._run
    def run(job):
        e.service.transition_source(rig.nid,rig.scope,rig.actor,e.row['id'],1,'revoke',guard=lambda:None)
        original(job)
    monkeypatch.setattr(e.manager,'_run',run)
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='FAILED' and e.provider.calls==0 and e.calls==['terminal']


def test_persisted_result_tampering_is_not_live_result_authority(rig,monkeypatch):
    e=setup(rig,monkeypatch);e.manager._start_research_ocr_job(e.job);wait(e)
    record=e.manager.persistence.get(e.job.id);record['output']='forged persisted output';e.manager.persistence.save(record)
    with pytest.raises(ValueError,match='TERMINAL_RESULT'):e.job.research_ocr_execution_authority.result()


def test_real_installed_native_ocr_through_original_job_manager(rig,monkeypatch):
    from app.local_tesseract_ocr import LocalTesseractOCRProvider
    from test_local_tesseract_ocr_additive import image_bytes
    executable=Path('/usr/bin/tesseract');traineddata=Path('/usr/share/tesseract-ocr/5/tessdata/eng.traineddata')
    if not executable.is_file() or not traineddata.is_file():pytest.skip('Installed native English tool unavailable')
    provider=LocalTesseractOCRProvider(provider_id='native-ocr',model_id='eng',executable=executable,
        executable_sha256=sha256(executable.read_bytes()).hexdigest(),traineddata=traineddata,
        model_sha256=sha256(traineddata.read_bytes()).hexdigest(),language='eng')
    e=setup(rig,monkeypatch,provider,image_bytes());e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='COMPLETED' and e.job.research_ocr_execution_authority.result().text=='STUDIO OCR 123'
    assert e.calls==['dispatch','terminal'] and rig.chapters.list(rig.nid)==[]


def test_stripped_passive_markers_cannot_select_author_worker(rig,monkeypatch):
    import app.jobs as jobs_module
    e=setup(rig,monkeypatch);original=e.manager._run;author_calls=[]
    def forbidden(*args,**kwargs):
        author_calls.append(True)
        raise RuntimeError('OCR must never enter Author routing')
    monkeypatch.setattr(jobs_module.runtime,'router',forbidden)
    def run(job):
        job.research_ocr_binding=None;job.experimental_origin=None;job.operation='continue'
        original(job)
    monkeypatch.setattr(e.manager,'_run',run)
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.research_ocr_execution_authority.worker_claimed, 'Transient OCR task escaped its typed worker'
    assert author_calls==[], 'Transient OCR identity was lost when passive markers were stripped'
    assert e.provider.calls==0 and e.job.output==''


def test_project_recreation_during_provider_cannot_publish_to_new_owner(rig,monkeypatch):
    e=setup(rig,monkeypatch)
    def recreate(_):
        rig.novels.delete(rig.nid)
        rig.create_project(nid=rig.nid)
    e.provider.mutate=recreate
    e.manager._start_research_ocr_job(e.job);wait(e)
    assert e.job.status=='FAILED' and e.job.output==''
    with pytest.raises(KeyError):e.manager.persistence.get(e.job.id)
    assert e.job.id not in reopen(rig).jobs
    assert rig.chapters.list(rig.nid)==[]
