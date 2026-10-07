"""Unique branch authority on actual File / opt-in real PostgreSQL owners."""
from copy import deepcopy
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.collaboration import Workspace, Storyline, Branch
from app.config import Settings
from app.document import markdown_to_document
from app.experimental.common import StaleSourceError
from app.experimental.store import ExperimentalStore
from app.experimental.ux import ReadContext
from app.repositories.chapter_repository import VersionConflict
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService
from app.services.branch_manuscript_service import BranchManuscriptService, FORKS, MERGES
from app.services.collaboration_scope_service import CollaborationScopeService


def doc(text): return markdown_to_document('# Synthetic branch\n\n' + text)
def confirm(row): return (row['id'], row['version'], row['preview_digest'], True)


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def env(tmp_path, request, monkeypatch):
    backend = request.param; url = os.getenv('TEST_POSTGRES_DATABASE_URL', '') if backend == 'postgres' else ''
    if backend == 'postgres' and not url: pytest.fail('real PostgreSQL branch contracts require TEST_POSTGRES_DATABASE_URL')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'branch_manuscript_v1'); monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url, novel_data=tmp_path), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters); chapters = ChapterService(bundle.chapters)
    nid = 'branch-fixture-' + uuid4().hex; novels.create({'id': nid, 'title': 'Synthetic only'})
    original = chapters.create(nid, {'title': 'Original', 'content': 'Before'})
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    wid, sid, bid = ('w-' + uuid4().hex, 's-' + uuid4().hex, 'b-' + uuid4().hex)
    scopes.create_workspace(Workspace(wid, 'Fixture')); scopes.link_project(wid, nid)
    scopes.create_storyline(Storyline(sid, wid, nid, 'Fixture'))
    scopes.create_branch(Branch(bid, wid, nid, sid, 'Branch'))
    scope = {'mode': 'collaboration', 'novel_id': nid, 'workspace_id': wid, 'storyline_id': sid, 'branch_id': bid}
    store = ExperimentalStore(tmp_path, backend, url); service = BranchManuscriptService(store, novels, chapters, scopes)
    ctx = ReadContext(nid, scope, 'fixture-author', 'fixture-token', bid)
    yield SimpleNamespace(service=service, store=store, novels=novels, chapters=chapters, nid=nid, original=original,
                          ctx=ctx, local={'mode': 'local', 'novel_id': nid}, scopes=scopes, backend=backend, url=url, root=tmp_path, bundle=bundle)
    if backend == 'postgres':
        with store._connect() as conn: conn.execute('DELETE FROM experimental_scope_documents WHERE novel_id=%s', (nid,))
        novels.delete(nid); bundle.novels.database.engine.dispose()


def fork(e, source_scope=None, ids=None):
    preview = e.service.preview_fork(e.ctx, source_scope or e.local, ids or [e.original['id']])
    row = e.service.apply_fork(e.ctx, *confirm(preview))
    return row, next(iter(row['id_map'].values()))


def test_unique_scope_owner_empty_then_rich_history_restart_and_tombstones(env):
    e = env; original = e.chapters.get(e.original['id'])
    assert not e.service.manifest(e.ctx)['initialized'] and not e.service.reader.available(e.ctx)
    assert e.service.chapters(e.ctx) == []
    with pytest.raises(FileNotFoundError): e.service.read(e.ctx, e.original['id'])
    rich = doc('Branch only'); rich['content'][1]['content'][0]['marks'] = [{'type': 'bold'}]
    row = e.service.create(e.ctx, {'title': 'Branch', 'document': rich})
    assert e.service.reader.available(e.ctx) and ':~b' in row['id'] and row['document'] == rich
    receipt = e.service.commit(e.ctx, row['id'], 1, doc('Saved'), 'save-once')
    assert receipt['after_version'] == 2
    assert e.service.commit(e.ctx, row['id'], 1, doc('Saved'), 'save-once') == receipt
    with pytest.raises(ValueError, match='REUSED'): e.service.commit(e.ctx, row['id'], 1, doc('Other'), 'save-once')
    restarted = BranchManuscriptService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters, e.scopes)
    assert restarted.read(e.ctx, row['id'])['document'] == doc('Saved')
    restored = restarted.restore(e.ctx, row['id'], 1, 2)
    assert restored['document'] == rich and restored['version'] == 3
    archived = restarted.archive(e.ctx, row['id'], True, 3)
    assert not restarted.chapters(e.ctx)
    deleted = restarted.delete(e.ctx, row['id'], archived['version'])
    assert deleted['identity_reusable'] is False
    with pytest.raises(FileNotFoundError): restarted.read(e.ctx, row['id'])
    new = restarted.create(e.ctx, {'title': 'Next', 'content': ''})
    assert new['id'] != row['id'] and new['number'] == 2
    assert e.chapters.get(e.original['id']) == original
    assert restarted.manifest(e.ctx)['tombstone_count'] == 1


