"""Actual File / explicitly selected real PostgreSQL B10 deterministic contracts."""
from copy import deepcopy
from dataclasses import replace
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.config import Settings
from app.experimental.common import StaleSourceError
from app.experimental.offline_sync import OfflineSyncService, safe_snapshot
from app.experimental.store import ExperimentalStore
from app.experimental.ux import ReadContext
from app.experimental.writing_focus import WritingFocusService
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.services.v1_capability_service import CapabilityVersionConflict


def doc(text='Synthetic seed'):
    return {'type': 'doc', 'content': [{'type': 'heading', 'attrs': {'level': 1}, 'content': [{'type': 'text', 'text': 'Shared'}]},
                                       {'type': 'paragraph', 'content': [{'type': 'text', 'text': text}]}]}


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def pair(request, tmp_path):
    backend = request.param; url = os.getenv('TEST_POSTGRES_DATABASE_URL', '') if backend == 'postgres' else ''
    if backend == 'postgres' and not url: pytest.fail('real B10 PostgreSQL requires TEST_POSTGRES_DATABASE_URL')
    values = []
    for label in ['A', 'B']:
        root = tmp_path / label; bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url, novel_data=root), data_root=root)
        novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
        nid = 'sync-test-' + uuid4().hex; novels.create({'id': nid, 'title': 'Synthetic ' + label})
        chapter = chapters.create(nid, {'title': 'Shared', 'content': ''}); chapter = chapters.save(chapter['id'], {'version': chapters.get(chapter['id'])['version'], 'document': doc()})
        store = ExperimentalStore(root, backend, url); sources = WritingFocusService(store, novels, chapters)
        ctx = ReadContext(nid, {'mode': 'local', 'novel_id': nid}, 'local-author')
        values.append(SimpleNamespace(service=OfflineSyncService(store, novels, chapters, sources=sources), chapters=chapters, novels=novels,
                                      store=store, ctx=ctx, nid=nid, cid=chapter['id'], bundle=bundle))
    a, b = values; stream = 'test-' + uuid4().hex
    for e, label, peer in [(a, 'A', 'B'), (b, 'B', 'A')]:
        e.channel = e.service.open_channel(e.ctx, {'stream_id': stream, 'endpoint_id': label, 'peer_id': peer, 'chapter_ids': [e.cid], 'allow_new_chapters': True})
    yield a, b
    if backend == 'postgres':
        for e in values:
            with e.store._connect() as c: c.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (e.nid,))
            e.novels.delete(e.nid); e.bundle.novels.database.engine.dispose()


def channel(e): return e.service._channel(e.ctx, e.channel['id'])
def edit(e, text):
    current = e.chapters.get(e.cid)
    return e.chapters.save(e.cid, {'version': current['version'], 'document': doc(text)})
def queue(e, **extra):
    return e.service.queue(e.ctx, e.channel['id'], {'expected_version': channel(e)['version'], 'chapter_id': e.cid, 'request_id': uuid4().hex, **extra})
def export(e, out):
    return e.service.export(e.ctx, out['id'], {'expected_version': out['version'], 'envelope_digest': out['envelope_digest'], 'acknowledge_copy_boundary': True})
def receive(e, out, **extra):
    body = {'expected_version': channel(e)['version'], 'envelope': out['envelope'], 'target_chapter_id': e.cid, **extra}
    return e.service.receive(e.ctx, e.channel['id'], body)
def review(e, row, choices=None): return e.service.review(e.ctx, row['id'], {'expected_version': row['version'], 'choices': choices or {}})
def create_writer(e, nid, title, document):
    row = e.chapters.create(nid, {'title': title, 'content': ''}); row = e.chapters.get(row['id'])
    return e.chapters.save(row['id'], {'version': row['version'], 'document': document, 'source': 'OFFLINE_SYNC_ADD'})
def apply(e, row, plan, **kwargs):
    return e.service.apply(e.ctx, row['id'], {'expected_version': row['version'], 'preview_digest': plan['preview_digest'], 'confirmed': True, 'choices': plan['choices']},
        **({'save_document': lambda cid, document, version, source: e.chapters.save(cid, {'version': version, 'document': document, 'source': source}),
            'archive_chapter': e.chapters.archive, 'create_chapter': lambda *args: create_writer(e, *args)} | kwargs))


