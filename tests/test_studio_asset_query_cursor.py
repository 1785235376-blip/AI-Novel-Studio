"""Real mounted routes and temporary File owners for cursor consistency.

Mutation fixtures use the existing Asset owner; rename/type-change fixtures
edit its real metadata because this task does not add mutation endpoints.
"""
import pytest

from test_studio_asset_query import get, ids, rig, shared_scope


pytestmark = pytest.mark.file_backend_only
FIELDS = {"id", "filename", "kind", "media_type", "size", "sha256", "version",
          "created_at", "updated_at", "deleted_at"}
ENVELOPE = {"items", "total", "limit", "has_more", "next_cursor", "projection"}


def cursor_get(rig, params=None, **kwargs):
    return get(rig, {"page_mode": "cursor", **(params or {})}, **kwargs)


def first_page(rig, *, scope=None, headers=None):
    rows = [rig.seed(f"needle-{index}.png", scope_value=scope,
                     stamp="2026-10-23T00:00:00+00:00") for index in range(3)]
    response = cursor_get(rig, {"limit": 1}, headers=headers)
    assert len(ids(response)) == 1
    assert response.json()["next_cursor"]
    return rows, response.json()["next_cursor"]


def refusal(rig, response, status, rows=(), message=None):
    assert response.status_code == status, response.text
    assert response.headers["cache-control"] == "no-store"
    assert str(rig.root) not in response.text
    assert "items" not in response.json() and "total" not in response.json()
    assert all(row["id"] not in response.text for row in rows)
    if message:
        assert response.json()["message"] == message


def test_stable_cursor_traversal_has_exact_visible_total_and_allowlisted_projection(rig, monkeypatch):
    from app.experimental import api as experimental_api

    stamp = "2026-10-23T00:00:00+00:00"
    selected = [rig.seed(f"Straße-{index}.png", stamp=stamp) for index in range(5)]
    rig.seed("Straße-audio.wav", "audio", stamp=stamp)
    rig.seed("different.png", stamp=stamp)
    rig.seed("Straße-private.png", owner="another-actor", stamp=stamp)
    rig.seed("Straße-deleted.png", deleted=True, stamp=stamp)
    rig.seed("Straße-hidden.png", required_features=("asset_lineage_v2",), stamp=stamp)
    rig.seed("Straße-other-project.png", project_id=rig.project(), stamp=stamp)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")

    def full_projection_forbidden(*_args, **_kwargs):
        raise AssertionError("metadata cursor invoked content/cross-owner projection")
    monkeypatch.setattr(experimental_api.independent_workspace_service, "_view", full_projection_forbidden)
    monkeypatch.setattr(rig.assets, "_verified_content", full_projection_forbidden)
    query = {"q": " STRASSE ", "kind": "image", "limit": 2}
    visited, token = [], None
    for count in (2, 2, 1):
        response = cursor_get(rig, {**query, **({"cursor": token} if token else {})})
        page = response.json()
        visited.extend(ids(response))
        assert set(page) == ENVELOPE
        assert page["projection"] == "asset-metadata/1"
        assert page["total"] == 5 and page["limit"] == 2 and len(page["items"]) == count
        assert all(set(row) == FIELDS for row in page["items"])
        assert all(not any(key in row for key in ("parameters", "path", "owner_actor_id"))
                   for row in page["items"])
        token = page["next_cursor"]
        assert page["has_more"] is (len(visited) < 5)
        assert bool(token) is page["has_more"]
    assert visited == sorted(row["id"] for row in selected)
    assert len(visited) == len(set(visited)) == 5


def test_cursor_default_limit_empty_result_and_old_response_compatibility(rig):
    saved = rig.seed("needle.png")
    initial = cursor_get(rig)
    assert ids(initial) == [saved["id"]]
    assert initial.json()["limit"] == 50 and initial.json()["next_cursor"] is None
    assert cursor_get(rig, {"q": "absent"}).json() == {
        "items": [], "total": 0, "limit": 50, "has_more": False,
        "next_cursor": None, "projection": "asset-metadata/1"}
    assert set(get(rig).json()) == {"items"}
    assert set(get(rig, {"limit": 1}).json()) == {"items", "total", "limit", "offset", "has_more"}


@pytest.mark.parametrize("params", [
    {"page_mode": "unknown"}, {"page_mode": ""}, {"cursor": "orphan"},
    {"page_mode": "cursor", "offset": 0}, {"page_mode": "cursor", "cursor": ""},
    {"page_mode": "cursor", "cursor": "x" * 2049},
    {"page_mode": "cursor", "cursor": "非ASCII"},
])
def test_cursor_mode_and_token_invalid_parameters_keep_fixed_safe_422(rig, params):
    refusal(rig, get(rig, params), 422, message="ASSET_QUERY_INVALID")


