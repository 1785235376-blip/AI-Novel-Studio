"""Real File / opt-in real PostgreSQL owners at the frozen Interop boundary.

The original Interop fixture/tests remain unchanged. This fixture attaches the
same production branch authority used by CollaborationReadService.
"""
from dataclasses import replace
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.collaboration import Branch, Storyline
from app.document import markdown_to_document
from app.experimental.store import ExperimentalStore
from app.experimental.ux import ReadContext
from app.local_interop.api import (
    AskInput, ConnectInput, ContextPreviewInput, HandoffInput,
    PermissionRevokeInput, create_local_interop_router,
)
from app.local_interop.chapter_ids import WIRE_ID, chapter_wire_id
from app.local_interop.errors import InteropFailure
from app.local_interop.host import LocalInteropHost
from app.local_interop.provider import InteropContextProvider, anchor_text
from app.services.branch_manuscript_service import BranchManuscriptService
from local_interop_protocol import HandoffTarget, ProtocolViolation
from test_local_interop_host import env as legacy_env, run  # Existing fixture; no edited tests.


@pytest.fixture
def branch_env(legacy_env, monkeypatch):
    e = legacy_env
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'local_tutor_interop_v1,branch_manuscript_v1')
    e.store = ExperimentalStore(e.tmp_path, e.backend, e.url)
    e.branch_owner = BranchManuscriptService(e.store, e.bundle.novels, e.bundle.chapters, e.scopes)
    e.collaboration.branch_manuscripts = e.branch_owner
    e.ctx = ReadContext(e.project_id, {'mode': 'collaboration', 'novel_id': e.project_id,
        **{key: e.scope[key] for key in ('workspace_id', 'storyline_id', 'branch_id')}}, e.actor_ids['author'], 'author', e.branch_id)
    preview = e.branch_owner.preview_fork(e.ctx, {'mode': 'local', 'novel_id': e.project_id}, [e.chapter['id']])
    receipt = e.branch_owner.apply_fork(e.ctx, preview['id'], preview['version'], preview['preview_digest'], True)
    e.branch = e.branch_owner.read(e.ctx, receipt['id_map'][e.chapter['id']])
    e.wire_id = chapter_wire_id(e.scope, e.branch['id'])
    e.session_sources = {}
    async def connect(*, chapter_id=e.wire_id, scope=None, token='author'):
        e.host.configure(token, True)
        body = ConnectInput(request_id=uuid4().hex, endpoint='http://127.0.0.1:41000', scope=scope or e.scope,
            project_id=(scope or e.scope)['project_id'], module='NOVEL', surface='editor', chapter_id=chapter_id)
        sid = (await e.host.run(token, body.request_id, lambda: e.host.connect(token, body)))['session_id']
        e.session_sources[sid] = e.host._snapshot(e.host.sessions[sid])['source_version']
        return sid
    e.connect_branch = connect
    yield e
    if e.backend == 'postgres':
        with e.store._connect() as conn:
            conn.execute('DELETE FROM experimental_scope_documents WHERE novel_id=%s', (e.project_id,))


def handoff(e, sid, cid, source=None, project=None):
    return HandoffInput(session_id=sid, explicit_click=True,
        handoff=HandoffTarget(action='OPEN_CHAPTER', target_product_id='poemseed.creative.studio',
                              chapter_id=cid, source_version=source or e.session_sources[sid], project_id=project))



def delete_branch(e, row):
    archived = e.branch_owner.archive(e.ctx, row['id'], True, row['version'])
    return e.branch_owner.delete(e.ctx, row['id'], archived['version'])

def test_wire_projection_is_bounded_stable_scoped_and_legacy_compatible():
    scope = dict(workspace_id='w', project_id='p', storyline_id='s', branch_id='b')
    native = 'p:~b00000000-0000-0000-0000-000000000001'
    assert chapter_wire_id(scope, native) == 'chapter-' + __import__('hashlib').sha256(
        b'["studio-chapter-v1","w","p","s","b","p:~b00000000-0000-0000-0000-000000000001"]').hexdigest()
    wire = chapter_wire_id(scope, native)
    assert WIRE_ID.fullmatch(wire) and len(wire) == 72 and native not in wire
    assert chapter_wire_id(scope, 'p:1') == 'p:1'
    assert chapter_wire_id(scope, 'x' * 128) == 'x' * 128
    for value in ('x' * 129, '~' * 2000, '稿件😀', 'a\n', '../chapter'):
        assert WIRE_ID.fullmatch(chapter_wire_id(scope, value))
    for key in scope:
        assert chapter_wire_id({**scope, key: 'other'}, native) != wire
    assert chapter_wire_id(scope, native.replace('0001', '0002')) != wire


