"""TaskCenter consistent-query File/HTTP contract probes.

All fixtures use synthetic temporary File projects and mounted app.main routes.
The original permission/membership/session chain and semantic_import reader run.
These probes are authored for M0 red / M1-M4 verification; execution results must
come from a real runner, never inferred from the assertions in this file.
"""
import hashlib
from dataclasses import replace

from fastapi import HTTPException

import pytest

from app.experimental.ux import TaskReader
from test_studio_asset_query import rig, shared_scope
from test_taskcenter_query_backend import (
    COVERAGE, LEGACY_KEYS, PAGE_KEYS, get, mounted,
)


pytestmark = pytest.mark.file_backend_only
AUTHORITIES = (
    "author_generation", "workflows", "semantic_import", "media", "agent_team",
    "audiobook", "voice_direction", "agents", "exports", "images",
    "review_inbox", "audio_tts", "motion", "subtitle_processing", "adaptation",
    "research_analysis", "visual_identity",
)
CAPABILITIES = {
    "authority_filter": {"supported": True, "operator": "OR"},
    "cursor": {"supported": True, "mode": "FILE_LOCAL_SEMANTIC_IMPORT_ONLY",
        "conditions": ["ACTUAL_FILE_OWNERS", "NON_PACKAGED_LOCAL_AUTHOR",
                       "NO_SESSION_OR_BRANCH_HEADER", "EXPLICIT_SEMANTIC_IMPORT_ONLY",
                       "EXISTING_PROJECT_AND_SOURCE_LIFECYCLE"]},
    "cross_owner_atomic_snapshot": False,
    "full_history_query": False,
    "cost": "UNKNOWN",
}
QUERY_ERROR = {"code": "EXPERIMENTAL_INVALID", "message": "TASKCENTER_QUERY_INVALID"}
UNSUPPORTED = {
    "code": "TASKCENTER_CURSOR_UNSUPPORTED",
    "message": "TASKCENTER_CURSOR_UNSUPPORTED",
}


@pytest.fixture(autouse=True)
def retain_two_original_file_reader_adapters(mounted):
    """Restore the second existing authority removed by the old small fixture.

    This is the registered media adapter's exact read path over its real owner.
    No media executor, provider, permission resolver or storage owner is faked.
    The collection is intentionally empty: authority selection is not inferred
    from the existence of result rows.
    """
    from app.experimental import api
    mounted.monkeypatch.setenv(
        "EXPERIMENTAL_FEATURES",
        "workspace_tools_v2,semantic_import_v2,cover_storyboard_generation",
    )
    mounted.monkeypatch.setattr(api.media_service, "store", mounted.store)
    mounted.monkeypatch.setattr(api.media_service, "novels", mounted.rig.novels)
    media = TaskReader(
        "media", "封面与分镜", "cover_storyboard_generation",
        lambda ctx: api.media_service.tasks(ctx.novel_id, ctx.scope),
        "cover_storyboard_generation",
    )
    mounted.monkeypatch.setattr(
        mounted.svc, "task_readers", mounted.svc.task_readers + (media,),
    )


