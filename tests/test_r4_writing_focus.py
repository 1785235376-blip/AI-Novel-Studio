"""U04 deterministic contracts on File and optional real PostgreSQL."""
import copy
import json
import os
import threading
import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.planning import PlanningService
from app.experimental.store import ExperimentalStore
from app.experimental.ux import ReadContext
from app.experimental.writing_focus import WritingFocusService, WritingPreferences
from app.experimental.writing_focus_api import create_writing_focus_router
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def focus_env(tmp_path, request):
    backend, url = request.param, os.getenv('TEST_POSTGRES_DATABASE_URL', '')
    if backend == 'postgres' and not url:
        pytest.skip('NOT_RUN: real PostgreSQL endpoint unavailable')
    nid = 'focus-' + uuid.uuid4().hex
    rows = [{'id': 'chapter', 'novel_id': nid, 'version': 1, 'title': '旧港', 'content': '海风吹过旧港。'}]
    datasets = {'characters': [{'id': 'qing', 'name': '阿青', 'role': '船长', 'personality': '谨慎', 'secret_text': '不应投影的秘密', 'api_key': 'not-for-card'}, {'id': 'hidden', 'name': '隐藏人物', 'hidden': True}], 'locations': [{'id': 'harbor', 'name': '旧港', 'description': '废弃的港口'}]}
    def get_novel(got):
        if got != nid: raise FileNotFoundError(got)
        return {'id': nid}
    def get_chapter(cid):
        found = next((row for row in rows if row['id'] == cid), None)
        if found is None: raise FileNotFoundError(cid)
        return copy.deepcopy(found)
    novels = SimpleNamespace(get=get_novel, data_set=lambda got, name: copy.deepcopy(datasets.get(name, [])))
    chapters = SimpleNamespace(list=lambda got: copy.deepcopy(rows), get=get_chapter)
    store = ExperimentalStore(tmp_path, backend, url)
    planning = PlanningService(store, novels, chapters)
    service = WritingFocusService(store, novels, chapters, planning=planning)
    ctx = ReadContext(nid, {'mode': 'local', 'novel_id': nid}, 'alice')
    env = SimpleNamespace(service=service, planning=planning, ctx=ctx, store=store, rows=rows, datasets=datasets,
                          novels=novels, chapters=chapters, backend=backend, url=url, root=tmp_path)
    yield env
    if backend == 'postgres':
        with store._connect() as conn:
            conn.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))


def note(e, **extra):
    return e.service.create_note(e.ctx, {'capture_id': uuid.uuid4().hex, 'title': '旧信', 'text': '让旧信指向失踪的船。', **extra})


def node(e):
    graph = e.planning.create_graph(e.ctx.novel_id, e.ctx.scope, e.ctx.actor, {'title': '港口故事', 'fields': {'goal': '找到船长'}})
    return e.planning.graph(e.ctx.novel_id, e.ctx.scope, graph['id'])['nodes'][0]


def test_preferences_restart_scope_actor_and_cas(focus_env):
    e = focus_env
    assert e.service.preferences(e.ctx)['version'] == 0
    settings = {'expected_version': 0, 'preferences': {'font_size': 24, 'column_width': 'narrow', 'paragraph_focus': True}}
    result = e.service.save_preferences(e.ctx, settings)
    assert result['version'] == 1 and result['preferences']['font_size'] == 24
    other = ReadContext(e.ctx.novel_id, e.ctx.scope, 'bob')
    assert e.service.preferences(other)['version'] == 0
    restarted = WritingFocusService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapters)
    assert restarted.preferences(e.ctx) == result
    with pytest.raises(CapabilityVersionConflict): e.service.save_preferences(e.ctx, settings)
    assert e.rows[0]['version'] == 1


def test_corrupt_preferences_recovery_strict_fields(focus_env):
    e = focus_env
    e.service.save_preferences(e.ctx, {'expected_version': 0})
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        next(iter(state['collections'][e.service.PREFERENCES].values()))['preferences'] = {'font_size': 999}
    result = e.service.preferences(e.ctx)
    assert result['recovery_required'] and result['preferences'] == WritingPreferences().model_dump()
    assert not e.service.save_preferences(e.ctx, {'expected_version': 1})['recovery_required']
    for body in [{'expected_version': 2, 'actor': 'other'}, {'expected_version': 2, 'preferences': {'font_size': 17}}, {'expected_version': 2, 'preferences': {'line_height': 1.9}}]:
        with pytest.raises(ValueError): e.service.save_preferences(e.ctx, body)


