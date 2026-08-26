from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.document import document_to_markdown
from app.repositories.postgres.chapter import PostgresChapterRepository


CASES = [
    ({"type": "doc", "content": []}, ""),
    ({"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "One"}]}]}, "One\n\n"),
    ({"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "One"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Two"}]},
    ]}, "One\n\nTwo\n\n"),
    ({"type": "doc", "content": [
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Title"}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "Body"}]},
    ]}, "## Title\n\nBody\n\n"),
]


@pytest.mark.parametrize(("document", "expected"), CASES)
def test_document_markdown_eof_policy(document, expected):
    assert document_to_markdown(document) == expected


@pytest.mark.parametrize(("document", "expected"), CASES)
def test_postgres_chapter_uses_shared_markdown_renderer(document, expected):
    novel = SimpleNamespace(slug="novel")
    chapter = SimpleNamespace(chapter_number=1, document=document, title="Title",
                              workflow_status="DRAFT", version=1, is_archived=False,
                              updated_at=None)
    assert PostgresChapterRepository._external(novel, chapter)["content"] == expected
