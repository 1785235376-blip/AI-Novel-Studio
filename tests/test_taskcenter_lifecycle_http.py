"""Real two-prefix File/local semantic-import cursor lifecycle probes.

Mounted app.main routes, original authorizer and reader, temporary actual File
repositories. Only service instances/storage and deterministic race hooks are
replaced. No synthetic successful adapter or bypass authorizer is used.
"""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace

import pytest

from test_studio_asset_query import rig
from app.experimental.imports import JOBS
from app.experimental.taskcenter_cursor import TaskCenterCursorEngine

pytestmark = pytest.mark.file_backend_only
UNSUPPORTED = {"code": "TASKCENTER_CURSOR_UNSUPPORTED", "message": "TASKCENTER_CURSOR_UNSUPPORTED"}
RESTART = {"code": "TASKCENTER_CURSOR_RESTART_REQUIRED", "message": "TASKCENTER_CURSOR_RESTART_REQUIRED"}
INVALID = {"code": "EXPERIMENTAL_INVALID", "message": "TASKCENTER_QUERY_INVALID"}


def snapshot(root):
    return {str(path.relative_to(root)): (path.stat().st_ino, path.stat().st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest())
            for path in root.rglob("*") if path.is_file()
            and path.relative_to(root).parts[0] != ".workspace-mutation-locks"}


@pytest.fixture
def cursor_rig(rig, monkeypatch):
    from app import api as legacy
    from app.experimental import api
    from app.experimental.store import ExperimentalStore
    store = ExperimentalStore(rig.root, "file", "")
    chapters = rig.workspace.creative.chapters
    monkeypatch.setattr(legacy, "chapter_service", chapters)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "workspace_tools_v2,semantic_import_v2")
    for service in (api.workspace_tools_service, api.import_service):
        monkeypatch.setattr(service, "store", store)
        monkeypatch.setattr(service, "novels", rig.novels)
        monkeypatch.setattr(service, "chapters", chapters)
    adapter = api.taskcenter_cursor_adapter
    monkeypatch.setattr(adapter, "engine", TaskCenterCursorEngine())
    # The original project owner creates identity as setup, before the first
    # real scope write. Every tested GET below must leave all business files alone.
    rig.seed("project-setup.bin", required_features=())

    def seed(count=3):
        with store.transaction(rig.nid, rig.scope) as doc:
            doc["collections"][JOBS] = {f"job-{i:03}": {
                "id": f"job-{i:03}", "novel_id": rig.nid, "scope": deepcopy(rig.scope),
                "status": "FAILED" if i % 2 else "QUEUED", "version": 1,
                "prompt": "private-manuscript", "error": "private-credential",
            } for i in range(count)}
    seed()
    return SimpleNamespace(rig=rig, store=store, source=api.import_service,
        svc=api.workspace_tools_service, adapter=adapter, seed=seed, monkeypatch=monkeypatch)


def get(e, params=None, *, prefix="/api", headers=None, nid=None):
    query = {"page_mode": "cursor", "authority": "semantic_import", "limit": 1}
    query.update(params or {})
    return e.rig.client.get(f"{prefix}/novels/{nid or e.rig.nid}/experimental/workspace/tasks",
                            params=query, headers=headers)


