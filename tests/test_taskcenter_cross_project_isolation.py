"""TaskCenter query isolation across projects (synthetic File/local rig).

The local development runtime intentionally has no multi-user project boundary;
these tests pin the *data and cursor source binding* instead: a cursor issued for
one project must never be replayed on another, an unrelated project queries as
empty rather than inheriting nearby rows, and a foreign-owner row placed in the
project's own document is not projected.
"""
from __future__ import annotations

from copy import deepcopy

import pytest

from test_studio_asset_query import rig  # noqa: F401 - fixture required by cursor_rig
from test_taskcenter_lifecycle_http import cursor_rig, get  # noqa: F401 - pytest fixtures/helpers

pytestmark = pytest.mark.file_backend_only


def test_cursor_cannot_be_replayed_on_another_project(cursor_rig):
    e = cursor_rig
    other = e.rig.project()
    first = get(e)
    assert first.status_code == 200, first.text
    cursor = first.json()["next_cursor"]
    assert cursor
    crossed = get(e, {"cursor": cursor}, nid=other)
    # A foreign cursor is never accepted; a project without a semantic-import
    # source fails closed (501) instead of interpreting the foreign cursor.
    assert crossed.status_code in (409, 422, 501), crossed.text
    assert "job-000" not in crossed.text and "private-" not in crossed.text
    # An unrelated project is empty (or explicitly unsupported), never a view of
    # the first project's rows.
    empty = get(e, nid=other)
    assert empty.status_code in (200, 501), empty.text
    assert "job-000" not in empty.text and "private-" not in empty.text
    if empty.status_code == 200:
        assert empty.json()["items"] == [] and empty.json()["observed_total"] == 0
    # The original project's own continuation is unaffected.
    again = get(e, {"cursor": cursor})
    assert again.status_code == 200, again.text
    assert [row["id"] for row in again.json()["items"]] == ["job-001"]


def test_foreign_owner_row_in_own_document_is_not_projected(cursor_rig):
    e = cursor_rig
    other = e.rig.project()
    with e.store.transaction(e.rig.nid, e.rig.scope) as document:
        from app.experimental.imports import JOBS
        document["collections"].setdefault(JOBS, {})["job-foreign"] = {
            "id": "job-foreign", "novel_id": other,
            "scope": {**deepcopy(e.rig.scope), "novel_id": other},
            "status": "QUEUED", "version": 1,
            "prompt": "foreign-private", "error": "foreign-credential",
        }
    rows = get(e, {"limit": 50})
    # A document containing a foreign-owner row either projects only the own
    # rows or fails closed as unsupported; it must never surface the foreign row.
    assert rows.status_code in (200, 501), rows.text
    body = rows.text
    if rows.status_code == 200:
        assert rows.json()["observed_total"] == 3
    assert "job-foreign" not in body
    assert "foreign-private" not in body and "foreign-credential" not in body
    assert other not in body


def test_cursor_binding_includes_authority_selection(cursor_rig):
    from copy import deepcopy
    from app.services.export_job_service import ExportJobService

    e = cursor_rig
    source = ExportJobService(e.rig.root, lambda *args: pytest.fail("no exporter"))
    from app import api as legacy
    e.monkeypatch.setattr(legacy, "export_job_service", source)
    e.monkeypatch.setattr(source, "_submit", lambda *args: None)
    e.monkeypatch.setattr(e.adapter.export_adapter, "source", source)
    source.create(e.rig.nid, "txt", permission_context=deepcopy(e.rig.scope))
    semantic_only = get(e, {"authority": "semantic_import"})
    assert semantic_only.status_code == 200, semantic_only.text
    cursor = semantic_only.json()["next_cursor"]
    widened = get(e, {"authority": ["semantic_import", "exports"], "cursor": cursor})
    assert widened.status_code in (409, 422), widened.text
    assert "job-000" not in widened.text and "private-" not in widened.text
    source._pool.shutdown(wait=False)