def test_actual_branch_metadata_content_and_exact_handoff_preserve_mainline(branch_env):
    e = branch_env
    before = e.bundle.chapters.get(e.chapter['id'])
    e.branch = e.branch_owner.save(e.ctx, e.branch['id'], markdown_to_document('Branch 😀 ONLY'), e.branch['version'])
    async def scenario():
        sid = await e.connect_branch()
        source = e.host.sources('author', sid)
        assert source['items'] == [{'id': e.wire_id, 'label': 'Chapter 1', 'version': e.branch['version']}]
        preview = e.host.context_preview('author', ContextPreviewInput(session_id=sid, chapter_id=e.wire_id))
        assert preview['capsule']['chapter_id'] == e.wire_id
        assert preview['capsule']['content'] == {'level': 'NONE', 'text': None, 'consent_id': None}
        assert e.branch['id'] not in json.dumps(preview) and 'Branch 😀 ONLY' not in json.dumps(preview, ensure_ascii=False)
        assert all(e.branch['id'] not in item['locator'] for item in preview['capsule']['evidence'])
        selected = e.host.context_preview('author', ContextPreviewInput(session_id=sid, chapter_id=e.wire_id,
            expected_chapter_version=e.branch['version'], content_kind='SELECTION', selection_start=0, selection_end=8, metadata_fields=[]))
        assert selected['capsule']['content']['text'] == 'Branch 😀'
        assert not any(op == 'tutor' for op, _, _ in e.recorded)
        await e.host.ask('author', AskInput(session_id=sid, preview_id=selected['preview_id'], confirmed=True))
        sent = next(message for op, message, _ in e.recorded if op == 'tutor')
        assert sent.context.chapter_id == e.wire_id and e.branch['id'] not in sent.model_dump_json()
        assert sent.context.content.text == 'Branch 😀'
        route = e.host.handoff('author', handoff(e, sid, e.wire_id, preview['capsule']['source_version']))['route']
        assert route['chapter_id'] == e.branch['id'] and route['chapter_version'] == e.branch['version'] and route['scope'] == e.scope
        for invalid in (e.chapter['id'], e.project_id + ':1', 'chapter-' + '0' * 64):
            with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'):
                e.host.handoff('author', handoff(e, sid, invalid))
        assert e.bundle.chapters.get(e.chapter['id']) == before
        await e.host.shutdown()
    run(scenario)


def test_branch_empty_and_another_owner_number_one_never_borrow_sources(branch_env):
    e = branch_env
    other_scope = {**e.scope, 'branch_id': e.other_branch_id}
    other_ctx = replace(e.ctx, scope={**e.ctx.scope, 'branch_id': e.other_branch_id}, branch=e.other_branch_id)
    e.authorization.assign_permission(PermissionAssignment('other-' + uuid4().hex, e.actor_ids['reader'], 'domain.read',
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.BRANCH, **other_scope), e.actor_ids['author']))
    async def scenario():
        sid = await e.connect_branch(chapter_id=None, scope=other_scope, token='reader')
        assert e.host.sources('reader', sid)['items'] == []
        for invalid in (e.wire_id, e.chapter['id'], e.project_id + ':1'):
            with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'):
                e.host.handoff('reader', handoff(e, sid, invalid))
        other = e.branch_owner.create(other_ctx, {'title': 'Other', 'content': 'Other branch only'})
        assert other['number'] == e.branch['number'] == 1
        other_wire = chapter_wire_id(other_scope, other['id'])
        assert other_wire != e.wire_id
        assert e.host.sources('reader', sid)['items'][0]['id'] == other_wire
        with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'):
            e.host.provider.chapter(e.scope, other_wire)
        with pytest.raises(InteropFailure, match='PERMISSION_DENIED'):
            e.host.handoff('reader', handoff(e, sid, other_wire, project='other-project'))
        with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'):
            e.host.handoff('reader', handoff(e, sid, chapter_wire_id(e.scope, other['id'])))
        await e.host.shutdown()
    run(scenario)


