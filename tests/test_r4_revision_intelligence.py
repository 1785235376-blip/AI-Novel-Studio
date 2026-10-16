"""A11/U05 original-authority contracts. File is real; PG explicitly requires its test DSN."""
from copy import deepcopy
import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.repositories.chapter_repository import VersionConflict
from app.services import ChapterService, NovelService
from app.experimental.store import ExperimentalStore
from app.experimental.common import StaleSourceError
from app.experimental.revision_intelligence import RevisionIntelligenceService, SelectionIn, selection_snapshot, text_blocks, utf16_size
from app.experimental.revision_intelligence_api import create_revision_intelligence_router
from app.revision_constraints import LOCK_ATTRIBUTE, RevisionConstraintError, assert_ai_locks, preserve_revision_constraints


def paragraph(text, **kw):
    return {'type': 'paragraph', **kw, 'content': [{'type': 'text', 'text': text}]}


def document(*nodes): return {'type': 'doc', 'content': list(nodes)}


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only), pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def revision_env(tmp_path, request):
    backend = request.param
    url = os.getenv('TEST_POSTGRES_DATABASE_URL', '') if backend == 'postgres' else ''
    if backend == 'postgres' and not url: pytest.skip('NOT_RUN: authorized real PostgreSQL endpoint unavailable')
    config = Settings(storage_backend=backend, database_url=url, novel_data=tmp_path, mock_provider=True, enable_cloud=False)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    chapters, novels = ChapterService(bundle.chapters), NovelService(bundle.novels, bundle.chapters)
    nid = 'revision-' + uuid4().hex
    novels.create({'id': nid, 'title': 'Synthetic revisions', 'genre': 'fantasy'})
    created = chapters.create(nid, {'title': '合成章节', 'content': 'temporary'})
    chapter = chapters.save(created['id'], {'version': created.get('version') or chapters.get(created['id'])['version'], 'document': document(paragraph('甲🙂e\u0301。'), paragraph('乙保留。'), paragraph('丙结尾。'))})
    store = ExperimentalStore(tmp_path, backend, url)
    service = RevisionIntelligenceService(store, novels, chapters, save_document=lambda cid, doc, version, source: chapters.save(cid, {'document': doc, 'version': version, 'source': source}))
    env = SimpleNamespace(service=service, store=store, chapters=chapters, novels=novels, nid=nid, cid=chapter['id'], chapter=chapter, scope={'mode': 'local', 'novel_id': nid}, backend=backend, bundle=bundle)
    yield env
    if backend == 'postgres':
        with store._connect() as connection: connection.execute('DELETE FROM experimental_scope_documents WHERE novel_id = %s', (nid,))
        novels.delete(nid)


def selection(e, first=0, last=None):
    chapter = e.chapters.get(e.cid); blocks = text_blocks(chapter['document']); last = first if last is None else last
    return {'chapter_id': e.cid, 'chapter_version': chapter['version'], 'from_pos': blocks[first]['start'], 'to_pos': blocks[last]['end'], 'text': '\n'.join(b['text'] for b in blocks[first:last + 1])}


def proposal(e, replacements=None, first=0, last=2, **extra):
    picked = selection(e, first, last); receipt = e.service.selection(e.nid, e.scope, picked)
    candidates = replacements or ['甲修改🙂e\u0301。', '乙改变。', '丙新结尾。'][first:last + 1]
    return e.service.create_proposal(e.nid, e.scope, 'author', {'selection': picked, 'selection_digest': receipt['selection_digest'], 'replacements': [{'anchor_id': b['anchor_id'], 'text': t} for b, t in zip(receipt['blocks'], candidates)], **extra})


def review(e, p, accepts=(), rejects=()):
    value = {'expected_version': p['version'], 'accept_ids': [p['blocks'][i]['anchor_id'] for i in accepts], 'reject_ids': [p['blocks'][i]['anchor_id'] for i in rejects]}
    receipt = e.service.preview(e.nid, e.scope, p['id'], value)
    return e.service.apply(e.nid, e.scope, 'author', p['id'], {**value, 'preview_digest': receipt['preview_digest']})


