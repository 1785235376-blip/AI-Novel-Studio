"""U06 actual File/optional real PG, mounted routing and original executor fences."""
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.audiobook import AudiobookV2Service
from app.experimental.change_impact import ChangeImpactService, node_key
from app.experimental.change_impact_api import create_change_impact_router
from app.experimental.common import StaleSourceError
from app.experimental.media import MediaService
from app.experimental.planning import PlanningService
from app.experimental.production_lineage import ProductionLineageService
from app.experimental.story_graph import StoryGraphService
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from app.source_privacy import content_digest, review_source_privacy
from test_r3_media_support import rig, branch_scope

FLAGS = {'change_impact_v2', 'temporal_story_graph_v2', 'character_mind_v2', 'world_character_engines_v2',
         'asset_lineage_v2', 'production_manifest_v2', 'advanced_planning_v2', 'audiobook_v2',
         'cover_storyboard_generation', 'media_adapter_registry'}


@pytest.fixture
def impact(rig, monkeypatch):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    r = rig
    media = MediaService(r.store, r.novels, r.chapters, r.assets, r.screenplays, production_capture_enabled=lambda: True)
    production = ProductionLineageService(r.store, r.novels, r.chapters, r.assets, media)
    service = ChangeImpactService(r.store, r.novels, r.chapters, StoryGraphService(r.store, r.novels, r.chapters),
        production, PlanningService(r.store, r.novels, r.chapters), AudiobookV2Service(r.store, r.novels, r.chapters, r.assets), enabled=lambda f: f in FLAGS)
    return service


