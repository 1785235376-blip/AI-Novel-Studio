"""Provider-free industry export integration through the durable queue."""
import io
import time
from types import SimpleNamespace
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.services.export_job_service import ExportJobService
from app.services.novel_service import NovelService


class Source:
    def __init__(self):
        self.screenplays = [{"id": "script-1", "branch_id": "branch-a", "title": "Original screenplay", "version": 7,
            "scenes": [{"id": "scene-1", "location": "STATION", "time": "DAY",
                        "action": "Original action", "dialogue": [{"character": "ALICE", "text": "Original dialogue"}]}]}]
        self.chapters = [{"id": "chapter-1", "title": "Chapter", "content": "Original prose", "version": 3}]

    def get(self, nid): return {"id": nid, "title": "Original novel", "updated_at": "2026-10-03"}
    def list(self, nid): return self.chapters
    def list_screenplays(self, nid): return self.screenplays
    def get_data_set(self, nid, name): return []
    def get_outline(self, nid): return {}


def wait(queue, jid):
    for _ in range(300):
        job = queue.get(jid)
        if job['status'] in {'succeeded', 'failed', 'cancelled'}:
            return job
        time.sleep(.01)
    pytest.fail(f"export did not finish: {queue.get(jid)}")


@pytest.fixture
def setup_queue(tmp_path, monkeypatch):
    import app.api as api
    source = Source()
    novels = NovelService(source, source)
    queue = ExportJobService(tmp_path, novels.export, snapshotter=novels.export_snapshot)
    monkeypatch.setattr(api, 'novel_service', novels)
    monkeypatch.setattr(api, 'export_job_service', queue)
    monkeypatch.setattr(api, 'settings', SimpleNamespace(enable_collaboration_runtime=True))
    class Sessions:
        def resolve(self, token):
            if token not in {'owner', 'outsider', 'other-branch'}: raise KeyError(token)
            return SimpleNamespace(actor_id=token, workspace_id='foreign' if token == 'outsider' else 'workspace')
    class Scopes:
        repository = None
        def project_workspace(self, project): return 'workspace'
        def get(self, collection, branch):
            if branch not in {'branch-a', 'branch-b'}: raise KeyError(branch)
            return {'project_id': 'project', 'workspace_id': 'workspace', 'storyline_id': 'story'}
        def validate_scope(self, scope): return scope
    scopes = Scopes(); scopes.repository = scopes
    class Membership:
        def require(self, actor, permission, domain, scope):
            if actor.actor_id == 'other-branch' and scope.branch_id != 'branch-b':
                raise PermissionError('wrong branch')
    monkeypatch.setattr(api, 'trusted_session_resolver', Sessions())
    monkeypatch.setattr(api, 'collaboration_scope_service', scopes)
    monkeypatch.setattr(api, 'membership_authorization_service', Membership())
    app = FastAPI(); app.include_router(api.router, prefix='/api')
    yield source, novels, queue, TestClient(app)
    queue._pool.shutdown(wait=True)


@pytest.mark.parametrize('fmt,extension,media', [
    ('screenplay-fountain', 'fountain', 'text/x-fountain'),
    ('screenplay-docx', 'docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'),
    ('screenplay-standard', 'fountain', 'text/x-fountain'),
])
def test_queue_api_download_uses_captured_body_and_provenance(setup_queue, monkeypatch, fmt, extension, media):
    source, novels, queue, client = setup_queue
    monkeypatch.setattr(queue, '_submit', lambda _: None)
    headers = {'X-Session-Token': 'owner', 'Idempotency-Key': 'same'}
    response = client.post('/api/exports?novel_id=project&branch_id=branch-a', json={'format': fmt}, headers=headers)
    assert response.status_code == 202, response.text
    job = response.json(); jid = job['id']
    assert job['format'] == ('screenplay-fountain' if fmt == 'screenplay-standard' else fmt)
    assert client.post('/api/exports?novel_id=project&branch_id=branch-a', json={'format': fmt}, headers=headers).json()['id'] == jid
    source.screenplays[0]['scenes'][0]['action'] = 'MUTATED ACTION'
    source.screenplays[0]['version'] = 99
    source.screenplays.reverse()
    source.screenplays.append({'id': 'later', 'scenes': []})
    source.chapters[0]['version'] = 44
    monkeypatch.setattr(novels.novels, 'list_screenplays', lambda _: pytest.fail('live screenplay read'))
    queue._run(jid)
    completed = wait(queue, jid)
    assert completed['status'] == 'succeeded', completed['error']
    downloaded = client.get(f'/api/exports/{jid}/download', headers=headers)
    assert downloaded.status_code == 200
    assert downloaded.headers['content-type'].startswith(media)
    assert f'.{extension}' in downloaded.headers['content-disposition']
    if extension == 'docx':
        with ZipFile(io.BytesIO(downloaded.content)) as archive:
            assert {'[Content_Types].xml', 'word/document.xml', 'word/styles.xml'} <= set(archive.namelist())
            document = ET.fromstring(archive.read('word/document.xml'))
            rendered = ''.join(document.itertext())
    else:
        rendered = downloaded.text
        assert 'Format: Fountain 1.1' in rendered and 'ALICE' in rendered and 'STATION' in rendered
    assert 'Original action' in rendered and 'Original dialogue' in rendered
    assert 'MUTATED' not in rendered
    assert job['snapshot_id'] in rendered
    assert "'version': 7" in rendered and "'version': 3" in rendered
    assert completed['artifact']['size'] == len(downloaded.content)


