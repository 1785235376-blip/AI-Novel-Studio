"""Manual review only: internal bound records, original File mutation owners."""
from copy import deepcopy
import json
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.jobs import JobManager
from app.lore.memory_agent import MemoryAgentRunner
from app.agents import AgentRunner, AgentRegistry
from app.services import GenerationService
from app.services.generation_project_binding import FIELD
from test_memory_agent_contract import Runtime, memory_settings
from test_passive_generation_manager_binding import source, _record, _replace_owner
from test_bound_review_port_blockers import project_bytes

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def bound(source, memory_settings, monkeypatch):
    from app.services import LoreService
    memory = MemoryAgentRunner(source.bundle.novels, source.bundle.chapters, LoreService(source.bundle.lore),
        GenerationService(source.bundle.generations), AgentRunner(AgentRegistry()), Runtime('{"proposals":[]}'))
    row = _record(source)
    source.persistence.save(row)
    def reopen():
        return JobManager(generations=source.persistence, chapters=source.chapters, contexts=source.contexts,
            canon=source.canon, memory_extractor=memory, snapshot_required=False)
    manager = reopen()
    finished = Event()
    original = memory._quiet_extract
    def quiet(*args, **kwargs):
        try: return original(*args, **kwargs)
        finally: finished.set()
    monkeypatch.setattr(memory, '_quiet_extract', quiet)
    yield SimpleNamespace(**vars(source), row=row, review_manager=manager, memory=memory,
                          memory_finished=finished, reopen_bound=reopen)
    # Only wait if the original memory worker was actually enqueued.
    if any(x.get('operation') == 'MEMORY_EXTRACTION' for x in source.bundle.generations.load_all()):
        assert finished.wait(10)


def test_cold_bound_accept_full_original_chain(bound):
    manager = bound.review_manager
    job = manager.get(bound.row['id'])
    result = manager.accept(job.id)
    assert job.status == 'ACCEPTED' and manager.persistence.get(job.id)[FIELD] == bound.row[FIELD]
    saved = bound.chapters.get(result['chapter']['id'])
    assert saved['id'] != job.chapter_id and job.output in saved['content']
    summaries = json.loads((bound.root/'novels'/job.novel_id/'summaries/index.json').read_text())
    assert summaries[-1]['summary'] == job.output[:240]
    assert bound.canon.list_pending(job.novel_id)[0]['id'] == result['pending_canon']['id']
    assert bound.memory_finished.wait(10)
    memory = [row for row in bound.bundle.generations.load_all() if row.get('operation') == 'MEMORY_EXTRACTION']
    assert len(memory) == 1 and memory[0]['status'] == 'COMPLETED'
    assert memory[0]['memory_project_binding']['project_incarnation'] == bound.incarnation
    assert memory[0]['chapter_id'] == saved['id']
    assert len(bound.memory.runtime.provider.calls) == 1
    with pytest.raises(ValueError): manager.accept(job.id)


def test_cold_bound_reject_changes_only_original_receipt(bound):
    before = project_bytes(bound.root, bound.row['novel_id'])
    job = bound.review_manager.reject(bound.row['id'])
    assert job.status == 'REJECTED'
    assert project_bytes(bound.root, job.novel_id) == before
    assert bound.persistence.get(job.id)[FIELD] == bound.row[FIELD]
    assert not bound.memory_finished.is_set()


@pytest.mark.parametrize('operation', ['accept', 'reject'])
def test_replacement_after_preliminary_read_cannot_be_adopted(bound, monkeypatch, operation):
    manager = bound.review_manager
    original = manager.get
    replacement = {}
    def get(jid):
        job = original(jid)
        _replace_owner(bound)
        replacement.update(project_bytes(bound.root, job.novel_id))
        return job
    monkeypatch.setattr(manager, 'get', get)
    old = bound.bundle.generations._job_path(bound.row['id']).read_bytes()
    with pytest.raises((KeyError, ValueError, HTTPException)):
        getattr(manager, operation)(bound.row['id'])
    assert project_bytes(bound.root, bound.row['novel_id']) == replacement
    assert bound.bundle.generations._job_path(bound.row['id']).read_bytes() == old


