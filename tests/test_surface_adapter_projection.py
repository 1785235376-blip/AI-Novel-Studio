"""Original adapter receipts in mounted Task/Review centers, File and real PG.

No provider admission, alternate approval, or rendered exact-open route is implied.
"""
from dataclasses import replace
import json

import pytest
from fastapi import HTTPException

from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
from app.experimental.common import change_row
from app.experimental.flags import FLAGS
from app.experimental.ux import ReadContext
from app.experimental.research_vision import SyntheticResearchVisionProvider
from app.services.v1_capability_service import VisualMemoryIn
from test_r3_mounted_contracts import mounted, prefix, checked, scoped
from test_surface_search_visual_research import surfaces, image_source, analysis, reference, check_request
from test_r4_research_library import payload


DOMAINS = ('research_analysis', 'visual_identity')


def receipt(e, domain, headers=None):
    if domain == 'research_analysis':
        source = image_source(e, headers)
        return analysis(e, source, headers=headers), source
    asset, profile = reference(e, getattr(e, 'branch', None))
    return checked(e.client.post(e.emb + '/visual-identity/checks', headers=headers or {},
        json=check_request(asset, profile)), 201), (asset, profile)


def original(e, domain):
    return (e.research, 'analysis_jobs', 'analysis_job', 'research_analysis_jobs') if domain == 'research_analysis' else (
        e.embedding, 'visual_checks', 'visual_check', 'visual_identity_checks')


def task(e, domain, rid, headers=None):
    rows = checked(e.client.get(e.base + '/workspace/tasks', headers=headers or {}))['items']
    return next(row for row in rows if row['authority'] == domain and row['id'] == rid)


def read_context(e):
    return ReadContext(e.nid, e.scope, getattr(e, 'lead', 'local-author'),
        getattr(e, 'lead', None), getattr(e, 'branch', None))


def reader(e, domain):
    return next(value for value in e.experimental.workspace_tools_service.task_readers if value.name == domain)


@pytest.mark.parametrize('domain', DOMAINS)
def test_mounted_projection_is_minimal_formal_and_cannot_approve(surfaces, domain):
    e = surfaces; job, source = receipt(e, domain)
    before = e.store.read(e.nid, e.scope)
    row = task(e, domain, job['id'])
    assert row['status'] == 'NOT_CONFIGURED' and row['actions'] == ['cancel']
    assert row['navigation_contract'] == 'FORMAL_SOURCE_ONLY' and row['source_domain'] == domain
    assert 'source' not in row and 'owner_navigation' not in row
    reviews = checked(e.client.get(e.base + '/review-inbox', params={'domain': domain}))['items']
    assert len(reviews) == 1 and reviews[0]['id'] == job['id']
    review = reviews[0]
    assert review['allowed_actions'] == [] and review['batch_actions'] == [] and not review['batch_safe']
    assert review['target']['navigation_contract'] == 'FORMAL_SOURCE_ONLY'
    assert review['preview'] == '' and review['source_versions'] == {'receipt_version': job['version']}
    assert review['model_quality'] == 'NOT_RUN' and review['runtime_admission'] == 'NOT_CONFIGURED'
    assert not review['automatic_resume'] and not review['durable_worker']
    for projected in (row, review):
        assert not {'request', 'result', 'model', 'source_snapshot', 'result_digest', 'execution_token'}.intersection(projected)
        encoded = json.dumps(projected)
        for value in [source['id']] if domain == 'research_analysis' else [source[0]['id'], source[1]['id']]:
            assert value not in encoded
    aggregate = task(e, 'review_inbox', domain + ':' + job['id'])
    assert aggregate['navigation_contract'] == 'FORMAL_SOURCE_ONLY' and 'open_source' not in aggregate['actions']
    for action in ('approve', 'reject', 'reopen'):
        assert e.client.post(e.base + f"/review-inbox/{domain}/{job['id']}/{action}",
            json={'expected_version': job['version']}).status_code == 422
    assert e.client.post(e.base + '/review-inbox/batch', json={'items': [{
        'domain': domain, 'id': job['id'], 'action': 'approve', 'expected_version': job['version']}]}).status_code == 422
    assert e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize('domain', DOMAINS)
