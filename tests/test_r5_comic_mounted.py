"""Actual mounted B06 router, original asset owner and trusted-session fences."""
import base64
import io
import json
import zipfile
import pytest
from app.experimental.flags import FLAGS
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_r5_comic_layouts import synthetic_png


def create_source(e, headers=None):
    source = e.screenplays.create(e.nid, 'Synthetic test comic', branch_id=e.scope.get('branch_id'))
    if e.scope.get('branch_id'):
        # Explicit independent synthetic scene, supported by the original source
        # authority; never pretend an unadapted manuscript belongs to a branch.
        for scene in source['scenes']:
            scene['source_chapter_id'] = None; scene['source_version'] = None; scene['source_independent'] = True
        source = e.screenplays._save_screenplay(e.nid, source)
    source = e.screenplays.approve(e.nid, source['id'], source['edit_version'])
    return e.screenplays.plan_shots(e.nid, source['id'], source['edit_version'])


def create_layout(e, headers=None):
    headers = headers or {}; source = create_source(e, headers)
    asset = e.assets.create(e.nid, 'SYNTHETIC-TEST-ASSET.png', base64.b64encode(synthetic_png()).decode(), 'image/png', branch_id=e.scope.get('branch_id'))
    image_path = e.base + '/comic-layouts/images/' + asset['id']
    response = e.client.get(image_path, headers=headers); assert response.status_code == 200 and response.content.startswith(b'\x89PNG')
    approved = checked(e.client.post(image_path + '/approve', headers=headers, json={'expected_version': asset['version']}))
    body = {'title': 'Synthetic reviewed layout', 'screenplay_id': source['id'], 'expected_screenplay_version': source['edit_version'], 'width': 800, 'height': 1120, 'segment_height': 560,
            'panels': [{'id': 'panel', 'shot_id': source['shots'][0]['id'], 'order': 1, 'x': 24, 'y': 24, 'width': 752, 'height': 1000, 'asset_id': asset['id'], 'expected_asset_version': approved['version']}]}
    row = checked(e.client.post(e.base + '/comic-layouts/records', headers=headers, json=body), 201)
    return row, asset, body


def test_mounted_draft_preflight_review_exact_png_export_and_privacy_headers(mounted):
    e = mounted; row, _, _ = create_layout(e); path = e.base + '/comic-layouts/records/' + row['id']
    denied = e.client.get(path + '/export?expected_version=1'); assert denied.status_code == 422 and denied.headers['cache-control'] == 'no-store'
    report = checked(e.client.post(path + '/preflight', json={'expected_version': 1})); assert report['can_render']
    approved = checked(e.client.post(path + '/approve', json={'expected_version': 1, 'review_digest': report['review_digest'], 'acknowledge_warnings': True}))
    exported = e.client.get(path + f"/export?expected_version={approved['version']}"); assert exported.status_code == 200
    assert exported.headers['cache-control'] == 'no-store' and exported.headers['x-content-type-options'] == 'nosniff'
    with zipfile.ZipFile(io.BytesIO(exported.content)) as archive:
        assert archive.read('segment-001.png') == e.client.get(path + '/segments/0?expected_version=2').content
    conflict = e.client.post(path + '/preflight', json={'expected_version': 1}); assert conflict.status_code == 409
    assert 'document' not in conflict.text and 'asset_sources' not in conflict.text


@pytest.mark.parametrize('flags,v1', [('', 'false'), ('*', 'false'), ('comic_layouts_v2', 'false'), (','.join(FLAGS), 'true')])
def test_mounted_off_v1_and_dependency_fences(mounted, monkeypatch, flags, v1):
    e = mounted; monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
    for method, path, body in [('get', '/catalog', None), ('get', '/records', None), ('post', '/records/missing/preflight', {'expected_version': 1}), ('get', '/records/missing/export?expected_version=1', None)]:
        response = getattr(e.client, method)(e.base + '/comic-layouts' + path, **({'json': body} if body else {})); assert response.status_code == 404
    assert not e.store.read(e.nid, e.scope)['collections'].get('comic_layouts_v2')


def test_mounted_actor_branch_and_role_revocation(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch); row, _, _ = create_layout(e, e.headers); path = e.base + '/comic-layouts/records/' + row['id']
    for headers in [{}, e.viewer_headers, {**e.headers, 'X-Branch-ID': e.other_branch}]:
        response = e.client.get(e.base + '/comic-layouts/records', headers=headers)
        assert row['id'] not in response.text and 'Synthetic reviewed layout' not in response.text
    report = checked(e.client.post(path + '/preflight', headers=e.headers, json={'expected_version': 1}))
    denied = e.client.post(path + '/approve', headers=e.viewer_headers, json={'expected_version': 1, 'review_digest': report['review_digest']}); assert denied.status_code == 403
    e.authorization.revoke_role(e.role, e.lead)
    assert e.client.post(path + '/preflight', headers=e.headers, json={'expected_version': 1}).status_code == 403


@pytest.mark.parametrize('change', ['flag', 'session'])
def test_mounted_mid_render_revocation_never_returns_pixels(mounted, monkeypatch, change):
    import app.experimental.comic_layouts as module
    e = scoped(mounted, monkeypatch); row, _, _ = create_layout(e, e.headers); original = module.compose
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs.get('render'):
            if change == 'flag': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
            else: e.sessions.revoke(e.lead)
        return result
    monkeypatch.setattr(module, 'compose', changed)
    response = e.client.get(e.base + f"/comic-layouts/records/{row['id']}/segments/0?expected_version=1", headers=e.headers)
    assert response.status_code in {401, 404} and not response.content.startswith(b'\x89PNG')
    assert response.headers['cache-control'] == 'no-store'


def test_mounted_stale_projection_hides_all_dialogue_and_old_asset_ids(mounted):
    e = mounted; row, asset, body = create_layout(e)
    body['panels'][0]['bubbles'] = [{'id': 'secret', 'text': 'Private draft dialogue', 'x': 40, 'y': 40, 'width': 500, 'height': 160}]
    checked(e.client.put(e.base + '/comic-layouts/records/' + row['id'], json={**body, 'expected_version': 1}))
    e.assets.update_metadata(asset['id'], {'parameters': {'changed': True}})
    response = e.client.get(e.base + '/comic-layouts/records'); assert response.status_code == 200
    assert 'Private draft dialogue' not in response.text and asset['id'] not in response.text
    assert response.json()['items'][0]['stale']
