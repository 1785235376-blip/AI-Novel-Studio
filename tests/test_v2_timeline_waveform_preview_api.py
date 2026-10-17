"""Mounted waveform preview retains the original Host and File authorities."""
from copy import deepcopy
from uuid import uuid4

import pytest

from app.actor_context import SessionContext
from app.asset_providers import AssetProviderRegistry
from test_r3_mounted_contracts import checked, mounted, prefix, scoped
from test_v2_independent_workspace_api import client
from test_v2_timeline_waveform_preview import (
    durable_files, forbid_effects, persist_audio, persist_visual, request_body, timeline, wav,
)

pytestmark = [pytest.mark.file_backend_only, pytest.mark.parametrize('mounted', ['file'], indirect=True)]


@pytest.fixture
def waveform_client(client, monkeypatch):
    e = client
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
    e.host = 'waveform-host-' + uuid4().hex
    e.session = SessionContext('session-' + e.host, 'client-' + e.host, 'waveform-author', 'waveform-workspace')
    e.sessions.register(e.host, e.session)
    e.headers = {'X-Session-Token': e.host}
    checked(e.client.post(e.studio_base + '/activate', headers=e.headers))
    e.production = e.experimental.studio_production_service
    monkeypatch.setattr(e.production, 'workspace', e.studio)
    monkeypatch.setattr(e.production, 'store', e.studio.store)
    monkeypatch.setattr(e.production, 'image_registry', AssetProviderRegistry())
    monkeypatch.setattr(e.production.timeline_inputs, 'workspace', e.studio)
    monkeypatch.setattr(e.production.timeline_inputs, 'store', e.studio.store)
    e.source = persist_audio(e.studio, e.nid, e.scope, wav([-32768] + [0] * 799))
    e.visual = persist_visual(e.studio, e.nid, e.scope)
    e.timeline_base = e.studio_base + '/production/timelines'
    e.saved = checked(e.client.post(e.timeline_base, headers=e.headers, json={
        'expected_version': 0, 'title': 'Mounted waveform fixture', 'timeline': timeline(e.source, e.visual)}), 201)
    e.path = e.timeline_base + '/' + e.saved['id'] + '/waveform-preview'
    e.body = request_body(e.saved)
    forbid_effects(monkeypatch, e.production)
    return e


def post(e, **kwargs):
    return e.client.post(e.path, headers=kwargs.pop('headers', e.headers),
                         **(kwargs or {'json': e.body}))


def test_original_mounted_route_measures_without_ai_flag_or_product_writes(waveform_client):
    e = waveform_client; before = durable_files(e.root)
    response = post(e); result = checked(response)
    assert result['contract'] == 'studio-timeline-waveform-preview/1'
    assert result['peaks'] == [1.0] + [0.0] * 399
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['x-content-type-options'] == 'nosniff'
    assert durable_files(e.root) == before
    assert checked(e.client.get(e.timeline_base + '/' + e.saved['id'], headers=e.headers)) == e.saved
    assert checked(e.client.get(e.timeline_base + '/' + e.saved['id'] + '/history', headers=e.headers))['items'] == []
    assert len(checked(e.client.get(e.studio_base + '/assets', headers=e.headers))['items']) == 2


@pytest.mark.parametrize('change', ['missing', 'forged', 'origin', 'forwarded', 'revoke', 'feature', 'acceptance'])
def test_current_original_authority_rejects_before_measurement(waveform_client, monkeypatch, change):
    e = waveform_client
    if change == 'missing': e.headers = {}
    elif change == 'forged': e.headers = {'X-Session-Token': 'forged-waveform-host'}
    elif change == 'origin': e.headers = {**e.headers, 'Origin': 'https://untrusted.invalid'}
    elif change == 'forwarded': e.headers = {**e.headers, 'Forwarded': 'for=127.0.0.1'}
    elif change == 'revoke': e.sessions.revoke(e.host)
    elif change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'asset_lineage_v2')
    elif change == 'acceptance': monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    before = durable_files(e.root)
    response = post(e)
    assert response.status_code in {401, 403, 404}, response.text
    assert 'peaks' not in response.json()
    assert response.headers['cache-control'] == 'no-store'
    assert durable_files(e.root) == before


@pytest.mark.parametrize('change', ['revoke', 'aba', 'actor', 'feature'])
def test_authority_change_during_original_bounded_read_suppresses_peaks(waveform_client, monkeypatch, change):
    e = waveform_client; original = e.assets.content; calls = []
    def changed(*args, **kwargs):
        assert kwargs['max_bytes'] == 8 * 1024 * 1024 and callable(kwargs['guard'])
        value = original(*args, **kwargs)
        if not calls:
            calls.append(True)
            if change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'asset_lineage_v2')
            else:
                e.sessions.revoke(e.host)
                if change == 'aba': e.sessions.register(e.host, e.session)
                elif change == 'actor':
                    e.sessions.register(e.host, SessionContext('other-session', 'other-client', 'other-actor', 'other-workspace'))
        return value
    monkeypatch.setattr(e.assets, 'content', changed)
    before = durable_files(e.root)
    response = post(e)
    assert calls and response.status_code in {401, 403, 404}, response.text
    assert 'peaks' not in response.json() and durable_files(e.root) == before