def assert_error(response, status, detail):
    assert response.status_code == status, response.text
    assert response.json()["detail"] == detail
    assert response.headers["cache-control"] == "no-store"
    assert "private-" not in response.text and "row_lifecycles" not in response.text


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_success_first_continuation_replay_final_and_zero_business_write(cursor_rig, prefix):
    e = cursor_rig
    before = snapshot(e.rig.root)
    first = get(e, prefix=prefix)
    assert first.status_code == 200, first.text
    page1 = first.json()
    assert [row["id"] for row in page1["items"]] == ["job-000"]
    assert page1["observed_total"] == 3 and page1["has_more"] is True
    assert page1["page_mode"] == "cursor" and page1["source_truncated"] is False
    assert "offset" not in page1 and "next_offset" not in page1
    second = get(e, {"cursor": page1["next_cursor"]}, prefix=prefix)
    assert second.status_code == 200, second.text
    page2 = second.json()
    assert [row["id"] for row in page2["items"]] == ["job-001"]
    replay = get(e, {"cursor": page1["next_cursor"]}, prefix=prefix)
    assert replay.json() == page2
    final = get(e, {"cursor": page2["next_cursor"]}, prefix=prefix)
    assert final.status_code == 200, final.text
    assert [row["id"] for row in final.json()["items"]] == ["job-002"]
    assert final.json()["next_cursor"] is None and final.json()["has_more"] is False
    assert final.json()["coverage"]["completeness"] == "NOT_ASSERTED"
    for response in (first, second, replay, final):
        assert response.headers["cache-control"] == "no-store"
        assert "private-" not in response.text and "file:" not in response.text
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("mutation", ["state", "aba", "recreate", "outside_page"])
def test_changed_relevant_row_restart_even_aba_and_outside_current_page(cursor_rig, mutation):
    e = cursor_rig
    token = get(e).json()["next_cursor"]
    rid = "job-002" if mutation == "outside_page" else "job-000"
    original = deepcopy(e.store.read(e.rig.nid, e.rig.scope)["collections"][JOBS][rid])
    with e.store.transaction(e.rig.nid, e.rig.scope) as doc:
        if mutation == "recreate":
            del doc["collections"][JOBS][rid]
        else:
            doc["collections"][JOBS][rid]["status"] = "RUNNING"
    if mutation in {"aba", "recreate"}:
        with e.store.transaction(e.rig.nid, e.rig.scope) as doc:
            doc["collections"][JOBS][rid] = original
    assert_error(get(e, {"cursor": token}), 409, RESTART)
    assert get(e).status_code == 200


@pytest.mark.parametrize("mutation", ["unselected", "hidden_tail", "unmatched"])
def test_unselected_tail_and_filter_excluded_changes_do_not_invalidate(cursor_rig, mutation):
    e = cursor_rig
    if mutation == "hidden_tail":
        e.seed(201)
    filters = {"q": "job-00"} if mutation != "unmatched" else {"failed_only": True}
    if mutation == "unmatched":
        e.seed(5)
    first = get(e, filters).json()
    with e.store.transaction(e.rig.nid, e.rig.scope) as doc:
        if mutation == "unselected":
            doc["collections"]["private_unselected_collection"] = {"secret": {"activity": 1}}
        else:
            rid = "job-200" if mutation == "hidden_tail" else "job-000"
            doc["collections"][JOBS][rid]["prompt"] = "private-changed-hidden-content"
    response = get(e, {**filters, "cursor": first["next_cursor"]})
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("params", [{"authority": "media"}, {"authority": "author_generation"},
                                    {"authority": ["semantic_import", "media"]}])
def test_other_authorities_remain_unsupported(cursor_rig, params):
    assert_error(get(cursor_rig, params), 501, UNSUPPORTED)


@pytest.mark.parametrize("header", ["X-Session-Token", "X-Branch-Id"])
def test_even_empty_session_and_branch_headers_are_unsupported(cursor_rig, header):
    assert_error(get(cursor_rig, headers={header: ""}), 501, UNSUPPORTED)


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("params", [{"cursor": "private-bad-token"}, {"q": "private-" * 30},
                                    {"failed_only": "private-nonbool"}, {"offset": "0"}])
def test_new_query_errors_are_sanitized_no_store(cursor_rig, prefix, params):
    assert_error(get(cursor_rig, params, prefix=prefix), 422, INVALID)


def test_validation_keeps_original_access_precedence(cursor_rig):
    response = get(cursor_rig, {"q": "private-" * 30}, nid="missing-project")
    assert response.status_code == 404, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "private-" not in response.text


@pytest.mark.parametrize("kind", ["legacy", "missing_marker"])
def test_initial_unbound_owner_is_unsupported_without_read_repair(cursor_rig, kind):
    e = cursor_rig
    if kind == "legacy":
        path = e.store.path(e.rig.nid, e.rig.scope)
        document = json.loads(path.read_text())
        document = {key: value for key, value in document.items()
                    if key in {"schema_version", "novel_id", "scope", "collections"}}
        path.write_text(json.dumps(document), encoding="utf-8")
    else:
        (e.rig.root / "novels" / e.rig.nid / "creative_project_v2.json").unlink()
    before = snapshot(e.rig.root)
    assert_error(get(e), 501, UNSUPPORTED)
    assert snapshot(e.rig.root) == before


