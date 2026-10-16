"""B08 real composed File and opted-in real PostgreSQL contracts. No auth stubs."""
import base64
import copy
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from test_r3_mounted_contracts import mounted, prefix, scoped, checked, planning_proposal
from app.actor_context import SessionContext
from app.authorization import AuthorizationScope, ScopeKind, ModalityDomain, PermissionAssignment
from app.experimental.flags import FLAGS
from app.experimental.store import ExperimentalStore
from app.identity import IdentityStatus


def room(e): return e.base + '/writer-room'

def task_body(e, title='Review synthetic gate', **extra):
    return {'title': title, 'description': 'Versioned team task', 'assignee': getattr(e, 'lead', 'local-author'),
            'reviewer': getattr(e, 'lead', 'local-author'), 'request_id': uuid4().hex, **extra}


def create_task(e, **extra):
    return checked(e.client.post(room(e) + '/tasks', headers=getattr(e, 'headers', {}), json=task_body(e, **extra)), 201)


def fields(row): return {k: row[k] for k in ('title', 'description', 'assignee', 'reviewer')}

def transition(e, row, action, note='', headers=None):
    return checked(e.client.post(room(e) + f'/tasks/{row["id"]}/transition', headers=headers or getattr(e, 'headers', {}),
                                json={'expected_version': row['version'], 'action': action, 'note': note}))


def test_writer_room_actual_local_read_comments_assignment_change_requests_and_original_inbox(mounted):
    e = mounted; original = copy.deepcopy(e.chapters.get(e.chapter['id']))
    e.canon.save_pending({'id': str(uuid4()), 'novel_id': e.nid, 'status': 'PENDING', 'proposals': [{'subject': 'Gate', 'predicate': 'has', 'object': 'one entrance'}]})
    catalog = checked(e.client.get(room(e) + '/catalog'))
    assert all(isinstance(r['preview'], str) for r in catalog['review_targets'])
    assert any(r['domain'] == 'legacy_canon' and r['preview'] == '原领域结构化审核项' for r in catalog['review_targets'])
    source = catalog['chapters'][0]; ref = {k: source[k] for k in ('id', 'revision')}
    read = checked(e.client.get(room(e) + '/chapters/' + source['id'], params={'revision': source['revision']}))
    assert read['mode'] == 'READ_ONLY' and 'Alice' in read['text']
    graph, proposal = planning_proposal(e, with_sources=True)
    target = {'domain': 'planning', 'id': proposal['id'], 'version': 1}
    task = create_task(e, chapter=ref, review_target=target)
    task = transition(e, task, 'start'); task = transition(e, task, 'submit')
    task = transition(e, task, 'request_changes', 'Clarify the gate motive')
    assert task['status'] == 'CHANGES_REQUESTED' and task['events'][-1]['note'] == 'Clarify the gate motive'
    task = transition(e, task, 'start'); task = transition(e, task, 'submit'); task = transition(e, task, 'close')
    assert task['status'] == 'CLOSED' and task['domain_acceptance'] == 'ORIGINAL_DOMAIN_ONLY'
    assert checked(e.client.get(e.base + '/planning/proposals/' + proposal['id']))['status'] == 'REVIEW'
    comment = checked(e.client.post(room(e) + '/comments', json={'chapter_id': source['id'], 'chapter_version': source['version'], 'quote': 'Alice', 'text': 'Synthetic version comment'}), 201)
    legacy = checked(e.client.get(e.prefix + f'/novels/{e.nid}/review-threads'))['items']
    assert any(r['id'] == comment['id'] for r in legacy)
    replied = checked(e.client.post(room(e) + '/comments/' + comment['id'], json={'expected_version': 1, 'action': 'reply', 'text': 'Addressed in pending draft'}))
    resolved = checked(e.client.post(room(e) + '/comments/' + comment['id'], json={'expected_version': replied['version'], 'action': 'resolve'}))
    assert resolved['status'] == 'RESOLVED'
    reopened = checked(e.client.post(room(e) + '/comments/' + comment['id'], json={'expected_version': resolved['version'], 'action': 'reopen'}))
    assert reopened['status'] == 'OPEN'
    assert e.chapters.get(e.chapter['id']) == original
    assert e.client.get(room(e)).headers['cache-control'] == 'no-store'