def test_atomic_cas_and_receipt_shared_with_realtime_transaction(env):
    e = env; row = e.service.create(e.ctx, {'title': 'Branch'})
    def update(i):
        service = BranchManuscriptService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters, e.scopes)
        try: return service.commit(e.ctx, row['id'], 1, doc(str(i)), 'parallel-' + str(i))
        except VersionConflict: return 'CONFLICT'
    with ThreadPoolExecutor(max_workers=2) as executor: result = list(executor.map(update, (1, 2)))
    assert result.count('CONFLICT') == 1 and e.service.read(e.ctx, row['id'])['version'] == 2
    before = e.service.read(e.ctx, row['id'])
    with pytest.raises(RuntimeError):
        with e.store.transaction(e.nid, e.ctx.scope) as state:
            e.service.commit(e.ctx, row['id'], 2, doc('Rolled back'), 'rollback', state=state)
            state['collections']['synthetic-operation-journal'] = {'operation': {'status': 'APPLIED'}}
            raise RuntimeError('synthetic transaction interruption')
    assert e.service.read(e.ctx, row['id']) == before
    with pytest.raises(FileNotFoundError): e.service.repository(e.ctx.scope).receipt('rollback')
    with e.store.transaction(e.nid, e.ctx.scope) as state:
        receipt = e.service.commit(e.ctx, row['id'], 2, doc('Atomic'), 'committed', state=state)
        state['collections']['synthetic-operation-journal'] = {'operation': {'after_version': receipt['after_version']}}
    assert e.service.read(e.ctx, row['id'])['version'] == 3


def test_revoke_and_flag_off_leave_branch_transaction_untouched(env, monkeypatch):
    e = env; row = e.service.create(e.ctx, {'title': 'Branch'})
    count = 0
    def revoke():
        nonlocal count
        count += 1
        if count == 2: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): e.service.commit(e.ctx, row['id'], 1, doc('Denied'), 'revoked', revoke)
    assert e.service.read(e.ctx, row['id'])['version'] == 1
    with pytest.raises(FileNotFoundError): e.service.repository(e.ctx.scope).receipt('revoked')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert not e.service.reader.available(e.ctx) and e.service.reader(e.ctx) == []


def test_fork_rich_snapshot_source_drift_and_cancel_are_real(env):
    e = env; preview = e.service.preview_fork(e.ctx, e.local, [e.original['id']])
    e.chapters.save(e.original['id'], {'version': 1, 'document': doc('Source changed')})
    with pytest.raises(StaleSourceError): e.service.apply_fork(e.ctx, *confirm(preview))
    assert e.service.chapters(e.ctx) == []
    cancel = e.service.cancel(e.ctx, 'fork', preview['id'], 1)
    assert cancel['status'] == 'CANCELLED'
    with pytest.raises(ValueError): e.service.apply_fork(e.ctx, *confirm(cancel))
    row, cid = fork(e)
    assert row['status'] == 'APPLIED' and e.service.read(e.ctx, cid)['document'] == e.chapters.get(e.original['id'])['document']
    assert e.service.read(e.ctx, cid)['origin']['chapter_id'] == e.original['id']