def cover(r, s, chapters=None, character_ids=None):
    b = s.media.create_cover(r.nid, r.scope, r.actor, {'title': 'Synthetic cover', 'prompt': 'PRIVATE_SYNTHETIC_PROMPT',
        'chapter_ids': [r.chapter['id']] if chapters is None else chapters, 'character_ids': character_ids or []})
    t = s.media.queue(r.nid, r.scope, r.actor, {'brief_id': b['id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1', 'candidate_count': 1})
    t = s.media.execute(r.nid, r.scope, r.actor, t['id'], 1)
    return b, t


def edit(r, content='The source has changed. Alice: “Hello again.”'):
    return r.chapters.save(r.chapter['id'], {'content': content})


def query(r, s, kind='CHAPTER', rid=None):
    return s.impact(r.nid, r.scope, {'source': {'kind': kind, 'id': rid or r.chapter['id']}})


def preflight(r, s, task, **kw):
    return s.preflight(r.nid, r.scope, r.actor, {'source': {'kind': 'CHAPTER', 'id': r.chapter['id']},
        'selected': [{'key': node_key('MEDIA_TASK', task['id']), 'expected_version': task['version']}], **kw})


def prepare(r, s, plan, key='one'):
    return s.prepare(r.nid, r.scope, r.actor, plan['id'], {'expected_version': plan['version'],
        'preflight_digest': plan['preflight_digest'], 'idempotency_key': key})['items'][0]


def test_exact_impact_across_graph_knowledge_planning_audio_media_and_exports(rig, impact):
    r, s = rig, impact
    graph = s.graph.create_record(r.nid, r.scope, r.actor, {'kind': 'STORY_RELATION', 'title': 'Visible relation',
        'chapter_id': r.chapter['id'], 'data': {'subject': {'kind': 'CHARACTER', 'id': 'alice'},
        'object': {'kind': 'CHAPTER', 'id': r.chapter['id']}, 'relation': 'ABOUT', 'layer': 'WORLD_FACT', 'statement': 'Alice knows a gate.'}})
    graph = s.graph.review(r.nid, r.scope, r.actor, graph['id'], 'approve', graph['version'])
    knowledge = s.graph.create_record(r.nid, r.scope, r.actor, {'kind': 'KNOWLEDGE_EVENT', 'title': 'Known gate',
        'chapter_id': r.chapter['id'], 'data': {'character_id': 'alice', 'operation': 'LEARN', 'category': 'KNOWN_FACT', 'relation_id': graph['id']}})
    planning = s.planning.create_graph(r.nid, r.scope, r.actor, {'title': 'Recorded planning', 'links': {'chapter_ids': [r.chapter['id']]}})
    audio = s.audiobook.create_plan(r.nid, r.scope, r.actor, {'chapter_id': r.chapter['id']})
    _, task = cover(r, s)
    manifest = s.production.capture(r.nid, r.scope, r.actor, {'task_id': task['id'], 'expected_task_version': task['version']})
    _, unrelated = cover(r, s, chapters=[])
    edit(r)
    result = query(r, s)
    by_key = {n['key']: n for n in result['items']}
    expected = [('WORLD_RECORD', graph['id']), ('WORLD_RECORD', knowledge['id']), ('PLANNING_NODE', planning['root_node_id']),
                ('AUDIO_PLAN', audio['id']), ('SUBTITLES', audio['id']), ('MEDIA_TASK', task['id']), ('EXPORT', manifest['id'])]
    assert all(by_key[node_key(k, rid)]['stale'] for k, rid in expected)
    assert node_key('MEDIA_TASK', unrelated['id']) not in by_key
    assert result['inferred'] == [] and result['unrecorded_dependencies'] == 'UNKNOWN'
    assert not result['automatic_regeneration']
    assert 'PRIVATE_SYNTHETIC_PROMPT' not in json.dumps(result)
    assert all(n['evidence_type'] == 'EXACT_RECORDED_EDGE' for n in result['items'])
    s.enabled = lambda f: f in FLAGS - {'character_mind_v2', 'audiobook_v2', 'production_manifest_v2'}
    reduced = json.dumps(query(r, s))
    assert knowledge['id'] not in reduced and audio['id'] not in reduced and manifest['id'] not in reduced


def test_selected_refresh_atomic_idempotent_new_snapshots_original_outcome_unchanged(rig, impact):
    r, s = rig, impact
    original_brief, original_task = cover(r, s)
    _, unrelated = cover(r, s, chapters=[])
    edit(r)
    before_original = s.media.get(r.nid, r.scope, s.media.TASKS, original_task['id'])
    before_unrelated = s.media.get(r.nid, r.scope, s.media.TASKS, unrelated['id'])
    plan = preflight(r, s, original_task)
    assert plan['ready'] and plan['cost']['estimate_microusd'] == 0
    assert len(s.media.tasks(r.nid, r.scope)) == 2
    refreshed = prepare(r, s, plan)
    assert prepare(r, s, plan) == refreshed
    assert len(s.media.tasks(r.nid, r.scope)) == 3
    task = s.media.get(r.nid, r.scope, s.media.TASKS, refreshed['task_id'])
    assert task['sources'][r.chapter['id']]['version'] == r.chapters.get(r.chapter['id'])['version']
    assert task['brief_id'] != original_brief['id']
    assert task['status'] == 'QUEUED' and not task['proposal_ids']
    result = s.execute(r.nid, r.scope, r.actor, refreshed['id'], refreshed['task_version'])
    assert result['status'] == 'SUCCEEDED' and result['source_current']
    assert result['outputs'][0]['status'] == 'PENDING_REVIEW'
    assert not r.assets.list(r.nid)
    assert s.media.get(r.nid, r.scope, s.media.TASKS, original_task['id']) == before_original
    assert s.media.get(r.nid, r.scope, s.media.TASKS, unrelated['id']) == before_unrelated
    assert next(n for n in query(r, s)['items'] if n['key'] == node_key('MEDIA_TASK', original_task['id']))['stale']
    restored = ChangeImpactService(ExperimentalStore(r.root, r.backend, r.store.database_url), r.novels, r.chapters,
        s.graph, s.production, s.planning, s.audiobook, enabled=s.enabled)
    assert restored.refreshes(r.nid, r.scope, r.actor)['items'][0]['status'] == 'SUCCEEDED'


def test_locks_version_conflicts_actor_branch_and_current_source_fences(rig, impact):
    r, s = rig, impact; _, task = cover(r, s); edit(r)
    plan = preflight(r, s, task)
    lock = {'key': node_key('MEDIA_TASK', task['id']), 'expected_version': task['version'], 'expected_lock_version': 0, 'locked': True}
    locked = s.set_lock(r.nid, r.scope, r.actor, lock)
    assert locked['locked'] and not locked['refresh_candidate']
    with pytest.raises(CapabilityVersionConflict): s.set_lock(r.nid, r.scope, r.actor, lock)
    with pytest.raises(StaleSourceError): prepare(r, s, plan)
    s.set_lock(r.nid, r.scope, r.actor, {**lock, 'expected_lock_version': 1, 'locked': False})
    assert preflight(r, s, task)['ready']
    plan = preflight(r, s, task)
    with pytest.raises(FileNotFoundError): s.prepare(r.nid, r.scope, 'other-author', plan['id'], {'expected_version': 1, 'preflight_digest': plan['preflight_digest'], 'idempotency_key': 'x'})
    with pytest.raises(FileNotFoundError): s.impact(r.nid, branch_scope(r), {'source': {'kind': 'CHAPTER', 'id': r.chapter['id']}})
    edit(r, 'A newer version.')
    with pytest.raises(StaleSourceError): prepare(r, s, plan)
    assert len(s.media.tasks(r.nid, r.scope)) == 1


def test_current_privacy_and_revocation_at_final_dispatch(rig, impact):
    r, s = rig, impact; _, task = cover(r, s); edit(r)
    plan = preflight(r, s, task); refreshed = prepare(r, s, plan)
    chapter = r.chapters.get(r.chapter['id'])
    review_source_privacy(chapter, None, r.actor, 'LOCAL_ONLY', chapter['version'], content_digest(chapter), r.root)
    with pytest.raises(StaleSourceError): s.execute(r.nid, r.scope, r.actor, refreshed['id'], 1)
    plan = preflight(r, s, task); refreshed = prepare(r, s, plan, 'second')
    checks = 0
    def revoke():
        nonlocal checks
        checks += 1
        if checks >= 8: raise ValueError('revoked')
    with pytest.raises(ValueError, match='revoked'):
        s.execute(r.nid, r.scope, r.actor, refreshed['id'], 1, revoke)
    assert not s.media.get(r.nid, r.scope, s.media.TASKS, refreshed['task_id'])['proposal_ids']


def test_cancel_and_changed_source_during_original_executor_discard_old_output(rig, impact, monkeypatch):
    r, s = rig, impact; _, task = cover(r, s); edit(r)
    plan = preflight(r, s, task); refreshed = prepare(r, s, plan)
    adapter = s.media.registry.resolve('mock-image-v1', 'cover_generation')
    original = adapter.generate; entered, release = Event(), Event()
    def blocked(request):
        entered.set(); assert release.wait(10); return original(request)
    monkeypatch.setattr(adapter, 'generate', blocked)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(s.execute, r.nid, r.scope, r.actor, refreshed['id'], 1)
        assert entered.wait(10)
        current = s.media.get(r.nid, r.scope, s.media.TASKS, refreshed['task_id'])
        cancelled = s.cancel(r.nid, r.scope, r.actor, refreshed['id'], current['version'])
        release.set()
        assert future.result()['status'] == cancelled['status'] == 'CANCELLED'
    assert not s.media.get(r.nid, r.scope, s.media.TASKS, refreshed['task_id'])['proposal_ids']
    plan = preflight(r, s, task); newer = prepare(r, s, plan, 'next')
    entered.clear(); release.clear()
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(s.execute, r.nid, r.scope, r.actor, newer['id'], 1)
        assert entered.wait(10); edit(r, 'Newer source during callback.'); release.set()
        with pytest.raises(StaleSourceError): future.result()
    row = s.media.get(r.nid, r.scope, s.media.TASKS, newer['task_id'])
    assert row['status'] == 'FAILED' and not row['proposal_ids']
    assert not s.refreshes(r.nid, r.scope, r.actor)['items'][-1]['source_current']


def test_cross_scope_ancestor_never_leaks_ids_titles_or_counts_and_rename_is_display_only(rig, impact, monkeypatch):
    r, s = rig, impact; _, task = cover(r, s, character_ids=['alice'])
    before = r.chapters.get(r.chapter['id'])
    r.novels.upsert_character(r.nid, 'alice', {'name': 'Renamed Alice', 'personality': 'Careful'})
    result = query(r, s, 'CHARACTER', 'alice')
    assert result['source']['label'] == 'Renamed Alice' and result['rename_policy'].startswith('STABLE_ID')
    assert any(n['id'] == task['id'] and n['stale'] for n in result['items'])
    assert r.chapters.get(r.chapter['id']) == before
    dataset = r.novels.data_set
    monkeypatch.setattr(r.novels, 'data_set', lambda nid, name: [{**row, 'name': 'DENIED_PARENT_NAME', 'branch_id': 'other-branch'} for row in dataset(nid, name)] if name == 'characters' else dataset(nid, name))
    result = query(r, s)
    assert result['items'] == []
    serial = json.dumps(result)
    assert task['id'] not in serial and 'alice' not in serial and 'DENIED_PARENT_NAME' not in serial


def test_unsupported_and_current_nodes_cannot_run_and_no_arbitrary_recipe(rig, impact):
    r, s = rig, impact; brief, task = cover(r, s)
    assert not preflight(r, s, task)['ready']
    edit(r)
    original = s.media.registry.resolve('mock-image-v1', 'cover_generation')
    original.definition = original.definition.model_copy(update={'local': False})
    blocked = preflight(r, s, task)
    assert not blocked['ready'] and blocked['cost']['estimate_microusd'] is None
    with pytest.raises(StaleSourceError): prepare(r, s, blocked)
    with pytest.raises(ValueError): s.preflight(r.nid, r.scope, r.actor, {'source': {'kind': 'CHAPTER', 'id': r.chapter['id']}, 'selected': [{'key': node_key('MEDIA_TASK', task['id']), 'expected_version': task['version']}], 'replacement_prompt': 'not allowed'})


def test_mounted_private_api_cas_current_authority_and_default_off_v1(rig, impact, monkeypatch):
    r, s = rig, impact; _, task = cover(r, s); edit(r)
    from app.experimental.flags import require_flag, enabled_flags
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    s.enabled = lambda f: f in enabled_flags()
    permissions = {'allowed': True}
    def authorize(nid, token, branch, permission):
        assert permission == 'domain.write'
        if token != 'author' or not permissions['allowed']: raise HTTPException(403, 'forbidden')
        return r.actor, r.scope if not branch else branch_scope(r, branch)
    app = FastAPI(); app.include_router(create_change_impact_router(s, authorize, require_flag), prefix='/api')
    client = TestClient(app); base = f'/api/novels/{r.nid}/experimental/change-impact'; headers = {'X-Session-Token': 'author'}
    assert client.get(base + '/sources').status_code == 403
    response = client.post(base + '/query', headers=headers, json={'source': {'kind': 'CHAPTER', 'id': r.chapter['id']}})
    assert response.status_code == 200 and response.headers['cache-control'] == 'no-store'
    plan = client.post(base + '/preflights', headers=headers, json={'source': {'kind': 'CHAPTER', 'id': r.chapter['id']}, 'selected': [{'key': node_key('MEDIA_TASK', task['id']), 'expected_version': task['version']}]}).json()
    refreshed = client.post(base + f"/preflights/{plan['id']}/prepare", headers=headers, json={'expected_version': 1, 'preflight_digest': plan['preflight_digest'], 'idempotency_key': 'mounted'}).json()['items'][0]
    permissions['allowed'] = False
    assert client.post(base + f"/refreshes/{refreshed['id']}/execute", headers=headers, json={'expected_task_version': 1}).status_code == 403
    permissions['allowed'] = True
    for state in ('off', 'v1'):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', '' if state == 'off' else ','.join(FLAGS))
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true' if state == 'v1' else 'false')
        assert client.get(base + '/sources', headers=headers).status_code == 404
        assert client.post(base + f"/refreshes/{refreshed['id']}/execute", headers=headers, json={'expected_task_version': 1}).status_code == 404
        with pytest.raises(FileNotFoundError):
            s.media.execute(r.nid, r.scope, r.actor, refreshed['task_id'], 1)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    with pytest.raises(ValueError, match='DISPATCH_AUTHORITY_REQUIRED'):
        s.media.execute(r.nid, r.scope, r.actor, refreshed['task_id'], 1)
    s.media.transition(r.nid, r.scope, r.actor, refreshed['task_id'], 'cancel', 1)
    with pytest.raises(ValueError, match='NEW_PREFLIGHT'):
        s.media.transition(r.nid, r.scope, r.actor, refreshed['task_id'], 'retry', 2)


def test_original_broker_reserve_dispatch_settlement_budget_change_and_cancel_recovery(rig, impact):
    from app.experimental.model_broker import ModelBrokerService
    from app.runtime import Runtime
    from app.stable_identity import StableIdentityStore
    r, s = rig, impact
    broker = ModelBrokerService(r.store, r.novels, r.chapters,
        runtime=Runtime(StableIdentityStore(r.root / 'runtime-ids.json')), media_registry=s.media.registry)
    s.production.broker = broker; s.production.broker_enabled = lambda: True
    _, task = cover(r, s); edit(r)
    plan = preflight(r, s, task); assert plan['ready']
    refreshed = prepare(r, s, plan)
    assert broker.ledger(r.nid, r.scope, r.actor) == []
    assert s.execute(r.nid, r.scope, r.actor, refreshed['id'], 1)['status'] == 'SUCCEEDED'
    ledger = broker.ledger(r.nid, r.scope, r.actor)
    assert len(ledger) == 1 and ledger[0]['status'] == 'SETTLED' and ledger[0]['actual_microusd'] == 0
    plan = preflight(r, s, task); refreshed = prepare(r, s, plan, 'next')
    broker.configure_budget(r.nid, r.scope, r.actor, {'expected_version': 0, 'limit_microusd': 0})
    with pytest.raises(StaleSourceError, match='BUDGET_CHANGED'): s.execute(r.nid, r.scope, r.actor, refreshed['id'], 1)
    assert s.media.get(r.nid, r.scope, s.media.TASKS, refreshed['task_id'])['status'] == 'QUEUED'
    plan = preflight(r, s, task); refreshed = prepare(r, s, plan, 'after-budget')
    private = s.get(r.nid, r.scope, s.PLANS, plan['id'])['entries'][0]
    entry = broker.reserve(r.nid, r.scope, r.actor, private['broker_decision_id'], private['broker_decision_version'], 'change-impact:' + refreshed['id'], refreshed['task_id'])
    assert broker.budget(r.nid, r.scope)['inflight'] == 1
    assert s.get(r.nid, r.scope, s.REFRESHES, refreshed['id'])['reservation_id'] is None
    s.cancel(r.nid, r.scope, r.actor, refreshed['id'], 1)
    assert broker.get(r.nid, r.scope, broker.LEDGER, entry['id'])['status'] == 'RELEASED'
    assert broker.budget(r.nid, r.scope)['inflight'] == 0


def test_atomic_rollback_and_concurrent_idempotent_prepare(rig, impact, monkeypatch):
    r, s = rig, impact; _, task = cover(r, s); _, second = cover(r, s); edit(r)
    plan = s.preflight(r.nid, r.scope, r.actor, {'source': {'kind': 'CHAPTER', 'id': r.chapter['id']}, 'selected': [
        {'key': node_key('MEDIA_TASK', t['id']), 'expected_version': t['version']} for t in (task, second)]})
    original = s.media.prepare_task; calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2: raise ValueError('atomic interrupted')
        return original(*args, **kwargs)
    monkeypatch.setattr(s.media, 'prepare_task', fail_second)
    with pytest.raises(ValueError, match='atomic interrupted'): prepare(r, s, plan)
    assert len(s.media.tasks(r.nid, r.scope)) == 2
    assert len(s.media.list(r.nid, r.scope, s.media.BRIEFS)) == 2
    assert s.refreshes(r.nid, r.scope, r.actor)['items'] == []
    monkeypatch.setattr(s.media, 'prepare_task', original)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outputs = list(pool.map(lambda _: prepare(r, s, plan), range(2)))
    assert outputs[0]['id'] == outputs[1]['id']
    assert len(s.media.tasks(r.nid, r.scope)) == 4
    assert len(s.refreshes(r.nid, r.scope, r.actor)['items']) == 2


def test_owned_media_legacy_lists_preview_reviews_queue_and_conflicts_hide_when_off(rig, impact, monkeypatch):
    r, s = rig, impact; original_brief, original = cover(r, s); edit(r)
    plan = preflight(r, s, original); refreshed = prepare(r, s, plan)
    task = s.media.get(r.nid, r.scope, s.media.TASKS, refreshed['task_id'])
    with pytest.raises(ValueError, match='OWNED_BRIEF'):
        s.media.queue(r.nid, r.scope, r.actor, {'brief_id': task['brief_id'], 'expected_brief_version': 1, 'adapter_id': 'mock-image-v1', 'candidate_count': 1})
    result = s.execute(r.nid, r.scope, r.actor, refreshed['id'], 1)
    pid = result['outputs'][0]['id']
    assert s.media.preview(r.nid, r.scope, pid)[0]
    for acceptance in ('false', 'true'):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS - {'change_impact_v2'}) if acceptance == 'false' else ','.join(FLAGS))
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', acceptance)
        assert [r['id'] for r in s.media.tasks(r.nid, r.scope)] == [original['id']]
        assert [r['id'] for r in s.media.list(r.nid, r.scope, s.media.BRIEFS)] == [original_brief['id']]
        assert [r['id'] for r in s.media.proposals(r.nid, r.scope)] == original['proposal_ids']
        for action in ('approve', 'reject', 'reopen'):
            with pytest.raises(FileNotFoundError): s.media.review(r.nid, r.scope, r.actor, pid, action, 999)
        with pytest.raises(FileNotFoundError): s.media.preview(r.nid, r.scope, pid)
        with pytest.raises(FileNotFoundError): s.media.transition(r.nid, r.scope, r.actor, task['id'], 'retry', 999)
        with pytest.raises(FileNotFoundError): s.media.update_cover(r.nid, r.scope, r.actor, task['brief_id'], 999, {'title': 'cannot overwrite'})
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS)); monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    with r.store.transaction(r.nid, r.scope) as doc:
        doc['collections'][s.media.TASKS][task['id']]['change_impact_refresh_id'] = {'malformed': True}
    assert [r['id'] for r in s.media.tasks(r.nid, r.scope)] == [original['id']]
    assert [r['id'] for r in s.media.proposals(r.nid, r.scope)] == original['proposal_ids']


