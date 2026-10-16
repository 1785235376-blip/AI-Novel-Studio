"""Immutable sharing projection of original structures/WorldService, real File/PG."""
from copy import deepcopy
from dataclasses import replace
import json
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.common import StaleSourceError
from app.experimental.flags import require_flag, FLAGS
from app.experimental.planning import digest
from app.experimental.project_forks_api import create_project_forks_router
from app.experimental.structured_forks import StructuredForksService
from app.experimental.world import WorldService
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r5_project_forks import env
from test_r5_structured_forks import structured, change


@pytest.fixture
def universe(structured):
    e = structured; e.world = WorldService(e.store, e.novels, e.chapters)
    e.target = 'universe-target-' + uuid4().hex
    e.novels.create({'id': e.target, 'title': 'Sequel original work'})
    for kind, data in [('CIVILIZATION', {'name': 'Harbor guild', 'location_ids': ['harbor']}),
                       ('ABILITY', {'name': 'Tide law', 'description': 'Only at night'}),
                       ('HISTORY', {'time': 1, 'description': 'The guild founded', 'character_ids': ['hero'], 'location_ids': ['harbor']})]:
        r = e.world.create_record(e.nid, e.ctx.scope, e.ctx.actor, {'kind': kind, 'title': kind, 'data': data})
        e.world.review(e.nid, e.ctx.scope, e.ctx.actor, r['id'], 'approve', r['version'])
    yield e
    e.novels.delete(e.target)


def request(e, keys=None):
    rows = e.structured.universe_catalog(e.ctx)['records']
    return {'universe_key': 'tide-universe', 'title': 'Shared tide world', 'records': [{'key': r['key'], 'source_digest': r['source_digest']} for r in rows if keys is None or r['key'] in keys], 'license': 'Synthetic author-owned', 'allow_local_copy': True}


def snapshot(e, keys=None, request_id=None):
    body = request(e, keys); preview = e.structured.universe_preview(e.ctx, body)
    return e.structured.create_universe_snapshot(e.ctx, {**body, 'preview_digest': preview['preview_digest'], 'request_id': request_id or uuid4().hex})


def pin(e, snap, version=0, **kw):
    body = {'snapshot_id': snap['id'], 'target_project_id': e.target, 'role': 'SEQUEL', 'expected_version': version}
    preview = e.structured.universe_pin_preview(e.ctx, body)
    return e.structured.pin_universe(e.ctx, {**body, 'preview_digest': preview['preview_digest'], 'confirmed': True}, **kw)


def test_snapshot_selected_domains_freeze_without_copying_second_canon_and_restart(universe):
    e = universe; source_before = e.novels.get(e.nid); target_before = e.novels.get(e.target); canon = e.world.canon(e.nid, e.ctx.scope)
    snap = snapshot(e); pinned = pin(e, snap)
    assert snap['status'] == 'IMMUTABLE' and snap['snapshot_revision'] == 1
    assert {r.get('kind') for key, r in snap['records'].items() if key.startswith('world:')} == {'CIVILIZATION', 'ABILITY', 'HISTORY'}
    assert pinned['status'] == 'PINNED' and pinned['role'] == 'SEQUEL'
    assert e.novels.get(e.nid) == source_before and e.novels.get(e.target) == target_before and e.world.canon(e.nid, e.ctx.scope) == canon
    assert e.novels.data_set(e.target, 'characters') == [] and e.chapters.list(e.target) == []
    e.structured = StructuredForksService(e.store, e.novels, e.chapters, sources=e.service.sources, assets=e.assets)
    assert e.structured.universe_snapshots(e.ctx)['items'][0]['records'] == snap['records']
    assert e.structured.universe_pins(e.ctx)['items'][0]['snapshot_digest'] == snap['snapshot_digest']
    change(e, 'characters:hero', {'name': 'Future changed hero'})
    current = e.structured.universe_snapshots(e.ctx)['items'][0]
    assert not current['content_withheld'] and current['records']['characters:hero']['name'] == 'hero'
    assert current['source_changes'] == ['characters:hero']
    assert e.structured.universe_pins(e.ctx)['items'][0]['snapshot_id'] == snap['id']


