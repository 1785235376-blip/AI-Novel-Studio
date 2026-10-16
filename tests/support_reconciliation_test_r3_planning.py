"""Additive reconciliation scenarios and their minimal independent fixture support."""

from __future__ import annotations

import copy

import os

import uuid

from types import SimpleNamespace

import pytest

from app.experimental.store import ExperimentalStore

from app.experimental.planning import PlanningService

@pytest.fixture(params=[pytest.param("file", marks=pytest.mark.file_backend_only), pytest.param("postgres", marks=pytest.mark.postgres_backend_only)])
def planning_env(tmp_path, request):
    backend = request.param
    url = os.getenv("TEST_POSTGRES_DATABASE_URL", "")
    if backend == "postgres" and not url:
        pytest.skip("NOT_RUN: real PostgreSQL endpoint unavailable")
    nid = "r3-" + uuid.uuid4().hex
    rows = {"characters": [{"id": "alice", "name": "Alice"}, {"id": "bob", "name": "Bob"}], "locations": [{"id": "city", "name": "City"}, {"id": "region", "name": "Region"}], "story_routes": [{"id": "route", "title": "Path"}], "canon": []}
    chapters = {f"{nid}:{i}": {"id": f"{nid}:{i}", "novel_id": nid, "number": i, "version": 1, "content": f"Synthetic chapter {i}"} for i in range(1, 5)}
    order = list(chapters)
    def get(cid):
        if cid not in chapters: raise FileNotFoundError(cid)
        return copy.deepcopy(chapters[cid])
    def novel_get(got):
        if got != nid: raise FileNotFoundError(got)
        return {"id": nid}
    novels = SimpleNamespace(get=novel_get, data_set=lambda got, name: copy.deepcopy(rows[name]))
    chapter_service = SimpleNamespace(get=get, list=lambda got: [get(cid) for cid in order])
    store = ExperimentalStore(tmp_path, backend=backend, database_url=url)
    scope = {"mode": "local", "novel_id": nid}
    env = SimpleNamespace(service=PlanningService(store, novels, chapter_service), store=store, nid=nid, scope=scope, chapters=chapters, chapter_service=chapter_service, novels=novels, rows=rows, order=order, root=tmp_path, backend=backend, url=url)
    yield env
    if backend == "postgres":
        with store._connect() as conn:
            conn.execute("DELETE FROM experimental_scope_documents WHERE novel_id = %s", (nid,))