def test_compare_human_merge_conflict_cas_and_checkpoint(env):
    e = env; _, cid = fork(e)
    e.service.save(e.ctx, cid, doc('Branch edit'), 1)
    e.chapters.save(e.original['id'], {'version': 1, 'document': doc('Main edit')})
    comparison = e.service.compare(e.ctx, cid, e.local, e.original['id'])
    assert not comparison['can_apply'] and comparison['conflicts']
    choices = {row['id']: 'FORK' for row in comparison['conflicts']}
    proposal = e.service.propose_merge(e.ctx, cid, e.local, e.original['id'], choices)
    calls = []
    def write(cid, document, version, source):
        calls.append(cid); return e.chapters.save(cid, {'document': document, 'version': version, 'source': source})
    result = e.service.apply_merge(e.ctx, *confirm(proposal), mainline_writer=write)
    assert result['status'] == 'APPLIED' and calls == [e.original['id']]
    assert e.chapters.get(e.original['id'])['document'] == doc('Branch edit')
    assert e.chapters.history(e.original['id'])[0]['document'] == doc('Main edit')
    with pytest.raises(ValueError): e.service.apply_merge(e.ctx, *confirm(result), mainline_writer=write)
    assert len(calls) == 1


def test_mainline_write_unknown_never_replays_after_restart(env):
    e = env; _, cid = fork(e); e.service.save(e.ctx, cid, doc('Branch edit'), 1)
    proposal = e.service.propose_merge(e.ctx, cid, e.local, e.original['id'])
    def lost_response(cid, document, version, source):
        e.chapters.save(cid, {'document': document, 'version': version, 'source': source})
        raise RuntimeError('synthetic lost response')
    with pytest.raises(RuntimeError): e.service.apply_merge(e.ctx, *confirm(proposal), mainline_writer=lost_response)
    row = e.service.records(e.ctx)['merges'][0]; assert row['status'] == 'RECOVERY_REQUIRED'
    restarted = BranchManuscriptService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters, e.scopes)
    result = restarted.recover_merge(e.ctx, row['id'], row['version'])
    assert result['status'] == 'RECOVERY_REQUIRED' and result['recovery']['matches_desired']
    assert result['recovery']['automatic_replay'] is False and not result['recovery']['operation_receipt_verified']
    assert e.chapters.get(e.original['id'])['version'] == 2


def test_branch_merge_exact_receipt_recovery_and_sibling_isolation(env):
    e = env
    parent = e.service.create(e.ctx, {'title': 'Parent', 'document': doc('Base')})
    bid = 'child-' + uuid4().hex; e.scopes.create_branch(Branch(bid, e.ctx.scope['workspace_id'], e.nid, e.ctx.scope['storyline_id'], 'Child'))
    child_ctx = replace(e.ctx, scope={**e.ctx.scope, 'branch_id': bid}, branch=bid)
    preview = e.service.preview_fork(child_ctx, e.ctx.scope, [parent['id']])
    forked = e.service.apply_fork(child_ctx, *confirm(preview)); cid = forked['id_map'][parent['id']]
    with pytest.raises(FileNotFoundError): e.service.read(child_ctx, parent['id'])
    with pytest.raises(FileNotFoundError): e.service.read(e.ctx, cid)
    e.service.save(child_ctx, cid, doc('Child result'), 1)
    proposal = e.service.propose_merge(child_ctx, cid, e.ctx.scope, parent['id'])
    merged = e.service.apply_merge(child_ctx, *confirm(proposal))
    assert merged['status'] == 'APPLIED' and e.service.read(e.ctx, parent['id'])['version'] == 2
    with e.store.transaction(e.nid, child_ctx.scope) as state:
        state['collections'][MERGES][merged['id']]['status'] = 'APPLYING'  # synthetic crash before final receipt
    recovered = e.service.recover_merge(child_ctx, merged['id'], merged['version'])
    assert recovered['status'] == 'APPLIED' and recovered['recovery']['operation_receipt_verified']
    assert e.service.read(e.ctx, parent['id'])['version'] == 2