def test_only_explicit_cas_repin_changes_one_work_history_and_release(universe):
    e = universe; first = snapshot(e, ['locations:harbor']); original = pin(e, first)
    change(e, 'locations:harbor', {'name': 'Harbor future'})
    second = snapshot(e, ['locations:harbor'])
    assert second['snapshot_revision'] == 2 and second['snapshot_digest'] != first['snapshot_digest']
    assert e.structured.universe_pins(e.ctx)['items'][0]['snapshot_id'] == first['id']
    with pytest.raises(CapabilityVersionConflict): pin(e, second)
    updated = pin(e, second, original['version'])
    history = e.structured.universe_pin_history(e.ctx, original['id'])['items']
    assert history[0]['snapshot_id'] == first['id'] and updated['snapshot_id'] == second['id']
    released = e.structured.release_universe_pin(e.ctx, updated['id'], {'expected_version': updated['version']})
    assert released['status'] == 'RELEASED'
    with pytest.raises(CapabilityVersionConflict): e.structured.release_universe_pin(e.ctx, updated['id'], {'expected_version': updated['version']})
    assert len(e.structured.universe_snapshots(e.ctx)['items']) == 2


def test_snapshot_preflight_exact_refs_idempotency_and_no_stale_copy(universe):
    e = universe
    with pytest.raises(ValueError, match='REFERENCED'): e.structured.universe_preview(e.ctx, request(e, ['characters:hero']))
    body = request(e, ['locations:harbor']); preview = e.structured.universe_preview(e.ctx, body)
    payload = {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'same-request'}
    saved = e.structured.create_universe_snapshot(e.ctx, payload)
    assert e.structured.create_universe_snapshot(e.ctx, payload)['id'] == saved['id']
    with pytest.raises(ValueError, match='REQUEST_ID_REUSED'): e.structured.create_universe_snapshot(e.ctx, {**payload, 'title': 'Changed request'})
    change(e, 'locations:harbor', {'description': 'Changed'})
    with pytest.raises(StaleSourceError): e.structured.create_universe_snapshot(e.ctx, {**payload, 'request_id': 'new-request'})
    assert len(e.structured.universe_snapshots(e.ctx)['items']) == 1


@pytest.mark.parametrize('mode', ['privacy', 'archive', 'delete', 'world_archive'])
def test_current_source_restriction_withholds_snapshot_and_pin_history(universe, mode):
    e = universe; snap = snapshot(e); pinned = pin(e, snap)
    if mode == 'privacy': change(e, 'characters:hero', {'privacy_level': 'LOCAL_ONLY'})
    elif mode == 'archive': change(e, 'characters:hero', {'status': 'ARCHIVED'})
    elif mode == 'delete':
        repository = e.novels.novels
        if e.store.backend == 'file':
            from app.storage import atomic_write
            path = repository.backend.novels / e.nid / 'characters' / 'characters.json'
            rows = json.loads(path.read_text()); atomic_write(path, json.dumps([r for r in rows if r['id'] != 'hero']))
        else:
            from sqlalchemy import select
            from app.repositories.postgres.models import CharacterModel
            from app.repositories.postgres.common import novel_or_raise
            with repository.database.session() as session:
                project = novel_or_raise(session, e.nid)
                entity = session.scalar(select(CharacterModel).where(CharacterModel.novel_id == project.id, CharacterModel.slug == 'hero'))
                session.delete(entity)
    else:
        world = next(r for r in e.world.records(e.nid, e.ctx.scope) if r['kind'] == 'ABILITY')
        e.world.review(e.nid, e.ctx.scope, e.ctx.actor, world['id'], 'archive', world['version'])
    result = e.structured.universe_snapshots(e.ctx)['items'][0]
    assert result['content_withheld'] and 'records' not in result and 'title' not in result
    assert e.structured.universe_pins(e.ctx)['items'][0]['content_withheld']
    with pytest.raises(FileNotFoundError): pin(e, snap, pinned['version'])
    assert e.structured.release_universe_pin(e.ctx, pinned['id'], {'expected_version': pinned['version']})['status'] == 'RELEASED'


def test_actor_branch_target_revocation_and_final_atomic_rollback(universe):
    e = universe; snap = snapshot(e, ['locations:harbor'])
    other = replace(e.ctx, actor='other')
    assert not e.structured.universe_snapshots(other)['items']
    with pytest.raises(FileNotFoundError): e.structured.universe_pin_preview(other, {'snapshot_id': snap['id'], 'target_project_id': e.target, 'role': 'PREQUEL', 'expected_version': 0})
    with pytest.raises(ValueError, match='BRANCH'): e.structured.universe_catalog(replace(e.ctx, branch='wrong'))
    calls = []; before = e.store.read(e.nid, e.ctx.scope)
    def deny():
        calls.append(1)
        if len(calls) >= 2: raise HTTPException(403, 'revoked')
    with pytest.raises(HTTPException): pin(e, snap, reauthorize=deny)
    assert e.store.read(e.nid, e.ctx.scope) == before
    def target_denied(nid): raise HTTPException(403, 'target denied')
    pinned = pin(e, snap)
    assert e.structured.universe_pins(e.ctx, target_authorize=target_denied)['items'][0] == {'id': pinned['id'], 'version': pinned['version'], 'status': 'PINNED', 'created_at': pinned['created_at'], 'content_withheld': True}


