"""Capture actual mounted JSON with synthetic local image transport, not inference."""
import base64
import json
import pytest
from test_v2_comic_image_generation_api import comic_api, image_client, mounted, prefix, client, checked, exact_action

pytestmark = [pytest.mark.file_backend_only,
    pytest.mark.parametrize('mounted', ['file'], indirect=True),
    pytest.mark.parametrize('prefix', ['/api'], indirect=True)]


def test_capture_original_comic_image_http_wire(comic_api):
    e = comic_api
    providers = checked(e.client.get(e.base + '/providers', headers=e.headers))
    prepared = checked(e.client.post(e.panel_base + '/image-request', headers=e.headers, json=e.request_body))
    preview = checked(e.client.post(e.base + '/preview', headers=e.headers, json=prepared['command']))
    queued = checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': prepared['command'], 'reviewed_preview_digest': preview['preview_digest']}), 201)
    path = e.base + '/jobs/image/' + queued['id']
    candidate = checked(e.client.post(path + '/execute', headers=e.headers, json=exact_action(queued)))
    read_candidate = checked(e.client.get(path, headers=e.headers))
    assert candidate == read_candidate and candidate['status'] == 'AWAITING_REVIEW'
    approved = checked(e.client.post(path + '/review', headers=e.headers, json={**exact_action(candidate),
        'reviewed_output_digest': candidate['output_candidate']['digest']}))
    adoption = {'expected_version': e.page['version'], 'job_id': approved['id'],
        'expected_job_version': approved['version'], 'expected_request_digest': approved['request_digest'],
        'expected_asset_version': approved['approved_asset_version'],
        'expected_output_digest': approved['output_candidate']['digest']}
    adopted = checked(e.client.post(e.panel_base + '/adopt-image', headers=e.headers, json=adoption))
    assert adopted['status'] == 'DRAFT' and adopted['version'] == e.page['version'] + 1
    assert len([url for url, _ in e.calls if url.endswith('/prompt')]) == 1
    data = {'capture_contract': 'actual-mounted-comic-image-wire/1',
        'synthetic_provider': True, 'live_inference': False,
        'project_id': e.nid, 'page': e.page, 'panel_id': 'panel', 'request_body': e.request_body,
        'providers': providers, 'prepared': prepared, 'preview': preview,
        'queued': queued, 'candidate': candidate, 'approved': approved,
        'adoption_body': adoption, 'adopted': adopted,
        'candidate_png_base64': base64.b64encode(e.pixels).decode()}
    target = e.root / 'comic-image-wire.json'
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print('COMIC_WIRE_CAPTURE=' + str(target))