def test_offline_saved_snapshot_is_durable_and_only_explicit_selected_chapter_exchanges(pair):
    a, b = pair; unselected = a.chapters.create(a.nid, {'title': 'Excluded', 'content': 'Never exchange'})
    edit(a, 'Offline saved'); out = queue(a)
    fresh = ExperimentalStore(a.store.root, a.store.backend, a.store.database_url)
    assert fresh.read(a.nid, a.ctx.scope)['collections'][a.service.OUTBOX][out['id']]['envelope']['snapshot']['document'] == doc('Offline saved')
    with pytest.raises(ValueError, match='NOT_SELECTED'): queue(a, chapter_id=unselected['id'])
    sent = export(a, out); before = deepcopy(b.chapters.get(b.cid)); inbox = receive(b, sent)
    assert b.chapters.get(b.cid) == before and inbox['status'] == 'PENDING_REVIEW'
    plan = review(b, inbox); assert plan['can_apply']
    done = apply(b, inbox, plan); assert done['status'] == 'APPLIED' and b.chapters.get(b.cid)['document'] == doc('Offline saved')
    ack = a.service.delivery(a.ctx, out['id'], {'expected_version': sent['version'], 'state': 'ACKNOWLEDGED', 'receipt': inbox['receipt']})
    assert ack['status'] == 'ACKNOWLEDGED'
    assert len(b.chapters.list(b.nid)) == 1


def test_duplicate_replay_gap_cursor_and_mutated_message_fail_closed(pair):
    a, b = pair; first = export(a, queue(a)); edit(a, 'Newest'); latest = export(a, queue(a)); received = receive(b, latest)
    assert channel(b)['receive_cursor'] == 2
    duplicate = receive(b, latest); assert duplicate['duplicate'] and duplicate['id'] == received['id']
    with pytest.raises(ValueError, match='OUT_OF_ORDER'): receive(b, first)
    mutated = deepcopy(latest); mutated['envelope']['snapshot']['title'] = 'tampered'
    with pytest.raises(ValueError, match='IDEMPOTENCY'): receive(b, mutated)
    bad = deepcopy(latest); bad['envelope']['message_id'] = uuid4().hex; bad['envelope']['sequence'] = 3; bad['envelope']['destination_endpoint'] = 'Wrong'
    with pytest.raises(ValueError, match='WRONG_PEER'): receive(b, bad)


def test_conflict_requires_explicit_diff_choice_and_original_cas_history(pair):
    a, b = pair; edit(a, 'Incoming'); edit(b, 'Local'); out = export(a, queue(a)); inbox = receive(b, out)
    plan = review(b, inbox); assert not plan['can_apply'] and plan['unresolved'] == 1
    with pytest.raises(ValueError, match='UNRESOLVED'): apply(b, inbox, plan)
    conflict = next(s for s in plan['segments'] if s['kind'] == 'CONFLICT')
    assert conflict['local'][0]['content'][0]['text'] == 'Local'
    plan = review(b, inbox, {conflict['id']: 'INCOMING'}); old = b.chapters.get(b.cid)
    apply(b, inbox, plan); assert b.chapters.get(b.cid)['document'] == doc('Incoming')
    assert any(r['document'] == old['document'] for r in b.chapters.history(b.cid))
    with pytest.raises(CapabilityVersionConflict): apply(b, inbox, plan)


def test_review_source_drift_and_current_authority_revocation_stop_before_write(pair):
    a, b = pair; edit(a, 'Incoming'); inbox = receive(b, export(a, queue(a))); plan = review(b, inbox); edit(b, 'New local')
    with pytest.raises(StaleSourceError): apply(b, inbox, plan)
    plan = review(b, inbox); conflict = next(s for s in plan['segments'] if s['kind'] == 'CONFLICT'); plan = review(b, inbox, {conflict['id']: 'INCOMING'})
    def denied(): raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): apply(b, inbox, plan, reauthorize=denied)
    assert b.chapters.get(b.cid)['document'] == doc('New local')
    out = queue(a); edit(a, 'newer source')
    with pytest.raises(StaleSourceError): export(a, out)