def test_original_cancel_uses_revision_and_retains_only_receipt_metadata(surfaces, domain):
    e = surfaces; job, _ = receipt(e, domain); row = task(e, domain, job['id'])
    endpoint = e.base + f"/workspace/tasks/{domain}/{job['id']}/cancel"
    assert e.client.post(endpoint, json={'expected_revision': '0' * 64}).status_code == 409
    result = checked(e.client.post(endpoint, json={'expected_revision': row['revision']}))
    assert result['cancellation_requested'] and result['executor'] is False
    assert result['item']['status'] == 'CANCELLED' and result['item']['actions'] == []
    assert result['item']['action_limits']['cancel'] == 'TERMINAL_OR_UNSUPPORTED'
    service, _, get, collection = original(e, domain)
    stored = e.store.read(e.nid, e.scope)['collections'][collection][job['id']]
    assert stored['status'] == 'CANCELLED' and stored['version'] == job['version'] + 1
    public = getattr(service, get)(e.nid, e.scope, 'local-author', job['id'])
    assert not {'request', 'source_snapshot', 'model', 'result_digest'}.intersection(public)
    assert e.client.post(endpoint, json={'expected_revision': row['revision']}).status_code == 409


@pytest.mark.parametrize('domain', DOMAINS)
def test_current_creator_branch_and_permission_fences(surfaces, monkeypatch, domain):
    e = scoped(surfaces, monkeypatch); job, _ = receipt(e, domain, e.headers)
    assert task(e, domain, job['id'], e.headers)['id'] == job['id']
    viewer = checked(e.client.get(e.base + '/workspace/tasks', headers=e.viewer_headers))
    assert job['id'] not in json.dumps(viewer)
    inbox = checked(e.client.get(e.base + '/review-inbox', headers=e.viewer_headers))
    assert job['id'] not in json.dumps(inbox)
    assert {'domain': 'research_analysis', 'reason': 'ORIGINAL_DOMAIN_ACCESS_REQUIRED'} in inbox['unavailable']
    assert e.client.get(e.base + '/workspace/tasks', headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code == 403
    context = read_context(e)
    for forged in (replace(context, actor=e.viewer), replace(context, scope={**e.scope, 'storyline_id': 'wrong'}),
                   replace(context, branch=e.other_branch)):
        with pytest.raises(HTTPException): reader(e, domain).read(forged)
    # Even a second writer cannot see a creator-only receipt.
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_permission(PermissionAssignment('writer-' + e.viewer, e.viewer, 'domain.write', ModalityDomain.NOVEL, scope, e.lead))
    assert job['id'] not in json.dumps(checked(e.client.get(e.base + '/workspace/tasks', headers=e.viewer_headers)))
    assert job['id'] not in json.dumps(checked(e.client.get(e.base + '/review-inbox', headers=e.viewer_headers)))


@pytest.mark.parametrize('domain', DOMAINS)
@pytest.mark.parametrize('revoke', ['role', 'feature'])
def test_late_read_revocation_discards_rows_and_unrelated_failures_propagate(surfaces, monkeypatch, domain, revoke):
    e = scoped(surfaces, monkeypatch); job, _ = receipt(e, domain, e.headers)
    service, listing, _, _ = original(e, domain); original_list = getattr(service, listing)
    def revoke_after_read(*args):
        result = original_list(*args)
        if revoke == 'role': e.authorization.revoke_role(e.role, e.lead)
        else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in FLAGS if flag != reader(e, domain).flag))
        return result
    monkeypatch.setattr(service, listing, revoke_after_read)
    with pytest.raises(HTTPException) as error: reader(e, domain).read(read_context(e))
    assert error.value.status_code in {403, 404}
    assert job['id'] not in str(error.value.detail)


@pytest.mark.parametrize('domain', DOMAINS)
def test_projection_does_not_swallow_corrupt_original_sources(surfaces, monkeypatch, domain):
    e = surfaces; receipt(e, domain); service, listing, _, _ = original(e, domain)
    def corrupt(*args): raise ValueError('CORRUPT_ORIGINAL_STORE')
    monkeypatch.setattr(service, listing, corrupt)
    with pytest.raises(ValueError, match='CORRUPT_ORIGINAL_STORE'): reader(e, domain).read(read_context(e))
    assert e.client.get(e.base + '/review-inbox', params={'domain': domain}).status_code == 422


