"""Mounted aliases and real authorization; original generic STYLE APIs stay fenced."""
from copy import deepcopy
import pytest
from app.creative.service import CreativeService
from app.experimental.style_dna import StyleDNAService
from app.experimental.common import snapshot
from app.experimental.planning import digest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped

@pytest.fixture
def captured_creation():
    import app.api as api
    return api.creation_workbench_service

@pytest.fixture
def style_http(captured_creation, mounted, monkeypatch):
    e = mounted
    creative = CreativeService(e.store, e.novels, e.chapters)
    adapter = StyleDNAService(creative, e.creation,
        require_enabled=lambda: e.experimental.require_flag('style_dna_v2'),
        require_creative_enabled=lambda: e.experimental.require_flag('narrative_production_v2'))
    monkeypatch.setattr(e.creation, 'style_dna_service', adapter)
    # Capture before mounted replaces the global: original router closure keeps it.
    monkeypatch.setattr(captured_creation, 'style_dna_service', adapter)
    monkeypatch.setattr(e.experimental.style_analysis_service, 'creation', e.creation)
    return e


def payload():
    return {'title': 'Original STYLE', 'instructions': 'Concrete nouns.',
            'style_dna': {'global_rules': {'color': 'Amber', 'music_theme': 'Quiet strings'}}}


def test_http_original_save_approve_resolve_and_generic_restore(style_http):
    e = style_http
    p = checked(e.client.post(e.base + '/style-analysis/profiles', json=payload()), 201)
    approved = checked(e.client.post(e.base + '/style-analysis/profiles/' + p['id'] + '/approve', json={'expected_version': p['version']}))
    body = {'expected_version': approved['version'], 'expected_digest': digest(snapshot(approved)), 'target': {'level': 'GLOBAL'}}
    result = checked(e.client.post(e.base + '/style-analysis/profiles/' + p['id'] + '/resolve', json=body))
    assert result['effective']['color']['value'] == 'Amber'
    assert result['coverage'] == 'PARTIAL_AUTHORED_RULES_ONLY'
    assert 'writing_tone' in result['uncovered_dimensions']
    assert not result['model_called'] and not result['execution_ready']
    generic = e.base.split('/experimental')[0] + '/creation-records'
    changed = checked(e.client.put(generic + '/' + p['id'] + '?expected_version=2', json={**payload(), 'kind': 'STYLE', 'title': 'Revised'}))
    restored = checked(e.client.post(generic + '/' + p['id'] + '/restore', json={'expected_version': changed['version'], 'restore_version': 1}))
    assert restored['style_dna'] == p['style_dna'] and restored['status'] == 'DRAFT'
    assert checked(e.client.get(generic + '?kind=STYLE'))['items'][0]['id'] == p['id']


def test_http_flag_and_forged_epoch_denials(style_http, monkeypatch):
    e = style_http; p = checked(e.client.post(e.base + '/style-analysis/profiles', json=payload()), 201)
    generic = e.base.split('/experimental')[0] + '/creation-records'
    forged = {**payload(), 'kind': 'STYLE', 'style_dna_project_incarnation': 'file:forged'}
    assert e.client.post(generic, json=forged).status_code == 422
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
    assert e.client.post(e.base + '/style-analysis/profiles/' + p['id'] + '/resolve', json={'expected_version': 1, 'expected_digest': digest(snapshot(p)), 'target': {'level': 'GLOBAL'}}).status_code == 404
    assert checked(e.client.get(generic))['items'] == []
    assert e.client.post(generic + '/' + p['id'] + '/approve', json={'expected_version': 1}).status_code == 404


def test_http_branch_reader_and_owner_scope(style_http, monkeypatch):
    e = scoped(style_http, monkeypatch)
    # Original branch authorization determines whether content can be observed.
    unauthorized = e.client.post(e.base + '/style-analysis/profiles', headers=e.viewer_headers, json=payload())
    assert unauthorized.status_code == 403
    created = checked(e.client.post(e.base + '/style-analysis/profiles', headers=e.headers, json=payload()), 201)
    other_scope = e.creation.local_scope(e.nid)
    with pytest.raises(FileNotFoundError): e.creation.get_record(e.nid, other_scope, created['id'])


