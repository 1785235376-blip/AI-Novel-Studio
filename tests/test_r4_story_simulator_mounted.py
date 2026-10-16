"""A01 mounted production composition, both API aliases, File/actual PostgreSQL."""
import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped


def start(e):
    cid = e.chapter['id']; version = e.chapters.get(cid)['version']
    graph = checked(e.client.post(e.base + '/planning/graphs', json={'title': 'Existing manual plan', 'links': {'chapter_ids': [cid]}}), 201)
    context = checked(e.client.post(e.base + '/story-simulator/context', json={'chapter_id': cid, 'expected_version': version, 'character_id': 'alice'}))
    body = {'chapter_ids': [cid], 'expected_versions': {cid: version}, 'chapter_id': cid, 'character_id': 'alice', 'node_id': graph['root_node_id'], 'expected_node_version': 1,
            'context_digest': context['context_digest'], 'character_goal': 'Enter the city', 'motivation_hypothesis': 'A deliberate author hypothesis.',
            'routes': [{'id': 'a', 'title': 'Locked gate route', 'events': [{'id': 'open', 'title': 'Try the locked gate', 'at': 1, 'requires': ['key'], 'question': 'Where can she find the key?'}]},
                       {'id': 'b', 'title': 'Wait for a guide', 'events': [{'id': 'wait', 'title': 'Wait outside', 'at': 1, 'adds': ['guide-arrived']}]}]}
    return checked(e.client.post(e.base + '/story-simulator/runs', json=body), 201), graph, body


def test_mounted_j05_rule_violation_comparison_to_pending_review_without_text_change(mounted):
    e = mounted; before = e.chapters.get(e.chapter['id']); row, graph, body = start(e)
    assert row['status'] == 'READY' and row['expansions'] == 0
    base = e.base + '/story-simulator/runs/' + row['id']
    row = checked(e.client.post(base + '/step', json={'expected_version': row['version']}))
    assert row['status'] == 'COMPLETED' and row['routes'][0]['violations'][0]['code'] == 'UNMET_PREREQUISITE'
    assert row['routes'][1]['steps'][0]['applied']
    saved = checked(e.client.post(base + '/save', json={'expected_version': row['version'], 'route_id': 'b'}), 201)
    p = checked(e.client.get(e.base + '/planning/proposals/' + saved['proposal_id']))
    assert p['status'] == 'REVIEW' and p['simulation_provenance']['run_id'] == row['id']
    assert checked(e.client.get(e.base + '/planning/graphs/' + graph['id']))['nodes'][0]['status'] == 'DRAFT'
    assert e.chapters.get(e.chapter['id']) == before and e.novels.data_set(e.nid, 'canon') == []
    e.chapters.save(before['id'], {'content': 'New source version', 'version': before['version']})
    stale = checked(e.client.get(base)); assert stale['stale'] and stale['routes'] == []
    assert 'Try the locked gate' not in e.client.get(base).text
    assert e.client.post(base + '/save', json={'expected_version': 3, 'route_id': 'a'}).status_code == 409
    assert checked(e.client.get(e.base + '/planning/proposals'))['items'] == []
    assert e.client.post(e.base + '/planning/proposals/' + p['id'] + '/approve', json={'expected_version': 1}).status_code == 409


def test_mounted_default_off_dependency_v1_and_no_unconfigured_model(mounted, monkeypatch):
    e = mounted; row, _, body = start(e)
    invalid = e.client.post(e.base + '/story-simulator/runs', json={**body, 'model_id': 'pretend-model'})
    assert invalid.status_code == 422 and 'MODEL_NOT_CONFIGURED' in invalid.text
    for flags, v1 in [('', 'false'), ('*', 'false'), ('story_simulator_v2', 'false'), ('advanced_planning_v2,story_simulator_v2,temporal_story_graph_v2,world_character_engines_v2,character_mind_v2', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        for path in ['/catalog', '/runs', '/runs/' + row['id']]:
            assert e.client.get(e.base + '/story-simulator' + path).status_code == 404
        assert e.client.post(e.base + '/story-simulator/runs', json=body).status_code == 404
        assert e.client.post(e.base + '/story-simulator/runs/' + row['id'] + '/step', json={'expected_version': 1}).status_code == 404


def test_mounted_author_only_and_last_read_authority(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    for path in ('/catalog', '/runs'):
        assert e.client.get(e.base + '/story-simulator' + path, headers=e.viewer_headers).status_code == 403
    service = e.experimental.story_simulator_service; original = service.catalog
    def revoked(*args):
        result = original(*args); result['private_test_marker'] = 'PRIVATE_SIMULATION_SCOPE'; e.sessions.revoke(e.lead); return result
    monkeypatch.setattr(service, 'catalog', revoked)
    response = e.client.get(e.base + '/story-simulator/catalog', headers=e.headers)
    assert response.status_code in {401, 403} and 'PRIVATE_SIMULATION_SCOPE' not in response.text