def lock(e, action='lock', block=0):
    picked = selection(e, block); receipt = e.service.selection(e.nid, e.scope, picked)
    return e.service.locks(e.nid, e.scope, 'author', {'selection': picked, 'selection_digest': receipt['selection_digest'], 'action': action})


def test_partial_accept_changes_only_two_reviewed_blocks_and_keeps_original_history(revision_env):
    e = revision_env; before = e.chapters.get(e.cid); p = proposal(e)
    result = review(e, p, (0, 2))
    saved = result['chapter']
    assert saved['document']['content'][1] == before['document']['content'][1]
    assert saved['document']['content'][0]['content'][0]['text'] == '甲修改🙂e\u0301。'
    assert saved['document']['content'][2]['content'][0]['text'] == '丙新结尾。'
    assert saved['version'] == before['version'] + 1
    assert result['proposal']['blocks'][1]['status'] == 'PENDING'
    assert e.chapters.history(e.cid)[0]['document'] == before['document']
    restarted = RevisionIntelligenceService(e.store, e.novels, e.chapters)
    assert restarted.proposal(e.nid, e.scope, p['id'])['stale']
    assert 'blocks' not in restarted.proposal(e.nid, e.scope, p['id'])
    with pytest.raises((StaleSourceError, ValueError)): review(e, p, (1,))


def test_reject_does_not_write_chapter_and_pending_still_reviewable(revision_env):
    e = revision_env; before = e.chapters.get(e.cid); p = proposal(e)
    result = review(e, p, (), (1,)); assert result['chapter'] is None
    assert e.chapters.get(e.cid) == before
    assert result['proposal']['blocks'][1]['status'] == 'REJECTED'
    assert review(e, result['proposal'], (0, 2))['chapter']['version'] == before['version'] + 1


@pytest.mark.parametrize('mode', ['version', 'document', 'privacy', 'branch'])
def test_stale_source_cannot_apply(revision_env, mode):
    e = revision_env; p = proposal(e)
    if mode == 'version': e.chapters.save(e.cid, {'version': e.chapter['version'], 'content': '另一个客户端'})
    elif mode == 'document':
        # This changes the authoritative document, even with equivalent Markdown.
        value = deepcopy(e.chapter['document']); value['content'][0]['content'][0]['marks'] = [{'type': 'bold'}]
        e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': value})
    elif mode == 'privacy':
        from app.source_privacy import content_digest, review_source_privacy
        review_source_privacy(e.chapter, None, 'author', 'CLOUD_ALLOWED', e.chapter['version'], content_digest(e.chapter), e.store.root)
    else: e.scope = {**e.scope, 'branch_id': 'other'}
    before = e.chapters.get(e.cid)
    with pytest.raises((StaleSourceError, ValueError, FileNotFoundError)): review(e, p, (0,))
    assert e.chapters.get(e.cid) == before


def test_exact_selection_disambiguates_duplicate_text_and_utf16(revision_env):
    e = revision_env; doc = document(paragraph('同名🙂e\u0301'), paragraph('同名🙂e\u0301'))
    e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': doc})
    chosen = selection(e, 1); receipt = e.service.selection(e.nid, e.scope, chosen)
    p = e.service.create_proposal(e.nid, e.scope, 'author', {'selection': chosen, 'selection_digest': receipt['selection_digest'], 'replacements': [{'anchor_id': receipt['blocks'][0]['anchor_id'], 'text': '只改第二处🙂e\u0301'}]})
    after = review(e, p, (0,))['chapter']['document']
    assert after['content'][0] == doc['content'][0]
    assert after['content'][1]['content'][0]['text'] == '只改第二处🙂e\u0301'


@pytest.mark.parametrize('text,from_pos,to_pos', [('🙂甲', 2, 3), ('e\u0301甲', 1, 2), ('👩\u200d💻甲', 1, 3), ('🇹🇼甲', 1, 3), ('👍🏽甲', 1, 3)])
def test_reject_split_unicode_boundaries(text, from_pos, to_pos):
    with pytest.raises(ValueError): selection_snapshot(document(paragraph(text)), SelectionIn(chapter_id='n:1', chapter_version=1, from_pos=from_pos, to_pos=to_pos, text='irrelevant'))