def test_branch_capacity_rejects_atomically_without_pruning_and_reserves_restore(env, monkeypatch):
    import app.repositories.branch_manuscript as model
    e = env; row = e.service.create(e.ctx, {'title': 'Bounded', 'document': doc('Base')})
    monkeypatch.setattr(model, 'MAX_HISTORY_PER_CHAPTER', 1)
    saved = e.service.save(e.ctx, row['id'], doc('First'), 1)
    with pytest.raises(ValueError, match='CAPACITY_HISTORY'):
        e.service.commit(e.ctx, row['id'], 2, doc('Rejected'), 'over-capacity')
    assert e.service.read(e.ctx, row['id']) == saved
    with pytest.raises(FileNotFoundError): e.service.repository(e.ctx.scope).receipt('over-capacity')
    # Recovery reserve keeps explicit restoration available; no snapshot is evicted.
    restored = e.service.restore(e.ctx, row['id'], 1, 2)
    assert restored['document'] == doc('Base') and len(e.service.repository(e.ctx.scope).history(row['id'])) == 2
    monkeypatch.setattr(model, 'MAX_HISTORY_PER_CHAPTER', 500)
    monkeypatch.setattr(model, 'MAX_OPERATION_RECEIPTS', 0)
    with pytest.raises(ValueError, match='CAPACITY'):
        e.service.commit(e.ctx, row['id'], restored['version'], doc('Receipt refused'), 'receipt-over-capacity')
    assert e.service.read(e.ctx, row['id']) == restored


def test_branch_fork_journal_capacity_and_scope_corruption_fail_closed(env, monkeypatch):
    import app.services.branch_manuscript_service as service_module
    e = env
    monkeypatch.setattr(service_module, 'MAX_REVIEW_RECORDS', {FORKS: 0, MERGES: 1, service_module.SNAPSHOTS: 1})
    with pytest.raises(ValueError, match='CAPACITY'):
        e.service.preview_fork(e.ctx, e.local, [e.original['id']])
    assert not e.service.records(e.ctx)['forks'] and not e.service.manifest(e.ctx)['initialized']
    row = e.service.create(e.ctx, {'title': 'Scope fence'})
    from app.repositories.branch_manuscript import COLLECTION
    with e.store.transaction(e.nid, e.ctx.scope) as state:
        state['collections'][COLLECTION][e.ctx.branch]['chapters'][row['id']]['branch_id'] = 'foreign'
    with pytest.raises(ValueError, match='IDENTITY_CORRUPT'): e.service.chapters(e.ctx)


def test_deleted_fork_source_never_rebinds_to_another_chapter(env):
    e = env
    parent = e.service.create(e.ctx, {'title': 'Source', 'document': doc('Original branch')})
    bid = 'child-' + uuid4().hex
    e.scopes.create_branch(Branch(bid, e.ctx.scope['workspace_id'], e.nid, e.ctx.scope['storyline_id'], 'Child'))
    child = replace(e.ctx, scope={**e.ctx.scope, 'branch_id': bid}, branch=bid)
    preview = e.service.preview_fork(child, e.ctx.scope, [parent['id']])
    archived = e.service.archive(e.ctx, parent['id'], True, 1)
    e.service.delete(e.ctx, parent['id'], archived['version'])
    replacement = e.service.create(e.ctx, {'title': 'Source', 'document': doc('Replacement')})
    assert replacement['number'] == 2 and replacement['id'] != parent['id']
    with pytest.raises(FileNotFoundError): e.service.apply_fork(child, *confirm(preview))
    assert e.service.chapters(child) == [] and e.service.records(child)['forks'][0]['status'] == 'REVIEW'
    with pytest.raises(FileNotFoundError): e.service.snapshot(e.ctx.scope, parent['id'], 1, {}, 'test', 'synthetic')


