"""Bound original File memory runner; real MockProvider, no external model."""
from copy import deepcopy
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.creative.project_store import CreativeProjectStore
from app.lore.memory_project_binding import FIELD, create_binding, memory_job_binding
from app.repositories.generation_repository import GenerationProjectIdentityError
from test_memory_agent_contract import runner, valid_output, memory_settings
from test_bound_review_port_blockers import replace_memory_owner, project_bytes

pytestmark = pytest.mark.file_backend_only


def setup(tmp_path):
    agent, bundle, nid, cid, version = runner(tmp_path, valid_output())
    owner = CreativeProjectStore(SimpleNamespace(backend='file', root=tmp_path))
    incarnation = owner.incarnation(nid)
    binding = create_binding(nid, cid, version, incarnation)
    return agent, bundle, nid, cid, version, owner, binding


def record(binding):
    return dict(id=binding['job_id'], novel_id=binding['project_id'], chapter_id=binding['chapter_id'],
                operation='MEMORY_EXTRACTION', status='QUEUED', request={'chapter_version': binding['chapter_version']},
                **{FIELD: deepcopy(binding)})


def test_bound_extract_original_owner_positive(tmp_path, memory_settings):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    ids = agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
    assert len(ids) == 1 and len(agent.runtime.provider.calls) == 1
    saved = bundle.generations.get(binding['job_id'])
    assert saved['status'] == 'COMPLETED' and memory_job_binding(saved) == binding
    assert len(bundle.lore.list_proposal_evidence(ids[0])) == 1
    assert len(bundle.lore.list_evidence(nid)) == 1
    assert agent.enqueue(nid, cid, version, project_incarnation=binding['project_incarnation']) == binding['job_id']
    assert len(agent.runtime.provider.calls) == 1


@pytest.mark.parametrize('stage', ['before_enqueue', 'delayed_thread', 'before_dispatch', 'during_inference'])
def test_replacement_has_zero_bound_memory_writes(tmp_path, memory_settings, monkeypatch, stage):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    replacement_bytes = {}
    threads = []
    import app.lore.memory_agent as module

    def replace():
        replace_memory_owner(tmp_path, bundle, nid)
        assert owner.incarnation(nid) != binding['project_incarnation']
        replacement_bytes.update(project_bytes(tmp_path, nid))

    if stage == 'before_enqueue':
        replace()
        with pytest.raises((GenerationProjectIdentityError, FileNotFoundError)):
            agent.enqueue(nid, cid, version, project_incarnation=binding['project_incarnation'])
    elif stage == 'delayed_thread':
        class DelayedThread(Thread):
            def start(self): threads.append(self)
        monkeypatch.setattr(module.threading, 'Thread', DelayedThread)
        agent.enqueue(nid, cid, version, project_incarnation=binding['project_incarnation'])
        queued = bundle.generations._job_path(binding['job_id']).read_bytes()
        replace()
        threads[0].run()
        assert bundle.generations._job_path(binding['job_id']).read_bytes() == queued
    else:
        if stage == 'before_dispatch':
            original = agent.runtime.prepare_text_route
            def prepare(*args):
                result = original(*args)
                replace()
                return result
            monkeypatch.setattr(agent.runtime, 'prepare_text_route', prepare)
        else:
            original = agent.runtime.provider._text
            def text(prompt):
                replace()  # No project lease spans model inference.
                return original(prompt)
            monkeypatch.setattr(agent.runtime.provider, '_text', text)
        with pytest.raises((GenerationProjectIdentityError, FileNotFoundError)):
            agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
    assert project_bytes(tmp_path, nid) == replacement_bytes
    assert len(agent.runtime.provider.calls) == (1 if stage == 'during_inference' else 0)
    with pytest.raises(KeyError): bundle.generations.get(binding['job_id'])