@pytest.mark.parametrize('change', ['feature', 'permission', 'tombstone', 'archive', 'version'])
def test_branch_authority_changes_reject_existing_context_and_handoff(branch_env, monkeypatch, change):
    e = branch_env
    async def scenario():
        sid = await e.connect_branch()
        preview = e.host.context_preview('author', ContextPreviewInput(session_id=sid, content_kind='CHAPTER',
            chapter_id=e.wire_id, expected_chapter_version=e.branch['version']))
        if change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'local_tutor_interop_v1')
        elif change == 'permission': e.authorization.revoke_permission(e.permission_ids['author'], e.actor_ids['author'])
        elif change == 'tombstone': delete_branch(e, e.branch)
        elif change == 'version': e.branch_owner.save(e.ctx, e.branch['id'], markdown_to_document('New current chapter'), e.branch['version'])
        else: e.branch_owner.archive(e.ctx, e.branch['id'], True, e.branch['version'])
        with pytest.raises((InteropFailure, ProtocolViolation)):
            await e.host.ask('author', AskInput(session_id=sid, preview_id=preview['preview_id'], confirmed=True))
        with pytest.raises(InteropFailure): e.host.handoff('author', handoff(e, sid, e.wire_id))
        assert not any(op == 'tutor' for op, _, _ in e.recorded)
        await e.host.shutdown()
    run(scenario)


def test_tombstone_and_restart_never_rebind_native_or_numeric_identity(branch_env):
    e = branch_env
    async def scenario():
        sid = await e.connect_branch()
        e.host.context_preview('author', ContextPreviewInput(session_id=sid))
        await e.host.shutdown()
        e.collaboration.branch_manuscripts = BranchManuscriptService(
            ExperimentalStore(e.tmp_path, e.backend, e.url), e.bundle.novels, e.bundle.chapters, e.scopes)
        restarted = LocalInteropHost(InteropContextProvider(e.collaboration), transport_factory=e.InProcessTransport)
        restarted.configure('author', True)
        with pytest.raises(InteropFailure, match='SESSION_REVOKED'): restarted.sources('author', sid)
        assert restarted.provider.chapter(e.scope, e.wire_id)['id'] == e.branch['id']
        fresh = (await restarted.connect('author', e.body().model_copy(update={'chapter_id': e.wire_id})))['session_id']
        assert fresh != sid
        e.session_sources[fresh] = restarted._snapshot(restarted.sessions[fresh])['source_version']
        assert restarted.handoff('author', handoff(e, fresh, e.wire_id))['route']['chapter_id'] == e.branch['id']
        delete_branch(e, e.branch)
        replacement = e.branch_owner.create(e.ctx, {'title': 'Replacement', 'content': anchor_text(e.branch['document'])})
        assert replacement['id'] != e.branch['id'] and replacement['number'] == 2
        with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'): restarted.provider.chapter(e.scope, e.wire_id)
        with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'): restarted.provider.chapter(e.scope, e.project_id + ':1')
        assert e.bundle.chapters.get(e.chapter['id']) == e.chapter
        await restarted.shutdown()
    run(scenario)


def test_alias_collision_and_malformed_wire_ids_fail_closed(branch_env, monkeypatch):
    e = branch_env
    e.branch_owner.create(e.ctx, {'title': 'Second', 'content': 'Second'})
    monkeypatch.setattr('app.local_interop.provider.chapter_wire_id', lambda scope, native: e.wire_id)
    with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'): e.host.provider.chapter(e.scope, e.wire_id)
    with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'): e.host.provider.chapter_entries(e.scope)
    for invalid in (e.branch['id'], '../chapter', 'a\n', 'a' * 129, ''):
        with pytest.raises(InteropFailure, match='INVALID_MESSAGE'): e.host.provider.chapter(e.scope, invalid)


def test_legacy_valid_label_cannot_shadow_a_native_digest_projection():
    scope = dict(workspace_id='w', project_id='p', storyline_id='s', branch_id='b')
    native = 'p:~00000000-0000-0000-0000-000000000001'
    wire = chapter_wire_id(scope, native)
    rows = {cid: {'id': cid, 'novel_id': 'p', 'version': 1, 'document': markdown_to_document(cid)} for cid in (native, wire)}
    chapters = SimpleNamespace(list=lambda _: list(rows.values()), get=rows.__getitem__)
    provider = InteropContextProvider(SimpleNamespace(chapters=chapters))
    with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'): provider.chapter(scope, wire)


