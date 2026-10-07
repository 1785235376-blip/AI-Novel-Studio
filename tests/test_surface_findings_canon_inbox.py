"""Read-through production Inbox integration; original records remain authoritative."""
from copy import deepcopy
from uuid import uuid4
import pytest
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.experimental.flags import RUNTIME_FLAGS
from app.services.branch_manuscript_service import BranchManuscriptService
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_surface_finding_review import review_env, run, decision as finding_decision
from test_surface_pending_canon_review import canon_env, preview, decision as canon_decision


@pytest.fixture
def inbox_env(canon_env, review_env, monkeypatch):
    assert canon_env is review_env
    e = canon_env
    captured = e.api.finding_review_service
    for name, value in [('continuity', e.continuity), ('narrative', e.narrative), ('chapters', e.chapters), ('novels', e.novels)]:
        monkeypatch.setattr(captured, name, value)
    # All-feature aggregate also uses the newly composed original adaptation reader.
    monkeypatch.setattr(e.api.adaptation_service, 'novels', e.bundle.novels)
    monkeypatch.setattr(e.api.adaptation_service, 'chapters', e.bundle.chapters)
    e.inbox = e.base + '/review-inbox'
    return e


@pytest.mark.parametrize('kind', ['continuity', 'narrative'])
def test_actual_main_inbox_finding_exact_source_revision_stale_and_readonly(inbox_env, kind):
    e = inbox_env; row = run(e, kind); domain = kind + '_finding'
    item = checked(e.client.get(e.inbox, params={'domain': domain}))['items'][0]
    assert item['id'] == row['id'] and item['version'] == item['review_revision'] == row['review_version']
    assert item['source_revision'] == e.chapter['version'] and item['source_hash'] == row['source_digest']
    assert item['source_versions'][e.chapter['id']]['digest'] == row['source']['digest']
    assert item['target']['source_navigation'] == row['navigation']
    assert item['target']['navigation_contract'] == 'FORMAL_TARGET_ONLY'
    assert item['authority_scope'] == e.scope and item['allowed_actions'] == [] and not item['batch_safe']
    assert e.client.post(e.inbox + f'/{domain}/{row["id"]}/approve', json={'expected_version': item['version']}).status_code == 422
    assert e.client.post(e.inbox + '/batch', json={'items': [{'domain': domain, 'id': row['id'], 'action': 'reject', 'expected_version': item['version']}]}).status_code == 422
    assert e.review.get(e.nid, e.scope, kind, row['id'])['review_version'] == row['review_version']
    e.review.review(e.nid, e.scope, 'author', kind, row['id'], finding_decision(row))
    e.chapters.save(e.chapter['id'], {'content': 'NEWER_INBOX_SOURCE', 'version': e.chapter['version']})
    stale = checked(e.client.get(e.inbox, params={'domain': domain, 'stale': True}))['items'][0]
    assert stale['status'] == 'REVIEW_REQUIRED' and stale['stale']
    assert stale['version'] == 2 and stale['source_revision'] == row['source']['version']


def test_actual_main_inbox_canon_replaces_legacy_once_and_keeps_original_authority(inbox_env):
    e = inbox_env
    initial = checked(e.client.get(e.inbox))['items']
    matches = [row for row in initial if row['id'] == e.pending_id]
    assert len(matches) == 1 and matches[0]['domain'] == 'pending_canon'
    assert matches[0]['source_revision'] is None
    assert matches[0]['preview']['source_state'] == 'NOT_CONFIGURED'
    row = preview(e); approved = e.canon_review.review(e.nid, e.pending_id, 'author', canon_decision(row))
    item = checked(e.client.get(e.inbox, params={'domain': 'pending_canon'}))['items'][0]
    assert item['id'] == e.pending_id and item['version'] == item['review_revision'] == approved['version']
    assert item['source_revision'] == row['source']['version']
    assert item['authority_scope'] == {'mode': 'project', 'novel_id': e.nid}
    assert item['target']['pending_id'] == e.pending_id
    assert item['target']['authority_scope'] == item['authority_scope']
    assert item['target']['navigation_contract'] == 'FORMAL_TARGET_ONLY'
    assert 'source_evidence' not in item and e.chapter['content'] not in str(item)
    assert item['allowed_actions'] == [] and not item['batch_safe']
    assert e.client.post(e.inbox + f'/pending_canon/{e.pending_id}/approve', json={'expected_version': item['version']}).status_code == 422
    assert len(e.canon.list(e.nid)) == 1
    changed = e.chapters.save(e.chapter['id'], {'content': 'Changed after Canon decision', 'version': e.chapter['version']})
    changed_item = checked(e.client.get(e.inbox, params={'domain': 'pending_canon', 'stale': True}))['items'][0]
    assert changed_item['source_revision'] == row['source']['version'] and changed_item['current_source_revision'] == changed['version']
    assert changed_item['target']['source_navigation']['available'] is False
    e.chapters.archive(e.chapter['id'], changed['version'])
    stale = checked(e.client.get(e.inbox, params={'domain': 'pending_canon', 'stale': True}))['items'][0]
    assert stale['preview']['source_state'] == 'SOURCE_UNAVAILABLE'
    assert stale['target']['source_navigation']['available'] is False
    assert stale['target']['source_navigation']['chapter_version'] == row['source']['version']


