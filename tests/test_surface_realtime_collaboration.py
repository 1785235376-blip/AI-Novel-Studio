"""Real mounted APIs, original File/opt-in PostgreSQL storage and authorization.

The only synthetic component is the explicitly named push transport. No fake
SQL sessions, altered existing assertions, production deployment or model calls.
"""
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from app.experimental.flags import RUNTIME_FLAGS as FLAGS
from app.experimental.planning import digest
from app.experimental.ux import ReadContext
from app.experimental.writer_room_realtime import RealtimeCollaboration
from app.services.branch_manuscript_service import BranchManuscriptService
from test_r3_mounted_contracts import mounted, prefix, scoped, checked


@pytest.fixture(autouse=True)
def explicit_surface_opt_in(request, monkeypatch):
    # Historical mounted fixtures deliberately enable only their frozen flags.
    if 'mounted' in request.fixturenames: request.getfixturevalue('mounted')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))


def rt(e): return e.base + '/writer-room/realtime'
def headers(e): return getattr(e, 'headers', {})
def context(e): return ReadContext(e.nid, e.scope, getattr(e, 'lead', 'local-author'), getattr(e, 'lead', None), getattr(e, 'branch', None))
def join(e, chapter=None, device=None):
    chapter = chapter or e.chapter
    return checked(e.client.post(rt(e) + '/participants', headers=headers(e), json={
        'device_id': device or uuid4().hex, 'chapter_id': chapter['id'], 'document_version': chapter['version']}), 201)

def edit_body(participant, chapter, text='Open', **extra):
    # Test chapters below always contain one paragraph text node.
    return {'participant_id': participant['id'], 'participant_version': participant['version'], 'request_id': uuid4().hex,
        'document_version': chapter['version'], 'document_digest': digest(chapter['document']),
        'edits': [{'path': [0, 0], 'start': 0, 'end': 0, 'text': text}], **extra}

def prepare(e, participant, chapter=None, **kwargs):
    return checked(e.client.post(rt(e) + '/operations', headers=headers(e), json=edit_body(participant, chapter or e.chapter, **kwargs)), 201)

def act(e, row, action, **kwargs):
    return e.client.post(rt(e) + '/operations/' + row['id'] + '/actions', headers=headers(e),
        json={'expected_version': row['version'], 'action': action, **kwargs})


def test_realtime_actual_push_cursor_selection_and_original_mainline_history(mounted):
    e = mounted; participant = join(e); service = e.experimental.writer_room_service.realtime; events = []
    contract = checked(e.client.get(rt(e)))
    assert contract['state'] == 'PARTIAL' and contract['production_server'] == 'NOT_CONFIGURED'
    assert not contract['polling_is_realtime'] and contract['http_reads'] == 'SNAPSHOT_ONLY'
    unsubscribe = service.subscribe(context(e), participant['id'], events.append)
    body = {'expected_version': participant['version'], 'document_version': e.chapter['version'],
        'anchor': {'path': [0, 0], 'offset': 0}, 'focus': {'path': [0, 0], 'offset': 2}}
    participant = checked(e.client.put(rt(e) + '/participants/' + participant['id'] + '/cursor', json=body))
    assert events[-1]['kind'] == 'CURSOR_CHANGED' and events[-1]['cursor'] == {'anchor': body['anchor'], 'focus': body['focus']}
    operation = prepare(e, participant, text='Synthetic live edit ')
    assert operation['status'] == 'PREPARED' and e.chapters.get(e.chapter['id']) == e.chapter
    done = checked(act(e, operation, 'apply'))
    assert done['status'] == 'APPLIED' and done['result_version'] == e.chapter['version'] + 1
    assert events[-1]['kind'] == 'DOCUMENT_COMMITTED' and events[-1]['edits'][0]['text'] == 'Synthetic live edit '
    assert any(r['document'] == e.chapter['document'] for r in e.chapters.history(e.chapter['id']))
    assert act(e, operation, 'apply').status_code == 409
    assert e.client.get(rt(e) + '/participants').headers['cache-control'] == 'no-store'
    unsubscribe()


