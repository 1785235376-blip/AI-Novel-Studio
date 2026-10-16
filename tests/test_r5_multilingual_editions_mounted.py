"""B05 production mounted API, real File/PG and trusted authorization stack."""
import json
import pytest
from test_r3_mounted_contracts import mounted, prefix, checked, scoped


@pytest.fixture
def editions(mounted):
    e = mounted
    e.path = e.base + '/language-editions'
    e.editions = e.experimental.multilingual_editions_service
    return e


def create(e):
    return checked(e.client.post(e.path, json={'title': 'Private edition title', 'source_language': 'en', 'target_language': 'ar',
        'style_note': 'Private style note', 'chapters': [{'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version']}]}), 201)


def test_actual_mounted_bilingual_review_and_utf8_download(editions):
    e = editions; original = e.chapters.get(e.chapter['id']); row = create(e)
    capability = checked(e.client.get(e.path + '/catalog'))['translation']
    assert capability['available'] is True and capability['execution_authorized'] is False and not capability['model_called']
    for index in range(len(row['segments'])):
        sid = row['segments'][index]['id']; base = e.path + f"/{row['id']}/segments/{sid}"
        row = checked(e.client.put(base, json={'expected_version': row['version'], 'text': 'ترجمة سرية🙂é'}))
        row = checked(e.client.post(base + '/review', json={'expected_version': row['version'], 'action': 'submit'}))
        p = checked(e.client.post(base + '/preview', json={'expected_version': row['version']}))
        row = checked(e.client.post(base + '/review', json={'expected_version': row['version'], 'action': 'accept', 'preview_digest': p['preview_digest']}))
    base = e.path + '/' + row['id']
    preview = checked(e.client.post(base + '/export-preview', json={'expected_version': row['version'], 'format': 'html'}))
    output = checked(e.client.post(base + '/export', json={'expected_version': row['version'], 'format': 'html', 'preview_digest': preview['preview_digest']}))
    assert 'ترجمة سرية🙂é' in output['content'] and 'dir="rtl"' in output['content']
    assert e.chapters.get(e.chapter['id']) == original
    assert checked(e.client.get(base))['status'] == 'ACCEPTED'
    assert e.client.get(base).headers['cache-control'] == 'no-store'
    # Existing source/legacy review surfaces never discover private edition prose.
    for url in [e.prefix + f"/chapters/{e.chapter['id']}", e.prefix + f"/chapters/{e.chapter['id']}/history", e.base + '/revisions/proposals', e.base + '/review-inbox', e.base + '/world/canon']:
        response = e.client.get(url)
        assert response.status_code == 200, response.text
        assert 'ترجمة سرية' not in response.text and 'Private edition title' not in response.text


def test_actual_off_v1_all_routes_and_legacy_surfaces_withhold_existing_content(editions, monkeypatch):
    e = editions; row = create(e); sid = row['segments'][0]['id']; item = e.path + '/' + row['id']
    checked(e.client.put(item + '/segments/' + sid, json={'expected_version': 1, 'text': 'LEAK_SENTINEL_PRIVATE'}))
    before = e.store.read(e.nid, e.scope)
    for flags, v1 in [('', 'false'), ('*', 'false'), ('multilingual_editions_v2', 'true')]:
        monkeypatch.setenv('EXPERIMENTAL_FEATURES', flags); monkeypatch.setenv('V1_ACCEPTANCE_MODE', v1)
        for url in [e.path, e.path + '/catalog', item]:
            response = e.client.get(url); assert response.status_code == 404 and 'LEAK_SENTINEL_PRIVATE' not in response.text
        for suffix in ['/refresh-preview', '/refresh', '/export-preview', '/export', '/rules', f'/segments/{sid}/preview', f'/segments/{sid}/review']:
            assert e.client.post(item + suffix, json={'expected_version': 2}).status_code == 404
        assert e.client.put(item + '/segments/' + sid, json={'expected_version': 2, 'text': 'overwrite'}).status_code == 404
    assert e.store.read(e.nid, e.scope) == before