@pytest.mark.parametrize('kind', ['extra', 'boolean-version', 'private-path', 'malformed-json', 'oversized'])
def test_route_local_bad_dto_is_bounded_sanitized_and_nonmutating(waveform_client, kind):
    e = waveform_client; marker = 'PRIVATE_SENTINEL_/home/private/waveform.wav'
    body = deepcopy(e.body)
    if kind == 'extra': body['filename'] = marker
    elif kind == 'boolean-version': body['expected_version'] = True
    elif kind == 'private-path': body['source_snapshot']['digest'] = marker
    elif kind == 'oversized': body['padding'] = marker * 200
    before = durable_files(e.root)
    response = post(e, content='{"private": "' + marker if kind == 'malformed-json' else None,
                    headers={**e.headers, 'Content-Type': 'application/json'}) if kind == 'malformed-json' else post(e, json=body)
    assert response.status_code in {413, 422}, response.text
    assert marker not in response.text and '/home/private' not in response.text
    assert 'peaks' not in response.json()
    assert response.headers['cache-control'] == 'no-store'
    assert durable_files(e.root) == before


@pytest.mark.parametrize('change', ['timeline-version', 'timeline-digest', 'source-digest', 'source-version'])
def test_mounted_stale_exact_review_pins_never_emit_envelope(waveform_client, change):
    e = waveform_client; body = deepcopy(e.body)
    if change == 'timeline-version': body['expected_version'] += 1
    elif change == 'timeline-digest': body['reviewed_timeline_digest'] = '0' * 64
    elif change == 'source-digest': body['source_snapshot']['digest'] = '0' * 64
    else: body['source_snapshot']['version'] += 1
    before = durable_files(e.root)
    response = post(e, json=body)
    assert response.status_code in {409, 422}, response.text
    assert 'peaks' not in response.json() and durable_files(e.root) == before


@pytest.mark.parametrize('change', ['revoke', 'aba', 'feature'])
def test_current_authority_at_pcm_checkpoint_suppresses_result(waveform_client, monkeypatch, change):
    import app.creative.timeline_waveform as module
    e = waveform_client; original = module.pcm16_envelope; calls = []
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(True)
        if change == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'asset_lineage_v2')
        else:
            e.sessions.revoke(e.host)
            if change == 'aba': e.sessions.register(e.host, e.session)
        kwargs['guard']()
        return result
    monkeypatch.setattr(module, 'pcm16_envelope', changed)
    before = durable_files(e.root)
    response = post(e)
    assert calls == [True] and response.status_code in {401, 403, 404}, response.text
    assert 'peaks' not in response.json() and durable_files(e.root) == before


@pytest.mark.parametrize('change', ['new-host-session', 'branch-header'])
def test_original_local_author_scope_remains_local_for_a_fresh_request(waveform_client, change):
    e = waveform_client
    # Existing local workbench authority is local-author, independent of the
    # valid Host's actor name and of collaboration headers while disabled.
    if change == 'new-host-session':
        e.sessions.revoke(e.host)
        e.sessions.register(e.host, SessionContext('replacement-session', 'replacement-client',
            'different-host-actor', 'different-host-workspace'))
    else:
        e.headers = {**e.headers, 'X-Branch-ID': 'ignored-local-branch'}
    before = durable_files(e.root)
    result = checked(post(e))
    assert result['branch_id'] is None and result['peaks'] == [1.0] + [0.0] * 399
    assert durable_files(e.root) == before


@pytest.mark.parametrize('change', ['missing-marker', 'deleted', 'recreated'])
def test_route_rejects_retired_or_missing_identity_without_provisioning(waveform_client, change):
    e = waveform_client
    if change == 'missing-marker':
        (e.root / 'novels' / e.nid / 'creative_project_v2.json').unlink()
    else:
        e.novels.delete(e.nid)
        if change == 'recreated':
            e.novels.create({'id': e.nid, 'title': 'New project under retired public ID'})
    before = durable_files(e.root)
    response = post(e)
    assert response.status_code in {403, 404, 409, 422}, response.text
    assert 'peaks' not in response.json()
    assert durable_files(e.root) == before


@pytest.mark.parametrize('caller', ['lead', 'viewer', 'wrong-branch'])
def test_real_collaboration_membership_does_not_grant_host_authority(waveform_client, monkeypatch, caller):
    e = scoped(waveform_client, monkeypatch)
    headers = e.viewer_headers if caller == 'viewer' else e.headers
    if caller == 'wrong-branch':
        headers = {**headers, 'X-Branch-ID': e.other_branch}
    before = durable_files(e.root)
    response = post(e, headers=headers)
    assert response.status_code == 403, response.text
    assert 'peaks' not in response.json() and durable_files(e.root) == before
