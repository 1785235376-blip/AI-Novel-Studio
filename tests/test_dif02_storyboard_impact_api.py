"""DIF02 real mounted File owners and trusted Host; no fabricated read ports."""
from copy import deepcopy
from uuid import uuid4

import pytest

from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, EXECUTION_FLAGS
from test_v2_storyboard_workspace_api import storyboard_client, get_storyboard

FLAGS = (*EXECUTION_FLAGS, 'change_impact_v2', 'temporal_story_graph_v2', 'world_character_engines_v2')


@pytest.fixture
def dif_client(storyboard_client, monkeypatch):
    e = storyboard_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(FLAGS))
    e.graphs = e.experimental.creative_graph_service
    for owner in (e.graphs, e.graphs.asset_inputs):
        monkeypatch.setattr(owner, 'store', e.studio.store)
        monkeypatch.setattr(owner, 'workspace', e.studio)
    e.graphs.configure_media(e.production)
    e.graph_base = e.studio_base + '/graphs'
    e.dif = e.experimental.change_impact_service
    e.dif_base = e.prefix + f'/novels/{e.nid}/experimental/change-impact'
    e.source = {'kind': 'CREATIVE_STORYBOARD', 'id': e.board_id}
    e.pin = get_storyboard(e)['document_snapshot']
    return e


def graph(e, count=1):
    return checked(e.client.post(e.graph_base, headers=e.headers, json={'request_id': uuid4().hex,
        'definition': {'schema_version': 4, 'title': 'Private author Storyboard dependency', 'nodes': [
            {'id': f'Board{i}', 'definition_id': 'storyboard_plan', 'parameters': {'document_snapshot': e.pin}}
            for i in range(count)], 'edges': []}}), 201)


def query(e, headers=None):
    return e.client.post(e.dif_base + '/query', headers=e.headers if headers is None else headers,
                         json={'source': e.source})


def decision(e):
    view = checked(query(e))
    return {'source': e.source, 'selected': [{'key': row['key'], 'expected_version': row['version'],
        'choice': 'REBUILD'} for row in view['items']]}


def preview(e, body):
    return checked(e.client.post(e.dif_base + '/decisions/preview', headers=e.headers, json=body))


def save(e, body, receipt, request_id='real-file-intent'):
    return e.client.post(e.dif_base + '/decisions', headers=e.headers,
        json={**body, 'preview_digest': receipt['preview_digest'], 'request_id': request_id})


def test_no_formal_asset_real_owner_query_preview_save_replay_and_reopen(dif_client, monkeypatch):
    e = dif_client; row = graph(e, 2)
    assert checked(e.client.get(e.studio_base + '/assets', headers=e.headers)) == {'items': []}
    before = deepcopy(e.store.read(e.nid, e.scope))
    response = query(e); view = checked(response)
    assert response.headers['cache-control'] == 'no-store'
    assert view['target_limit'] == 20 and not view['truncated'] and len(view['items']) == 2
    assert all(item['kind'] == 'CREATIVE_GRAPH_NODE' and not item['refresh_candidate'] for item in view['items'])
    body = decision(e); receipt = preview(e, body)
    assert e.store.read(e.nid, e.scope) == before
    # Full Graph projection reads must finish before entering the DIF transaction.
    for name in ('list', 'get'):
        original = getattr(e.graphs, name)
        def outside_transaction(*args, _original=original, **kwargs):
            assert e.store.key(e.nid, e.scope) not in getattr(e.store._local, 'active', {})
            return _original(*args, **kwargs)
        monkeypatch.setattr(e.graphs, name, outside_transaction)
    saved = checked(save(e, body, receipt), 201)
    assert saved['decision_only'] and not saved['automatic_execution'] and saved['current']
    params = {'source_kind': e.source['kind'], 'source_id': e.board_id}
    assert checked(e.client.get(e.dif_base + '/decisions', headers=e.headers, params=params)) == {'items': [saved]}
    assert checked(save(e, body, receipt), 201) == saved
    after = e.store.read(e.nid, e.scope)
    assert set(after['collections']) - set(before['collections']) == {e.dif.DECISIONS}
    assert {k: v for k, v in after['collections'].items() if k != e.dif.DECISIONS} == before['collections']
    assert checked(e.client.get(e.graph_base + '/' + row['id'], headers=e.headers)) == row
    assert checked(e.client.get(e.dif_base + '/refreshes', headers=e.headers)) == {'items': []}
    assert e.calls == [] and e.discovery.center.lifecycle.start.call_count == 0


