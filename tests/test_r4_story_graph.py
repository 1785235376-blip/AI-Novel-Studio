"""Temporal/mind privacy invariants against durable File and real PostgreSQL."""
import copy
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.experimental.common import StaleSourceError
from app.experimental.story_graph import StoryGraphService
from app.experimental.story_graph_api import create_story_graph_router
from app.experimental.world import WorldService
from app.experimental.world_api import create_world_router
from app.experimental.store import ExperimentalStore
from app.services.v1_capability_service import CapabilityVersionConflict
from test_r3_planning import planning_env


@pytest.fixture
def env(planning_env):
    e = planning_env
    e.graph = StoryGraphService(e.store, e.novels, e.chapter_service)
    e.world = WorldService(e.store, e.novels, e.chapter_service)
    return e


def make(e, kind, data, chapter=1, approve=True, **kwargs):
    row = e.graph.create_record(e.nid, e.scope, 'author', {'kind': kind, 'title': kind, 'chapter_id': e.order[chapter-1], 'data': data, **kwargs})
    if approve: row = e.graph.review(e.nid, e.scope, 'reviewer', row['id'], 'approve', row['version'])
    return row


def relation(e, text='The key opens the east gate', **kwargs):
    chapter = kwargs.pop('chapter', 1)
    approved = kwargs.pop('approve', True)
    return make(e, 'STORY_RELATION', {'subject': {'kind': 'CHARACTER', 'id': 'bob'}, 'object': {'kind': 'LOCATION', 'id': 'city'}, 'relation': 'ABOUT', 'layer': 'WORLD_FACT', 'statement': text, **kwargs}, chapter=chapter, approve=approved)


def learn(e, row, character='alice', chapter=2, **kwargs):
    approve = kwargs.pop('approve', True)
    return make(e, 'KNOWLEDGE_EVENT', {'character_id': character, 'operation': 'LEARN', 'category': 'SECRET', 'relation_id': row['id'], **kwargs}, chapter=chapter, approve=approve)


def context(e, character='alice', chapter=4, **kwargs):
    return e.graph.character_context(e.nid, e.scope, character, e.order[chapter-1], **kwargs)


def test_review_reuses_world_authority_persistence_and_no_manuscript_writes(env):
    e = env; before = copy.deepcopy((e.rows, e.chapters))
    r = relation(e)
    k = learn(e, r)
    assert r['canon_state'] == 'CANON' and k['canon_state'] == 'REVIEWED'
    assert not e.world.records(e.nid, e.scope) and not e.world.canon(e.nid, e.scope)
    with pytest.raises(FileNotFoundError): e.world.record(e.nid, e.scope, r['id'])
    with pytest.raises(FileNotFoundError): e.world.review(e.nid, e.scope, 'writer', r['id'], 'archive', 2)
    restored = StoryGraphService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service)
    assert restored.character_context(e.nid, e.scope, 'alice', e.order[3])['secrets'][0]['text'] == r['data']['statement']
    assert (e.rows, e.chapters) == before


def test_unknown_secret_physically_absent_from_serialized_adapter_context(env):
    e = env; secret = 'VILLAIN_ONLY_CROWN_PASSWORD_紫钥匙'
    r = relation(e, secret)
    learn(e, r, character='bob', chapter=1)
    captured = []
    def adapter(request): captured.append(json.dumps(request, ensure_ascii=False))
    adapter({'context': context(e, 'alice'), 'instruction': 'Describe what this character knows.'})
    assert secret not in captured[-1]
    assert r['id'] not in captured[-1]
    query = e.graph.graph(e.nid, e.scope, e.order[3], 'alice')
    assert query['edges'] == [] and query['nodes'] == [] and query['visible_count'] == 0
    assert secret not in json.dumps(query)
    event = learn(e, r, chapter=3, approve=False)
    adapter({'context': context(e)})
    assert secret not in captured[-1]
    e.graph.review(e.nid, e.scope, 'reviewer', event['id'], 'approve', 1)
    assert secret not in json.dumps(context(e, chapter=2), ensure_ascii=False)
    adapter({'context': context(e, chapter=3)})
    assert secret in captured[-1]


def test_false_belief_is_distinct_and_does_not_reveal_true_statement_or_nodes(env):
    e = env; r = relation(e, 'The queen is the hidden enemy')
    learn(e, r, operation='MISUNDERSTAND', category='FALSE_BELIEF', value='The queen protects us')
    c = context(e)
    assert c['known_facts'] == [] and c['secrets'] == []
    assert c['false_beliefs'][0]['text'] == 'The queen protects us'
    assert 'hidden enemy' not in json.dumps(c)
    assert e.graph.graph(e.nid, e.scope, e.order[3], 'alice')['visible_count'] == 0
    learn(e, r, chapter=3, operation='CORRECT', category='KNOWN_FACT')
    c = context(e)
    assert c['false_beliefs'] == [] and c['known_facts'][0]['text'] == r['data']['statement']


