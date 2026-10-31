"""Bounded TaskCenter projection paging, not Production/history pagination.

Unit readers exercise aggregation boundaries. Mounted tests keep the real
middleware, scope resolver and File permission owners; no provider executes.
"""
from collections import OrderedDict
from copy import deepcopy
from threading import RLock
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.experimental.ux import ReadContext, TaskReader, WorkspaceToolsService, projected_task
from test_studio_asset_query import rig, shared_scope
from test_studio_asset_query_authority import source_snapshot


CTX = ReadContext("book", {"mode": "local", "novel_id": "book"}, "local-author")
LEGACY_KEYS = {"items", "unavailable", "truncated", "executor", "refresh", "automatic_retries"}
PAGE_KEYS = LEGACY_KEYS | {"observed_total", "limit", "offset", "has_more", "next_offset",
                           "source_truncated", "coverage"}
COVERAGE = {"scope": "BOUNDED_AUTHORIZED_PROJECTION", "completeness": "NOT_ASSERTED"}


def row(rid, ctx=CTX, **extra):
    return {"id": rid, "novel_id": ctx.novel_id, "scope": deepcopy(ctx.scope),
            "status": "QUEUED", "version": 1, **extra}


def reader(name, rows, **extra):
    return TaskReader(name, name, "history", lambda ctx: deepcopy(rows), **extra)


def service(*readers):
    return WorkspaceToolsService(None, None, None, task_readers=readers)


def tasks(svc, *, ctx=CTX, **kwargs):
    return svc.tasks(ctx, lambda flag: None, **kwargs)


def test_legacy_envelope_and_all_original_projection_fields_remain_exact():
    original = reader("owner", [row("one", status="RUNNING", prompt="never expose", error_code="secret")],
                      cancel=lambda *args: pytest.fail("read must not cancel"))
    svc = service(original)
    expected = {"items": [projected_task(original, row("one", status="RUNNING", prompt="never expose", error_code="secret"))],
                "unavailable": [], "truncated": False, "executor": False,
                "refresh": "MANUAL", "automatic_retries": False}
    assert tasks(svc) == expected
    assert tasks(svc, query="ONE") == expected
    assert set(tasks(svc)) == LEGACY_KEYS
    page = tasks(svc, limit=1)
    assert set(page) == PAGE_KEYS and page["items"] == expected["items"]
    assert page["coverage"] == COVERAGE and page["observed_total"] == 1
    assert page["next_offset"] is None and page["source_truncated"] is False
    assert "never expose" not in str(page) and "secret" not in str(page)


def test_pages_preserve_reader_order_and_reach_past_legacy_500_cap():
    readers = [reader(name, [row(f"{name}-{n:03}") for n in range(200)]) for name in ("z", "a", "m")]
    svc = service(*readers)
    expected = [projected_task(r, item) for r in readers for item in r.read(CTX)]
    legacy = tasks(svc)
    assert legacy["items"] == expected[:500] and legacy["truncated"] is True
    actual = []
    for offset in range(0, 600, 73):
        page = tasks(svc, limit=73, offset=offset)
        actual.extend(page["items"])
        more = offset + len(page["items"]) < 600
        assert page["observed_total"] == 600 and page["source_truncated"] is False
        assert page["has_more"] is more and page["truncated"] is more
        assert page["next_offset"] == (offset + len(page["items"]) if more else None)
        assert page["coverage"] == COVERAGE and "total" not in page
    assert actual == expected
    assert tasks(svc)["items"] == expected[:500]


@pytest.mark.parametrize("offset", [0, 1, 2, 1_000_000])
def test_empty_and_out_of_range_pages_never_loop(offset):
    page = tasks(service(), offset=offset)
    assert (page["items"], page["observed_total"], page["limit"], page["offset"]) == ([], 0, 50, offset)
    assert page["has_more"] is False and page["next_offset"] is None
    page = tasks(service(reader("x", [row("one")])), limit=1, offset=max(1, offset))
    assert page["items"] == [] and page["observed_total"] == 1
    assert page["has_more"] is False and page["next_offset"] is None