def test_readonly_references_pins_stale_missing_privacy(focus_env):
    e = focus_env
    before = copy.deepcopy(e.datasets)
    result = e.service.references(e.ctx)
    assert len(result['items']) == 3
    serialized = json.dumps(result, ensure_ascii=False)
    assert '不应投影的秘密' not in serialized and 'api_key' not in serialized and '隐藏人物' not in serialized
    card = result['items'][0]
    pin = {key: card[key] for key in ('kind', 'id', 'revision')}
    e.service.save_preferences(e.ctx, {'expected_version': 0, 'pins': [pin]})
    assert e.service.pinned(e.ctx)['items'][0]['card']['read_only'] is True
    assert e.datasets == before
    e.datasets['characters'][0]['role'] = '新的身份'
    assert e.service.pinned(e.ctx)['items'][0]['state'] == 'STALE'
    assert e.service.pinned(e.ctx)['items'][0]['card'] is None
    # Typography updates may retain a stale pin, without accepting new content.
    e.service.save_preferences(e.ctx, {'expected_version': 1, 'pins': [pin], 'preferences': {'font_size': 20}})
    e.datasets['characters'][0]['hidden'] = True
    assert e.service.pinned(e.ctx)['items'][0]['state'] == 'UNAVAILABLE'
    assert e.service.pinned(e.ctx)['items'][0]['title'] == '资料不可用'
    e.service.save_preferences(e.ctx, {'expected_version': 2, 'pins': []})
    assert not e.service.pinned(e.ctx)['items']


def test_pin_source_fence_duplicates_and_bounded_chapter_reference(focus_env):
    e = focus_env
    e.rows[0]['content'] = '汉' * 20000
    card = e.service.references(e.ctx, kind='chapter')['items'][0]
    assert card['truncated'] and len(card['text']) == 12000
    pin = {key: card[key] for key in ('kind', 'id', 'revision')}
    with pytest.raises(ValueError): e.service.save_preferences(e.ctx, {'expected_version': 0, 'pins': [pin, pin]})
    e.rows[0]['version'] = 2
    with pytest.raises(StaleSourceError): e.service.save_preferences(e.ctx, {'expected_version': 0, 'pins': [pin]})
    assert e.service.preferences(e.ctx)['version'] == 0


def test_missing_branch_sources_fail_closed(focus_env):
    e = focus_env
    branch = ReadContext(e.ctx.novel_id, {'mode': 'collaboration', 'novel_id': e.ctx.novel_id, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}, 'alice')
    assert e.service.references(branch) == {'items': [], 'truncated': False, 'branch_sources_available': False}
    with pytest.raises(FileNotFoundError): e.service.create_note(branch, {'capture_id': 'branch-capture', 'text': '分支灵感', 'chapter_id': 'chapter', 'chapter_version': 1})
    row = e.service.create_note(branch, {'capture_id': 'branch-note', 'text': '本分支独立笔记'})
    assert row['scope'] == branch.scope and e.service.notes(e.ctx)['items'] == []
    e.service.entity_readers = {'character': lambda ctx: e.datasets['characters']}
    assert not e.service.references(branch)['items']  # untagged base data remains rejected
    e.datasets['characters'][0]['branch_id'] = 'b'
    assert e.service.references(branch)['items'][0]['id'] == 'qing'


def test_notes_real_persistence_private_draft_idempotency_and_archive(focus_env):
    e = focus_env
    row = note(e, capture_id='one-capture', chapter_id='chapter', chapter_version=1)
    assert row['source_state'] == 'READY' and row['status'] == 'DRAFT'
    assert row['included_in_ai_context'] is False and row['canon'] is False
    same = note(e, capture_id='one-capture', chapter_id='chapter', chapter_version=1)
    assert same['id'] == row['id'] and len(e.service.notes(e.ctx)['items']) == 1
    with pytest.raises(ValueError): note(e, capture_id='one-capture', text='different')
    other = ReadContext(e.ctx.novel_id, e.ctx.scope, 'bob')
    assert e.service.notes(other)['items'] == []
    with pytest.raises(FileNotFoundError): e.service.transition_note(other, row['id'], 1, 'archive')
    archived = e.service.transition_note(e.ctx, row['id'], 1, 'archive')
    assert archived['status'] == 'ARCHIVED' and e.service.notes(e.ctx)['items'] == []
    assert e.service.notes(e.ctx, archived=True)['items'][0]['id'] == row['id']
    restored = e.service.transition_note(e.ctx, row['id'], 2, 'restore')
    assert restored['version'] == 3 and restored['text'] == row['text']
    assert e.store.read(e.ctx.novel_id, e.ctx.scope)['collections'].keys() == {e.service.NOTES}
    assert e.rows[0]['version'] == 1


