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
        enable_narrative_context=False, enable_experimental_file_keyed_generation=True)
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
    responses=[]
    def adapter_stream(request):
        counts['adapter'] += 1
        for event in original_adapter(request):
            if event.event_type=='generation.completed': responses.append(event.response)
            yield event
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
        store=store, owner=owner, incarnation=owner.incarnation(novel['id']), counts=counts, responses=responses,
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
        package=f.root/'novels'/job.novel_id/'documents'/f"chapter-{f.chapter['number']:04d}.json"
        package.write_text(package.read_text().replace('ORIGINAL_SOURCE','CHANGED_DIGEST'))
        assert f.chapters.get(job.chapter_id)['version']==1
        assert chapter_digest(f.chapters.get(job.chapter_id))!=chapter_digest(f.chapter)
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
        package=f.root/'novels'/job.novel_id/'documents'/f"chapter-{f.chapter['number']:04d}.json"
        package.write_text(package.read_text().replace('ORIGINAL_SOURCE','DIGEST_CHANGED'))
        assert f.chapters.get(job.chapter_id)['version']==1
        assert chapter_digest(f.chapters.get(job.chapter_id))!=chapter_digest(f.chapter)
    cold=f.reopen()
    f.monkeypatch.setattr(api,'jobs',cold)
    before=files(f)
    accepted=f.client.post(f'/api/generation/{job.id}/accept',json={'expected_version':1})
    assert accepted.status_code>=400, accepted.text
    assert files(f)==before and not f.memory_finished.is_set()


@pytest.mark.parametrize('port',['context','snapshot','dispatch'])
def test_same_thread_replacement_at_final_preparation_ports(keyed,port):
    f=keyed
    replaced=[]; replacement={}; replacement_complete=[]
    def change():
        if not replaced:
            replaced.append(True)
            try:
                replace_owner(f)
                replacement_complete.append(True)
            finally: replacement.update(files(f))
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
    assert replaced and replacement_complete, 'scheduled original replacement did not complete'
    assert files(f)==replacement and job.status!='COMPLETED'
    if port!='snapshot': assert f.counts['provider']==0


def test_concurrent_completion_review_and_cold_restore_do_not_deadlock(keyed):
    f=keyed
    entered, release=Event(), Event()
    original=f.bundle.generations.save
    def save(row, **kwargs):
        result=original(row, **kwargs)
        if row.get('operation')=='continue' and row.get('status')=='COMPLETED':
            entered.set()
            assert release.wait(10)
        return result
    f.monkeypatch.setattr(f.bundle.generations,'save',save)
    _,job=queued(f)
    f.release.set(); assert entered.wait(5)
    errors=[]; adopted=[]; restored=[]
    def review():
        try: adopted.append(f.manager.accept(job.id))
        except BaseException as exc: errors.append(exc)
    def restore():
        try: restored.append(f.reopen())
        except BaseException as exc: errors.append(exc)
    threads=[Thread(target=review),Thread(target=restore)]
    for thread in threads: thread.start()
    release.set()
    for thread in threads: thread.join(10)
    assert all(not thread.is_alive() for thread in threads) and not errors
    assert f.finished.wait(5) and adopted and restored
    assert f.persistence.get(job.id)['status']=='ACCEPTED'
    assert f.memory_finished.wait(10)
    assert f.counts['worker']==f.counts['provider']==1


@pytest.mark.parametrize('boundary',['reserved','queue_before','queue_after'])
def test_uncertain_admission_boundaries_retain_receipt_and_never_redispatch(keyed,boundary):
    f=keyed
    if boundary=='reserved':
        original=f.store.put
        def put(key,value):
            result=original(key,value)
            if value.get('admission_state')=='RESERVED': raise OSError('committed RESERVED acknowledgement lost')
            return result
        f.monkeypatch.setattr(f.store,'put',put)
    else:
        original=f.bundle.generations.save
        def save(row,**kwargs):
            if row.get('status')=='QUEUED':
                assert FIELD in row and row[FIELD]['schema_version']==2
                if boundary=='queue_after': original(row,**kwargs)
                raise OSError('controlled durable queue uncertainty')
            return original(row,**kwargs)
        f.monkeypatch.setattr(f.bundle.generations,'save',save)
    first=post(f)
    assert first.status_code==503,first.text
    assert not f.entered.is_set() and f.counts['provider']==0
    retained=json.loads(f.store.path.read_text())
    assert retained
    again=post(f)
    assert again.status_code==409 and again.json()['detail']['code']=='ADMISSION_UNCONFIRMED'
    f.reopen()
    assert f.counts['worker']==f.counts['provider']==0
    for row in f.bundle.generations.load_all():
        assert FIELD in row and row[FIELD]['schema_version']==2