def test_filtering_uses_original_projection_status_casefold_and_no_trim():
    rows = [row("Straße", status="failed"), row("recover", status="RUNNING", recoverable=True),
            row("weird", status="new-unrecognized-state"), row("cancel", status="CANCELLED"),
            row("raw-only", title="needle", prompt="needle", provider_id="needle")]
    svc = service(reader("source", rows))
    assert [r["id"] for r in tasks(svc, failed_only=True, limit=1, offset=1)["items"]] == ["recover"]
    assert tasks(svc, failed_only=True, limit=1)["observed_total"] == 3
    assert tasks(svc, query="STRASSE", limit=1)["observed_total"] == 1
    assert tasks(svc, query=" STRASSE ", limit=1)["observed_total"] == 0
    assert tasks(svc, query="needle", limit=1)["observed_total"] == 0
    assert tasks(svc, query="失败", limit=1)["observed_total"] == 1


def test_scope_fences_precede_counts_without_merging_distinct_authorities():
    foreign = [row("foreign-project", novel_id="other"), row("foreign-scope", scope={"mode": "local", "novel_id": "other"}),
               row("foreign-branch", branch_id="secret-branch")]
    svc = service(reader("a", foreign + [row("same")]), reader("b", [row("same")]))
    page = tasks(svc, limit=100)
    assert [(r["authority"], r["id"]) for r in page["items"]] == [("a", "same"), ("b", "same")]
    assert page["observed_total"] == 2 and "foreign" not in str(page)


def test_export_permission_envelope_and_collaboration_scope_are_not_relaxed():
    scope = {"mode": "collaboration", "novel_id": "book", "workspace_id": "w", "storyline_id": "s", "branch_id": "b"}
    ctx = ReadContext("book", scope, "actor", "token", "b")
    envelope = {**scope, "actor_id": "actor"}
    rows = [row("ok", ctx, permission_context=envelope), row("other-actor", ctx, permission_context={**envelope, "actor_id": "other"}),
            row("no-envelope", ctx), row("other-branch", ctx, branch_id="other", permission_context=envelope)]
    page = tasks(service(reader("exports", rows)), ctx=ctx, limit=100)
    assert [r["id"] for r in page["items"]] == ["ok"] and page["observed_total"] == 1


@pytest.mark.parametrize("hint", [{"has_more": True}, {"next_offset": 100}, {"next_offset": 0}])
def test_source_truncation_is_separate_from_empty_filtered_page(hint):
    svc = service(reader("source", {"items": [row("visible")], **hint}))
    page = tasks(svc, query="not-a-match", limit=1)
    assert page["items"] == [] and page["observed_total"] == 0
    assert page["source_truncated"] is True and page["truncated"] is True
    assert page["has_more"] is False and page["next_offset"] is None


def test_per_owner_scan_bound_and_hidden_only_hints_remain_unchanged():
    calls = []
    payload = {"items": [row(str(i)) for i in range(201)]}
    svc = service(TaskReader("bounded", "bounded", "history", lambda ctx: calls.append(ctx) or payload))
    page = tasks(svc, offset=200)
    assert page["observed_total"] == 200 and page["items"] == []
    assert page["source_truncated"] is True and calls == [CTX]
    hidden = [row(f"hidden-{i}", novel_id="foreign") for i in range(201)]
    svc = service(reader("hidden", {"items": hidden, "has_more": True, "total": 999999}))
    page = tasks(svc, limit=1)
    assert page["observed_total"] == 0 and page["source_truncated"] is False
    assert page["unavailable"] == [] and "hidden" not in str(page) and "999999" not in str(page)
    # Even a visible row outside the original 200-row window is not inspected.
    hidden[-1] = row("outside-window")
    assert tasks(service(reader("hidden", hidden)), limit=1)["observed_total"] == 0


@pytest.mark.parametrize("status", [403, 404, 401, 500])
def test_original_owner_failures_and_feature_denials_keep_their_policy(status):
    def denied(ctx):
        raise HTTPException(status, {"secret": "private-owner-details"})
    page = tasks(service(TaskReader("owner", "owner", "history", denied)), limit=1)
    assert page["observed_total"] == 0 and page["source_truncated"] is False
    assert page["unavailable"] == ([] if status in {403, 404} else
                                    [{"authority": "owner", "label": "owner", "reason": "SOURCE_UNAVAILABLE"}])
    assert "private-owner-details" not in str(page)


