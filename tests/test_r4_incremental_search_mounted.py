"""Actual composed U03 routes, using isolated synthetic File repositories."""
from collections import OrderedDict
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import api as legacy
from app.config import Settings, settings
from app.experimental import api as workspace_api
from app.experimental.store import ExperimentalStore
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService

pytestmark = pytest.mark.file_backend_only


def test_mounted_search_no_write_multi_project_rebuild_stale_and_flag_fences(monkeypatch, tmp_path):
    if settings.enable_collaboration_runtime: pytest.skip('isolated local author contract')
    # The mounted router captures its WorkspaceToolsService at app composition.
    # Give both it and the ORIGINAL workbench authorization/create routes the
    # same real, isolated repositories. Otherwise an earlier test's projects
    # can consume the documented 20-authorized-scope bound before our target.
    bundle = create_repository_bundle(Settings(storage_backend='file'), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    monkeypatch.setattr(legacy, 'novel_service', novels)
    monkeypatch.setattr(legacy, 'chapter_service', chapters)
    monkeypatch.setattr(legacy.collaboration_scope_service, 'repository', bundle.scope)
    monkeypatch.setattr(legacy.continuity_finding_service, 'repository', bundle.continuity)
    service = workspace_api.workspace_tools_service
    monkeypatch.setattr(service, 'novels', novels)
    monkeypatch.setattr(service, 'chapters', chapters)
    monkeypatch.setattr(service, 'store', ExperimentalStore(tmp_path, 'file'))
    monkeypatch.setattr(service, '_indexes', OrderedDict())
    monkeypatch.setattr(service, '_search_operations', OrderedDict())
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    client = TestClient(app); ids = ['search-mounted-' + uuid4().hex for _ in range(2)]
    for nid in ids: assert client.post('/api/novels', json={'id': nid, 'title': 'Synthetic ' + nid}).status_code == 201
    try:
        backend = legacy.chapter_service.repository.backend
        backend.create_chapter(ids[0], {'title': '起点', 'content': '纯合成正文'})
        chapter = backend.create_chapter(ids[1], {'title': '跨项目灯塔', 'content': '灯塔😀跨项目合成正文'})
        roots = [backend.novels / nid for nid in ids]
        snapshot = lambda: {(root.name, str(path.relative_to(root))): path.read_bytes()
                            for root in roots for path in root.rglob('*') if path.is_file()}
        before = snapshot(); base = f'/api/novels/{ids[0]}/experimental/workspace'
        response = client.get(base + '/search', params={'scope': 'authorized', 'q': '灯塔'})
        assert response.status_code == 200, response.text
        value = response.json(); assert value['match_count'] == 1 and value['incremental_chapters']
        assert not value['index_truncated'] and len(value['items']) == 1
        assert snapshot() == before
        item = value['items'][0]; assert item['novel_id'] == ids[1]
        warm = client.get(base + '/search', params={'scope': 'authorized', 'q': '灯塔'}).json()
        assert warm['chapter_bodies_read'] == 0
        target = {key: item[key] for key in ('kind', 'id', 'novel_id', 'branch_id', 'revision', 'offset')}
        assert client.post(base + '/search/resolve', json=target).json()['id'] == chapter['id']
        saved = legacy.chapter_service.save(chapter['id'], {'version': 1, 'content': '新的星港合成正文'})
        assert client.post(base + '/search/resolve', json=target).status_code == 409
        rebuilt = client.post(base + '/search/rebuild', json={'scope': 'authorized', 'q': '星港'})
        assert rebuilt.status_code == 200 and rebuilt.json()['items'][0]['version'] == saved['version']
        assert client.post(base + '/search/cancel', json={'request_id': 'pre-cancel'}).status_code == 200
        assert client.get(base + '/search', params={'request_id': 'pre-cancel'}).json()['detail']['code'] == 'SEARCH_CANCELLED'
        for flag, value in [('EXPERIMENTAL_FEATURES', ''), ('V1_ACCEPTANCE_MODE', 'true')]:
            monkeypatch.setenv(flag, value)
            assert client.get(base + '/search').status_code == 404
            assert client.post(base + '/search/rebuild', json={}).status_code == 404
            assert client.post(base + '/search/cancel', json={'request_id': 'x'}).status_code == 404
            monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'workspace_tools_v2')
    finally:
        for nid in ids: legacy.novel_service.delete(nid)