def test_source_changes_after_snapshot_preserve_execution_facts_but_not_candidate(keyed):
    f=keyed
    original=f.contexts.save_snapshot
    effects=[]
    def snapshot(*args,**kwargs):
        result=original(*args,**kwargs)
        effects.append(result)
        package=f.root/'novels'/f.chapter['novel_id']/'documents'/f"chapter-{f.chapter['number']:04d}.json"
        package.write_text(package.read_text().replace('ORIGINAL_SOURCE','CHANGED_AFTER_MODEL'))
        return result
    f.monkeypatch.setattr(f.contexts,'save_snapshot',snapshot)
    _,job=queued(f)
    f.release.set(); assert f.finished.wait(10)
    assert effects and f.counts['provider']==1
    assert job.status!='COMPLETED' and not job.output
    assert job.execution_outcome=='COMPLETED'
    from dataclasses import asdict
    assert len(f.responses)==1
    response=f.responses[0]
    assert job.usage_status==('REPORTED' if response.usage else 'UNKNOWN')
    assert job.usage==(asdict(response.usage) if response.usage else None)
    assert job.execution_mode==response.execution_mode
    assert job.provider_reference_id==response.provider_reference_id
    assert f.persistence.get(job.id)['status']!='COMPLETED'
    assert list((f.root/'novels'/job.novel_id/'lore/context_snapshots').glob('*.json'))
    assert f.client.post(f'/api/generation/{job.id}/accept').status_code>=400


def test_cached_v2_of_existing_unbound_job_is_not_upgraded(keyed):
    f=keyed
    result,job=queued(f,key=None)
    finish(f,job)
    row=f.persistence.get(job.id)
    assert FIELD not in row
    path=f.bundle.generations._job_path(job.id)
    before=path.read_bytes()
    key,digest=receipt_key(f)
    f.store.put(key,{'schema_version':2,'project_incarnation':f.incarnation,
        'request_digest':digest,'result':result})
    response=post(f,key='old-key')
    assert response.status_code==202 and response.json()==result
    assert path.read_bytes()==before and FIELD not in f.persistence.get(job.id)
    assert f.counts['worker']==f.counts['provider']==1


def test_narrative_context_mode_is_explicitly_unbound(keyed):
    f=keyed
    f.contexts.enable_narrative_context=True
    _,job=queued(f)
    assert FIELD not in f.persistence.get(job.id)
    finish(f,job)


@pytest.mark.parametrize('field',['source','selected_text'])
def test_explicit_selection_requests_remain_unbound(keyed,field):
    f=keyed
    _,job=queued(f,**{field:'ORIGINAL_SOURCE'})
    assert FIELD not in f.persistence.get(job.id)
    finish(f,job)


def test_original_workbench_style_request_remains_unbound(keyed):
    from app.services.creation_workbench_service import CreationWorkbenchService, WorkbenchRecordIn
    from app.services.v1_capability_service import V1CapabilityService
    f=keyed
    capabilities=V1CapabilityService(f.root,f.novels,f.chapters,None)
    workbench=CreationWorkbenchService(capabilities,f.chapters,f.novels)
    scope=workbench.local_scope(f.chapter['novel_id'])
    row=workbench.save_record(f.chapter['novel_id'],scope,'local-author',
        WorkbenchRecordIn(kind='STYLE',title='Original style',instructions='Use short sentences'))
    workbench.transition_record(f.chapter['novel_id'],scope,'local-author',row['id'],'approve',row['version'])
    f.monkeypatch.setattr(api,'creation_workbench_service',workbench)
    _,job=queued(f,style_profile_id=row['id'])
    assert FIELD not in f.persistence.get(job.id) and job.creation_records
    finish(f,job)


def test_unsupported_legacy_adapter_family_remains_unbound(keyed):
    f=keyed
    class LegacyStandin(MockProvider):
        def _text(self,prompt): return DRAFT
    f.runtime.providers['ollama']=LegacyStandin(delay_ms=0)
    f.runtime._sync_model('ollama','legacy-model')
    _,job=queued(f,provider_id='ollama',model_id='legacy-model')
    assert FIELD not in f.persistence.get(job.id)
    finish(f,job)
    assert job.provider=='ollama' and job.output==DRAFT