def test_disabled_reader_is_not_read_or_reported_as_hidden_coverage():
    disabled = TaskReader("hidden", "hidden", "history", lambda ctx: pytest.fail("disabled reader called"), "disabled")
    def flag(name):
        raise HTTPException(404, {"code": "EXPERIMENTAL_FEATURE_DISABLED"})
    page = service(disabled).tasks(CTX, flag, limit=1)
    assert page["items"] == [] and page["unavailable"] == []
    assert page["observed_total"] == 0 and page["source_truncated"] is False
    assert page["coverage"] == COVERAGE and "hidden" not in str(page)


def test_raw_owner_totals_and_unsupported_truncation_flags_are_not_global_counts():
    svc = service(reader("owner", {"items": [row("one")], "total": 9999, "truncated": True}))
    page = tasks(svc, limit=1)
    assert page["observed_total"] == 1 and page["has_more"] is False
    assert page["source_truncated"] is False and page["coverage"] == COVERAGE
    assert "9999" not in str(page)


@pytest.mark.parametrize("params", [{"limit": True}, {"limit": 1.0}, {"limit": "1"}, {"limit": 0},
                                    {"offset": False}, {"offset": 0.0}, {"offset": -1}, {"offset": 1_000_001}])
def test_internal_new_parameters_are_bounded_strict_and_sanitized(params):
    svc = service(TaskReader("not-read", "not-read", "history", lambda ctx: pytest.fail("invalid page read an owner")))
    with pytest.raises(ValueError, match="^TASKCENTER_QUERY_INVALID$"):
        tasks(svc, **params)
    def denied():
        raise HTTPException(403, {"code": "WORKSPACE_AUTHORITY_CHANGED"})
    with pytest.raises(HTTPException):
        tasks(svc, reauthorize=denied, **params)


@pytest.mark.parametrize("fail_at", [1, 2, 3, 4])
def test_reauthorization_refusals_are_never_swallowed_as_reader_unavailability(fail_at):
    count = 0
    calls = []
    def authorize():
        nonlocal count
        count += 1
        if count == fail_at:
            raise HTTPException(403, {"code": "WORKSPACE_AUTHORITY_CHANGED"})
    svc = service(*(TaskReader(n, n, "history", lambda ctx, n=n: calls.append(n) or [row(n)]) for n in ("a", "b")))
    with pytest.raises(HTTPException) as error:
        tasks(svc, limit=1, reauthorize=authorize)
    assert error.value.status_code == 403
    assert len(calls) == max(0, fail_at - 2)


@pytest.fixture
def mounted(rig, monkeypatch):
    from app.experimental import api
    from app.experimental.store import ExperimentalStore
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "workspace_tools_v2,semantic_import_v2")
    svc = api.workspace_tools_service
    store = ExperimentalStore(rig.root, "file", "")
    for target in (svc, api.import_service):
        monkeypatch.setattr(target, "store", store)
        monkeypatch.setattr(target, "novels", rig.novels)
    original = next(r for r in svc.task_readers if r.name == "semantic_import")
    monkeypatch.setattr(svc, "task_readers", (original,))
    def seed(count=3, scope=None):
        from app.experimental.imports import JOBS
        selected = scope or rig.scope
        with store.transaction(rig.nid, selected) as state:
            state["collections"][JOBS] = {f"job-{i:03}": row(f"job-{i:03}", ReadContext(rig.nid, selected, "local-author"),
                status="FAILED" if i % 2 else "QUEUED") for i in range(count)}
    seed()
    return SimpleNamespace(rig=rig, svc=svc, seed=seed, store=store, monkeypatch=monkeypatch)


def get(mounted, params=None, *, prefix="/api", headers=None, nid=None):
    return mounted.rig.client.get(f"{prefix}/novels/{nid or mounted.rig.nid}/experimental/workspace/tasks",
                                  params=params, headers=headers)


