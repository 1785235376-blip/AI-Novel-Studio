"""U11/U15 deterministic contracts; real File repository and optional real PG."""
import copy
import hashlib
import json
import os
from types import SimpleNamespace
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.experimental.store import ExperimentalStore
from app.experimental.ux import ReadContext
from app.experimental.writing_focus import WritingFocusService
from app.experimental.reader_preflight import ReaderPreflightService
from app.experimental.reader_preflight_api import create_reader_preflight_router
from app.experimental.writing_sessions import WritingSessionsService
from app.experimental.writing_sessions_api import create_writing_sessions_router
from app.experimental.common import StaleSourceError
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def env(tmp_path, request):
    backend = request.param; url = os.getenv('TEST_POSTGRES_DATABASE_URL', '') if backend == 'postgres' else ''
    if backend == 'postgres' and not url: pytest.skip('NOT_RUN: authorized real PostgreSQL endpoint unavailable')
    config = Settings(storage_backend=backend, database_url=url, novel_data=tmp_path, mock_provider=True, enable_cloud=False)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    chapters, novels = ChapterService(bundle.chapters), NovelService(bundle.novels, bundle.chapters)
    nid = 'reader-' + uuid4().hex; novels.create({'id': nid, 'title': 'Synthetic reader', 'genre': 'fantasy'})
    chapter = chapters.create(nid, {'title': '港口', 'content': '甲🙂。\n阿青！！ the the 船长。'})
    chapter = chapters.save(chapter['id'], {'version': chapters.get(chapter['id'])['version'], 'document': {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': '甲🙂。'}]}, {'type': 'paragraph', 'content': [{'type': 'text', 'text': '阿青！！ the the 船长。'}]}]}})
    ctx = ReadContext(nid, {'mode': 'local', 'novel_id': nid}, 'author')
    store = ExperimentalStore(tmp_path, backend, url); sources = WritingFocusService(store, novels, chapters)
    task_rows = []
    task_reader = lambda ctx: {'items': copy.deepcopy(task_rows), 'truncated': False, 'unavailable': []}
    reader = ReaderPreflightService(store, novels, chapters, sources=sources, task_reader=task_reader)
    sessions = WritingSessionsService(store, novels, chapters, sources=sources, task_reader=task_reader)
    e = SimpleNamespace(reader=reader, sessions=sessions, sources=sources, store=store, novels=novels, chapters=chapters, ctx=ctx, cid=chapter['id'], tasks=task_rows)
    yield e
    if backend == 'postgres':
        with store._connect() as conn: conn.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))
        novels.delete(nid)


def anchor(e):
    chapter = e.reader.read(e.ctx)['chapters'][0]; p = chapter['paragraphs'][1]
    return {'chapter_id': chapter['id'], 'revision': chapter['revision'], 'offset': p['offset'], 'quote': p['text']}


def test_reader_unicode_offsets_and_readonly_preflight(env):
    e = env; before = e.store.read(e.ctx.novel_id, e.ctx.scope); history = e.chapters.history(e.cid)
    a = anchor(e); assert a['offset'] == 4  # emoji is one codepoint
    assert e.reader.open_anchor(e.ctx, a)['anchor']['offset'] == 4
    report = e.reader.preflight(e.ctx, {'format': 'epub', 'draft_status': [{'chapter_id': e.cid, 'chapter_version': 2, 'state': 'LOCAL_DRAFT'}]})
    assert report['read_only'] and report['model_calls'] == 0 and not report['export_snapshot_created']
    assert not report['target_renderer_verified']
    assert any(x['code'] == 'LOCAL_LOCAL_DRAFT' for x in report['findings'])
    assert {'area': 'generation_candidates', 'state': 'UNKNOWN'} in report['coverage']
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before
    assert e.chapters.history(e.cid) == history


def test_proof_rules_ignore_reason_and_exact_quote_cas(env):
    e = env; cfg = e.reader.save_settings(e.ctx, {'expected_version': 0, 'rules': {'literals': [{'kind': 'naming', 'find': '阿青', 'suggest': '青船长'}]}})
    findings = e.reader.proof(e.ctx)['items']; assert {f['kind'] for f in findings} == {'punctuation', 'repeated_words', 'naming'}
    f = next(f for f in findings if f['kind'] == 'naming'); assert f['offset'] == 4 and f['paragraph'] == 1
    ignored = e.reader.ignore(e.ctx, {'expected_version': cfg['version'], 'finding_id': f['id'], 'reason': '此处使用昵称'})
    assert next(x for x in e.reader.proof(e.ctx)['items'] if x['id'] == f['id'])['ignored_reason'] == '此处使用昵称'
    with pytest.raises(CapabilityVersionConflict): e.reader.ignore(e.ctx, {'expected_version': 1, 'finding_id': f['id'], 'reason': 'stale'})
    with pytest.raises(ValueError): e.reader.ignore(e.ctx, {'expected_version': ignored['version'], 'finding_id': f['id'], 'reason': '  '})
    assert e.chapters.get(e.cid)['version'] == 2


def test_annotations_persist_and_hide_stale_quote_not_auto_edit(env):
    e = env; a = anchor(e); result = e.reader.annotate(e.ctx, {**a, 'expected_version': 0, 'note': '人物称谓需确认'})
    assert result['version'] == 1 and e.reader.read(e.ctx)['annotations'][0]['quote'] == a['quote']
    e.chapters.save(e.cid, {'version': 2, 'content': '新稿'})
    assert e.reader.read(e.ctx)['annotations'][0]['stale'] and e.reader.read(e.ctx)['annotations'][0]['quote'] == ''
    with pytest.raises(StaleSourceError): e.reader.open_anchor(e.ctx, a)
    with pytest.raises(StaleSourceError): e.reader.annotate(e.ctx, {**a, 'expected_version': 1, 'note': 'stale'})
    assert e.reader.settings(e.ctx)['version'] == 1


def test_unknown_foreign_draft_status_rejected_without_accepting_content(env):
    e = env
    with pytest.raises(FileNotFoundError): e.reader.preflight(e.ctx, {'draft_status': [{'chapter_id': 'foreign', 'chapter_version': 2, 'state': 'SAVED'}]})
    with pytest.raises(ValueError): e.reader.preflight(e.ctx, {'draft_status': [], 'draft_text': 'must not transmit'})
    bad = anchor(e); bad['quote'] = 'forged'
    with pytest.raises(StaleSourceError): e.reader.open_anchor(e.ctx, bad)


def test_media_checks_real_bytes_without_path_or_secret_leak(env):
    e = env; raw = b'valid synthetic media'; row = e.chapters.get(e.cid)
    row['asset_id'] = 'owned'; e.sources.chapter_reader = lambda ctx: [row]
    asset = {'id': 'owned', 'novel_id': e.ctx.novel_id, 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), 'filename': '/secret/path'}
    e.reader.assets = SimpleNamespace(get=lambda rid, **kw: asset, content=lambda rid, **kw: raw)
    report = e.reader.preflight(e.ctx, {})
    assert not any(x['code'] == 'MISSING_MEDIA' for x in report['findings'])
    e.reader.assets.content = lambda rid, **kw: b'corrupt'
    report = e.reader.preflight(e.ctx, {})
    assert report['has_integrity_blockers'] and '/secret/path' not in json.dumps(report)


