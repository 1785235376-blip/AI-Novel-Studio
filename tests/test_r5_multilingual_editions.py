"""B05 real storage, deterministic terminology/Unicode/review/privacy contracts."""
from copy import deepcopy
import hashlib
import json

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from test_r4_revision_intelligence import revision_env, paragraph, document
from app.experimental.common import StaleSourceError
from app.experimental.multilingual_editions import (
    MultilingualEditionsService, EditionIn, SegmentIn, RuleIn, language_code,
    terminology_issues, contains,
)
from app.experimental.multilingual_editions_api import create_multilingual_editions_router
from app.services.v1_capability_service import CapabilityVersionConflict


@pytest.fixture
def editions_env(revision_env):
    e = revision_env
    e.service = MultilingualEditionsService(e.store, e.novels, e.chapters)
    return e


def create(e, **kw):
    return e.service.create_edition(e.nid, e.scope, 'author', {'title': '合成 Arabic edition', 'source_language': 'zh-Hant', 'target_language': 'ar', 'chapters': [{'chapter_id': e.cid, 'chapter_version': e.chapters.get(e.cid)['version']}], **kw})


def save(e, row, text='ترجمة 🙂 e\u0301 العربية', index=0, **kw):
    return e.service.save_segment(e.nid, e.scope, 'author', row['id'], row['segments'][index]['id'], {'expected_version': row['version'], 'text': text, **kw})


def review(e, row, action, index=0, **kw):
    return e.service.review_segment(e.nid, e.scope, 'author', row['id'], row['segments'][index]['id'], {'expected_version': row['version'], 'action': action, **kw})


def accept(e, row, index=0):
    row = review(e, row, 'submit', index) if row['segments'][index]['status'] != 'REVIEW' else row
    p = e.service.preview_segment(e.nid, e.scope, 'author', row['id'], row['segments'][index]['id'], {'expected_version': row['version']})
    return review(e, row, 'accept', index, preview_digest=p['preview_digest'])


def rule(e, row, **kw):
    row = e.service.add_rule(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'source_term': '甲', 'preferred': 'Jia', 'forbidden': ['BadJia'], **kw})
    return e.service.review_rule(e.nid, e.scope, 'author', row['id'], row['rules'][-1]['id'], {'expected_version': row['version'], 'action': 'approve'})


def test_independent_language_edition_reviewed_export_never_changes_original(editions_env):
    e = editions_env; original = e.chapters.get(e.cid); history = e.chapters.history(e.cid)
    row = create(e)
    assert row['direction'] == 'rtl' and row['privacy_level'] == 'LOCAL_ONLY'
    assert row['storage_contract'] == 'INDEPENDENT_LANGUAGE_EDITION_NOT_MANUSCRIPT_BRANCH'
    assert len(row['segments']) == 3 and len(row['checks']['missing']) == 3
    for index in range(3):
        row = accept(e, save(e, row, f'ترجمة {index} 🙂e\u0301 <script>bad()</script>', index), index)
    assert row['status'] == 'ACCEPTED' and row['checks']['can_export']
    for format in ['txt', 'html', 'json']:
        data = {'expected_version': row['version'], 'format': format}
        preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], data)
        output = e.service.export(e.nid, e.scope, 'author', row['id'], {**data, 'preview_digest': preview['preview_digest']})
        assert output['encoding'] == 'UTF-8' and output['published'] is False and output['model_called'] is False
        assert hashlib.sha256(output['content'].encode('utf-8')).hexdigest() == output['sha256']
        assert output['content'].encode('utf-8').decode('utf-8') == output['content']
        if format == 'html':
            assert '<html lang="ar" dir="rtl">' in output['content'] and '<meta charset="utf-8">' in output['content']
            assert '<script>' not in output['content'] and '&lt;script&gt;' in output['content']
        if format == 'json':
            package = json.loads(output['content']); assert len(package['segments']) == 3
            assert package['segments'][0]['source_version'] == original['version']
    assert e.chapters.get(e.cid) == original and e.chapters.history(e.cid) == history
    restarted = MultilingualEditionsService(e.store, e.novels, e.chapters)
    assert restarted.edition(e.nid, e.scope, 'author', row['id'])['segments'][0]['target_text'].startswith('ترجمة')
    assert restarted.editions(e.nid, e.scope, 'other')['items'] == []
    with pytest.raises(FileNotFoundError): restarted.edition(e.nid, e.scope, 'other', row['id'])


