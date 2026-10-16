"""U03 real repository sources. PostgreSQL cases require the marked hosted job."""
import copy
import json
import os
import threading
import time
import platform
try:
    import resource
except ImportError:  # Windows has no resource module.
    resource = None
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.document import markdown_to_document
from app.experimental.common import StaleSourceError
from app.experimental.search_sources import create_search_candidates
from app.experimental.store import ExperimentalStore
from app.experimental.ux import WorkspaceToolsService, ReadContext
from app.experimental.ux_api import create_ux_router
from app.repositories.factory import create_repository_bundle
from app.services import NovelService, ChapterService


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def source_env(tmp_path, request):
    backend = request.param; url = os.getenv('TEST_POSTGRES_DATABASE_URL', '')
    if backend == 'postgres' and not url: pytest.skip('NOT_RUN: real PostgreSQL endpoint unavailable')
    bundle = create_repository_bundle(Settings(storage_backend=backend, database_url=url), data_root=tmp_path)
    novels, chapters = NovelService(bundle.novels, bundle.chapters), ChapterService(bundle.chapters)
    nid = novels.create({'id': 'search-' + uuid4().hex, 'title': 'Synthetic search'})['id']
    other = novels.create({'id': 'search-' + uuid4().hex, 'title': 'Synthetic second'})['id']
    rows = [chapters.create(nid, {'title': f'第{n}章', 'content': '合成石城与阿青。' * 50}) for n in range(1, 4)]
    outside = chapters.create(other, {'title': '第二作品灯塔', 'content': '独有的灯塔信号。'})
    service = WorkspaceToolsService(ExperimentalStore(tmp_path, backend, url), novels, chapters,
        search_candidates=create_search_candidates(bundle.scope))
    ctx = ReadContext(nid, {'mode': 'local', 'novel_id': nid}, 'alice')
    env = SimpleNamespace(service=service, ctx=ctx, novels=novels, chapters=chapters, rows=rows,
                          other=other, outside=outside, bundle=bundle, backend=backend, root=tmp_path)
    yield env
    novels.delete(nid); novels.delete(other)


def test_incremental_repository_manifest_reads_only_changed_sources(source_env, monkeypatch):
    e = source_env
    first = e.service.search(e.ctx, '合成')
    assert first['incremental_chapters'] and first['source_rows_read'] == 3
    assert first['match_count'] == 3
    import app.experimental.ux as ux
    original = ux.chapter_text
    reads = []
    monkeypatch.setattr(ux, 'chapter_text', lambda row: (reads.append(row['id']), original(row))[1])
    monkeypatch.setattr(e.chapters, 'list', lambda nid: pytest.fail('warm manifest scanned complete chapters'))
    warm = e.service.search(e.ctx, '阿青')
    assert warm['source_rows_read'] == warm['updated_documents'] == 0 and reads == []
    saved = e.chapters.save(e.rows[0]['id'], {'version': 1, 'content': '更新后的山城。'})
    changed = e.service.search(e.ctx, '山城')
    assert changed['updated_documents'] == changed['source_rows_read'] == 1
    assert reads == [saved['id']] and changed['items'][0]['version'] == 2
    with pytest.raises(StaleSourceError): e.service.resolve(e.ctx, {k: first['items'][0][k] for k in ('kind', 'id', 'revision')})
    e.chapters.archive(e.rows[1]['id'], 1)
    assert e.service.search(e.ctx, '合成')['match_count'] == 1
    e.chapters.delete(e.rows[2]['id'])
    assert e.service.search(e.ctx, '合成')['match_count'] == 0
    rebuilt = e.service.search(e.ctx, '山城', rebuild=True)
    assert rebuilt['source_rows_read'] == 1 and rebuilt['items'][0]['id'] == saved['id']