def test_realtime_stale_conflict_preserves_candidates_and_cancel(mounted):
    e = mounted; participant = join(e)
    body = edit_body(participant, e.chapter, document_digest='0' * 64)
    conflict = checked(e.client.post(rt(e) + '/operations', json=body), 201)
    assert conflict['status'] == 'CONFLICT' and conflict['candidates_preserved']
    inspect = checked(e.client.get(rt(e) + '/operations/' + conflict['id']))
    assert inspect['current_document'] == e.chapter['document'] and inspect['edits'] == body['edits']
    assert act(e, conflict, 'apply').status_code == 422
    cancelled = checked(act(e, conflict, 'cancel'))
    assert cancelled['status'] == 'CANCELLED' and act(e, cancelled, 'apply').status_code == 422
    assert e.chapters.get(e.chapter['id']) == e.chapter
    assert checked(e.client.post(rt(e) + '/operations', json=body), 201)['id'] == conflict['id']
    body['edits'][0]['text'] = 'different'
    assert e.client.post(rt(e) + '/operations', json=body).status_code == 422


def test_realtime_disconnect_expiry_restart_reconnect_and_terminal_revocation(mounted, monkeypatch):
    e = mounted; service = e.experimental.writer_room_service.realtime; participant = join(e); ctx = context(e)
    operation = prepare(e, participant)
    disconnected = checked(e.client.post(rt(e) + '/participants/' + participant['id'] + '/actions', json={
        'expected_version': participant['version'], 'action': 'disconnect'}))
    assert act(e, operation, 'apply').status_code == 422
    fresh = RealtimeCollaboration(e.experimental.writer_room_service)
    monkeypatch.setattr(e.experimental.writer_room_service, '_realtime', fresh)
    participant = checked(e.client.post(rt(e) + '/participants/' + participant['id'] + '/actions', json={
        'expected_version': disconnected['version'], 'action': 'reconnect', 'document_version': e.chapter['version']}))
    assert participant['status'] == 'ACTIVE' and participant['cursor'] is None
    monkeypatch.setattr(fresh, 'clock', lambda: participant['lease_until'] + 1)
    assert fresh.presence(ctx)['items'][0]['status'] == 'EXPIRED'
    assert act(e, operation, 'apply').status_code == 422
    monkeypatch.setattr(fresh, 'clock', lambda: participant['lease_until'] - 1)
    revoked = checked(e.client.post(rt(e) + '/participants/' + participant['id'] + '/actions', json={
        'expected_version': participant['version'], 'action': 'revoke'}))
    assert revoked['status'] == 'REVOKED'
    assert e.client.post(rt(e) + '/participants/' + participant['id'] + '/actions', json={
        'expected_version': revoked['version'], 'action': 'reconnect', 'document_version': e.chapter['version']}).status_code == 422
    assert act(e, operation, 'apply').status_code == 422


def test_realtime_unknown_external_write_never_replayed_manual_recovery(mounted, monkeypatch):
    e = mounted; participant = join(e); operation = prepare(e, participant)
    old_save = e.chapters.save; calls = []
    def lost(*args, **kwargs):
        calls.append(1); old_save(*args, **kwargs); raise RuntimeError('Synthetic receipt loss')
    monkeypatch.setattr(e.chapters, 'save', lost)
    with pytest.raises(RuntimeError, match='receipt loss'): act(e, operation, 'apply')
    unknown = checked(e.client.get(rt(e) + '/operations/' + operation['id']))
    assert unknown['status'] == 'UNKNOWN' and len(calls) == 1
    fresh = RealtimeCollaboration(e.experimental.writer_room_service)
    monkeypatch.setattr(e.experimental.writer_room_service, '_realtime', fresh)
    assert act(e, unknown, 'apply').status_code == 422
    recovery = checked(act(e, unknown, 'inspect_recovery'))
    assert recovery['can_adopt'] and not recovery['retry_allowed']
    adopted = checked(act(e, unknown, 'adopt', recovery_digest=recovery['recovery_digest']))
    assert adopted['status'] == 'ADOPTED' and len(calls) == 1