def test_real_screenplay_source_versions_propagate_to_shots_storyboards_and_motion(rig, impact):
    r, s = rig, impact
    screenplay = r.screenplays.create(r.nid)
    screenplay = r.screenplays.approve(r.nid, screenplay['id'], screenplay['edit_version'])
    screenplay = r.screenplays.plan_shots(r.nid, screenplay['id'], screenplay['edit_version'])
    screenplay = r.screenplays.approve_shots(r.nid, screenplay['id'], screenplay['edit_version'])
    screenplay = r.screenplays.plan_storyboard(r.nid, screenplay['id'], screenplay['edit_version'])
    # Existing recorded references only; no provider probing or video calls.
    shot = screenplay['shots'][0]; frame = screenplay['storyboard'][0]
    r.screenplays._save_screenplay(r.nid, {**screenplay, 'motion_task_revision': 1,
        'motion_tasks': [{'id': 'synthetic-motion', 'start_frame': 'storyboard:' + frame['id'], 'end_frame': 'shot:' + shot['id'], 'status': 'PENDING'}]})
    edit(r)
    result = query(r, s)
    for kind in ('SCREENPLAY_SCENE', 'SHOT', 'STORYBOARD_FRAME', 'MOTION_TASK'):
        rows = [row for row in result['items'] if row['kind'] == kind]
        assert len(rows) == 1 and rows[0]['stale'] and not rows[0]['refresh_candidate']
    assert not s.media.tasks(r.nid, r.scope)