@pytest.mark.parametrize('flag', ['research_library_v2', 'semantic_import_v2', 'temporal_story_graph_v2', 'world_character_engines_v2', 'visual_embeddings'])
def test_original_feature_and_dependencies_hide_projections(surfaces, monkeypatch, flag):
    e = surfaces; research, _ = receipt(e, 'research_analysis'); visual, _ = receipt(e, 'visual_identity')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(value for value in FLAGS if value != flag))
    payloads = [checked(e.client.get(e.base + path)) for path in ('/workspace/tasks', '/review-inbox')]
    hidden, visible = (visual, research) if flag == 'visual_embeddings' else (research, visual)
    for result in payloads:
        assert hidden['id'] not in json.dumps(result)
        assert visible['id'] in json.dumps(result)


def test_research_source_changes_invalidate_revision_then_revoke_omits_every_projection(surfaces):
    e = surfaces; job, source = receipt(e, 'research_analysis'); initial = task(e, 'research_analysis', job['id'])
    replaced = checked(e.client.put(e.lib + f"/sources/{source['id']}/file", json=payload('replacement text', expected_version=source['version'])))
    current = task(e, 'research_analysis', job['id'])
    assert current['stale'] and current['revision'] != initial['revision']
    assert e.client.post(e.base + f"/workspace/tasks/research_analysis/{job['id']}/cancel",
        json={'expected_revision': initial['revision']}).status_code == 409
    e.research.transition_source(e.nid, e.scope, 'local-author', source['id'], replaced['version'], 'revoke', guard=lambda: None)
    for path in ('/workspace/tasks', '/review-inbox'):
        result = checked(e.client.get(e.base + path))
        assert job['id'] not in json.dumps(result) and source['id'] not in json.dumps(result)


@pytest.mark.parametrize('revoke', ['asset', 'approval'])
def test_visual_source_removal_omits_all_receipt_views(surfaces, revoke):
    e = surfaces; job, (asset, profile) = receipt(e, 'visual_identity')
    before = task(e, 'visual_identity', job['id'])
    if revoke == 'asset': e.assets.delete(asset['id'])
    else: e.capabilities.update_visual_memory(e.nid, profile['id'], VisualMemoryIn(
        entity_type='CHARACTER', entity_id='alice', asset_id=asset['id'], appearance={'hair': 'red'}), profile['version'])
    for path in ('/workspace/tasks', '/review-inbox'):
        encoded = json.dumps(checked(e.client.get(e.base + path)))
        assert job['id'] not in encoded and asset['id'] not in encoded and profile['id'] not in encoded
    assert e.client.post(e.base + f"/workspace/tasks/visual_identity/{job['id']}/cancel",
        json={'expected_revision': before['revision']}).status_code == 404


@pytest.mark.parametrize('domain', DOMAINS)
def test_cancel_checks_original_cas_after_projection(surfaces, monkeypatch, domain):
    e = surfaces; job, _ = receipt(e, domain); before = task(e, domain, job['id'])
    service, _, _, collection = original(e, domain)
    method = 'analysis_action' if domain == 'research_analysis' else 'visual_action'
    action = getattr(service, method)
    def competing_revision(*args, **kwargs):
        with e.store.transaction(e.nid, e.scope) as state:
            row = state['collections'][collection][job['id']]
            change_row(row, 'local-author', row['version'], lambda target: target.update(error_code='PRIVATE_FAILURE_SECRET'))
        return action(*args, **kwargs)
    monkeypatch.setattr(service, method, competing_revision)
    response = e.client.post(e.base + f"/workspace/tasks/{domain}/{job['id']}/cancel", json={'expected_revision': before['revision']})
    assert response.status_code == 409 and response.json()['detail']['current'] == {'version': 2}
    assert 'PRIVATE_FAILURE_SECRET' not in response.text and 'source_snapshot' not in response.text
    assert e.store.read(e.nid, e.scope)['collections'][collection][job['id']]['status'] == 'NOT_CONFIGURED'


@pytest.mark.parametrize('domain', DOMAINS)
def test_cancel_requires_current_write_even_for_readable_creator(surfaces, monkeypatch, domain):
    e = scoped(surfaces, monkeypatch); job, _ = receipt(e, domain, e.headers)
    before = task(e, domain, job['id'], e.headers)
    scope = AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch)
    e.authorization.assign_permission(PermissionAssignment('read-lead-' + e.lead, e.lead, 'domain.read', ModalityDomain.NOVEL, scope, e.lead))
    e.authorization.revoke_role(e.role, e.lead)
    response = e.client.post(e.base + f"/workspace/tasks/{domain}/{job['id']}/cancel", headers=e.headers,
        json={'expected_revision': before['revision']})
    assert response.status_code == 403
    current = checked(e.client.get(e.base + '/workspace/tasks', headers=e.headers))
    assert (job['id'] in json.dumps(current)) == (domain == 'visual_identity')


