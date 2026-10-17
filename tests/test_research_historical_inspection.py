"""Exact author-only historical reads; original fixtures and persistence owners."""
import copy
import hashlib
import json

import pytest

from app.experimental.common import StaleSourceError
from app.experimental.research_library import ResearchLibraryService
from app.experimental.store import ExperimentalStore
from test_r3_planning import planning_env
from test_r4_research_library import imported, citation, payload
from test_v2_creative_project_lifecycle import rig


@pytest.fixture
def research(rig):
    rig.chapter_service = rig.chapters
    rig.research = ResearchLibraryService(rig.store, rig.novels, rig.chapters, historical_inspection=True)
    return rig


def revised(e, **kwargs):
    row = imported(e, **kwargs)
    e.research.replace_file(e.nid, e.scope, 'author', row['id'],
                           {**payload('Current replacement.'), 'expected_version': 1}, guard=lambda: None)
    return row, citation(row)


def inspect(e, row, ref, actor='author', version=2):
    return e.research.inspect_history(e.nid, e.scope, actor, row['id'], version, ref)


def test_restart_exact_plain_text_is_bounded_read_only_and_never_resolves(research, monkeypatch):
    e = research
    text = '<script>bad()</script> 🌊e\u0301' + 'x' * 7970
    row, ref = revised(e, text=text)
    before = copy.deepcopy(e.store.read(e.nid, e.scope))
    path = e.store.path(e.nid, e.scope)
    disk = path.read_bytes() if e.backend == 'file' else None
    stamp = path.stat().st_mtime_ns if disk else None
    def no_write(*args, **kwargs): raise AssertionError('Historical inspection wrote storage')
    monkeypatch.setattr('app.experimental.store.atomic_write', no_write)
    e.research = ResearchLibraryService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, historical_inspection=True)
    value = inspect(e, row, ref)
    assert value == {'historical_citation': ref, 'current_version': 2, 'text': text, 'page': None,
                     'historical_only': True, 'not_understood': False, 'usable_as_current_evidence': False}
    assert len(value['text']) <= 8000 and len(json.dumps(value).encode()) < 50000
    assert e.store.read(e.nid, e.scope) == before
    if disk:
        assert path.read_bytes() == disk and path.stat().st_mtime_ns == stamp
    for operation in [lambda: e.research.resolve(e.nid, e.scope, 'author', ref),
                      lambda: e.research.context(e.nid, e.scope, 'author', [ref])]:
        with pytest.raises(StaleSourceError): operation()


@pytest.mark.parametrize('change', ['hash', 'paragraph', 'version', 'source', 'current_version', 'foreign_author', 'revoke', 'delete'])
def test_rejects_unavailable_or_inexact_without_text(research, change):
    e = research; row, ref = revised(e, access='PROJECT')
    actor, version = 'author', 2
    if change == 'hash': ref['quote_sha256'] = '0' * 64
    if change == 'paragraph': ref['paragraph'] = 5000
    if change == 'version': ref['source_version'] = 2
    if change == 'source': ref['source_id'] = 'foreign'
    if change == 'current_version': version = 1
    if change == 'foreign_author': actor = 'other'
    if change in {'revoke', 'delete'}:
        e.research.transition_source(e.nid, e.scope, 'author', row['id'], 2, change, guard=lambda: None)
        version = 3
    with pytest.raises(FileNotFoundError): inspect(e, row, ref, actor, version)


@pytest.mark.parametrize('field,value', [('id', 'foreign'), ('created_by', 'other'), ('novel_id', 'other'), ('scope', {'mode': 'local', 'novel_id': 'other'}), ('status', 'REVOKED')])
def test_corrupt_foreign_revision_is_not_authority(research, field, value):
    e = research; row, ref = revised(e)
    with e.store.transaction(e.nid, e.scope) as state:
        state['collections']['research_sources'][row['id']]['history'][0][field] = value
    with pytest.raises(FileNotFoundError): inspect(e, row, ref)


def test_unread_page_is_only_a_marker_and_never_text(research):
    e = research; row = imported(e)
    with e.store.transaction(e.nid, e.scope) as state:
        source = state['collections']['research_sources'][row['id']]
        source['unread_pages'] = [2]
        source['paragraphs'] = []
    ref = e.research._page_cite(row, 2)
    e.research.replace_file(e.nid, e.scope, 'author', row['id'], {**payload(), 'expected_version': 1}, guard=lambda: None)
    value = inspect(e, row, ref)
    assert value['text'] == '' and value['page'] == 2 and value['not_understood'] is True
    with pytest.raises(FileNotFoundError): inspect(e, row, {**ref, 'page': 1})


def test_duplicate_revision_and_oversized_paragraph_fail_closed(research):
    e = research; row, ref = revised(e)
    with e.store.transaction(e.nid, e.scope) as state:
        history = state['collections']['research_sources'][row['id']]['history']
        history.append(copy.deepcopy(history[0]))
    with pytest.raises(FileNotFoundError): inspect(e, row, ref)
    with e.store.transaction(e.nid, e.scope) as state:
        history = state['collections']['research_sources'][row['id']]['history']
        history.pop(); history[0]['paragraphs'][0]['text'] = 'x' * 8001
    ref['quote_sha256'] = hashlib.sha256(('x' * 8001).encode()).hexdigest()
    with pytest.raises(FileNotFoundError): inspect(e, row, ref)
