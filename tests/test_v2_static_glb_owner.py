"""Actual File/Asset owner persistence and isolation for static GLB metadata.

No viewport, GPU, model calls, external resources, or full glTF acceptance.
"""
import base64
from pathlib import Path

import pytest

from test_v2_independent_workspace import rig, reopened
from test_v2_static_glb_inspection import glb, triangle_document

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('rig', ['file'], indirect=True)]


def body(data=None, key='static-glb'):
    return {'contract': 'studio-static-glb-import/1', 'filename': 'triangle.glb',
            'content_base64': base64.b64encode(glb() if data is None else data).decode(), 'idempotency_key': key}


def upload(rig, value=None):
    return rig.service.import_model_reference(rig.nid, rig.scope, rig.actor, body() if value is None else value)


def test_real_original_asset_import_exact_reopen_and_readonly_geometry(rig):
    value = upload(rig)
    assert value['kind'] == 'model' and value['media_type'] == 'model/gltf-binary' and value['version'] == 1
    assert rig.chapters.list(rig.nid) == []
    service = reopened(rig)
    before = {str(path): path.read_bytes() for path in rig.root.rglob('*') if path.is_file()}
    inspected = service.inspect_model_reference(rig.nid, rig.scope, value['id'])
    assert inspected['asset_snapshot']['version'] == 1
    assert inspected['asset_snapshot']['digest'] == value['sha256']
    assert inspected['inspection']['bounds']['max'] == [1, 2, 0]
    assert service.download(rig.nid, rig.scope, value['id'])[1] == glb()
    after = {str(path): path.read_bytes() for path in rig.root.rglob('*') if path.is_file()}
    assert before == after


def test_same_import_is_idempotent_and_invalid_content_leaves_no_new_asset(rig):
    one = upload(rig)
    assert upload(rig)['id'] == one['id']
    with pytest.raises(ValueError, match='MODEL_REFERENCE_GLB_'):
        upload(rig, body(b'opaque bytes', 'invalid'))
    assert [row['id'] for row in rig.service.list_assets(rig.nid, rig.scope)['items']] == [one['id']]


def test_refuses_cross_project_deleted_asset_and_recreated_project(rig):
    value = upload(rig)
    other = rig.create_project('Other')
    with pytest.raises((FileNotFoundError, ValueError)):
        rig.service.inspect_model_reference(other, {'mode': 'local', 'novel_id': other}, value['id'])
    rig.service.lifecycle(rig.nid, rig.scope, value['id'], value['version'])
    with pytest.raises((FileNotFoundError, ValueError)):
        rig.service.inspect_model_reference(rig.nid, rig.scope, value['id'])
    rig.novels.delete(rig.nid)
    rig.create_project('Recreated', rig.nid)
    with pytest.raises((FileNotFoundError, ValueError)):
        reopened(rig).inspect_model_reference(rig.nid, rig.scope, value['id'])
    fresh = reopened(rig).import_model_reference(rig.nid, rig.scope, rig.actor, body(key='new-owner'))
    assert fresh['id'] != value['id']


def test_revocation_after_decode_prevents_inspection_return(rig, monkeypatch):
    import app.creative.model_reference_glb as parser
    value = upload(rig)
    original = parser.inspect_static_glb
    allowed = True
    def changed(data):
        nonlocal allowed
        result = original(data); allowed = False; return result
    monkeypatch.setattr(parser, 'inspect_static_glb', changed)
    def guard():
        if not allowed: raise PermissionError('revoked')
    with pytest.raises(PermissionError, match='revoked'):
        rig.service.inspect_model_reference(rig.nid, rig.scope, value['id'], guard)


def test_closed_new_route_admission_does_not_expand_execution_or_old_import_kind(rig):
    from app.creative.workspace_api import is_independent_studio_route
    from app.creative.workspace_models import ManualAssetImport
    root = '/api/projects/project/studio/assets'
    assert is_independent_studio_route('POST', root + '/model-reference')
    assert is_independent_studio_route('GET', root + '/asset/model-reference')
    for method, suffix in [('PUT', '/model-reference'), ('POST', '/asset/model-reference'), ('POST', '/model-reference/execute'), ('GET', '/asset/model-reference/download')]:
        assert not is_independent_studio_route(method, root + suffix)
    with pytest.raises(ValueError):
        ManualAssetImport.model_validate({'filename': 'triangle.glb', 'kind': 'model', 'content_base64': 'AAAA', 'idempotency_key': 'old-contract'})


def test_real_router_import_inspection_authority_and_private_validation(rig, monkeypatch):
    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient
    from app.creative.workspace_api import create_independent_workspace_router, ModelReferenceImportRoute
    from app.experimental.flags import require_flag
    permissions = {'domain.read', 'domain.write'}
    def authorize(nid, token, branch, permission):
        if nid != rig.nid or token != 'fixture-session' or branch is not None or permission not in permissions:
            raise HTTPException(403, {'code': 'DENIED'})
        return rig.actor, rig.scope
    app = FastAPI()
    app.include_router(create_independent_workspace_router(rig.service, authorize, require_flag,
        create_project=lambda *args: None, workspace_writer=lambda token: rig.actor), prefix='/api')
    with TestClient(app) as client:
        root = f'/api/projects/{rig.nid}/studio/assets'
        assert client.post(root + '/model-reference', json=body()).status_code == 403
        headers = {'X-Session-Token': 'fixture-session'}
        bad = client.post(root + '/model-reference', headers=headers, json={**body(), 'unexpected': 'PRIVATE-FIXTURE-VALUE'})
        assert bad.status_code == 422 and 'PRIVATE-FIXTURE-VALUE' not in bad.text
        assert bad.headers['cache-control'] == 'no-store'
        response = client.post(root + '/model-reference', headers=headers, json=body())
        assert response.status_code == 201, response.text
        asset = response.json()
        inspected = client.get(root + '/' + asset['id'] + '/model-reference', headers=headers)
        assert inspected.status_code == 200 and inspected.json()['inspection']['triangle_count_per_primitive'] == 1
        assert inspected.headers['cache-control'] == 'no-store'
        permissions.remove('domain.read')
        assert client.get(root + '/' + asset['id'] + '/model-reference', headers=headers).status_code == 403
        monkeypatch.setattr(ModelReferenceImportRoute, 'MAX_BODY', 1000)
        large = client.post(root + '/model-reference', headers=headers, content=b' ' * 1001)
        assert large.status_code == 413 and 'MODEL_REFERENCE_REQUEST_LIMIT' in large.text