def complete_business_snapshot(root):
    """Observe every durable file, excluding only the original lock directory.

    Unlike the older asset-query helper this does not ignore arbitrary dot
    paths. The original project marker and hidden business files are included.
    Read atime and operational lock-file creation are not business writes.
    """
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if relative.parts[0] == ".workspace-mutation-locks" or not path.is_file():
            continue
        info = path.stat()
        result[relative.as_posix()] = (
            info.st_ino, info.st_size, info.st_mtime_ns,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
    return result


def assert_query_error(response):
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == QUERY_ERROR
    assert "input" not in response.text
    assert "private-" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_m0_authority_filter_excludes_other_registered_authority(mounted, prefix):
    """Fixed-baseline gap: authority used to be ignored, returning all 3 jobs."""
    before = complete_business_snapshot(mounted.rig.root)
    try:
        response = get(mounted, {"authority": "media", "limit": 1}, prefix=prefix)
        assert response.status_code == 200, response.text
        page = response.json()
        assert page["items"] == []
        assert page["observed_total"] == 0
        assert page["has_more"] is False and page["next_offset"] is None
        assert page["coverage"] == COVERAGE
        assert page["source_truncated"] is False
    finally:
        assert complete_business_snapshot(mounted.rig.root) == before


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_m0_explicit_cursor_never_silently_returns_an_offset_page(mounted, prefix):
    """Fixed-baseline gap: page_mode/cursor used to be silently ignored."""
    before = complete_business_snapshot(mounted.rig.root)
    try:
        response = get(mounted, {"page_mode": "cursor", "limit": 1}, prefix=prefix)
        assert response.status_code == 501, response.text
        assert response.json()["detail"] == UNSUPPORTED
        assert "items" not in response.json() and "observed_total" not in response.json()
        assert "job-" not in response.text
        assert str(mounted.rig.root) not in response.text
        assert response.headers["cache-control"] == "no-store"
    finally:
        assert complete_business_snapshot(mounted.rig.root) == before


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_authority_or_duplicates_and_combined_filters(mounted, prefix):
    before = complete_business_snapshot(mounted.rig.root)
    try:
        params = [
            ("authority", "media"), ("authority", "semantic_import"),
            ("authority", "semantic_import"), ("q", "JOB-001"),
            ("failed_only", "true"), ("limit", "1"),
        ]
        response = get(mounted, params, prefix=prefix)
        assert response.status_code == 200, response.text
        page = response.json()
        assert [item["id"] for item in page["items"]] == ["job-001"]
        assert [item["authority"] for item in page["items"]] == ["semantic_import"]
        assert page["observed_total"] == 1
        assert page["coverage"] == COVERAGE
        assert page["has_more"] is False and page["next_offset"] is None
        empty = get(mounted, {
            "authority": "media", "q": "JOB-001", "failed_only": "true", "limit": 1,
        }, prefix=prefix)
        assert empty.status_code == 200, empty.text
        assert empty.json()["items"] == [] and empty.json()["observed_total"] == 0
    finally:
        assert complete_business_snapshot(mounted.rig.root) == before


def test_or_filter_uses_original_reader_order_not_query_parameter_order(mounted):
    """Synthetic rows are read by both real original File domain owners."""
    from app.experimental import api
    e = mounted.rig
    with mounted.store.transaction(e.nid, e.scope) as state:
        state["collections"][api.media_service.TASKS] = {
            "media-001": {
                "id": "media-001", "novel_id": e.nid, "scope": dict(e.scope),
                "status": "FAILED", "version": 1,
            },
        }
    before = complete_business_snapshot(e.root)
    try:
        response = get(mounted, [
            ("authority", "media"), ("authority", "semantic_import"),
            ("authority", "media"), ("failed_only", "true"), ("limit", "100"),
        ])
        assert response.status_code == 200, response.text
        value = response.json()
        assert [(r["authority"], r["id"]) for r in value["items"]] == [
            ("semantic_import", "job-001"), ("media", "media-001"),
        ]
        assert value["observed_total"] == 2
        assert value["has_more"] is False and value["next_offset"] is None
    finally:
        assert complete_business_snapshot(e.root) == before


@pytest.mark.parametrize("params", [
    {"authority": ""},
    {"authority": "SEMANTIC_IMPORT"},
    {"authority": "semantic_import "},
    {"authority": " semantic_import"},
    {"authority": "semantic_import,media"},
    {"authority": "private-unknown-authority"},
    [("authority", "semantic_import"), ("authority", "")],
    [("authority", "private-hidden"), ("authority", "semantic_import")],
])
def test_m0_authority_invalid_values_cannot_be_silently_ignored(mounted, params):
    before = complete_business_snapshot(mounted.rig.root)
    try:
        assert_query_error(get(mounted, params))
    finally:
        assert complete_business_snapshot(mounted.rig.root) == before


@pytest.mark.parametrize("authority", ["semantic_import", "media"])
def test_actual_registered_authorities_are_valid_even_without_observed_rows(mounted, authority):
    response = get(mounted, {"authority": authority, "limit": 1})
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["observed_total"] == (3 if authority == "semantic_import" else 0)
    assert page["coverage"] == COVERAGE
    assert "hidden_count" not in page and "denied_count" not in page
    assert "scanned_count" not in page and "reader_coverage" not in page


@pytest.mark.parametrize("params", [
    {"page_mode": ""},
    {"page_mode": "CURSOR"},
    {"page_mode": "private-invalid-mode"},
    {"page_mode": "cursor", "offset": 0},
    {"page_mode": "cursor", "offset": "private-offset"},
    {"page_mode": "cursor", "cursor": ""},
    {"page_mode": "cursor", "cursor": "x" * 513},
    [("page_mode", "offset"), ("page_mode", "private-invalid-mode")],
])
def test_new_mode_validation_has_fixed_error_and_zero_business_writes(mounted, params):
    before = complete_business_snapshot(mounted.rig.root)
    try:
        assert_query_error(get(mounted, params))
    finally:
        assert complete_business_snapshot(mounted.rig.root) == before


def test_new_mode_scalar_last_value_and_old_unknown_cursor_compatibility(mounted):
    legacy = get(mounted)
    assert legacy.status_code == 200
    assert set(legacy.json()) == LEGACY_KEYS
    assert get(mounted, {"cursor": "private-ignored-legacy-value"}).json() == legacy.json()
    response = get(mounted, [
        ("page_mode", "private-invalid-mode"), ("page_mode", "offset"),
        ("limit", "private-invalid-limit"), ("limit", "1.0"), ("offset", "0.0"),
    ])
    assert response.status_code == 200, response.text
    page = response.json()
    assert set(page) == PAGE_KEYS | {"capabilities"}
    assert page["items"] == legacy.json()["items"][:1]
    assert (page["limit"], page["offset"], page["observed_total"]) == (1, 0, 3)


def test_authority_filter_alone_keeps_legacy_envelope(mounted):
    response = get(mounted, {"authority": "semantic_import"})
    assert response.status_code == 200, response.text
    assert set(response.json()) == LEGACY_KEYS | {"observed_total", "source_truncated", "coverage", "capabilities"}
    assert response.json()["capabilities"] == CAPABILITIES
    assert response.json()["coverage"] == COVERAGE
    assert len(response.json()["items"]) == 3
    assert response.json()["observed_total"] == 3
    assert response.json()["source_truncated"] is False
    response = get(mounted, {"authority": "media"})
    assert response.status_code == 200, response.text
    assert set(response.json()) == LEGACY_KEYS | {"observed_total", "source_truncated", "coverage", "capabilities"}
    assert response.json()["items"] == []
    assert response.json()["observed_total"] == 0
    assert response.json()["capabilities"] == CAPABILITIES


def test_explicit_offset_mode_activates_default_page_without_changing_old_calls(mounted):
    response = get(mounted, {"page_mode": "offset"})
    assert response.status_code == 200, response.text
    value = response.json()
    assert set(value) == PAGE_KEYS | {"capabilities"}
    assert (value["limit"], value["offset"], value["observed_total"]) == (50, 0, 3)
    assert value["capabilities"] == CAPABILITIES
    assert set(get(mounted).json()) == LEGACY_KEYS
    assert set(get(mounted, {"limit": 1}).json()) == PAGE_KEYS


@pytest.mark.parametrize("identity_present", [False, True])
def test_unsupported_cursor_does_not_scan_readers_or_provision_project_identity(mounted, identity_present):
    marker = mounted.rig.root / "novels" / mounted.rig.nid / "creative_project_v2.json"
    if identity_present:
        if not marker.exists():
            from app.creative.project_store import CreativeProjectStore
            CreativeProjectStore(mounted.store).incarnation(mounted.rig.nid)
    else:
        # This is the test's synthetic project, before the query snapshot.
        marker.unlink(missing_ok=True)
    assert marker.exists() is identity_present

    def forbidden_read(ctx):
        pytest.fail("unsupported cursor mode scanned a reader")

    mounted.monkeypatch.setattr(
        mounted.svc, "task_readers",
        tuple(replace(item, read=forbidden_read) for item in mounted.svc.task_readers),
    )
    before = complete_business_snapshot(mounted.rig.root)
    response = get(mounted, {"page_mode": "cursor"})
    assert response.status_code == 501, response.text
    assert response.json()["detail"] == UNSUPPORTED
    assert marker.exists() is identity_present
    assert complete_business_snapshot(mounted.rig.root) == before


@pytest.mark.parametrize("case,expected", [
    ("feature", 404), ("missing", 404), ("no-read", 403), ("branch", 400),
    ("session", 401), ("invalid-session", 401), ("revoked", 403),
])
def test_original_access_precedes_new_authority_and_cursor_query_validation(mounted, case, expected):
    e = mounted.rig
    nid, headers = e.nid, None
    if case in {"no-read", "branch", "session", "invalid-session", "revoked"}:
        scope, headers = shared_scope(e)
        mounted.seed(scope=scope)
        if case == "no-read":
            headers = {**headers, "X-Session-Token": "token-no-grants"}
        elif case == "branch":
            headers = {"X-Session-Token": "token-reader"}
        elif case == "session":
            headers = {"X-Branch-Id": "query-branch-a"}
        elif case == "invalid-session":
            headers = {**headers, "X-Session-Token": "private-invalid-session"}
        elif case == "revoked":
            from app.identity import IdentityStatus
            e.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    elif case == "feature":
        mounted.monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    else:
        nid = "missing-consistent-query-project"
    before = complete_business_snapshot(e.root)
    try:
        for params in (
            {"authority": "private-hidden-owner"},
            {"page_mode": "cursor", "cursor": "private-invalid-token"},
        ):
            response = get(mounted, params, headers=headers, nid=nid)
            assert response.status_code == expected, response.text
            assert "job-" not in response.text
            assert "observed_total" not in response.json()
            assert "private-" not in response.text
            assert str(e.root) not in response.text
    finally:
        assert complete_business_snapshot(e.root) == before


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
@pytest.mark.parametrize("owner_raises", [False, True])
def test_authority_filtered_real_read_mid_revocation_aborts_everything(mounted, prefix, owner_raises):
    from app.identity import IdentityStatus
    scope, headers = shared_scope(mounted.rig)
    mounted.seed(scope=scope)
    original = mounted.svc.task_readers[0]
    before = complete_business_snapshot(mounted.rig.root)
    injected = {}

    def revoke_during_real_read(ctx):
        result = original.read(ctx)
        # The real owner read itself must have performed no business write.
        assert complete_business_snapshot(mounted.rig.root) == before
        mounted.rig.identities.set_membership_status(
            "reader", "query-workspace", IdentityStatus.INACTIVE,
        )
        # This deliberate test mutation is the only allowed business delta.
        injected["after_revocation"] = complete_business_snapshot(mounted.rig.root)
        if owner_raises:
            raise HTTPException(403, {"code": "private-original-owner-revoked"})
        return result

    mounted.monkeypatch.setattr(
        mounted.svc, "task_readers",
        (replace(original, read=revoke_during_real_read), mounted.svc.task_readers[1]),
    )
    response = get(
        mounted, {"authority": "semantic_import", "limit": 1},
        headers=headers, prefix=prefix,
    )
    assert response.status_code == 403, response.text
    assert "items" not in response.json() and "observed_total" not in response.json()
    assert "job-" not in response.text and "private-" not in response.text
    assert "after_revocation" in injected
    assert complete_business_snapshot(mounted.rig.root) == injected["after_revocation"]


@pytest.mark.parametrize("prefix", ["/api", "/api/v1"])
def test_openapi_declares_authority_or_semantics_and_explicit_modes(mounted, prefix):
    from app.main import app
    mounted.monkeypatch.setattr(app, "openapi_schema", None)
    operation = app.openapi()["paths"][
        f"{prefix}/novels/{{nid}}/experimental/workspace/tasks"
    ]["get"]
    params = {p["name"]: p for p in operation["parameters"]}
    assert {"authority", "page_mode", "cursor"} <= set(params)
    authority = params["authority"]
    assert authority["required"] is False
    assert authority["style"] == "form" and authority["explode"] is True
    assert authority["schema"]["type"] == "array"
    assert tuple(authority["schema"]["items"]["enum"]) == AUTHORITIES
    assert set(params["page_mode"]["schema"]["enum"]) == {"offset", "cursor"}
    assert params["cursor"]["schema"]["maxLength"] == 512


@pytest.mark.parametrize("status", [403, 404, 500])
def test_capabilities_are_static_and_never_dynamic_hidden_reader_coverage(mounted, status):
    baseline = get(mounted, {"authority": "semantic_import", "limit": 1})
    assert baseline.status_code == 200, baseline.text
    assert baseline.json()["capabilities"] == CAPABILITIES
    original = mounted.svc.task_readers[1]

    def failure(ctx):
        raise HTTPException(status, {"code": "private-owner-exception", "path": "private-path"})

    mounted.monkeypatch.setattr(
        mounted.svc, "task_readers",
        (mounted.svc.task_readers[0], replace(original, read=failure)),
    )
    before = complete_business_snapshot(mounted.rig.root)
    try:
        page = get(mounted, {"authority": "media", "limit": 1})
        assert page.status_code == 200, page.text
        value = page.json()
        assert value["capabilities"] == CAPABILITIES
        assert value["coverage"] == COVERAGE
        assert value["observed_total"] == 0 and value["items"] == []
        assert value["has_more"] is False and value["source_truncated"] is False
        assert "private-" not in page.text
        assert "reader_coverage" not in value and "hidden_count" not in value
        assert "denied_count" not in value and "scanned_count" not in value
        if status in {403, 404}:
            assert value["unavailable"] == []
        else:
            assert value["unavailable"] == [{
                "authority": "media", "label": "封面与分镜", "reason": "SOURCE_UNAVAILABLE",
            }]
    finally:
        assert complete_business_snapshot(mounted.rig.root) == before


def test_actual_registry_rejects_static_authority_without_reader(mounted):
    """A static OpenAPI type is not proof that the current service hosts it."""
    assert_query_error(get(mounted, {"authority": "visual_identity", "limit": 1}))


def test_filtered_empty_final_page_never_claims_history_completeness(mounted):
    mounted.seed(201)
    before = complete_business_snapshot(mounted.rig.root)
    try:
        response = get(mounted, {
            "authority": "semantic_import", "q": "job-200", "limit": 1,
        })
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["items"] == [] and value["observed_total"] == 0
        assert value["has_more"] is False and value["next_offset"] is None
        assert value["source_truncated"] is True and value["truncated"] is True
        assert value["coverage"] == COVERAGE
        assert value["capabilities"] == CAPABILITIES
        assert value["capabilities"]["cost"] == "UNKNOWN"
    finally:
        assert complete_business_snapshot(mounted.rig.root) == before


def test_complete_snapshot_includes_hidden_business_files(mounted):
    hidden = mounted.rig.root / ".synthetic-business"
    hidden.mkdir()
    (hidden / "metadata.json").write_text("{}", encoding="utf-8")
    snapshot = complete_business_snapshot(mounted.rig.root)
    assert ".synthetic-business/metadata.json" in snapshot
    assert all(not name.startswith(".workspace-mutation-locks/") for name in snapshot)
