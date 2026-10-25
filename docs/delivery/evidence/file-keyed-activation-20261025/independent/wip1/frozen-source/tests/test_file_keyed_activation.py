"""Real mounted File keyed admission, original Mock stream and manual adoption.

Provider payloads and scheduling are controlled; authority, source, worker,
repositories, context/snapshot and review implementations are never bypassed.
"""
from copy import copy, deepcopy
import hashlib
import json
from threading import Event, Thread
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import api, jobs as jobs_module
from app.agents import AgentRegistry, AgentRunner
from app.author_request import chapter_digest
from app.config import Settings
from app.creative.project_store import CreativeProjectStore
from app.idempotency import IdempotencyStore
from app.jobs import JobManager
from app.lore.memory_agent import MemoryAgentRunner
from app.providers import MockProvider
from app.repositories.factory import create_repository_bundle
from app.runtime import Runtime
from app.services import CanonService, ChapterService, ContextService, GenerationService, LoreService, NovelService
from app.services.generation_project_binding import FIELD
from app.stable_identity import StableIdentityStore
from test_memory_agent_contract import Runtime as MemoryRuntime, memory_settings

pytestmark = pytest.mark.file_backend_only
DRAFT = 'BOUND_DRAFT: the original harbor secret remains.'


@pytest.fixture
def keyed(tmp_path, monkeypatch, memory_settings):
    import app.main as main_module
    import app.config as config_module
    from app.main import app
    config = Settings(storage_backend='file', novel_data=tmp_path, mock_provider=True,
        enable_collaboration_runtime=False, enable_packaged_runtime=False,
        enable_narrative_context=False)
    bundle = create_repository_bundle(config, tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    novel = novels.create({'id':'keyed-file-book', 'title':'Original File owner'})
    chapter = chapters.get(chapters.create(novel['id'], {'title':'One', 'content':'ORIGINAL_SOURCE'})['id'])
    lore = LoreService(bundle.lore)
    contexts = ContextService(bundle.novels, bundle.chapters, lore,
        enable_narrative_context=False)
    canon = CanonService(bundle.canon)
    persistence = GenerationService(bundle.generations)
    memory = MemoryAgentRunner(bundle.novels, bundle.chapters, lore, persistence,
        AgentRunner(AgentRegistry()), MemoryRuntime('{"proposals":[]}'))
    runtime = Runtime(StableIdentityStore(tmp_path/'runtime'/'identities.json'))
    provider = MockProvider(delay_ms=0)
    monkeypatch.setattr(provider, '_text', lambda prompt: DRAFT)
    runtime.providers['mock'] = provider
    runtime._sync_model('mock', 'mock-writer')
    counts = dict(adapter=0, provider=0, worker=0)
    provider_entered, provider_release = Event(), Event()
    provider_release.set()
    original_stream = provider.stream
    def stream(*args, **kwargs):
        counts['provider'] += 1
        provider_entered.set()
        assert provider_release.wait(10), 'Mock release timed out'
        yield from original_stream(*args, **kwargs)
    monkeypatch.setattr(provider, 'stream', stream)
    adapter = runtime.provider_registry.resolve('mock')
    original_adapter = adapter.stream_text
    def adapter_stream(request):
        counts['adapter'] += 1
        yield from original_adapter(request)
    monkeypatch.setattr(adapter, 'stream_text', adapter_stream)
    for module in (api, jobs_module, main_module, config_module):
        monkeypatch.setattr(module, 'settings', config)
    monkeypatch.setattr(api, 'runtime', runtime)
    monkeypatch.setattr(jobs_module, 'runtime', runtime)
    monkeypatch.setattr(api, 'novel_service', novels)
    monkeypatch.setattr(api, 'chapter_service', chapters)
    def reopen():
        return JobManager(generations=persistence, chapters=chapters, contexts=contexts,
            canon=canon, memory_extractor=memory, snapshot_required=False)
    manager = reopen()
    monkeypatch.setattr(api, 'jobs', manager)
    store = IdempotencyStore(tmp_path/'idempotency.json')
    monkeypatch.setattr(api, '_idempotency_store', store)
    entered, release, finished, memory_finished = Event(), Event(), Event(), Event()
    original_run = manager._run
    def run(job):
        counts['worker'] += 1
        entered.set()
        assert release.wait(10), 'worker release timed out'
        try: return original_run(job)
        finally: finished.set()
    monkeypatch.setattr(manager, '_run', run)
    original_memory = memory._quiet_extract
    def quiet(*args, **kwargs):
        try: return original_memory(*args, **kwargs)
        finally: memory_finished.set()
    monkeypatch.setattr(memory, '_quiet_extract', quiet)
    owner = CreativeProjectStore(SimpleNamespace(backend='file', root=tmp_path))
    fixture = SimpleNamespace(root=tmp_path, config=config, bundle=bundle, novels=novels,
        chapters=chapters, chapter=chapter, lore=lore, contexts=contexts, canon=canon,
        persistence=persistence, memory=memory, runtime=runtime, manager=manager,
        store=store, owner=owner, incarnation=owner.incarnation(novel['id']), counts=counts,
        entered=entered, release=release, finished=finished, memory_finished=memory_finished,
        provider_entered=provider_entered, provider_release=provider_release,
        original_run=original_run, reopen=reopen, monkeypatch=monkeypatch,
        client=TestClient(app, raise_server_exceptions=False),
        payload={'novel_id':novel['id'], 'chapter_id':chapter['id'], 'instruction':'Continue',
                 'profile':'LOCAL_ONLY', 'provider_id':'mock', 'model_id':'mock-writer'})
    yield fixture
    release.set(); provider_release.set()
    if entered.is_set(): assert finished.wait(10), 'writer worker did not finish'
    if any(row.get('operation')=='MEMORY_EXTRACTION' for row in bundle.generations.load_all()):
        assert memory_finished.wait(10), 'memory worker did not finish'


def post(f, key='original-key', operation='continue', **payload):
    return f.client.post('/api/generate/'+operation, json={**f.payload, **payload},
        headers={'Idempotency-Key':key} if key is not None else {})


def queued(f, **kwargs):
    response = post(f, **kwargs)
    assert response.status_code == 202, response.text
    result = response.json()
    assert set(result) == {'job_id','status','events_url','base_chapter_version'}
    assert result['status'] == 'QUEUED' and result['base_chapter_version'] == 1
    assert f.entered.wait(5)
    return result, f.manager.jobs[result['job_id']]


def finish(f, job):
    f.release.set()
    assert f.finished.wait(10)
    assert job.status == 'COMPLETED', (job.status, job.error_code, job.error)
    return f.persistence.get(job.id)


def files(f):
    root = f.root/'novels'/f.chapter['novel_id']
    return {str(p.relative_to(root)):p.read_bytes() for p in root.rglob('*') if p.is_file()}


def replace_owner(f):
    nid = f.chapter['novel_id']
    f.novels.delete(nid)
    f.novels.create({'id':nid, 'title':'Replacement'})
    f.chapters.create(nid, {'title':'One', 'content':'REPLACEMENT_SOURCE'})
    assert f.owner.incarnation(nid) != f.incarnation


@pytest.mark.parametrize('operation', ['continue', 'rewrite'])
def test_real_keyed_mock_candidate_to_http_manual_adoption(keyed, operation):
    f = keyed
    result, job = queued(f, operation=operation)
    initial = f.persistence.get(job.id)
    assert initial['status'] == 'QUEUED' and FIELD in initial
    binding = deepcopy(initial[FIELD])
    assert binding['project_incarnation'] == f.incarnation
    assert binding['schema_version'] == 2
    assert binding['base_chapter_version'] == f.chapter['version']
    assert binding['base_chapter_digest'] == chapter_digest(f.chapter)
    assert FIELD not in job.public() and 'base_chapter_digest' not in job.public()
    row = finish(f, job)
    assert row[FIELD] == binding and row['output'] == DRAFT
    assert f.counts['adapter'] == f.counts['provider'] == 1
    snapshots = list((f.root/'novels'/job.novel_id/'lore/context_snapshots').glob('*.json'))
    assert snapshots, 'deferred writer snapshot must not be skipped'
    accepted_cid = job.novel_id+':2' if operation=='continue' else job.chapter_id
    accepted_version = 1 if operation=='continue' else 2
    f.memory.runtime.provider.text = json.dumps({'proposals':[{'proposal_type':'EVENT',
        'payload':{'description':DRAFT}, 'confidence':.9,
        'evidence':[{'chapter_id':accepted_cid,'chapter_version':accepted_version,'excerpt':DRAFT,
                     'locator':{'kind':'DOCUMENT_RANGE','from':0,'to':len(DRAFT)}}]}]})
    response = f.client.post(f'/api/generation/{job.id}/accept', json={'expected_version':1})
    assert response.status_code == 200, response.text
    accepted = response.json()
    assert accepted['chapter']['id'] == accepted_cid
    assert DRAFT in f.chapters.get(accepted_cid)['content']
    assert f.canon.list_pending(job.novel_id)[0]['id'] == accepted['pending_canon']['id']
    assert DRAFT[:240] in (f.root/'novels'/job.novel_id/'summaries/index.json').read_text()
    assert f.memory_finished.wait(10)
    proposals = f.bundle.lore.list_proposals(job.novel_id)
    assert len(proposals) == 1
    relations = f.bundle.lore.list_proposal_evidence(proposals[0]['id'])
    assert len(relations) == 1
    assert f.bundle.lore.get_evidence(relations[0]['evidence_id'])['excerpt'] == DRAFT
    memory = f.persistence.get(proposals[0]['generation_job_id'])
    assert memory['status']=='COMPLETED'
    assert memory['memory_project_binding']['project_incarnation']==f.incarnation
    assert f.persistence.get(job.id)[FIELD] == binding
    replay = post(f, operation=operation)
    assert replay.status_code == 202 and replay.json() == result
    assert f.counts['worker'] == f.counts['provider'] == 1


@pytest.mark.parametrize('key,operation,profile', [(None,'continue','LOCAL_ONLY'),
    ('polish-key','polish','LOCAL_ONLY'), ('brainstorm-key','brainstorm','LOCAL_ONLY'),
    ('hybrid-key','continue','HYBRID')])
def test_excluded_legacy_modes_remain_unbound(keyed, key, operation, profile):
    _, job = queued(keyed, key=key, operation=operation, profile=profile)
    assert FIELD not in keyed.persistence.get(job.id)
    finish(keyed, job)


@pytest.mark.parametrize('port', ['memory', 'canon', 'contexts', 'generation'])
def test_eligible_bad_composition_refuses_before_reservation(keyed, port):
    f=keyed
    other = create_repository_bundle(Settings(storage_backend='file', novel_data=f.root/'other'), f.root/'other')
    if port=='memory': f.manager.memory_extractor = SimpleNamespace(enqueue=lambda *a: None)
    if port=='canon': f.manager.canon = CanonService(other.canon)
    if port=='contexts': f.manager.contexts = ContextService(other.novels, other.chapters, LoreService(other.lore))
    if port=='generation': f.manager.persistence = GenerationService(other.generations)
    response = post(f)
    assert response.status_code >= 400, response.text
    assert not f.store.path.exists() or not json.loads(f.store.path.read_text())
    assert not f.bundle.generations.load_all() and f.counts['worker']==f.counts['provider']==0


@pytest.mark.parametrize('change', ['version','digest','archive','marker','owner'])
def test_pre_dispatch_source_or_owner_change_refuses_without_model(keyed, change):
    f=keyed
    _, job = queued(f)
    if change=='version': f.chapters.save(job.chapter_id, {'content':'NEW_SOURCE','version':1,'source':'MANUAL'})
    elif change=='archive': f.chapters.archive(job.chapter_id, 1)
    elif change=='owner': replace_owner(f)
    elif change=='marker': (f.root/'novels'/job.novel_id/'creative_project_v2.json').unlink()
    else:
        chapter_path = f.root/'novels'/job.novel_id/'chapters'
        candidates = [p for p in chapter_path.rglob('*.md') if 'ORIGINAL_SOURCE' in p.read_text()]
        assert candidates
        candidates[0].write_text(candidates[0].read_text().replace('ORIGINAL_SOURCE','CHANGED_DIGEST'))
    before=files(f)
    f.release.set(); assert f.finished.wait(10)
    assert f.counts['provider']==0 and job.status != 'COMPLETED'
    assert files(f)==before


def test_deletion_during_mock_wait_does_not_write_replacement(keyed):
    f=keyed
    f.provider_release.clear()
    _, job=queued(f)
    f.release.set(); assert f.provider_entered.wait(5)
    replace_owner(f)
    before=files(f)
    f.provider_release.set(); assert f.finished.wait(10)
    assert files(f)==before and job.status != 'COMPLETED'
    assert f.client.post(f'/api/generation/{job.id}/accept').status_code >= 400


def test_cold_queued_record_never_restarts_or_upgrades(keyed):
    f=keyed
    _, job=queued(f)
    binding=deepcopy(f.persistence.get(job.id)[FIELD])
    cold=f.reopen()
    restored=cold.jobs[job.id]
    assert restored.status=='FAILED'
    assert f.persistence.get(job.id)[FIELD]==binding
    assert f.counts['worker']==1 and f.counts['provider']==0
    with pytest.raises(Exception): cold.start_prepared(restored)
    with pytest.raises(Exception): cold._run(restored)
    assert f.counts['provider']==0


def test_bound_retry_cancel_and_staging_remain_closed(keyed):
    f=keyed
    _, job=queued(f)
    for endpoint in ('retry','cancel'):
        response=f.client.post(f'/api/generation/{job.id}/{endpoint}')
        assert response.status_code==409, response.text
    assert not job.cancelled.is_set()
    finish(f, job)


def test_duplicate_and_copied_start_capability_cannot_dispatch(keyed):
    f=keyed
    _, job=queued(f)
    with pytest.raises(Exception): f.manager.start_prepared(job)
    clone=copy(job)
    with pytest.raises(Exception): f.manager.start_prepared(clone)
    with pytest.raises(Exception): f.original_run(clone)
    assert f.counts['worker']==1 and f.counts['provider']==0
    finish(f, job)


def test_replaced_authorization_callback_cannot_grant_execution(keyed):
    f=keyed
    _, job=queued(f)
    job.request_authorization=lambda: None
    f.release.set(); assert f.finished.wait(10)
    assert f.counts['provider']==0 and job.status!='COMPLETED'


def test_authorization_callbacks_run_outside_owner_review_condition(keyed):
    from app.file_project_lifecycle import project_operation
    f=keyed
    from app.services.file_generation_admission import _Admission
    original=_Admission.revalidate
    checks=[]
    def context(*args, **kwargs):
        if f.entered.is_set():
            acquired=Event()
            def probe():
                with project_operation(f.root, f.chapter['novel_id']):
                    for job in tuple(f.manager.jobs.values()):
                        with f.manager._review_mutation(job.id), job.condition: pass
                    acquired.set()
            thread=Thread(target=probe)
            thread.start()
            ok=acquired.wait(2)
            checks.append(ok)
            assert ok, 'request authorization ran under owner/review/condition lock'
            thread.join(3)
        return original(*args, **kwargs)
    f.monkeypatch.setattr(_Admission, 'revalidate', context)
    _, job=queued(f)
    finish(f, job)
    assert checks and all(checks)


def receipt_key(f, key='old-key'):
    authority=[f.chapter['novel_id'], f.chapter['id'], 'local-author', 'local', None]
    scope=hashlib.sha256(json.dumps(authority).encode()).hexdigest()
    payload=api.GenerateIn(**f.payload).model_dump(exclude={'count'})
    digest=hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f'generate:continue:{scope}:{key}', digest


@pytest.mark.parametrize('phase', ['RECORDED','RESERVED'])
def test_retained_original_receipt_never_dispatches_or_upgrades(keyed, phase):
    from uuid import uuid4
    from app.services.generation_admission_receipt import reservation
    f=keyed
    key,digest=receipt_key(f)
    jid=str(uuid4())
    result={'job_id':jid,'status':'QUEUED','events_url':f'/api/generation/{jid}/events','base_chapter_version':1}
    value=({'schema_version':2,'project_incarnation':f.incarnation,'request_digest':digest,'result':result}
        if phase=='RECORDED' else reservation(f.incarnation,digest,jid))
    f.store.put(key,value)
    before=f.store.path.read_bytes()
    response=post(f,key='old-key')
    if phase=='RECORDED': assert response.status_code==202 and response.json()==result
    else: assert response.status_code==409 and response.json()['detail']['code']=='ADMISSION_UNCONFIRMED'
    assert f.store.path.read_bytes()==before
    assert f.counts['worker']==f.counts['provider']==0 and not f.bundle.generations.load_all()
    conflict=post(f,key='old-key',instruction='Different request')
    assert conflict.status_code==409
    assert conflict.json()['detail']['code']=='IDEMPOTENCY_REQUEST_MISMATCH'
    assert f.counts['worker']==0


def test_cold_completed_candidate_adopts_without_new_execution(keyed):
    f=keyed
    _, job=queued(f)
    row=finish(f,job)
    cold=f.reopen()
    restored=cold.get(job.id)
    assert restored.status=='COMPLETED' and FIELD in row
    f.monkeypatch.setattr(api,'jobs',cold)
    accepted=f.client.post(f'/api/generation/{job.id}/accept',json={'expected_version':1})
    assert accepted.status_code==200, accepted.text
    assert f.memory_finished.wait(10)
    assert f.counts['provider']==f.counts['worker']==1


@pytest.mark.parametrize('change',['version','digest'])
def test_cold_manual_adoption_rechecks_original_source(keyed,change):
    f=keyed
    _, job=queued(f)
    finish(f,job)
    if change=='version': f.chapters.save(job.chapter_id,{'content':'CHANGED','version':1,'source':'MANUAL'})
    else:
        candidates=[p for p in (f.root/'novels'/job.novel_id/'chapters').rglob('*.md') if 'ORIGINAL_SOURCE' in p.read_text()]
        assert candidates
        candidates[0].write_text(candidates[0].read_text().replace('ORIGINAL_SOURCE','DIGEST_CHANGED'))
    cold=f.reopen()
    f.monkeypatch.setattr(api,'jobs',cold)
    before=files(f)
    accepted=f.client.post(f'/api/generation/{job.id}/accept',json={'expected_version':1})
    assert accepted.status_code>=400, accepted.text
    assert files(f)==before and not f.memory_finished.is_set()


@pytest.mark.parametrize('port',['context','snapshot','dispatch'])
def test_same_thread_replacement_at_final_preparation_ports(keyed,port):
    f=keyed
    replaced=[]; replacement={}
    def change():
        if not replaced:
            replaced.append(True)
            replace_owner(f)
            replacement.update(files(f))
    if port=='context':
        target,name=f.contexts,'for_chapter'
    elif port=='snapshot':
        target,name=f.contexts,'save_snapshot'
    else:
        target,name=f.runtime.generation_runtime.text_node,'stream'
    original=getattr(target,name)
    def wrapped(*args,**kwargs):
        change()
        return original(*args,**kwargs)
    f.monkeypatch.setattr(target,name,wrapped)
    _,job=queued(f)
    f.release.set(); assert f.finished.wait(10)
    assert replaced, 'scheduled original seam was never reached'
    assert files(f)==replacement and job.status!='COMPLETED'
    if port!='snapshot': assert f.counts['provider']==0