def test_writer_room_two_independent_trusted_clients_preserve_conflict_candidates_and_resolve(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); task = create_task(e)
    token = 'second-' + uuid4().hex
    e.sessions.register(token, SessionContext('second-session', 'second-client', e.lead, e.workspace))
    clients = [TestClient(e.main.app), TestClient(e.main.app)]
    headers = [e.headers, {'X-Session-Token': token, 'X-Branch-ID': e.branch}]
    candidates = [{**fields(task), 'expected_version': 1, 'description': label} for label in ('Client A complete candidate', 'Client B complete candidate')]
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda i: clients[i].put(room(e) + '/tasks/' + task['id'], headers=headers[i], json=candidates[i]), (0, 1)))
        assert sorted(r.status_code for r in responses) == [200, 409]
        winner = next(r.json() for r in responses if r.status_code == 200)
        error = next(r.json() for r in responses if r.status_code == 409)
        assert error['detail']['candidates_preserved'] is True
        conflict = checked(e.client.get(room(e) + '/conflicts', headers=e.headers))['items'][0]
        assert {conflict['current_candidate']['description'], conflict['submitted_candidate']['description']} == {c['description'] for c in candidates}
        fresh_store = ExperimentalStore(e.root, e.backend, e.url)
        persisted = fresh_store.read(e.nid, e.scope)['collections']['writer_room_conflicts_v2'][conflict['id']]
        assert persisted['submitted_candidate'] == conflict['submitted_candidate']
        accepted = checked(e.client.put(room(e) + '/tasks/' + task['id'], headers=e.headers, json={**fields(conflict['submitted_candidate']), 'expected_version': winner['version'], 'resolve_conflict_id': conflict['id']}))
        assert accepted['version'] == 3 and accepted['description'] == conflict['submitted_candidate']['description']
        conflict2 = checked(e.client.get(room(e) + '/conflicts', headers=e.headers))['items'][0]
        assert conflict2['status'] == 'RESOLVED' and conflict2['current_candidate'] == conflict['current_candidate']
    finally:
        for client in clients: client.close()


def test_writer_room_reuses_original_comment_CAS_and_preserves_rejected_reply(mounted):
    e = mounted
    comment = checked(e.client.post(room(e) + '/comments', json={'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'], 'text': 'First note'}), 201)
    first = checked(e.client.post(room(e) + '/comments/' + comment['id'], json={'expected_version': 1, 'action': 'reply', 'text': 'First client reply'}))
    second = e.client.post(room(e) + '/comments/' + comment['id'], json={'expected_version': 1, 'action': 'reply', 'text': 'Second client preserved reply'})
    assert second.status_code == 409
    conflicts = checked(e.client.get(room(e) + '/conflicts'))['items']
    assert conflicts[0]['target'] == {'kind': 'comment', 'id': comment['id']}
    assert conflicts[0]['current_candidate']['messages'][-1]['text'] == 'First client reply'
    assert conflicts[0]['submitted_candidate']['text'] == 'Second client preserved reply'
    retried = checked(e.client.post(room(e) + '/comments/' + comment['id'], json={'expected_version': first['version'], 'action': 'reply', 'text': 'Second client preserved reply'}))
    assert len(retried['messages']) == 3


def test_writer_room_collaboration_fails_closed_for_unscoped_chapters_and_branch_separation(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); task = create_task(e)
    catalog = checked(e.client.get(room(e) + '/catalog', headers=e.headers))
    assert catalog['chapter_state'] == 'BRANCH_SOURCE_UNAVAILABLE' and catalog['chapters'] == []
    assert checked(e.client.get(room(e) + '/comments', headers=e.headers))['items'] == []
    assert e.client.post(room(e) + '/comments', headers=e.headers, json={'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version'], 'text': 'Must not reach base chapter'}).status_code == 404
    assert e.client.get(room(e)).status_code == 401
    assert e.client.get(room(e), headers={'X-Session-Token': 'untrusted', 'X-Branch-ID': e.branch}).status_code == 401
    assert e.client.get(room(e), headers={'X-Session-Token': e.lead}).status_code == 400
    other = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.other_branch)
    for permission in ('domain.read', 'domain.write', 'domain.review'):
        e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, permission, ModalityDomain.NOVEL, other, e.lead))
    other_headers = {**e.headers, 'X-Branch-ID': e.other_branch}
    assert checked(e.client.get(room(e), headers=other_headers))['items'] == []
    assert e.client.put(room(e) + '/tasks/' + task['id'], headers=other_headers, json={**fields(task), 'expected_version': 1}).status_code == 404