def test_hardbreak_and_nested_blocks_preserve_rich_semantics(revision_env):
    e = revision_env
    first = {'type': 'paragraph', 'attrs': {'align': 'left'}, 'content': [{'type': 'text', 'text': '前', 'marks': [{'type': 'bold'}]}, {'type': 'text', 'text': '中🙂'}, {'type': 'hardBreak'}, {'type': 'text', 'text': '后'}, {'type': 'text', 'text': '尾', 'marks': [{'type': 'italic'}]}]}
    doc = document({'type': 'blockquote', 'content': [first]}, {'type': 'bulletList', 'content': [{'type': 'listItem', 'content': [paragraph('列表留着')]}]})
    current = e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': doc})
    picked = {'chapter_id': e.cid, 'chapter_version': current['version'], 'from_pos': 3, 'to_pos': 8, 'text': '中🙂\n后'}
    receipt = e.service.selection(e.nid, e.scope, picked)
    p = e.service.create_proposal(e.nid, e.scope, 'author', {'selection': picked, 'selection_digest': receipt['selection_digest'], 'replacements': [{'anchor_id': receipt['blocks'][0]['anchor_id'], 'text': '新🙂\n行'}]})
    saved = review(e, p, (0,))['chapter']['document']; content = saved['content'][0]['content'][0]['content']
    assert content[0] == first['content'][0] and content[-1] == first['content'][-1]
    assert saved['content'][1] == doc['content'][1]
    assert {'type': 'hardBreak'} in content


def test_mixed_marks_reject_candidate_without_flattening(revision_env):
    e = revision_env
    doc = document({'type': 'paragraph', 'content': [{'type': 'text', 'text': '甲', 'marks': [{'type': 'bold'}]}, {'type': 'text', 'text': '乙'}]})
    e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': doc})
    with pytest.raises(ValueError, match='mixed'): proposal(e, ['新文'], 0, 0)
    assert e.chapters.get(e.cid)['document'] == doc