def test_note_edit_cas_concurrency_and_stale_source_recovery(focus_env):
    e = focus_env
    row = note(e, chapter_id='chapter', chapter_version=1)
    e.rows[0]['content'] = '现在的海港'; e.rows[0]['version'] = 2
    assert e.service.notes(e.ctx)['items'][0]['source_state'] == 'STALE'
    body = {key: row[key] for key in ('capture_id', 'title', 'text', 'chapter_id', 'chapter_version')}
    with pytest.raises(StaleSourceError): e.service.edit_note(e.ctx, row['id'], {**body, 'expected_version': 1})
    body.update(chapter_version=2)
    barrier, outcomes = threading.Barrier(2), []
    def edit(text):
        barrier.wait()
        try:
            e.service.edit_note(e.ctx, row['id'], {**body, 'text': text, 'expected_version': 1})
            outcomes.append('saved')
        except CapabilityVersionConflict: outcomes.append('conflict')
    workers = [threading.Thread(target=edit, args=(str(index),)) for index in range(2)]
    for worker in workers: worker.start()
    for worker in workers: worker.join()
    assert sorted(outcomes) == ['conflict', 'saved']
    e.rows.clear()
    assert e.service.notes(e.ctx)['items'][0]['source_state'] == 'UNAVAILABLE'
    unlinked = e.service.edit_note(e.ctx, row['id'], {**body, 'chapter_id': None, 'chapter_version': None, 'expected_version': 2})
    assert unlinked['source_state'] == 'NONE'


def test_reviewed_copy_is_atomic_existing_planning_review_not_canon(focus_env):
    e = focus_env
    target = node(e); row = note(e)
    body = {'expected_version': 1, 'node_id': target['id'], 'expected_node_version': 1, 'field': 'goal'}
    preview = e.service.preview_copy(e.ctx, row['id'], body)
    assert preview['before'] == '找到船长' and row['text'] in preview['after']
    assert not e.planning.proposals(e.ctx.novel_id, e.ctx.scope)
    copied = e.service.copy_to_planning(e.ctx, row['id'], {**body, 'preview_digest': preview['preview_digest']})
    assert copied['note']['version'] == 2 and copied['status'] == 'REVIEW'
    proposal = e.planning.proposal(e.ctx.novel_id, e.ctx.scope, copied['proposal_id'])
    assert proposal['status'] == 'REVIEW' and proposal['execution_mode'] == 'USER_AUTHORED'
    assert proposal['fields']['goal'] == preview['after']
    assert e.planning.get(e.ctx.novel_id, e.ctx.scope, e.planning.NODES, target['id']) == target
    replay = e.service.copy_to_planning(e.ctx, row['id'], {**body, 'preview_digest': preview['preview_digest']})
    assert replay['replayed'] and replay['proposal_id'] == copied['proposal_id']
    assert len(e.planning.proposals(e.ctx.novel_id, e.ctx.scope)) == 1
    assert e.rows[0]['content'] == '海风吹过旧港。'


def test_copy_rejects_stale_preview_note_target_source_and_authority(focus_env):
    e = focus_env
    target = node(e); row = note(e, chapter_id='chapter', chapter_version=1)
    body = {'expected_version': 1, 'node_id': target['id'], 'expected_node_version': 1}
    preview = e.service.preview_copy(e.ctx, row['id'], body)
    with pytest.raises(StaleSourceError): e.service.copy_to_planning(e.ctx, row['id'], {**body, 'preview_digest': 'a'*64})
    def revoked(): raise HTTPException(403)
    with pytest.raises(HTTPException): e.service.copy_to_planning(e.ctx, row['id'], {**body, 'preview_digest': preview['preview_digest']}, revoked)
    assert e.service.notes(e.ctx)['items'][0]['version'] == 1
    assert not e.planning.proposals(e.ctx.novel_id, e.ctx.scope)
    e.rows[0]['version'] = 2
    with pytest.raises(StaleSourceError): e.service.copy_to_planning(e.ctx, row['id'], {**body, 'preview_digest': preview['preview_digest']})
    e.rows[0]['version'] = 1
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        state['collections'][e.planning.NODES][target['id']]['version'] = 2
    with pytest.raises(CapabilityVersionConflict): e.service.copy_to_planning(e.ctx, row['id'], {**body, 'preview_digest': preview['preview_digest']})
    assert not e.planning.proposals(e.ctx.novel_id, e.ctx.scope)