@pytest.mark.parametrize('fmt', ['screenplay-fountain', 'screenplay-docx'])
@pytest.mark.parametrize('rows,message', [([], 'requires a screenplay'), ([{'scenes': []}], 'at least one scene'),
    ([{'scenes': [{'id': 'duplicate'}, {'id': 'duplicate'}]}], '影视导出数据校验失败')])
def test_invalid_screenplay_is_useful_failed_job(setup_queue, fmt, rows, message):
    source, _, queue, _ = setup_queue
    source.screenplays = rows
    job = wait(queue, queue.create('project', fmt)['id'])
    assert job['status'] == 'failed'
    assert message in job['error']['message'].lower()
    assert job['result'] is None
    if rows:
        assert job['error']['code'] == 'EXPORT_SCHEMA_INVALID'
        assert job['error']['details']['issues']


@pytest.mark.parametrize('fmt', ['screenplay-fountain', 'screenplay-docx'])
def test_industry_routes_keep_project_branch_scope_and_lifecycle(setup_queue, monkeypatch, fmt):
    _, _, queue, client = setup_queue
    monkeypatch.setattr(queue, '_submit', lambda _: None)
    headers = {'X-Session-Token': 'owner', 'Idempotency-Key': 'shared-key'}
    path = '/api/exports?novel_id=project&branch_id=branch-a'
    assert client.post(path, json={'format': fmt}).status_code == 401
    assert client.post(path, json={'format': fmt}, headers={'X-Session-Token': 'outsider'}).status_code == 403
    job = client.post(path, json={'format': fmt}, headers=headers).json()
    for token in ['outsider', 'other-branch']:
        for method, suffix in [('get', ''), ('get', '/download'), ('post', '/cancel'), ('post', '/retry')]:
            assert getattr(client, method)(f"/api/exports/{job['id']}{suffix}", headers={'X-Session-Token': token}).status_code == 404
    other = client.post('/api/exports?novel_id=project&branch_id=branch-b', json={'format': fmt}, headers={**headers, 'X-Session-Token': 'other-branch'}).json()
    assert other['id'] != job['id']
    assert client.post(f"/api/exports/{job['id']}/cancel", headers=headers).json()['status'] == 'cancelled'
    retry = client.post(f"/api/exports/{job['id']}/retry", headers=headers)
    assert retry.status_code == 202
    assert retry.json()['retry_of'] == job['id']
    assert retry.json()['permission_context']['branch_id'] == 'branch-a'
    queue._run(retry.json()['id'])
    assert wait(queue, retry.json()['id'])['status'] == 'succeeded'


def test_restart_replays_original_industry_snapshot(setup_queue, monkeypatch, tmp_path):
    source, novels, queue, _ = setup_queue
    monkeypatch.setattr(queue, '_submit', lambda _: None)
    job = queue.create('project', 'screenplay-fountain')
    source.screenplays.clear()
    restored = ExportJobService(tmp_path, novels.export, snapshotter=novels.export_snapshot)
    try:
        done = wait(restored, job['id'])
        assert done['status'] == 'succeeded'
        assert done['recovery_count'] == 1
        assert done['snapshot_id'] == job['snapshot_id']
        assert b'Original action' in restored.download(job['id'])['content']
    finally:
        restored._pool.shutdown(wait=True)


def test_snapshot_is_deep_copy(setup_queue):
    source, novels, _, _ = setup_queue
    snapshot = novels.export_snapshot('project')
    source.screenplays[0]['scenes'][0]['action'] = 'changed'
    assert snapshot['source']['screenplays'][0]['scenes'][0]['action'] == 'Original action'


@pytest.mark.parametrize('fmt', ['screenplay-fountain', 'screenplay-docx', 'screenplay-standard', 'screenplay-package', 'shot-list-package', 'storyboard-html', 'storyboard-package'])
def test_legacy_export_does_not_expose_industry_renderer(setup_queue, fmt):
    _, _, queue, client = setup_queue
    assert client.get(f'/api/novels/project/export?format={fmt}').status_code == 400
    if fmt == 'storyboard-html':
        with pytest.raises(ValueError, match='unsupported'):
            queue.create('project', fmt)


def test_legacy_shot_list_preserves_eight_columns_and_embedded_newlines(setup_queue):
    import csv
    source, novels, _, _ = setup_queue
    action = 'Walk, pause\nSay "hello"'
    source.screenplays[0]['shots'] = [{'number': 1, 'scene_id': 'scene-1', 'shot_size': 'wide',
        'camera_angle': 'eye level', 'camera_motion': 'static', 'subject_position': 'center',
        'action': action, 'duration_seconds': 5}]
    result = novels.export('project', 'shot-list')
    rows = list(csv.reader(io.StringIO(result['content'])))
    assert len(rows) == 2 and all(len(row) == 8 for row in rows)
    assert rows[0] == ['镜号', '场景', '景别', '角度', '运动', '主体位置', '动作', '时长']
    assert rows[1] == ['1', 'scene-1', 'wide', 'eye level', 'static', 'center', action, '5']