def test_ready_analysis_projection_and_resume_never_copy_model_results(surfaces, monkeypatch):
    e = surfaces; job, source = receipt(e, 'research_analysis')
    monkeypatch.setattr(e.research, 'vision_provider', SyntheticResearchVisionProvider())
    ready = checked(e.client.post(e.lib + f"/analysis/jobs/{job['id']}/run", json={'expected_version': job['version']}))
    assert ready['result']['blocks'] and ready['model']['verification'] == 'MOCK_ONLY'
    save = checked(e.client.put(e.base + '/workspace/resume', json={
        'expected_version': 0, 'chapter_id': None, 'chapter_version': None,
        'anchor': {'offset': 0, 'scroll': 0}, 'stopping_note': 'Continue receipt review.'}))
    pending = [row for row in save['item']['pending_tasks'] if row['authority'] == 'research_analysis']
    assert pending[0]['id'] == job['id'] and pending[0]['navigation_contract'] == 'FORMAL_SOURCE_ONLY'
    for path in ('/workspace/tasks', '/workspace/resume', '/review-inbox?domain=research_analysis'):
        encoded = json.dumps(checked(e.client.get(e.base + path)))
        assert 'Synthetic contract result' not in encoded and source['id'] not in encoded
        assert 'source_snapshot' not in encoded and 'result_digest' not in encoded
    e.research.transition_source(e.nid, e.scope, 'local-author', source['id'], source['version'], 'revoke', guard=lambda: None)
    resume = checked(e.client.get(e.base + '/workspace/resume'))
    assert job['id'] not in json.dumps(resume) and resume['item']['tasks_recovery_required']


@pytest.mark.parametrize('domain', DOMAINS)
@pytest.mark.parametrize('revoke', ['role', 'feature'])
def test_late_cancel_authority_revocation_rolls_back_original_receipt(surfaces, monkeypatch, domain, revoke):
    e = scoped(surfaces, monkeypatch); job, _ = receipt(e, domain, e.headers)
    before = task(e, domain, job['id'], e.headers)
    service, _, _, collection = original(e, domain)
    snapshot = e.store.read(e.nid, e.scope)['collections'][collection][job['id']]
    method = 'analysis_action' if domain == 'research_analysis' else 'visual_action'
    action = getattr(service, method)
    calls = []
    def revoke_before_commit(*args, **kwargs):
        guard = kwargs['guard'] if domain == 'research_analysis' else args[-1]
        def late_guard():
            calls.append(True)
            if len(calls) == 2:
                if revoke == 'role': e.authorization.revoke_role(e.role, e.lead)
                else: monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in FLAGS if flag != reader(e, domain).flag))
            guard()
        if domain == 'research_analysis': kwargs['guard'] = late_guard
        else: args = (*args[:-1], late_guard)
        return action(*args, **kwargs)
    monkeypatch.setattr(service, method, revoke_before_commit)
    response = e.client.post(e.base + f"/workspace/tasks/{domain}/{job['id']}/cancel", headers=e.headers,
        json={'expected_revision': before['revision']})
    assert response.status_code in {403, 404} and len(calls) == 2
    assert e.store.read(e.nid, e.scope)['collections'][collection][job['id']] == snapshot


@pytest.mark.parametrize('domain', DOMAINS)
def test_formal_receipts_cannot_create_fallback_search_navigation(surfaces, domain):
    e = surfaces; job, _ = receipt(e, domain)
    result = checked(e.client.get(e.base + '/workspace/search', params={'q': job['id'], 'kind': 'task'}))
    assert result['items'] == []
    result = checked(e.client.get(e.base + '/workspace/search', params={'q': job['id'], 'kind': 'review'}))
    assert result['items'] == []


@pytest.mark.parametrize('domain', DOMAINS)
def test_running_receipts_and_their_review_aggregate_are_recovery_only(surfaces, domain):
    e = surfaces; job, _ = receipt(e, domain)
    _, _, _, collection = original(e, domain)
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections'][collection][job['id']]
        change_row(row, 'local-author', row['version'], lambda target: target.update(status='RUNNING', execution_token='orphaned-fixture'))
    for authority, rid in ((domain, job['id']), ('review_inbox', domain + ':' + job['id'])):
        row = task(e, authority, rid)
        assert row['status'] == 'UNKNOWN' and row['stage_label'] == '等待原服务恢复'
        assert 'open_source' not in row['actions'] and 'orphaned-fixture' not in json.dumps(row)