def test_actor_bound_research_records_never_enter_unscoped_impact_projection(rig, impact):
    r, s = rig, impact
    ordinary = s.graph.create_record(r.nid, r.scope, r.actor, {'kind': 'STORY_RELATION', 'title': 'Allowed relation',
        'chapter_id': r.chapter['id'], 'data': {'subject': {'kind': 'CHARACTER', 'id': 'alice'}, 'object': {'kind': 'CHAPTER', 'id': r.chapter['id']},
        'relation': 'ABOUT', 'layer': 'WORLD_FACT', 'statement': 'Ordinary evidence'}})
    research = {**copy.deepcopy(ordinary), 'id': 'private-research-node', 'title': 'PRIVATE_RESEARCH_TITLE',
        'research_sources': {'private-source': {'version': 1}}, 'status': 'RESEARCH_REVIEWED'}
    child = {**copy.deepcopy(ordinary), 'id': 'private-research-child', 'title': 'PRIVATE_RESEARCH_CHILD',
        'semantic_sources': {research['id']: {'version': 1, 'digest': 'synthetic'}}}
    with r.store.transaction(r.nid, r.scope) as doc:
        doc['collections'][s.graph.RECORDS].update({research['id']: research, child['id']: child})
    for available in (FLAGS, FLAGS | {'research_library_v2'}):
        s.enabled = lambda flag: flag in available
        projection = query(r, s)
        assert [row['id'] for row in projection['items']] == [ordinary['id']]
        serialized = json.dumps([projection, s.catalog(r.nid, r.scope)])
        for secret in ('private-research-node', 'private-research-child', 'PRIVATE_RESEARCH_TITLE', 'PRIVATE_RESEARCH_CHILD', 'private-source'):
            assert secret not in serialized
        with pytest.raises(FileNotFoundError): query(r, s, 'WORLD_RECORD', research['id'])