def test_source_privacy_branch_and_owner_never_fallback(env):
    e = env; row = e.chapters.get(e.cid)
    e.sources.chapter_reader = lambda ctx: [row, {**row, 'id': 'private', 'hidden': True, 'title': 'SECRET', 'content': 'leak'}]
    assert len(e.reader.read(e.ctx)['chapters']) == 1
    assert e.sessions.overview(e.ctx)['project_goal']['current_chapters'] == 1
    e.reader.annotate(e.ctx, {**anchor(e), 'expected_version': 0, 'note': 'private annotation'})
    other = ReadContext(e.ctx.novel_id, e.ctx.scope, 'other')
    assert e.reader.settings(other)['version'] == 0 and e.reader.read(other)['annotations'] == []
    branch = ReadContext(e.ctx.novel_id, {'mode': 'collaboration', 'novel_id': e.ctx.novel_id, 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'b'}, 'author')
    assert e.reader.read(branch)['chapters'] == [] and e.sessions.overview(branch)['project_goal'] is None
    e.sources.chapter_reader = None
    with pytest.raises(ValueError): e.sessions.start(branch, {'capture_id': 'branch'})


def test_session_real_persisted_history_recap_and_original_goal_unchanged(env):
    e = env; e.novels.update_writing_goal(e.ctx.novel_id, {'target_words': 1000, 'target_chapters': 10})
    original = e.novels.get(e.ctx.novel_id)['writing_goal']
    session = e.sessions.start(e.ctx, {'capture_id': 'one', 'goal': '写结尾', 'target_characters': 10, 'tasks': [{'id': 't', 'text': '收束旧信'}]})
    assert e.sessions.start(e.ctx, {'capture_id': 'one', 'goal': '写结尾', 'target_characters': 10, 'tasks': [{'id': 't', 'text': '收束旧信'}]})['id'] == session['id']
    old = e.chapters.get(e.cid); e.chapters.save(e.cid, {'version': old['version'], 'content': old['content'] + '新结尾'})
    result = e.sessions.update(e.ctx, session['id'], {'expected_version': 1, 'tasks': [{'id': 't', 'text': '收束旧信', 'done': True}], 'stopping_note': '下一次核对时间线', 'complete': True})
    assert result['recap']['persisted_revision_events'] == 1 and result['recap']['net_characters'] == 3
    assert result['recap']['completed_checklist_items'] == 1
    assert e.sessions.overview(e.ctx)['items'][0]['stopping_note'] == '下一次核对时间线'
    assert e.novels.get(e.ctx.novel_id)['writing_goal'] == original
    with pytest.raises(ValueError): e.sessions.update(e.ctx, session['id'], {'expected_version': 2})