def test_research_speculation_and_beliefs_never_promoted_to_facts(env):
    e = env
    for layer in ['RESEARCH', 'SPECULATION', 'CHARACTER_BELIEF']:
        r = relation(e, layer=layer, observer_id='alice' if layer == 'CHARACTER_BELIEF' else None)
        assert r['canon_state'] == 'REVIEWED'
        with pytest.raises(ValueError, match='cannot become'): learn(e, r)
        learn(e, r, operation='HEARSAY', category='BELIEF', value='An uncertain report')
    c = context(e)
    assert len(c['beliefs']) == 3 and not c['known_facts']
    state = e.store.read(e.nid, e.scope)
    assert not state['collections'].get('world_canon')


def test_world_time_unknown_flashback_and_validity_do_not_collapse(env):
    e = env
    unknown = relation(e, 'Unknown-time fact')
    past = relation(e, 'Flashback to earlier world time', chapter=3, world_time=10, valid_from=10, valid_to=20)
    q = lambda ch, t=None: e.graph.graph(e.nid, e.scope, e.order[ch-1], world_time=t)
    assert {edge['id'] for edge in q(2)['edges']} == {unknown['id']}
    assert {edge['id'] for edge in q(3, 15)['edges']} == {past['id']}
    assert not q(3, 20)['edges']
    assert next(edge for edge in q(3)['edges'] if edge['id'] == unknown['id'])['time_state'] == 'UNKNOWN'
    with pytest.raises(ValueError, match='valid_to'): relation(e, valid_from=20, valid_to=10)


def test_current_chapter_expiry_and_rollback_reconstruct_knowledge(env):
    e = env
    r = relation(e, until_chapter_id=e.order[3])
    learn(e, r, chapter=2)
    assert not context(e, chapter=1)['secrets']
    assert context(e, chapter=2)['secrets']
    learn(e, r, chapter=3, operation='FORGET')
    assert not context(e, chapter=3)['secrets']
    assert context(e, chapter=2)['secrets']
    assert not e.graph.graph(e.nid, e.scope, e.order[3])['edges']


def test_source_change_archive_and_entity_change_revoke_context(env):
    e = env; r = relation(e); event = learn(e, r)
    assert context(e)['secrets']
    e.chapters[e.order[0]]['content'] += ' changed'
    assert not context(e)['secrets']
    assert e.graph.record(e.nid, e.scope, event['id'])['stale']
    e.chapters[e.order[0]]['content'] = 'Synthetic chapter 1'
    e.rows['characters'][1]['name'] = 'Changed'
    assert not context(e)['secrets']
    e.rows['characters'][1]['name'] = 'Bob'
    e.graph.review(e.nid, e.scope, 'reviewer', r['id'], 'archive', r['version'])
    assert not context(e)['secrets']
    assert e.graph.impact(e.nid, e.scope, r['id'])['items'][0]['stale']


def test_knowledge_revocation_and_explicit_goals_motives_psychology(env):
    e = env; r = relation(e); event = learn(e, r)
    e.graph.review(e.nid, e.scope, 'reviewer', event['id'], 'archive', event['version'])
    assert not context(e)['secrets']
    psych = e.world.create_record(e.nid, e.scope, 'writer', {'kind': 'PSYCHOLOGY', 'title': 'Intent', 'chapter_id': e.order[0], 'data': {'character_id': 'alice', 'state': 'Anxious'}})
    psych = e.world.review(e.nid, e.scope, 'reviewer', psych['id'], 'approve', 1)
    for category in ['GOAL', 'FEAR', 'VALUE', 'EMOTION', 'INTENT']:
        make(e, 'KNOWLEDGE_EVENT', {'character_id': 'alice', 'category': category, 'operation': 'SET_STATE', 'value': category, 'psychology_id': psych['id']})
    c = context(e)
    assert c['emotion'][0]['text'] == 'EMOTION'
    assert c['intent'][0]['evidence_status'] == 'HYPOTHESIS'
    assert c['goals'][0]['text'] == 'GOAL'