def test_variants_remain_unbound_even_with_request_key(keyed):
    f=keyed
    response=f.client.post('/api/generate/continue/variants',json={**f.payload,'count':2},
        headers={'Idempotency-Key':'not-an-activation-route'})
    assert response.status_code==202,response.text
    result=response.json()
    assert result['count']==2
    jobs=[f.manager.jobs[row['job_id']] for row in result['variants']]
    assert all(FIELD not in f.persistence.get(job.id) for job in jobs)
    f.release.set()
    import time
    deadline=time.monotonic()+10
    while any(job.status not in f.manager.terminal for job in jobs) and time.monotonic()<deadline:
        time.sleep(.01)
    assert all(job.status=='COMPLETED' for job in jobs)
    assert f.counts['worker']==f.counts['provider']==2


def use_default_file_keyed_mode(f):
    """Omit the opt-in field, exercising the product default rather than a stub."""
    from dataclasses import fields
    import app.config as config_module
    import app.main as main_module
    values={item.name:getattr(f.config,item.name) for item in fields(f.config)
            if item.name!='enable_experimental_file_keyed_generation'}
    default_config=Settings(**values)
    assert default_config.enable_experimental_file_keyed_generation is False
    assert default_config.mock_provider and not default_config.enable_packaged_runtime
    for module in (api,jobs_module,main_module,config_module):
        f.monkeypatch.setattr(module,'settings',default_config)
    f.config=default_config


@pytest.mark.parametrize('operation',['continue','rewrite'])
def test_default_off_local_only_keyed_generation_retains_original_mock_path(keyed,operation):
    f=keyed
    use_default_file_keyed_mode(f)
    result,job=queued(f,operation=operation)
    assert job.profile=='LOCAL_ONLY'
    assert FIELD not in f.persistence.get(job.id)
    assert job._ordinary_execution_capability is None
    row=finish(f,job)
    assert row['output']==DRAFT and FIELD not in row
    assert f.counts['worker']==f.counts['adapter']==f.counts['provider']==1
    replay=post(f,operation=operation)
    assert replay.status_code==202 and replay.json()==result
    assert f.counts['worker']==1


def test_default_off_local_only_keyed_cancel_and_retry_remain_available(keyed):
    f=keyed
    use_default_file_keyed_mode(f)
    _,job=queued(f)
    cancelled=f.client.post(f'/api/generation/{job.id}/cancel')
    assert cancelled.status_code==200,cancelled.text
    assert cancelled.json()['status']=='CANCELLED' and job.cancelled.is_set()
    assert f.persistence.get(job.id)['status']=='CANCELLED'
    assert FIELD not in f.persistence.get(job.id)
    f.release.set(); assert f.finished.wait(10)
    assert f.counts['provider']==0
    f.finished.clear(); f.entered.clear(); f.release.clear()
    response=f.client.post(f'/api/generation/{job.id}/retry')
    assert response.status_code==202,response.text
    result=response.json()
    assert result['retry_of']==job.id and result['job_id']!=job.id
    assert f.entered.wait(5)
    retried=f.manager.jobs[result['job_id']]
    assert retried.profile=='LOCAL_ONLY' and FIELD not in f.persistence.get(retried.id)
    assert retried._ordinary_execution_capability is None
    finish(f,retried)
    assert f.counts['worker']==2 and f.counts['provider']==f.counts['adapter']==1
    assert f.persistence.get(job.id)['status']=='CANCELLED'


def test_default_off_failed_actual_mock_request_can_be_retried(keyed):
    from app.providers import ProviderError
    f=keyed
    use_default_file_keyed_mode(f)
    provider=f.runtime.providers['mock']
    def fail(_): raise ProviderError('Controlled original Mock failure')
    f.monkeypatch.setattr(provider,'_text',fail)
    _,job=queued(f)
    f.release.set(); assert f.finished.wait(10)
    assert job.status=='FAILED' and f.persistence.get(job.id)['status']=='FAILED'
    assert FIELD not in f.persistence.get(job.id)
    assert f.counts['provider']==1
    f.monkeypatch.setattr(provider,'_text',lambda _:DRAFT)
    f.finished.clear(); f.entered.clear(); f.release.clear()
    response=f.client.post(f'/api/generation/{job.id}/retry')
    assert response.status_code==202,response.text
    assert response.json()['retry_of']==job.id
    assert f.entered.wait(5)
    retried=f.manager.jobs[response.json()['job_id']]
    assert retried.profile=='LOCAL_ONLY' and FIELD not in f.persistence.get(retried.id)
    finish(f,retried)
    assert f.counts['worker']==f.counts['provider']==f.counts['adapter']==2
    assert f.persistence.get(job.id)['status']=='FAILED'