@pytest.mark.parametrize('loss', ['hidden', 'secret', 'deleted'])
def test_generic_endpoints_hide_current_and_historical_inaccessible_sources(style_http, monkeypatch, loss):
    e = style_http
    from app.source_privacy import content_digest
    local = {'level': 'CHAPTER', 'chapter': {'id': e.chapter['id'], 'version': e.chapter['version'], 'digest': content_digest(e.chapter)}}
    original = {**payload(), 'style_dna': {'global_rules': {'color': 'PUBLIC_AMBER'}, 'overrides': [
        {'target': local, 'rules': {'color': 'PRIVATE_STYLE_CANARY'}}]}}
    generic = e.base.split('/experimental')[0] + '/creation-records'
    p = checked(e.client.post(generic, json={**original, 'kind': 'STYLE'}), 201)
    # Current clean global rules still carry private source references in original history.
    p = checked(e.client.put(generic + '/' + p['id'] + '?expected_version=1', json={**payload(), 'kind': 'STYLE'}))
    if loss == 'deleted': e.chapters.delete(e.chapter['id'])
    else:
        get = e.chapters.get
        monkeypatch.setattr(e.chapters, 'get', lambda cid: {**get(cid), **({loss: True} if cid == e.chapter['id'] else {})})
    response = e.client.get(generic)
    assert checked(response)['items'] == []
    assert 'PRIVATE_STYLE_CANARY' not in response.text and e.chapter['id'] not in response.text
    for response in [e.client.put(generic + '/' + p['id'] + '?expected_version=999', json={**payload(), 'kind': 'STYLE'}),
                     e.client.post(generic + '/' + p['id'] + '/approve', json={'expected_version': 999}),
                     e.client.post(generic + '/' + p['id'] + '/restore', json={'expected_version': 999, 'restore_version': 1})]:
        assert response.status_code == 404, response.text
        assert 'PRIVATE_STYLE_CANARY' not in response.text and e.chapter['id'] not in response.text
    with pytest.raises(FileNotFoundError): e.creation.get_record(e.nid, e.scope, p['id'])


def test_generic_stale_repair_read_is_labelled_and_conflict_is_sanitized(style_http):
    e = style_http
    from app.source_privacy import content_digest
    generic = e.base.split('/experimental')[0] + '/creation-records'
    data = {**payload(), 'kind': 'STYLE', 'style_dna': {'global_rules': {'color': 'PRIVATE_STYLE_CANARY'}, 'overrides': [
        {'target': {'level': 'CHAPTER', 'chapter': {'id': e.chapter['id'], 'version': e.chapter['version'], 'digest': content_digest(e.chapter)}}, 'rules': {'color': 'Old override'}}]}}
    p = checked(e.client.post(generic, json=data), 201)
    e.chapters.save(e.chapter['id'], {'content': 'Updated current source.', 'version': e.chapter['version']})
    visible = checked(e.client.get(generic))['items'][0]
    assert visible['style_dna_resolution']['stale'] is True
    conflict = e.client.post(generic + '/' + p['id'] + '/approve', json={'expected_version': 999})
    assert conflict.status_code == 409 and 'PRIVATE_STYLE_CANARY' not in conflict.text and 'history' not in conflict.text
    assert e.client.post(generic + '/' + p['id'] + '/approve', json={'expected_version': 1}).status_code in (409, 422)


def test_bound_profile_legacy_analysis_is_explicitly_unsupported(style_http):
    e = style_http
    p = checked(e.client.post(e.base + '/style-analysis/profiles', json=payload()), 201)
    response = e.client.post(e.base + '/style-analysis/analyses', json={'style_id': p['id'], 'expected_style_version': p['version'],
        'language': 'en', 'samples': [{'chapter_id': e.chapter['id'], 'expected_version': e.chapter['version']}]})
    assert response.status_code == 422 and 'STYLE_DNA_LEGACY_ANALYSIS_NOT_SUPPORTED' in response.text
    response = e.client.post(e.base + '/style-analysis/profiles/' + p['id'] + '/preview', json={'expected_version': 999, 'operation': 'continue'})
    assert response.status_code == 422 and 'STYLE_DNA_EXECUTION_ADOPTION_NOT_SUPPORTED' in response.text
    assert 'Quiet strings' not in response.text and 'history' not in response.text


@pytest.mark.parametrize('surface', ['generic', 'style'])
def test_mounted_revocation_after_initial_authorization_prevents_commit(style_http, monkeypatch, surface):
    e = scoped(style_http, monkeypatch)
    if e.backend == 'postgres':
        _postgres_role_revocation_serializes_after_write(e, monkeypatch, surface)
        return
    from app.services.creation_workbench_service import CreationWorkbenchService
    path = e.creation.store._path('creation_records')
    before = path.read_bytes() if path.exists() else None
    original = CreationWorkbenchService._references
    revoked = []
    def revoke_before_write(self, nid, scope, body):
        result = original(self, nid, scope, body)
        if body.style_dna is not None and not revoked:
            e.authorization.revoke_role(e.role, e.lead)
            revoked.append(True)
        return result
    monkeypatch.setattr(CreationWorkbenchService, '_references', revoke_before_write)
    uri = e.base.split('/experimental')[0] + '/creation-records' if surface == 'generic' else e.base + '/style-analysis/profiles'
    response = e.client.post(uri, headers=e.headers, json={**payload(), **({'kind': 'STYLE'} if surface == 'generic' else {})})
    assert revoked and response.status_code == 403, response.text
    assert (path.read_bytes() if path.exists() else None) == before