@pytest.mark.file_backend_only
@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_mounted_original_owner_paging_defaults_projection_and_read_only(mounted, prefix):
    before = source_snapshot(mounted.rig.root)
    legacy = get(mounted, prefix=prefix).json()
    assert set(legacy) == LEGACY_KEYS and len(legacy["items"]) == 3
    for params, limit, offset in [({"limit": 1}, 1, 0), ({"offset": 0}, 50, 0),
                                  ({"limit": 1, "offset": 1}, 1, 1)]:
        response = get(mounted, params, prefix=prefix)
        assert response.status_code == 200, response.text
        page = response.json()
        assert set(page) == PAGE_KEYS and page["items"] == legacy["items"][offset:offset + limit]
        assert page["observed_total"] == 3 and (page["limit"], page["offset"]) == (limit, offset)
        assert page["coverage"] == COVERAGE
    assert get(mounted, {"q": "job-001", "failed_only": True}, prefix=prefix).json()["items"] == legacy["items"][1:2]
    assert source_snapshot(mounted.rig.root) == before


@pytest.mark.file_backend_only
@pytest.mark.parametrize("params", [{"limit": ""}, {"limit": 0}, {"limit": -1}, {"limit": 101},
    {"limit": "1.5"}, {"limit": "secret-path"}, {"offset": ""}, {"offset": -1},
    {"offset": 1_000_001}, {"offset": "NaN"}, {"offset": "1.5"}, {"offset": "9" * 100},
    [("limit", "1"), ("limit", "bad")]])
def test_mounted_paging_validation_has_fixed_sanitized_error(mounted, params):
    before = source_snapshot(mounted.rig.root)
    response = get(mounted, params)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == {"code": "EXPERIMENTAL_INVALID", "message": "TASKCENTER_QUERY_INVALID"}
    assert "input" not in response.text and "secret-path" not in response.text
    assert source_snapshot(mounted.rig.root) == before


@pytest.mark.file_backend_only
def test_existing_wire_filters_unknown_keys_and_scalar_convention(mounted):
    assert get(mounted, {"q": "x" * 161}).status_code == 422
    assert get(mounted, {"failed_only": "not-bool"}).status_code == 422
    assert get(mounted, {"ignored": "yes", "page_size": 1, "cursor": "unused"}).json() == get(mounted).json()
    page = get(mounted, [("limit", "bad"), ("limit", "1.0"), ("offset", "0.0")]).json()
    assert page["limit"] == 1 and page["offset"] == 0 and len(page["items"]) == 1


@pytest.mark.file_backend_only
def test_original_fastapi_filter_validation_precedence_is_unchanged(mounted):
    mounted.monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    for params in ({"q": "x" * 161, "limit": "bad"}, {"failed_only": "not-bool", "offset": "bad"}):
        response = get(mounted, params)
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
    assert get(mounted, {"q": "x" * 160, "limit": "bad"}).status_code == 404


@pytest.mark.file_backend_only
def test_mounted_reader_limit_and_filtering_do_not_refill_from_unobserved_history(mounted):
    mounted.seed(201)
    page = get(mounted, {"offset": 199, "limit": 100}).json()
    assert page["observed_total"] == 200 and len(page["items"]) == 1
    assert page["source_truncated"] is True and page["has_more"] is False
    filtered = get(mounted, {"q": "job-200", "limit": 1}).json()
    assert filtered["observed_total"] == 0 and filtered["items"] == []
    assert filtered["source_truncated"] is True and filtered["next_offset"] is None


@pytest.mark.file_backend_only
@pytest.mark.parametrize("case, expected", [("feature", 404), ("missing", 404), ("no-read", 403),
    ("branch", 400), ("session", 401), ("invalid-session", 401), ("revoked", 403)])