def test_repository_source_race_and_cancel_leave_prior_index_atomic(source_env, monkeypatch):
    e = source_env; e.service.search(e.ctx, '合成')
    before = copy.deepcopy(e.service._indexes)
    original = e.service._search_manifest; calls = 0
    def raced(*args):
        nonlocal calls
        calls += 1
        if calls == 2: e.chapters.save(e.rows[0]['id'], {'version': 1, 'content': '并发修改'})
        return original(*args)
    monkeypatch.setattr(e.service, '_search_manifest', raced)
    with pytest.raises(StaleSourceError): e.service.search(e.ctx, '合成', rebuild=True)
    assert e.service._indexes == before
    monkeypatch.setattr(e.service, '_search_manifest', original)
    e.service.cancel_search(e.ctx, 'cancel-before-start')
    with pytest.raises(HTTPException) as cancelled: e.service.search(e.ctx, '合成', rebuild=True, request_id='cancel-before-start')
    assert cancelled.value.detail['code'] == 'SEARCH_CANCELLED' and e.service._indexes == before
    entered, release = threading.Event(), threading.Event()
    def waiting(*args):
        entered.set(); assert release.wait(5)
        return original(*args)
    monkeypatch.setattr(e.service, '_search_manifest', waiting)
    errors = []
    def worker():
        try: e.service.search(e.ctx, '合成', rebuild=True, request_id='cancel-inflight')
        except HTTPException as exc: errors.append(exc.detail['code'])
    thread = threading.Thread(target=worker); thread.start(); assert entered.wait(5)
    e.service.cancel_search(e.ctx, 'cancel-inflight'); release.set(); thread.join(5)
    assert not thread.is_alive() and errors == ['SEARCH_CANCELLED'] and e.service._indexes == before


def test_local_alias_tags_recent_fulltext_and_unresolved_findings(source_env):
    e = source_env
    now = datetime.now(timezone.utc).isoformat()
    e.service.entity_readers['character'] = lambda ctx: [
        {'id': 'qing', 'name': '阿青', 'aliases': ['石城'], 'tags': ['主角'], 'updated_at': now},
        {'id': 'private', 'name': '不可见别名', 'hidden': True},
        {'id': 'old', 'name': '旧人物', 'updated_at': '2020-01-01T00:00:00+00:00'}]
    e.service.finding_reader = lambda ctx: [{'id': 'finding-1', 'project_id': ctx.novel_id, 'finding_type': 'LOCATION', 'message': '人物位置未解决', 'status': 'OPEN'},
        {'id': 'resolved', 'project_id': ctx.novel_id, 'message': '已解决', 'status': 'RESOLVED'},
        {'id': 'foreign', 'project_id': 'other-project', 'message': '不可泄漏', 'status': 'OPEN'}]
    assert e.service.search(e.ctx, '石城')['items'][0]['id'] == 'qing'
    assert [r['id'] for r in e.service.search(e.ctx, tag='主角')['items']] == ['qing']
    assert [r['id'] for r in e.service.search(e.ctx, kind='character', recent_days=1)['items']] == ['qing']
    assert all(r['kind'] == 'chapter' for r in e.service.search(e.ctx, '石城', fulltext=True)['items'])
    assert [r['id'] for r in e.service.search(e.ctx, kind='finding', unresolved=True)['items']] == ['finding-1']
    assert not e.service.search(e.ctx, '不可')['items']


def test_mounted_multi_project_reauthorizes_counts_suggestions_and_resolve(source_env, monkeypatch):
    e = source_env; denied = set(); calls = []
    def authorize(nid, token, branch, permission):
        calls.append(nid)
        if nid in denied: raise HTTPException(403)
        if nid not in {e.ctx.novel_id, e.other}: raise HTTPException(404)
        return 'alice', {'mode': 'local', 'novel_id': nid}
    api = FastAPI(); api.include_router(create_ux_router(e.service, authorize, lambda flag: None))
    client = TestClient(api); base = f'/novels/{e.ctx.novel_id}/experimental/workspace'
    first = client.get(base + '/search', params={'scope': 'authorized', 'q': '灯塔'})
    assert first.status_code == 200 and first.json()['match_count'] == 1
    row = first.json()['items'][0]; assert row['novel_id'] == e.other
    target = {k: row[k] for k in ('kind', 'id', 'novel_id', 'branch_id', 'revision', 'offset')}
    assert client.post(base + '/search/resolve', json=target).json()['novel_id'] == e.other
    denied.add(e.other)
    result = client.get(base + '/search', params={'scope': 'authorized', 'q': '灯塔'}).json()
    assert result['match_count'] == 0 and result['items'] == result['suggestions'] == []
    assert e.other not in json.dumps(result)
    assert client.post(base + '/search/resolve', json=target).status_code == 403
    denied.clear()
    original = e.service.search
    def revoke_after_read(ctx, *args, **kwargs):
        result = original(ctx, *args, **kwargs)
        if ctx.novel_id == e.other: denied.add(e.other)
        return result
    monkeypatch.setattr(e.service, 'search', revoke_after_read)
    result = client.get(base + '/search', params={'scope': 'authorized', 'q': '灯塔'}).json()
    assert result['match_count'] == 0 and not result['suggestions']
    assert calls.count(e.other) > 3


