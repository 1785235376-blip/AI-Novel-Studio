"""Actual mounted display API, original authority and File/PostgreSQL owners."""
import copy
from uuid import uuid4
import pytest
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client, upload_body
from test_v2_creative_graph_api import graph_client


@pytest.fixture
def canvas(graph_client, monkeypatch):
    from app.creative.graph_asset_inputs import GraphAssetInputs
    from app.creative.canvas_views import CreativeCanvasViews
    e = graph_client
    monkeypatch.setattr(e.graphs, 'asset_inputs', GraphAssetInputs(e.graphs))
    monkeypatch.setattr(e.graphs, 'canvas_views', CreativeCanvasViews(e.graphs))
    e.canvas_base = e.studio_base + '/canvas-views'
    return e


def body(title='Display view'):
    return {'request_id': 'view-' + uuid4().hex, 'definition': {'title': title, 'cards': []}}


def test_display_save_reopen_and_asset_tombstone(canvas):
    e = canvas
    asset = checked(e.client.post(e.studio_base + '/assets', json=upload_body()), 201)
    payload = body()
    payload['definition']['cards'] = [{'id': 'Card', 'position': {'x': 10, 'y': 20},
        'asset': {'asset_id': asset['id'], 'version': asset['version'], 'digest': asset['sha256'], 'kind': asset['kind']}}]
    row = checked(e.client.post(e.canvas_base, json=payload), 201)
    assert checked(e.client.post(e.canvas_base, json=payload), 201) == row
    assert row['execution_authority'] is False and row['binary_content_verified'] is False
    path = e.canvas_base + '/' + row['id']
    definition = copy.deepcopy(row['definition'])
    definition['cards'][0]['position']['x'] = 48
    saved = checked(e.client.put(path, json={'expected_version': 1, 'definition': definition}))
    assert saved['version'] == 2
    response = e.client.get(path)
    assert checked(response) == saved
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert checked(e.client.get(e.canvas_base))['items'][0]['card_count'] == 1
    conflict = e.client.put(path, json={'expected_version': 1, 'definition': definition})
    assert conflict.status_code == 409
    assert set(conflict.json()['detail']['current']) <= {'version', 'status'}
    checked(e.client.delete(e.studio_base + f"/assets/{asset['id']}?expected_version={asset['version']}"))
    unavailable = checked(e.client.get(path))
    assert unavailable['reference_states'] == [{'card_id': 'Card', 'state': 'UNAVAILABLE'}]
    assert 'asset' not in unavailable['definition']['cards'][0]
    assert checked(e.client.get(e.graph_base)) == {'items': []}


def test_display_authority_and_closed_actions(canvas, monkeypatch):
    e = scoped(canvas, monkeypatch)
    assert e.client.get(e.canvas_base).status_code == 401
    assert e.client.get(e.canvas_base, headers={'X-Session-Token': e.lead}).status_code == 400
    row = checked(e.client.post(e.canvas_base, headers=e.headers, json=body()), 201)
    assert checked(e.client.get(e.canvas_base, headers=e.viewer_headers))['items'] == []
    assert e.client.get(e.canvas_base + '/' + row['id'], headers=e.viewer_headers).status_code == 404
    assert e.client.post(e.canvas_base, headers=e.viewer_headers, json=body()).status_code == 403
    for method, suffix in [('POST', '/one/execute'), ('POST', '/one/runs'), ('DELETE', '/one'), ('PATCH', '/one')]:
        response = e.client.request(method, e.canvas_base + suffix, headers=e.headers)
        assert response.status_code == 501
        assert response.json()['detail']['code'] == 'COLLABORATION_ROUTE_NOT_ENABLED'
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.get(e.canvas_base, headers=e.headers).status_code == 403


def test_display_validation_bound_and_default_off(canvas, monkeypatch):
    e = canvas
    secret = 'private-invalid-input'
    malformed = body(secret)
    malformed['definition']['execution'] = secret
    response = e.client.post(e.canvas_base, json=malformed)
    assert response.status_code == 422 and secret not in response.text
    assert response.headers['cache-control'] == 'no-store'
    response = e.client.post(e.canvas_base, content=b'x' * 768_001, headers={'content-type': 'application/json', 'content-length': '1'})
    assert response.status_code == 413
    assert response.headers['cache-control'] == 'no-store'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    for method, suffix, payload in [('GET', '', None), ('POST', '', body()), ('GET', '/missing', None),
            ('PUT', '/missing', {'expected_version': 1, 'definition': {'title': 'Off'}})]:
        response = e.client.request(method, e.canvas_base + suffix, json=payload)
        assert response.status_code == 404
        assert response.json()['detail']['code'] == 'EXPERIMENTAL_FEATURE_DISABLED'


@pytest.mark.parametrize('private_error', [False, True])
def test_display_late_revocation_masks_result_or_error(canvas, monkeypatch, private_error):
    e = scoped(canvas, monkeypatch)
    row = checked(e.client.post(e.canvas_base, headers=e.headers, json=body('private-canvas-title')), 201)
    original = e.graphs.canvas_views.get
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        e.sessions.revoke(e.lead)
        if private_error:
            raise ValueError('private-canvas-title')
        return result
    monkeypatch.setattr(e.graphs.canvas_views, 'get', revoked)
    response = e.client.get(e.canvas_base + '/' + row['id'], headers=e.headers)
    assert response.status_code == 401
    assert row['id'] not in response.text and 'private-canvas-title' not in response.text