@pytest.mark.parametrize('port', ['evidence', 'proposal', 'relation', 'terminal'])
def test_final_original_lease_excludes_delete_through_every_write(tmp_path, memory_settings, monkeypatch, port):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    at_write, release, deleting, deleted = Event(), Event(), Event(), Event()
    errors = []
    target, name = {'evidence': (bundle.lore, 'create_evidence'),
                    'proposal': (bundle.lore, 'create_proposal'),
                    'relation': (bundle.lore, 'link_evidence'),
                    'terminal': (bundle.generations, 'save')}[port]
    original = getattr(target, name)

    def gated(item, **kwargs):
        if port != 'terminal' or item.get('status') == 'COMPLETED':
            at_write.set()
            assert release.wait(5)
        return original(item, **kwargs)
    monkeypatch.setattr(target, name, gated)

    def extract():
        try: agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
        except BaseException as exc: errors.append(exc)
    def replace():
        deleting.set()
        try: replace_memory_owner(tmp_path, bundle, nid)
        except BaseException as exc: errors.append(exc)
        finally: deleted.set()
    worker = Thread(target=extract); worker.start()
    assert at_write.wait(5)
    deletion = Thread(target=replace); deletion.start()
    try:
        assert deleting.wait(2)
        assert not deleted.wait(.1), 'delete passed original lifecycle lease'
    finally:
        release.set()
    worker.join(5); deletion.join(5)
    assert not worker.is_alive() and not deletion.is_alive() and not errors
    assert deleted.is_set() and owner.incarnation(nid) != binding['project_incarnation']
    assert not list((tmp_path/'novels'/nid/'lore'/'evidence').glob('*.json'))
    assert not list((tmp_path/'novels'/nid/'lore'/'proposals').glob('*.json'))
    with pytest.raises(KeyError): bundle.generations.get(binding['job_id'])


def test_replacement_enqueue_does_not_inherit_old_receipt(tmp_path, memory_settings, monkeypatch):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    bundle.generations.save(record(binding))
    replacement, _, _ = replace_memory_owner(tmp_path, bundle, nid)
    new_identity = owner.incarnation(nid)
    import app.lore.memory_agent as module
    threads = []
    class DelayedThread(Thread):
        def start(self): threads.append(self)
    monkeypatch.setattr(module.threading, 'Thread', DelayedThread)
    new_id = replacement.enqueue(nid, cid, version, project_incarnation=new_identity)
    assert new_id != binding['job_id'] and len(threads) == 1
    assert bundle.generations.get(new_id)[FIELD]['project_incarnation'] == new_identity
    assert bundle.generations._job_path(binding['job_id']).exists()


@pytest.mark.parametrize('change', ['null', 'unknown', 'bool_version', 'wrong_job', 'wrong_operation', 'wrong_chapter', 'wrong_version', 'ordinary_project_binding', 'graph_binding', 'adaptation_binding', 'creative_director_binding', 'director_image_binding', 'research_ocr_binding', 'research_ocr_output_evidence', '_creative_director_terminal_evidence', 'director_image_terminal_v3'])
def test_memory_binding_is_strict_and_disjoint(tmp_path, change):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    row = record(binding)
    if change == 'null': row[FIELD] = None
    elif change == 'unknown': row[FIELD]['extra'] = 1
    elif change == 'bool_version': row[FIELD]['schema_version'] = True
    elif change == 'wrong_job': row['id'] = str(uuid4())
    elif change == 'wrong_operation': row['operation'] = 'continue'
    elif change == 'wrong_chapter': row['chapter_id'] = nid + ':2'
    elif change == 'wrong_version': row['request']['chapter_version'] = True
    else: row[change] = None
    with pytest.raises(GenerationProjectIdentityError): bundle.generations.save(row)
    assert not bundle.generations._job_path(row['id']).exists()


@pytest.mark.parametrize('change', ['drop', 'change', 'upgrade'])
def test_original_memory_binding_is_immutable(tmp_path, change):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    original = record(binding)
    if change == 'upgrade': original.pop(FIELD)
    bundle.generations.save(original)
    before = bundle.generations._job_path(binding['job_id']).read_bytes()
    changed = record(binding)
    if change == 'drop': changed.pop(FIELD)
    if change == 'change': changed[FIELD]['project_incarnation'] = 'file:' + str(uuid4())
    with pytest.raises(GenerationProjectIdentityError): bundle.generations.save(changed)
    assert bundle.generations._job_path(binding['job_id']).read_bytes() == before