def test_paragraph_lock_survives_legacy_markdown_user_edit_and_blocks_every_ai_accept(revision_env, monkeypatch):
    e = revision_env; locked = lock(e)
    assert locked['version'] == e.chapter['version'] + 1
    for flags, v1 in [('', 'false'), ('revision_intelligence_v2', 'false'), ('revision_intelligence_v2', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        with pytest.raises(RevisionConstraintError): e.chapters.save(e.cid, {'version': locked['version'], 'content': 'AI overwrite', 'source': 'AI_ACCEPT'})
        assert e.chapters.get(e.cid) == locked
    edited = e.chapters.save(e.cid, {'version': locked['version'], 'content': '手动修改。\n\n乙保留。\n\n丙结尾。', 'source': 'USER'})
    assert LOCK_ATTRIBUTE in edited['document']['content'][0]['attrs']
    assert e.service.catalog(e.nid, e.scope, e.cid)['blocks'][0]['lock_state'] == 'STALE'
    with pytest.raises(RevisionConstraintError): e.chapters.save(e.cid, {'version': edited['version'], 'document': edited['document'], 'source': 'AI_ACCEPT'})
    unlocked = lock(e, 'unlock')
    assert unlocked['document']['content'][0]['attrs'][LOCK_ATTRIBUTE]['state'] == 'UNLOCKED'
    p = proposal(e, ['明确解锁后修订'], 0, 0); assert review(e, p, (0,))['chapter']


def test_lock_allows_unlocked_block_and_original_restore_creates_current_revision(revision_env):
    e = revision_env; locked = lock(e); original_history = deepcopy(e.chapters.history(e.cid))
    p = proposal(e, ['第二段修订'], 1, 1)
    saved = review(e, p, (0,))['chapter']
    assert saved['document']['content'][0] == locked['document']['content'][0]
    restored = e.chapters.restore(e.cid, locked['version'], saved['version'])
    assert restored['version'] == saved['version'] + 1 and restored['document'] == locked['document']
    assert e.chapters.history(e.cid)[-len(original_history):] == original_history


def test_lock_creation_cas_defeats_concurrent_ai_candidate(revision_env):
    e = revision_env; p = proposal(e); lock(e)
    with pytest.raises(StaleSourceError): review(e, p, (0,))


def test_semantic_assessment_requires_exact_changed_quote_evidence(revision_env):
    e = revision_env; picked = selection(e, 0); receipt = e.service.selection(e.nid, e.scope, picked); anchor = receipt['blocks'][0]['anchor_id']
    body = {'selection': picked, 'selection_digest': receipt['selection_digest'], 'replacements': [{'anchor_id': anchor, 'text': '甲改变。'}], 'explanations': [{'anchor_id': anchor, 'kind': 'motivation', 'explanation': '假设更直接', 'before_quote': '不存在', 'after_quote': '改变', 'source': 'IMPORTED_MODEL_ASSESSMENT'}]}
    with pytest.raises(ValueError, match='quote'): e.service.create_proposal(e.nid, e.scope, 'author', body)
    body['explanations'][0]['before_quote'] = '甲'
    result = e.service.create_proposal(e.nid, e.scope, 'author', body)
    assert result['model_called'] is False
    assert result['explanations'][0]['source'] == 'IMPORTED_MODEL_ASSESSMENT'
    assert result['blocks'][0]['diff_method'] == 'EXACT_CODEPOINT_DIFF'


def test_generation_full_chapter_output_is_not_silently_adopted(revision_env):
    e = revision_env; picked = selection(e, 0); receipt = e.service.selection(e.nid, e.scope, picked)
    job = {'id': 'job', 'status': 'COMPLETED', 'novel_id': e.nid, 'chapter_id': e.cid, 'base_chapter_version': e.chapter['version'], 'source': picked['text'], 'output': '全章第一段\n全章第二段'}
    job.update(partial_revision_only=True, revision_selection_binding={'selection': picked, 'selection_digest': receipt['selection_digest']})
    e.service.read_job = lambda jid: deepcopy(job)
    with pytest.raises(ValueError, match='unrepresentable'):
        e.service.create_proposal(e.nid, e.scope, 'author', {'selection': picked, 'selection_digest': receipt['selection_digest'], 'job_id': 'job', 'replacements': [{'anchor_id': receipt['blocks'][0]['anchor_id'], 'text': job['output']}]})
    assert e.chapters.get(e.cid) == e.chapter


def test_generated_derivative_rechecks_origin_before_preview_and_apply(revision_env):
    e = revision_env; picked = selection(e, 0); allowed = [True]
    job = {'id': 'job', 'status': 'COMPLETED', 'novel_id': e.nid, 'chapter_id': e.cid, 'base_chapter_version': e.chapter['version'], 'source': picked['text'], 'output': '新段落'}
    def read(jid):
        if not allowed[0]: raise HTTPException(404, {'code': 'ORIGIN_DISABLED'})
        return job
    job.update(partial_revision_only=True, revision_selection_binding={'selection': picked, 'selection_digest': e.service.selection(e.nid, e.scope, picked)['selection_digest']})
    e.service.read_job = read
    p = proposal(e, ['新段落'], 0, 0, job_id='job')
    value = {'expected_version': p['version'], 'accept_ids': [p['blocks'][0]['anchor_id']]}
    preview = e.service.preview(e.nid, e.scope, p['id'], value)
    allowed[0] = False
    for operation in [lambda: e.service.proposal(e.nid, e.scope, p['id']), lambda: e.service.preview(e.nid, e.scope, p['id'], value), lambda: e.service.apply(e.nid, e.scope, 'author', p['id'], {**value, 'preview_digest': preview['preview_digest']})]:
        with pytest.raises(HTTPException): operation()
    assert e.chapters.get(e.cid) == e.chapter


def test_interrupted_acceptance_claim_is_durable_and_never_replayed(revision_env):
    e = revision_env; p = proposal(e); writer = e.service.save_document
    def uncertain(*args): writer(*args); raise RuntimeError('test interruption after chapter saved')
    e.service.save_document = uncertain
    with pytest.raises(RuntimeError): review(e, p, (0,))
    after = e.chapters.get(e.cid)
    assert after['version'] == e.chapter['version'] + 1
    assert e.service.get(e.nid, e.scope, e.service.COLLECTION, p['id'])['status'] == 'ACCEPTANCE_UNCERTAIN'
    with pytest.raises(ValueError): review(e, p, (0,))
    assert e.chapters.get(e.cid) == after


def test_milestone_references_original_version_without_duplicate_manuscript(revision_env):
    e = revision_env
    result = e.service.milestone(e.nid, e.scope, 'author', {'chapter_id': e.cid, 'chapter_version': e.chapter['version'], 'title': '一稿', 'goal': '修订人物目标'})
    assert result['storage'] == 'ORIGINAL_CHAPTER_VERSION_REFERENCE' and not result['copies_document']
    assert 'document' not in result and e.chapters.get(e.cid) == e.chapter


def test_router_off_v1_and_final_authority_fence(revision_env, monkeypatch):
    from app.experimental.flags import require_flag
    e = revision_env; allowed = [True]
    def authorize(nid, token, branch, permission):
        if not allowed[0]: raise HTTPException(403, {'code': 'REVOKED'})
        return 'author', e.scope
    app = FastAPI(); app.include_router(create_revision_intelligence_router(e.service, authorize, require_flag))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/revisions'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ''); assert client.get(base + '/catalog').status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'revision_intelligence_v2'); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.post(base + '/selection', json=selection(e)).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    response = client.post(base + '/selection', json=selection(e)); assert response.status_code == 200, response.text
    assert response.headers['cache-control'] == 'no-store'
    original = e.service.selection
    def revoke(*args): result = original(*args); allowed[0] = False; return result
    monkeypatch.setattr(e.service, 'selection', revoke)
    response = client.post(base + '/selection', json=selection(e))
    assert response.status_code == 403 and '甲' not in response.text


def test_explicit_remaining_review_reuses_only_unchanged_anchors(revision_env):
    e = revision_env; p = proposal(e)
    partial = review(e, p, (0, 2))['proposal']; current = e.chapters.get(e.cid)
    fresh = e.service.rebase(e.nid, e.scope, 'author', partial['id'], {'expected_version': partial['version'], 'chapter_version': current['version']})
    assert len(fresh['blocks']) == 1 and fresh['blocks'][0]['before'] == '乙保留。'
    assert fresh['id'] != partial['id'] and fresh['source_proposal_id'] == partial['id']
    assert e.chapters.get(e.cid) == current
    final = review(e, fresh, (0,))['chapter']
    assert final['document']['content'][0] == current['document']['content'][0]
    assert final['document']['content'][2] == current['document']['content'][2]
    assert final['document']['content'][1]['content'][0]['text'] == '乙改变。'


def test_external_change_defeats_remaining_relocation(revision_env):
    e = revision_env; p = proposal(e); partial = review(e, p, (0,))['proposal']
    current = e.chapters.get(e.cid); changed = e.chapters.save(e.cid, {'version': current['version'], 'content': '其他客户端已改正文'})
    with pytest.raises(StaleSourceError): e.service.rebase(e.nid, e.scope, 'author', partial['id'], {'expected_version': partial['version'], 'chapter_version': changed['version']})


def test_existing_audited_persistence_honors_lock_without_audit_or_history_side_effect(revision_env):
    from app.application.persistence import create_atomic_chapter_audit_port
    e = revision_env; locked = lock(e); before_history = e.chapters.history(e.cid)
    port = create_atomic_chapter_audit_port(e.bundle.chapters, e.bundle.authorization)
    event = {'id': str(uuid4()), 'actor_id': 'synthetic-author', 'action': 'CHAPTER_UPDATED', 'target_type': 'Chapter', 'target_id': e.cid, 'scope': {}, 'metadata': {}}
    before_audit = e.bundle.authorization.list_audit_events()
    with pytest.raises(RevisionConstraintError):
        port.save_chapter_with_audit(e.cid, document(paragraph('forbidden')), locked['version'], 'AI_ACCEPT', 'synthetic-author', event)
    assert e.chapters.get(e.cid) == locked
    assert e.chapters.history(e.cid) == before_history
    assert e.bundle.authorization.list_audit_events() == before_audit


def test_selection_and_replacement_preserve_exact_whitespace_and_newlines(revision_env):
    e = revision_env; before = '  首行\n尾行  '
    current = e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': document(paragraph(before))})
    chosen = selection(e); snapshot = e.service.selection(e.nid, e.scope, chosen)
    assert snapshot['selection']['text'] == before
    after = '  新首行\n\n新尾行 \n'
    p = e.service.create_proposal(e.nid, e.scope, 'author', {'selection': chosen, 'selection_digest': snapshot['selection_digest'], 'replacements': [{'anchor_id': snapshot['blocks'][0]['anchor_id'], 'text': after}]})
    assert p['blocks'][0]['after'] == after
    final = review(e, p, (0,))['chapter']
    assert text_blocks(final['document'])[0]['text'] == after


def test_corrupt_marker_stays_failclosed_until_explicit_versioned_unlock(revision_env):
    e = revision_env; doc = deepcopy(e.chapter['document']); doc['content'][0]['attrs'] = {LOCK_ATTRIBUTE: 'unknown-marker'}
    current = e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': doc})
    with pytest.raises(RevisionConstraintError): e.chapters.save(e.cid, {'version': current['version'], 'document': doc, 'source': 'AI_ACCEPT'})
    unlocked = lock(e, 'unlock')
    assert unlocked['document']['content'][0]['attrs'][LOCK_ATTRIBUTE]['state'] == 'UNLOCKED'


def test_concurrent_different_review_claims_have_one_original_cas_winner(revision_env):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    e = revision_env; a = proposal(e); b = proposal(e)
    requests = []
    for p in (a, b):
        value = {'expected_version': p['version'], 'accept_ids': [p['blocks'][0]['anchor_id']]}
        preview = e.service.preview(e.nid, e.scope, p['id'], value)
        requests.append((p['id'], {**value, 'preview_digest': preview['preview_digest']}))
    original = e.service.save_document; barrier = Barrier(2)
    def write(*args): barrier.wait(timeout=10); return original(*args)
    e.service.save_document = write
    def run(request):
        try: return e.service.apply(e.nid, e.scope, 'author', request[0], request[1])
        except VersionConflict: return None
    with ThreadPoolExecutor(max_workers=2) as pool: results = list(pool.map(run, requests))
    assert sum(result is not None for result in results) == 1
    assert e.chapters.get(e.cid)['version'] == e.chapter['version'] + 1
    statuses = [e.service.get(e.nid, e.scope, e.service.COLLECTION, p['id'])['status'] for p in (a, b)]
    assert sorted(statuses) == ['ACCEPTANCE_UNCERTAIN', 'PARTIAL']


def test_repeated_acceptance_cannot_reapply_reviewed_block(revision_env):
    e = revision_env; p = proposal(e); result = review(e, p, (0, 1, 2)); current = e.chapters.get(e.cid)
    with pytest.raises(ValueError): review(e, result['proposal'], (0,))
    assert e.chapters.get(e.cid) == current


def test_emptied_locked_paragraph_has_explicit_version_and_digest_bound_recovery(revision_env):
    e = revision_env; locked = lock(e); doc = deepcopy(locked['document']); doc['content'][0].pop('content')
    empty = e.chapters.save(e.cid, {'version': locked['version'], 'document': doc})
    catalog = e.service.catalog(e.nid, e.scope, e.cid)
    assert catalog['blocks'][0]['text'] == '' and catalog['blocks'][0]['lock_state'] == 'STALE'
    with pytest.raises(StaleSourceError): e.service.unlock_block(e.nid, e.scope, 'author', {'chapter_id': e.cid, 'chapter_version': locked['version'], 'path': [0], 'document_digest': catalog['document_digest']})
    result = e.service.unlock_block(e.nid, e.scope, 'author', {'chapter_id': e.cid, 'chapter_version': empty['version'], 'path': [0], 'document_digest': catalog['document_digest']})
    assert result['document']['content'][0]['attrs'][LOCK_ATTRIBUTE]['state'] == 'UNLOCKED'