def test_refresh_manifest_keeps_current_origin_and_feature_visibility(rig, impact):
    r, s = rig, impact; _, original = cover(r, s); edit(r)
    refreshed = prepare(r, s, preflight(r, s, original))
    completed = s.execute(r.nid, r.scope, r.actor, refreshed['id'], 1)
    manifest = s.production.capture(r.nid, r.scope, r.actor, {'task_id': completed['task_id'], 'expected_task_version': completed['task_version']})
    stored = s.production.get(r.nid, r.scope, s.production.MANIFESTS, manifest['id'])
    assert stored['origin']['refresh_id'] == refreshed['id']
    assert s.production.preflight(r.nid, r.scope, r.actor, manifest['id'], 1)['ready']
    edit(r, 'A further change requires fresh preparation.')
    assert not s.production.preflight(r.nid, r.scope, r.actor, manifest['id'], 1)['ready']


def test_simulation_proposals_use_original_visibility_without_private_ids_or_counts(rig, impact, monkeypatch):
    from app.experimental.story_simulator import StorySimulatorService
    r, s = rig, impact
    StorySimulatorService(r.store, r.novels, r.chapters, s.planning, s.graph)
    graph = s.planning.create_graph(r.nid, r.scope, r.actor, {'title': 'Original plan', 'links': {'chapter_ids': [r.chapter['id']]}})
    ordinary = s.planning.create_proposal(r.nid, r.scope, r.actor, {'node_id': graph['root_node_id'], 'expected_node_version': 1,
        'title': 'Ordinary proposal', 'links': {'chapter_ids': [r.chapter['id']]}})
    derived = {**copy.deepcopy(ordinary), 'id': 'private-simulation-proposal', 'title': 'PRIVATE_SIMULATION_TITLE',
        'simulation_provenance': {'run_id': 'unavailable-private-run', 'route_id': 'private-route', 'input_digest': 'synthetic'}}
    with r.store.transaction(r.nid, r.scope) as doc: doc['collections'][s.planning.PROPOSALS][derived['id']] = derived
    for configured in (FLAGS, FLAGS | {'story_simulator_v2'}):
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(configured))
        result = query(r, s)
        assert [n['id'] for n in result['items'] if n['kind'] == 'PLANNING_PROPOSAL'] == [ordinary['id']]
        serial = json.dumps(result)
        assert derived['id'] not in serial and derived['title'] not in serial and 'unavailable-private-run' not in serial