def test_new_addition_is_explicit_never_duplicate_after_unknown_receipt(pair):
    a, b = pair; out = export(a, queue(a)); before = len(b.chapters.list(b.nid))
    inbox = receive(b, out, target_chapter_id=None, create_new=True); plan = review(b, inbox); calls = []
    def lost(*args): calls.append(1); create_writer(b, *args); raise RuntimeError('lost receipt')
    with pytest.raises(RuntimeError): apply(b, inbox, plan, create_chapter=lost)
    unknown = b.service._owned(b.ctx, b.service.INBOX, inbox['id']); assert unknown['status'] == 'UNKNOWN'
    with pytest.raises(CapabilityVersionConflict): apply(b, inbox, plan, create_chapter=lost)
    observation = b.service.recover(b.ctx, unknown['id'], {'expected_version': unknown['version']})
    assert observation['can_adopt'] and not observation['retry_allowed'] and len(calls) == 1
    reconciled = b.service.recover(b.ctx, unknown['id'], {'expected_version': unknown['version'], 'adopt_matching_result': True, 'preview_digest': observation['preview_digest']})
    assert reconciled['status'] == 'RECONCILED' and len(b.chapters.list(b.nid)) == before + 1
    assert receive(b, out, target_chapter_id=None, create_new=True)['duplicate']


def test_disconnect_manual_retry_retains_same_id_and_no_network_connection(pair, monkeypatch):
    a, b = pair
    import socket
    def no_network(*args, **kwargs): raise AssertionError('Production sync must not open a connection')
    monkeypatch.setattr(socket, 'create_connection', no_network)
    out = queue(a); attempt = export(a, out)
    failed = a.service.delivery(a.ctx, out['id'], {'expected_version': attempt['version'], 'state': 'FAILED'})
    again = export(a, failed); assert again['id'] == out['id'] and again['envelope'] == attempt['envelope']
    row = receive(b, again); assert receive(b, again)['duplicate']
    apply(b, row, review(b, row))


def test_tombstone_blocks_older_pending_and_future_exchange_but_keeps_downloads(pair):
    a, b = pair; out = export(a, queue(a)); inbox = receive(b, out)
    current = a.chapters.get(a.cid); a.chapters.archive(a.cid, current['version'])
    tombstone = export(a, queue(a, tombstone=True)); deletion = receive(b, tombstone)
    assert tombstone['envelope']['snapshot'] is None and b.chapters.get(b.cid)['is_archived'] is False
    with pytest.raises(CapabilityVersionConflict): review(b, inbox)
    with pytest.raises(ValueError, match='TOMBSTONED'): a.service.inspect_outbox(a.ctx, out['id'])
    plan = review(b, deletion); assert not plan['can_apply']; key = plan['segments'][0]['id']
    plan = review(b, deletion, {key: 'INCOMING'}); apply(b, deletion, plan)
    assert b.chapters.get(b.cid)['is_archived'] and out['envelope']['snapshot']['document'] == doc()
    restored = a.chapters.restore_archive(a.cid, a.chapters.get(a.cid)['version'])
    with pytest.raises(ValueError, match='TOMBSTONED'): queue(a)
    a.service.revoke(a.ctx, a.channel['id'], {'expected_version': channel(a)['version']})
    with pytest.raises(ValueError, match='REVOKED'): export(a, tombstone)


def test_unknown_failed_write_never_silently_retried_and_pending_updates_fenced(pair):
    a, b = pair; edit(a, 'new'); row = receive(b, export(a, queue(a))); plan = review(b, row)
    def failed(*args): raise RuntimeError('synthetic disconnect')
    with pytest.raises(RuntimeError): apply(b, row, plan, save_document=failed)
    unknown = b.service._owned(b.ctx, b.service.INBOX, row['id']); observation = b.service.recover(b.ctx, row['id'], {'expected_version': unknown['version']})
    assert observation['observations'][0]['state'] == 'CHECKPOINT_UNCHANGED' and not observation['can_adopt']
    edit(a, 'newer'); out = export(a, queue(a))
    with pytest.raises(ValueError, match='RECONCILIATION'): receive(b, out)