@pytest.mark.parametrize('revoke', ['asset', 'approval'])
def test_visual_source_revoked_after_initial_get_is_omitted_by_final_source_fence(surfaces, monkeypatch, revoke):
    e = surfaces; job, (asset, profile) = receipt(e, 'visual_identity')
    get = e.embedding.visual_check; calls = []
    def revoke_after_get(*args):
        result = get(*args); calls.append(True)
        if len(calls) == 1:
            if revoke == 'asset': e.assets.delete(asset['id'])
            else: e.capabilities.update_visual_memory(e.nid, profile['id'], VisualMemoryIn(
                entity_type='CHARACTER', entity_id='alice', asset_id=asset['id'], appearance={'hair': 'red'}), profile['version'])
        return result
    monkeypatch.setattr(e.embedding, 'visual_check', revoke_after_get)
    assert reader(e, 'visual_identity').read(read_context(e)) == []
    assert calls == [True]


@pytest.mark.parametrize('domain', DOMAINS)
def test_exhausted_original_cancel_capacity_is_not_advertised(surfaces, domain):
    e = surfaces; job, _ = receipt(e, domain); _, _, _, collection = original(e, domain)
    with e.store.transaction(e.nid, e.scope) as state:
        row = state['collections'][collection][job['id']]
        row.update(status='DRAFT', history=[{'version': index + 1, 'status': 'CANCELLED'} for index in range(99)], version=100)
    projected = task(e, domain, job['id'])
    assert 'cancel' not in projected['actions']
    assert projected['action_limits']['cancel'] == 'RECEIPT_CAPACITY_EXHAUSTED'
    denied = e.client.post(e.base + f"/workspace/tasks/{domain}/{job['id']}/cancel", json={'expected_revision': projected['revision']})
    assert denied.status_code == 422
    stored = e.store.read(e.nid, e.scope)['collections'][collection][job['id']]
    assert stored['status'] == 'DRAFT' and stored['version'] == 100


@pytest.mark.parametrize('domain', DOMAINS)
@pytest.mark.parametrize('terminal', ['REVIEWED', 'INVALIDATED'])
def test_terminal_adapter_receipts_are_not_saved_as_pending_resume_work(surfaces, monkeypatch, domain, terminal):
    from app.experimental.embeddings import MockEmbeddingProvider
    e = surfaces; job, _ = receipt(e, domain)
    path = (e.lib + '/analysis/jobs/' if domain == 'research_analysis' else e.emb + '/visual-identity/checks/') + job['id']
    if terminal == 'REVIEWED':
        if domain == 'research_analysis': monkeypatch.setattr(e.research, 'vision_provider', SyntheticResearchVisionProvider())
        else: monkeypatch.setattr(e.embedding, 'provider', MockEmbeddingProvider())
        ready = checked(e.client.post(path + '/run', json={'expected_version': job['version']}))
        checked(e.client.post(path + '/review', json={'expected_version': ready['version']}))
    else:
        checked(e.client.post(path + '/invalidate', json={'expected_version': job['version']}))
    assert task(e, domain, job['id'])['status'] == terminal
    assert task(e, 'review_inbox', domain + ':' + job['id'])['status'] == terminal
    saved = checked(e.client.put(e.base + '/workspace/resume', json={'expected_version': 0,
        'chapter_id': None, 'chapter_version': None, 'anchor': {'offset': 0, 'scroll': 0}}))
    assert job['id'] not in json.dumps(saved['item']['pending_tasks'])


def test_terminal_receipt_pending_rule_preserves_unrelated_actionable_domains():
    from app.experimental.ux import WorkspaceToolsService
    for status in ('REVIEWED', 'INVALIDATED'):
        for authority in ('research_analysis', 'visual_identity', 'review_inbox'):
            assert not WorkspaceToolsService._pending({'authority': authority, 'status': status,
                'navigation_contract': 'FORMAL_SOURCE_ONLY'})
        # An original owner's invalidated record can still require rebuild/repair.
        # Its historical pending semantics must not inherit adapter completion.
        assert WorkspaceToolsService._pending({'authority': 'media', 'status': status})