def test_session_cas_reauthorize_rollback_and_scope_isolation(env):
    e = env; row = e.sessions.start(e.ctx, {'capture_id': 'one'})
    def denied(): raise HTTPException(403)
    with pytest.raises(HTTPException): e.sessions.update(e.ctx, row['id'], {'expected_version': 1, 'stopping_note': 'not saved'}, denied)
    assert e.sessions.overview(e.ctx)['items'][0]['version'] == 1
    with pytest.raises(CapabilityVersionConflict): e.sessions.update(e.ctx, row['id'], {'expected_version': 2})
    other = ReadContext(e.ctx.novel_id, e.ctx.scope, 'other')
    assert e.sessions.overview(other)['items'] == []
    with pytest.raises(FileNotFoundError): e.sessions.update(other, row['id'], {'expected_version': 1})
    with pytest.raises(ValueError): e.sessions.start(e.ctx, {'capture_id': 'two'})


def test_notice_dedupe_actual_task_event_focus_acknowledge(env):
    e = env
    e.tasks.extend([{'authority': 'exports', 'id': 'task', 'version': 1, 'status': 'SUCCEEDED', 'label': '导出', 'feature': 'exports'}] * 2)
    e.tasks += [{'authority': 'workflows', 'id': 'failed', 'version': 2, 'status': 'FAILED', 'label': '工作流', 'feature': 'workflow'}]
    result = e.sessions.notices(e.ctx); assert len(result['items']) == 2
    focused = e.sessions.notices(e.ctx, True); assert len(focused['items']) == 1 and focused['deferred_count'] == 1
    assert focused['items'][0]['priority'] == 'urgent' and focused['save_failures_always_visible']
    event = next(item['event_id'] for item in result['items'] if item['kind'] == 'completion'); e.sessions.acknowledge(e.ctx, {'expected_version': 0, 'event_id': event})
    assert len(e.sessions.notices(e.ctx)['items']) == 1
    e.tasks[0]['version'] = 2; assert len(e.sessions.notices(e.ctx)['items']) == 2


def test_reminders_off_timezone_validated_no_executor_and_restart_metadata(env):
    e = env; preferences = e.sessions.preferences(e.ctx)
    assert not preferences['reminder']['enabled'] and not preferences['network_push'] and not preferences['model_execution']
    with pytest.raises(ValueError): e.sessions.save_preferences(e.ctx, {'expected_version': 0, 'reminder': {'timezone': 'Invented/Zone'}})
    result = e.sessions.save_preferences(e.ctx, {'expected_version': 0, 'reminder': {'enabled': True, 'time': '18:30', 'timezone': 'Asia/Shanghai'}})
    assert result['requires_open'] == 'TASK_CENTER' and result['restart'] == 'MISSED_REMINDERS_NOT_REPLAYED'
    assert e.sessions.save_preferences(e.ctx, {'expected_version': 1})['reminder']['enabled'] is False