def test_terms_aliases_forbidden_transliteration_and_approval_trace(editions_env):
    e = editions_env; row = rule(e, create(e), source_aliases=['阿甲'], target_aliases=['Chia'], category='character', strategy='transliteration')
    rule_record = row['rules'][0]
    assert rule_record['reviewed_by'] == 'author' and rule_record['reviewed_at'] and rule_record['version'] == 2
    row = review(e, save(e, row, 'BadJia'), 'submit')
    issues = row['segments'][0]['issues']; assert {i['code'] for i in issues} == {'TERM_FORBIDDEN'}  # Literal substring includes Jia.
    with pytest.raises(ValueError): accept(e, row)
    row = accept(e, save(e, row, 'Chia 🙂e\u0301'))
    assert row['segments'][0]['accepted_term_revision'] == row['term_revision']
    row = rule(e, row, source_term='乙', preferred='Yi', forbidden=[])
    assert row['segments'][0]['status'] == 'REVIEW' and not row['checks']['can_export']
    row = e.service.review_rule(e.nid, e.scope, 'author', row['id'], row['rules'][1]['id'], {'expected_version': row['version'], 'action': 'revoke'})
    assert row['rules'][1]['status'] == 'REVOKED'
    assert e.chapters.get(e.cid) == e.chapter


def test_rule_conflicts_and_missing_translation_block_accept_and_export(editions_env):
    e = editions_env; row = rule(e, create(e)); row = rule(e, row, preferred='OtherJia', forbidden=[])
    row = review(e, save(e, row, 'Jia OtherJia'), 'submit')
    assert 'RULE_CONFLICT' in {i['code'] for i in row['segments'][0]['issues']}
    with pytest.raises(ValueError): accept(e, row)
    data = {'expected_version': row['version'], 'format': 'txt'}
    preview = e.service.export_preview(e.nid, e.scope, 'author', row['id'], data)
    assert not preview['can_export'] and len(preview['checks']['missing']) == 2
    with pytest.raises(ValueError): e.service.export(e.nid, e.scope, 'author', row['id'], {**data, 'preview_digest': preview['preview_digest']})


def test_exact_unicode_duplicate_paragraph_alignment(editions_env):
    e = editions_env
    current = e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': document(paragraph('同名🙂e\u0301'), paragraph('同名🙂e\u0301'), {'type': 'blockquote', 'content': [paragraph('مرحبا “甲”')]} )})
    row = create(e); assert row['segments'][0]['id'] != row['segments'][1]['id']
    assert row['segments'][0]['to_pos'] - row['segments'][0]['from_pos'] == 6
    assert row['segments'][2]['path'] == [2, 0]
    row = accept(e, save(e, row, 'Only second 🙂e\u0301', 1), 1)
    assert row['segments'][0]['target_text'] == '' and row['segments'][1]['target_text'] == 'Only second 🙂e\u0301'
    assert e.chapters.get(e.cid) == current