@pytest.mark.parametrize("change", ["insert", "delete", "rename", "kind", "remove-metadata"])
def test_changed_asset_source_requires_restart_without_partial_result(rig, change):
    rows, token = first_page(rig)
    if change == "insert":
        rows.append(rig.seed("needle-new.png"))
    else:
        with rig.workspace._asset_scope(rig.nid, rig.scope):
            if change == "delete":
                rig.assets.delete(rows[-1]["id"])
            elif change == "remove-metadata":
                (rig.assets.root / (rows[-1]["id"] + ".json")).unlink()
            else:
                row = rig.assets.get(rows[-1]["id"])
                row["filename" if change == "rename" else "kind"] = "renamed.png" if change == "rename" else "audio"
                rig.assets._write_meta(row)
    response = cursor_get(rig, {"limit": 1, "cursor": token})
    refusal(rig, response, 409, rows, "ASSET_QUERY_RESTART_REQUIRED")


def test_change_during_page_is_detected_before_return(rig, monkeypatch):
    rows, token = first_page(rig)
    index = rig.workspace.query_index
    original = index.verify
    changed = []

    def mutate_before_verify(snapshot, **kwargs):
        row = rig.assets.get(rows[-1]["id"])
        row["filename"] = "changed-during-query.png"
        rig.assets._write_meta(row)
        changed.append(True)
        return original(snapshot, **kwargs)
    monkeypatch.setattr(index, "verify", mutate_before_verify)
    response = cursor_get(rig, {"limit": 1, "cursor": token})
    assert changed == [True]
    refusal(rig, response, 409, rows, "ASSET_QUERY_RESTART_REQUIRED")


@pytest.mark.parametrize("changes", [{"q": "needle"}, {"kind": "image"}, {"limit": 2},
                                      {"include_deleted": True}])
def test_cursor_is_bound_to_normalized_query_and_page_size(rig, changes):
    rows, token = first_page(rig)
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": token, **changes}), 422,
            rows, "ASSET_QUERY_INVALID")


def test_equivalent_normalized_query_can_continue(rig):
    for index in range(3):
        rig.seed(f"Straße-{index}.png")
    page = cursor_get(rig, {"q": " STRASSE ", "kind": "image", "limit": 1})
    first = ids(page)
    continued = cursor_get(rig, {"q": "straße", "kind": "image", "limit": "1.0",
                                 "cursor": page.json()["next_cursor"]})
    assert len(ids(continued)) == 1 and not set(first) & set(ids(continued))


def test_tampered_signed_token_is_refused_without_metadata(rig):
    rows, token = first_page(rig)
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": tampered}), 422,
            rows, "ASSET_QUERY_INVALID")


@pytest.mark.parametrize("prefix,suffix", [(" ", ""), ("", " "), ("\t", ""),
                                           (" " * 3000, ""), ("\u3000", "")])
def test_raw_cursor_is_bounded_before_any_model_whitespace_normalization(rig, prefix, suffix):
    rows, token = first_page(rig)
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": prefix + token + suffix}), 422,
            rows, "ASSET_QUERY_INVALID")


@pytest.mark.parametrize("field", ["filename", "kind", "media_type", "created_at", "updated_at", "deleted_at"])
@pytest.mark.parametrize("container", [dict, list])
def test_metadata_projection_rejects_nested_source_values_without_disclosure(rig, field, container):
    row = rig.seed("scalar-metadata.png")
    nested = {"_owner_actor_id": "synthetic-private-marker"}
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        current = rig.assets.get(row["id"])
        current[field] = nested if container is dict else [nested]
        rig.assets._write_meta(current)
    # Include deleted metadata explicitly so a corrupted truthy deleted_at
    # fixture reaches the projection instead of being deliberately excluded.
    response = cursor_get(rig, {"limit": 1, "include_deleted": True})
    refusal(rig, response, 503, [row], "ASSET_QUERY_INDEX_UNAVAILABLE")
    assert "synthetic-private-marker" not in response.text
    assert "_owner_actor_id" not in response.text


def test_cross_project_and_project_recreation_do_not_reuse_cursor(rig):
    rows, token = first_page(rig)
    other = rig.project()
    rig.seed("other.png", project_id=other)
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": token}, nid=other), 422,
            rows, "ASSET_QUERY_INVALID")
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    rig.seed("new-incarnation.png")
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": token}), 422,
            rows, "ASSET_QUERY_INVALID")