def test_actual_source_change_marks_stale_without_silent_translation(editions):
    e = editions; row = create(e); item = e.path + '/' + row['id']; sid = row['segments'][0]['id']
    row = checked(e.client.put(item + '/segments/' + sid, json={'expected_version': row['version'], 'text': 'PRIVATE_TARGET'}))
    before = e.store.read(e.nid, e.scope)
    checked(e.client.put(e.prefix + '/chapters/' + e.chapter['id'], json={'version': e.chapter['version'], 'content': 'changed source'}))
    view = checked(e.client.get(item)); assert view['stale'] and 'segments' not in view
    assert 'PRIVATE_TARGET' not in json.dumps(checked(e.client.get(e.path)))
    assert e.store.read(e.nid, e.scope) == before
    preview = checked(e.client.post(item + '/refresh-preview', json={'expected_version': row['version']}))
    refreshed = checked(e.client.post(item + '/refresh', json={'expected_version': row['version'], 'preview_digest': preview['preview_digest']}))
    assert refreshed['segments'][0]['source_text'] == 'changed source'
    assert refreshed['segments'][0]['target_text'] == ''


def test_actual_reader_wrong_branch_and_missing_session_are_denied(editions, monkeypatch):
    e = scoped(editions, monkeypatch)
    for headers in [e.viewer_headers, {}, {**e.headers, 'X-Branch-ID': e.other_branch}]:
        for url in [e.path, e.path + '/catalog']:
            response = e.client.get(url, headers=headers)
            assert response.status_code in {401, 403, 404}
    catalog = checked(e.client.get(e.path + '/catalog', headers=e.headers))
    assert catalog['chapters'] == [] and not catalog['branch_sources_available']
    response = e.client.post(e.path, headers=e.headers, json={'title': 'wrong source', 'source_language': 'en', 'target_language': 'ar', 'chapters': [{'chapter_id': e.chapter['id'], 'chapter_version': e.chapter['version']}]})
    assert response.status_code == 422


@pytest.mark.parametrize('cutoff', ['feature', 'v1'])
def test_actual_final_cutoff_rolls_back_segment_write(editions, monkeypatch, cutoff):
    e = editions; row = create(e); before = e.store.read(e.nid, e.scope); calls = []
    original = e.editions._current
    def current(*args):
        result = original(*args); calls.append(1)
        if len(calls) == 2:
            if cutoff == 'feature': monkeypatch.setenv('EXPERIMENTAL_FEATURES', '')
            else: monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true')
        return result
    monkeypatch.setattr(e.editions, '_current', current)
    response = e.client.put(e.path + f"/{row['id']}/segments/{row['segments'][0]['id']}", json={'expected_version': row['version'], 'text': 'must rollback'})
    assert response.status_code == 404 and e.store.read(e.nid, e.scope) == before


@pytest.mark.parametrize('revocation', ['role', 'session'])
def test_actual_final_authority_recheck_after_projection(editions, monkeypatch, revocation):
    e = scoped(editions, monkeypatch); original = e.editions.catalog
    def catalog(*args):
        result = original(*args)
        if revocation == 'role': e.authorization.revoke_role(e.role, e.lead)
        else: e.sessions.revoke(e.lead)
        return result
    monkeypatch.setattr(e.editions, 'catalog', catalog)
    assert e.client.get(e.path + '/catalog', headers=e.headers).status_code in {401, 403}


def test_actual_created_heading_is_a_segment_and_wrong_fixture_alignment_blocks_review(editions):
    """Reproduce the e12 browser fixture mismatch without weakening term guards."""
    e = editions
    prose = ['阿青🙂é来到港口。', '船长保留原位。', '第三段：钟声响起。']
    created = checked(e.client.post(e.prefix + f'/novels/{e.nid}/chapters', json={
        'title': '合成多语章节', 'content': '\n\n'.join(prose),
    }), 201)
    current = checked(e.client.get(e.prefix + '/chapters/' + created['id']))
    row = checked(e.client.post(e.path, json={'title': 'Reproduce real heading alignment',
        'source_language': 'zh-Hant', 'target_language': 'ar',
        'chapters': [{'chapter_id': current['id'], 'chapter_version': current['version']}]}), 201)
    assert [s['source_text'] for s in row['segments']] == ['合成多语章节', *prose]
    item = e.path + '/' + row['id']
    row = checked(e.client.post(item + '/rules', json={'expected_version': row['version'],
        'source_term': '阿青', 'preferred': 'تشينغ', 'forbidden': ['WrongName'], 'strategy': 'transliteration'}))
    row = checked(e.client.post(item + f"/rules/{row['rules'][0]['id']}/review",
        json={'expected_version': row['version'], 'action': 'approve'}))
    # e12 treated segment zero (the H1) as the first body paragraph. Its second
    # iteration therefore supplied a generic target for the actual 阿青 source.
    segment = row['segments'][1]; segment_path = item + '/segments/' + segment['id']
    row = checked(e.client.put(segment_path, json={'expected_version': row['version'], 'text': 'فقرة عربية 2 🙂é'}))
    row = checked(e.client.post(segment_path + '/review', json={'expected_version': row['version'], 'action': 'submit'}))
    preview = checked(e.client.post(segment_path + '/preview', json={'expected_version': row['version']}))
    assert preview['can_accept'] is False
    assert [(issue['code'], issue.get('term'), issue.get('expected')) for issue in preview['issues']] == [('TERM_REQUIRED', '阿青', 'تشينغ')]
    denied = e.client.post(segment_path + '/review', json={'expected_version': row['version'], 'action': 'accept', 'preview_digest': preview['preview_digest']})
    assert denied.status_code == 422
    assert checked(e.client.get(item))['segments'][1]['status'] == 'REVIEW'
    assert checked(e.client.get(e.prefix + '/chapters/' + current['id'])) == current
    print('B05 e12 reproduction:', json.dumps({'source_segments': ['合成多语章节', *prose], 'selected_source': segment['source_text'], 'can_accept': preview['can_accept'], 'issues': preview['issues']}, ensure_ascii=False))


