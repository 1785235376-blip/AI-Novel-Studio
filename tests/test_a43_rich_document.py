"""A43-01 safety assertions. Additive; original audit/old regressions are unchanged.

Both storage variants use real repositories. PostgreSQL needs the dedicated test
endpoint; absence is NOT_RUN rather than a mocked integration pass.
"""
from copy import deepcopy
from io import BytesIO
import os
import time
from types import SimpleNamespace
from uuid import uuid4
from xml.etree import ElementTree as ET
from zipfile import ZipFile

import pytest

from app.document import document_to_markdown, plain_text
from app.config import Settings
from app.repositories.factory import create_repository_bundle
from app.services import ChapterService, NovelService
from app.services.export_job_service import ExportJobService, ExportJobUnavailable


def text(value, *marks):
    return {'type': 'text', 'text': value, **({'marks': [{'type': mark} for mark in marks]} if marks else {})}


def paragraph(value):
    return {'type': 'paragraph', 'content': [text(value)]}


def rich_document():
    return {'type': 'doc', 'content': [
        {'type': 'heading', 'attrs': {'level': 1}, 'content': [text('第一章')]},
        paragraph('普通段落中文🙂e\u0301'),
        {'type': 'bulletList', 'content': [{'type': 'listItem', 'content': [
            paragraph('LISTSECRET'),
            {'type': 'orderedList', 'attrs': {'start': 3, 'type': None}, 'content': [
                {'type': 'listItem', 'content': [paragraph('ORDERSECRET'),
                    {'type': 'blockquote', 'content': [paragraph('NESTEDQUOTE')]}
                ]},
                {'type': 'listItem', 'content': [paragraph('SECONDORDER')]},
            ]},
        ]}]},
        {'type': 'blockquote', 'content': [paragraph('QUOTESECRET'),
            {'type': 'bulletList', 'content': [{'type': 'listItem', 'content': [paragraph('QUOTELIST')]}]},
        ]},
        {'type': 'paragraph', 'content': [text('前句'), {'type': 'hardBreak'}, text('后句')]},
        {'type': 'codeBlock', 'attrs': {'language': 'python'}, 'content': [text('CODESECRET\nprint("中文🙂")')]},
        {'type': 'paragraph', 'content': [text('BOLDSECRET', 'bold'), text('ITALICSECRET', 'italic'),
            text('STRIKESECRET', 'strike'), text('INLINESECRET', 'code')]},
        {'type': 'horizontalRule'},
        paragraph('尾声'),
    ]}


EXPECTED_PLAIN = ('第一章\n普通段落中文🙂e\u0301\nLISTSECRET\nORDERSECRET\nNESTEDQUOTE\nSECONDORDER\n'
                  'QUOTESECRET\nQUOTELIST\n前句\n后句\nCODESECRET\nprint("中文🙂")\n'
                  'BOLDSECRETITALICSECRETSTRIKESECRETINLINESECRET\n尾声')
WORDS = ('LISTSECRET', 'ORDERSECRET', 'NESTEDQUOTE', 'SECONDORDER', 'QUOTESECRET',
         'QUOTELIST', 'CODESECRET', 'BOLDSECRET', 'ITALICSECRET', 'STRIKESECRET', 'INLINESECRET', '中文🙂')


@pytest.fixture(params=[pytest.param('file', marks=pytest.mark.file_backend_only),
                        pytest.param('postgres', marks=pytest.mark.postgres_backend_only)])
def rich_env(tmp_path, request):
    backend = request.param
    url = os.getenv('TEST_POSTGRES_DATABASE_URL', '') if backend == 'postgres' else ''
    if backend == 'postgres' and not url:
        pytest.skip('NOT_RUN: dedicated real PostgreSQL endpoint unavailable')
    config = Settings(storage_backend=backend, database_url=url, novel_data=tmp_path,
                      mock_provider=True, enable_cloud=False)
    bundle = create_repository_bundle(config, data_root=tmp_path)
    chapters, novels = ChapterService(bundle.chapters), NovelService(bundle.novels, bundle.chapters)
    nid = 'a43-rich-' + uuid4().hex
    novels.create({'id': nid, 'title': '合成作品', 'genre': 'fantasy'})
    created = chapters.create(nid, {'title': '第一章', 'content': 'initial'})
    env = SimpleNamespace(chapters=chapters, novels=novels, bundle=bundle, nid=nid, cid=created['id'],
                          root=tmp_path, config=config, backend=backend)
    yield env
    if backend == 'postgres':
        novels.delete(nid)