def test_actual_main_inbox_flag_off_restores_historical_canon_projection(inbox_env, monkeypatch):
    e = inbox_env; row = run(e)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(flag for flag in RUNTIME_FLAGS if flag != 'finding_review_v1'))
    items = checked(e.client.get(e.inbox))['items']
    assert [item['domain'] for item in items if item['id'] == e.pending_id] == ['legacy_canon']
    assert all(item['id'] != row['id'] for item in items)
    assert e.client.get(e.inbox, params={'domain': 'continuity_finding'}).status_code == 404
    assert e.client.get(e.inbox, params={'domain': 'pending_canon'}).status_code == 404
    assert e.client.post(e.inbox + f'/pending_canon/{e.pending_id}/approve', json={'expected_version': 1}).status_code == 404


def test_actual_main_inbox_legacy_canon_not_suppressed_if_new_binding_is_absent(inbox_env, monkeypatch):
    import app.experimental.api as experimental
    e = inbox_env
    monkeypatch.delitem(experimental.inbox_service.bindings, 'pending_canon')
    items = checked(e.client.get(e.inbox, params={'domain': 'legacy_canon'}))['items']
    assert len(items) == 1 and items[0]['id'] == e.pending_id


def test_actual_main_inbox_branch_finding_scope_and_project_only_canon(inbox_env, monkeypatch):
    e = inbox_env; local = run(e); scoped(e, monkeypatch)
    owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, 'branch_authority', owner.for_scope, raising=False)
    chapter = owner.for_scope(e.scope).create(e.nid, {'title': 'Own branch evidence', 'content': 'BRANCH_INBOX_SOURCE'})
    own = run(e, chapter=chapter)
    items = checked(e.client.get(e.inbox, headers=e.headers, params={'domain': 'continuity_finding'}))['items']
    assert [item['id'] for item in items] == [own['id']] and local['id'] not in str(items)
    assert items[0]['target']['source_navigation']['scope'] == e.scope
    assert e.client.get(e.inbox, headers={**e.headers, 'X-Branch-ID': e.other_branch}, params={'domain': 'continuity_finding'}).status_code == 403
    denied = checked(e.client.get(e.inbox, headers=e.headers, params={'domain': 'pending_canon'}))
    assert denied['items'] == [] and denied['unavailable'][0]['domain'] == 'pending_canon'
    assert 'The door is sealed.' not in str(denied)
    role = DomainRoleAssignment('inbox-project-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    canon = checked(e.client.get(e.inbox, headers=e.headers, params={'domain': 'pending_canon'}))['items'][0]
    assert canon['authority_scope']['mode'] == 'project' and canon['target']['authority_scope']['mode'] == 'project'
    assert canon['scope'] == e.scope  # Containing Inbox context is not Canon's owner scope.
    assert e.client.post(e.inbox + f'/continuity_finding/{own["id"]}/approve', headers=e.viewer_headers, json={'expected_version': 1}).status_code == 403
    e.authorization.revoke_role(role.id, e.lead)
    assert checked(e.client.get(e.inbox, headers=e.headers, params={'domain': 'pending_canon'}))['items'] == []


def test_actual_main_inbox_withholds_loaded_findings_after_late_revoke(inbox_env, monkeypatch):
    e = inbox_env; scoped(e, monkeypatch)
    owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, 'branch_authority', owner.for_scope, raising=False)
    chapter = owner.for_scope(e.scope).create(e.nid, {'title': 'Scoped source', 'content': 'PRIVATE_SCOPE'})
    row = run(e, chapter=chapter); service = e.api.finding_review_service; original = service.list
    def revoke(*args):
        result = original(*args); e.authorization.revoke_role(e.role, e.lead); return result
    monkeypatch.setattr(service, 'list', revoke)
    response = e.client.get(e.inbox, headers=e.headers, params={'domain': 'continuity_finding'})
    assert response.status_code == 403 and row['description'] not in response.text


def test_actual_main_inbox_withholds_loaded_canon_after_late_project_revoke(inbox_env, monkeypatch):
    e = inbox_env; scoped(e, monkeypatch)
    role = DomainRoleAssignment('inbox-late-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    original = e.api.pending_canon_review_service.list
    def revoke(*args):
        result = original(*args); e.authorization.revoke_role(role.id, e.lead); return result
    monkeypatch.setattr(e.api.pending_canon_review_service, 'list', revoke)
    response = e.client.get(e.inbox, headers=e.headers, params={'domain': 'pending_canon'})
    data = checked(response)
    assert data['items'] == [] and data['unavailable'][0]['domain'] == 'pending_canon'
    assert 'The door is sealed.' not in response.text


def test_actual_main_inbox_withholds_loaded_finding_after_late_feature_disable(inbox_env, monkeypatch):
    e = inbox_env; row = run(e); original = e.api.finding_review_service.list
    def disable(*args):
        result = original(*args)
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'unified_review_inbox')
        return result
    monkeypatch.setattr(e.api.finding_review_service, 'list', disable)
    response = e.client.get(e.inbox, params={'domain': 'continuity_finding'})
    assert checked(response)['items'] == [] and row['description'] not in response.text