def test_original_authority_precedes_new_bad_paging(mounted, case, expected):
    e = mounted.rig
    headers, nid = None, e.nid
    if case in {"no-read", "branch", "session", "invalid-session", "revoked"}:
        scope, headers = shared_scope(e)
        mounted.seed(scope=scope)
        if case == "no-read": headers = {**headers, "X-Session-Token": "token-no-grants"}
        if case == "branch": headers = {"X-Session-Token": "token-reader"}
        if case == "session": headers = {"X-Branch-Id": "query-branch-a"}
        if case == "invalid-session": headers = {**headers, "X-Session-Token": "invalid"}
        if case == "revoked":
            from app.identity import IdentityStatus
            e.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    elif case == "feature": mounted.monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    else: nid = "missing-project"
    for params in ({"limit": 1}, {"limit": "secret-invalid"}):
        response = get(mounted, params, headers=headers, nid=nid)
        assert response.status_code == expected, response.text
        assert "job-" not in response.text and "observed_total" not in response.json()


@pytest.mark.file_backend_only
def test_collaboration_needs_no_new_production_host_gate_and_stays_branch_scoped(mounted):
    scope, headers = shared_scope(mounted.rig)
    mounted.seed(3, scope)
    other = {**scope, "branch_id": "query-branch-b"}
    mounted.seed(1, other)
    assert get(mounted, {"limit": 1}, headers=headers).json()["observed_total"] == 3
    assert get(mounted, {"limit": 1}, headers={**headers, "X-Branch-Id": "query-branch-b"}).json()["observed_total"] == 1


@pytest.mark.file_backend_only
@pytest.mark.parametrize("owner_raises", [False, True])
def test_real_membership_revocation_during_owner_read_aborts_the_whole_response(mounted, owner_raises):
    from app.identity import IdentityStatus
    scope, headers = shared_scope(mounted.rig)
    mounted.seed(scope=scope)
    original = mounted.svc.task_readers[0]
    def read(ctx):
        result = original.read(ctx)
        mounted.rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
        if owner_raises:
            raise HTTPException(403, {"code": "ORIGINAL_OWNER_REVOKED"})
        return result
    mounted.monkeypatch.setattr(mounted.svc, "task_readers", (TaskReader(original.name, original.label, original.feature, read),))
    response = get(mounted, {"limit": 1}, headers=headers)
    assert response.status_code == 403 and "observed_total" not in response.json()
    assert "job-" not in response.text


@pytest.mark.file_backend_only
def test_global_loopback_gate_still_precedes_new_paging(mounted):
    from app.main import app
    with TestClient(app, client=("192.168.1.44", 50000)) as client:
        response = client.get(f"/api/novels/{mounted.rig.nid}/experimental/workspace/tasks?limit=bad")
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "LOCAL_RUNTIME_LOOPBACK_REQUIRED"


@pytest.mark.file_backend_only
def test_packaged_gate_does_not_accept_a_development_session_for_paging(mounted):
    _, headers = shared_scope(mounted.rig)
    object.__setattr__(mounted.rig.settings, "enable_packaged_runtime", True)
    for selected in (None, headers, {"X-Session-Token": "invalid"}):
        response = get(mounted, {"limit": "bad"}, headers=selected)
        assert response.status_code == 401 and "observed_total" not in response.json()
        assert "TASKCENTER_QUERY_INVALID" not in response.text


@pytest.mark.file_backend_only
def test_openapi_lists_opt_in_integer_bounds_on_both_mounted_routes(mounted):
    from app.main import app
    mounted.monkeypatch.setattr(app, "openapi_schema", None)
    schema = app.openapi()
    for prefix in ("/api", "/api/v1"):
        params = {p["name"]: p for p in schema["paths"][f"{prefix}/novels/{{nid}}/experimental/workspace/tasks"]["get"]["parameters"]}
        for name, minimum, maximum in (("limit", 1, 100), ("offset", 0, 1_000_000)):
            assert params[name]["required"] is False
            variants = params[name]["schema"].get("anyOf", [params[name]["schema"]])
            integer = next(v for v in variants if v.get("type") == "integer")
            assert integer["minimum"] == minimum and integer["maximum"] == maximum