@pytest.mark.parametrize('count', [20, 21])
def test_complete_direct_target_bound_never_returns_partial_inventory(dif_client, count):
    e = dif_client; graph(e, count)
    before = deepcopy(e.store.read(e.nid, e.scope))
    response = query(e)
    if count == 20:
        assert len(checked(response)['items']) == 20
    else:
        assert response.status_code == 422
        assert response.json()['detail']['code'] == 'CHANGE_IMPACT_STORYBOARD_TARGET_LIMIT'
        assert 'items' not in response.json() and 'Private author' not in response.text
    assert e.store.read(e.nid, e.scope) == before and e.calls == []


@pytest.mark.parametrize('change', ['revoke', 'aba', 'graph-version', 'source-version'])
def test_mid_read_authority_and_pin_changes_discard_whole_projection(dif_client, monkeypatch, change):
    e = dif_client; row = graph(e)
    original = e.graphs.get; changed = []
    def altered(*args, **kwargs):
        result = original(*args, **kwargs)
        if not changed:
            changed.append(True)
            if change in {'revoke', 'aba'}:
                e.sessions.revoke(e.host)
                if change == 'aba': e.sessions.register(e.host, e.session)
            else:
                # A real owner revision after the first read, not a fabricated
                # read-port, malformed raw record, or permission callback.
                if change == 'graph-version':
                    checked(e.client.put(e.graph_base + '/' + row['id'], headers=e.headers,
                        json={'expected_version': row['version'],
                              'definition': {**row['definition'], 'title': 'Concurrent original revision'}}))
                else:
                    from test_v2_storyboard_workspace import board_value
                    checked(e.client.put(e.board_path, headers=e.headers,
                        json={'expected_version': e.pin['version'], **board_value(title='Concurrent original revision')}))
        return result
    monkeypatch.setattr(e.graphs, 'get', altered)
    response = query(e)
    assert response.status_code in {401, 403, 409}, response.text
    assert 'items' not in response.json() and 'Private author' not in response.text
    assert e.store.read(e.nid, e.scope)['collections'].get(e.dif.DECISIONS, {}) == {}
    assert e.calls == []


def test_original_trusted_session_revoked_at_decision_write_rolls_back(dif_client, monkeypatch):
    import app.experimental.change_impact as module
    e = dif_client; graph(e); body = decision(e); receipt = preview(e, body)
    original = module.new_row
    def revoked(*args, **kwargs):
        row = original(*args, **kwargs)
        e.sessions.revoke(e.host)
        return row
    monkeypatch.setattr(module, 'new_row', revoked)
    before = deepcopy(e.store.read(e.nid, e.scope))
    response = save(e, body, receipt)
    assert response.status_code in {401, 403} and e.store.read(e.nid, e.scope) == before
    assert 'Private author' not in response.text and e.calls == []


def test_stale_preview_is_rejected_and_authorized_old_intent_reopens_as_stale(dif_client):
    e = dif_client; row = graph(e); body = decision(e); receipt = preview(e, body)
    checked(save(e, body, receipt), 201)
    changed = {**row['definition'], 'title': 'Author revised graph'}
    checked(e.client.put(e.graph_base + '/' + row['id'], headers=e.headers,
        json={'expected_version': row['version'], 'definition': changed}))
    assert save(e, body, receipt, 'stale-preview').status_code == 409
    reopened = checked(e.client.get(e.dif_base + '/decisions', headers=e.headers,
        params={'source_kind': e.source['kind'], 'source_id': e.board_id}))
    assert len(reopened['items']) == 1 and not reopened['items'][0]['current'] and e.calls == []