def test_feature_visibility_change_invalidates_cursor_binding(rig, monkeypatch):
    rows, token = first_page(rig)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": token}), 422,
            rows, "ASSET_QUERY_INVALID")


def test_expired_cursor_requires_restart_without_renewing_ttl(rig, monkeypatch):
    from app.creative.asset_query_cursor import AssetQueryCursorCodec

    clock = [1000]
    monkeypatch.setattr(AssetQueryCursorCodec, "_now", lambda self: clock[0])
    rows, token = first_page(rig)
    clock[0] = 1800
    second = cursor_get(rig, {"limit": 1, "cursor": token})
    assert len(ids(second)) == 1
    clock[0] = 1900
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": second.json()["next_cursor"]}),
            409, rows, "ASSET_QUERY_RESTART_REQUIRED")


def test_last_page_expiry_during_verify_requires_restart(rig, monkeypatch):
    from app.creative.asset_query_cursor import AssetQueryCursorCodec

    clock = [1000]
    monkeypatch.setattr(AssetQueryCursorCodec, "_now", lambda self: clock[0])
    rows = [rig.seed(f"last-page-{index}.png") for index in range(3)]
    first = cursor_get(rig, {"limit": 2})
    assert len(ids(first)) == 2
    token = first.json()["next_cursor"]
    assert token
    clock[0] = 1800
    original = rig.workspace.query_index.verify
    verified = []

    def expire_after_verify(snapshot, **kwargs):
        result = original(snapshot, **kwargs)
        clock[0] = 1900
        verified.append(True)
        return result
    monkeypatch.setattr(rig.workspace.query_index, "verify", expire_after_verify)
    response = cursor_get(rig, {"limit": 2, "cursor": token})
    assert verified == [True]
    refusal(rig, response, 409, rows, "ASSET_QUERY_RESTART_REQUIRED")


def test_branch_actor_and_revoked_membership_are_rechecked_on_every_page(rig):
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.identity import IdentityStatus

    scope, headers = shared_scope(rig)
    rows, token = first_page(rig, scope=scope, headers=headers)
    query = {"limit": 1, "cursor": token}
    other_branch = {**headers, "X-Branch-Id": "query-branch-b"}
    refusal(rig, cursor_get(rig, query, headers=other_branch), 422, rows, "ASSET_QUERY_INVALID")
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid)
    rig.grants.assign_permission(PermissionAssignment("query-second-reader", "no-grants", "domain.read",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    other_actor = {**headers, "X-Session-Token": "token-no-grants"}
    refusal(rig, cursor_get(rig, query, headers=other_actor), 422, rows, "ASSET_QUERY_INVALID")
    rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    refusal(rig, cursor_get(rig, query, headers=headers), 403, rows)
    refusal(rig, cursor_get(rig, {**query, "cursor": "invalid"}, headers=headers), 403, rows)


@pytest.mark.parametrize("when", ["before-page", "before-final-guard"])
def test_permission_revocation_uses_original_guard_not_cached_cursor_authority(rig, monkeypatch, when):
    scope, headers = shared_scope(rig)
    rows, token = first_page(rig, scope=scope, headers=headers)
    if when == "before-page":
        rig.grants.revoke_permission("query-read", "fixture")
    else:
        original = rig.workspace.query_index.verify

        def revoke_before_final_guard(snapshot, **kwargs):
            result = original(snapshot, **kwargs)
            rig.grants.revoke_permission("query-read", "fixture")
            return result
        monkeypatch.setattr(rig.workspace.query_index, "verify", revoke_before_final_guard)
    refusal(rig, cursor_get(rig, {"limit": 1, "cursor": token}, headers=headers), 403, rows)


@pytest.mark.parametrize("boundary, expected", [("no_read", 403), ("missing_branch", 400),
                                               ("feature_disabled", 404), ("missing_project", 404)])
def test_invalid_cursor_preserves_original_boundary_error(rig, monkeypatch, boundary, expected):
    headers, nid = None, rig.nid
    if boundary in {"no_read", "missing_branch"}:
        _, headers = shared_scope(rig)
        if boundary == "no_read":
            headers = {**headers, "X-Session-Token": "token-no-grants"}
        else:
            headers = {"X-Session-Token": "token-reader"}
    elif boundary == "feature_disabled":
        monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    else:
        nid = "nonexistent-project"
    for token in ("invalid", "x" * 2049):
        refusal(rig, cursor_get(rig, {"limit": 1, "cursor": token}, nid=nid, headers=headers), expected)