def test_router_read_and_write_recheck_flag_scope_permissions(env):
    e = env; enabled = {'yes': True}; auth = {'deny': False, 'calls': 0, 'flip': False}
    def gate(flag):
        if not enabled['yes']: raise HTTPException(404)
    def authorize(nid, token, branch, permission):
        auth['calls'] += 1
        if auth['deny']: raise HTTPException(403)
        return ('different' if auth['flip'] and auth['calls'] % 2 == 0 else 'author'), e.ctx.scope
    app = FastAPI(); app.include_router(create_reader_preflight_router(e.reader, authorize, gate)); app.include_router(create_writing_sessions_router(e.sessions, authorize, gate))
    client = TestClient(app); base = f'/novels/{e.ctx.novel_id}/experimental'
    assert client.get(base + '/reader-preflight/read').headers['cache-control'] == 'no-store'
    assert client.get(base + '/writing-sessions').status_code == 200
    auth.update(calls=0, flip=True)
    assert client.post(base + '/writing-sessions', json={'capture_id': 'flip'}).status_code == 409
    assert not e.sessions.overview(e.ctx)['items']
    auth.update(calls=0, flip=False, deny=True)
    assert client.post(base + '/reader-preflight/check', json={}).status_code == 403
    auth['deny'] = False; enabled['yes'] = False
    for path in ('/reader-preflight/read', '/reader-preflight/proof', '/writing-sessions', '/writing-sessions/notices'):
        assert client.get(base + path).status_code == 404
    assert client.post(base + '/writing-sessions', json={'capture_id': 'off'}).status_code == 404


def test_preflight_tasks_and_candidates_are_explicitly_not_acceptance(env):
    e = env; e.tasks.append({'authority': 'media', 'id': 'media', 'status': 'REVIEW_REQUIRED', 'feature': 'assets', 'stale': True})
    e.reader.candidate_reader = lambda ctx: {'items': [{'chapter_id': e.cid}, {'chapter_id': 'denied'}], 'truncated': False}
    report = e.reader.preflight(e.ctx, {})
    codes = [f['code'] for f in report['findings']]
    assert codes.count('UNACCEPTED_GENERATION') == 1 and 'UNACCEPTED_CANDIDATE' in codes and 'STALE_REFERENCE' in codes
    assert not report['has_integrity_blockers'] and e.chapters.get(e.cid)['version'] == 2


def test_never_opened_legacy_chapter_read_preflight_does_not_materialize(env):
    e = env
    if e.store.backend != 'file': pytest.skip('legacy file boundary only')
    repo = e.chapters.repository.backend
    # create_chapter writes only Markdown; do not call ChapterService.get/list.
    legacy = repo.create_chapter(e.ctx.novel_id, {'title': 'Never opened', 'content': 'Only in markdown.'})
    root = repo.novels / e.ctx.novel_id
    before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    document = root / 'documents' / f"chapter-{legacy['number']:04d}.json"
    assert not document.exists()
    reading = e.reader.read(e.ctx)
    assert any(c['id'] == legacy['id'] for c in reading['chapters'])
    e.reader.preflight(e.ctx, {})
    e.sessions.overview(e.ctx)
    after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
    assert before == after and not document.exists()


def test_empty_title_only_chapter_and_export_snapshot_remains_immutable(env):
    e = env
    e.chapters.save(e.cid, {'version': 2, 'document': {'type': 'doc', 'content': [{'type': 'heading', 'attrs': {'level': 1}, 'content': [{'type': 'text', 'text': '空章'}]}]}})
    assert any(f['code'] == 'EMPTY_CHAPTER' for f in e.reader.preflight(e.ctx, {})['findings'])
    # Reuse the original immutable export authority, not this preflight report.
    snapshot = e.novels.export_snapshot(e.ctx.novel_id, format='txt')
    original = e.novels.export_snapshot_result(snapshot, 'txt')
    e.chapters.save(e.cid, {'version': 3, 'content': '后来的正文'})
    e.reader.preflight(e.ctx, {})
    assert e.novels.export_snapshot_result(snapshot, 'txt') == original
    assert '后来的正文' not in original['content']


