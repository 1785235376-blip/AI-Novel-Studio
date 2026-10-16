"""Nonsecurity File owner evidence for the bounded original-view handoff."""
import pytest
from test_r4_research_library import research, planning_env, payload
from app.experimental.common import StaleSourceError
from app.experimental.research_library import ResearchLibraryService
from app.experimental.store import ExperimentalStore


def test_duplicate_unicode_exact_paragraph_note_reopen_and_history_metadata(research):
    e = research
    text = '🌊e\u0301 港口'
    row = e.research.import_file(e.nid, e.scope, 'author', payload(text='\n\n'.join([text] * 25)), guard=lambda: None)
    ref = row['paragraphs'][21]['citation']
    assert ref['paragraph'] == 22
    proof = e.research.resolve(e.nid, e.scope, 'author', ref)
    assert proof['paragraph'] == 22 and proof['text'] == text
    note = e.research.create_note(e.nid, e.scope, 'author', {'title': 'Original fiction note', 'text': 'My fictional harbor closes at dawn.', 'citations': [ref]}, guard=lambda: None)
    reopened = ResearchLibraryService(ExperimentalStore(e.root, e.backend, e.url), e.novels, e.chapter_service, legacy=e.legacy, world=e.world)
    saved = reopened.notes(e.nid, e.scope, 'author')['items'][0]
    assert saved['id'] == note['id'] and saved['citations'] == [ref]
    assert saved['evidence'][0]['text'] == text
    reopened.edit_source(e.nid, e.scope, 'author', row['id'], {'title': 'New metadata', 'expected_version': 1}, guard=lambda: None)
    with pytest.raises(StaleSourceError):
        reopened.resolve(e.nid, e.scope, 'author', ref)
    history = reopened.source_history(e.nid, e.scope, 'author', row['id'])
    assert history['current_version'] == 2
    assert [item['version'] for item in history['items']] == [1, 2]
    assert all('paragraphs' not in item for item in history['items'])