def branch_setup(e, monkeypatch):
    e = scoped(e, monkeypatch)
    authority = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.experimental.writer_room_service, 'branch_documents', authority, raising=False)
    e.branch_authority = authority
    e.branch_chapter = authority.create(context(e), {'title': 'Scoped chapter', 'content': 'Branch-owned words'})
    return e


def test_realtime_atomic_branch_authority_scope_permissions_and_rollback(mounted, monkeypatch):
    e = branch_setup(mounted, monkeypatch); participant = join(e, e.branch_chapter); operation = prepare(e, participant, e.branch_chapter)
    assert e.client.post(rt(e) + '/operations', headers=e.viewer_headers, json=edit_body(participant, e.branch_chapter)).status_code == 403
    other_headers = {**e.headers, 'X-Branch-ID': e.other_branch}
    assert e.client.get(rt(e) + '/operations/' + operation['id'], headers=other_headers).status_code in {403, 404}
    done = checked(act(e, operation, 'apply'))
    assert done['status'] == 'APPLIED' and done['version'] == 2  # one shared atomic commit, no external claim phase
    assert e.branch_authority.read(context(e), e.branch_chapter['id'])['version'] == 2
    assert e.chapters.get(e.chapter['id']) == e.chapter
    # A final permission failure rolls back BOTH manuscript and journal.
    chapter = e.branch_authority.read(context(e), e.branch_chapter['id'])
    op = prepare(e, participant, chapter)
    service = e.experimental.writer_room_service.realtime
    finish = service._finish
    def revoked(*args, **kwargs):
        finish(*args, **kwargs)
        raise HTTPException(403, 'Synthetic permission revoked before scope commit')
    monkeypatch.setattr(service, '_finish', revoked)
    assert act(e, op, 'apply').status_code == 403
    assert e.branch_authority.read(context(e), chapter['id']) == chapter
    assert checked(e.client.get(rt(e) + '/operations/' + op['id'], headers=e.headers))['status'] == 'PREPARED'


def test_realtime_push_authorization_and_cross_document_fence(mounted, monkeypatch):
    e = branch_setup(mounted, monkeypatch); participant = join(e, e.branch_chapter)
    service = e.experimental.writer_room_service.realtime; events = []; allowed = [True]
    def guard():
        if not allowed[0]: raise HTTPException(403, 'revoked')
    service.subscribe(context(e), participant['id'], events.append, guard)
    another = e.branch_authority.create(context(e), {'title': 'Other document', 'content': 'Other words'})
    other = join(e, another); prepare(e, other, another)
    assert events == []
    allowed[0] = False
    prepare(e, participant, e.branch_chapter)
    assert events == []
    assert not service.transport._subscribers
    e.sessions.revoke(e.lead)
    assert e.client.get(rt(e) + '/participants', headers=e.headers).status_code == 401


@pytest.mark.parametrize('configuration', ['', '*', 'realtime_collaboration_v1', 'V1'])
def test_realtime_feature_flag_fail_closed(mounted, monkeypatch, configuration):
    if configuration == 'V1': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', configuration)
    assert mounted.client.get(rt(mounted)).status_code == 404


