"""Mounted existing Write / Generation and new branch API with real permissions."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
import time
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.application.audit_service import AuditService
from app.application.collaboration_service import CollaborationApplicationService
from app.application.persistence import create_atomic_chapter_audit_port
from app.authorization import AuthorizationScope, DomainRole, DomainRoleAssignment, ModalityDomain, ScopeKind
from app.experimental.branch_manuscript_composition import mount_branch_manuscript
from app.experimental.flags import RUNTIME_FLAGS, require_flag
from app.experimental.ux import ReadContext
from app.services.branch_manuscript_service import BranchManuscriptService
from app.services.generation_service import GenerationService
from test_r3_mounted_contracts import mounted, prefix, scoped, checked
from test_surface_branch_manuscript import doc


@pytest.fixture
def branch_env(mounted, monkeypatch):
    e = scoped(mounted, monkeypatch)
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(RUNTIME_FLAGS))
    e.owner = BranchManuscriptService(e.store, e.novels, e.chapters, e.scopes)
    monkeypatch.setattr(e.chapters, 'branch_authority', e.owner.for_scope, raising=False)
    monkeypatch.setattr(e.novels, 'branch_authority', e.owner.for_scope, raising=False)
    e.application = CollaborationApplicationService(e.membership,
        create_atomic_chapter_audit_port(e.bundle.chapters, e.bundle.authorization), AuditService(e.bundle.authorization))
    e.application.branch_manuscripts = e.owner
    monkeypatch.setattr(e.api, 'collaboration_application_service', e.application)
    monkeypatch.setattr(e.api, 'audit_service', AuditService(e.bundle.authorization))
    app = FastAPI()
    mount_branch_manuscript(app, e.api, e.owner, require_flag, e.experimental.require_inspection_host_session)
    e.branch_client = TestClient(app); e.branch_base = f'/novels/{e.nid}/experimental/branch-manuscript'
    e.ctx = ReadContext(e.nid, e.scope, e.lead, e.lead, e.branch)
    yield e
    e.branch_client.close()


def create(e):
    return checked(e.branch_client.post(e.branch_base + '/chapters', headers=e.headers,
                                        json={'title': 'Real branch', 'document': doc('Branch only')}), 201)


def test_branch_api_permissions_flag_cas_history_and_existing_write_routes(branch_env, monkeypatch):
    e = branch_env; base = e.branch_base; client = e.branch_client
    assert client.get(base + '/catalog').status_code == 401
    assert checked(client.get(base + '/catalog', headers=e.headers))['initialized'] is False
    assert checked(client.get(base + '/chapters', headers=e.headers))['items'] == []
    row = create(e)
    assert checked(e.client.get(e.prefix + f"/chapters/{row['id']}", headers=e.headers))['document'] == row['document']
    assert e.client.get(e.prefix + f"/chapters/{e.chapter['id']}", headers=e.headers).status_code == 404
    assert client.post(base + '/chapters', headers=e.viewer_headers, json={'title': 'deny'}).status_code == 403
    response = checked(e.client.put(e.prefix + f"/chapters/{row['id']}", headers=e.headers,
                                    json={'document': doc('Edited in original Write'), 'version': 1}))
    assert response['version'] == 2 and e.chapters.get(e.chapter['id']) == e.chapter
    conflict = client.put(base + f"/chapters/{row['id']}", headers=e.headers,
                          json={'document': doc('Stale'), 'expected_version': 1, 'operation_id': 'stale'})
    assert conflict.status_code == 409 and 'document' not in conflict.text and 'Branch only' not in conflict.text
    history = checked(client.get(base + f"/chapters/{row['id']}/history", headers=e.headers))['items']
    assert history[0]['version'] == 1
    restored = checked(client.post(base + f"/chapters/{row['id']}/restore", headers=e.headers,
                                    json={'version': 1, 'expected_version': 2}))
    assert restored['version'] == 3 and restored['document'] == row['document']
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert client.get(base + '/chapters', headers=e.headers).status_code == 404
    assert e.client.get(e.prefix + f"/chapters/{row['id']}", headers=e.headers).status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ','.join(RUNTIME_FLAGS))
    e.authorization.revoke_role(e.role, e.lead)
    assert client.get(base + '/catalog', headers=e.headers).status_code == 403
    assert e.client.get(e.prefix + f"/chapters/{row['id']}", headers=e.headers).status_code == 403


def test_branch_role_cannot_import_or_merge_mainline_without_project_authority(branch_env):
    e = branch_env; request = {'chapter_ids': [e.chapter['id']]}
    assert e.branch_client.post(e.branch_base + '/forks/preview', headers=e.headers, json=request).status_code == 403
    role = DomainRoleAssignment('project-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
                                AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    preview = checked(e.branch_client.post(e.branch_base + '/forks/preview', headers=e.headers, json=request))
    applied = checked(e.branch_client.post(e.branch_base + f"/forks/{preview['id']}/apply", headers=e.headers,
        json={'expected_version': 1, 'preview_digest': preview['preview_digest'], 'confirmed': True}))
    cid = applied['id_map'][e.chapter['id']]
    assert cid != e.chapter['id'] and e.owner.read(e.ctx, cid)['document'] == e.chapter['document']
    assert e.owner.read(e.ctx, cid)['version'] == 1
    assert checked(e.branch_client.get(e.branch_base + '/chapters', headers={**e.headers, 'X-Branch-ID': e.other_branch}))['items'] == []
    e.authorization.revoke_role(role.id, e.lead)
    assert e.branch_client.get(e.branch_base + '/chapters', headers={**e.headers, 'X-Branch-ID': e.other_branch}).status_code == 403
    assert e.branch_client.get(e.branch_base + '/sources', headers=e.headers).status_code == 403
    assert checked(e.branch_client.get(e.branch_base + '/records', headers=e.headers))['forks'] == []


def test_existing_job_manager_generates_branch_content_review_and_durable_restart(branch_env, monkeypatch):
    import app.jobs as jobs_module
    import app.dependencies as dependencies
    from app.jobs import JobManager, GenerationStateConflict
    from app.model_runtime import GenerationEvent, TextGenerationResponse
    from app.router import Route
    e = branch_env; chapter = create(e); captured = []
    monkeypatch.setattr(dependencies, 'membership_authorization_service', e.membership)
    class Node:
        def stream(self, value):
            value.request.dispatch_guard(); captured.append(deepcopy(value.request.context))
            assert 'Branch only' in value.request.prompt and 'Alice said' not in value.request.prompt
            yield GenerationEvent('generation.delta', None, delta='Synthetic branch output')
            yield GenerationEvent('generation.completed', None, response=TextGenerationResponse('Synthetic branch output', 'stop', 'fixture', 'model'))
    runtime = SimpleNamespace(is_remote_text_provider=lambda _: False,
        router=lambda *_: SimpleNamespace(routes={'writer': [Route('fixture', 'model')], 'editor': [Route('fixture', 'model')]}),
        packaged_author_route_ready=lambda _: True, prepare_text_route=lambda *_: Node())
    monkeypatch.setattr(jobs_module, 'runtime', runtime)
    monkeypatch.setattr(jobs_module, 'runtime_log', SimpleNamespace(write=lambda **_: None))
    monkeypatch.setattr(jobs_module, 'deterministic_review', lambda *_: [])
    manager = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                         contexts=SimpleNamespace(), canon=e.canon, memory_extractor=SimpleNamespace(), snapshot_required=True,
                         collaboration_updates=e.application)
    monkeypatch.setattr(e.api, 'jobs', manager)
    response = checked(e.client.post(e.prefix + '/generate/polish', headers=e.headers,
        json={'novel_id': e.nid, 'chapter_id': chapter['id'], 'profile': 'LOCAL_ONLY', 'provider_id': 'fixture', 'model_id': 'model'}), 202)
    deadline = time.monotonic() + 5
    while manager.get(response['job_id']).status not in {'COMPLETED', 'FAILED'} and time.monotonic() < deadline: time.sleep(.01)
    job = manager.get(response['job_id'])
    assert job.status == 'COMPLETED', job.error
    assert captured[0]['branch_id'] == e.branch and job.context_snapshot_id
    assert manager.persistence.get(job.id)['chapter_id'] == chapter['id']
    accepted = manager.accept(job.id, actor=e.sessions.resolve(e.lead), scope=AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch))
    assert accepted['chapter']['version'] == 2 and accepted['pending_canon'] is None
    assert e.owner.read(e.ctx, chapter['id'])['content'].strip() == 'Synthetic branch output'
    assert e.chapters.get(e.chapter['id']) == e.chapter and e.canon.list_pending(e.nid) == []
    with pytest.raises(GenerationStateConflict): manager.reject(job.id)
    restarted = JobManager(generations=GenerationService(e.bundle.generations), chapters=e.chapters,
                           contexts=SimpleNamespace(), canon=e.canon, snapshot_required=True, collaboration_updates=e.application)
    assert restarted.get(job.id).status == 'ACCEPTED'


def test_branch_two_clients_race_real_http_cas_without_cross_scope_writes(branch_env):
    from concurrent.futures import ThreadPoolExecutor
    e = branch_env; chapter = create(e)
    role = DomainRoleAssignment('second-writer-' + uuid4().hex, e.viewer, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.BRANCH, e.workspace, e.nid, e.storyline, e.branch), e.lead)
    e.authorization.assign_role(role)
    assert checked(e.branch_client.get(e.branch_base + f"/chapters/{chapter['id']}", headers=e.viewer_headers))['version'] == 1
    def write(i):
        return e.branch_client.put(e.branch_base + f"/chapters/{chapter['id']}",
            headers=e.headers if i == 1 else e.viewer_headers,
            json={'document': doc(f'Client {i}'), 'expected_version': 1, 'operation_id': f'client-{i}'})
    with ThreadPoolExecutor(max_workers=2) as executor: results = list(executor.map(write, (1, 2)))
    assert sorted(row.status_code for row in results) == [200, 409]
    current = e.owner.read(e.ctx, chapter['id']); assert current['version'] == 2
    assert e.chapters.get(e.chapter['id']) == e.chapter
    assert len(e.owner.repository(e.scope).history(chapter['id'])) == 1


def test_original_comment_revocation_after_real_branch_source_read(branch_env, monkeypatch):
    from app.services.creation_workbench_service import CommentIn
    from app.identity import IdentityStatus
    from fastapi import HTTPException
    e = branch_env; chapter = create(e); calls = []
    original = e.creation._anchor
    def revoke_after_read(*args):
        result = original(*args); calls.append(result)
        e.identity.set_membership_status(e.lead, e.workspace, IdentityStatus.INACTIVE)
        return result
    monkeypatch.setattr(e.creation, '_anchor', revoke_after_read)
    with pytest.raises(HTTPException) as error:
        e.creation.create_comment(e.nid, e.scope, e.lead,
            CommentIn(chapter_id=chapter['id'], chapter_version=1, text='Must not persist'),
            reauthorize=lambda: e.api._workbench_authorize(e.nid, e.lead, e.branch, 'domain.write'))
    assert error.value.status_code == 403 and len(calls) == 1
    assert e.creation.list_comments(e.nid, e.scope)['items'] == []


def test_production_router_mount_and_original_collaboration_catalog_never_fall_back(branch_env, monkeypatch):
    import app.dependencies as dependencies
    e = branch_env; owner = e.experimental.branch_manuscript_service
    for name in ('store', 'novels', 'mainline', 'scopes'):
        monkeypatch.setattr(owner, name, getattr(e.owner, name))
    read = dependencies.collaboration_read_service
    for name, value in {'sessions': e.sessions, 'membership_authorization': e.membership,
                        'identity': e.identity, 'authorization': e.authorization, 'scopes': e.scopes,
                        'chapters': e.bundle.chapters, 'generations': e.bundle.generations, 'novels': e.bundle.novels,
                        'branch_manuscripts': e.owner, 'collaboration_application': e.application}.items():
        monkeypatch.setattr(read, name, value)
    path = e.base + '/branch-manuscript'
    assert checked(e.client.get(path + '/catalog', headers=e.headers))['initialized'] is False
    collab = e.prefix + f'/collaboration/workspaces/{e.workspace}/projects/{e.nid}/storylines/{e.storyline}/branches/{e.branch}/chapters'
    assert checked(e.client.get(collab, headers=e.headers))['items'] == []
    chapter = checked(e.client.post(collab, headers=e.headers, json={'title': 'Original Write create'}), 201)
    assert chapter['id'].startswith(e.nid + ':~b')
    assert [item['id'] for item in checked(e.client.get(collab, headers=e.headers))['items']] == [chapter['id']]
    assert checked(e.client.get(path + '/catalog', headers=e.headers))['initialized'] is True
    assert e.chapters.get(e.chapter['id']) == e.chapter
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert e.client.get(collab, headers=e.headers).status_code == 404
    assert e.client.get(e.prefix + f"/chapters/{e.chapter['id']}", headers=e.headers).status_code == 404
    assert e.client.post(collab, headers=e.headers, json={'title': 'Disabled'}).status_code == 404
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_default_job_manager_keeps_registered_source_authority(monkeypatch):
    import app.jobs as jobs_module
    assert callable(jobs_module.chapter_service.branch_authority)
    manager = jobs_module.JobManager()
    assert manager.chapters is jobs_module.chapter_service
    assert manager.chapters.branch_authority is jobs_module.chapter_service.branch_authority


def test_registered_branch_export_never_captures_mainline_or_unscoped_story_records(branch_env, monkeypatch):
    e = branch_env; chapter = create(e)
    context = e.api._export_request_context(e.nid, e.branch, e.lead)
    # Branch-labelled data in a PROJECT store is still not branch-owned.
    monkeypatch.setattr(e.novels, 'data_set', lambda *_: pytest.fail('project dataset read'))
    monkeypatch.setattr(e.novels, 'outline', lambda *_: pytest.fail('project outline read'))
    snapshot = e.novels.export_snapshot(e.nid, format='json', permission_context=context)
    assert snapshot['manuscript_authority'] == 'BRANCH_MANUSCRIPT_V1' and snapshot['manuscript_scope'] == e.scope
    assert [row['id'] for row in snapshot['source']['chapters']] == [chapter['id']]
    assert not snapshot['source']['datasets']['characters'] and not snapshot['source']['datasets']['outline']
    assert snapshot['source_versions']['chapters'][0]['authority'] == 'BRANCH_MANUSCRIPT_V1'
    assert snapshot['source_versions']['chapters'][0]['scope'] == e.scope
    exported = checked(e.client.get(e.prefix + f'/novels/{e.nid}/export?format=json', headers=e.headers))
    assert 'Branch only' in exported['content'] and 'Alice said' not in exported['content']


def test_branch_export_provenance_and_historical_project_artifacts_reauthorize_without_rewriting(branch_env, monkeypatch):
    from hashlib import sha256
    e = branch_env; chapter = create(e)
    monkeypatch.setattr(e.exports, 'snapshotter', e.novels.export_snapshot)
    monkeypatch.setattr(e.exports, '_submit', lambda _: None)
    context = e.api._export_request_context(e.nid, e.branch, e.lead)
    # Simulate a retained pre-branch-authority artifact containing mainline
    # prose, with the old branch permission label. Do not relabel its source.
    historical = e.exports.create(e.nid, 'json')
    e.exports._run(historical['id'])
    retained = e.exports._read()
    retained[historical['id']]['permission_context'] = context
    retained[historical['id']]['snapshot'].pop('manuscript_authority')
    retained[historical['id']]['snapshot'].pop('manuscript_scope')
    e.exports._write(retained)
    original = deepcopy(e.exports.get(historical['id']))
    artifact_digest = sha256(e.exports.download(historical['id'])['content']).hexdigest()
    path = e.prefix + f"/exports/{historical['id']}"
    for method, suffix in [('get', ''), ('get', '/download'), ('post', '/retry'), ('post', '/cancel')]:
        assert getattr(e.client, method)(path + suffix, headers=e.headers).status_code == 404
    hidden = checked(e.client.get(e.prefix + f'/exports?novel_id={e.nid}&limit=1', headers=e.headers))
    assert hidden['items'] == [] and hidden['next_offset'] is None
    project_role = DomainRoleAssignment('project-export-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
                                       AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(project_role)
    assert e.client.get(path + '/download', headers=e.headers).status_code == 200
    assert [row['id'] for row in checked(e.client.get(e.prefix + f'/exports?novel_id={e.nid}', headers=e.headers))['items']] == [historical['id']]
    e.authorization.revoke_role(project_role.id, e.lead)
    assert e.client.get(path + '/download', headers=e.headers).status_code == 404
    assert e.exports.get(historical['id']) == original
    assert sha256(e.exports.download(historical['id'])['content']).hexdigest() == artifact_digest
    # New exact branch snapshots remain immutable after live source edits,
    # and require only their actual branch grant.
    created = checked(e.client.post(e.prefix + f'/exports?novel_id={e.nid}', headers=e.headers,
                                    json={'format': 'json'}), 202)
    visible = checked(e.client.get(e.prefix + f'/exports?novel_id={e.nid}&limit=1', headers=e.headers))
    assert [row['id'] for row in visible['items']] == [created['id']] and visible['next_offset'] is None
    e.owner.save(e.ctx, chapter['id'], doc('Later branch'), 1)
    e.exports._run(created['id'])
    download = e.client.get(e.prefix + f"/exports/{created['id']}/download", headers=e.headers)
    assert download.status_code == 200 and 'Branch only' in download.text and 'Later branch' not in download.text and 'Alice said' not in download.text
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert e.client.get(e.prefix + f"/exports/{created['id']}/download", headers=e.headers).status_code == 404


@pytest.mark.parametrize('corruption', ['owner', 'scope', 'document_digest', 'project_dataset'])
def test_branch_export_labels_do_not_override_source_ownership(branch_env, monkeypatch, corruption):
    e = branch_env; create(e)
    monkeypatch.setattr(e.exports, 'snapshotter', e.novels.export_snapshot)
    monkeypatch.setattr(e.exports, '_submit', lambda _: None)
    context = e.api._export_request_context(e.nid, e.branch, e.lead)
    job = e.exports.create(e.nid, 'json', permission_context=context)
    state = e.exports._read(); snapshot = state[job['id']]['snapshot']; row = snapshot['source']['chapters'][0]
    if corruption == 'owner': row['authority'] = 'PROJECT_MANUSCRIPT_V1'
    elif corruption == 'scope': row['scope']['branch_id'] = e.other_branch
    elif corruption == 'document_digest': row['document_digest'] = '0' * 64
    else: snapshot['source']['datasets']['characters'] = [{'id': 'project-only', 'branch_id': e.branch}]
    e.exports._write(state)
    assert e.client.get(e.prefix + f"/exports/{job['id']}", headers=e.headers).status_code == 404
    assert e.client.get(e.prefix + f"/exports/{job['id']}/download", headers=e.headers).status_code == 404


def test_branch_export_list_rechecks_permission_after_owner_filter(branch_env, monkeypatch):
    e = branch_env; create(e)
    monkeypatch.setattr(e.exports, 'snapshotter', e.novels.export_snapshot)
    monkeypatch.setattr(e.exports, '_submit', lambda _: None)
    context = e.api._export_request_context(e.nid, e.branch, e.lead)
    e.exports.create(e.nid, 'json', permission_context=context)
    original = e.exports.list
    def revoke_after_list(*args, **kwargs):
        result = original(*args, **kwargs)
        e.authorization.revoke_role(e.role, e.lead)
        return result
    monkeypatch.setattr(e.exports, 'list', revoke_after_list)
    response = e.client.get(e.prefix + f'/exports?novel_id={e.nid}', headers=e.headers)
    assert response.status_code == 403 and 'source_versions' not in response.text


def test_branch_shared_inbox_is_read_only_with_exact_original_navigation_and_permissions(branch_env, monkeypatch):
    e = branch_env
    owner = e.experimental.branch_manuscript_service
    for name in ('store', 'novels', 'mainline', 'scopes'):
        monkeypatch.setattr(owner, name, getattr(e.owner, name))
    project_role = DomainRoleAssignment('inbox-project-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
                                       AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(project_role)
    preview = checked(e.branch_client.post(e.branch_base + '/forks/preview', headers=e.headers,
                                           json={'chapter_ids': [e.chapter['id']]}))
    path = e.base + '/review-inbox'
    result = checked(e.client.get(path + '?domain=branch_manuscript', headers=e.headers))
    assert [row['id'] for row in result['items']] == [preview['id']]
    item = result['items'][0]
    assert item['allowed_actions'] == [] and item['batch_actions'] == [] and item['batch_safe'] is False
    assert item['review_mode'] == 'ORIGINAL_DOMAIN_REQUIRED'
    target = item['target']
    assert target['panel'] == 'BranchManuscriptPanel' and target['feature'] == 'branch_manuscript_v1'
    assert target['id'] == preview['id'] and target['version'] == 1 and target['scope'] == e.scope
    assert target['api']['cancel'] == e.branch_base + f"/fork/{preview['id']}/cancel"
    assert target['api']['cancel_body'] == {'expected_version': 1}
    assert target['api']['cancel_permissions'] == ['domain.read', 'domain.review']
    assert target['api']['scope_headers'] == {'X-Branch-Id': e.branch} and target['api']['session_required']
    assert 'token' not in str(target).lower()
    for action in ('approve', 'reject', 'reopen', 'cancel'):
        denied = e.client.post(path + f"/branch_manuscript/{preview['id']}/{action}", headers=e.headers,
                               json={'expected_version': 1})
        assert denied.status_code == 422
    batch = e.client.post(path + '/batch', headers=e.headers,
        json={'items': [{'domain': 'branch_manuscript', 'id': preview['id'], 'action': 'reject', 'expected_version': 1}]})
    assert batch.status_code == 422 and e.owner.records(e.ctx)['forks'][0]['status'] == 'REVIEW'
    # An owner role on the target branch cannot disclose revoked counterpart
    # project sources through the shared projection.
    e.authorization.revoke_role(project_role.id, e.lead)
    hidden = checked(e.client.get(path + '?domain=branch_manuscript', headers=e.headers))
    assert hidden['items'] == [] and hidden['total'] == 0
    # Cancel remains solely the original versioned endpoint and original grants.
    assert e.branch_client.post(target['api']['cancel'], headers=e.viewer_headers, json={'expected_version': 1}).status_code == 403
    cancelled = checked(e.branch_client.post(target['api']['cancel'], headers=e.headers, json={'expected_version': 1}))
    assert cancelled['status'] == 'CANCELLED' and cancelled['version'] == 2
    assert e.chapters.get(e.chapter['id']) == e.chapter


def test_historical_branch_label_is_not_export_manuscript_proof(branch_env, monkeypatch):
    from fastapi import HTTPException
    e = branch_env
    context = e.api._export_request_context(e.nid, e.branch, e.lead)
    historical = {'id': 'historical-synthetic', 'novel_id': e.nid, 'permission_context': context,
                  'snapshot': {'source': {'chapters': [e.chapter]}}}
    monkeypatch.setattr(e.api.export_job_service, 'get', lambda _: deepcopy(historical))
    with pytest.raises(HTTPException) as denied: e.api._authorize_export_job(historical['id'], e.lead, 'domain.read', e.branch)
    assert denied.value.status_code == 404
    role = DomainRoleAssignment('historical-project-' + uuid4().hex, e.lead, DomainRole.DOMAIN_LEAD, ModalityDomain.NOVEL,
        AuthorizationScope(ScopeKind.PROJECT, e.workspace, e.nid), e.lead)
    e.authorization.assign_role(role)
    assert e.api._authorize_export_job(historical['id'], e.lead, 'domain.read', e.branch)['id'] == historical['id']
