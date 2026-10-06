"""Original-scene temporal knowledge and last-hop authority contracts."""
import copy
import json
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.experimental.character_author_context import CharacterContextSource, configure_character_job, resolve_character_author_context
from app.experimental.common import StaleSourceError
from app.experimental.story_graph import StoryGraphService
from app.experimental.story_graph_api import create_story_graph_router
from app.experimental.story_simulator import StorySimulatorService
from app.experimental.store import ExperimentalStore
from app.jobs import Job
from test_r3_planning import planning_env
from test_r4_story_graph import env, make, relation, learn


def scenes(e, chapter=2):
    plan = e.service.create_graph(e.nid, e.scope, 'author', {'title': 'Original planning'})
    def create(parent, level, title, position=0):
        return e.service.create_node(e.nid, e.scope, 'author', {'graph_id': plan['id'], 'parent_id': parent,
            'level': level, 'title': title, 'position': position,
            'links': {'chapter_ids': [e.order[chapter - 1]]} if level != 'VOLUME' else {}})
    volume = create(plan['root_node_id'], 'VOLUME', 'Volume')
    chapter_node = create(volume['id'], 'CHAPTER', 'Chapter')
    return create(chapter_node['id'], 'SCENE', 'Before reveal', 10), create(chapter_node['id'], 'SCENE', 'After reveal', 20)


def at(e, scene, chapter=2):
    return e.graph.character_context(e.nid, e.scope, 'alice', e.order[chapter - 1], scene_id=scene['id'])


def test_exact_scene_boundary_excludes_future_secret_nodes_counts_and_model_context(env):
    e = env; before, after = scenes(e); secret = 'ONLY_LATER_SCENE_PASSWORD_蓝'
    r = relation(e, secret); learn(e, r, chapter=2, scene_id=after['id'])
    assert secret not in json.dumps(at(e, before), ensure_ascii=False)
    query = e.graph.graph(e.nid, e.scope, e.order[1], 'alice', scene_id=before['id'])
    assert query['nodes'] == query['edges'] == [] and query['visible_count'] == 0
    assert at(e, after)['secrets'][0]['text'] == secret
    assert at(e, after)['scene_boundary']['position'] == 20
    assert e.graph.character_context(e.nid, e.scope, 'alice', e.order[1])['secrets']
    restarted = StoryGraphService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
    assert restarted.character_context(e.nid, e.scope, 'alice', e.order[1], scene_id=after['id']) == at(e, after)


def test_unknown_scene_never_invents_timing_or_resurrects_prior_knowledge(env):
    e = env; before, _ = scenes(e); r = relation(e)
    learn(e, r, chapter=1); learn(e, r, chapter=2, operation='FORGET')
    assert not at(e, before)['secrets']
    make(e, 'KNOWLEDGE_EVENT', {'character_id': 'alice', 'operation': 'SET_STATE', 'category': 'EMOTION', 'value': 'Unknown scene panic'}, chapter=2)
    assert not at(e, before)['emotion']


def test_foreign_chapter_scene_and_ambiguous_original_positions_fail_closed(env):
    e = env; before, after = scenes(e)
    with pytest.raises(ValueError, match='selected chapter'): at(e, before, chapter=1)
    with pytest.raises(ValueError, match='selected chapter'): relation(e, scene_id=before['id'])
    e.service.edit_node(e.nid, e.scope, 'author', after['id'], {'title': after['title'], 'expected_version': after['version'], 'position': before['position'], 'links': after['links']})
    with pytest.raises(ValueError, match='ambiguous'): at(e, before)


def test_scene_reorder_source_drift_archival_are_bound_to_original_authority(env):
    e = env; before, after = scenes(e); r = relation(e)
    event = learn(e, r, chapter=2, scene_id=after['id'])
    assert at(e, after)['secrets']
    e.service.edit_node(e.nid, e.scope, 'author', after['id'], {'title': after['title'], 'expected_version': after['version'], 'position': 5, 'links': after['links']})
    assert not at(e, before)['secrets']
    assert e.graph.record(e.nid, e.scope, event['id'])['stale']