def test_original_author_scan_window_does_not_become_global_complete():
    from app.experimental.author_task_projection import create_author_task_reader
    visited = []
    # A visible historical job outside the recent 1000 IDs is deliberately not read.
    jobs = OrderedDict((str(i), SimpleNamespace(novel_id="book" if i == 0 else "foreign")) for i in range(1001))
    manager = SimpleNamespace(jobs=jobs, lock=RLock(), get=lambda jid: visited.append(jid) or jobs[jid])
    original = create_author_task_reader(manager, lambda *args: (CTX.actor, CTX.scope), lambda flag: None,
                                        lambda *args: pytest.fail("foreign candidates must not reach generation"))
    page = tasks(service(TaskReader("author_generation", "正文生成", "history", original)), limit=100)
    assert len(visited) == 1000 and "0" not in visited
    assert page["observed_total"] == 0 and page["source_truncated"] is False and page["coverage"] == COVERAGE


def test_original_adaptation_silent_cap_remains_unknown_not_complete():
    from app.experimental.adaptation_projection import adaptation_reader
    proposal = {"id": "p", "revision": 1, "title": "proposal", "created_at": "2026-01-01", "execution_manifest": [
        {"id": f"task-{i}", "status": "QUEUED", "source_chapter_id": "book:1", "source_version": 1,
         "target_chapter_id": "book:2", "unit": "chapter"} for i in range(201)]}
    owner = SimpleNamespace(list=lambda *args: [proposal], _source=lambda *args, **kwargs: None)
    legacy = SimpleNamespace(collaboration_scope_service=SimpleNamespace(repository=SimpleNamespace(project_workspace=lambda nid: None)),
                             _adaptation_context=lambda *args: (None, None))
    original = adaptation_reader(owner, legacy, lambda flag: None)
    page = tasks(service(TaskReader("adaptation", "改编原任务", "adaptation_lifecycle_v1", original)), limit=100, offset=100)
    assert page["observed_total"] == 200 and page["has_more"] is False
    assert page["source_truncated"] is False and page["coverage"] == COVERAGE


@pytest.mark.file_backend_only
def test_internal_search_diagnostics_preflight_and_notices_keep_legacy_default(mounted):
    from app.experimental import api
    from app.experimental.reader_preflight import ReaderPreflightService
    from app.experimental.writing_sessions import WritingSessionsService
    e, svc = mounted.rig, mounted.svc
    ctx = ReadContext(e.nid, e.scope, "local-author")
    readers = tuple(reader(name, [row(f"{name}-{i}", ctx, status="FAILED") for i in range(200)]) for name in ("a", "b", "c"))
    mounted.monkeypatch.setattr(svc, "task_readers", readers)
    mounted.monkeypatch.setattr(svc, "chapter_reader", lambda ctx: [])
    mounted.monkeypatch.setattr(svc, "entity_readers", {name: lambda ctx: [] for name in
        ("character", "location", "foreshadowing", "volume", "scene", "timeline", "organization", "rule", "story_graph", "asset", "workflow")})
    mounted.monkeypatch.setattr(svc, "finding_reader", None)
    default = api.read_optional_workspace_tasks(ctx)
    assert set(default) == LEGACY_KEYS and len(default["items"]) == 500 and default["truncated"] is True
    search = svc.search(ctx, kind="task", limit=2000, require_flag=api.require_flag)
    assert len(search["items"]) == 500
    diagnostic = svc.diagnostics(ctx, {}, api.require_flag)
    assert len(diagnostic["sections"]["task_states"]) == 500
    sources = SimpleNamespace(novels=e.novels, chapter_reader=lambda ctx: [], _source_rows=lambda ctx, kind: [], _owner=svc._owner)
    preflight = ReaderPreflightService(mounted.store, e.novels, None, sources=sources, task_reader=api.read_optional_workspace_tasks)
    report = preflight.preflight(ctx, {"format": "txt"})
    assert sum(f["code"] == "UNRESOLVED_TASK" for f in report["findings"]) == 500
    sessions = WritingSessionsService(mounted.store, e.novels, None, sources=sources, task_reader=api.read_optional_workspace_tasks)
    assert len(sessions.notices(ctx)["items"]) == 500
    assert get(mounted, {"limit": 1}).json()["observed_total"] == 600
    assert api.read_optional_workspace_tasks(ctx) == default