def test_actual_other_project_reference_cannot_be_replayed_into_authorized_branch(branch_env):
    e = branch_env
    nid = 'interop-foreign-' + uuid4().hex
    e.bundle.novels.create({'id': nid, 'title': 'Another synthetic project'})
    storyline, branch = 's-' + uuid4().hex, 'b-' + uuid4().hex
    e.scopes.link_project(e.workspace_id, nid)
    e.scopes.create_storyline(Storyline(storyline, e.workspace_id, nid, 'Other'))
    e.scopes.create_branch(Branch(branch, e.workspace_id, nid, storyline, 'Other'))
    scope = dict(workspace_id=e.workspace_id, project_id=nid, storyline_id=storyline, branch_id=branch)
    ctx = ReadContext(nid, dict(mode='collaboration', novel_id=nid, workspace_id=e.workspace_id,
        storyline_id=storyline, branch_id=branch), e.actor_ids['author'])
    row = e.branch_owner.create(ctx, {'title': 'Foreign', 'content': 'FOREIGN_BODY_MUST_STAY_PRIVATE'})
    wire = chapter_wire_id(scope, row['id'])
    e.authorization.assign_permission(PermissionAssignment('foreign-' + uuid4().hex, e.actor_ids['reader'], 'domain.read',
        ModalityDomain.NOVEL, AuthorizationScope(ScopeKind.BRANCH, **scope), e.actor_ids['author']))
    async def scenario():
        ours = await e.connect_branch()
        theirs = await e.connect_branch(scope=scope, chapter_id=wire, token='reader')
        assert e.host.sources('reader', theirs)['items'][0]['id'] == wire
        for token, sid, replay in [('author', ours, wire), ('reader', theirs, e.wire_id)]:
            with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'):
                e.host.handoff(token, handoff(e, sid, replay))
            with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'):
                e.host.context_preview(token, ContextPreviewInput(session_id=sid, content_kind='SPECIFIC_CONTEXT', context_ids=[replay]))
        await e.host.shutdown()
    try:
        run(scenario)
    finally:
        if e.backend == 'postgres':
            with e.store._connect() as conn: conn.execute('DELETE FROM experimental_scope_documents WHERE novel_id=%s', (nid,))
        e.bundle.novels.delete(nid)


def test_a43_qualified_native_id_roundtrips_only_on_explicit_legacy_owner(legacy_env):
    e = legacy_env
    # The existing original fixture intentionally has no branch owner. Model a
    # migrated mainline whose numeric allocation history is unknown.
    if e.backend == 'file':
        (e.tmp_path / 'novels' / e.project_id / 'chapter_identity.json').unlink()
    else:
        from app.repositories.postgres.common import novel_or_raise
        with e.bundle.novels.database.session() as session:
            novel_or_raise(session, e.project_id).chapter_identity_provenance = 'UNKNOWN_NO_HISTORICAL_ALLOCATION_LOG'
    native = e.bundle.chapters.create(e.project_id, {'title': 'A43 native', 'content': 'A43 only'})
    assert ':~' in native['id']
    wire = chapter_wire_id(e.scope, native['id'])
    assert e.host.provider.chapter(e.scope, wire)['id'] == native['id']
    with pytest.raises(InteropFailure, match='HANDOFF_TARGET_NOT_FOUND'):
        e.host.provider.chapter(e.scope, e.project_id + ':' + str(native['number']))
    async def scenario():
        e.host.configure('author', True)
        body = e.body().model_copy(update={'chapter_id': wire})
        sid = (await e.host.connect('author', body))['session_id']
        source = e.host.context_preview('author', ContextPreviewInput(session_id=sid))['capsule']
        e.session_sources = {sid: source['source_version']}
        assert source['chapter_id'] == wire and native['id'] not in json.dumps(source)
        assert e.host.handoff('author', handoff(e, sid, wire))['route']['chapter_id'] == native['id']
        await e.host.shutdown()
    run(scenario)


def test_frozen_browser_api_rejects_raw_native_and_malformed_ids(branch_env):
    e = branch_env
    async def scenario():
        sid = await e.connect_branch()
        app = FastAPI(); app.include_router(create_local_interop_router(e.host))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, client=('127.0.0.1', 9000)), base_url='http://127.0.0.1') as client:
            for invalid in (e.branch['id'], '../chapter', 'a\n', 'a' * 129):
                response = await client.post('/api/local-interop/context/preview', headers={'X-Session-Token': 'author'},
                    json={'session_id': sid, 'chapter_id': invalid, 'content_kind': 'NONE'})
                assert response.status_code == 400 and response.json()['code'] == 'INVALID_MESSAGE'
                assert invalid not in response.text
            duplicate = await client.post('/api/local-interop/context/preview', headers={'X-Session-Token': 'author'},
                json={'session_id': sid, 'context_ids': [e.wire_id, e.wire_id], 'content_kind': 'SPECIFIC_CONTEXT'})
            assert duplicate.status_code == 403 and duplicate.json()['code'] == 'CONTEXT_NOT_AUTHORIZED'
        await e.host.shutdown()
    run(scenario)