@pytest.mark.parametrize('stage', ['chapter', 'summary', 'canon'])
def test_real_delete_waits_across_original_review_effects(bound, monkeypatch, stage):
    at, release, deleting, deleted = Event(), Event(), Event(), Event()
    target, name = {'chapter':(bound.chapters,'create'), 'summary':(bound.chapters,'save_summary'),
                    'canon':(bound.canon,'save_pending')}[stage]
    original = getattr(target, name)
    def gate(*args, **kwargs):
        at.set(); assert release.wait(5)
        return original(*args, **kwargs)
    monkeypatch.setattr(target, name, gate)
    # Capture the gate as an actual original facade method before review starts.
    errors=[]; result=[]
    def accept():
        try: result.append(bound.review_manager.accept(bound.row['id']))
        except BaseException as exc: errors.append(exc)
    def replace():
        deleting.set()
        try:_replace_owner(bound)
        except BaseException as exc: errors.append(exc)
        finally:deleted.set()
    worker=Thread(target=accept); worker.start(); assert at.wait(5)
    deletion=Thread(target=replace); deletion.start()
    try:
        assert deleting.wait(2) and not deleted.wait(.1)
    finally:release.set()
    worker.join(10); deletion.join(10)
    assert not worker.is_alive() and not deletion.is_alive() and not errors and result
    assert deleted.is_set()
    assert len(bound.chapters.list(bound.row['novel_id'])) == 1
    assert bound.canon.list_pending(bound.row['novel_id']) == []
    assert not list((bound.root/'novels'/bound.row['novel_id']/'lore'/'proposals').glob('*.json'))


@pytest.mark.parametrize('stage', ['chapter', 'summary'])
def test_port_rotation_cannot_redirect_later_effects(bound, monkeypatch, stage):
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import CanonService
    other = create_repository_bundle(Settings(storage_backend='file',novel_data=bound.root/'other'),bound.root/'other')
    original = bound.chapters.create if stage == 'chapter' else bound.chapters.save_summary
    def rotate(*args, **kwargs):
        result = original(*args, **kwargs)
        bound.review_manager.canon = CanonService(other.canon)
        return result
    monkeypatch.setattr(bound.chapters, 'create' if stage == 'chapter' else 'save_summary', rotate)
    before = {str(p):p.read_bytes() for p in (bound.root/'other').rglob('*') if p.is_file()}
    with pytest.raises(ValueError): bound.review_manager.accept(bound.row['id'])
    assert before == {str(p):p.read_bytes() for p in (bound.root/'other').rglob('*') if p.is_file()}
    assert bound.persistence.get(bound.row['id'])['status'] == 'ACCEPTING'
    assert bound.review_manager.jobs[bound.row['id']].status == 'ACCEPTANCE_UNCERTAIN'


@pytest.mark.parametrize('operation', ['accept', 'reject'])
def test_missing_durable_row_never_falls_back_to_cache(bound, monkeypatch, operation):
    manager=bound.review_manager
    original=manager.get
    before=project_bytes(bound.root,bound.row['novel_id'])
    def get(jid):
        job=original(jid)
        bound.bundle.generations._job_path(jid).unlink()
        return job
    monkeypatch.setattr(manager,'get',get)
    with pytest.raises((KeyError, HTTPException)):getattr(manager,operation)(bound.row['id'])
    assert project_bytes(bound.root,bound.row['novel_id']) == before


def test_helper_context_expires_and_cannot_cross_threads(bound, monkeypatch):
    manager=bound.review_manager
    original=manager._accept_claimed; held=[]; denied=[]
    def accept(*args, **kwargs):
        review=kwargs['_review']; held.append(review)
        def misuse():
            try: review.persist()
            except Exception as exc:denied.append(exc)
        thread=Thread(target=misuse);thread.start();thread.join(2)
        assert not thread.is_alive() and denied
        return original(*args, **kwargs)
    monkeypatch.setattr(manager,'_accept_claimed',accept)
    manager.accept(bound.row['id'])
    with pytest.raises(ValueError,match='EXPIRED'):held[0].persist()
    job=manager.get(bound.row['id'])
    with pytest.raises(ValueError,match='EXPIRED'):
        original(job, bound.chapter, bound.chapter['version'], _review=held[0])
    with pytest.raises(HTTPException):original(job,bound.chapter,bound.chapter['version'])


@pytest.mark.parametrize('stage', ['chapter', 'summary', 'canon'])
def test_reentrant_replacement_is_checked_in_final_original_port(bound, monkeypatch, stage):
    target,name={'chapter':(bound.chapters,'create'),'summary':(bound.chapters,'save_summary'),
                 'canon':(bound.canon,'save_pending')}[stage]
    original=getattr(target,name); replacement={}; changed=[]
    def replace_then_write(*args, **kwargs):
        if not changed:
            changed.append(True)
            _replace_owner(bound)
            replacement.update(project_bytes(bound.root,bound.row['novel_id']))
        return original(*args,**kwargs)
    monkeypatch.setattr(target,name,replace_then_write)
    with pytest.raises((ValueError,FileNotFoundError)):
        bound.review_manager.accept(bound.row['id'])
    assert changed and project_bytes(bound.root,bound.row['novel_id']) == replacement
    assert bound.review_manager.jobs[bound.row['id']].status == 'ACCEPTANCE_UNCERTAIN'
    assert not bound.memory_finished.is_set()