def save_rich(e, document=None):
    current = e.chapters.get(e.cid)
    return e.chapters.save(e.cid, {'version': current['version'], 'document': document or rich_document()})


def test_recursive_projection_contains_every_editor_text_node_and_hardbreak():
    doc = rich_document(); before = deepcopy(doc)
    assert plain_text(doc) == EXPECTED_PLAIN
    markdown = document_to_markdown(doc)
    assert all(word in markdown for word in WORDS)
    assert '前句\n后句' in markdown
    assert '3. ORDERSECRET' in markdown and '4. SECONDORDER' in markdown
    assert '> QUOTESECRET' in markdown
    assert doc == before


@pytest.mark.parametrize('project', [plain_text, document_to_markdown])
@pytest.mark.parametrize('node', [
    {'type': 'futureNode', 'content': [paragraph('MUST_NOT_VANISH')]},
    {'type': 'futureLeaf', 'text': 'MUST_NOT_VANISH'},
    {'type': 'paragraph', 'content': [text('TEXT', 'futureMark')]},
])
def test_unknown_nodes_and_marks_fail_explicitly(project, node):
    with pytest.raises(ValueError, match='unsupported|Unsupported'):
        project({'type': 'doc', 'content': [node]})


def test_save_reopen_duplicate_preserve_full_structure_and_single_title(rich_env):
    e = rich_env; doc = rich_document(); saved = save_rich(e, doc)
    restarted = create_repository_bundle(e.config, data_root=e.root)
    reopened = ChapterService(restarted.chapters).get(e.cid)
    assert reopened['document'] == doc and saved['document'] == doc
    assert all(word in reopened['content'] for word in WORDS)
    duplicate = e.chapters.duplicate(e.cid)
    expected = deepcopy(doc)
    expected['content'][0]['content'] = [text('第一章 Copy')]
    assert duplicate['document'] == expected
    assert duplicate['version'] == 1
    assert plain_text(duplicate['document']).count('第一章') == 1
    assert e.chapters.get(e.cid)['document'] == doc
    listed = next(c for c in e.chapters.list(e.nid) if c['id'] == e.cid)
    assert listed['document'] == doc


def test_unsupported_save_keeps_document_version_and_history_unchanged(rich_env):
    e = rich_env; before = save_rich(e); history = e.chapters.history(e.cid)
    unknown = deepcopy(before['document'])
    unknown['content'].append({'type': 'unknownContainer', 'content': [paragraph('SECRET')]})
    with pytest.raises(ValueError, match='unsupported|Unsupported'):
        e.chapters.save(e.cid, {'version': before['version'], 'document': unknown})
    assert e.chapters.get(e.cid) == before
    assert e.chapters.history(e.cid) == history


def test_plain_search_interop_diff_and_pm_selection_coordinates_agree():
    from app.experimental.ux import chapter_text
    from app.local_interop.provider import anchor_text
    from app.experimental.revision_intelligence import text_blocks, SelectionIn, selection_snapshot, utf16_size
    doc = rich_document()
    # A horizontal rule is a non-text atom, so revision's explicit unsupported
    # object fence is retained; it is absent from plain-text search coordinates.
    doc['content'] = [node for node in doc['content'] if node['type'] != 'horizontalRule']
    assert chapter_text({'document': doc}) == anchor_text(doc) == plain_text(doc) == EXPECTED_PLAIN
    blocks = text_blocks(doc)
    assert '\n'.join(b['text'] for b in blocks) == plain_text(doc)
    for block in blocks:
        receipt = selection_snapshot(doc, SelectionIn(chapter_id='synthetic:1', chapter_version=2,
            from_pos=block['start'], to_pos=block['end'], text=block['text']))
        assert receipt['blocks'][0]['before'] == block['text']
        assert block['end'] - block['start'] == utf16_size(block['text'])
        start = plain_text(doc).index(block['text'])
        assert plain_text(doc)[start:start + len(block['text'])] == block['text']
    emoji = next(b for b in blocks if b['text'].startswith('普通'))
    assert emoji['end'] - emoji['start'] > len(emoji['text'])