def test_universe_routes_defaultoff_v1_permissions_exact_pin_and_no_store(universe, monkeypatch):
    e = universe; allowed = [True]
    def authorize(nid, token, branch, permission):
        if token != 'host' or not allowed[0]: raise HTTPException(403, 'denied')
        e.novels.get(nid)
        return e.ctx.actor, {'mode': 'local', 'novel_id': nid}
    app = FastAPI(); app.include_router(create_project_forks_router(e.service, authorize, require_flag, lambda token: None))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/project-forks/universe'; headers = {'X-Session-Token': 'host'}
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ''); assert client.get(base + '/catalog', headers=headers).status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.get(base + '/catalog', headers=headers).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    response = client.get(base + '/catalog', headers=headers); assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    body = request(e, ['locations:harbor']); p = client.post(base + '/snapshot-preview', headers=headers, json=body); assert p.status_code == 200, p.text
    created = client.post(base + '/snapshots', headers=headers, json={**body, 'preview_digest': p.json()['preview_digest'], 'request_id': 'api-snapshot'})
    assert created.status_code == 201, created.text
    pinbody = {'snapshot_id': created.json()['id'], 'target_project_id': e.target, 'role': 'SIDE_STORY', 'expected_version': 0}
    preview = client.post(base + '/pin-preview', headers=headers, json=pinbody); assert preview.status_code == 200, preview.text
    result = client.post(base + '/pins', headers=headers, json={**pinbody, 'preview_digest': preview.json()['preview_digest'], 'confirmed': True})
    assert result.status_code == 200, result.text
    allowed[0] = False
    for suffix in ['catalog', 'snapshots', 'pins', f"pins/{result.json()['id']}/history"]:
        denied = client.get(base + '/' + suffix, headers=headers); assert denied.status_code == 403 and 'Shared tide' not in denied.text


def test_final_snapshot_projection_failure_rolls_back_no_unknown_saved_copy(universe, monkeypatch):
    e = universe; body = request(e, ['locations:harbor']); preview = e.structured.universe_preview(e.ctx, body)
    before = e.store.read(e.nid, e.ctx.scope)
    monkeypatch.setattr(e.structured, '_universe_snapshot_view', lambda *a: {'content_withheld': True})
    with pytest.raises(FileNotFoundError): e.structured.create_universe_snapshot(e.ctx, {**body, 'preview_digest': preview['preview_digest'], 'request_id': 'revoked-before-return'})
    assert e.store.read(e.nid, e.ctx.scope) == before


def test_target_work_reads_original_pinned_snapshot_without_a_shadow_copy(universe):
    e = universe; snap = snapshot(e, ['locations:harbor']); pinned = pin(e, snap)
    target = replace(e.ctx, novel_id=e.target, scope={'mode': 'local', 'novel_id': e.target})
    before = e.store.read(e.target, target.scope)
    refs = e.structured.universe_incoming(target)
    assert len(refs['items']) == 1 and refs['items'][0]['source_project_id'] == e.nid
    view = e.structured.read_universe_incoming(target, e.nid, pinned['id'])
    assert view['mode'] == 'READ_ONLY' and view['snapshot']['records']['locations:harbor']['name'] == 'Synthetic harbor'
    assert e.store.read(e.target, target.scope) == before
    change(e, 'locations:harbor', {'name': 'Current source name'})
    assert e.structured.read_universe_incoming(target, e.nid, pinned['id'])['snapshot']['records']['locations:harbor']['name'] == 'Synthetic harbor'
    def denied(nid):
        if nid == e.nid: raise HTTPException(403, 'source revoked')
    assert e.structured.universe_incoming(target, authorize_project=denied)['items'] == []
    with pytest.raises(HTTPException): e.structured.read_universe_incoming(target, e.nid, pinned['id'], authorize_project=denied)
    e.structured.release_universe_pin(e.ctx, pinned['id'], {'expected_version': pinned['version']})
    assert e.structured.universe_incoming(target)['items'] == []
    with pytest.raises(FileNotFoundError): e.structured.read_universe_incoming(target, e.nid, pinned['id'])