def test_switch_off_keeps_issued_bound_grant_and_new_requests_unbound(keyed):
    f=keyed
    result,job=queued(f)
    binding=deepcopy(f.persistence.get(job.id)[FIELD])
    use_default_file_keyed_mode(f)
    replay=post(f)
    assert replay.status_code==202 and replay.json()==result
    row=finish(f,job)
    assert row[FIELD]==binding and row['output']==DRAFT
    assert f.counts['provider']==1
    before=f.bundle.generations._job_path(job.id).read_bytes()
    for endpoint in ('retry','cancel'):
        response=f.client.post(f'/api/generation/{job.id}/{endpoint}')
        assert response.status_code==409,response.text
        assert response.json()['detail']['code']=='GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED'
    cold=f.reopen()
    restored=cold.get(job.id)
    assert restored.ordinary_project_binding==binding
    assert restored._ordinary_execution_capability is None
    with pytest.raises(Exception): cold.start_prepared(restored)
    with pytest.raises(Exception): cold._run(restored)
    with pytest.raises(Exception): f.original_run(copy(job))
    assert f.bundle.generations._job_path(job.id).read_bytes()==before
    f.finished.clear(); f.entered.clear(); f.release.clear()
    _,new_job=queued(f,key='new-request-after-switch-off')
    assert new_job.id!=job.id and FIELD not in f.persistence.get(new_job.id)
    assert new_job._ordinary_execution_capability is None
    finish(f,new_job)
    assert f.counts['worker']==f.counts['provider']==2
    assert f.persistence.get(job.id)[FIELD]==binding


def test_switch_off_never_restarts_cold_bound_queued_record(keyed):
    f=keyed
    _,job=queued(f)
    binding=deepcopy(f.persistence.get(job.id)[FIELD])
    use_default_file_keyed_mode(f)
    cold=f.reopen()
    restored=cold.get(job.id)
    assert restored.status=='FAILED'
    assert restored._ordinary_execution_capability is None
    assert f.persistence.get(job.id)[FIELD]==binding
    before=f.bundle.generations._job_path(job.id).read_bytes()
    with pytest.raises(Exception): cold.start_prepared(restored)
    with pytest.raises(Exception): cold._run(restored)
    f.monkeypatch.setattr(api,'jobs',cold)
    for endpoint in ('retry','cancel'):
        response=f.client.post(f'/api/generation/{job.id}/{endpoint}')
        assert response.status_code==409,response.text
        assert response.json()['detail']['code']=='GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED'
    assert f.bundle.generations._job_path(job.id).read_bytes()==before
    f.release.set(); assert f.finished.wait(10)
    assert f.counts['worker']==1 and f.counts['provider']==0
    assert f.persistence.get(job.id)[FIELD]==binding


@pytest.mark.parametrize('configured,expected',[(None,'False'),('true','True')])
def test_file_keyed_switch_default_and_environment_are_fresh_imports(tmp_path,configured,expected):
    from pathlib import Path
    import subprocess
    import sys
    root=Path(__file__).resolve().parents[1]
    # Minimal explicit environment: no inherited credentials, API keys or DB URL.
    environment={'PYTHONPATH':str(root),'PROJECT_ROOT':str(root),'HOME':str(tmp_path),
        'NOVEL_DATA_PATH':str(tmp_path/'data'),'STORAGE_BACKEND':'file',
        'MOCK_PROVIDER':'true','ENABLE_PACKAGED_RUNTIME':'false','ENABLE_CLOUD':'false',
        'PYTHONDONTWRITEBYTECODE':'1'}
    if configured is not None:
        environment['ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION']=configured
    else:
        assert 'ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION' not in environment
    result=subprocess.run([sys.executable,'-c',
        'from app.config import settings; print(settings.enable_experimental_file_keyed_generation)'],
        cwd=root,env=environment,capture_output=True,text=True,check=True,timeout=15)
    assert result.stdout.strip()==expected
