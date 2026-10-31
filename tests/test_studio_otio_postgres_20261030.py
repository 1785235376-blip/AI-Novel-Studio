"""Real PostgreSQL scope persistence + File media, synthetic HTTP OTIO acceptance.

An explicitly selected loopback test database is required. This does not change
or disable the default environment-clearing fixture or touch a production DB.
"""
from copy import deepcopy
import os
import re
from types import SimpleNamespace
from urllib.parse import urlsplit
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from test_studio_otio_runtime_20261029 import case, base, call
import test_studio_otio_external_native_20261030 as native_checks

pytestmark = pytest.mark.postgres_backend_only
TEST_URL = os.environ.get('TEST_POSTGRES_DATABASE_URL', '')


def checked_url():
    parsed = urlsplit(TEST_URL)
    if (parsed.scheme not in {'postgresql', 'postgresql+psycopg'}
            or parsed.hostname not in {'127.0.0.1', 'localhost', '::1'}
            or not re.fullmatch(r'/ai_novel_studio_e2e_[a-z0-9_-]{1,42}', parsed.path)
            or parsed.query or parsed.fragment):
        pytest.fail('Explicit isolated loopback ai_novel_studio_e2e_ database required')
    return TEST_URL


@pytest.fixture
def rig(tmp_path, monkeypatch):
    from app import api, main
    from app.config import Settings, settings
    from app.experimental import api as experimental_api
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.authorization_service import AuthorizationService
    from app.services.collaboration_scope_service import CollaborationScopeService
    from app.services.identity_service import IdentityService
    from app.services.membership_authorization_service import MembershipAuthorizationService
    from app.trusted_sessions import TrustedSessionResolver
    from test_studio_canvas_audio_return import services

    url = checked_url()
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'narrative_production_v2,asset_lineage_v2')
    monkeypatch.delenv('V1_ACCEPTANCE_MODE', raising=False)
    object.__setattr__(settings, 'enable_collaboration_runtime', False)
    object.__setattr__(settings, 'enable_packaged_runtime', False)
    bundle = create_repository_bundle(Settings(storage_backend='postgres', database_url=url,
        novel_data=tmp_path, enable_cloud=False, mock_provider=True), data_root=tmp_path)
    assert bundle.novels.database.engine.dialect.name == 'postgresql'
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    workspace = services(tmp_path, 'postgres', url, novels, chapters)
    assert workspace.store.backend == 'postgres'
    mounted = experimental_api.independent_workspace_service
    for name, value in workspace.__dict__.items():
        monkeypatch.setattr(mounted, name, value)
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    identities = IdentityService(bundle.identity, scopes)
    grants = AuthorizationService(bundle.authorization, scopes)
    membership = MembershipAuthorizationService(identities, grants)
    sessions = TrustedSessionResolver()
    for name, value in (('novel_service', novels), ('collaboration_scope_service', scopes),
                        ('membership_authorization_service', membership),
                        ('trusted_session_resolver', sessions)):
        monkeypatch.setattr(api, name, value)
    monkeypatch.setattr(main, 'trusted_session_resolver', sessions)
    nid = novels.create({'id': 'pg-otio-' + uuid4().hex, 'title': 'Synthetic PG OTIO'})['id']
    scope = {'mode': 'local', 'novel_id': nid}
    assert workspace.store.incarnation(nid).startswith('postgres:')
    client = TestClient(main.app)
    yield SimpleNamespace(client=client, nid=nid, scope=scope, workspace=workspace,
        assets=workspace.assets, novels=novels, chapters=chapters, scopes=scopes,
        identities=identities, grants=grants, sessions=sessions, root=tmp_path,
        settings=settings, url=url, bundle=bundle)
    client.close()
    with workspace.store._connect() as connection:
        connection.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))
    novels.delete(nid)
    bundle.novels.database.engine.dispose()


def persisted(e):
    with psycopg.connect(e.rig.url.replace('postgresql+psycopg://', 'postgresql://')) as connection:
        row = connection.execute(
            'SELECT document, revision FROM experimental_scope_documents WHERE scope_key = %s',
            (e.rig.workspace.store.key(e.rig.nid, e.rig.scope),)).fetchone()
    assert row is not None
    assert not e.rig.workspace.store.path(e.rig.nid, e.rig.scope).exists()
    return deepcopy(row)


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('edit', ['trim', 'speed', 'gap'])
def test_real_postgres_native_edit_ack_commit_replay_reopen(case, prefix, edit):
    from test_studio_canvas_audio_return import services
    e = case
    before = persisted(e)
    native_checks.test_explicit_native_edit_preview_ack_apply_replay(e, prefix, edit)
    after = persisted(e)
    assert after[1] == before[1] + 1
    rows = after[0]['collections']['creative_production_timelines_v2']
    row = rows[e.row['id']]
    assert row['version'] == 2
    assert row['project_incarnation'].startswith('postgres:')
    # New service/store instances must read the database, not an in-memory owner.
    reopened = services(e.rig.root, 'postgres', e.rig.url, e.rig.novels, e.rig.chapters)
    assert reopened.store.read(e.rig.nid, e.rig.scope)['collections']['creative_production_timelines_v2'][e.row['id']] == row
    assert persisted(e) == after


@pytest.mark.parametrize('mutation', ['bytes', 'binding', 'mode', 'cas', 'digest', 'source'])
def test_real_postgres_rejected_changed_inputs_preserve_database(case, mutation):
    before = persisted(case)
    native_checks.test_changed_preview_inputs_cannot_write(case, mutation)
    assert persisted(case) == before


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_real_postgres_preview_and_missing_ack_leave_no_database_write(case, prefix):
    e = case
    before = persisted(e)
    _, request = native_checks.edited(e, prefix)
    assert persisted(e) == before
    preview = call(e, base(e, prefix) + '/transfer-preview', request)
    assert persisted(e) == before
    response = e.rig.client.post(base(e, prefix) + '/transfer-import', headers=e.headers, json={
        **request, 'request_id': 'pg-missing-ack', 'reviewed_preview_digest': preview['preview_digest']})
    assert response.status_code == 422 and 'REVIEW_LOSS_REPORT_REQUIRED' in response.text
    assert persisted(e) == before