def test_original_memory_chain_creates_evidence_and_proposal(bound):
    cid=bound.row['novel_id']+':2'
    bound.memory.runtime.provider.text=json.dumps({'proposals':[{'proposal_type':'EVENT',
        'payload':{'description':'RETAINED_DRAFT'},'confidence':.9,
        'evidence':[{'chapter_id':cid,'chapter_version':1,'excerpt':'RETAINED_DRAFT',
                     'locator':{'kind':'DOCUMENT_RANGE','from':0,'to':14}}]}]})
    result=bound.review_manager.accept(bound.row['id'])
    assert result['chapter']['id'] == cid
    assert bound.memory_finished.wait(10)
    proposals=bound.bundle.lore.list_proposals(bound.row['novel_id'])
    assert len(proposals)==1 and proposals[0]['source_chapter_id']==cid
    relations=bound.bundle.lore.list_proposal_evidence(proposals[0]['id'])
    assert len(relations)==1
    assert bound.bundle.lore.get_evidence(relations[0]['evidence_id'])['excerpt']=='RETAINED_DRAFT'
    memory=bound.persistence.get(proposals[0]['generation_job_id'])
    assert memory['status']=='COMPLETED' and memory['memory_project_binding']['project_incarnation']==bound.incarnation


@pytest.mark.parametrize('failure', ['claim', 'chapter', 'canon', 'terminal'])
def test_original_persistence_failures_never_replay(bound, monkeypatch, failure):
    manager=bound.review_manager; jid=bound.row['id']
    if failure in ('claim','terminal'):
        original=bound.bundle.generations.save
        def save(row,**kwargs):
            if row.get('status')==('ACCEPTING' if failure=='claim' else 'ACCEPTED'):
                raise OSError('synthetic persistence failure')
            return original(row,**kwargs)
        monkeypatch.setattr(bound.bundle.generations,'save',save)
    elif failure=='chapter':
        def create(*args,**kwargs):raise OSError('synthetic chapter failure')
        monkeypatch.setattr(bound.chapters,'create',create)
    else:
        def canon(*args,**kwargs):raise OSError('synthetic Canon failure')
        monkeypatch.setattr(bound.canon,'save_pending',canon)
    with pytest.raises(OSError):manager.accept(jid)
    saved=bound.persistence.get(jid)
    if failure=='claim':
        assert saved['status']=='COMPLETED' and len(bound.chapters.list(bound.row['novel_id']))==1
        assert bound.canon.list_pending(bound.row['novel_id'])==[]
    else:
        assert saved['status']=='ACCEPTANCE_UNCERTAIN'
        with pytest.raises(ValueError):bound.reopen_bound().accept(jid)
    assert not bound.memory_finished.is_set()


def test_partial_effect_notifications_flush_after_locks_even_on_failure(bound, monkeypatch):
    from app.runtime_events import runtime_events
    from app.repositories.file.mutation_coordinator import workspace_mutation_lock
    observed=[]
    def observe(change):
        if change.project_id != bound.row['novel_id']:return
        acquired=[]
        def contender():
            lock=workspace_mutation_lock(bound.root,f'project-lifecycle:{(bound.root/"novels"/change.project_id).resolve()}')
            ok=lock.acquire(timeout=.5);acquired.append(ok)
            if ok:lock.release()
        thread=Thread(target=contender);thread.start();thread.join(1)
        observed.append((change.module,acquired==[True]))
    def fail(*args,**kwargs):raise OSError('synthetic Canon failure')
    monkeypatch.setattr(bound.canon,'save_pending',fail)
    unsubscribe=runtime_events.subscribe(observe)
    try:
        with pytest.raises(OSError):bound.review_manager.accept(bound.row['id'])
    finally:unsubscribe()
    assert any(module=='CHAPTER' for module,_ in observed)
    assert any(module=='TASK' for module,_ in observed)
    assert all(released for _,released in observed)
    assert bound.persistence.get(bound.row['id'])['status']=='ACCEPTANCE_UNCERTAIN'


