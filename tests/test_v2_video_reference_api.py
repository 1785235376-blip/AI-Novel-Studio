"""Mounted original-authority source-frame preparation, no model routes."""
import copy
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from test_v2_independent_workspace import rig
from test_v2_video_reference_owner import video_bytes, source_asset, preview_body, prepared, files


def client_for(e, *, permissions=None, allowed=None):
    from app.creative.workspace_api import create_independent_workspace_router
    from app.experimental.flags import require_flag
    def authorize(nid, token, branch, permission):
        if permissions is not None: permissions.append(permission)
        if allowed is not None and not allowed[0]: raise HTTPException(403, {'code': 'DENIED'})
        if nid != e.nid or branch is not None or token not in {'writer', 'reader'}:
            raise HTTPException(403, {'code': 'DENIED'})
        if token == 'reader' and permission != 'domain.read': raise HTTPException(403, {'code': 'DENIED'})
        return e.actor, e.scope
    app = FastAPI()
    app.include_router(create_independent_workspace_router(e.service, authorize, require_flag,
        create_project=lambda *a: None, workspace_writer=lambda token: e.actor), prefix='/api')
    return TestClient(app)


def paths(e, source):
    root = f'/api/projects/{e.nid}/studio/assets/{source["id"]}/video-reference'
    return root + '/preview', root + '/save'


def test_reader_observes_writer_explicitly_saves_original_image(rig, video_bytes):
    from app.creative.workspace_api import is_independent_studio_route
    e = rig; source, review, body = prepared(e, video_bytes); preview, save = paths(e, source); permissions = []
    assert is_independent_studio_route('POST', preview) and is_independent_studio_route('POST', save)
    for method, path in [('GET', preview), ('PUT', save), ('POST', save + '-other')]:
        assert not is_independent_studio_route(method, path)
    with client_for(e, permissions=permissions) as client:
        response = client.post(preview, json=preview_body(source), headers={'X-Session-Token': 'reader'})
        assert response.status_code == 200, response.text
        assert response.json() == review
        assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
        denied = client.post(save, json=body, headers={'X-Session-Token': 'reader'})
        assert denied.status_code == 403 and len(e.service.list_assets(e.nid, e.scope)['items']) == 1
        success = client.post(save, json=body, headers={'X-Session-Token': 'writer'})
        assert success.status_code == 201, success.text
        assert success.json()['asset']['video_reference']['model_called'] is False
        assert success.json()['receipt']['asset_created'] is True
    assert set(permissions) == {'domain.read', 'domain.write'}


@pytest.mark.parametrize('mutation', ['extra', 'coerced', 'bool', 'zero', 'oversize', 'leak'])
def test_strict_request_bounds_and_sanitized_validation(rig, video_bytes, mutation):
    e = rig; source = source_asset(e, video_bytes); before = files(e); preview, _ = paths(e, source)
    body = preview_body(source)
    if mutation == 'extra': body['provider_id'] = 'must-not-be-a-provider'
    elif mutation == 'coerced': body['in_ms'] = '300'
    elif mutation == 'bool': body['source_version'] = True
    elif mutation == 'zero': body['out_ms'] = body['in_ms']
    elif mutation == 'oversize': body['secret'] = 'private-path-' * 500
    else: body['source_sha256'] = '/private/user/path-secret'
    with client_for(e) as client:
        response = client.post(preview, json=body, headers={'X-Session-Token': 'reader'})
    assert response.status_code == (413 if mutation == 'oversize' else 422)
    assert response.json() == {'detail': {'code': 'VIDEO_REFERENCE_REQUEST_LIMIT' if mutation == 'oversize' else 'VIDEO_REFERENCE_REQUEST_INVALID'}}
    assert response.headers['cache-control'] == 'no-store' and response.headers['x-content-type-options'] == 'nosniff'
    assert files(e) == before


@pytest.mark.parametrize('case', ['session', 'branch', 'source', 'stale', 'flag'])
def test_permission_source_scope_and_staleness_fail_closed(rig, video_bytes, monkeypatch, case):
    e = rig; source = source_asset(e, video_bytes); before = files(e); preview, _ = paths(e, source)
    body = preview_body(source); headers = {'X-Session-Token': 'reader'}
    if case == 'session': headers = {}
    elif case == 'branch': headers['X-Branch-Id'] = 'other-branch'
    elif case == 'source': preview = preview.replace(source['id'], 'missing-source')
    elif case == 'stale': body['source_version'] += 1
    else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    with client_for(e) as client:
        response = client.post(preview, json=body, headers=headers)
    assert response.status_code in {403, 404, 409}
    assert files(e) == before and '_video_reference_origin' not in response.text


def test_native_authority_revocation_prevents_preview_and_save(rig, video_bytes, monkeypatch):
    import app.services.studio_video_reference_frames as native
    e = rig; source = source_asset(e, video_bytes); before = files(e); preview, _ = paths(e, source)
    allowed = [True]; original = native.prepare_frames
    def revoke(*a, **kw):
        allowed[0] = False
        return original(*a, **kw)
    monkeypatch.setattr(native, 'prepare_frames', revoke)
    with client_for(e, allowed=allowed) as client:
        response = client.post(preview, json=preview_body(source), headers={'X-Session-Token': 'writer'})
    assert response.status_code == 403 and files(e) == before


def test_preview_changed_and_source_changed_never_echo_sensitive_input(rig, video_bytes):
    e = rig; source, review, body = prepared(e, video_bytes); before = files(e); _, save = paths(e, source)
    body['reviewed_preview_digest'] = '0' * 64
    with client_for(e) as client:
        response = client.post(save, json=body, headers={'X-Session-Token': 'writer'})
    assert response.status_code == 409 and response.json() == {'detail': {'code': 'VIDEO_REFERENCE_SOURCE_CHANGED'}}
    assert files(e) == before