def test_branch_tombstone_capacity_and_byte_recovery_reserve_are_atomic(env, monkeypatch):
    import app.repositories.branch_manuscript as model
    e = env; row = e.service.create(e.ctx, {'title': 'Bounded', 'document': doc('Base')})
    saved = e.service.save(e.ctx, row['id'], doc('Saved'), 1)
    used = e.service.manifest(e.ctx)['capacity']['used_bytes']
    monkeypatch.setattr(model, 'RECOVERY_RESERVE_BYTES', 8192)
    monkeypatch.setattr(model, 'MAX_MANUSCRIPT_BYTES', used + 8192)
    with pytest.raises(ValueError, match='CAPACITY'):
        e.service.save(e.ctx, row['id'], doc('Normal write has no reserve access'), 2)
    assert e.service.read(e.ctx, row['id']) == saved
    restored = e.service.restore(e.ctx, row['id'], 1, 2)
    assert restored['version'] == 3 and restored['document'] == doc('Base')
    before = e.store.read(e.nid, e.ctx.scope)
    monkeypatch.setattr(model, 'MAX_MANUSCRIPT_BYTES', e.service.manifest(e.ctx)['capacity']['used_bytes'])
    with pytest.raises(ValueError, match='CAPACITY'): e.service.restore(e.ctx, row['id'], 2, 3)
    assert e.store.read(e.nid, e.ctx.scope) == before
    monkeypatch.setattr(model, 'MAX_MANUSCRIPT_BYTES', 64 * 1024 * 1024)
    archived = e.service.archive(e.ctx, row['id'], True, 3)
    e.service.delete(e.ctx, row['id'], archived['version'])
    monkeypatch.setattr(model, 'MAX_CHAPTER_IDENTITIES', 1)
    before = e.store.read(e.nid, e.ctx.scope)
    with pytest.raises(ValueError, match='CHAPTER_LIMIT'): e.service.create(e.ctx, {'title': 'Must not reuse tombstone'})
    assert e.store.read(e.nid, e.ctx.scope) == before and e.service.manifest(e.ctx)['tombstone_count'] == 1


def test_branch_review_reserve_permits_terminal_cancel_but_never_over_hard_limit(env, monkeypatch):
    import app.services.branch_manuscript_service as service_module
    from app.experimental.store import canonical
    e = env; preview = e.service.preview_fork(e.ctx, e.local, [e.original['id']])
    state = e.store.read(e.nid, e.ctx.scope)
    owned = {key: state['collections'].get(key, {}) for key in service_module.MAX_REVIEW_RECORDS}
    used = len(canonical(owned).encode())
    monkeypatch.setattr(service_module, 'MAX_REVIEW_BYTES', used - 1)
    with pytest.raises(ValueError, match='CAPACITY'): e.service.cancel(e.ctx, 'fork', preview['id'], 1)
    assert e.store.read(e.nid, e.ctx.scope) == state
    monkeypatch.setattr(service_module, 'MAX_REVIEW_BYTES', used + 256)
    with pytest.raises(ValueError, match='CAPACITY'): e.service.preview_fork(e.ctx, e.local, [e.original['id']])
    assert len(e.service.records(e.ctx)['forks']) == 1
    cancelled = e.service.cancel(e.ctx, 'fork', preview['id'], 1)
    assert cancelled['status'] == 'CANCELLED' and cancelled['version'] == 2


@pytest.mark.postgres_backend_only
def test_postgres_generation_legacy_project_marker_is_not_a_branch_identifier(tmp_path):
    from sqlalchemy import select
    from app.repositories.postgres.models import NovelModel, GenerationJobModel
    from app.repositories.postgres.common import external_uuid
    url = os.getenv('TEST_POSTGRES_DATABASE_URL', '')
    if not url: pytest.fail('real PostgreSQL identity contract requires TEST_POSTGRES_DATABASE_URL')
    bundle = create_repository_bundle(Settings(storage_backend='postgres', database_url=url, novel_data=tmp_path), data_root=tmp_path)
    original = 'legacy-marker-' + uuid4().hex; nid = original + ':~b-component'
    novels = NovelService(bundle.novels, bundle.chapters)
    try:
        novels.create({'id': original, 'title': 'Synthetic legacy marker'})
        chapter = bundle.chapters.create(original, {'title': 'Mainline', 'content': 'Mainline original'})
        # Only synthetic data: emulate a preexisting legacy slug containing
        # the branch marker without changing any historical production record.
        with bundle.novels.database.session() as session:
            model = session.scalar(select(NovelModel).where(NovelModel.slug == original))
            model.slug = nid
        cid = nid + ':' + chapter['id'].rsplit(':', 1)[1]
        record = {'id': str(uuid4()), 'novel_id': nid, 'chapter_id': cid, 'operation': 'polish', 'status': 'FAILED'}
        bundle.generations.save(record)
        assert bundle.generations.get(record['id'])['chapter_id'] == cid
        with bundle.novels.database.session() as session:
            assert session.get(GenerationJobModel, external_uuid(record['id'])).chapter_id is not None
    finally:
        try: novels.delete(nid)
        except FileNotFoundError: novels.delete(original)
        bundle.novels.database.engine.dispose()