def test_memory_composition_rotation_is_detected_before_accepted(bound, monkeypatch):
    original=bound.chapters.create
    def create(*args,**kwargs):
        result=original(*args,**kwargs)
        bound.memory.lore=SimpleNamespace(repository=bound.bundle.lore)
        return result
    monkeypatch.setattr(bound.chapters,'create',create)
    with pytest.raises(ValueError):bound.review_manager.accept(bound.row['id'])
    assert bound.persistence.get(bound.row['id'])['status']=='ACCEPTING'
    assert bound.review_manager.jobs[bound.row['id']].status=='ACCEPTANCE_UNCERTAIN'
    assert bound.canon.list_pending(bound.row['novel_id'])==[]


def test_original_independent_memory_failure_does_not_undo_acceptance(bound, monkeypatch):
    calls=[]
    def unavailable(*args,**kwargs):
        calls.append(kwargs['project_incarnation'])
        raise OSError('synthetic independent memory queue failure')
    monkeypatch.setattr(bound.memory,'enqueue',unavailable)
    result=bound.review_manager.accept(bound.row['id'])
    assert result['chapter'] and result['pending_canon']
    assert calls==[bound.incarnation]
    assert bound.persistence.get(bound.row['id'])['status']=='ACCEPTED'


@pytest.mark.parametrize('change', ['version', 'unsettled', 'scope', 'callback_authority'])
def test_current_original_review_preconditions(bound, change, monkeypatch):
    jid=bound.row['id']; manager=bound.review_manager
    if change=='version':
        bound.chapters.save(bound.chapter['id'],{'content':'newer','version':bound.chapter['version']})
    elif change=='unsettled':
        row=bound.persistence.get(jid);row.update(dispatch_hooks_required=True,terminal_hook_status='PENDING')
        bound.persistence.save(row)
    elif change=='scope':
        # Caller-supplied collaboration cannot turn this local record into a scoped review.
        pass
    else:
        def refused():raise PermissionError('synthetic revoked local request')
        manager.get(jid).request_authorization=refused
    before=project_bytes(bound.root,bound.row['novel_id'])
    with pytest.raises((ValueError,RuntimeError,HTTPException,PermissionError)):
        manager.accept(jid, actor=object() if change=='scope' else None)
    assert project_bytes(bound.root,bound.row['novel_id'])==before


@pytest.mark.parametrize('operation', ['cancel','start_prepared','_run','_cancel_execution'])
def test_other_bound_mutation_gates_stay_closed_even_with_composed_ports(bound, operation):
    manager=bound.review_manager; job=manager.get(bound.row['id'])
    before=bound.bundle.generations._job_path(job.id).read_bytes()
    with pytest.raises(HTTPException) as exc:
        getattr(manager,operation)(job.id if operation=='cancel' else job)
    assert exc.value.status_code==409 and exc.value.detail['code']=='GENERATION_ORDINARY_MUTATION_NOT_INTEGRATED'
    assert bound.bundle.generations._job_path(job.id).read_bytes()==before
    assert len(bound.chapters.list(job.novel_id))==1


def test_bound_accept_body_is_single_use(bound,monkeypatch):
    manager=bound.review_manager; original=manager._accept_claimed; attempts=[]
    def call(*args,**kwargs):
        result=original(*args,**kwargs)
        with pytest.raises(ValueError,match='ALREADY_CONSUMED'):
            original(*args,**kwargs)
        attempts.append(True)
        return result
    monkeypatch.setattr(manager,'_accept_claimed',call)
    manager.accept(bound.row['id'])
    assert attempts==[True] and len(bound.chapters.list(bound.row['novel_id']))==2


def test_stale_interrupted_restore_never_holds_review_lock_while_waiting_for_owner(bound):
    from app.file_project_lifecycle import project_operation
    from app.repositories.file.mutation_coordinator import workspace_mutation_lock
    row=deepcopy(bound.row);row['status']='QUEUED'
    manager=bound.review_manager
    waiting,entered,finished=Event(),Event(),Event();errors=[]
    def recovery():
        waiting.set()
        try:
            with manager._restore_mutation(row):entered.set()
        except BaseException as exc:errors.append(exc)
        finally:finished.set()
    with project_operation(bound.root,row['novel_id']):
        thread=Thread(target=recovery);thread.start();assert waiting.wait(2)
        assert not entered.wait(.1)
        lock=workspace_mutation_lock(bound.bundle.generations.root,f'generation-accept:{row["id"]}')
        acquired=lock.acquire(timeout=.5)
        try:assert acquired,'restore held review leaf while waiting for original owner'
        finally:
            if acquired:lock.release()
    thread.join(5)
    assert finished.is_set() and entered.is_set() and not errors