@pytest.mark.parametrize('drift', ['version', 'formatting', 'privacy', 'deleted'])
def test_source_changes_withhold_all_plaintext_and_block_late_accept(editions_env, drift):
    e = editions_env; row = rule(e, save(e, create(e), 'PRIVATE TARGET'))
    row = review(e, row, 'submit')
    preview = e.service.preview_segment(e.nid, e.scope, 'author', row['id'], row['segments'][0]['id'], {'expected_version': row['version']})
    if drift == 'version': e.chapters.save(e.cid, {'version': e.chapter['version'], 'content': 'changed'})
    elif drift == 'formatting':
        doc = deepcopy(e.chapter['document']); doc['content'][0]['content'][0]['marks'] = [{'type': 'bold'}]
        e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': doc})
    elif drift == 'privacy':
        from app.source_privacy import content_digest, review_source_privacy
        review_source_privacy(e.chapter, None, 'author', 'CLOUD_ALLOWED', e.chapter['version'], content_digest(e.chapter), e.store.root)
    else: e.chapters.delete(e.cid)
    view = e.service.edition(e.nid, e.scope, 'author', row['id'])
    assert view['stale'] and view['content_withheld']
    assert not {'segments', 'rules', 'history', 'title', 'style_note', 'archived_segments'} & set(view)
    assert 'PRIVATE TARGET' not in json.dumps(e.service.editions(e.nid, e.scope, 'author'))
    with pytest.raises((StaleSourceError, FileNotFoundError)): review(e, row, 'accept', preview_digest=preview['preview_digest'])


