"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import os

from types import SimpleNamespace

from uuid import uuid4

import pytest

from app.config import Settings

from app.repositories.factory import create_repository_bundle

from app.services import ChapterService, NovelService

from app.experimental.store import ExperimentalStore

from app.experimental.revision_intelligence import RevisionIntelligenceService

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