def test_specific_context_and_cross_chapter_handoff_pin_all_delivery_sources(branch_env):
    e = branch_env
    extra = e.branch_owner.create(e.ctx, {'title': 'Additional', 'content': 'Additional branch context'})
    wire = chapter_wire_id(e.scope, extra['id'])
    async def scenario():
        sid = await e.connect_branch()
        preview_body = ContextPreviewInput(session_id=sid, content_kind='SPECIFIC_CONTEXT', context_ids=[wire], metadata_fields=[])
        preview = e.host.context_preview('author', preview_body)
        assert preview['capsule']['content']['text'] == anchor_text(extra['document'])
        assert e.branch['id'] not in json.dumps(preview) and extra['id'] not in json.dumps(preview)
        route_body = handoff(e, sid, wire)
        assert e.host.handoff('author', route_body)['route']['chapter_id'] == extra['id']
        e.branch_owner.save(e.ctx, extra['id'], markdown_to_document('Changed additional source'), extra['version'])
        for request_id in (preview_body.request_id, route_body.request_id):
            with pytest.raises(InteropFailure, match='SOURCE_CHANGED'): e.host.delivery_guard('author', sid, request_id)
        with pytest.raises(InteropFailure, match='SOURCE_CHANGED'):
            await e.host.ask('author', AskInput(session_id=sid, preview_id=preview['preview_id'], confirmed=True))
        assert not any(op == 'tutor' for op, _, _ in e.recorded)
        await e.host.shutdown()
    run(scenario)


def test_selection_and_deep_link_permission_remain_independent(branch_env):
    e = branch_env
    async def scenario():
        sid = await e.connect_branch()
        e.host.permission_revoke('author', PermissionRevokeInput(session_id=sid, permission_id='selection'))
        with pytest.raises(InteropFailure):
            e.host.context_preview('author', ContextPreviewInput(session_id=sid, content_kind='SELECTION',
                chapter_id=e.wire_id, expected_chapter_version=e.branch['version'], selection_start=0, selection_end=3))
        assert e.host.context_preview('author', ContextPreviewInput(session_id=sid, content_kind='CHAPTER',
            chapter_id=e.wire_id, expected_chapter_version=e.branch['version']))['capsule']['content']['level'] == 'CURRENT_CHAPTER'
        e.host.permission_revoke('author', PermissionRevokeInput(session_id=sid, permission_id='deep_link'))
        with pytest.raises(InteropFailure): e.host.handoff('author', handoff(e, sid, e.wire_id))
        await e.host.shutdown()
    run(scenario)


@pytest.mark.parametrize('route', ['sources', 'handoff', 'preview', 'events'])
def test_response_send_boundary_rechecks_nonactive_chapter(branch_env, route):
    e = branch_env
    extra = e.branch_owner.create(e.ctx, {'title': 'Second', 'content': 'Must not escape after deletion'})
    wire = chapter_wire_id(e.scope, extra['id'])
    async def scenario():
        sid = await e.connect_branch()
        if route == 'events':
            e.subscribe(sid)
            e.host.capture_event('author', sid)
        app = FastAPI(); app.include_router(create_local_interop_router(e.host))
        class DeleteAtHeaders:
            async def __call__(self, scope, receive, send):
                async def frame(message):
                    if message['type'] == 'http.response.start':
                        delete_branch(e, e.branch if route == 'events' else extra)
                    await send(message)
                await app(scope, receive, frame)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=DeleteAtHeaders(), client=('127.0.0.1', 9000)), base_url='http://127.0.0.1') as client:
            headers = {'X-Session-Token': 'author'}
            if route == 'sources': response = await client.get('/api/local-interop/context/sources', params={'session_id': sid}, headers=headers)
            elif route == 'events': response = await client.get('/api/local-interop/events', params={'session_id': sid}, headers=headers)
            elif route == 'handoff': response = await client.post('/api/local-interop/handoff', json=handoff(e, sid, wire).model_dump(mode='json'), headers=headers)
            else: response = await client.post('/api/local-interop/context/preview', json=ContextPreviewInput(session_id=sid,
                content_kind='SPECIFIC_CONTEXT', context_ids=[wire]).model_dump(mode='json'), headers=headers)
        assert response.json()['code'] in {'SOURCE_CHANGED', 'HANDOFF_TARGET_NOT_FOUND'}
        assert extra['id'] not in response.text and 'Must not escape' not in response.text
        await e.host.shutdown()
    run(scenario)