def test_mounted_permission_revocation_mid_read_and_disabled_cancel(source_env):
    e = source_env; state = {'enabled': True, 'calls': 0, 'allowed': True}
    def gate(flag):
        if not state['enabled']: raise HTTPException(404)
    def authorize(nid, *args):
        state['calls'] += 1
        if not state['allowed'] or state['calls'] > 2: raise HTTPException(403)
        return e.ctx.actor, e.ctx.scope
    api = FastAPI(); api.include_router(create_ux_router(e.service, authorize, gate))
    client = TestClient(api); base = f'/novels/{e.ctx.novel_id}/experimental/workspace'
    response = client.get(base + '/search?q=合成')
    assert response.status_code == 403 and '合成' not in response.text and not e.service._indexes
    state['enabled'] = False
    assert client.post(base + '/search/cancel', json={'request_id': 'x'}).status_code == 404
    assert client.post(base + '/search/rebuild', json={}).status_code == 404


def test_never_opened_file_search_is_read_only_and_detects_nonversioned_edits(source_env):
    e = source_env
    if e.backend == 'postgres':
        # The marked PG contract must execute, not skip a File-only branch.
        # Observe the same read-only/freshness invariant in original PG storage.
        import hashlib
        from app.repositories.postgres.common import chapter_or_raise
        before = [e.chapters.get(row['id']) for row in e.rows]
        e.service.search(e.ctx, '阿青')
        assert [e.chapters.get(row['id']) for row in e.rows] == before
        markdown = '# 原地编辑\n\n外部变更灯塔'
        with e.bundle.chapters.database.session() as session:
            _, chapter = chapter_or_raise(session, e.rows[0]['id'])
            assert chapter.version == before[0]['version']
            chapter.title = '原地编辑'
            chapter.document = markdown_to_document(markdown)
            chapter.content_hash = hashlib.sha256(markdown.encode()).hexdigest()
            chapter.updated_at = datetime.now(timezone.utc)
        assert e.chapters.get(e.rows[0]['id'])['version'] == before[0]['version']
        result = e.service.search(e.ctx, '灯塔')
        assert result['source_rows_read'] == 1 and result['items'][0]['title'] == '原地编辑'
        assert result['items'][0]['id'] == e.rows[0]['id']
        return
    root = e.bundle.chapters.backend.novels / e.ctx.novel_id
    snapshot = lambda: {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    before = snapshot(); e.service.search(e.ctx, '阿青'); assert snapshot() == before
    assert not (root / 'documents').exists()
    path = root / 'chapters' / 'chapter-0001.md'
    path.write_text('# 原地编辑\n\n外部变更灯塔', encoding='utf-8')
    result = e.service.search(e.ctx, '灯塔')
    assert result['source_rows_read'] == 1 and result['items'][0]['title'] == '原地编辑'


def test_large_project_warm_search_does_not_project_manuscript(source_env, monkeypatch, record_property):
    e = source_env
    from app.experimental import ux
    record_property('python', platform.python_version())
    record_property('platform', platform.platform())
    record_property('measurement', 'in-process service; 3 chapters; 20 warmed literal queries; nearest-rank p95; no entities/tasks; timings exclude fixture creation')
    for size in [100_000, 500_000, 1_000_000]:
        current = e.chapters.get(e.rows[0]['id'])
        e.chapters.save(current['id'], {'version': current['version'], 'content': '汉' * size + '灯塔'})
        started = time.perf_counter(); cold = e.service.search(e.ctx, '灯塔', rebuild=True); cold_ms = (time.perf_counter() - started) * 1000
        measurements = []
        with monkeypatch.context() as patch:
            patch.setattr(ux, 'chapter_text', lambda row: pytest.fail('warm search reprojected manuscript'))
            for _ in range(20):
                started = time.perf_counter(); result = e.service.search(e.ctx, '灯塔'); measurements.append((time.perf_counter() - started) * 1000)
                assert result['source_rows_read'] == 0 and len(result['items']) == 1
        record_property(f'{e.backend}_{size}_cold_ms', round(cold_ms, 3))
        record_property(f'{e.backend}_{size}_warm_p95_ms', round(sorted(measurements)[18], 3))
        assert cold['incremental_chapters']
        tracemalloc.start()
        e.service.search(e.ctx, '灯塔', rebuild=True)
        _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
        record_property(f'{e.backend}_{size}_index_rebuild_peak_python_bytes', peak)
        record_property(f'{e.backend}_{size}_process_peak_rss_kib', resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else 'NOT_MEASURED')


def test_warm_manifest_never_reads_file_bodies_or_pg_document_column(source_env, monkeypatch):
    e = source_env; e.service.search(e.ctx)
    if e.backend == 'file':
        original = Path.read_text
        def checked(path, *args, **kwargs):
            if path.parent.name in {'chapters', 'documents'}: pytest.fail('warm search read manuscript body')
            return original(path, *args, **kwargs)
        monkeypatch.setattr(Path, 'read_text', checked)
        assert e.service.search(e.ctx, '阿青')['chapter_bodies_read'] == 0
    else:
        from sqlalchemy import event
        engine = e.bundle.chapters.database.engine; statements = []
        def record(conn, cursor, statement, parameters, context, many): statements.append(statement)
        event.listen(engine, 'before_cursor_execute', record)
        try: assert e.service.search(e.ctx, '阿青')['chapter_bodies_read'] == 0
        finally: event.remove(engine, 'before_cursor_execute', record)
        chapter_queries = [sql for sql in statements if 'FROM chapters' in sql]
        assert chapter_queries and all('chapters.document' not in sql for sql in chapter_queries)


def test_count_paging_and_actor_cancellation_isolation(source_env):
    e = source_env
    e.service.entity_readers['character'] = lambda ctx: [{'id': f'name-{i:03}', 'name': f'合成人物{i:03}'} for i in range(60)]
    first = e.service.search(e.ctx, '合成人物'); second = e.service.search(e.ctx, '合成人物', offset=50)
    assert first['match_count'] == second['match_count'] == 60
    assert len(first['items']) == 50 and len(second['items']) == 10
    assert first['next_offset'] == 50 and second['next_offset'] is None
    assert not ({r['id'] for r in first['items']} & {r['id'] for r in second['items']})
    stranger = ReadContext(e.ctx.novel_id, e.ctx.scope, 'bob')
    e.service.cancel_search(stranger, 'same-request')
    assert e.service.search(e.ctx, request_id='same-request')['items']


def test_generation_task_search_preserves_original_source_version(source_env):
    from app.experimental.ux import TaskReader
    e = source_env
    # Use the existing, actor-scoped task projection's supported generation shape.
    row = {'id': 'original-job', 'novel_id': e.ctx.novel_id, 'scope': e.ctx.scope, 'actor_id': e.ctx.actor,
           'status': 'COMPLETED', 'version': 9, 'chapter_id': e.rows[0]['id'], 'base_chapter_version': 2}
    e.service.task_readers = (TaskReader('author_generation', '正文生成', 'history', lambda ctx: [row]),)
    result = e.service.search(e.ctx, '正文生成', kind='task')
    assert result['match_count'] == 1
    assert e.service.search(e.ctx, 'original-job', kind='task')['match_count'] == 1
    item = result['items'][0]
    target = e.service.resolve(e.ctx, {k: item[k] for k in ('kind', 'id', 'revision')})
    assert target['kind'] == 'generation' and target['id'] == 'original-job'
    assert target['chapter_id'] == e.rows[0]['id'] and target['version'] == 2
