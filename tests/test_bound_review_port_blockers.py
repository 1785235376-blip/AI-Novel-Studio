"""Executable activation blockers, NOT successful bound acceptance coverage.

Legacy counterexamples intentionally demonstrate adoption by slug. Never remove
ordinary mutation gates merely because individual existing ports take locks.
"""
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from test_passive_generation_manager_binding import (
    source, _load, _replace_owner, MUTATION_CODE,
)
from test_memory_agent_contract import runner, valid_output, memory_settings
from app.creative.project_store import CreativeProjectStore
from app.services import NovelService

pytestmark = pytest.mark.file_backend_only


def project_bytes(root, nid):
    return {str(p.relative_to(root)): p.read_bytes()
            for p in (root / 'novels' / nid).rglob('*') if p.is_file()}


@pytest.mark.parametrize('operation', ['accept', 'reject'])
def test_bound_review_replacement_after_initial_read_still_writes_nothing(source, monkeypatch, operation):
    row, manager, job = _load(source)
    original_get = manager.get
    replacement = {}

    def get_then_replace(jid):
        value = original_get(jid)
        _replace_owner(source)
        replacement.update(project_bytes(source.root, job.novel_id))
        return value

    monkeypatch.setattr(manager, 'get', get_then_replace)
    before_record = source.bundle.generations._job_path(job.id).read_bytes()
    with pytest.raises(HTTPException) as exc:
        getattr(manager, operation)(job.id)
    assert exc.value.status_code == 409 and exc.value.detail['code'] == MUTATION_CODE
    assert project_bytes(source.root, job.novel_id) == replacement
    assert source.bundle.generations._job_path(job.id).read_bytes() == before_record
    assert job.status == 'COMPLETED'
    assert source.counts == dict(worker=0, adapter=0, stream=0, memory=0)


@pytest.mark.parametrize('seam', ['before_review_lock', 'before_chapter_write', 'between_summary_canon'])
def test_legacy_review_ports_are_not_an_incarnation_fence(source, monkeypatch, seam):
    """A last-minute read or per-port lock cannot substitute for composition."""
    row, manager, job = _load(source, bound=False)
    replaced = []

    def replace():
        assert not replaced
        replaced.append(True)
        _replace_owner(source)

    if seam == 'before_review_lock':
        import app.repositories.file.mutation_coordinator as coordinator
        original = coordinator.workspace_mutation

        @contextmanager
        def mutation(root, key):
            if key == f'generation-accept:{job.id}' and not replaced:
                replace()
            with original(root, key):
                yield

        monkeypatch.setattr(coordinator, 'workspace_mutation', mutation)
    elif seam == 'before_chapter_write':
        original = source.chapters.create

        def create(nid, payload):
            if not replaced:
                replace()
            return original(nid, payload)

        monkeypatch.setattr(source.chapters, 'create', create)
    else:
        original = source.canon.save_pending

        def save_pending(item):
            # Original chapter and summary are already durable at this point.
            assert len(source.chapters.list(job.novel_id)) == 2
            assert (source.root / 'novels' / job.novel_id / 'summaries/index.json').exists()
            replace()
            return original(item)

        monkeypatch.setattr(source.canon, 'save_pending', save_pending)

    result = manager.accept(job.id)
    assert replaced == [True] and job.status == 'ACCEPTED'
    assert source.owner.incarnation(job.novel_id) != source.incarnation
    # These are counterexamples on genuinely UNBOUND legacy jobs. Their writes
    # are expected here and are the reason the bound mutation gate stays closed.
    pending = source.canon.list_pending(job.novel_id)
    assert len(pending) == 1 and pending[0]['id'] == result['pending_canon']['id']
    if seam != 'between_summary_canon':
        assert job.output in source.chapters.get(result['chapter']['id'])['content']
    else:
        assert len(source.chapters.list(job.novel_id)) == 1
    assert source.counts['memory'] == 1


def replace_memory_owner(tmp_path, bundle, nid):
    novels = NovelService(bundle.novels, bundle.chapters)
    novels.delete(nid)
    replacement, _, new_nid, new_cid, new_version = runner(tmp_path, valid_output())
    assert new_nid == nid
    return replacement, new_cid, new_version


def test_delayed_original_memory_enqueue_adopts_replacement_owner(tmp_path, monkeypatch, memory_settings):
    """Original enqueue loses owner identity before its existing thread starts."""
    agent, bundle, nid, cid, version = runner(tmp_path, valid_output())
    owner = CreativeProjectStore(SimpleNamespace(backend='file', root=tmp_path))
    old_owner = owner.incarnation(nid)
    threads = []
    import app.lore.memory_agent as memory_module
    real_thread = memory_module.threading.Thread

    class DelayedThread(real_thread):
        def start(self):
            threads.append(self)

    monkeypatch.setattr(memory_module.threading, 'Thread', DelayedThread)
    jid = agent.enqueue(nid, cid, version)
    assert len(threads) == 1 and bundle.generations.get(jid)['status'] == 'QUEUED'
    replacement, new_cid, new_version = replace_memory_owner(tmp_path, bundle, nid)
    assert (new_cid, new_version) == (cid, version)
    assert owner.incarnation(nid) != old_owner
    threads[0].run()  # Original _quiet_extract -> extract -> real MockProvider.
    record = bundle.generations.get(jid)
    assert record['status'] == 'COMPLETED'
    assert record['execution_mode'] == 'mock_standin'
    assert len(agent.runtime.provider.calls) == 1
    assert len(bundle.lore.list_proposals(nid)) == len(bundle.lore.list_evidence(nid)) == 1
    # Existing deterministic enqueue identity also aliases the replacement.
    assert replacement.enqueue(nid, cid, version) == jid
    assert len(threads) == 1


def test_memory_final_input_recheck_is_not_a_final_write_fence(tmp_path, monkeypatch, memory_settings):
    agent, bundle, nid, cid, version = runner(tmp_path, valid_output())
    owner = CreativeProjectStore(SimpleNamespace(backend='file', root=tmp_path))
    old_owner = owner.incarnation(nid)
    original_input = agent._input
    inputs = []

    def input_then_replace(*args):
        data = original_input(*args)
        inputs.append(data)
        if len(inputs) == 2:
            replace_memory_owner(tmp_path, bundle, nid)
        return data

    monkeypatch.setattr(agent, '_input', input_then_replace)
    ids = agent.extract(nid, cid, version, job_id='memory-last-check-counterexample')
    assert len(inputs) == 2 and inputs[0] == inputs[1]
    assert owner.incarnation(nid) != old_owner
    assert len(ids) == 1 and len(agent.runtime.provider.calls) == 1
    assert len(bundle.lore.list_evidence(nid)) == 1
    assert len(bundle.lore.list_proposal_evidence(ids[0])) == 1
    assert bundle.generations.get('memory-last-check-counterexample')['status'] == 'COMPLETED'