def test_relationship_state_stays_character_claim_and_false_belief_hides_truth(env):
    e = env; first, _ = scenes(e)
    r = relation(e, 'Bob secretly hates Alice', relation='HATES', object={'kind': 'CHARACTER', 'id': 'alice'})
    make(e, 'KNOWLEDGE_EVENT', {'character_id': 'alice', 'operation': 'SET_STATE', 'category': 'RELATIONSHIP_STATE',
         'relation_id': r['id'], 'state_key': 'bob', 'value': 'I trust Bob', 'scene_id': first['id']}, chapter=2)
    learn(e, r, operation='MISUNDERSTAND', category='FALSE_BELIEF', value='Bob is my ally', scene_id=first['id'])
    result = at(e, first)
    assert result['relationships'][0]['text'] == 'I trust Bob'
    assert result['relationships'][0]['epistemic_status'] == 'RELATIONSHIP_STATE'
    assert result['false_beliefs'][0]['text'] == 'Bob is my ally'
    assert 'secretly hates' not in json.dumps(result)
    assert not e.graph.graph(e.nid, e.scope, e.order[1], 'alice', scene_id=first['id'])['edges']


@pytest.mark.parametrize('verb', ['KNOWS', 'BELIEVES', 'BELONGS_TO', 'HATES', 'TRUSTS', 'RELATED_TO', 'APPEARS_IN'])
def test_requested_relation_types_are_metadata_never_implicit_character_knowledge(env, verb):
    e = env; r = relation(e, relation=verb)
    assert e.graph.graph(e.nid, e.scope, e.order[3])['edges'][0]['relation'] == verb
    assert not e.graph.character_context(e.nid, e.scope, 'bob', e.order[3])['known_facts']
    assert r['version'] == 2


def test_original_object_concept_and_legacy_item_both_remain_supported(env):
    e = env
    for kind in ('OBJECT', 'ITEM'):
        concept = make(e, 'STORY_CONCEPT', {'concept_type': kind, 'description': 'Reviewable object'})
        assert relation(e, object={'kind': kind, 'id': concept['id']})['status'] == 'APPROVED'


def test_scene_character_binding_rechecks_newer_position_before_model_dispatch(env, monkeypatch):
    e = env; first, later = scenes(e); r = relation(e); learn(e, r, scene_id=later['id'])
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'world_character_engines_v2,temporal_story_graph_v2,character_mind_v2')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    ctx = CharacterContextSource(novel_id=e.nid, scope=e.scope, actor='author', service=e.graph, user_instruction='Safe scene-only request')
    job = Job('scene-contract', 'continue', e.nid, e.order[1], '', 'LOCAL_ONLY')
    configure_character_job(job, ctx, 'alice', e.order[1], scene_id=first['id'], authorize=lambda: ('author', e.scope))
    assert not resolve_character_author_context(job, cloud=False)['character_viewpoint']['secrets']
    assert job.character_viewpoint['scene_id'] == first['id']
    e.service.edit_node(e.nid, e.scope, 'author', first['id'], {'title': first['title'], 'expected_version': first['version'], 'position': 30, 'links': first['links']})
    with pytest.raises(StaleSourceError): resolve_character_author_context(job, cloud=False)


def test_simulator_receipt_includes_distinct_reviewed_mind_and_scene_without_leak(env):
    e = env; first, later = scenes(e); secret = relation(e, 'Future hidden secret'); learn(e, secret, scene_id=later['id'])
    for category in ('FEAR', 'VALUE', 'EMOTION', 'INTENT'):
        make(e, 'KNOWLEDGE_EVENT', {'character_id': 'alice', 'operation': 'SET_STATE', 'category': category,
            'value': category + ' personal claim', 'scene_id': first['id']}, chapter=2)
    sim = StorySimulatorService(e.store, e.novels, e.chapter_service, e.service, e.graph)
    result = sim.context(e.nid, e.scope, {'chapter_id': e.order[1], 'expected_version': 1, 'character_id': 'alice', 'scene_id': first['id']})
    assert result['scene_id'] == first['id'] and result['mind']['emotion'][0]['text'] == 'EMOTION personal claim'
    assert 'Future hidden secret' not in json.dumps(result)
    assert not result['knowledge']