def test_realtime_rejects_invalid_position_and_strict_body_without_content_mutation(mounted):
    e = mounted; participant = join(e)
    body = edit_body(participant, e.chapter); body['edits'][0]['path'] = [999999]
    assert e.client.post(rt(e) + '/operations', json=body).status_code == 422
    body = edit_body(participant, e.chapter); body['edits'][0]['start'] = True
    assert e.client.post(rt(e) + '/operations', json=body).status_code == 422
    body = edit_body(participant, e.chapter); body['grant_permission'] = True
    assert e.client.post(rt(e) + '/operations', json=body).status_code == 422
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_realtime_concurrent_branch_operations_have_single_CAS_winner_and_preserved_loser(mounted, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    e = branch_setup(mounted, monkeypatch); first = join(e, e.branch_chapter); second = join(e, e.branch_chapter)
    operations = [prepare(e, first, e.branch_chapter, text='First '), prepare(e, second, e.branch_chapter, text='Second ')]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda op: act(e, op, 'apply'), operations))
    assert sorted(r.status_code for r in replies) == [200, 409]
    chapter = e.branch_authority.read(context(e), e.branch_chapter['id'])
    assert chapter['version'] == 2
    retained = [checked(e.client.get(rt(e) + '/operations/' + op['id'], headers=e.headers)) for op in operations]
    assert sorted(r['status'] for r in retained) == ['APPLIED', 'PREPARED']
    assert {r['edits'][0]['text'] for r in retained} == {'First ', 'Second '}
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_realtime_restart_disconnects_live_presence_and_rechecks_revoked_session_lease(mounted, monkeypatch):
    e = branch_setup(mounted, monkeypatch); participant = join(e, e.branch_chapter)
    service = e.experimental.writer_room_service.realtime
    fresh = RealtimeCollaboration(e.experimental.writer_room_service)
    assert fresh.presence(context(e))['items'][0]['status'] == 'DISCONNECTED'
    # Another still-authorized participant must see the revoked session as
    # revoked immediately, rather than fabricated active until lease expiry.
    e.sessions.revoke(e.lead)
    viewer_ctx = replace(context(e), actor=e.viewer, token=e.viewer)
    assert service.presence(viewer_ctx)['items'][0]['status'] == 'REVOKED'


def test_realtime_source_version_changes_preserve_review_and_fail_closed(mounted):
    e = mounted; participant = join(e); operation = prepare(e, participant)
    current = deepcopy(e.chapter['document']); current['content'][0]['content'][0]['text'] += ' Other authoritative edit'
    e.chapters.save(e.chapter['id'], {'version': e.chapter['version'], 'document': current})
    assert act(e, operation, 'apply').status_code == 409
    assert checked(e.client.get(rt(e) + '/operations/' + operation['id']))['status'] == 'PREPARED'
    assert e.client.put(rt(e) + '/participants/' + participant['id'] + '/cursor', json={
        'expected_version': participant['version'], 'document_version': e.chapter['version'],
        'anchor': {'path': [0, 0], 'offset': 0}, 'focus': {'path': [0, 0], 'offset': 1}}).status_code == 409
    assert e.chapters.get(e.chapter['id'])['document'] == current


def test_realtime_bounded_strict_json_and_journal_rollback(mounted, monkeypatch):
    import app.experimental.writer_room_realtime as realtime_module
    e = mounted; participant = join(e)
    assert e.client.post(rt(e) + '/participants', content='x' * (512 * 1024 + 1)).status_code == 413
    assert e.client.post(rt(e) + '/participants', content='{"device_id":"one","device_id":"two"}').status_code == 422
    monkeypatch.setattr(realtime_module, 'MAX_OPERATIONS', 0)
    assert e.client.post(rt(e) + '/operations', json=edit_body(participant, e.chapter)).status_code == 422
    assert not e.store.read(e.nid, e.scope)['collections'].get(realtime_module.RealtimeCollaboration.OPERATIONS)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert e.client.post(rt(e) + '/operations', json={}).status_code == 404
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_realtime_revision_lock_blocks_prepare_without_manuscript_or_journal_write(mounted):
    from app.revision_constraints import LOCK_ATTRIBUTE, node_digest
    e = mounted; locked = deepcopy(e.chapter['document']); node = locked['content'][0]
    node.setdefault('attrs', {})[LOCK_ATTRIBUTE] = {'id': 'synthetic-lock', 'state': 'LOCKED', 'digest': node_digest(node)}
    chapter = e.chapters.save(e.chapter['id'], {'version': e.chapter['version'], 'document': locked})
    participant = join(e, chapter)
    assert e.client.post(rt(e) + '/operations', json=edit_body(participant, chapter)).status_code == 409
    assert e.chapters.get(e.chapter['id']) == chapter
    assert not e.store.read(e.nid, e.scope)['collections'].get(RealtimeCollaboration.OPERATIONS)
