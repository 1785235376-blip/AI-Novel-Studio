"""Comic request/adoption routes retain original mounted authority and Image owners."""
from copy import deepcopy

import pytest

from test_r3_mounted_contracts import mounted, prefix, checked
from test_v2_independent_workspace_api import client
from test_v2_discovered_image_production_api import image_client, EXECUTION_FLAGS


@pytest.fixture
def comic_api(image_client, monkeypatch):
    e = image_client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join((*EXECUTION_FLAGS, 'comic_layouts_v2', 'ai_director_v2')))
    e.comic = e.experimental.comic_layouts_service
    monkeypatch.setattr(e.comic, 'independent_store', e.studio.store)
    monkeypatch.setattr(e.production, 'comic_images', None)
    e.production.configure_comic(e.comic)
    e.comic_base = e.prefix + f'/novels/{e.nid}/experimental/comic-layouts/records'
    e.page = checked(e.client.post(e.comic_base, headers=e.headers, json={
        'title': 'SYNTHETIC comic image', 'source_mode': 'INDEPENDENT', 'panels': [
            {'id': 'panel', 'artwork_mode': 'IMAGE', 'order': 1,
             'x': 24, 'y': 24, 'width': 752, 'height': 320, 'image_brief': 'SYNTHETIC quiet harbour'}]}), 201)
    e.panel_base = e.base + '/comic-pages/' + e.page['id'] + '/panels/panel'
    e.request_body = {'expected_version': 1, 'request_id': 'mounted-comic-image',
        'provider_id': e.adapter.candidate['provider_id'], 'model_id': e.adapter.candidate['id'],
        'parameters': {'width': 64, 'height': 64, 'seed': 3}}
    return e


def exact_action(row):
    return {'expected_version': row['version'], 'expected_request_digest': row['request_digest']}


def test_mounted_request_private_review_separate_adopt_and_stale_replay(comic_api):
    e = comic_api
    response = e.client.post(e.panel_base + '/image-request', headers=e.headers, json=e.request_body)
    request = checked(response)
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert request['contract'] == 'studio-comic-image-request/1' and not request['automatic_dispatch']
    assert request['command']['prompt'] == e.page['document']['panels'][0]['image_brief']
    assert not e.calls
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=request['command']))
    queued = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': request['command'], 'reviewed_preview_digest': preview['preview_digest']}), 201)
    assert not e.calls
    path = e.base + '/jobs/image/' + queued['id']
    candidate = checked(e.client.post(path + '/execute', headers=e.headers, json=exact_action(queued)))
    assert candidate['status'] == 'AWAITING_REVIEW'
    private = e.client.get(e.studio_base + '/assets/' + candidate['output_candidate']['id'], headers=e.headers)
    assert private.status_code == 404
    assert checked(e.client.get(e.comic_base, headers=e.headers))['items'][0]['version'] == 1
    approved = checked(e.client.post(path + '/review', headers=e.headers, json={**exact_action(candidate),
        'reviewed_output_digest': candidate['output_candidate']['digest']}))
    assert approved['status'] == 'APPROVED'
    assert checked(e.client.get(e.comic_base, headers=e.headers))['items'][0]['version'] == 1
    body = {'expected_version': 1, 'job_id': approved['id'], 'expected_job_version': approved['version'],
        'expected_request_digest': approved['request_digest'], 'expected_asset_version': approved['approved_asset_version'],
        'expected_output_digest': approved['output_candidate']['digest']}
    adopted = checked(e.client.post(e.panel_base + '/adopt-image', headers=e.headers, json=body))
    assert adopted['id'] == e.page['id'] and adopted['version'] == 2 and adopted['status'] == 'DRAFT'
    assert adopted['document']['panels'][0]['asset_id'] == approved['output_candidate']['id']
    stale = e.client.post(e.panel_base + '/adopt-image', headers=e.headers, json=body)
    assert stale.status_code == 409
    assert checked(e.client.get(e.comic_base, headers=e.headers))['items'][0]['version'] == 2
    assert len([url for url, _ in e.calls if url.endswith('/prompt')]) == 1


@pytest.mark.parametrize('suffix', ['image-request', 'adopt-image'])
def test_mounted_routes_reject_untrusted_session_without_side_effects(comic_api, suffix):
    e = comic_api; before = deepcopy(e.store.read(e.nid, {'mode': 'local', 'novel_id': e.nid}))
    response = e.client.post(e.panel_base + '/' + suffix, headers={'X-Session-Token': 'untrusted'},
        json=e.request_body if suffix == 'image-request' else {'expected_version': 1, 'job_id': 'missing',
            'expected_job_version': 1, 'expected_request_digest': '0' * 64, 'expected_asset_version': 2,
            'expected_output_digest': '0' * 64})
    assert response.status_code == 401
    assert e.store.read(e.nid, {'mode': 'local', 'novel_id': e.nid}) == before and not e.calls


def test_mounted_request_rejects_stale_page_and_extra_prompt(comic_api):
    e = comic_api
    response = e.client.post(e.panel_base + '/image-request', headers=e.headers,
        json={**e.request_body, 'expected_version': 99})
    assert response.status_code == 409
    response = e.client.post(e.panel_base + '/image-request', headers=e.headers,
        json={**e.request_body, 'prompt': 'UNSAVED PRIVATE OVERRIDE'})
    assert response.status_code == 422 and not e.calls


@pytest.mark.parametrize('flag', ['comic_layouts_v2', 'asset_lineage_v2', 'ai_director_v2', 'narrative_production_v2'])
def test_mounted_request_requires_original_feature_gates(comic_api, monkeypatch, flag):
    import os
    e = comic_api
    flags = os.environ['EXPERIMENTAL_FEATURES'].split(',')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(value for value in flags if value != flag))
    response = e.client.post(e.panel_base + '/image-request', headers=e.headers, json=e.request_body)
    assert response.status_code == 404 and not e.calls


def test_execution_revocation_allows_passive_request_but_blocks_provider(comic_api, monkeypatch):
    import os
    e = comic_api
    request = checked(e.client.post(e.panel_base + '/image-request', headers=e.headers, json=e.request_body))
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=request['command']))
    queued = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': request['command'], 'reviewed_preview_digest': preview['preview_digest']}), 201)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in
        os.environ['EXPERIMENTAL_FEATURES'].split(',') if flag != 'ai_execution_v2'))
    assert checked(e.client.post(e.panel_base + '/image-request', headers=e.headers, json=e.request_body)) == request
    response = e.client.post(e.base + '/jobs/image/' + queued['id'] + '/execute',
        headers=e.headers, json=exact_action(queued))
    assert response.status_code == 404 and not e.calls
    assert checked(e.client.get(e.comic_base, headers=e.headers))['items'][0]['version'] == 1