def test_project_identity_change_rejects_old_token_and_new_first_page(cursor_rig):
    e = cursor_rig
    token = get(e).json()["next_cursor"]
    marker = e.rig.root / "novels" / e.rig.nid / "creative_project_v2.json"
    marker.unlink()
    e.rig.workspace.creative.store.incarnation(e.rig.nid)
    before = snapshot(e.rig.root)
    assert_error(get(e, {"cursor": token}), 409, RESTART)
    assert_error(get(e), 501, UNSUPPORTED)
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("kind", ["expired", "evicted", "restarted", "query", "limit"])
def test_cursor_metadata_lifetime_and_binding_restart(cursor_rig, kind):
    e = cursor_rig
    now = [0.0]
    e.monkeypatch.setattr(e.adapter, "engine", TaskCenterCursorEngine(capacity=1, ttl_seconds=1, clock=lambda: now[0]))
    token = get(e).json()["next_cursor"]
    params = {"cursor": token}
    if kind == "expired":
        now[0] = 1.0
    elif kind == "evicted":
        assert get(e).status_code == 200
    elif kind == "restarted":
        e.monkeypatch.setattr(e.adapter, "engine", TaskCenterCursorEngine())
    elif kind == "query":
        params["q"] = "job-"
    else:
        params["limit"] = 2
    assert_error(get(e, params), 409, RESTART)


def test_wrong_actual_repository_owner_cannot_be_selected_from_settings(cursor_rig):
    e = cursor_rig
    e.monkeypatch.setattr(e.adapter, "actual_repositories", lambda: (None, None))
    assert_error(get(e), 501, UNSUPPORTED)


def test_reader_denial_never_uses_captured_rows_as_permission(cursor_rig):
    e = cursor_rig
    # Replace only the source's original reader implementation with a failure;
    # the configured reader still calls this owner through the normal path.
    from fastapi import HTTPException
    e.monkeypatch.setattr(e.source, "jobs", lambda *args: (_ for _ in ()).throw(HTTPException(403, {"private": "denied"})))
    assert_error(get(e), 501, UNSUPPORTED)


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_jobs_created_by_original_http_writer_are_cursor_pageable(cursor_rig, prefix):
    e = cursor_rig
    nid = e.rig.project()
    # Real asset creation uses the original CreativeProjectStore owner without
    # constructing a marker in this test or running a reader to repair one.
    e.rig.seed("original-owner-setup.bin", project_id=nid, required_features=())
    chapter = e.source.chapters.create(nid, {"title": "Source", "content": "Alice entered the forest."})
    ids = []
    for _ in range(3):
        created = e.rig.client.post(f"{prefix}/novels/{nid}/experimental/imports/jobs",
                                    json={"chapter_ids": [chapter["id"]]})
        assert created.status_code == 201, created.text
        ids.append(created.json()["id"])
    before = snapshot(e.rig.root)
    response = get(e, prefix=prefix, nid=nid)
    actual = []
    while True:
        assert response.status_code == 200, response.text
        actual.extend(row["id"] for row in response.json()["items"])
        token = response.json()["next_cursor"]
        if token is None:
            break
        response = get(e, {"cursor": token}, prefix=prefix, nid=nid)
    assert set(actual) == set(ids) and len(actual) == len(ids)
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("stage", ["reader", "engine"])
@pytest.mark.parametrize("replacement", ["source_store", "actual_novels"])
def test_actual_repository_replacement_mid_request_fails_closed(cursor_rig, tmp_path, stage, replacement):
    from app import api as legacy
    from app.experimental.store import ExperimentalStore
    e = cursor_rig
    token = get(e).json()["next_cursor"]
    from app.config import Settings
    from app.repositories.factory import create_repository_bundle
    from app.services import NovelService
    other_root = tmp_path / "actual-other-owner"
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=other_root,
        enable_cloud=False, mock_provider=True), data_root=other_root)
    other_novels = NovelService(bundle.novels, bundle.chapters)
    other_novels.create({"id": e.rig.nid, "title": "Same slug, different original owner"})
    def swap():
        if replacement == "source_store":
            e.monkeypatch.setattr(e.source, "store", ExperimentalStore(tmp_path / "other-owner"))
        else:
            e.monkeypatch.setattr(legacy, "novel_service", other_novels)
    if stage == "reader":
        original = e.source.jobs
        def hooked(*args, **kwargs):
            rows = original(*args, **kwargs)
            swap()
            return rows
        e.monkeypatch.setattr(e.source, "jobs", hooked)
    else:
        original = e.adapter.engine.page
        def hooked(**kwargs):
            page = original(**kwargs)
            swap()
            return page
        e.monkeypatch.setattr(e.adapter.engine, "page", hooked)
    response = get(e, {"cursor": token})
    assert response.status_code in {409, 501}, response.text
    assert response.headers["cache-control"] == "no-store"
    assert "items" not in response.json()


