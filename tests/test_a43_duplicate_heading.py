"""Additive A43 heading-copy safety: never rebuild rich H1 from title metadata.

File and PostgreSQL have different existing title metadata projections. Copy
must preserve original inline runs and later lines independently of those rules.
"""
from copy import deepcopy
from io import BytesIO
import json
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from app.document import plain_text

import pytest

from app.repositories.factory import create_repository_bundle
from app.services import ChapterService
from test_a43_rich_document import rich_env, text, paragraph, wait_terminal, export_text


HEADING_CASES = [
    pytest.param([text('中文🙂FIRST', 'bold'), text('SECONDLINESECRET', 'italic')],
                 [text('中文🙂FIRST', 'bold'), text('SECONDLINESECRET Copy', 'italic')], id='mixed-marks'),
    pytest.param([text('中文🙂FIRST', 'bold'), {'type': 'hardBreak'}, text('SECONDLINESECRET', 'italic')],
                 [text('中文🙂FIRST Copy', 'bold'), {'type': 'hardBreak'}, text('SECONDLINESECRET', 'italic')], id='hard-break'),
    pytest.param([text('中文🙂FIRST\nSECONDLINESECRET', 'italic')],
                 [text('中文🙂FIRST Copy\nSECONDLINESECRET', 'italic')], id='literal-lf'),
    pytest.param([text('中文🙂FIRST\r\nSECONDLINESECRET', 'italic')],
                 [text('中文🙂FIRST Copy\r\nSECONDLINESECRET', 'italic')], id='literal-crlf'),
    pytest.param([text('中文', 'bold'), text('🙂FIRST\nSECONDLINESECRET', 'italic')],
                 [text('中文', 'bold'), text('🙂FIRST Copy\nSECONDLINESECRET', 'italic')], id='split-marks-lf'),
    pytest.param([text('中文🙂FIRST\n', 'bold'), text('SECONDLINESECRET', 'italic')],
                 [text('中文🙂FIRST Copy\n', 'bold'), text('SECONDLINESECRET', 'italic')], id='run-ends-with-lf'),
]


def document(content):
    return {'type': 'doc', 'content': [
        {'type': 'heading', 'attrs': {'level': 1}, 'content': deepcopy(content)},
        paragraph('BODY-MUST-STAY'),
    ]}


@pytest.mark.parametrize('original_runs,expected_runs', HEADING_CASES)
def test_duplicate_preserves_rich_heading_runs_breaks_later_text_and_history(rich_env, original_runs, expected_runs):
    e = rich_env; doc = document(original_runs); expected = document(expected_runs)
    saved = e.chapters.save(e.cid, {'version': 1, 'document': doc})
    original_history = e.chapters.history(e.cid)
    copied = e.chapters.duplicate(e.cid)
    assert copied['document'] == expected
    assert copied['version'] == 1 and copied['id'] != e.cid
    assert len([node for node in copied['document']['content'] if node['type'] == 'heading']) == 1
    assert 'SECONDLINESECRET' in json.dumps(copied['document'], ensure_ascii=False)
    reopened = ChapterService(create_repository_bundle(e.config, data_root=e.root).chapters).get(copied['id'])
    assert reopened['document'] == expected
    assert e.chapters.get(e.cid) == saved
    assert e.chapters.history(e.cid) == original_history
    snapshot = e.novels.export_snapshot(e.nid, format='json')
    exported = json.loads(e.novels.export(e.nid, 'json', snapshot=snapshot)['content'])
    exported_copy = next(row for row in exported['chapters'] if row['id'] == copied['id'])
    assert exported_copy['document'] == expected


@pytest.mark.parametrize('original_runs,expected_runs', HEADING_CASES)
@pytest.mark.parametrize('prefix', ['/api', '/api/v1'])
def test_duplicate_api_and_original_queue_export_preserve_rich_h1(rich_env, monkeypatch, original_runs, expected_runs, prefix):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.api as api
    from app.services.export_job_service import ExportJobService
    e = rich_env
    object.__setattr__(api.settings, 'enable_collaboration_runtime', False)
    monkeypatch.setattr(api, 'chapter_service', e.chapters)
    monkeypatch.setattr(api, 'novel_service', e.novels)
    queue = ExportJobService(e.root / 'heading-queue', e.novels.export, snapshotter=e.novels.export_snapshot)
    monkeypatch.setattr(api, 'export_job_service', queue)
    app = FastAPI(); app.include_router(api.router, prefix=prefix); client = TestClient(app)
    try:
        saved = client.put(prefix + '/chapters/' + e.cid, json={'version': 1, 'document': document(original_runs)})
        assert saved.status_code == 200, saved.text
        response = client.post(prefix + '/chapters/' + e.cid + '/duplicate')
        assert response.status_code == 201, response.text
        copied = response.json(); expected = document(expected_runs)
        assert copied['document'] == expected
        readback = client.get(prefix + '/chapters/' + copied['id'])
        assert readback.status_code == 200 and readback.json()['document'] == expected
        for format in ('json', 'txt', 'docx', 'epub'):
            response = client.post(prefix + '/exports', params={'novel_id': e.nid}, json={'format': format})
            assert response.status_code == 202, response.text
            jid = response.json()['id']; outcome = wait_terminal(queue, jid)
            assert outcome['status'] == 'succeeded', outcome
            downloaded = client.get(prefix + '/exports/' + jid + '/download')
            assert downloaded.status_code == 200
            if format == 'json':
                row = next(ch for ch in downloaded.json()['chapters'] if ch['id'] == copied['id'])
                assert row['document'] == expected
            else:
                if format == 'epub':
                    with ZipFile(BytesIO(downloaded.content)) as archive:
                        xml = ET.fromstring(archive.read('OEBPS/content.xhtml'))
                        content = '\n'.join(''.join(node.itertext()) for node in xml.iter()
                            if node.tag.rsplit('}', 1)[-1] in {'h1', 'h2', 'p'})
                else:
                    content = export_text(downloaded.content, format)
                # Existing PG metadata flattens heading hardBreaks; metadata
                # labels may repeat words. Check the full manuscript sequence,
                # not a guessed global title/word count.
                projected = '\n'.join(line for line in content.replace('\r\n', '\n').split('\n') if line)
                for source in (document(original_runs), expected):
                    exact = '\n'.join(line for line in plain_text(source).replace('\r\n', '\n').split('\n') if line)
                    assert exact in projected
                assert content.count('BODY-MUST-STAY') == 2
        assert e.chapters.get(e.cid)['document'] == document(original_runs)
    finally:
        queue._pool.shutdown(wait=True)
