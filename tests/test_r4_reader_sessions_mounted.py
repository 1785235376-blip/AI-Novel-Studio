"""U11/U15 actual composed routes with a never-opened synthetic File chapter."""
import json
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app import api as legacy
from app.config import settings

pytestmark = pytest.mark.file_backend_only


def test_mounted_reader_preflight_session_roundtrip_and_v1_no_leak(monkeypatch):
    if settings.enable_collaboration_runtime: pytest.skip('requires isolated local File profile')
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'reader_preflight_v2,writing_sessions_v2,workspace_tools_v2')
    client = TestClient(app); nid = 'reader-mounted-' + uuid4().hex
    assert client.post('/api/novels', json={'id': nid, 'title': 'Synthetic reader mounted'}).status_code == 201
    try:
        repo = legacy.chapter_service.repository.backend
        chapter = repo.create_chapter(nid, {'title': 'Never opened synthetic chapter', 'content': 'the the 🙂！！'})
        base = f'/api/novels/{nid}/experimental'
        root = repo.novels / nid
        before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        reading = client.get(base + '/reader-preflight/read'); assert reading.status_code == 200
        result = client.post(base + '/reader-preflight/check', json={'format': 'docx'})
        assert result.status_code == 200 and result.json()['model_calls'] == 0
        assert result.json()['read_only'] and result.json()['export_snapshot_created'] is False
        after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
        assert before == after
        proof = client.get(base + '/reader-preflight/proof').json()
        assert len(proof['items']) == 2
        session = client.post(base + '/writing-sessions', json={'capture_id': 'mounted', 'goal': 'PRIVATE_SESSION_GOAL'}).json()
        finished = client.put(base + '/writing-sessions/' + session['id'], json={'expected_version': session['version'], 'stopping_note': 'PRIVATE_STOP_NOTE', 'complete': True})
        assert finished.status_code == 200 and finished.json()['recap']['persisted_revision_events'] == 0
        assert 'PRIVATE_STOP_NOTE' not in json.dumps(client.get(f'/api/novels/{nid}').json())
        assert 'PRIVATE_SESSION_GOAL' not in json.dumps(client.get(f'/api/novels/{nid}/writing-goal').json())
        monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        for suffix in ('/reader-preflight/read', '/reader-preflight/settings', '/writing-sessions', '/writing-sessions/notices'):
            response = client.get(base + suffix)
            assert response.status_code == 404 and 'PRIVATE_' not in response.text
    finally:
        legacy.novel_service.delete(nid)