def test_preflight_source_change_midcheck_fails_stale_without_persisting(env):
    e = env
    def candidate_reader(ctx):
        e.chapters.save(e.cid, {'version': 2, 'content': '被外部编辑的稿件'})
        return {'items': [], 'truncated': False}
    e.reader.candidate_reader = candidate_reader
    before = e.store.read(e.ctx.novel_id, e.ctx.scope)
    with pytest.raises(StaleSourceError): e.reader.preflight(e.ctx, {})
    assert e.store.read(e.ctx.novel_id, e.ctx.scope) == before


def test_completed_recap_counts_redacted_when_source_no_longer_accessible(env):
    e = env; session = e.sessions.start(e.ctx, {'capture_id': 'complete'})
    e.sessions.update(e.ctx, session['id'], {'expected_version': 1, 'complete': True})
    e.chapters.archive(e.cid, e.chapters.get(e.cid)['version'])
    recap = e.sessions.overview(e.ctx)['items'][0]['recap']
    assert recap['net_characters'] is None and recap['persisted_revision_events'] is None
    assert recap['statistics_scope'] == 'SOURCE_ACCESS_CHANGED'


def test_exact_allowlist_v1_off_and_dependency_gate(env, monkeypatch):
    from app.experimental.flags import require_flag
    e = env
    app = FastAPI(); authorize = lambda nid, token, branch, permission: (e.ctx.actor, e.ctx.scope)
    app.include_router(create_reader_preflight_router(e.reader, authorize, require_flag))
    app.include_router(create_writing_sessions_router(e.sessions, authorize, require_flag))
    client = TestClient(app); base = f'/novels/{e.ctx.novel_id}/experimental'
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false'); monkeypatch.setenv('EXPERIMENTAL_FEATURES', '*')
    assert client.get(base + '/reader-preflight/read').status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'reader_preflight_v2,writing_sessions_v2')
    assert client.get(base + '/reader-preflight/read').status_code == 200
    assert client.get(base + '/writing-sessions').status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'reader_preflight_v2,writing_sessions_v2,workspace_tools_v2')
    assert client.get(base + '/writing-sessions').status_code == 200
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.get(base + '/reader-preflight/read').status_code == 404
    assert client.get(base + '/writing-sessions/notices').status_code == 404
    assert client.post(base + '/writing-sessions', json={'capture_id': 'v1-off'}).status_code == 404


def test_config_limits_literal_regex_is_data_and_whitespace_rejected(env):
    e = env
    with pytest.raises(ValueError): e.reader.save_settings(e.ctx, {'expected_version': 0, 'rules': {'literals': [{'find': 'x', 'suggest': 'y'}] * 31}})
    e.reader.save_settings(e.ctx, {'expected_version': 0, 'rules': {'punctuation': False, 'repeated_words': False, 'literals': [{'find': '(a+)+$', 'suggest': 'literal'}]}})
    assert e.reader.proof(e.ctx)['items'] == []
    with pytest.raises(ValueError): e.sessions.start(e.ctx, {'capture_id': 'forged', 'actor': 'other'})
    with pytest.raises(ValueError): e.sessions.start(e.ctx, {'capture_id': 'duplicate', 'tasks': [{'id': 'x', 'text': 'first'}, {'id': 'x', 'text': 'second'}]})


def test_pdf_font_check_reuses_original_status_never_renders(env, monkeypatch):
    import app.pdf_export as pdf
    monkeypatch.setattr(pdf, 'pdf_font_status', lambda: {'available': True, 'embedded': False})
    report = env.reader.preflight(env.ctx, {'format': 'pdf'})
    assert {'area': 'pdf_font', 'state': 'FALLBACK'} in report['coverage']
    assert any(f['code'] == 'PDF_FONT_NOT_EMBEDDED' and f['severity'] == 'WARNING' for f in report['findings'])
    assert not report['target_renderer_verified']


def test_legacy_in_memory_revision_stays_stable_after_original_editor_opens(env):
    e = env
    if e.store.backend != 'file': pytest.skip('legacy file boundary only')
    legacy = e.chapters.repository.backend.create_chapter(e.ctx.novel_id, {'title': 'Legacy', 'content': '未打开的正文'})
    before = next(r for r in e.reader.read(e.ctx)['chapters'] if r['id'] == legacy['id'])
    e.chapters.get(legacy['id'])  # original editor is allowed to initialize it
    after = next(r for r in e.reader.read(e.ctx)['chapters'] if r['id'] == legacy['id'])
    assert before['revision'] == after['revision']