def test_writer_room_readonly_member_no_grants_and_current_revocation_across_all_surfaces(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); task = create_task(e)
    before_permissions = e.authorization.repository.list_permission_assignments(e.viewer)
    overview = checked(e.client.get(room(e), headers=e.viewer_headers))
    assert not overview['can_write'] and not overview['can_review']
    assert overview['items'][0]['id'] == task['id']
    assert e.client.post(room(e) + '/tasks', headers=e.viewer_headers, json=task_body(e)).status_code == 403
    assert e.client.post(room(e) + '/tasks', headers=e.headers, json=task_body(e, assignee=e.viewer)).status_code == 403
    assert e.authorization.repository.list_permission_assignments(e.viewer) == before_permissions
    e.identity.set_membership_status(e.viewer, e.workspace, IdentityStatus.INACTIVE)
    for path in ('', '/catalog', '/index?query=Review', '/notices', '/conflicts', '/comments'):
        response = e.client.get(room(e) + path, headers=e.viewer_headers)
        assert response.status_code == 403, (path, response.text)
        assert 'Review synthetic gate' not in response.text
    e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
    assert e.client.post(room(e) + f'/tasks/{task["id"]}/transition', headers=e.headers, json={'expected_version': 1, 'action': 'start'}).status_code == 403
    assert e.store.read(e.nid, e.scope)['collections']['writer_room_tasks_v2'][task['id']]['version'] == 1


def test_writer_room_review_only_responsible_actor_can_request_changes_without_manuscript_write(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    authority = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.viewer, 'domain.review', ModalityDomain.NOVEL, authority, e.lead))
    task = create_task(e, reviewer=e.viewer)
    task = transition(e, task, 'start'); task = transition(e, task, 'submit')
    assert e.client.post(room(e) + f'/tasks/{task["id"]}/transition', headers=e.headers, json={'expected_version': task['version'], 'action': 'close'}).status_code == 403
    changed = transition(e, task, 'request_changes', 'Responsible reviewer wants a revision', headers=e.viewer_headers)
    assert changed['status'] == 'CHANGES_REQUESTED'
    assert e.client.put(room(e) + f'/tasks/{task["id"]}', headers=e.viewer_headers, json={**fields(task), 'expected_version': changed['version']}).status_code == 403


def test_writer_room_selected_review_package_contains_only_selected_current_sources(mounted):
    e = mounted
    secret = checked(e.client.post(e.prefix + f'/novels/{e.nid}/chapters', json={'title': 'Unselected secret', 'content': 'UNSELECTED_SECRET_MARKER'}), 201)
    selected_asset = e.assets.create(e.nid, 'selected.txt', base64.b64encode(b'SELECTED_ASSET').decode(), 'text/plain', 'file')
    e.assets.create(e.nid, 'unselected.txt', base64.b64encode(b'UNSELECTED_ASSET_MARKER').decode(), 'text/plain', 'file')
    source = next(r for r in checked(e.client.get(room(e) + '/catalog'))['chapters'] if r['id'] == e.chapter['id'])
    selection = {'chapters': [{k: source[k] for k in ('id', 'revision')}], 'asset_ids': [selected_asset['id']]}
    preview = checked(e.client.post(room(e) + '/packages/preview', json=selection))
    assert preview['transmission'] == 'LOCAL_DOWNLOAD_ONLY' and preview['permission_change'] is False
    body = {**selection, 'preview_digest': preview['preview_digest'], 'acknowledge_copy_boundary': True}
    exported = checked(e.client.post(room(e) + '/packages/download', json=body))
    raw = base64.b64decode(exported['content_base64'])
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        assert set(archive.namelist()) == {'manifest.json', 'chapters/001.txt', 'assets/001.bin'}
        manifest = json.loads(archive.read('manifest.json'))
        assert [r['id'] for r in manifest['chapters']] == [e.chapter['id']]
        assert [r['id'] for r in manifest['assets']] == [selected_asset['id']]
        all_bytes = b''.join(archive.read(name) for name in archive.namelist())
        assert b'UNSELECTED' not in all_bytes and secret['id'].encode() not in all_bytes
        assert archive.read('assets/001.bin') == b'SELECTED_ASSET'
        assert '无法' in manifest['copy_warning']
    assert e.client.post(room(e) + '/packages/download', json={**body, 'acknowledge_copy_boundary': False}).status_code == 422
    assert e.client.post(room(e) + '/packages/preview', json={}).status_code == 422
    changed = copy.deepcopy(e.chapter['document']); changed['content'].append({'type': 'paragraph', 'content': [{'type': 'text', 'text': 'New current source'}]})
    e.chapters.save(e.chapter['id'], {'document': changed, 'version': e.chapter['version']})
    assert e.client.post(room(e) + '/packages/download', json=body).status_code == 409


def test_writer_room_index_notices_idempotency_and_restart(mounted, monkeypatch):
    e = mounted; body = task_body(e)
    task = checked(e.client.post(room(e) + '/tasks', json=body), 201)
    assert checked(e.client.post(room(e) + '/tasks', json=body), 201)['id'] == task['id']
    assert e.client.post(room(e) + '/tasks', json={**body, 'title': 'Changed request'}).status_code == 422
    monkeypatch.setattr(e.experimental.writer_room_service, 'store', ExperimentalStore(e.root, e.backend, e.url))
    assert checked(e.client.get(room(e) + '/index', params={'query': 'synthetic'}))['items'][0]['id'] == task['id']
    assert checked(e.client.get(room(e) + '/notices'))['items'][0]['task_id'] == task['id']
    assert checked(e.client.get(room(e)))['presence'] == 'NOT_IMPLEMENTED'


