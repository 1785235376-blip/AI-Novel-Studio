"""Independent mounted controls for the closed audiobook candidate gate."""
import copy

import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from test_audio_history_status_readonly import snapshot
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def closed(rig, monkeypatch):
    from app.experimental import api as experimental_api
    from app.experimental.audiobook import AudiobookV2Service
    scope, headers = shared_scope(rig)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', rig.nid)
    for perm in ('domain.write', 'domain.review'):
        rig.grants.assign_permission(PermissionAssignment('test-' + perm, 'reader', perm,
            ModalityDomain.NOVEL, grant_scope, 'fixture'))
    row = candidate()
    row.update(novel_id=rig.nid, scope=copy.deepcopy(scope), status='APPROVING',
               promotion_token='synthetic-token', promotion_started_at='synthetic-time',
               promotion_actor='reader')
    with rig.workspace.store.store.transaction(rig.nid, scope) as doc:
        doc['collections']['audio_v2_mix_proposals'] = {row['id']: row}
        doc['collections']['audio_v2_plans'] = {'synthetic-plan': {
            'id': 'synthetic-plan', 'novel_id': rig.nid, 'scope': copy.deepcopy(scope),
            'version': 1, 'segments': []}}
    service = AudiobookV2Service(rig.workspace.store.store, rig.novels,
        rig.workspace.creative.chapters, assets=rig.assets)
    mounted = experimental_api.audiobook_service
    for name in ('store', 'novels', 'chapters', 'assets'):
        monkeypatch.setattr(mounted, name, getattr(service, name))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',
        'narrative_production_v2,asset_lineage_v2,audiobook_v2,unified_review_inbox')
    asset = rig.seed('existing.wav', 'audio', scope_value=scope)
    return rig, scope, headers, row, asset


@pytest.mark.parametrize('alias', [False, True])
def test_mounted_approving_candidate_denied_before_side_effects_and_original_reads_work(closed, monkeypatch, alias):
    rig, scope, headers, row, asset = closed
    monkeypatch.setattr(rig.assets, 'create', lambda *a, **kw: pytest.fail('asset create reached'))
    prefix = f"/api{'/v1' if alias else ''}"
    base = prefix + f'/novels/{rig.nid}/experimental/audiobook'
    before = snapshot(rig.root)
    denied = rig.client.post(base + f"/mixes/{row['id']}/approve", headers=headers,
                             json={'expected_version': row['version']})
    assert denied.status_code == 422, denied.text
    assert denied.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    mixes = rig.client.get(base + '/mixes', headers=headers)
    assert mixes.status_code == 200, mixes.text
    assert row['id'] in [item['id'] for item in mixes.json()['items']]
    download = rig.client.get(prefix + f"/projects/{rig.nid}/studio/assets/{asset['id']}/download", headers=headers)
    assert download.status_code == 200, download.text
    assert download.content == b'synthetic fixture bytes'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_unauthorized_review_denied_before_gate(closed, alias):
    rig, _, headers, row, _ = closed
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f"/novels/{rig.nid}/experimental/audiobook/mixes/{row['id']}/approve"
    before = snapshot(rig.root)
    response = rig.client.post(path, headers={**headers, 'X-Session-Token': 'token-no-grants'},
                               json={'expected_version': row['version']})
    assert response.status_code == 403, response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_inbox_review_of_approving_candidate_is_also_closed(closed, monkeypatch, alias):
    rig, scope, headers, row, _ = closed
    with rig.workspace.store.store.transaction(rig.nid, scope) as doc:
        doc['collections']['audio_v2_plans'] = {}
    monkeypatch.setattr(rig.assets, 'create', lambda *a, **kw: pytest.fail('asset create reached'))
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f"/novels/{rig.nid}/experimental/review-inbox/audiobook/{row['id']}/approve"
    before = snapshot(rig.root)
    response = rig.client.post(path, headers=headers, json={'expected_version': row['version']})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_mix_entry_closed_before_mixer_and_no_mutation(closed, monkeypatch, alias):
    rig, _, headers, _, _ = closed
    from app.experimental import api as experimental_api
    class Mixer:
        local = True
        adapter_id = 'synthetic'
        def mix(self, request):
            pytest.fail('mixer reached')
    monkeypatch.setattr(experimental_api.audiobook_service, 'mixer', Mixer())
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{rig.nid}/experimental/audiobook/plans/synthetic-plan/mix'
    before = snapshot(rig.root)
    response = rig.client.post(path, headers=headers, json={'expected_version': 1})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(rig.root) == before

@pytest.mark.parametrize('alias', [False, True])
def test_closed_mix_on_uninitialized_scope_does_not_create_lock(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2')
    mounted = experimental_api.audiobook_service
    for name, value in (('store', rig.workspace.store.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    prefix = f"/api{'/v1' if alias else ''}"
    before = snapshot(rig.root)
    response = rig.client.post(prefix + f'/novels/{rig.nid}/experimental/audiobook/plans/missing-plan/mix',
                               json={'expected_version': 1})
    assert response.status_code in (404, 422), response.text
    assert snapshot(rig.root) == before

@pytest.mark.parametrize('alias', [False, True])
def test_closed_candidate_review_on_uninitialized_scope_does_not_create_lock(rig, monkeypatch, alias):
    from app.experimental import api as experimental_api
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,audiobook_v2')
    mounted = experimental_api.audiobook_service
    for name, value in (('store', rig.workspace.store.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    prefix = f"/api{'/v1' if alias else ''}"
    before = snapshot(rig.root)
    response = rig.client.post(prefix + f'/novels/{rig.nid}/experimental/audiobook/mixes/missing-candidate/approve',
                               json={'expected_version': 1})
    assert response.status_code == 422, response.text
    assert snapshot(rig.root) == before