def test_evidence_exact_quote_and_no_quote_leak_to_character(env):
    e = env
    e.chapters[e.order[0]]['content'] = 'Visible phrase. A secret unlearned phrase.'
    r = relation(e, 'Visible phrase', evidence=[{'chapter_id': e.order[0], 'quote': 'A secret unlearned phrase.', 'start': 16}])
    learn(e, r)
    assert 'unlearned phrase' not in json.dumps(context(e))
    with pytest.raises(ValueError, match='quote'): relation(e, evidence=[{'chapter_id': e.order[0], 'quote': 'forged', 'start': 0}])


def test_branch_sources_fail_closed_and_metadata_isolated(env):
    e = env; r = relation(e)
    branch = {**e.scope, 'mode': 'collaboration', 'workspace_id': 'workspace', 'storyline_id': 'story', 'branch_id': 'b'}
    with pytest.raises(ValueError, match='BRANCH_SOURCE'): e.graph.graph(e.nid, branch, e.order[0], 'alice')
    payload = {key: r[key] for key in ('kind', 'title', 'chapter_id', 'event_order', 'data')}
    with pytest.raises(ValueError, match='BRANCH_SOURCE'): e.graph.create_record(e.nid, branch, 'author', payload)
    for row in e.chapters.values(): row['branch_id'] = 'b'
    assert not e.graph.graph(e.nid, branch, e.order[0], 'alice')['edges']
    with pytest.raises(FileNotFoundError): e.graph.record(e.nid, branch, r['id'])
    copied = e.graph.create_record(e.nid, branch, 'author', payload)
    assert copied['scope'] == branch and copied['id'] != r['id']


def test_versioned_edit_history_archive_recompute_only_affected(env):
    e = env; r = relation(e, approve=False)
    raw = {key: r[key] for key in ('kind', 'title', 'chapter_id', 'event_order', 'data')}
    changed = e.graph.edit_record(e.nid, e.scope, 'author', r['id'], {**raw, 'title': 'Edited', 'expected_version': 1})
    with pytest.raises(CapabilityVersionConflict): e.graph.edit_record(e.nid, e.scope, 'author', r['id'], {**raw, 'expected_version': 1})
    approved = e.graph.review(e.nid, e.scope, 'reviewer', r['id'], 'approve', changed['version'])
    k = learn(e, approved); other = relation(e, 'Unaffected')
    result = e.graph.recompute(e.nid, e.scope, 'author', r['id'], approved['version'])
    assert set(result['recomputed_ids']) == {r['id'], k['id']}
    assert other['id'] not in result['recomputed_ids']
    assert len(e.graph.history(e.nid, e.scope, r['id'])) == 2


def test_concepts_reuse_real_ids_and_dependencies(env):
    e = env
    concept = make(e, 'STORY_CONCEPT', {'concept_type': 'SECRET', 'description': 'Secret concept'})
    r = relation(e, object={'kind': 'SECRET', 'id': concept['id']})
    learn(e, r, character='bob')
    assert not e.graph.graph(e.nid, e.scope, e.order[3], 'alice')['nodes']
    e.graph.review(e.nid, e.scope, 'reviewer', concept['id'], 'archive', 2)
    assert not context(e, 'bob')['secrets']
    with pytest.raises(ValueError): relation(e, subject={'kind': 'CHARACTER', 'id': 'made-up'})


def test_api_flags_permissions_author_view_and_legacy_bypass(env):
    e = env; r = relation(e); k = learn(e, r)
    controls = {'graph': True, 'mind': True, 'review': True}
    def flag(name):
        if name == 'temporal_story_graph_v2' and not controls['graph']: raise HTTPException(404)
        if name == 'character_mind_v2' and not controls['mind']: raise HTTPException(404)
    def auth(nid, token, branch, permission):
        if token not in {'author', 'viewer'} or (token == 'viewer' and permission != 'domain.read') or (permission == 'domain.review' and not controls['review']): raise HTTPException(403)
        return token, e.scope
    app = FastAPI(); app.include_router(create_story_graph_router(e.graph, auth, flag)); app.include_router(create_world_router(e.world, auth, flag))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/story-graph'; headers = {'X-Session-Token': 'author'}
    assert client.get(base + '/records', headers={'X-Session-Token': 'viewer'}).status_code == 403
    assert client.get(base + '/query', params={'chapter_id': e.order[3]}, headers={'X-Session-Token': 'viewer'}).status_code == 403
    assert client.get(base + '/query', params={'chapter_id': e.order[3], 'character_id': 'alice'}, headers={'X-Session-Token': 'viewer'}).status_code == 200
    controls['review'] = False
    assert client.post(base + f'/records/{r["id"]}/archive', json={'expected_version': 2}, headers=headers).status_code == 403
    controls['mind'] = False
    assert k['id'] not in json.dumps(client.get(base + '/records', headers=headers).json())
    recomputed = client.post(base + f'/records/{r["id"]}/recompute', json={'expected_version': r['version']}, headers=headers)
    assert recomputed.status_code == 200
    assert recomputed.json()['recomputed_ids'] == [r['id']] and recomputed.json()['count'] == 1
    assert client.post(base + '/character-context', json={'character_id': 'alice', 'chapter_id': e.order[3]}, headers=headers).status_code == 404
    old = f'/novels/{e.nid}/experimental/world'
    assert client.get(old + f'/records/{k["id"]}', headers=headers).status_code == 404
    assert not client.get(old + '/records', headers=headers).json()['items']
    controls['graph'] = False
    assert client.get(base + '/catalog', headers=headers).status_code == 404


