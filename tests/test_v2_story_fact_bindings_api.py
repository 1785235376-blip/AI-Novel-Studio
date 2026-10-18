"""Mounted fact-use reads/confirmation retain original Host and scope authority."""
import json
import pytest

from test_r3_mounted_contracts import mounted, prefix, checked
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client
from test_v2_storyboard_workspace_api import storyboard_client, get_storyboard

FLAGS = 'narrative_production_v2,asset_lineage_v2,world_character_engines_v2,temporal_story_graph_v2,change_impact_v2'


@pytest.fixture
def fact_client(storyboard_client, monkeypatch):
    e = storyboard_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', FLAGS)
    graph = e.experimental.story_graph_service
    monkeypatch.setattr(e.creative.story_facts, 'graph', graph)
    monkeypatch.setattr(graph, 'creation_owner', e.creative.store)
    source = checked(e.client.post(e.prefix + f'/novels/{e.nid}/experimental/story-graph/records', headers=e.headers, json={
        'kind': 'STORY_RELATION', 'title': 'Approved scar', 'chapter_id': e.chapter['id'], 'data': {
            'subject': {'kind': 'CHARACTER', 'id': 'alice'}, 'object': {'kind': 'LOCATION', 'id': 'city'},
            'relation': 'ABOUT', 'layer': 'WORLD_FACT', 'statement': 'Alice has a scar.'}}), 201)
    e.fact = checked(e.client.post(e.prefix + f'/novels/{e.nid}/experimental/story-graph/records/{source["id"]}/approve',
        headers=e.headers, json={'expected_version': source['version']}))
    return e


def request(e):
    board = get_storyboard(e)
    fact = checked(e.client.get(e.creative_base + '/story-facts', headers=e.headers))['items'][0]
    shot = board['shots'][0]
    return {'expected_version': board['document_snapshot']['version'], 'document_digest': board['document_snapshot']['digest'],
            'shot_version': shot['shot_version'], 'shot_digest': shot['shot_digest'],
            'fact': {k: fact[k] for k in ('id', 'version', 'digest')}, 'purpose': 'APPEARANCE_STATE',
            'rationale': 'The visible scar applies to this shot.', 'confirmed': True}


def test_mounted_create_reopen_fact_impact_is_private_read_only(fact_client):
    e = fact_client
    before = checked(e.client.get(e.board_path, headers=e.headers))
    saved = checked(e.client.post(e.board_path + '/shots/shot-1/fact-uses', headers=e.headers, json=request(e)), 201)
    for path in (e.board_path + '/fact-uses', e.creative_base + f'/story-facts/{e.fact["id"]}/impact'):
        response = e.client.get(path, headers=e.headers)
        result = checked(response)
        assert response.headers['cache-control'] == 'no-store'
        assert result['items'][0]['id'] == saved['id']
        assert result['items'][0]['state'] == 'CURRENT'
        assert result['model_called'] is result['automatic_regeneration'] is False
    assert checked(e.client.get(e.board_path, headers=e.headers)) == before
    assert e.calls == []


@pytest.mark.parametrize('flag', ['temporal_story_graph_v2', 'change_impact_v2', 'asset_lineage_v2', 'narrative_production_v2'])
def test_each_required_flag_denies_without_private_fact_ids(fact_client, monkeypatch, flag):
    e = fact_client
    body = request(e)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(f for f in FLAGS.split(',') if f != flag))
    for method, path, payload in [('GET', e.creative_base + '/story-facts', None),
        ('GET', e.board_path + '/fact-uses', None),
        ('POST', e.board_path + '/shots/shot-1/fact-uses', body)]:
        response = e.client.request(method, path, headers=e.headers, json=payload)
        assert response.status_code == 404, response.text
        assert e.fact['id'] not in response.text and 'Approved scar' not in response.text


def test_missing_host_and_revoked_session_cannot_read_or_confirm(fact_client):
    e = fact_client
    payload = request(e)
    for method, path, body in [('GET', e.creative_base + '/story-facts', None),
        ('GET', e.board_path + '/fact-uses', None),
        ('POST', e.board_path + '/shots/shot-1/fact-uses', payload)]:
        response = e.client.request(method, path, json=body)
        assert response.status_code in (401, 403), response.text
        assert e.fact['id'] not in response.text
    # Explicitly invalid session token is not an alternate anonymous authority.
    response = e.client.get(e.creative_base + '/story-facts', headers={'X-Session-Token': 'unregistered'})
    assert response.status_code in (401, 403)
    assert e.calls == []


def test_mounted_foreign_entity_hides_saved_fact_and_rationale(fact_client):
    e = fact_client
    saved = checked(e.client.post(e.board_path + '/shots/shot-1/fact-uses', headers=e.headers, json=request(e)), 201)
    e.novels.upsert_character(e.nid, 'alice', {'name': 'Alice', 'branch_id': 'foreign'})
    response = e.client.get(e.board_path + '/fact-uses', headers=e.headers)
    result = checked(response)
    assert result['items'] == []
    for secret in (saved['id'], e.fact['id'], 'Approved scar', 'The visible scar applies'):
        assert secret not in response.text
    assert e.client.get(e.creative_base + f'/story-facts/{e.fact["id"]}/impact', headers=e.headers).status_code == 404


def test_write_without_original_review_permission_cannot_confirm(fact_client, monkeypatch):
    from app.authorization import AuthorizationScope, PermissionAssignment, ScopeKind, ModalityDomain
    from test_r3_mounted_contracts import scoped
    e = fact_client
    payload = request(e)
    scoped(e, monkeypatch)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_permission(PermissionAssignment('fact-write-' + e.viewer, e.viewer, 'domain.write',
        ModalityDomain.NOVEL, scope, e.lead))
    response = e.client.post(e.board_path + '/shots/shot-1/fact-uses', headers=e.viewer_headers, json=payload)
    assert response.status_code == 403, response.text
    assert e.fact['id'] not in response.text
    assert 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE' not in response.text
    # Review authorization is checked before Host admission. Even a real lead
    # cannot bypass the original unsupported collaboration Host boundary.
    lead = e.client.get(e.creative_base + '/story-facts', headers=e.headers)
    assert lead.status_code == 403 and 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE' in lead.text


def test_corrupt_owner_validation_error_never_echoes_private_input(fact_client):
    e = fact_client
    with e.creative.store.transaction(e.nid, e.scope) as state:
        state['collections'][e.creative.COLLECTION][e.board_id]['shots'][0]['duration_seconds'] = 'PRIVATE_BAD_DURATION'
    response = e.client.get(e.board_path + '/fact-uses', headers=e.headers)
    assert response.status_code == 422
    assert response.json()['detail']['code'] == 'CREATIVE_STORY_FACT_EVIDENCE_INVALID'
    assert 'PRIVATE_BAD_DURATION' not in response.text