def test_current_authorization_flag_and_router_contract(focus_env):
    e = focus_env
    state = {'enabled': True, 'planning': True, 'allowed': True, 'change_actor': False}; calls = []
    def gate(flag):
        if not state['enabled'] or (flag == 'advanced_planning_v2' and not state['planning']): raise HTTPException(404)
    def authorize(nid, token, branch, permission):
        calls.append((token, branch, permission))
        if not state['allowed']: raise HTTPException(403)
        return ('bob' if state['change_actor'] and len(calls) % 2 == 0 else token or 'alice'), e.ctx.scope
    app = FastAPI(); app.include_router(create_writing_focus_router(e.service, authorize, gate))
    client = TestClient(app); base = f'/novels/{e.ctx.novel_id}/experimental/writing-focus'
    headers = {'X-Session-Token': 'alice', 'X-Branch-Id': 'requested'}
    assert client.get(base+'/preferences', headers=headers).headers['cache-control'] == 'no-store'
    result = client.put(base+'/preferences', headers=headers, json={'expected_version': 0})
    assert result.status_code == 200 and calls[-1] == ('alice', 'requested', 'domain.write')
    assert client.put(base+'/preferences', json={'expected_version': 0}).status_code == 409
    note_result = client.post(base+'/notes', json={'capture_id': 'mounted', 'text': '真实路由草稿'})
    assert note_result.status_code == 201
    rid = note_result.json()['id']
    assert client.get(base+'/notes', headers={'X-Session-Token': 'bob'}).json()['items'] == []
    assert client.post(base+f'/notes/{rid}/archive', json={'expected_version': 1}).status_code == 200
    assert client.post(base+f'/notes/{rid}/restore', json={'expected_version': 2}).status_code == 200
    assert client.post(base+'/notes', json={'capture_id': 'spoof', 'text': 'x', 'canon': True}).status_code == 422
    state['planning'] = False
    assert client.get(base+'/planning-targets').status_code == 404
    state['allowed'] = False
    assert client.get(base+'/references').status_code == 403
    assert client.post(base+'/notes', json={'capture_id': 'denied', 'text': 'x'}).status_code == 403
    state['enabled'] = False
    for path in ['/preferences', '/references', '/pins', '/notes']:
        assert client.get(base+path).status_code == 404
    assert client.put(base+'/preferences', json={'expected_version': 1}).status_code == 404


def test_write_reauthorizes_after_source_reads_and_rolls_back(focus_env):
    e = focus_env
    calls = []
    def revoked():
        calls.append('rechecked')
        raise HTTPException(403)
    with pytest.raises(HTTPException): e.service.create_note(e.ctx, {'capture_id': 'revoked', 'text': 'must-not-save'}, revoked)
    assert calls == ['rechecked'] and not e.service.notes(e.ctx)['items']
    with pytest.raises(HTTPException): e.service.save_preferences(e.ctx, {'expected_version': 0}, revoked)
    assert e.service.preferences(e.ctx)['version'] == 0


def test_router_rechecks_current_actor_and_flags_before_commit(focus_env):
    e = focus_env
    authority = {'calls': 0, 'flip': True, 'enabled': True}
    def gate(flag):
        if not authority['enabled']: raise HTTPException(404)
    def authorize(nid, token, branch, permission):
        authority['calls'] += 1
        return ('bob' if authority['flip'] and authority['calls'] == 2 else 'alice'), e.ctx.scope
    app = FastAPI(); app.include_router(create_writing_focus_router(e.service, authorize, gate))
    client = TestClient(app); base = f'/novels/{e.ctx.novel_id}/experimental/writing-focus'
    result = client.post(base+'/notes', json={'capture_id': 'switch', 'text': 'must not commit'})
    assert result.status_code == 409 and result.json()['detail']['code'] == 'WRITING_FOCUS_SCOPE_CHANGED'
    assert not e.service.notes(e.ctx)['items']
    authority.update(calls=0, flip=False)
    def chapter_reader(ctx):
        authority['enabled'] = False
        return e.rows
    e.service.chapter_reader = chapter_reader
    result = client.post(base+'/notes', json={'capture_id': 'gate-off', 'text': 'must not commit', 'chapter_id': 'chapter', 'chapter_version': 1})
    assert result.status_code == 404 and not e.service.notes(e.ctx)['items']