def test_storyboard_selected_refresh_reuses_current_original_shot_authority(rig, impact):
    r, s = rig, impact
    screenplay = r.screenplays.create(r.nid)
    screenplay = r.screenplays.approve(r.nid, screenplay['id'], screenplay['edit_version'])
    screenplay = r.screenplays.plan_shots(r.nid, screenplay['id'], screenplay['edit_version'])
    shot = screenplay['shots'][0]
    brief = s.media.create_storyboard(r.nid, r.scope, r.actor, {'screenplay_id': screenplay['id'],
        'shot_id': shot['id'], 'expected_screenplay_version': screenplay['edit_version']})
    original = s.media.queue(r.nid, r.scope, r.actor, {'brief_id': brief['id'], 'expected_brief_version': 1,
        'adapter_id': 'mock-image-v1', 'candidate_count': 1})
    original = s.media.execute(r.nid, r.scope, r.actor, original['id'], 1)
    r.screenplays.update_shot(r.nid, screenplay['id'], shot['id'], {**shot, 'expected_version': screenplay['edit_version'], 'action': 'Updated original shot action.'})
    plan = preflight(r, s, original)
    assert plan['ready'], plan
    refreshed = prepare(r, s, plan)
    complete = s.execute(r.nid, r.scope, r.actor, refreshed['id'], 1)
    assert complete['status'] == 'SUCCEEDED'
    task = s.media.get(r.nid, r.scope, s.media.TASKS, complete['task_id'])
    assert task['brief_snapshot']['kind'] == 'STORYBOARD'
    assert task['brief_snapshot']['shot_snapshot']['action'] == 'Updated original shot action.'
    assert original['brief_snapshot']['shot_snapshot']['action'] == shot['action']
