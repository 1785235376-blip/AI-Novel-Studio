"""Independent verification of audiobook scope write closure."""
import copy

import pytest

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from test_audio_history_status_readonly import snapshot
from test_audio_shared_replacement_plan_independent import candidate
from test_studio_asset_query import rig, shared_scope

pytestmark = pytest.mark.file_backend_only


@pytest.fixture
def env(rig, monkeypatch):
    from app.experimental import api as experimental_api
    mounted = experimental_api.audiobook_service
    for name, value in (('store', rig.workspace.store.store), ('novels', rig.novels),
                        ('chapters', rig.workspace.creative.chapters), ('assets', rig.assets)):
        monkeypatch.setattr(mounted, name, value)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES',
        'narrative_production_v2,asset_lineage_v2,audiobook_v2,unified_review_inbox')
    return rig


@pytest.mark.parametrize('alias', [False, True])
@pytest.mark.parametrize('path,body', [
    ('profiles', {'display_name': 'synthetic', 'provider_id': 'local', 'model_id': 'local',
                  'voice_id': 'synthetic', 'license_note': 'synthetic'}),
    ('mappings', {'character_id': '__narrator__', 'profile_id': 'missing'}),
    ('plans', {'chapter_id': 'missing', 'title': 'synthetic'}),
    ('plans/missing/approve', {'expected_version': 1}),
    ('mixes/missing/approve', {'expected_version': 1}),
])
def test_first_write_rejected_without_initializing_scope(env, alias, path, body):
    prefix = f"/api{'/v1' if alias else ''}"
    before = snapshot(env.root)
    response = env.client.post(prefix + f'/novels/{env.nid}/experimental/audiobook/' + path, json=body)
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(env.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_no_review_authority_precedes_closure(env, alias):
    _, headers = shared_scope(env)
    before = snapshot(env.root)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{env.nid}/experimental/audiobook/plans/missing/approve'
    response = env.client.post(path, headers={**headers, 'X-Session-Token': 'token-no-grants'},
                               json={'expected_version': 1})
    assert response.status_code == 403, response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(env.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_existing_approving_candidate_can_be_listed_but_cannot_be_reviewed(env, alias):
    row = candidate()
    row.update(novel_id=env.nid, scope=copy.deepcopy(env.scope), status='APPROVING',
               promotion_token='synthetic-token', promotion_started_at='synthetic-time', promotion_actor='local-author')
    with env.workspace.store.store.transaction(env.nid, env.scope) as doc:
        doc['collections']['audio_v2_mix_proposals'] = {row['id']: row}
    asset = env.seed('existing.wav', 'audio')
    before = snapshot(env.root)
    prefix = f"/api{'/v1' if alias else ''}"
    base = prefix + f'/novels/{env.nid}/experimental/audiobook'
    listed = env.client.get(base + '/mixes')
    assert listed.status_code == 200, listed.text
    assert row['id'] in [item['id'] for item in listed.json()['items']]
    review = env.client.post(base + f"/mixes/{row['id']}/approve", json={'expected_version': row['version']})
    assert review.status_code == 422, review.text
    assert review.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    inbox = env.client.post(prefix + f"/novels/{env.nid}/experimental/review-inbox/audiobook/{row['id']}/approve",
                            json={'expected_version': row['version']})
    assert inbox.status_code == 422, inbox.text
    assert inbox.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    downloaded = env.client.get(prefix + f"/projects/{env.nid}/studio/assets/{asset['id']}/download")
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.content == b'synthetic fixture bytes'
    assert snapshot(env.root) == before


@pytest.mark.parametrize('alias', [False, True])
def test_existing_plan_review_is_also_closed_compatibility_change(env, alias):
    with env.workspace.store.store.transaction(env.nid, env.scope) as doc:
        doc['collections']['audio_v2_plans'] = {'synthetic-plan': {
            'id': 'synthetic-plan', 'novel_id': env.nid, 'scope': copy.deepcopy(env.scope),
            'version': 1, 'segments': [], 'status': 'PENDING_REVIEW', 'history': [],
            'created_by': 'local-author', 'created_at': 'synthetic-time'}}
    before = snapshot(env.root)
    prefix = f"/api{'/v1' if alias else ''}"
    response = env.client.post(prefix + f'/novels/{env.nid}/experimental/audiobook/plans/synthetic-plan/reject',
                               json={'expected_version': 1})
    assert response.status_code == 422, response.text
    assert response.json()['detail']['message'] == 'AUDIO_CAPACITY_WRITE_UNAVAILABLE'
    assert snapshot(env.root) == before

@pytest.mark.parametrize('alias', [False, True])
def test_first_inbox_review_does_not_create_scope_lock(env, alias):
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{env.nid}/experimental/review-inbox/audiobook/missing/approve'
    before = snapshot(env.root)
    response = env.client.post(path, json={'expected_version': 1})
    assert response.status_code in (404, 422), response.text
    assert snapshot(env.root) == before

@pytest.mark.parametrize('alias', [False, True])
def test_first_inbox_audio_only_batch_does_not_create_scope_lock(env, alias):
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{env.nid}/experimental/review-inbox/batch'
    payload = {'items': [{'domain': 'audiobook', 'id': 'missing', 'action': 'approve', 'expected_version': 1}]}
    before = snapshot(env.root)
    response = env.client.post(path, json=payload)
    assert response.status_code in (404, 422), response.text
    assert snapshot(env.root) == before

@pytest.mark.parametrize('alias', [False, True])
def test_inbox_authorization_and_audio_flag_precede_closed_gate(env, monkeypatch, alias):
    _, headers = shared_scope(env)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{env.nid}/experimental/review-inbox/audiobook/missing/approve'
    before = snapshot(env.root)
    denied = env.client.post(path, headers={**headers, 'X-Session-Token': 'token-no-grants'},
                             json={'expected_version': 1})
    assert denied.status_code == 403, denied.text
    assert snapshot(env.root) == before
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', env.nid)
    env.grants.assign_permission(PermissionAssignment('test-inbox-review', 'reader', 'domain.review',
        ModalityDomain.NOVEL, grant_scope, 'synthetic'))
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2,unified_review_inbox')
    before = snapshot(env.root)
    disabled = env.client.post(path, headers=headers, json={'expected_version': 1})
    assert disabled.status_code == 404, disabled.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in disabled.text
    assert snapshot(env.root) == before


def test_other_inbox_domain_retains_original_review_and_batch():
    from app.experimental.inbox import UnifiedReviewInbox, ReviewBinding, ReviewContext
    from types import SimpleNamespace
    seen = []
    inbox = UnifiedReviewInbox()
    row = {'id': 'one', 'version': 1, 'allowed_actions': ['reject']}
    inbox.register(ReviewBinding('other', lambda context: [row],
        lambda context, rid, action, version: seen.append((rid, action, version)) or {'ok': True},
        batch_actions=frozenset({'reject'})))
    ctx = ReviewContext('synthetic', {'mode': 'local', 'novel_id': 'synthetic'}, 'actor')
    assert inbox.review(ctx, 'other', 'one', 'reject', 1) == {'ok': True}
    item = SimpleNamespace(domain='other', id='one', action='reject', expected_version=1)
    assert inbox.batch(ctx, [item], lambda: None)['status'] == 'COMPLETED'
    assert seen == [('one', 'reject', 1), ('one', 'reject', 1)]

@pytest.mark.parametrize('alias', [False, True])
def test_inbox_review_also_requires_original_audio_read_permission(env, alias):
    _, headers = shared_scope(env)
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, 'query-workspace', env.nid)
    env.grants.assign_permission(PermissionAssignment('review-only', 'no-grants', 'domain.review',
        ModalityDomain.NOVEL, grant_scope, 'synthetic'))
    before = snapshot(env.root)
    prefix = f"/api{'/v1' if alias else ''}"
    path = prefix + f'/novels/{env.nid}/experimental/review-inbox/audiobook/missing/approve'
    response = env.client.post(path, headers={**headers, 'X-Session-Token': 'token-no-grants'},
                               json={'expected_version': 1})
    assert response.status_code == 403, response.text
    assert 'AUDIO_CAPACITY_WRITE_UNAVAILABLE' not in response.text
    assert snapshot(env.root) == before