def test_planning_copy_revalidates_note_ancestor_and_field_size(focus_env):
    e = focus_env
    target = node(e); row = note(e)
    body = {'expected_version': 1, 'node_id': target['id'], 'expected_node_version': 1}
    preview = e.service.preview_copy(e.ctx, row['id'], body)
    note_body = {key: row[key] for key in ('capture_id', 'title', 'text', 'chapter_id', 'chapter_version')}
    e.service.edit_note(e.ctx, row['id'], {**note_body, 'text': '修改后的灵感', 'expected_version': 1})
    with pytest.raises(CapabilityVersionConflict): e.service.copy_to_planning(e.ctx, row['id'], {**body, 'preview_digest': preview['preview_digest']})
    # An arbitrarily large combined planning field must not bypass its schema.
    with e.store.transaction(e.ctx.novel_id, e.ctx.scope) as state:
        state['collections'][e.planning.NODES][target['id']]['fields']['goal'] = '字'*12000
    with pytest.raises(ValueError): e.service.preview_copy(e.ctx, row['id'], {**body, 'expected_version': 2})
    assert not e.planning.proposals(e.ctx.novel_id, e.ctx.scope)


def test_existing_scene_overview_is_readonly_scoped_and_bounded(focus_env):
    e = focus_env
    e.datasets['scenes'] = [
        {'id': 'scene-real', 'chapter_id': 'chapter', 'title': '码头相遇', 'sequence': 1, 'purpose': '建立信任', 'conflict': '隐瞒来意', 'outcome': '暂时合作', 'secret_text': '不可投影'},
        {'id': 'orphan', 'chapter_id': 'deleted', 'title': '不可借用'},
        {'id': 'hidden-scene', 'chapter_id': 'chapter', 'title': '隐藏', 'hidden': True},
        {'id': 'other-branch', 'chapter_id': 'chapter', 'title': '别的支线', 'branch_id': 'elsewhere'},
    ]
    before = copy.deepcopy(e.datasets)
    overview = e.service.overview(e.ctx, 'chapter')
    assert overview['read_only'] and overview['chapter_sources_available'] and overview['scene_sources_available']
    chapter = overview['items'][0]
    assert chapter['id'] == 'chapter' and chapter['scene_count'] == 1
    assert chapter['scenes'][0]['id'] == 'scene-real' and chapter['scenes'][0]['purpose'] == '建立信任'
    assert '不可投影' not in json.dumps(overview, ensure_ascii=False)
    assert e.datasets == before and e.store.read(e.ctx.novel_id, e.ctx.scope)['collections'] == {}
    with pytest.raises(FileNotFoundError): e.service.overview(e.ctx, 'foreign-project-chapter')
    branch = ReadContext(e.ctx.novel_id, {'mode': 'collaboration', 'novel_id': e.ctx.novel_id, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}, 'alice')
    assert e.service.overview(branch)['items'] == []
    assert not e.service.overview(branch)['scene_sources_available']
    e.datasets['scenes'] = [{'id': f'scene-{index}', 'chapter_id': 'chapter', 'title': str(index)} for index in range(25)]
    assert e.service.overview(e.ctx)['items'][0]['scenes_truncated']
    assert len(e.service.overview(e.ctx)['items'][0]['scenes']) == 20


def test_chapter_bookmark_reuses_pin_and_revalidates_navigation(focus_env):
    e = focus_env
    chapter = e.service.overview(e.ctx)['items'][0]
    e.service.save_preferences(e.ctx, {'expected_version': 0, 'pins': [{'kind': 'chapter', 'id': chapter['id'], 'revision': chapter['revision']}]})
    result = e.service.open_bookmark(e.ctx, {'id': chapter['id'], 'revision': chapter['revision']})
    assert result == {'kind': 'chapter', 'id': 'chapter', 'version': 1, 'anchor': {'offset': 0, 'scroll': 0}, 'coordinate': 'EDITOR_TEXT_CODEPOINT', 'stale': False}
    e.rows[0]['version'] = 2
    with pytest.raises(StaleSourceError): e.service.open_bookmark(e.ctx, {'id': chapter['id'], 'revision': chapter['revision']})
    opened = e.service.open_bookmark(e.ctx, {'id': chapter['id'], 'revision': chapter['revision'], 'open_current': True})
    assert opened['version'] == 2 and opened['stale'] and opened['anchor']['offset'] == 0
    assert e.service.preferences(e.ctx)['version'] == 1  # opening cannot repin newer source implicitly
    e.rows.clear()
    with pytest.raises(FileNotFoundError): e.service.open_bookmark(e.ctx, {'id': chapter['id'], 'revision': chapter['revision'], 'open_current': True})
    assert e.store.read(e.ctx.novel_id, e.ctx.scope)['collections'].keys() == {e.service.PREFERENCES}
