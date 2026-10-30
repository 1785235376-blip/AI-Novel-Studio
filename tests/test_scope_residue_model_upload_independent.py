"""Actual mounted GLB upload must not bypass closed project capacity admission."""
import base64
import hashlib
import json
import struct

import pytest

from test_studio_workspace_identity_history_contract import audio_history
from test_studio_asset_query import rig, shared_scope
from test_audio_history_status_readonly import snapshot


def glb_triangle():
    binary = struct.pack('<9f', 0, 0, 0, 1, 0, 0, 0, 1, 0)
    doc = {'asset': {'version': '2.0'}, 'buffers': [{'byteLength': len(binary)}],
           'bufferViews': [{'buffer': 0, 'byteLength': len(binary)}],
           'accessors': [{'bufferView': 0, 'componentType': 5126, 'count': 3, 'type': 'VEC3'}],
           'meshes': [{'primitives': [{'attributes': {'POSITION': 0}}]}]}
    payload = json.dumps(doc, separators=(',', ':')).encode()
    payload += b' ' * (-len(payload) % 4)
    total = 12 + 8 + len(payload) + 8 + len(binary)
    return (struct.pack('<III', 0x46546c67, 2, total)
            + struct.pack('<II', len(payload), 0x4e4f534a) + payload
            + struct.pack('<II', len(binary), 0x004e4942) + binary)


@pytest.mark.parametrize('alias', ['', '/v1'])
def test_real_model_upload_cannot_bypass_residue_or_closed_capacity(audio_history, alias):
    e = audio_history
    scope_path = e.rig.workspace.store.path(e.rig.nid, e.rig.scope)
    scope_path.parent.mkdir(parents=True, exist_ok=True)
    residue = scope_path.parent / (scope_path.name + '.unowned-synthetic.tmp')
    residue.write_bytes(b'unknown synthetic residue')
    before = hashlib.sha256(residue.read_bytes()).hexdigest()
    data = glb_triangle()
    result = e.client.post(f'/api{alias}/projects/{e.rig.nid}/studio/assets/model-reference',
        headers=e.headers, json={'contract': 'studio-static-glb-import/1',
            'filename': 'triangle.glb', 'kind': 'model',
            'content_base64': base64.b64encode(data).decode(), 'idempotency_key': 'independent-glb'})
    assert hashlib.sha256(residue.read_bytes()).hexdigest() == before
    if result.status_code == 201:
        with e.rig.workspace._asset_scope(e.rig.nid, e.rig.scope):
            assert e.rig.assets.content(result.json()['id']) == data
    assert result.status_code == 503, (result.status_code, result.text)
    assert result.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'


def payload():
    return {'contract': 'studio-static-glb-import/1', 'filename': 'triangle.glb',
            'kind': 'model', 'content_base64': base64.b64encode(glb_triangle()).decode(),
            'idempotency_key': 'synthetic-glb-independent'}


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_closed_before_marker_and_preserves_permission_priority(rig, prefix):
    marker = rig.root / 'novels' / rig.nid / 'creative_project_v2.json'
    assert not marker.exists()
    before = snapshot(rig.root)
    response = rig.client.post(f'{prefix}/projects/{rig.nid}/studio/assets/model-reference', json=payload())
    assert response.status_code == 503, response.text
    assert response.json()['detail']['code'] == 'PROJECT_CAPACITY_WRITE_UNAVAILABLE'
    assert not marker.exists() and snapshot(rig.root) == before


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_revoked_and_unprivileged_cannot_learn_gate(rig, prefix):
    _, headers = shared_scope(rig)
    path = f'{prefix}/projects/{rig.nid}/studio/assets/model-reference'
    before = snapshot(rig.root)
    denied = rig.client.post(path, json=payload(), headers={**headers, 'X-Session-Token': 'token-no-grants'})
    assert denied.status_code == 403 and 'PROJECT_CAPACITY_WRITE_UNAVAILABLE' not in denied.text
    rig.sessions.revoke(headers['X-Session-Token'])
    revoked = rig.client.post(path, json=payload(), headers=headers)
    assert revoked.status_code in (401, 403) and 'PROJECT_CAPACITY_WRITE_UNAVAILABLE' not in revoked.text
    assert snapshot(rig.root) == before


def test_direct_service_closed_before_decode_or_write(rig, monkeypatch):
    from app.creative import model_reference_glb
    monkeypatch.setattr(model_reference_glb, 'inspect_static_glb', lambda _: pytest.fail('GLB decoded before closed gate'))
    before = snapshot(rig.root)
    with pytest.raises(ValueError, match='PROJECT_CAPACITY_WRITE_UNAVAILABLE'):
        rig.workspace.import_model_reference(rig.nid, rig.scope, 'synthetic-actor', payload())
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_feature_disabled_before_capacity_error(rig, monkeypatch, prefix):
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    before = snapshot(rig.root)
    response = rig.client.post(f'{prefix}/projects/{rig.nid}/studio/assets/model-reference', json=payload())
    assert response.status_code != 503 and 'PROJECT_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_existing_model_bytes_are_still_readable(rig, prefix):
    data = glb_triangle()
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        asset = rig.assets.create(rig.nid, 'old.glb', base64.b64encode(data).decode(),
                                  'model/gltf-binary', 'model', required_features=('narrative_production_v2',))
    before = snapshot(rig.root)
    result = rig.client.get(f'{prefix}/projects/{rig.nid}/studio/assets/{asset["id"]}/download')
    assert result.status_code == 200 and result.content == data
    assert snapshot(rig.root) == before