def test_writer_room_off_v1_dependency_gate_and_no_background_side_effects(mounted, monkeypatch):
    e = mounted; before = e.store.read(e.nid, e.scope)
    for configured, v1 in [('', 'false'), ('*', 'false'), ('writer_room_v2', 'false'), (','.join(FLAGS), 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', configured); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        for path in ('', '/catalog', '/index', '/notices', '/comments', '/conflicts'):
            assert e.client.get(room(e) + path).status_code == 404
        assert e.client.post(room(e) + '/tasks', json=task_body(e)).status_code == 404
    assert e.store.read(e.nid, e.scope) == before


def test_writer_room_revoke_during_read_and_before_task_commit_fences_results(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); service = e.experimental.writer_room_service
    original = service.overview
    def revoked(ctx):
        result = original(ctx)
        e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
        return result
    monkeypatch.setattr(service, 'overview', revoked)
    assert e.client.get(room(e), headers=e.headers).status_code == 403
    e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.ACTIVE)
    original_participants = service._participants; calls = 0
    def revoke_before_commit(ctx, assignee, reviewer):
        nonlocal calls
        calls += 1
        original_participants(ctx, assignee, reviewer)
        if calls == 2: e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
    monkeypatch.setattr(service, '_participants', revoke_before_commit)
    assert e.client.post(room(e) + '/tasks', headers=e.headers, json=task_body(e)).status_code == 403
    assert e.store.read(e.nid, e.scope)['collections'].get('writer_room_tasks_v2', {}) == {}


def test_writer_room_removed_source_withholds_derived_index_notices_and_conflicts(mounted):
    e = mounted
    source = checked(e.client.get(room(e) + '/catalog'))['chapters'][0]
    task = create_task(e, chapter={k: source[k] for k in ('id', 'revision')}, title='SOURCE_PRIVATE_MARKER')
    checked(e.client.put(room(e) + '/tasks/' + task['id'], json={**fields(task), 'description': 'First candidate', 'expected_version': 1}))
    assert e.client.put(room(e) + '/tasks/' + task['id'], json={**fields(task), 'description': 'Second candidate', 'expected_version': 1}).status_code == 409
    e.chapters.delete(e.chapter['id'])
    for path in ('', '/index?query=SOURCE_PRIVATE_MARKER', '/notices', '/conflicts'):
        response = e.client.get(room(e) + path)
        assert response.status_code == 200 and 'SOURCE_PRIVATE_MARKER' not in response.text
        assert response.json()['items'] == []


def test_writer_room_asset_package_preserves_original_asset_authority_and_revocation(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    asset = e.assets.create(e.nid, 'scoped.txt', base64.b64encode(b'SCOPED_SELECTED').decode(), 'text/plain', 'file', branch_id=e.branch)
    other = e.assets.create(e.nid, 'other.txt', base64.b64encode(b'OTHER_BRANCH').decode(), 'text/plain', 'file', branch_id=e.other_branch)
    selection = {'asset_ids': [asset['id']]}
    # A novel branch role alone never expands the stronger original asset gate.
    denied = e.client.post(room(e) + '/packages/preview', headers=e.headers, json=selection)
    assert denied.status_code in {403, 501}
    project = AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid)
    e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, 'domain.read', ModalityDomain.NOVEL, project, e.lead))
    original = e.client.get(e.prefix + '/assets/' + asset['id'], headers=e.headers, params={'novel_id': e.nid})
    preview_response = e.client.post(room(e) + '/packages/preview', headers=e.headers, json=selection)
    assert original.status_code == 200, original.text
    assert preview_response.status_code == 200, preview_response.text
    preview = checked(preview_response)
    body = {**selection, 'preview_digest': preview['preview_digest'], 'acknowledge_copy_boundary': True}
    exported = checked(e.client.post(room(e) + '/packages/download', headers=e.headers, json=body))
    assert exported['filename'] == 'restricted-review.zip'
    # Original project AND branch authority is preserved; selecting another
    # branch cannot make its content available.
    denied_other = e.client.post(room(e) + '/packages/preview', headers=e.headers, json={'asset_ids': [other['id']]})
    assert denied_other.status_code in {403, 404, 501}
    e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
    assert e.client.post(room(e) + '/packages/preview', headers=e.headers, json=selection).status_code == 403