@pytest.mark.parametrize("stage", ["before_capture", "reader", "after_projection", "engine", "final_capture"])
def test_persistent_aba_in_each_read_phase_requires_restart(cursor_rig, stage):
    e = cursor_rig
    token = get(e).json()["next_cursor"]
    def aba():
        original = deepcopy(e.store.read(e.rig.nid, e.rig.scope)["collections"][JOBS]["job-002"])
        with e.store.transaction(e.rig.nid, e.rig.scope) as doc:
            doc["collections"][JOBS]["job-002"]["status"] = "RUNNING"
        with e.store.transaction(e.rig.nid, e.rig.scope) as doc:
            doc["collections"][JOBS]["job-002"] = original
    if stage == "reader":
        original = e.source.jobs
        def hooked(*args, **kwargs):
            rows = original(*args, **kwargs)
            aba()
            return rows
        e.monkeypatch.setattr(e.source, "jobs", hooked)
    elif stage == "engine":
        original = e.adapter.engine.page
        def hooked(**kwargs):
            result = original(**kwargs)
            aba()
            return result
        e.monkeypatch.setattr(e.adapter.engine, "page", hooked)
    else:
        original = e.source.jobs_observation
        count = 0
        target = {"before_capture": 1, "after_projection": 2, "final_capture": 3}[stage]
        def hooked(*args, **kwargs):
            nonlocal count
            count += 1
            if count == target:
                aba()
            return original(*args, **kwargs)
        e.monkeypatch.setattr(e.source, "jobs_observation", hooked)
    assert_error(get(e, {"cursor": token}), 409, RESTART)


def test_unobserved_transient_membership_history_is_not_collection_aba_coverage(cursor_rig):
    """Row evidence does not promise history for a member never observed.

    In particular, do not fix this deliberate boundary with a collection epoch:
    doing so would invalidate the cursor for unselected/hidden activity too.
    """
    e = cursor_rig
    first = get(e).json()
    with e.store.transaction(e.rig.nid, e.rig.scope) as doc:
        doc["collections"][JOBS]["transient-unobserved"] = {
            "id": "transient-unobserved", "novel_id": e.rig.nid,
            "scope": deepcopy(e.rig.scope), "status": "QUEUED", "version": 1,
        }
    with e.store.transaction(e.rig.nid, e.rig.scope) as doc:
        del doc["collections"][JOBS]["transient-unobserved"]
    response = get(e, {"cursor": first["next_cursor"]})
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["items"]] == ["job-001"]


def test_real_project_retirement_and_same_id_recreation_never_adopts_old_scope(cursor_rig):
    e = cursor_rig
    token = get(e).json()["next_cursor"]
    old_scope = e.store.path(e.rig.nid, e.rig.scope).read_bytes()
    e.rig.novels.delete(e.rig.nid)
    assert e.rig.project(e.rig.nid) == e.rig.nid
    e.rig.seed("new-owner-setup.bin", required_features=())
    assert e.store.path(e.rig.nid, e.rig.scope).read_bytes() == old_scope
    before = snapshot(e.rig.root)
    assert_error(get(e, {"cursor": token}), 409, RESTART)
    assert_error(get(e), 501, UNSUPPORTED)
    assert snapshot(e.rig.root) == before


@pytest.mark.parametrize("packaged", [False, True])
def test_collaboration_is_unsupported_and_packaged_retains_original_session_gate(cursor_rig, packaged):
    from test_studio_asset_query import shared_scope
    e = cursor_rig
    _, headers = shared_scope(e.rig)
    object.__setattr__(e.rig.settings, "enable_packaged_runtime", packaged)
    response = get(e, headers=headers)
    if packaged:
        # A development trusted-session fixture is not a launcher-issued
        # packaged session. The original middleware must reject it first.
        assert response.status_code == 401
        assert response.json()["detail"] == {"code": "INVALID_SESSION"}
        assert response.headers["cache-control"] == "no-store"
    else:
        assert_error(response, 501, UNSUPPORTED)