@pytest.mark.parametrize('port', ['novels', 'chapters', 'lore', 'generations', 'generation_root', 'chapter_root', 'lore_root', 'novel_root'])
def test_bound_ports_cannot_be_swapped_or_rerooted(tmp_path, memory_settings, monkeypatch, port):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    other, other_bundle, *_ = runner(tmp_path/'other', valid_output())
    if port in ('novels', 'chapters', 'lore', 'generations'):
        setattr(agent, port, getattr(other, port))
    elif port == 'generation_root': monkeypatch.setattr(bundle.generations, 'root', other_bundle.generations.root)
    else:
        target = {'chapter_root': bundle.chapters, 'lore_root': bundle.lore, 'novel_root': bundle.novels}[port]
        monkeypatch.setattr(target.backend, 'data', tmp_path/'other')
    before = {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    with pytest.raises(GenerationProjectIdentityError, match='STORE_MISMATCH'):
        agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
    assert {str(p.relative_to(tmp_path)):p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()} == before


def test_missing_marker_is_not_provisioned(tmp_path, memory_settings):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    marker = tmp_path/'novels'/nid/'creative_project_v2.json'
    marker.unlink()
    with pytest.raises(FileNotFoundError):
        agent.enqueue(nid, cid, version, project_incarnation=binding['project_incarnation'])
    assert not marker.exists() and not bundle.generations._job_path(binding['job_id']).exists()


def test_bound_retry_repairs_partial_original_proposal_links(tmp_path, memory_settings, monkeypatch):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    original = bundle.lore.link_evidence
    def fail(_item, **_kwargs): raise OSError('synthetic interrupted relation write')
    monkeypatch.setattr(bundle.lore, 'link_evidence', fail)
    with pytest.raises(OSError):
        agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
    proposals = bundle.lore.list_proposals(nid)
    assert len(proposals) == 1
    assert bundle.lore.list_proposal_evidence(proposals[0]['id']) == []
    assert bundle.generations.get(binding['job_id'])['status'] == 'FAILED'
    monkeypatch.setattr(bundle.lore, 'link_evidence', original)
    ids = agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
    assert ids == [proposals[0]['id']]
    assert len(bundle.lore.list_proposal_evidence(ids[0])) == 1
    assert bundle.generations.get(binding['job_id'])['status'] == 'COMPLETED'


def test_bound_effect_ids_do_not_adopt_legacy_receipts(tmp_path, memory_settings):
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    legacy = agent.extract(nid, cid, version, job_id='legacy-memory')
    bound = agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
    assert set(legacy).isdisjoint(bound)
    assert bundle.lore.get_proposal(bound[0])['generation_job_id'] == binding['job_id']
    assert len(bundle.lore.list_proposals(nid)) == len(bundle.lore.list_evidence(nid)) == 2


def test_bound_runtime_observers_run_after_project_lock_release(tmp_path, memory_settings):
    from app.runtime_events import runtime_events
    from app.repositories.file.mutation_coordinator import workspace_mutation_lock
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    observations = []
    def observe(change):
        if change.project_id != nid: return
        acquired = []
        def contender():
            lock = workspace_mutation_lock(tmp_path, f'project-lifecycle:{(tmp_path/"novels"/nid).resolve()}')
            locked = lock.acquire(timeout=.5)
            acquired.append(locked)
            if locked: lock.release()
        thread = Thread(target=contender); thread.start(); thread.join(1)
        observations.append(acquired == [True])
    unsubscribe = runtime_events.subscribe(observe)
    try: agent.extract(nid, cid, version, project_incarnation=binding['project_incarnation'])
    finally: unsubscribe()
    assert observations and all(observations)


def test_bound_memory_is_not_restored_as_writer_job(tmp_path, memory_settings):
    from app.jobs import JobManager
    from app.services import ChapterService, CanonService, ContextService, LoreService
    agent, bundle, nid, cid, version, owner, binding = setup(tmp_path)
    row = record(binding); row['status'] = 'GENERATING'
    bundle.generations.save(row)
    before = bundle.generations._job_path(binding['job_id']).read_bytes()
    manager = JobManager(generations=agent.generations, chapters=ChapterService(bundle.chapters),
        contexts=ContextService(bundle.novels,bundle.chapters,LoreService(bundle.lore)),
        canon=CanonService(bundle.canon),memory_extractor=agent,snapshot_required=False)
    assert binding['job_id'] not in manager.jobs
    assert bundle.generations._job_path(binding['job_id']).read_bytes() == before


def test_postgres_bound_memory_is_explicitly_unsupported_without_session(tmp_path):
    from app.repositories.postgres.generation import PostgresGenerationRepository
    *_, binding = setup(tmp_path)
    def no_session(): raise AssertionError('unsupported path opened PostgreSQL session')
    repository = PostgresGenerationRepository(SimpleNamespace(session=no_session))
    with pytest.raises(GenerationProjectIdentityError, match='POSTGRES_UNSUPPORTED'):
        repository.save(record(binding))