def test_missing_outer_authority_injection_fails_closed_only_for_multimodal(style_http):
    e = style_http
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.creation_workbench_api import create_workbench_router
    from app.experimental.style_analysis_api import create_style_analysis_router
    app = FastAPI()
    app.include_router(create_workbench_router(e.creation, e.api._workbench_authorize))
    app.include_router(create_style_analysis_router(e.experimental.style_analysis_service, e.experimental.authorize, e.experimental.require_flag))
    with TestClient(app) as client:
        generic = f'/novels/{e.nid}/creation-records'
        assert client.post(generic, json={**payload(), 'kind': 'STYLE'}).status_code == 409
        assert client.post(generic, json={'kind': 'STYLE', 'title': 'Legacy allowed', 'instructions': 'Plain.'}).status_code == 201
        assert client.post(f'/novels/{e.nid}/experimental/style-analysis/profiles', json=payload()).status_code == 409


def test_generic_list_late_revocation_suppresses_bound_payload(style_http, monkeypatch):
    e = scoped(style_http, monkeypatch)
    generic = e.base.split('/experimental')[0] + '/creation-records'
    checked(e.client.post(generic, headers=e.headers, json={**payload(), 'kind': 'STYLE'}), 201)
    if e.backend == 'postgres':
        _postgres_session_revocation_serializes_after_read(e, monkeypatch, generic)
        return
    from app.services.creation_workbench_service import CreationWorkbenchService
    original = CreationWorkbenchService.list_records
    def revoke_after_read(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        e.sessions.revoke(e.lead)
        return result
    monkeypatch.setattr(CreationWorkbenchService, 'list_records', revoke_after_read)
    response = e.client.get(generic, headers=e.headers)
    assert response.status_code in (401, 403), response.text
    assert 'Quiet strings' not in response.text and 'style_dna' not in response.text


def _postgres_role_revocation_serializes_after_write(e, monkeypatch, surface):
    """A second real PG transaction must wait for the original authority lease.

    Unlike File's same-thread reentrant fault injection, synchronous PG revoke
    would wait on the caller's own advisory lock on another connection forever.
    The first operation is authorized until commit; subsequent requests must fail.
    """
    from threading import Event, Thread, current_thread
    from app.services.creation_workbench_service import CreationWorkbenchService
    repository = e.authorization.repository
    attempted, finished = Event(), Event()
    errors, outcomes, started = [], [], []
    original_lock = repository._lock_workspace
    original_references = CreationWorkbenchService._references

    def revoke():
        try:
            outcomes.append(e.authorization.revoke_role(e.role, e.lead))
        except BaseException as exc:
            errors.append(type(exc).__name__ + ': ' + str(exc))
        finally:
            finished.set()
    worker = Thread(target=revoke, name='style-dna-pg-role-revoker', daemon=True)

    def observed_lock(connection, workspace_id):
        if current_thread() is worker:
            # Transaction-local timeout prevents a failed probe stranding PG.
            connection.execute("SELECT set_config('lock_timeout', '5000', true)")
            attempted.set()
        return original_lock(connection, workspace_id)
    monkeypatch.setattr(type(repository), '_lock_workspace', staticmethod(observed_lock))

    def attempt_during_write(self, nid, scope, body):
        result = original_references(self, nid, scope, body)
        if body.style_dna is not None and not started:
            started.append(True)
            worker.start()
            assert attempted.wait(3), 'PG revoker did not reach the original authorization lock'
            assert not finished.wait(.15), 'PG revocation crossed the held write authority lease'
        return result
    monkeypatch.setattr(CreationWorkbenchService, '_references', attempt_during_write)
    generic = e.base.split('/experimental')[0] + '/creation-records'
    uri = generic if surface == 'generic' else e.base + '/style-analysis/profiles'
    body = {**payload(), **({'kind': 'STYLE'} if surface == 'generic' else {})}
    try:
        response = e.client.post(uri, headers=e.headers, json=body)
    finally:
        if worker.ident is not None:
            worker.join(7)
    assert started and attempted.is_set()
    assert finished.is_set() and not worker.is_alive(), 'PG revoker did not finish after authority lease release'
    assert not errors, errors
    saved = checked(response, 201)
    assert outcomes and outcomes[0]['id'] == e.role
    assert not any(row['id'] == e.role for row in repository.list_role_assignments(e.lead))
    rows = [row for row in e.creation._rows('creation_records') if row['novel_id'] == e.nid and row['scope'] == e.scope]
    assert len(rows) == 1 and rows[0]['id'] == saved['id'] and rows[0]['version'] == 1
    path = e.creation.store._path('creation_records')
    after_authorized_commit = path.read_bytes()
    denied_write = e.client.post(uri, headers=e.headers, json=body)
    denied_read = e.client.get(generic, headers=e.headers)
    assert denied_write.status_code == 403 and denied_read.status_code == 403
    assert 'Quiet strings' not in denied_read.text and 'style_dna' not in denied_read.text
    assert path.read_bytes() == after_authorized_commit


def _postgres_session_revocation_serializes_after_read(e, monkeypatch, generic):
    """The original binding lease owns the read; revocation takes effect next."""
    from threading import Event, Thread
    from app.services.creation_workbench_service import CreationWorkbenchService
    attempted, finished = Event(), Event()
    errors, started = [], []
    original_list = CreationWorkbenchService.list_records
    path = e.creation.store._path('creation_records')
    before = path.read_bytes()
    def revoke():
        attempted.set()
        try:
            e.sessions.revoke(e.lead)
        except BaseException as exc:
            errors.append(type(exc).__name__ + ': ' + str(exc))
        finally:
            finished.set()
    worker = Thread(target=revoke, name='style-dna-pg-session-revoker', daemon=True)
    def attempt_during_read(self, *args, **kwargs):
        result = original_list(self, *args, **kwargs)
        if not started:
            started.append(True)
            worker.start()
            assert attempted.wait(3), 'Session revoker did not attempt the original binding owner'
            assert not finished.wait(.15), 'Session revocation crossed the held read authority lease'
        return result
    monkeypatch.setattr(CreationWorkbenchService, 'list_records', attempt_during_read)
    try:
        response = e.client.get(generic, headers=e.headers)
    finally:
        if worker.ident is not None:
            worker.join(7)
    assert started and attempted.is_set()
    assert finished.is_set() and not worker.is_alive(), 'Session revoker did not finish after read lease release'
    assert not errors, errors
    assert len(checked(response)['items']) == 1
    with pytest.raises(KeyError):
        e.sessions.resolve(e.lead)
    denied = e.client.get(generic, headers=e.headers)
    assert denied.status_code in (401, 403), denied.text
    assert 'Quiet strings' not in denied.text and 'style_dna' not in denied.text
    assert path.read_bytes() == before


@pytest.mark.parametrize('restriction', ['hidden', 'secret'])
def test_style_catalog_exact_chapter_pins_exclude_private_sources(style_http, monkeypatch, restriction):
    from app.source_privacy import content_digest
    e = style_http
    result = checked(e.client.get(e.base + '/style-analysis/catalog'))
    source = next(row for row in result['chapters'] if row['id'] == e.chapter['id'])
    assert source['version'] == e.chapter['version']
    assert source['content_digest'] == content_digest(e.chapter)
    assert 'content' not in source
    target = {'level': 'CHAPTER', 'chapter': {'id': source['id'], 'version': source['version'], 'digest': source['content_digest']}}
    body = {**payload(), 'style_dna': {'global_rules': {'color': 'Amber'},
        'overrides': [{'target': target, 'rules': {'color': 'Blue'}}]}}
    profile = checked(e.client.post(e.base + '/style-analysis/profiles', json=body), 201)
    checked(e.client.post(e.base + '/style-analysis/profiles/' + profile['id'] + '/approve', json={'expected_version': profile['version']}))
    current = next(row for row in checked(e.client.get(e.base + '/style-analysis/catalog'))['styles'] if row['id'] == profile['id'])
    resolved = checked(e.client.post(e.base + '/style-analysis/profiles/' + profile['id'] + '/resolve', json={
        'expected_version': current['version'], 'expected_digest': current['style_dna_resolution']['source_digest'], 'target': target}))
    assert resolved['effective']['color']['value'] == 'Blue'
    assert resolved['effective']['color']['level'] == 'CHAPTER'
    original = e.chapters.get
    monkeypatch.setattr(e.chapters, 'get', lambda cid: {
        **original(cid), **({restriction: True} if cid == e.chapter['id'] else {})})
    result = checked(e.client.get(e.base + '/style-analysis/catalog'))
    assert all(row['id'] != e.chapter['id'] for row in result['chapters'])
