"""Additive A43 compatibility: original portable/fork document node vocabulary.

Media are reference atoms, not decoded or fetched by manuscript projection.
The original portable/relink/fork assertions remain unchanged.
"""
from copy import deepcopy
from io import BytesIO
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from app.document import document_to_markdown, plain_text, chapter_body_text
from app.export_formats import novel_to_docx, novel_to_epub
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService
from test_a43_rich_document import rich_env, paragraph, text, wait_terminal, export_text


def media_node(kind):
    attrs = {'asset_id': 'synthetic-asset-reference', 'title': '合成标题🙂\nTITLE-TEXT'}
    if kind == 'image':
        attrs['alt'] = '图像替代说明ALT-TEXT'
    return {'type': kind, 'attrs': attrs}


def media_document(kind):
    return {'type': 'doc', 'content': [paragraph('前文'),
        {'type': 'blockquote', 'content': [media_node(kind)]}, paragraph('后文')]}


def media_marker(kind):
    return '[' + kind + ' media not embedded]'


@pytest.mark.parametrize('kind', ['image', 'audio', 'video'])
def test_known_media_metadata_projects_with_visible_omission_marker_and_no_source_mutation(kind):
    doc = media_document(kind); before = deepcopy(doc)
    markdown = document_to_markdown(doc)
    assert media_marker(kind) in markdown
    assert '合成标题🙂' in markdown and 'TITLE-TEXT' in markdown
    if kind == 'image': assert 'ALT-TEXT' in markdown
    assert 'synthetic-asset-reference' not in markdown
    with pytest.warns(UserWarning, match='non-text media'):
        assert plain_text(doc) == '前文\n后文'
    body = chapter_body_text({'document': doc, 'content': 'STALE'})
    expected = '前文\n' + media_marker(kind) + '\n合成标题🙂\nTITLE-TEXT'
    if kind == 'image': expected += '\n图像替代说明ALT-TEXT'
    assert body == expected + '\n后文'
    assert doc == before


@pytest.mark.parametrize('kind', ['image', 'audio', 'video'])
def test_original_known_media_save_reopen_copy_history_keep_reference_and_metadata(rich_env, kind):
    e = rich_env; original = e.chapters.get(e.cid); doc = media_document(kind)
    saved = e.chapters.save(e.cid, {'version': original['version'], 'document': doc})
    restarted = ChapterService(create_repository_bundle(e.config, data_root=e.root).chapters)
    assert restarted.get(e.cid)['document'] == doc
    assert e.chapters.history(e.cid)[0]['document'] == original['document']
    copied = e.chapters.duplicate(e.cid)
    assert copied['document']['content'][1:] == doc['content']
    assert copied['version'] == 1
    assert e.chapters.get(e.cid)['document'] == doc
    assert media_marker(kind) in saved['content']


@pytest.mark.parametrize('mark', ['underline', 'subscript', 'superscript'])
def test_preexisting_portable_marks_stay_structured_and_preserve_text(rich_env, mark):
    e = rich_env; doc = {'type': 'doc', 'content': [
        {'type': 'paragraph', 'content': [text('原标记文字🙂', mark)]}]}
    current = e.chapters.get(e.cid)
    saved = e.chapters.save(e.cid, {'version': current['version'], 'document': doc})
    assert saved['document'] == doc and plain_text(doc) == '原标记文字🙂'
    copied = e.chapters.duplicate(e.cid)
    assert copied['document']['content'][1:] == doc['content']
    assert copied['document']['content'][1]['content'][0]['marks'] == [{'type': mark}]


@pytest.mark.parametrize('kind', ['image', 'audio', 'video'])
def test_known_media_original_docx_epub_export_retains_all_caption_text_and_explicit_marker(kind):
    doc = media_document(kind); chapter = {'title': 'Chapter', 'content': 'STALE', 'document': doc}
    body = '前文\n' + media_marker(kind) + '\n合成标题🙂\nTITLE-TEXT'
    if kind == 'image': body += '\n图像替代说明ALT-TEXT'
    body += '\n后文'
    assert export_text(novel_to_docx('Book', [chapter]), 'docx') == 'Book\nChapter\n' + body
    assert export_text(novel_to_epub('Book', [chapter]), 'epub') == body
    assert doc == media_document(kind)


@pytest.mark.parametrize('node', [
    {'type': 'audio', 'attrs': {'asset_id': 'asset', 'transcript': 'MUST_NOT_DISAPPEAR'}},
    {'type': 'image', 'attrs': {'src': 'file:///unapproved/path', 'alt': 'MUST_NOT_DISAPPEAR'}},
    {'type': 'video', 'attrs': {'asset_id': 'asset', 'title': {'text': 'MUST_NOT_DISAPPEAR'}}},
    {'type': 'audio', 'attrs': {'asset_id': '../invalid'}},
    {'type': 'audio', 'attrs': {'asset_id': 'asset'}, 'content': [paragraph('MUST_NOT_DISAPPEAR')]},
])
def test_media_extension_cannot_hide_unknown_text_fields_or_fetch_arbitrary_sources(node):
    doc = {'type': 'doc', 'content': [node]}
    with pytest.raises(ValueError, match='unsupported'):
        document_to_markdown(doc)
    with pytest.raises(ValueError, match='unsupported'):
        chapter_body_text({'document': doc})


def test_captionless_media_still_has_explicit_export_placeholder():
    doc = {'type': 'doc', 'content': [{'type': 'audio', 'attrs': {'asset_id': 'synthetic'}}]}
    assert document_to_markdown(doc) == '[audio media not embedded]\n\n'
    assert chapter_body_text({'document': doc}) == '[audio media not embedded]'
    with pytest.warns(UserWarning, match='non-text media'):
        assert plain_text(doc) == ''


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
@pytest.mark.parametrize('mode', ['OFF', 'ON', 'V1'])
def test_known_media_original_aliases_and_frozen_export_queue_remain_usable(rich_env, monkeypatch, prefix, mode):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api
    from app.experimental.flags import FLAGS
    from app.services.export_job_service import ExportJobService
    e = rich_env
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '' if mode == 'OFF' else ','.join(FLAGS))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true' if mode == 'V1' else 'false')
    object.__setattr__(api.settings, 'enable_collaboration_runtime', False)
    monkeypatch.setattr(api, 'chapter_service', e.chapters)
    monkeypatch.setattr(api, 'novel_service', e.novels)
    queue = ExportJobService(e.root / 'media-queue', e.novels.export, snapshotter=e.novels.export_snapshot)
    monkeypatch.setattr(api, 'export_job_service', queue)
    app = FastAPI(); app.include_router(api.router, prefix=prefix); client = TestClient(app)
    try:
        response = client.put(prefix + '/chapters/' + e.cid, json={'version': 1, 'document': media_document('audio')})
        assert response.status_code == 200, response.text
        assert response.json()['document'] == media_document('audio')
        for format in ('txt', 'markdown', 'docx', 'epub'):
            response = client.post(prefix + '/exports', params={'novel_id': e.nid}, json={'format': format})
            assert response.status_code == 202, response.text
            jid = response.json()['id']; result = wait_terminal(queue, jid)
            assert result['status'] == 'succeeded', result
            downloaded = client.get(prefix + '/exports/' + jid + '/download')
            assert downloaded.status_code == 200
            rendered = export_text(downloaded.content, format)
            assert '前文' in rendered and '后文' in rendered and '合成标题🙂' in rendered and 'TITLE-TEXT' in rendered
            assert media_marker('audio') in rendered
    finally:
        queue._pool.shutdown(wait=True)
