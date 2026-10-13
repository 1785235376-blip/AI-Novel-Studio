"""Mounted standalone CPU cutout: trusted Host authority and original receipts."""
import json
import os
from copy import deepcopy
from uuid import uuid4

import pytest

from app.actor_context import SessionContext
from app.services.image_job_service import ImageJobService
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_manual_mask_api import mask_client, post
from test_v2_cpu_cutout_owner import NoControl, snapshot


@pytest.fixture
def cpu_client(mask_client, monkeypatch):
    e = mask_client
    e.mask_response = checked(post(e), 201); e.mask = e.mask_response['asset']
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.production = e.experimental.studio_production_service
    for name, value in (('workspace', e.studio), ('store', e.studio.store),
            ('image_jobs', ImageJobService(e.root)), ('image_registry', NoControl()), ('vault', NoControl()), ('transport', NoControl())):
        monkeypatch.setattr(e.production, name, value)
    e.base = e.studio_base + '/production'
    e.command = {'operation_id': 'm5.image.cutout', 'request_id': 'mounted-cutout', 'provider_id': None,
        'model_id': None, 'prompt': '', 'parameters': {}, 'allow_cloud': False, 'license_note': '',
        'source_snapshots': [snapshot(e.source), snapshot(e.mask)]}
    import app.creative.production_execution as module
    import app.services.studio_image_execution as image_owner
    import subprocess
    def denied(*a, **k): raise AssertionError('cutout attempted generic media decoder/process')
    monkeypatch.setattr(module, 'inspect_image', denied)
    monkeypatch.setattr(image_owner, 'inspect_image', denied)
    monkeypatch.setattr(subprocess, 'run', denied); monkeypatch.setattr(subprocess, 'Popen', denied)
    return e


def preview(e): return e.client.post(e.base + '/preview', headers=e.headers, json=e.command)


def queue(e):
    captured = checked(preview(e))
    return captured, checked(e.client.post(e.base + '/jobs', headers=e.headers,
        json={'command': e.command, 'reviewed_preview_digest': captured['preview_digest']}), 201)


def action(row): return {'expected_version': row['version'], 'expected_request_digest': row['request_digest']}


def run(e, row): return e.client.post(e.base + '/jobs/image/' + row['id'] + '/execute', headers=e.headers, json=action(row))


def test_mounted_cutout_no_ai_flag_response_fixture_and_explicit_approval(cpu_client, tmp_path):
    e = cpu_client; captured, row = queue(e)
    assert captured['command']['parameters'] == row['command']['parameters'] == {}
    executed = checked(run(e, row)); assert executed['status'] == 'AWAITING_REVIEW'
    asset = executed['output_candidate']
    assert e.client.get(e.studio_base + '/assets/' + asset['id'], headers=e.headers).status_code == 404
    downloaded = e.client.get(e.base + '/jobs/image/' + row['id'] + '/candidate', headers=e.headers)
    assert downloaded.status_code == 200
    assert downloaded.headers['x-asset-sha256'] == executed['processing_proof']['output_sha256']
    approved = checked(e.client.post(e.base + '/jobs/image/' + row['id'] + '/review', headers=e.headers,
        json={**action(executed), 'reviewed_output_digest': asset['digest']}))
    assert approved['status'] == 'APPROVED' and approved['approved_asset_version'] == 2
    result = checked(e.client.get(e.studio_base + '/assets/' + asset['id'], headers=e.headers))
    assert result['provenance']['origin'] == 'DERIVED_PROCESSING'
    assert result['provider_id'] is None and result['model_id'] is None
    assert e.mask['manual_mask'] == e.mask_response['receipt']
    if os.environ.get('STUDIO_CAPTURE_CPU_CUTOUT') == '1':
        fixture = {'command': e.command, 'source': e.studio.asset(e.nid, e.scope, e.source['id']),
            'mask': e.mask, 'preview': captured, 'queued': row, 'executed': executed, 'approved': approved, 'result': result}
        (tmp_path / 'cpu-cutout-response.json').write_text(json.dumps(fixture))
    for response in (preview(e),):
        assert response.headers['cache-control'] == 'no-store'
        assert response.headers['x-content-type-options'] == 'nosniff'


@pytest.mark.parametrize('change', ['missing', 'forged', 'origin', 'forwarded', 'lineage', 'feature', 'acceptance'])
def test_host_feature_and_acceptance_fail_closed(cpu_client, monkeypatch, change):
    e = cpu_client
    if change == 'missing': e.headers = {}
    elif change == 'forged': e.headers = {'X-Session-Token': 'forged'}
    elif change == 'origin': e.headers = {**e.headers, 'Origin': 'https://untrusted.invalid'}
    elif change == 'forwarded': e.headers = {**e.headers, 'Forwarded': 'for=127.0.0.1'}
    elif change == 'lineage': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
    elif change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'asset_lineage_v2')
    else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    response = preview(e)
    assert response.status_code in {401, 403, 404}, response.text
    assert response.headers['cache-control'] == 'no-store'
    assert len(list(e.assets.root.glob('*.bin'))) == 2


@pytest.mark.parametrize('change', ['revoke', 'aba', 'rebind', 'lineage'])
def test_renderer_rechecks_host_incarnation_before_publication(cpu_client, monkeypatch, change):
    e = cpu_client; _, row = queue(e)
    import app.services.studio_image_cutout as pixels
    original = pixels.render_cutout
    def changed(*a, **k):
        value = original(*a, **k)
        if change == 'lineage': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2')
        else:
            e.sessions.revoke(e.host)
            if change == 'aba': e.sessions.register(e.host, e.session)
            elif change == 'rebind': e.sessions.register(e.host, SessionContext('other', 'other', 'other', 'other'))
        return value
    monkeypatch.setattr(pixels, 'render_cutout', changed)
    response = run(e, row)
    assert response.status_code in {401, 403, 404}, response.text
    assert len(list(e.assets.root.glob('*.bin'))) == 2


def test_exact_original_job_response_cas_and_source_binding(cpu_client):
    e = cpu_client; _, row = queue(e)
    path = e.base + '/jobs/image/' + row['id']
    assert checked(e.client.get(path, headers=e.headers)) == row
    wrong = {**action(row), 'expected_version': row['version'] + 1}
    response = e.client.post(path + '/cancel', headers=e.headers, json=wrong)
    assert response.status_code == 409
    cancelled = checked(e.client.post(path + '/cancel', headers=e.headers, json=action(row)))
    assert cancelled['status'] == 'CANCELLED' and cancelled['cancellation_mode'] == 'COOPERATIVE_LOCAL_CANCEL'
    assert cancelled['processing_proof'] is None and not cancelled['remote_compute_may_continue']
    assert checked(e.client.get(path, headers=e.headers)) == cancelled
    assert run(e, cancelled).status_code == 422


def test_collaboration_session_cannot_supply_trusted_host(cpu_client, monkeypatch):
    e = scoped(cpu_client, monkeypatch)
    assert preview(e).status_code == 403
