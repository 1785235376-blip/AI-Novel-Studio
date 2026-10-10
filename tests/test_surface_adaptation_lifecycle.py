"""Original adaptation owner: File and opted-in real PostgreSQL contracts."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import os
from threading import Barrier, Event
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app.config import Settings, settings
from app.document import markdown_to_document
from app.repositories.factory import create_repository_bundle
from app.repositories.chapter_repository import VersionConflict
from app.services.adaptation_service import AdaptationService, digest

@pytest.fixture(params=[pytest.param('file',marks=pytest.mark.file_backend_only),pytest.param('postgres',marks=pytest.mark.postgres_backend_only)])
def env(tmp_path,request):
    backend=request.param;url=os.getenv('TEST_POSTGRES_DATABASE_URL','') if backend=='postgres' else ''
    if backend=='postgres' and not url:pytest.fail('real PostgreSQL adaptation requires TEST_POSTGRES_DATABASE_URL')
    config=Settings(storage_backend=backend,database_url=url,novel_data=tmp_path)
    bundle=create_repository_bundle(config,data_root=tmp_path);nid='adaptation-'+uuid4().hex
    bundle.novels.create({'id':nid,'title':'Synthetic adaptation'})
    source=bundle.chapters.create(nid,{'title':'One','content':'Original rich prose'})
    document=markdown_to_document('# One\n\nOriginal rich prose')
    document['content'][1]['attrs']={'blockId':'stable-original-block'}
    document['content'][1]['content'][0]['marks']=[{'type':'bold'}]
    source=bundle.chapters.save(source['id'],document,bundle.chapters.get(source['id'])['version'])
    service=AdaptationService(bundle.novels,bundle.chapters)
    e=SimpleNamespace(bundle=bundle,service=service,nid=nid,source=source,config=config,root=tmp_path)
    yield e
    if backend=='postgres':
        targets=[row.get('adapted_novel_id') or row.get('materialization',{}).get('project_id') for row in bundle.novels.list_adaptation_proposals(nid)]
        for target in targets:
            if target:
                try:bundle.novels.delete(target)
                except (KeyError,FileNotFoundError):pass
        bundle.novels.delete(nid);bundle.novels.database.engine.dispose()

def proposal(e):return e.service.create(e.nid,'SCREEN')
def materialized(e):
    p=proposal(e);e.service.approve(e.nid,p['id'],expected_revision=p['revision']);e.service.materialize(e.nid,p['id']);return e.service.get(e.nid,p['id'])
def accepted(e):
    p=materialized(e);tid=p['execution_manifest'][0]['id'];e.service.generate_draft(e.nid,p['id'],tid);e.service.review_draft(e.nid,p['id'],tid,'ACCEPTED');return e.service.get(e.nid,p['id']),tid

def test_blueprint_two_writers_and_history_reopen(env):
    e=env;p=proposal(e);barrier=Barrier(2)
    def change(label):
        barrier.wait()
        try:return e.service.update_blueprint(e.nid,p['id'],{**p['blueprint'],'focus':label},expected_revision=p['revision'])
        except VersionConflict:return None
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(change,['A','B']))
    assert sum(row is not None for row in results)==1
    reopened=AdaptationService(e.bundle.novels,e.bundle.chapters).get(e.nid,p['id'])
    assert reopened['revision']==2 and reopened['revision_history'][0]['blueprint']==p['blueprint']
    assert 'revision_history' not in reopened['revision_history'][0]
    with pytest.raises(VersionConflict):e.service.approve(e.nid,p['id'],expected_revision=1)

def test_materialization_preserves_rich_document_identity_and_idempotency(env):
    e=env;p=materialized(e);tid=p['execution_manifest'][0]['id'];cid=p['execution_manifest'][0]['target_chapter_id']
    assert cid!=e.source['id']
    assert e.bundle.chapters.get(cid)['document']==e.source['document']
    again=e.service.materialize(e.nid,p['id']);assert again['id']==p['adapted_novel_id']
    assert len(e.bundle.chapters.list(again['id']))==1
    assert p['materialization']['phase']=='COMPLETED' and p['source_snapshots'][0]['digest']==digest(e.source['document'])
    e.service.generate_draft(e.nid,p['id'],tid);e.service.review_draft(e.nid,p['id'],tid,'ACCEPTED');e.service.apply_draft(e.nid,p['id'],tid)
    assert e.bundle.chapters.get(cid)['document']==e.source['document']

def test_reviewed_target_never_uses_latest_version_legacy_or_flag_on(env,monkeypatch):
    e=env;p,tid=accepted(e);task=p['execution_manifest'][0];before=e.bundle.chapters.get(task['target_chapter_id'])
    saved=e.bundle.chapters.save(before['id'],markdown_to_document('# One\n\nNewer human edit'),before['version'])
    for flags in ['', 'adaptation_lifecycle_v1']:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES',flags)
        with pytest.raises(VersionConflict):e.service.apply_draft(e.nid,p['id'],tid)
        assert e.bundle.chapters.get(before['id'])==saved

def test_source_deleted_blocks_before_target_creation(env):
    e=env;p=proposal(e);e.service.approve(e.nid,p['id']);e.bundle.chapters.delete(e.source['id']);before=e.bundle.novels.list()
    with pytest.raises((FileNotFoundError,KeyError)):e.service.materialize(e.nid,p['id'])
    assert e.bundle.novels.list()==before and e.service.get(e.nid,p['id'])['status']=='APPROVED'

def test_source_edited_after_generation_blocks_review(env):
    e=env;p=materialized(e);tid=p['execution_manifest'][0]['id'];e.service.generate_draft(e.nid,p['id'],tid)
    e.bundle.chapters.save(e.source['id'],markdown_to_document('Changed source'),e.source['version'])
    with pytest.raises(VersionConflict):e.service.review_draft(e.nid,p['id'],tid,'ACCEPTED')

def test_project_lost_response_retains_intent_and_never_replays(env,monkeypatch):
    e=env;p=proposal(e);e.service.approve(e.nid,p['id']);original=e.bundle.novels.create;calls=[]
    def lost(payload):calls.append(payload['id']);original(payload);raise OSError('lost response')
    monkeypatch.setattr(e.bundle.novels,'create',lost)
    with pytest.raises(OSError):e.service.materialize(e.nid,p['id'])
    row=e.service.get(e.nid,p['id']);assert row['status']=='RECOVERY_REQUIRED' and row['materialization']['phase']=='PROJECT_WRITE_INTENT'
    restarted=AdaptationService(e.bundle.novels,e.bundle.chapters)
    with pytest.raises(ValueError,match='RECOVERY'):restarted.materialize(e.nid,p['id'])
    with pytest.raises(ValueError,match='RECONCILIATION'):restarted.action(e.nid,p['id'],'recover')
    assert len(calls)==1 and e.bundle.novels.get(calls[0])['id']==calls[0]

def test_chapter_lost_response_never_uses_count_to_replay(env,monkeypatch):
    e=env;p=proposal(e);e.service.approve(e.nid,p['id']);original=e.bundle.chapters.create;calls=[]
    def lost(nid,payload):created=original(nid,payload);calls.append(created['id']);raise OSError('lost chapter response')
    monkeypatch.setattr(e.bundle.chapters,'create',lost)
    with pytest.raises(OSError):e.service.materialize(e.nid,p['id'])
    row=e.service.get(e.nid,p['id']);assert row['materialization']['phase']=='CHAPTER_WRITE_INTENT'
    with pytest.raises(ValueError,match='RECOVERY'):e.service.materialize(e.nid,p['id'])
    assert len(calls)==1 and len(e.bundle.chapters.list(row['adapted_novel_id']))==1

def test_apply_lost_response_reconciles_without_second_write(env,monkeypatch):
    e=env;p,tid=accepted(e);task=p['execution_manifest'][0];original=e.bundle.chapters.save;calls=[]
    def lost(*args,**kwargs):saved=original(*args,**kwargs);calls.append(saved);raise OSError('response lost')
    monkeypatch.setattr(e.bundle.chapters,'save',lost)
    with pytest.raises(OSError):e.service.apply_draft(e.nid,p['id'],tid)
    current=e.service.get(e.nid,p['id']);assert current['execution_manifest'][0]['status']=='RECOVERY_REQUIRED'
    reopened=AdaptationService(e.bundle.novels,e.bundle.chapters);recovered=reopened.action(e.nid,p['id'],'recover',task_id=tid,expected_revision=current['revision'])
    assert recovered['status']=='APPLIED' and len(calls)==1 and recovered['result_version']==task['target_version']+1
    with pytest.raises(ValueError):reopened.apply_draft(e.nid,p['id'],tid)

def test_uncertain_apply_cannot_replay_if_target_unchanged(env,monkeypatch):
    e=env;p,tid=accepted(e)
    monkeypatch.setattr(e.bundle.chapters,'save',lambda *a,**kw:(_ for _ in ()).throw(OSError('unknown')))
    with pytest.raises(OSError):e.service.apply_draft(e.nid,p['id'],tid)
    with pytest.raises(ValueError,match='RECONCILIATION'):e.service.action(e.nid,p['id'],'recover',task_id=tid)

def test_real_model_without_original_admission_is_not_configured(env,monkeypatch):
    e=env;p=materialized(e);tid=p['execution_manifest'][0]['id'];called=[]
    e.service.runtime=SimpleNamespace(providers={'remote':object()},is_remote_text_provider=lambda _:True,prepare_text_route=lambda *a:called.append(a))
    object.__setattr__(settings,'mock_provider',False)
    task=e.service.generate_draft(e.nid,p['id'],tid,'model','remote','model')
    assert task['status']=='NOT_CONFIGURED' and not called and task.get('draft') is None

def test_cancel_during_synthetic_generation_fences_late_response(env,monkeypatch):
    from app.providers import MockProvider
    from app.model_runtime import TextGenerationResponse,TextModelNodeOutput
    e=env;p=materialized(e);tid=p['execution_manifest'][0]['id'];entered=Event();release=Event()
    class Node:
        def execute(self,_):
            entered.set();assert release.wait(5)
            data={'schema':'adaptation_chapter_draft','content':'Late draft','source_chapter_id':e.source['id'],'source_version':e.source['version']}
            response=TextGenerationResponse(json.dumps(data),'completed','mock','mock-writer')
            return TextModelNodeOutput(response.text,response,tid)
    e.service.runtime=SimpleNamespace(providers={'mock':MockProvider(0)},is_remote_text_provider=lambda _:False,prepare_text_route=lambda *a:Node())
    e.service.agent_runner=SimpleNamespace(build_prompt=lambda *a:'synthetic fixture')
    object.__setattr__(settings,'mock_provider',True);object.__setattr__(settings,'enable_packaged_runtime',False)
    with ThreadPoolExecutor(1) as pool:
        future=pool.submit(e.service.generate_draft,e.nid,p['id'],tid,'model','mock','mock-writer')
        assert entered.wait(5)
        running=e.service.get(e.nid,p['id']);e.service.action(e.nid,p['id'],'cancel',expected_revision=running['revision'],task_id=tid)
        release.set();result=future.result(timeout=10)
    assert result['status']=='CANCELLED' and result.get('draft') is None
    restarted=AdaptationService(e.bundle.novels,e.bundle.chapters)
    recovered=restarted.action(e.nid,p['id'],'recover',task_id=tid)
    assert recovered['status']=='PENDING_REWRITE' and recovered.get('draft') is None

def test_review_cas_and_draft_binding_tamper(env):
    e=env;p=materialized(e);tid=p['execution_manifest'][0]['id'];e.service.generate_draft(e.nid,p['id'],tid);p=e.service.get(e.nid,p['id'])
    e.service.review_draft(e.nid,p['id'],tid,'ACCEPTED',expected_revision=p['revision'])
    with pytest.raises(VersionConflict):e.service.review_draft(e.nid,p['id'],tid,'REJECTED',expected_revision=p['revision'])
    p=e.service.get(e.nid,p['id']);p['execution_manifest'][0]['draft']['content']='forged'
    e.bundle.novels.save_adaptation_proposal(e.nid,p,expected_revision=p['revision'])
    with pytest.raises(ValueError,match='changed after review'):e.service.apply_draft(e.nid,p['id'],tid)

def test_feature_revoke_blocks_lifecycle_proposal_mutation(env,monkeypatch):
    e=env;monkeypatch.setenv('EXPERIMENTAL_FEATURES','adaptation_lifecycle_v1');p=proposal(e)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES','')
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as error:e.service.approve(e.nid,p['id'],expected_revision=p['revision'])
    assert error.value.status_code==404 and e.service.get(e.nid,p['id'])['status']=='DRAFT'

def test_revocation_before_commit_leaves_original_blueprint(env):
    e=env;p=proposal(e)
    def denied():raise PermissionError('permission revoked')
    with pytest.raises(PermissionError):e.service.update_blueprint(e.nid,p['id'],{**p['blueprint'],'focus':'No'},expected_revision=p['revision'],check=denied)
    assert e.service.get(e.nid,p['id'])['blueprint']==p['blueprint']


def test_cancel_during_committed_apply_is_uncertain_until_reconciled(env,monkeypatch):
    e=env;p,tid=accepted(e);original=e.bundle.chapters.save;calls=[]
    def cancel_after_write(*args,**kwargs):
        result=original(*args,**kwargs);calls.append(result)
        latest=e.service.get(e.nid,p['id'])
        cancelled=e.service.action(e.nid,p['id'],'cancel',expected_revision=latest['revision'],task_id=tid)
        assert cancelled['status']=='RECOVERY_REQUIRED'
        return result
    monkeypatch.setattr(e.bundle.chapters,'save',cancel_after_write)
    with pytest.raises(ValueError,match='CLAIM_LOST'):e.service.apply_draft(e.nid,p['id'],tid)
    current=e.service.get(e.nid,p['id']);assert current['execution_manifest'][0]['status']=='RECOVERY_REQUIRED'
    recovered=e.service.action(e.nid,p['id'],'recover',expected_revision=current['revision'],task_id=tid)
    assert recovered['status']=='APPLIED' and len(calls)==1


def test_restart_after_clean_project_receipt_resumes_only_remaining_chapters(env,monkeypatch):
    e=env;p=proposal(e);e.service.approve(e.nid,p['id'])
    original=e.service._save;paused=[]
    def pause(item,changes,check=None,**kwargs):
        result=original(item,changes,check,**kwargs)
        if changes.get('materialization',{}).get('phase')=='PROJECT_COMMITTED' and not paused:
            paused.append(result['adapted_novel_id']);raise OSError('restart at clean checkpoint')
        return result
    monkeypatch.setattr(e.service,'_save',pause)
    with pytest.raises(OSError):e.service.materialize(e.nid,p['id'])
    restarted=AdaptationService(e.bundle.novels,e.bundle.chapters);row=restarted.get(e.nid,p['id'])
    assert row['status']=='RECOVERY_REQUIRED' and row['materialization']['phase']=='PROJECT_COMMITTED'
    recovered=restarted.action(e.nid,p['id'],'recover',expected_revision=row['revision'])
    result=restarted.materialize(e.nid,p['id'],expected_revision=recovered['revision'])
    assert result['id']==paused[0] and len(e.bundle.chapters.list(result['id']))==1


def test_capacity_preserves_history_and_reserved_cancellation(env,monkeypatch):
    from app.repositories import adaptation_versions as limits
    e=env;p=proposal(e)
    monkeypatch.setattr(limits,'MAX_REVISIONS',6);monkeypatch.setattr(limits,'FINALIZATION_RESERVE',2)
    for index in range(4):p=e.service.update_blueprint(e.nid,p['id'],{**p['blueprint'],'focus':str(index)},expected_revision=p['revision'])
    before=deepcopy(p)
    with pytest.raises(ValueError,match='CAPACITY_REVISION'):e.service.update_blueprint(e.nid,p['id'],{**p['blueprint'],'focus':'Overflow'},expected_revision=p['revision'])
    assert e.service.get(e.nid,p['id'])==before
    cancelled=e.service.action(e.nid,p['id'],'cancel',expected_revision=p['revision'])
    assert cancelled['status']=='CANCELLED' and len(cancelled['revision_history'])==5
    assert cancelled['revision_history'][:4]==before['revision_history']


def test_capacity_rejects_new_materialization_before_any_target_write(env,monkeypatch):
    from app.repositories import adaptation_versions as limits
    e=env;p=proposal(e);p=e.service.approve(e.nid,p['id']);before=e.bundle.novels.list()
    monkeypatch.setattr(limits,'MAX_REVISIONS',len(p['revision_history'])+4);monkeypatch.setattr(limits,'FINALIZATION_RESERVE',2)
    with pytest.raises(ValueError,match='CAPACITY'):e.service.materialize(e.nid,p['id'])
    assert e.bundle.novels.list()==before and e.service.get(e.nid,p['id'])['status']=='APPROVED'


def test_capacity_bounds_sources_proposals_drafts_and_generation_attempts(env,monkeypatch):
    import app.repositories.adaptation_versions as limits
    import app.repositories.file.novel as file_owner
    import app.repositories.postgres.novel as pg_owner
    import app.services.adaptation_service as service_module
    e=env
    monkeypatch.setattr(limits,'MAX_SOURCE_BYTES',10)
    with pytest.raises(ValueError,match='SOURCE_BYTES'):proposal(e)
    assert e.service.list(e.nid)==[]
    monkeypatch.setattr(limits,'MAX_SOURCE_BYTES',8_000_000)
    p=materialized(e);tid=p['execution_manifest'][0]['id']
    monkeypatch.setattr(file_owner,'MAX_PROPOSALS',1);monkeypatch.setattr(pg_owner,'MAX_PROPOSALS',1)
    with pytest.raises(ValueError,match='PROPOSAL_LIMIT'):proposal(e)
    monkeypatch.setattr(limits,'MAX_MANIFEST_DRAFT_BYTES',100)
    task=e.service.generate_draft(e.nid,p['id'],tid)
    assert task['status']=='FAILED' and task['error_code']=='ADAPTATION_CAPACITY_DRAFT_LIMIT' and task.get('draft') is None
    monkeypatch.setattr(service_module,'MAX_ATTEMPTS',1)
    with pytest.raises(ValueError,match='ATTEMPT_LIMIT'):e.service.generate_draft(e.nid,p['id'],tid)
    assert e.service.get(e.nid,p['id'])['execution_manifest'][0]['generation_attempts']==1