def test_unsupported_branch_private_scope_unsafe_metadata_or_paths_rejected(pair):
    a, b = pair
    other_actor = replace(a.ctx, actor='other')
    with pytest.raises(FileNotFoundError): a.service._channel(other_actor, a.channel['id'])
    branch = replace(a.ctx, branch='not-a-base-chapter', scope={'mode': 'collaboration', 'novel_id': a.nid, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'})
    with pytest.raises(ValueError, match='BRANCH_WRITER'): a.service.catalog(branch)
    with pytest.raises(ValueError): safe_snapshot({'title': 'Secret', 'document': doc(), 'credentials': 'blocked'})
    with pytest.raises(ValueError, match='SENSITIVE'): safe_snapshot({'title': 'Secret', 'document': doc('api_key=synthetic-never-real')})
    with pytest.raises(ValueError, match='SENSITIVE'): safe_snapshot({'title': 'Local path', 'document': doc('/home/example/private')})
    media = {'type': 'doc', 'content': [{'type': 'image', 'attrs': {'asset_id': 'excluded'}}]}
    with pytest.raises(ValueError): safe_snapshot({'title': 'No media', 'document': media})


def test_retry_cap_bounded_history_and_invalid_receipt(pair):
    a, b = pair; out = queue(a)
    for attempt in range(8):
        out = export(a, out); assert out['attempts'] == attempt + 1
        if attempt == 0:
            with pytest.raises(ValueError, match='RECEIPT'): a.service.delivery(a.ctx, out['id'], {'expected_version': out['version'], 'state': 'ACKNOWLEDGED', 'receipt': {'invented': True}})
    with pytest.raises(ValueError, match='RETRY_LIMIT'): export(a, out)
    raw = a.service._owned(a.ctx, a.service.OUTBOX, out['id'])
    assert len(raw['history']) == 8 and all('envelope' not in h for h in raw['history'])


def test_idempotent_queue_is_stable_and_cannot_reuse_key_for_other_content(pair):
    a, b = pair; key = uuid4().hex; out = queue(a, request_id=key)
    assert queue(a, request_id=key)['id'] == out['id']
    current = a.chapters.get(a.cid); a.chapters.archive(a.cid, current['version'])
    with pytest.raises(ValueError, match='IDEMPOTENCY'): queue(a, request_id=key, tombstone=True)
    tombstone = queue(a, request_id='tombstone-retry', tombstone=True)
    assert queue(a, request_id='tombstone-retry', tombstone=True)['id'] == tombstone['id']


def test_same_message_concurrent_apply_only_one_original_write(pair):
    from concurrent.futures import ThreadPoolExecutor
    a, b = pair; edit(a, 'Concurrent candidate'); row = receive(b, export(a, queue(a))); plan = review(b, row)
    calls = []
    def write(cid, document, version, source):
        calls.append(cid); return b.chapters.save(cid, {'version': version, 'document': document, 'source': source})
    def attempt():
        try: return apply(b, row, plan, save_document=write)['status']
        except CapabilityVersionConflict: return 'STALE'
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(lambda _: attempt(), [0, 1]))
    assert sorted(results) == ['APPLIED', 'STALE'] and calls == [b.cid]


def test_revision_locks_and_cross_target_binding_are_fail_closed(pair):
    from app.revision_constraints import LOCK_ATTRIBUTE, node_digest
    a, b = pair
    # Introduce locks after selection, so incoming baseline is still the exact
    # registered initial baseline, but final local authority protects the lock.
    local = b.chapters.get(b.cid); locked = deepcopy(local['document']); node = locked['content'][1]
    node['attrs'] = {LOCK_ATTRIBUTE: {'id': 'synthetic-lock', 'state': 'LOCKED', 'digest': node_digest(node)}}
    b.chapters.save(b.cid, {'version': local['version'], 'document': locked})
    edit(a, 'Incoming tries locked paragraph'); out = export(a, queue(a)); row = receive(b, out); plan = review(b, row)
    key = next(s['id'] for s in plan['segments'] if s['kind'] == 'CONFLICT'); plan = review(b, row, {key: 'INCOMING'})
    assert plan['blocked'] == ['SYNC_REVISION_LOCKED'] and not plan['can_apply']
    with pytest.raises(ValueError, match='BLOCKED'): apply(b, row, plan)
    other = b.chapters.create(b.nid, {'title': 'Unselected', 'content': 'keep'})
    with pytest.raises(ValueError, match='IDEMPOTENCY'): receive(b, out, target_chapter_id=other['id'])
    edit(a, 'Next message'); latest = export(a, queue(a))
    with pytest.raises(ValueError, match='BINDING'): receive(b, latest, target_chapter_id=other['id'])


def test_pending_newer_snapshot_supersedes_old_review_and_keeps_both_candidates(pair):
    a, b = pair; edit(a, 'older'); old = receive(b, export(a, queue(a))); old_plan = review(b, old)
    edit(a, 'newer'); fresh = receive(b, export(a, queue(a)))
    with pytest.raises(CapabilityVersionConflict): apply(b, old, old_plan)
    stored = b.service._owned(b.ctx, b.service.INBOX, old['id']); assert stored['status'] == 'SUPERSEDED'
    assert 'older' in str(stored['envelope']['snapshot']['document'])
    apply(b, fresh, review(b, fresh)); assert b.chapters.get(b.cid)['document'] == doc('newer')


def test_explicit_close_retains_unknown_candidates_then_allows_fresh_review(pair):
    a, b = pair; edit(a, 'first'); row = receive(b, export(a, queue(a))); plan = review(b, row)
    def fail(*args): raise RuntimeError('before write')
    with pytest.raises(RuntimeError): apply(b, row, plan, save_document=fail)
    raw = b.service._owned(b.ctx, b.service.INBOX, row['id']); observation = b.service.recover(b.ctx, row['id'], {'expected_version': raw['version']})
    result = b.service.recover(b.ctx, row['id'], {'expected_version': raw['version'], 'close_without_replay': True, 'preview_digest': observation['preview_digest']})
    assert result['status'] == 'CLOSED_WITHOUT_REPLAY' and b.service._owned(b.ctx, b.service.INBOX, row['id'])['checkpoint']
    with pytest.raises(CapabilityVersionConflict): b.service.recover(b.ctx, row['id'], {'expected_version': raw['version']})
    edit(a, 'fresh'); fresh = receive(b, export(a, queue(a))); apply(b, fresh, review(b, fresh))
    assert b.chapters.get(b.cid)['document'] == doc('fresh')


def test_protocol_bounds_and_payload_metadata_are_not_downgraded(pair):
    a, b = pair; exported = export(a, queue(a))
    changed = deepcopy(exported); changed['envelope']['protocol'] = 'AI_NOVEL_SYNC_2'
    with pytest.raises(ValueError): receive(b, changed)
    changed = deepcopy(exported); changed['envelope']['snapshot']['document']['content'].append({'type': 'script', 'text': 'never execute'})
    with pytest.raises(ValueError): receive(b, changed)
    changed = deepcopy(exported); changed['envelope']['snapshot']['document']['content'][1]['content'][0]['text'] = 'x' * 270000
    with pytest.raises(ValueError, match='SIZE_LIMIT'): receive(b, changed)
    changed = deepcopy(exported); changed['envelope']['operation'] = 'TOMBSTONE'
    with pytest.raises(ValueError, match='OPERATION'): receive(b, changed)
    assert not b.service.records(b.ctx)['inbox']


def test_cross_project_or_path_shaped_source_rejected_before_repository_read(pair, monkeypatch):
    a, b = pair; calls = []
    monkeypatch.setattr(a.chapters, 'get', lambda cid: calls.append(cid))
    for cid in [b.cid, '../other:1', a.nid + ':../1', '/tmp/not-a-project:1']:
        with pytest.raises(FileNotFoundError): a.service._chapter(a.ctx, cid)
    assert calls == []


def selection(e, *, add=(), withdraw=(), preview=None):
    body = {'expected_version': channel(e)['version'], 'add_chapter_ids': list(add), 'withdraw_chapter_ids': list(withdraw)}
    plan = preview or e.service.preview_selection(e.ctx, e.channel['id'], body)
    return e.service.change_selection(e.ctx, e.channel['id'], {**body, 'preview_digest': plan['preview_digest'], 'confirmed': True})


def test_selective_withdrawal_fences_queued_export_duplicate_receive_review_and_apply(pair):
    a, b = pair; edit(a, 'Candidate before withdrawal'); outgoing = export(a, queue(a)); inbox = receive(b, outgoing); plan = review(b, inbox)
    before = deepcopy(b.chapters.get(b.cid)); old_base = deepcopy(channel(b)['baseline']); historical = deepcopy(outgoing['envelope'])
    selection(a, withdraw=[a.cid]); selection(b, withdraw=[b.cid])
    assert channel(a)['status'] == channel(b)['status'] == 'ACTIVE'
    assert channel(b)['baseline'] == old_base and not channel(b)['chapter_ids']
    with pytest.raises(ValueError, match='SELECTION_REVOKED'): a.service.inspect_outbox(a.ctx, outgoing['id'])
    with pytest.raises(ValueError, match='SELECTION_REVOKED'): export(a, outgoing)
    with pytest.raises(ValueError, match='NOT_SELECTED'): queue(a)
    with pytest.raises(ValueError, match='SELECTION_REVOKED'): receive(b, outgoing)
    # A bound withdrawn source cannot bypass withdrawal through new-chapter mode.
    changed = deepcopy(outgoing); changed['envelope']['message_id'] = uuid4().hex; changed['envelope']['sequence'] += 1
    with pytest.raises(ValueError, match='SELECTION_REVOKED'): receive(b, changed, target_chapter_id=None, create_new=True)
    with pytest.raises(CapabilityVersionConflict): review(b, inbox)
    with pytest.raises(CapabilityVersionConflict): apply(b, inbox, plan)
    raw = b.service._owned(b.ctx, b.service.INBOX, inbox['id'])
    assert raw['status'] == 'SELECTION_REVOKED' and raw['selection_withdrawn']
    assert raw['envelope'] == historical and b.chapters.get(b.cid) == before
    assert outgoing['envelope'] == historical  # exported bytes are never recalled
    with pytest.raises(ValueError, match='SELECTION_REVOKED'): selection(b, add=[b.cid])


def test_new_selection_requires_fresh_reviewed_immutable_baseline_and_keeps_other_selection(pair):
    a, b = pair
    original = deepcopy(channel(a)['baseline'][a.cid]); extra = a.chapters.create(a.nid, {'title': 'New selected', 'content': 'Fresh seed'})
    request = {'expected_version': channel(a)['version'], 'add_chapter_ids': [extra['id']], 'withdraw_chapter_ids': []}
    plan = a.service.preview_selection(a.ctx, a.channel['id'], request)
    assert plan['additions'][0]['id'] == extra['id'] and extra['id'] not in channel(a)['chapter_ids']
    chapter = a.chapters.get(extra['id']); a.chapters.save(extra['id'], {'version': chapter['version'], 'document': doc('Changed since baseline preview')})
    with pytest.raises(StaleSourceError, match='SELECTION_REVIEW_CHANGED'): selection(a, add=[extra['id']], preview=plan)
    selection(a, add=[extra['id']]); frozen = deepcopy(channel(a)['baseline'][extra['id']]); selection(a, withdraw=[a.cid])
    assert channel(a)['chapter_ids'] == [extra['id']] and channel(a)['baseline'][a.cid] == original
    extra_current = a.chapters.get(extra['id']); a.chapters.save(extra['id'], {'version': extra_current['version'], 'document': doc('Next change')})
    sent = export(a, queue(a, chapter_id=extra['id']))
    assert sent['envelope']['base'] == frozen and sent['envelope']['snapshot']['document'] == doc('Next change')
    assert channel(a)['baseline'][extra['id']] == frozen


def test_selection_version_fence_and_invalid_changes_leave_channel_unchanged(pair):
    a, b = pair; before = deepcopy(channel(a)); request = {'expected_version': before['version'], 'withdraw_chapter_ids': [a.cid]}
    plan = a.service.preview_selection(a.ctx, a.channel['id'], request); queue(a)
    with pytest.raises(CapabilityVersionConflict):
        a.service.change_selection(a.ctx, a.channel['id'], {**request, 'preview_digest': plan['preview_digest'], 'confirmed': True})
    for extra in [{}, {'withdraw_chapter_ids': [a.cid, a.cid]}, {'add_chapter_ids': [a.cid]}, {'add_chapter_ids': [b.cid]}, {'withdraw_chapter_ids': [b.cid]}, {'add_chapter_ids': [a.cid], 'withdraw_chapter_ids': [a.cid]}]:
        current = deepcopy(channel(a))
        with pytest.raises((ValueError, FileNotFoundError)):
            a.service.preview_selection(a.ctx, a.channel['id'], {'expected_version': current['version'], **extra})
        assert channel(a) == current
    assert channel(a)['baseline'] == before['baseline']


def test_withdrawal_between_claim_and_dispatch_stops_original_write(pair, monkeypatch):
    from contextlib import contextmanager
    a, b = pair; edit(a, 'Not written'); inbox = receive(b, export(a, queue(a))); plan = review(b, inbox)
    original_transaction = b.store.transaction; armed = [True]; calls = []
    @contextmanager
    def transaction(nid, scope):
        with original_transaction(nid, scope) as state: yield state
        if armed[0]:
            armed[0] = False
            selection(b, withdraw=[b.cid])
    monkeypatch.setattr(b.store, 'transaction', transaction)
    with pytest.raises(ValueError, match='SELECTION_REVOKED'):
        apply(b, inbox, plan, save_document=lambda *args: calls.append(args))
    assert calls == [] and b.chapters.get(b.cid)['document'] == doc()
    unknown = b.service._owned(b.ctx, b.service.INBOX, inbox['id'])
    assert unknown['status'] == 'UNKNOWN' and unknown['selection_withdrawn']
    observed = b.service.recover(b.ctx, inbox['id'], {'expected_version': unknown['version']})
    assert observed['selection_withdrawn'] and not observed['can_adopt']
    closed = b.service.recover(b.ctx, inbox['id'], {'expected_version': unknown['version'], 'close_without_replay': True, 'preview_digest': observed['preview_digest']})
    assert closed['status'] == 'CLOSED_WITHOUT_REPLAY'


def test_selection_withdrawal_serializes_with_started_original_write(pair):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    a, b = pair; edit(a, 'Started write'); inbox = receive(b, export(a, queue(a))); plan = review(b, inbox)
    entered, release, attempting, withdrew = Event(), Event(), Event(), Event()
    def write(cid, document, version, source):
        entered.set(); assert release.wait(10)
        return b.chapters.save(cid, {'version': version, 'document': document, 'source': source})
    def withdraw():
        attempting.set(); result = selection(b, withdraw=[b.cid]); withdrew.set(); return result
    with ThreadPoolExecutor(max_workers=2) as pool:
        writing = pool.submit(apply, b, inbox, plan, save_document=write)
        try:
            assert entered.wait(10); withdrawing = pool.submit(withdraw); assert attempting.wait(10)
            assert not withdrew.wait(.1)  # cannot revoke ahead of an already fenced dispatch
        finally: release.set()
        assert writing.result(timeout=10)['status'] == 'APPLIED'
        assert withdrawing.result(timeout=10)['withdrawn_chapter_ids'] == [b.cid]
    assert b.chapters.get(b.cid)['document'] == doc('Started write')
    with pytest.raises(ValueError, match='SELECTION_REVOKED'): receive(b, export(a, queue(a)))


def test_unknown_matching_result_cannot_be_adopted_after_selection_withdrawal(pair):
    a, b = pair; edit(a, 'Unknown written result'); inbox = receive(b, export(a, queue(a))); plan = review(b, inbox)
    def lost(cid, document, version, source):
        b.chapters.save(cid, {'version': version, 'document': document, 'source': source}); raise RuntimeError('lost receipt')
    with pytest.raises(RuntimeError): apply(b, inbox, plan, save_document=lost)
    selection(b, withdraw=[b.cid]); unknown = b.service._owned(b.ctx, b.service.INBOX, inbox['id'])
    result = b.service.recover(b.ctx, inbox['id'], {'expected_version': unknown['version']})
    assert result['observations'][0]['state'] == 'MATCHES_INTENT_UNCONFIRMED' and not result['can_adopt']
    with pytest.raises(StaleSourceError):
        b.service.recover(b.ctx, inbox['id'], {'expected_version': unknown['version'], 'adopt_matching_result': True, 'preview_digest': result['preview_digest']})
    assert b.chapters.get(b.cid)['document'] == doc('Unknown written result')


def test_sync_reads_never_mutate_original_chapter_authority(pair, monkeypatch):
    a, b = pair
    if a.store.backend != 'file':
        before = deepcopy(a.chapters.get(a.cid)); outgoing = queue(a)
        a.service.catalog(a.ctx); a.service.inspect_outbox(a.ctx, outgoing['id']); export(a, outgoing)
        assert a.chapters.get(a.cid) == before
        return
    legacy = a.chapters.create(a.nid, {'title': 'Legacy original', 'content': 'Original Markdown bytes'})
    repo = a.chapters.repository; root = repo.backend.novels / a.nid
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    def forbidden(*args, **kwargs): raise AssertionError('sync read must not materialize original packages')
    monkeypatch.setattr(a.chapters, 'get', forbidden); monkeypatch.setattr(a.chapters, 'list', forbidden)
    assert legacy['id'] in [r['id'] for r in a.service.catalog(a.ctx)['chapters']]
    selection(a, add=[legacy['id']]); outgoing = queue(a, chapter_id=legacy['id']); a.service.inspect_outbox(a.ctx, outgoing['id']); export(a, outgoing)
    assert a.service._chapter(a.ctx, legacy['id'])['version'] == 1
    assert {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()} == before
    assert not repo._paths(legacy['id'])[2].exists()


def test_added_selection_respects_reserved_new_chapter_capacity(pair):
    a, b = pair; inbox = receive(b, export(a, queue(a)), target_chapter_id=None, create_new=True)
    extras = [b.chapters.create(b.nid, {'title': f'Extra {index}', 'content': 'Synthetic bounded baseline'})['id'] for index in range(19)]
    selection(b, add=extras[:18])
    with pytest.raises(ValueError, match='SELECTION_LIMIT'): selection(b, add=extras[18:])
    assert len(channel(b)['baseline']) == 19
    apply(b, inbox, review(b, inbox)); assert len(channel(b)['baseline']) == 20


def test_unknown_created_chapter_selected_separately_cannot_overwrite_its_fresh_baseline(pair):
    a, b = pair; edit(a, 'New chapter candidate'); inbox = receive(b, export(a, queue(a)), target_chapter_id=None, create_new=True); plan = review(b, inbox)
    created = []
    def lost(*args):
        created.append(create_writer(b, *args)); raise RuntimeError('lost creation receipt')
    with pytest.raises(RuntimeError): apply(b, inbox, plan, create_chapter=lost)
    unknown = b.service._owned(b.ctx, b.service.INBOX, inbox['id'])
    selection(b, add=[created[0]['id']]); frozen = deepcopy(channel(b)['baseline'][created[0]['id']])
    result = b.service.recover(b.ctx, inbox['id'], {'expected_version': unknown['version']})
    assert not result['can_adopt'] and result['target_already_selected']
    with pytest.raises(StaleSourceError):
        b.service.recover(b.ctx, inbox['id'], {'expected_version': unknown['version'], 'adopt_matching_result': True, 'preview_digest': result['preview_digest']})
    assert channel(b)['baseline'][created[0]['id']] == frozen
    assert channel(b)['chapter_ids'].count(created[0]['id']) == 1


def test_manual_close_between_claim_and_dispatch_is_not_replayed_or_reopened(pair, monkeypatch):
    from contextlib import contextmanager
    a, b = pair; edit(a, 'Do not replay closed candidate'); inbox = receive(b, export(a, queue(a))); plan = review(b, inbox)
    original_transaction = b.store.transaction; armed = [True]; calls = []
    @contextmanager
    def transaction(nid, scope):
        with original_transaction(nid, scope) as state: yield state
        if armed[0]:
            armed[0] = False
            claimed = b.service._owned(b.ctx, b.service.INBOX, inbox['id'])
            result = b.service.recover(b.ctx, inbox['id'], {'expected_version': claimed['version']})
            b.service.recover(b.ctx, inbox['id'], {'expected_version': claimed['version'], 'close_without_replay': True, 'preview_digest': result['preview_digest']})
    monkeypatch.setattr(b.store, 'transaction', transaction)
    with pytest.raises(CapabilityVersionConflict): apply(b, inbox, plan, save_document=lambda *args: calls.append(args))
    assert calls == [] and b.chapters.get(b.cid)['document'] == doc()
    assert b.service._owned(b.ctx, b.service.INBOX, inbox['id'])['status'] == 'CLOSED_WITHOUT_REPLAY'