def test_original_read_permission_is_required_in_addition_to_dif_write(dif_client, monkeypatch):
    from app.authorization import AuthorizationScope, PermissionAssignment, ScopeKind, ModalityDomain
    e = dif_client; graph(e)
    scoped(e, monkeypatch)
    e.authorization.revoke_role(e.role, e.lead)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_permission(PermissionAssignment(uuid4().hex, e.lead, 'domain.write',
        ModalityDomain.NOVEL, scope, e.lead))
    response = query(e)
    assert response.status_code == 403 and 'LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE' not in response.text
    assert 'Private author' not in response.text and e.calls == []


@pytest.mark.parametrize('change', ['missing', 'forged', 'origin'])
def test_original_host_boundary_cannot_be_replaced_by_dif_write_authority(dif_client, change):
    e = dif_client; graph(e)
    headers = {} if change == 'missing' else ({'X-Session-Token': 'unregistered'} if change == 'forged' else
                                           {**e.headers, 'Origin': 'https://untrusted.invalid'})
    before = deepcopy(e.store.read(e.nid, e.scope))
    response = query(e, headers)
    assert response.status_code in {401, 403} and 'Private author' not in response.text
    assert e.store.read(e.nid, e.scope) == before and e.calls == []


def test_missing_or_replaced_original_incarnation_never_provisions_or_adopts(dif_client):
    import json
    e = dif_client; graph(e)
    marker = e.root / 'novels' / e.nid / 'creative_project_v2.json'
    assert marker.resolve().is_relative_to(e.root.resolve())
    marker.unlink()  # Exactly the disposable fixture marker, no recursive deletion.
    before = deepcopy(e.store.read(e.nid, e.scope))
    response = query(e)
    assert response.status_code in {404, 409} and not marker.exists()
    assert e.store.read(e.nid, e.scope) == before
    marker.write_text(json.dumps({'schema_version': 1, 'project_incarnation': str(uuid4())}))
    response = query(e)
    assert response.status_code in {404, 409} and 'Private author' not in response.text
    assert e.store.read(e.nid, e.scope) == before and e.calls == []


@pytest.mark.parametrize('owner', ['storyboard', 'graph'])
def test_corrupt_original_owner_validation_never_echoes_private_input(dif_client, owner):
    e = dif_client; row = graph(e)
    with e.store.transaction(e.nid, e.scope) as state:
        if owner == 'storyboard':
            state['collections'][e.creative.COLLECTION][e.board_id]['shots'][0]['duration_seconds'] = 'PRIVATE_BAD_INPUT'
        else:
            state['collections'][e.graphs.GRAPHS][row['id']]['definition']['nodes'][0]['parameters']['document_snapshot']['version'] = 'PRIVATE_BAD_INPUT'
    before = deepcopy(e.store.read(e.nid, e.scope))
    response = query(e)
    assert response.status_code == 422 and 'PRIVATE_BAD_INPUT' not in response.text
    assert 'Private author' not in response.text and e.store.read(e.nid, e.scope) == before and e.calls == []


@pytest.mark.parametrize('flag', ['narrative_production_v2', 'change_impact_v2', 'temporal_story_graph_v2', 'asset_lineage_v2'])
def test_each_original_feature_gate_remains_closed(dif_client, monkeypatch, flag):
    e = dif_client; graph(e)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(name for name in FLAGS if name != flag))
    response = query(e)
    assert response.status_code == 404 and response.json()['detail']['code'] == 'EXPERIMENTAL_FEATURE_DISABLED'
    assert 'Private author' not in response.text and e.calls == []
