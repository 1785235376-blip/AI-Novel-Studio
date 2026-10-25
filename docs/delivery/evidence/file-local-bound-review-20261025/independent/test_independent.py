"""Independent runtime-only review probes; original File owners, Mock only."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4
import pytest
from app import jobs as jobs_module
from app.agents import AgentRegistry, AgentRunner
from app.jobs import JobManager
from app.lore.memory_agent import MemoryAgentRunner
from app.services import GenerationService, CanonService, ChapterService
from app.services.generation_project_binding import FIELD, IDENTITY_FIELDS
from app.runtime_events import runtime_events
from test_passive_generation_manager_binding import source, _record, _replace_owner
from test_memory_agent_contract import Runtime as MemoryRuntime, memory_settings

@pytest.fixture
def ready(source, memory_settings, monkeypatch):
    # Generate a genuine original Mock draft, then construct a new internal bound
    # record from it. No API capture/admission or historical record upgrade.
    manager = source.manager
    job = manager.create('rewrite', {'novel_id':source.chapter['novel_id'], 'chapter_id':source.chapter['id'],
        'source':source.chapter['content'], 'instruction':'Continue locally', 'profile':'LOCAL_ONLY',
        'provider_id':'mock', 'model_id':'mock-writer'})
    assert source.finished.wait(10)
    assert job.status == 'COMPLETED', (job.status,job.error)
    row = job.record(); row['id'] = str(uuid4()); row['experimental_origin'] = None
    row[FIELD] = dict(schema_version=1, project_incarnation=source.incarnation,
        job_id=row['id'], project_id=row['novel_id'], **{key:deepcopy(row[key]) for key in IDENTITY_FIELDS})
    source.persistence.save(row)
    output={'proposals':[{'proposal_type':'EVENT','payload':{'title':'Local event','description':'Local review'},
        'confidence':.9,'evidence':[{'chapter_id':row['chapter_id'],'chapter_version':source.chapter['version']+1,
        'excerpt':row['output'][:20], 'locator':{'kind':'DOCUMENT_RANGE','from':1,'to':21}}]}]}
    memory=MemoryAgentRunner(source.bundle.novels,source.bundle.chapters,
        source.contexts.lore if hasattr(source.contexts,'lore') else __import__('app.services',fromlist=['LoreService']).LoreService(source.bundle.lore),
        source.persistence,AgentRunner(AgentRegistry()),MemoryRuntime(json.dumps(output)))
    def reopen():
        return JobManager(generations=source.persistence, chapters=source.chapters, contexts=source.contexts,
            canon=source.canon,memory_extractor=memory,snapshot_required=False)
    finished=Event(); original=memory._quiet_extract
    def quiet(*args, **kwargs):
        try:return original(*args, **kwargs)
        finally:finished.set()
    monkeypatch.setattr(memory,'_quiet_extract',quiet)
    cold=reopen(); restored=cold.get(row['id'])
    yield SimpleNamespace(s=source,manager=cold,job=restored,memory=memory,reopen=reopen,memory_finished=finished)
    if any('memory_project_binding' in x for x in source.bundle.generations.load_all()):assert finished.wait(10)

def files(root):
    return {str(p.relative_to(root)):p.read_bytes() for p in Path(root).rglob('*') if p.is_file() and '.workspace-mutation-locks' not in str(p)}

def test_genuine_cold_bound_accept_all_effects(ready):
    r=ready; result=r.manager.accept(r.job.id)
    assert r.job.status=='ACCEPTED'
    assert result['chapter']['content'].strip()==r.job.output.strip()
    assert len(r.s.canon.list_pending(r.job.novel_id))==1
    assert (r.s.root/'novels'/r.job.novel_id/'summaries/index.json').exists()
    import time
    deadline=time.monotonic()+10
    while time.monotonic()<deadline:
        memory_rows=[x for x in r.s.bundle.generations.load_all() if 'memory_project_binding' in x]
        if memory_rows and memory_rows[0]['status'] in {'COMPLETED','FAILED'}:break
        time.sleep(.02)
    assert len(memory_rows)==1
    assert memory_rows[0]['status']=='COMPLETED',memory_rows
    assert len(r.s.bundle.lore.list_proposals(r.job.novel_id))==1
    assert len(r.s.bundle.lore.list_evidence(r.job.novel_id))==1
    with pytest.raises(Exception):r.reopen().accept(r.job.id)

def test_cold_reject(ready):
    r=ready; before=files(r.s.root/'novels')
    assert r.manager.reject(r.job.id).status=='REJECTED'
    assert files(r.s.root/'novels')==before
    assert not r.memory.runtime.provider.calls

@pytest.mark.parametrize('stage',['before_lock','before_chapter','between_summary_canon'])
def test_reentrant_replacement_never_writes_new_owner(ready,monkeypatch,stage):
    r=ready; replacement={}; seen=[]
    def replace():
        _replace_owner(r.s); replacement.update(files(r.s.root/'novels'));seen.append(True)
    if stage=='before_lock':
        import app.repositories.file.mutation_coordinator as module
        original=module.workspace_mutation
        @contextmanager
        def wrapped(root,key):
            if key==f'generation-accept:{r.job.id}' and not seen:replace()
            with original(root,key):yield
        monkeypatch.setattr(module,'workspace_mutation',wrapped)
    else:
        target,name=(r.s.chapters,'save') if stage=='before_chapter' else (r.s.canon,'save_pending')
        original=getattr(target,name)
        def wrapped(*args,**kwargs):
            if not seen:replace()
            return original(*args,**kwargs)
        monkeypatch.setattr(target,name,wrapped)
    with pytest.raises(Exception):r.manager.accept(r.job.id)
    assert seen and files(r.s.root/'novels')==replacement
    assert not r.memory.runtime.provider.calls

@pytest.mark.parametrize('port',['chapters','canon','memory','generation'])
def test_rotated_facade_denied_without_writes(ready,port):
    r=ready
    if port=='chapters':r.manager.chapters=ChapterService(r.s.bundle.chapters)
    elif port=='canon':r.manager.canon=CanonService(r.s.bundle.canon)
    elif port=='generation':r.manager.persistence=GenerationService(r.s.bundle.generations)
    else:r.manager.memory_extractor=MemoryAgentRunner(r.memory.novels,r.memory.chapters,r.memory.lore,r.memory.generations,r.memory.agent_runner,r.memory.runtime)
    before=files(r.s.root)
    with pytest.raises(Exception):r.manager.accept(r.job.id)
    assert files(r.s.root)==before

@pytest.mark.parametrize('status',['ACCEPTING','ACCEPTANCE_UNCERTAIN'])
def test_failed_claim_never_replays(ready,status):
    r=ready; r.job.status=status;r.manager._persist(r.job)
    before=files(r.s.root)
    with pytest.raises(Exception):r.reopen().accept(r.job.id)
    assert files(r.s.root)==before

@pytest.mark.parametrize('seam',['chapter','canon','generation'])
def test_concurrent_delete_waits_until_original_synchronous_effects_finish(ready,monkeypatch,seam):
    r=ready;at=Event();release=Event();deleting=Event();deleted=Event();errors=[];results=[]
    target,name=(r.s.chapters,'save') if seam=='chapter' else ((r.s.canon,'save_pending') if seam=='canon' else (r.s.bundle.generations,'save'))
    original=getattr(target,name)
    def wrapped(*args,**kwargs):
        if seam!='generation' or args[0].get('status')=='ACCEPTED':
            at.set();assert release.wait(10)
        return original(*args,**kwargs)
    monkeypatch.setattr(target,name,wrapped)
    def accepting():
        try:results.append(r.manager.accept(r.job.id))
        except BaseException as e:errors.append(e)
    def deleting_owner():
        deleting.set()
        try:_replace_owner(r.s)
        except BaseException as e:errors.append(e)
        finally:deleted.set()
    t=Thread(target=accepting);t.start();assert at.wait(10)
    d=Thread(target=deleting_owner);d.start();assert deleting.wait(10)
    assert not deleted.wait(.15), 'Deletion escaped original synchronous owner lease'
    release.set();t.join(10);d.join(10)
    assert not t.is_alive() and not d.is_alive() and not errors,errors
    assert len(results)==1
    assert r.s.owner.incarnation(r.job.novel_id)!=r.s.incarnation
    assert len(r.s.chapters.list(r.job.novel_id))==1
    assert not r.s.canon.list_pending(r.job.novel_id)


def test_context_not_usable_other_thread_or_held_callback_and_events_unlocked(ready,monkeypatch):
    r=ready;contexts=[];errors=[];observed=[]
    original=r.manager._accept_claimed
    def wrapped(*args,**kwargs):
        ctx=kwargs['_review'];contexts.append(ctx)
        def use_context():
            try:ctx.check()
            except Exception as e:errors.append(e)
        t=Thread(target=use_context);t.start();t.join(2);assert not t.is_alive()
        return original(*args,**kwargs)
    monkeypatch.setattr(r.manager,'_accept_claimed',wrapped)
    def observer(change):
        if change.project_id!=r.job.novel_id:return
        import app.repositories.file.mutation_coordinator as coordinator
        assert not getattr(coordinator._thread_state,'depths',{})
        observed.append(change)
        assert contexts and not contexts[0].active
    unsub=runtime_events.subscribe(observer)
    try:r.manager.accept(r.job.id)
    finally:unsub()
    assert errors and observed
    assert r.memory_finished.wait(10)
    before=files(r.s.root)
    with pytest.raises(Exception):contexts[0].chapters.save_summary(r.job.novel_id,1,'FORBIDDEN')
    assert files(r.s.root)==before

@pytest.mark.parametrize('mutation',['backend_data','backend_novels','generation_root','memory_lore','scope'])
def test_physical_port_rotation_and_scope_denied(ready,tmp_path,mutation):
    r=ready
    if mutation=='backend_data':r.s.bundle.chapters.backend.data=tmp_path/'different'
    elif mutation=='backend_novels':r.s.bundle.chapters.backend.novels=tmp_path/'different'
    elif mutation=='generation_root':r.s.bundle.generations.root=tmp_path/'different'
    elif mutation=='memory_lore':
        from app.services import LoreService
        r.memory.lore=LoreService(r.s.bundle.lore)
    else:r.job.scope={'kind':'PROJECT','project_id':r.job.novel_id,'workspace_id':'w'}
    before=files(r.s.root)
    with pytest.raises(Exception):r.manager.accept(r.job.id)
    assert files(r.s.root)==before

@pytest.mark.parametrize('allow',[True,False])
def test_authorization_runs_before_any_owner_or_review_lock(ready,allow):
    r=ready;checks=[]
    def authorization():
        import app.repositories.file.mutation_coordinator as coordinator
        checks.append(dict(getattr(coordinator._thread_state,'depths',{})))
        if not allow:raise PermissionError('Review denied')
    r.job.request_authorization=authorization
    before=files(r.s.root)
    if allow:assert r.manager.reject(r.job.id).status=='REJECTED'
    else:
        with pytest.raises(jobs_module._OrdinaryRequestAuthorizationFailed):r.manager.reject(r.job.id)
        assert files(r.s.root)==before
    assert checks and all(not locks for locks in checks)


def test_failed_original_canon_port_leaves_nonreplayable_receipt(ready,monkeypatch):
    r=ready
    def failing(*args,**kwargs):raise OSError('Independent simulated Canon I/O failure')
    monkeypatch.setattr(r.s.canon,'save_pending',failing)
    with pytest.raises(OSError):r.manager.accept(r.job.id)
    assert r.s.persistence.get(r.job.id)['status'] in {'ACCEPTING','ACCEPTANCE_UNCERTAIN'}
    before=files(r.s.root)
    with pytest.raises(Exception):r.reopen().accept(r.job.id)
    assert files(r.s.root)==before


def test_stale_base_version_has_zero_review_writes(ready):
    r=ready
    r.s.chapters.save(r.job.chapter_id,{'content':'An intervening human edit','version':r.s.chapter['version']})
    before=files(r.s.root)
    from app.repositories.chapter_repository import VersionConflict
    with pytest.raises(VersionConflict) as conflict:r.manager.accept(r.job.id)
    assert conflict.value.expected_version==r.s.chapter['version']
    assert conflict.value.actual_version==r.s.chapter['version']+1
    assert files(r.s.root)==before


def test_partial_committed_changes_publish_after_failure_and_unlock(ready,monkeypatch):
    r=ready;seen=[];locks=[]
    def fail(*args,**kwargs):raise OSError('Canon interrupted after chapter+summary')
    monkeypatch.setattr(r.s.canon,'save_pending',fail)
    def observer(change):
        if change.project_id==r.job.novel_id:
            import app.repositories.file.mutation_coordinator as coordinator
            seen.append(change);locks.append(dict(getattr(coordinator._thread_state,'depths',{})))
    unsub=runtime_events.subscribe(observer)
    try:
        with pytest.raises(OSError):r.manager.accept(r.job.id)
    finally:unsub()
    assert r.job.status=='ACCEPTANCE_UNCERTAIN'
    assert r.s.chapters.get(r.job.chapter_id)['version']==r.s.chapter['version']+1
    assert {'CHAPTER','TASK'} <= {x.module for x in seen}
    assert all(not x for x in locks),locks
    assert not r.memory.runtime.provider.calls

@pytest.mark.parametrize('mutation',['memory_lore','canon'])
def test_rotation_after_chapter_blocks_next_original_effect(ready,monkeypatch,mutation):
    r=ready;original=r.s.chapters.save
    def rotate(*args,**kwargs):
        result=original(*args,**kwargs)
        if mutation=='canon':r.manager.canon=CanonService(r.s.bundle.canon)
        else:
            from app.services import LoreService
            r.memory.lore=LoreService(r.s.bundle.lore)
        return result
    monkeypatch.setattr(r.s.chapters,'save',rotate)
    with pytest.raises(Exception):r.manager.accept(r.job.id)
    assert not r.s.canon.list_pending(r.job.novel_id)
    assert r.s.persistence.get(r.job.id)['status']=='ACCEPTING'
    assert r.job.status=='ACCEPTANCE_UNCERTAIN'
    assert not r.memory.runtime.provider.calls

@pytest.mark.parametrize('operation',['accept','reject'])
def test_existing_http_review_for_internal_bound_draft(ready,monkeypatch,operation):
    from app import api
    r=ready;monkeypatch.setattr(api,'jobs',r.manager)
    response=r.s.client.post(f'/api/generation/{r.job.id}/{operation}')
    assert response.status_code==200,response.text
    assert r.job.status==('ACCEPTED' if operation=='accept' else 'REJECTED')
    assert FIELD not in response.json()

@pytest.mark.parametrize('operation',['cancel','start_prepared','_run'])
def test_bound_writer_and_cancel_gates_stay_closed(ready,operation):
    r=ready;before=files(r.s.root)
    with pytest.raises(Exception):
        getattr(r.manager,operation)(r.job.id if operation=='cancel' else r.job)
    assert files(r.s.root)==before
    assert not r.job.cancelled.is_set()


def test_stale_bound_restore_snapshot_uses_project_before_review_lock(ready,monkeypatch):
    r=ready;original_load=r.s.persistence.load_all;original_rows=original_load()
    stale=deepcopy(original_rows)
    for row in stale:
        if row['id']==r.job.id:row['status']='QUEUED'
    monkeypatch.setattr(r.s.persistence,'load_all',lambda:deepcopy(stale))
    import app.repositories.file.mutation_coordinator as coordinator
    original=coordinator.workspace_mutation;observed=[]
    @contextmanager
    def locking(root,key):
        if key==f'generation-accept:{r.job.id}':
            depths=dict(getattr(coordinator._thread_state,'depths',{}))
            observed.append(depths)
        with original(root,key):yield
    monkeypatch.setattr(coordinator,'workspace_mutation',locking)
    before=files(r.s.root)
    fresh=r.reopen()
    assert fresh.get(r.job.id).status=='COMPLETED'
    assert observed and all(any('project-lifecycle:' in key[1] for key in locks) for locks in observed),observed
    assert files(r.s.root)==before