def test_actual_structured_three_paragraph_fixture_maps_terms_and_preserves_original(editions):
    e = editions
    prose = ['阿青🙂é来到港口。', '船长保留原位。', '第三段：钟声响起。']
    document = {'type': 'doc', 'content': [{'type': 'paragraph', 'content': [{'type': 'text', 'text': text}]} for text in prose]}
    created = checked(e.client.post(e.prefix + f'/novels/{e.nid}/chapters', json={'title': '合成多语章节', 'content': '\n\n'.join(prose)}), 201)
    initial = checked(e.client.get(e.prefix + '/chapters/' + created['id']))
    saved = checked(e.client.put(e.prefix + '/chapters/' + created['id'], json={'version': initial['version'], 'document': document}))
    original = checked(e.client.get(e.prefix + '/chapters/' + created['id']))
    assert original['version'] == saved['version'] == initial['version'] + 1
    assert original['document'] == document
    original_history = checked(e.client.get(e.prefix + '/chapters/' + created['id'] + '/history'))
    row = checked(e.client.post(e.path, json={'title': 'Structured language edition', 'source_language': 'zh-Hant', 'target_language': 'ar',
        'chapters': [{'chapter_id': original['id'], 'chapter_version': original['version']}]}), 201)
    assert [s['source_text'] for s in row['segments']] == prose
    item = e.path + '/' + row['id']
    row = checked(e.client.post(item + '/rules', json={'expected_version': row['version'], 'source_term': '阿青', 'preferred': 'تشينغ', 'forbidden': ['WrongName'], 'strategy': 'transliteration'}))
    row = checked(e.client.post(item + f"/rules/{row['rules'][0]['id']}/review", json={'expected_version': row['version'], 'action': 'approve'}))
    targets = ['تشينغ وصل إلى الميناء 🙂é', 'فقرة عربية 2 🙂é', 'فقرة عربية 3 🙂é']
    for index, text in enumerate(targets):
        path = item + '/segments/' + row['segments'][index]['id']
        row = checked(e.client.put(path, json={'expected_version': row['version'], 'text': text}))
        row = checked(e.client.post(path + '/review', json={'expected_version': row['version'], 'action': 'submit'}))
        preview = checked(e.client.post(path + '/preview', json={'expected_version': row['version']}))
        assert preview['can_accept'] and not preview['issues'], json.dumps(preview, ensure_ascii=False)
        row = checked(e.client.post(path + '/review', json={'expected_version': row['version'], 'action': 'accept', 'preview_digest': preview['preview_digest']}))
    assert [s['target_text'] for s in row['segments']] == targets
    assert [s['status'] for s in row['segments']] == ['ACCEPTED'] * 3
    assert row['checks']['can_export']
    preview = checked(e.client.post(item + '/export-preview', json={'expected_version': row['version'], 'format': 'html'}))
    output = checked(e.client.post(item + '/export', json={'expected_version': row['version'], 'format': 'html', 'preview_digest': preview['preview_digest']}))
    assert output['content'].count('<p>') == 3 and 'lang="ar" dir="rtl"' in output['content']
    assert checked(e.client.get(e.prefix + '/chapters/' + created['id'])) == original
    assert checked(e.client.get(e.prefix + '/chapters/' + created['id'] + '/history')) == original_history