def export_text(payload, format):
    if format in {'docx', 'word'}:
        with ZipFile(BytesIO(payload)) as archive:
            root = ET.fromstring(archive.read('word/document.xml'))
            # Word represents hard line breaks/tabs as empty elements, not
            # text nodes. itertext() alone silently joins the adjacent runs.
            word = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            paragraphs = []
            for paragraph in root.iter(word + 'p'):
                parts = []
                for node in paragraph.iter():
                    if node.tag == word + 't':
                        parts.append(node.text or '')
                    elif node.tag == word + 'br':
                        parts.append('\n')
                    elif node.tag == word + 'tab':
                        parts.append('\t')
                paragraphs.append(''.join(parts))
            return '\n'.join(paragraphs)
    if format == 'epub':
        with ZipFile(BytesIO(payload)) as archive:
            root = ET.fromstring(archive.read('OEBPS/content.xhtml'))
            return '\n'.join(''.join(p.itertext()) for p in root.iter('{http://www.w3.org/1999/xhtml}p'))
    return payload.decode('utf-8')


def wait_terminal(queue, jid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        item = queue.get(jid)
        if item['status'] in {'succeeded', 'failed', 'cancelled'}:
            return item
        time.sleep(.01)
    pytest.fail('bounded original export queue did not reach terminal state')


@pytest.mark.parametrize('mode', ['OFF', 'ON', 'V1'])
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_original_api_aliases_and_export_queue_keep_entire_rich_text(rich_env, monkeypatch, mode, prefix):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api
    from app.experimental.flags import FLAGS
    e = rich_env
    monkeypatch.setenv('EXPERIMENTAL_FEATURES', '' if mode == 'OFF' else ','.join(FLAGS))
    monkeypatch.setenv('V1_ACCEPTANCE_MODE', 'true' if mode == 'V1' else 'false')
    object.__setattr__(api.settings, 'enable_collaboration_runtime', False)
    monkeypatch.setattr(api, 'chapter_service', e.chapters)
    monkeypatch.setattr(api, 'novel_service', e.novels)
    queue = ExportJobService(e.root / 'rich-queue', e.novels.export, snapshotter=e.novels.export_snapshot)
    monkeypatch.setattr(api, 'export_job_service', queue)
    app = FastAPI(); app.include_router(api.router, prefix=prefix)
    client = TestClient(app)
    try:
        saved = client.put(prefix + '/chapters/' + e.cid, json={'version': 1, 'document': rich_document()})
        assert saved.status_code == 200, saved.text
        assert client.get(prefix + '/chapters/' + e.cid).json()['document'] == rich_document()
        duplicated = client.post(prefix + '/chapters/' + e.cid + '/duplicate')
        assert duplicated.status_code == 201, duplicated.text
        assert duplicated.json()['document']['content'][1:] == rich_document()['content'][1:]
        for format in ('txt', 'text', 'markdown', 'md', 'docx', 'word', 'epub', 'json'):
            created = client.post(prefix + '/exports', params={'novel_id': e.nid}, json={'format': format})
            assert created.status_code == 202, created.text
            jid = created.json()['id']; result = wait_terminal(queue, jid)
            assert result['status'] == 'succeeded', result
            response = client.get(prefix + '/exports/' + jid + '/download')
            assert response.status_code == 200
            content = export_text(response.content, format)
            assert all(word in content for word in WORDS), (format, content)
            if format in {'txt', 'text', 'markdown', 'md'}:
                assert '前句\n后句' in content
    finally:
        queue._pool.shutdown(wait=True)


def test_exporters_prefer_document_over_stale_projection_and_reject_unknown():
    from app.export_formats import novel_to_docx, novel_to_epub
    source = {'title': '第一章', 'content': 'STALE_ONLY', 'document': rich_document()}
    for format, render in [('docx', novel_to_docx), ('epub', novel_to_epub)]:
        output = export_text(render('Book', [source]), format)
        assert all(word in output for word in WORDS)
        assert output == ('Book\n' + EXPECTED_PLAIN if format == 'docx' else EXPECTED_PLAIN.split('\n', 1)[1])
        assert 'STALE_ONLY' not in output
        source_bad = {**source, 'document': {'type': 'doc', 'content': [{'type': 'futureNode', 'text': 'LOST'}]}}
        with pytest.raises(ValueError, match='unsupported|Unsupported'):
            render('Book', [source_bad])


def test_pdf_cid_fallback_rejects_unrepresentable_emoji_instead_of_success(monkeypatch, tmp_path):
    from app import pdf_export
    monkeypatch.setattr(pdf_export, '_register_cjk_font', lambda: ('STSong-Light', False))
    with pytest.raises(pdf_export.PDFExportError) as error:
        pdf_export.novel_to_pdf('Book', [{'title': '第一章', 'content': 'KEEP🙂TEXT'}])
    assert error.value.code == 'PDF_UNSUPPORTED_CHARACTERS'
    with pytest.raises(pdf_export.PDFExportError) as error:
        pdf_export._novel_to_pdf_cid_fallback('Book', [{'title': '章', 'content': 'KEEP🙂TEXT'}],
            version=None, require_embedded_font=False, progress_callback=None)
    assert error.value.code == 'PDF_UNSUPPORTED_CHARACTERS'


@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_unknown_put_is_clear_client_error_and_keeps_original_authority(rich_env, monkeypatch, prefix):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api
    e = rich_env; before = save_rich(e); history = e.chapters.history(e.cid)
    object.__setattr__(api.settings, 'enable_collaboration_runtime', False)
    monkeypatch.setattr(api, 'chapter_service', e.chapters)
    app = FastAPI(); app.include_router(api.router, prefix=prefix)
    unknown = deepcopy(before['document']); unknown['content'].append({'type': 'futureNode'})
    response = TestClient(app).put(prefix + '/chapters/' + e.cid,
        json={'version': before['version'], 'document': unknown})
    assert response.status_code == 400
    assert response.json()['detail']['code'] == 'DOCUMENT_PROJECTION_UNSUPPORTED'
    assert e.chapters.get(e.cid) == before and e.chapters.history(e.cid) == history


@pytest.mark.file_backend_only
def test_legacy_unknown_document_read_copy_export_leave_original_json_untouched(tmp_path):
    import json
    from app.repository import FileRepository
    from app.repositories.file.chapter import FileChapterRepository
    from app.repositories.file.novel import FileNovelRepository
    backend = FileRepository(tmp_path / 'data'); backend.create_novel({'id': 'old', 'title': 'Synthetic'})
    repo = FileChapterRepository(backend); chapters = ChapterService(repo)
    created = chapters.create('old', {'title': 'Old', 'content': 'stale cache'})
    chapters.get(created['id'])
    path = backend.novels / 'old' / 'documents' / 'chapter-0001.json'
    package = json.loads(path.read_text())
    package['document']['content'].append({'type': 'legacyCustom', 'content': [paragraph('OLD-PROSE-KEEP')]})
    path.write_text(json.dumps(package, ensure_ascii=False), encoding='utf-8')
    original = path.read_bytes()
    ns = NovelService(FileNovelRepository(backend), repo)
    for operation in (lambda: chapters.get(created['id']), lambda: chapters.duplicate(created['id']),
                      lambda: ns.export_snapshot('old', format='docx')):
        with pytest.raises(ValueError, match='unsupported'):
            operation()
        assert path.read_bytes() == original
    assert len(list((backend.novels / 'old' / 'chapters').glob('*.md'))) == 1


def test_source_context_and_exact_selection_use_full_saved_projection(rich_env):
    from app.author_request import author_source, saved_source_matches
    e = rich_env; saved = save_rich(e)
    source = author_source(SimpleNamespace(request_scope={'source_mode': 'AUTO'}, source=''), saved)
    assert len(saved['content']) < 2000  # Existing context tail budget is unchanged.
    assert all(word in source for word in WORDS)
    for quote in ('ORDERSECRET\nNESTEDQUOTE', '前句\n后句', '普通段落中文🙂e\u0301'):
        assert saved_source_matches(saved, quote)
    assert not saved_source_matches({**saved, 'content': 'stale'}, 'ORDERSECRET\nNESTEDQUOTE')


def test_export_snapshot_is_frozen_after_later_rich_edits(rich_env):
    e = rich_env; before = save_rich(e)
    snapshot = e.novels.export_snapshot(e.nid, format='docx')
    later = deepcopy(before['document'])
    later['content'][2]['content'][0]['content'][0] = paragraph('LATER_ONLY')
    e.chapters.save(e.cid, {'version': before['version'], 'document': later})
    import base64
    exported = e.novels.export(e.nid, 'docx', snapshot=snapshot)
    content = export_text(base64.b64decode(exported['content_base64']), 'docx')
    assert 'LISTSECRET' in content and 'LATER_ONLY' not in content
    assert snapshot['source']['chapters'][0]['document'] == before['document']


@pytest.mark.parametrize('kind', ['marked-title', 'non-title-heading', 'empty'])
def test_duplicate_title_does_not_remove_body_nodes(rich_env, kind):
    e = rich_env
    if kind == 'marked-title':
        document = {'type': 'doc', 'content': [
            {'type': 'heading', 'attrs': {'level': 1}, 'content': [text('第一章', 'bold')]}, paragraph('BODY')]}
    elif kind == 'non-title-heading':
        document = {'type': 'doc', 'content': [
            {'type': 'heading', 'attrs': {'level': 2}, 'content': [text('Section')]}, paragraph('BODY')]}
    else:
        document = {'type': 'doc', 'content': []}
    original = save_rich(e, document)
    duplicate = e.chapters.duplicate(e.cid)
    if kind == 'marked-title':
        assert duplicate['document']['content'][0]['content'][0]['marks'] == [{'type': 'bold'}]
        assert duplicate['document']['content'][1:] == document['content'][1:]
        assert duplicate['title'] == '第一章 Copy'
    else:
        assert duplicate['document']['content'][1:] == document['content']
    assert e.chapters.get(e.cid)['document'] == original['document']


def test_original_pdf_queue_rejects_emoji_and_exports_supported_nested_text(rich_env, monkeypatch):
    from app import pdf_export
    from pypdf import PdfReader
    e = rich_env
    # Force the documented CID path regardless of optional machine fonts.
    monkeypatch.setattr(pdf_export, '_register_cjk_font', lambda: ('STSong-Light', False))
    save_rich(e)
    queue = ExportJobService(e.root / 'pdf-queue', e.novels.export, snapshotter=e.novels.export_snapshot)
    try:
        denied = queue.create(e.nid, 'pdf'); result = wait_terminal(queue, denied['id'])
        assert result['status'] == 'failed' and result['error']['code'] == 'PDF_UNSUPPORTED_CHARACTERS'
        with pytest.raises(ExportJobUnavailable): queue.download(denied['id'])
        supported = rich_document()
        def bmp(node):
            if node.get('type') == 'text': node['text'] = node['text'].replace('🙂', '').replace('e\u0301', 'e')
            for child in node.get('content', []): bmp(child)
        bmp(supported); save_rich(e, supported)
        # Ensure registration rather than relying on another test's PDF use.
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        job = queue.create(e.nid, 'pdf'); result = wait_terminal(queue, job['id'])
        assert result['status'] == 'succeeded', result
        content = '\n'.join(page.extract_text() for page in PdfReader(BytesIO(queue.download(job['id'])['content'])).pages)
        assert all(word in content for word in WORDS if word != '中文🙂')
        assert '中文' in content and '前句' in content and '后句' in content
    finally:
        queue._pool.shutdown(wait=True)


def test_shared_frontend_fixture_pins_plain_and_pm_coordinates():
    import json
    from pathlib import Path
    from app.experimental.revision_intelligence import text_blocks
    fixture = json.loads((Path(__file__).parent / 'fixtures' / 'a43_rich_document_coordinates.json').read_text(encoding='utf-8'))
    assert fixture['document'] == rich_document()
    assert plain_text(fixture['document']) == fixture['plain_text'] == EXPECTED_PLAIN
    assert fixture['text_blocks'] == [{k: block[k] for k in ('path', 'start', 'end', 'text')}
        for block in text_blocks(fixture['document']) if block['supported']]


def test_empty_blocks_and_literal_code_whitespace_are_not_collapsed():
    document = {'type': 'doc', 'content': [
        {'type': 'paragraph'},
        {'type': 'blockquote', 'content': [{'type': 'paragraph'},
            {'type': 'paragraph', 'content': [text('前'), {'type': 'hardBreak'}, {'type': 'hardBreak'}, text('后')]}]},
        {'type': 'codeBlock', 'attrs': {'language': None}, 'content': [text('  a\n\n```\n  b  ')]},
        {'type': 'paragraph'},
    ]}
    assert plain_text(document) == '\n\n前\n\n后\n  a\n\n```\n  b  \n'
    markdown = document_to_markdown(document)
    assert '````\n  a\n\n```\n  b  \n````' in markdown
    assert document['content'][2]['content'][0]['text'] == '  a\n\n```\n  b  '
