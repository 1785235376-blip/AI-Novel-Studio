"""Fresh mounted manual mask route through original File/real PostgreSQL owners."""
import base64
import json
from uuid import uuid4

import pytest
from app.actor_context import SessionContext
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_manual_mask_pixels import source_png, plane


@pytest.fixture
def mask_client(client, monkeypatch):
    e = client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
    e.host = 'manual-mask-host-' + uuid4().hex
    e.session = SessionContext('session-' + e.host, 'client-' + e.host, 'mask-author', 'mask-workspace')
    e.sessions.register(e.host, e.session); e.headers = {'X-Session-Token': e.host}
    with e.studio._asset_scope(e.nid, e.scope):
        e.source = e.assets.create(e.nid, 'source.png', base64.b64encode(source_png()).decode(), 'image/png', 'image', 'source', required_features=('narrative_production_v2',))
    e.body = {'contract': 'manual-binary-mask/1', 'source_version': 1, 'source_sha256': e.source['sha256'],
        'width': 64, 'height': 64, 'bitplane_base64': plane(), 'idempotency_key': 'mask-request'}
    e.path = e.studio_base + f"/assets/{e.source['id']}/mask"
    return e


def post(e, **kw): return e.client.post(e.path, headers=kw.pop('headers', e.headers), **({'json': e.body} if not kw else kw))


def private_error(response, status):
    assert response.status_code == status, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert 'private-canary' not in response.text


def test_mounted_real_save_download_replay_and_provenance(mask_client, tmp_path):
    e = mask_client; response = post(e); result = checked(response, 201)
    assert response.headers['cache-control'] == 'no-store'
    asset, receipt = result['asset'], result['receipt']
    assert asset['version'] == 1 and asset['provenance']['origin'] == 'MANUAL_EDIT'
    assert asset['provenance']['integrity'] == 'VERIFIED' and not asset['provenance']['stale']
    assert asset['provenance']['parents'][0]['state'] == 'CURRENT'
    assert receipt['source_asset_id'] == e.source['id'] and receipt['mask_sha256'] == asset['sha256']
    assert checked(post(e), 201) == result
    downloaded = e.client.get(e.studio_base + f"/assets/{asset['id']}/download", headers=e.headers)
    assert downloaded.status_code == 200
    from app.services.studio_image_mask_authoring import verify_mask
    assert verify_mask(downloaded.content)['mask_sha256'] == receipt['mask_sha256']
    assert '_manual_mask_origin' not in json.dumps(result) and 'scope_key' not in json.dumps(result)
    # Optional cross-owner decoder evidence uses only this test-owned directory.
    import os
    if os.getenv('STUDIO_CAPTURE_MANUAL_MASK') == '1':
        (tmp_path / 'manual-mask-response.json').write_text(json.dumps({'request': e.body, 'source': e.studio.asset(e.nid, e.scope, e.source['id']), 'response': result}))


@pytest.mark.parametrize('headers,status', [({}, 401), ({'X-Session-Token': 'forged'}, 401), ({'Origin': 'https://untrusted.invalid'}, 403), ({'Forwarded': 'for=127.0.0.1'}, 403)])
def test_actual_host_is_required(mask_client, headers, status):
    e = mask_client
    if 'X-Session-Token' not in headers and headers: headers = {**e.headers, **headers}
    private_error(post(e, headers=headers), status)
    assert len(list(e.assets.root.glob('*.json'))) == 1


@pytest.mark.parametrize('flag', ['narrative_production_v2', 'asset_lineage_v2', 'acceptance'])
def test_both_feature_flags_and_acceptance_override_fail_closed(mask_client, monkeypatch, flag):
    e = mask_client
    if flag == 'acceptance': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(x for x in ['narrative_production_v2', 'asset_lineage_v2'] if x != flag))
    private_error(post(e), 404)
    assert len(list(e.assets.root.glob('*.json'))) == 1


@pytest.mark.parametrize('change', ['unknown', 'type', 'json', 'base64', 'dimensions', 'digest'])
def test_private_body_errors_never_echo_inputs(mask_client, change):
    e = mask_client; body = dict(e.body)
    if change == 'json': response = post(e, content=b'{"private-canary":', headers={**e.headers, 'Content-Type': 'application/json'})
    else:
        if change == 'unknown': body['private-canary'] = 'private-canary'
        elif change == 'type': body['source_version'] = 'private-canary'
        elif change == 'base64': body['bitplane_base64'] = 'private-canary'
        elif change == 'dimensions': body['width'] = 65
        else: body['source_sha256'] = 'private-canary'
        response = post(e, json=body)
    private_error(response, 422)
    assert len(list(e.assets.root.glob('*.json'))) == 1


@pytest.mark.parametrize('length', [None, '1', '9999999'])
def test_stream_cap_does_not_trust_content_length(mask_client, length):
    e = mask_client; headers = {**e.headers, 'Content-Type': 'application/json'}
    if length is not None: headers['Content-Length'] = length
    def chunks():
        for _ in range(4): yield b'private-canary' + b'x' * 65536
    private_error(post(e, headers=headers, content=chunks()), 413)
    assert len(list(e.assets.root.glob('*.json'))) == 1


@pytest.mark.parametrize('change', ['revoke', 'same_epoch_aba', 'rebind', 'flag'])
def test_late_authority_change_before_staging_denies(mask_client, monkeypatch, change):
    import app.services.studio_image_mask_authoring as pixels
    e = mask_client; original = pixels.encode_mask
    def changed(*a, **k):
        answer = original(*a, **k)
        if change == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        else:
            e.sessions.revoke(e.host)
            if change == 'same_epoch_aba': e.sessions.register(e.host, e.session)
            elif change == 'rebind': e.sessions.register(e.host, SessionContext('other', 'other', 'other', 'other'))
        return answer
    monkeypatch.setattr(pixels, 'encode_mask', changed)
    response = post(e)
    assert response.status_code in (401, 403, 404), response.text
    assert len(list(e.assets.root.glob('*.json'))) == 1


def test_collaboration_only_and_unknown_routes_do_not_gain_host_authority(mask_client, monkeypatch):
    e = scoped(mask_client, monkeypatch)
    private_error(post(e), 403)
    for method, suffix in [('GET', ''), ('PUT', ''), ('POST', '/extra')]:
        response = e.client.request(method, e.path + suffix, headers=e.headers, json=e.body)
        assert response.status_code == 501
    assert len(list(e.assets.root.glob('*.json'))) == 1


def test_source_revision_conflict_and_lost_response_are_explicit(mask_client, monkeypatch):
    e = mask_client; original = e.studio.author_mask
    def lost(*a, **k): original(*a, **k); raise ValueError('IMAGE_MASK_SYNTHETIC_LOST_RESPONSE')
    monkeypatch.setattr(e.studio, 'author_mask', lost)
    assert post(e).status_code == 422
    assert len(list(e.assets.root.glob('*.json'))) == 2
    monkeypatch.setattr(e.studio, 'author_mask', original)
    with e.studio._asset_scope(e.nid, e.scope): e.assets.update_metadata(e.source['id'], {'scene_id': 'changed'}, expected_version=1)
    response = post(e); private_error(response, 409)
    assert response.json()['detail']['code'] == 'EXPERIMENTAL_SOURCE_STALE'
    assert len(list(e.assets.root.glob('*.json'))) == 2
    rows = checked(e.client.get(e.studio_base + '/assets', headers=e.headers))['items']
    assert any(x['provenance']['origin'] == 'MANUAL_EDIT' and x['provenance']['stale'] for x in rows)