def test_explicit_source_refresh_retains_exact_anchors_and_reopens_all(editions_env):
    e = editions_env; row = accept(e, save(e, create(e), 'keep first'))
    row = accept(e, save(e, row, 'archive changed second', 1), 1)
    doc = deepcopy(e.chapter['document']); doc['content'][1] = paragraph('new second🙂')
    e.chapters.save(e.cid, {'version': e.chapter['version'], 'document': doc})
    receipt = e.service.refresh_preview(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version']})
    assert receipt['retained_exact'] == 2 and receipt['new_or_changed'] == receipt['archived_old'] == 1
    updated = e.service.refresh_sources(e.nid, e.scope, 'author', row['id'], {'expected_version': row['version'], 'preview_digest': receipt['preview_digest']})
    assert updated['segments'][0]['target_text'] == 'keep first' and updated['segments'][1]['target_text'] == ''
    assert updated['segments'][1]['source_text'] == 'new second🙂'
    assert updated['archived_segments'][0]['target_text'] == 'archive changed second'
    assert updated['archived_segments'][0]['source_version'] == e.chapter['version']
    assert all(s['status'] == 'DRAFT' for s in updated['segments'])
    stored = e.service.get(e.nid, e.scope, e.service.COLLECTION, row['id'])
    assert any(s['target_text'] == 'archive changed second' for s in stored['history'][-1]['segments'])
    assert 'history' not in updated


def test_refresh_preview_and_segment_review_bind_exact_versions(editions_env):
    e = editions_env; row = review(e, save(e, create(e), 'first'), 'submit')
    p = e.service.preview_segment(e.nid, e.scope, 'author', row['id'], row['segments'][0]['id'], {'expected_version': row['version']})
    changed = save(e, row, 'second')
    with pytest.raises(CapabilityVersionConflict) as exc: review(e, row, 'accept', preview_digest=p['preview_digest'])
    assert set(exc.value.current) == {'id', 'version', 'status'}
    changed = review(e, changed, 'submit')
    with pytest.raises(StaleSourceError): review(e, changed, 'accept', preview_digest=p['preview_digest'])
    rp = e.service.refresh_preview(e.nid, e.scope, 'author', changed['id'], {'expected_version': changed['version']})
    e.chapters.save(e.cid, {'version': e.chapter['version'], 'content': 'other'})
    with pytest.raises(StaleSourceError): e.service.refresh_sources(e.nid, e.scope, 'author', changed['id'], {'expected_version': changed['version'], 'preview_digest': rp['preview_digest']})


def test_final_authority_failure_rolls_back_whole_write(editions_env):
    e = editions_env; row = create(e); before = e.store.read(e.nid, e.scope); called = []
    def revoke():
        called.append(1)
        if len(called) >= 3: raise HTTPException(403, {'code': 'REVOKED'})
    with pytest.raises(HTTPException):
        e.service.save_segment(e.nid, e.scope, 'author', row['id'], row['segments'][0]['id'], {'expected_version': row['version'], 'text': 'not committed'}, reauthorize=revoke)
    assert e.store.read(e.nid, e.scope) == before


def test_branch_actor_and_project_sources_are_never_borrowed(editions_env):
    e = editions_env; row = create(e)
    other = {**e.scope, 'mode': 'collaboration', 'workspace_id': 'w', 'storyline_id': 's', 'branch_id': 'other'}
    assert e.service.catalog(e.nid, other)['chapters'] == []
    assert e.service.editions(e.nid, other, 'author')['items'] == []
    with pytest.raises(ValueError): e.service.create_edition(e.nid, other, 'author', {'title': 'wrong', 'source_language': 'zh', 'target_language': 'en', 'chapters': [{'chapter_id': e.cid, 'chapter_version': e.chapter['version']}]})
    with pytest.raises(FileNotFoundError): e.service.save_segment(e.nid, e.scope, 'other', row['id'], row['segments'][0]['id'], {'expected_version': row['version'], 'text': 'other'})


def test_multiple_chapters_preserve_order_and_reject_duplicates(editions_env):
    e = editions_env; extra = e.chapters.create(e.nid, {'title': 'two', 'content': '第二章'})
    extra = e.chapters.get(extra['id'])
    selected = [{'chapter_id': extra['id'], 'chapter_version': extra['version']}, {'chapter_id': e.cid, 'chapter_version': e.chapter['version']}]
    row = create(e, chapters=selected)
    assert row['segments'][0]['chapter_id'] == extra['id']
    assert len(row['sources']) == 2
    with pytest.raises(ValueError, match='duplicate'): create(e, chapters=selected + selected)


def test_router_flag_v1_and_no_store_without_model_or_side_effect(editions_env, monkeypatch):
    from app.experimental.flags import require_flag
    e = editions_env; allowed = [True]
    def authorize(nid, token, branch, permission):
        if not allowed[0]: raise HTTPException(403, {'code': 'REVOKED'})
        return 'author', e.scope
    app = FastAPI(); app.include_router(create_multilingual_editions_router(e.service, authorize, require_flag))
    client = TestClient(app); base = f'/novels/{e.nid}/experimental/language-editions'
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', ''); assert client.get(base + '/catalog').status_code == 404
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', 'multilingual_editions_v2'); monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
    assert client.get(base).status_code == 404
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'false')
    r = client.get(base + '/catalog'); assert r.status_code == 200, r.text
    assert r.headers['cache-control'] == 'no-store' and r.json()['translation']['available'] is False
    original = e.service.catalog
    def revoked(*args): result = original(*args); allowed[0] = False; return result
    monkeypatch.setattr(e.service, 'catalog', revoked)
    r = client.get(base + '/catalog'); assert r.status_code == 403 and '合成' not in r.text


@pytest.mark.parametrize('value', ['en/../../path', 'ar\" onload=\"x', '', 'x', 'zh_' , 'en-' + 'a' * 9])
def test_language_tags_reject_path_and_markup(value):
    with pytest.raises(ValueError): language_code(value)


def test_unicode_rules_are_literal_bounded_and_preservation_is_exact():
    assert contains('Alice!', 'Alice', 'word') and not contains('Malice', 'alice', 'word')
    assert contains('阿甲🙂', '甲', 'substring') and not contains('e\u0301', 'é', 'substring')
    with pytest.raises(ValidationError): SegmentIn(expected_version=1, text='\ud800')
    with pytest.raises(ValidationError): RuleIn(expected_version=1, source_term='甲', preferred='A', strategy='preserve')
    with pytest.raises(ValidationError): RuleIn(expected_version=1, source_term='甲', preferred='A', forbidden=['A'])
    with pytest.raises(ValidationError): RuleIn(expected_version=1, source_term='甲', preferred='甲', strategy='preserve', target_aliases=['translated'])