def test_stale_or_revoked_later_change_never_resurrects_older_secret(env):
    e = env; r = relation(e); learn(e, r, chapter=2)
    forget = learn(e, r, chapter=3, operation='FORGET')
    assert not context(e)['secrets']
    e.chapters[e.order[2]]['content'] += ' changed'
    assert not context(e)['secrets'], 'A stale forget must not bring an old secret back'
    e.chapters[e.order[2]]['content'] = 'Synthetic chapter 3'
    e.graph.review(e.nid, e.scope, 'reviewer', forget['id'], 'archive', 2)
    assert not context(e)['secrets'], 'Revocation of latest knowledge leaves a fail-closed tombstone'
    learn(e, r, chapter=4, operation='CORRECT')
    assert context(e)['secrets']


def test_stale_order_fences_approval_and_later_source_drift(env):
    e = env; r = relation(e, approve=False)
    e.order[0], e.order[1] = e.order[1], e.order[0]
    with pytest.raises(StaleSourceError): e.graph.review(e.nid, e.scope, 'reviewer', r['id'], 'approve', 1)
    assert e.graph.record(e.nid, e.scope, r['id'])['status'] == 'REVIEW'


def test_scene_reference_uses_real_planning_and_source_versions(env):
    e = env
    root = e.service.create_graph(e.nid, e.scope, 'author', {'title': 'Root'})
    volume = e.service.create_node(e.nid, e.scope, 'author', {'graph_id': root['id'], 'parent_id': root['root_node_id'], 'level': 'VOLUME', 'title': 'Volume'})
    chapter = e.service.create_node(e.nid, e.scope, 'author', {'graph_id': root['id'], 'parent_id': volume['id'], 'level': 'CHAPTER', 'title': 'Chapter', 'links': {'chapter_ids': [e.order[0]]}})
    scene = e.service.create_node(e.nid, e.scope, 'author', {'graph_id': root['id'], 'parent_id': chapter['id'], 'level': 'SCENE', 'title': 'Scene', 'links': {'chapter_ids': [e.order[0]]}})
    r = relation(e, object={'kind': 'SCENE', 'id': scene['id']})
    assert not e.graph.record(e.nid, e.scope, r['id'])['stale']
    e.service.edit_node(e.nid, e.scope, 'author', scene['id'], {'title': 'Changed scene', 'expected_version': 1, 'links': {'chapter_ids': [e.order[0]]}})
    assert e.graph.record(e.nid, e.scope, r['id'])['stale']


def test_graph_mutation_invalidates_only_affected_index_entries_atomically(env):
    e = env; r = relation(e); k = learn(e, r); unrelated = relation(e, 'Unrelated world fact')
    before = e.store.read(e.nid, e.scope)['collections'][e.graph.INDEX]
    e.graph.review(e.nid, e.scope, 'reviewer', r['id'], 'archive', r['version'])
    index = e.store.read(e.nid, e.scope)['collections'][e.graph.INDEX]
    assert index[r['id']]['status'] == 'INVALID'
    assert index[k['id']]['status'] == 'INVALID' and index[k['id']]['stale']
    assert index[unrelated['id']] == before[unrelated['id']]


def test_goal_with_relation_evidence_does_not_overwrite_learned_fact(env):
    e = env; r = relation(e); learn(e, r)
    make(e, 'KNOWLEDGE_EVENT', {'character_id': 'alice', 'operation': 'GOAL_CHANGE', 'category': 'GOAL', 'relation_id': r['id'], 'value': 'Find the key'}, chapter=3)
    c = context(e)
    assert c['secrets'][0]['text'] == r['data']['statement']
    assert c['goals'][0]['text'] == 'Find the key'