def test_graph_api_revocation_at_read_return_and_write_commit_is_atomic(env, monkeypatch):
    e = env; revoked = [False]
    def auth(nid, token, branch, permission):
        if revoked[0]: raise HTTPException(403, 'Revoked')
        return 'author', e.scope
    app = FastAPI(); app.include_router(create_story_graph_router(e.graph, auth, lambda _: None))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/story-graph'
    original = e.graph.character_context
    def read(*args, **kw):
        value = original(*args, **kw); revoked[0] = True; return value
    monkeypatch.setattr(e.graph, 'character_context', read)
    response = client.post(base + '/character-context', json={'character_id': 'alice', 'chapter_id': e.order[0]})
    assert response.status_code == 403
    revoked[0] = False; before = copy.deepcopy(e.store.read(e.nid, e.scope))
    def revoke(*_): revoked[0] = True
    monkeypatch.setattr(e.graph, '_after_record_mutation', revoke)
    response = client.post(base + '/records', json={'kind': 'STORY_CONCEPT', 'title': 'Candidate', 'chapter_id': e.order[0], 'data': {'concept_type': 'OBJECT'}})
    assert response.status_code == 403 and e.store.read(e.nid, e.scope) == before


def test_simulator_step_effects_are_actual_rule_delta_and_history_is_persisted(env):
    e = env; sim = StorySimulatorService(e.store, e.novels, e.chapter_service, e.service, e.graph)
    plan = e.service.create_graph(e.nid, e.scope, 'author', {'title': 'Plan', 'links': {'chapter_ids': [e.order[3]]}})
    context = sim.context(e.nid, e.scope, {'chapter_id': e.order[3], 'expected_version': 1, 'character_id': 'alice'})
    row = sim.create_run(e.nid, e.scope, 'author', {'chapter_ids': [e.order[3]], 'expected_versions': {e.order[3]: 1}, 'chapter_id': e.order[3],
        'character_id': 'alice', 'context_digest': context['context_digest'], 'node_id': plan['root_node_id'], 'expected_node_version': 1,
        'assumptions': ['outside'], 'resources': {'coin': 2}, 'routes': [
            {'id': 'good', 'title': 'Pay', 'events': [{'id': 'pay', 'title': 'Pay toll', 'at': 3, 'adds': ['inside'], 'removes': ['outside'], 'resource_delta': {'coin': -1}}]},
            {'id': 'bad', 'title': 'Cannot pay', 'events': [{'id': 'pay', 'title': 'Pay too much', 'at': 3, 'adds': ['inside'], 'resource_delta': {'coin': -3}}]}]})
    result = sim.step(e.nid, e.scope, 'author', row['id'], 1)
    good, bad = [route['steps'][0]['rule_effects'] for route in result['routes']]
    assert good['facts_added'] == ['inside'] and good['facts_removed'] == ['outside']
    assert good['resource_changes'] == {'coin': {'before': 2, 'after': 1}}
    assert good['time_before'] is None and good['time_after'] == 3
    assert bad['facts_added'] == [] and bad['resource_changes'] == {} and bad['time_after'] is None
    assert good['interpretation'] == 'HYPOTHETICAL_RULE_EFFECTS_NOT_WORLD_FACTS'
    assert result['history_receipts'][0]['version'] == 1
    assert set(result['history_receipts'][0]) == {'version', 'status', 'updated_at', 'expansions', 'request_digest', 'result_digest'}


def test_moved_or_archived_forgetting_scene_never_resurrects_old_secret(env):
    e = env; first, later = scenes(e); r = relation(e); learn(e, r, chapter=1)
    forget = learn(e, r, chapter=2, scene_id=first['id'], operation='FORGET')
    assert not at(e, later)['secrets']
    e.service.edit_node(e.nid, e.scope, 'author', first['id'], {'title': first['title'], 'expected_version': first['version'], 'position': 30, 'links': first['links']})
    assert not at(e, later)['secrets'], 'A stale forget cannot be moved into the future by changing its Scene'
    assert e.graph.record(e.nid, e.scope, forget['id'])['stale']


@pytest.mark.parametrize('position', [10, 10**12])
def test_chapter_end_legacy_timing_applies_after_explicit_scenes(env, position):
    e = env; first, _ = scenes(e); r = relation(e)
    if position != first['position']:
        first = e.service.edit_node(e.nid, e.scope, 'author', first['id'], {'title': first['title'], 'expected_version': first['version'], 'position': position, 'links': first['links']})
    learn(e, r, chapter=2, scene_id=first['id'])
    make(e, 'KNOWLEDGE_EVENT', {'character_id': 'alice', 'operation': 'FORGET', 'category': 'SECRET', 'relation_id': r['id']}, chapter=2, event_order=10)
    assert not e.graph.character_context(e.nid, e.scope, 'alice', e.order[1])['secrets']
    assert not at(e, first)['secrets'], 'Unplaced same-chapter forget is an uncertainty fence'
