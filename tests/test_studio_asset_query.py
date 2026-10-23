"""Real mounted Studio GET routes over temporary File owners; no provider calls.

Only storage/service instances are replaced. The application's mounted route,
middleware, authority resolver, membership and permission checks remain real.
"""
import base64
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.file_backend_only
FLAGS = "narrative_production_v2,asset_lineage_v2"


@pytest.fixture
def rig(tmp_path, monkeypatch):
    from app import api, main
    from app.config import Settings, settings
    from app.creative.service import CreativeService
    from app.creative.workspace import IndependentWorkspaceService
    from app.experimental import api as experimental_api
    from app.experimental.media import MediaService
    from app.experimental.production_lineage import ProductionLineageService
    from app.experimental.store import ExperimentalStore
    from app.repositories.factory import create_repository_bundle
    from app.services import ChapterService, NovelService
    from app.services.asset_library_service import AssetLibraryService
    from app.services.authorization_service import AuthorizationService
    from app.services.collaboration_scope_service import CollaborationScopeService
    from app.services.identity_service import IdentityService
    from app.services.membership_authorization_service import MembershipAuthorizationService
    from app.trusted_sessions import TrustedSessionResolver

    monkeypatch.setenv("EXPERIMENTAL_FEATURES", FLAGS)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    # Settings is frozen; the repository's autouse fixture restores its fields.
    object.__setattr__(settings, "enable_collaboration_runtime", False)
    object.__setattr__(settings, "enable_packaged_runtime", False)
    bundle = create_repository_bundle(Settings(storage_backend="file", novel_data=tmp_path,
        enable_cloud=False, mock_provider=True), data_root=tmp_path)
    novels = NovelService(bundle.novels, bundle.chapters)
    chapters = ChapterService(bundle.chapters)
    store = ExperimentalStore(tmp_path, "file", "")
    assets = AssetLibraryService(tmp_path)
    creative = CreativeService(store, novels, chapters)
    media = MediaService(store, novels, chapters, assets)
    lineage = ProductionLineageService(store, novels, chapters, assets, media)
    workspace = IndependentWorkspaceService(creative, assets, lineage)
    # The mounted route closes over this original object; replacing a module
    # variable alone would accidentally test the process-global storage.
    mounted = experimental_api.independent_workspace_service
    for name, value in workspace.__dict__.items():
        monkeypatch.setattr(mounted, name, value)
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    identities = IdentityService(bundle.identity, scopes)
    grants = AuthorizationService(bundle.authorization, scopes)
    membership = MembershipAuthorizationService(identities, grants)
    sessions = TrustedSessionResolver()
    for name, value in (("novel_service", novels), ("collaboration_scope_service", scopes),
                        ("membership_authorization_service", membership),
                        ("trusted_session_resolver", sessions)):
        monkeypatch.setattr(api, name, value)
    monkeypatch.setattr(main, "trusted_session_resolver", sessions)

    def project(nid=None):
        return novels.create({"id": nid or "query-" + uuid4().hex, "title": "Synthetic query fixture"})["id"]

    nid = project()
    scope = {"mode": "local", "novel_id": nid}

    def seed(filename, kind="image", *, project_id=nid, scope_value=None, owner=None,
             required_features=("narrative_production_v2",), deleted=False, stamp=None):
        selected = scope_value or {"mode": "local", "novel_id": project_id}
        with workspace._asset_scope(project_id, selected):
            row = assets.create(project_id, filename, base64.b64encode(b"synthetic fixture bytes").decode(),
                "application/octet-stream", kind, branch_id=selected.get("branch_id"),
                required_features=required_features, owner_actor_id=owner)
            if stamp is not None:
                row["created_at"] = stamp
                assets._write_meta(row)
            if deleted:
                assets.delete(row["id"], branch_id=selected.get("branch_id"), actor_id=owner)
            return row

    client = TestClient(main.app)
    yield SimpleNamespace(client=client, nid=nid, scope=scope, seed=seed, project=project,
        workspace=workspace, assets=assets, novels=novels, scopes=scopes, identities=identities,
        grants=grants, sessions=sessions, root=tmp_path, settings=settings)
    client.close()


def get(rig, params=None, *, nid=None, headers=None):
    return rig.client.get(f"/api/projects/{nid or rig.nid}/studio/assets", params=params, headers=headers)


def ids(response):
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


def test_existing_shape_and_combined_filename_kind_filter(rig):
    first = rig.seed("Shrine Cover.PNG")
    second = rig.seed("shrine ambience.wav", "audio")
    rig.seed("Forest.png")
    assert set(get(rig).json()) == {"items"}
    assert ids(get(rig, {"q": " SHRINE ", "kind": "image"})) == [first["id"]]
    assert ids(get(rig, {"q": "shrine", "kind": "audio"})) == [second["id"]]
    assert len(ids(get(rig, {"q": "shrine"}))) == 2
    assert get(rig, {"q": "nonexistent", "kind": "image", "limit": 3}).json() == {
        "items": [], "total": 0, "limit": 3, "offset": 0, "has_more": False}


def test_name_search_is_unicode_casefold_literal_substring(rig):
    folded = rig.seed("Straße_神社.png")
    literal = rig.seed("100%_cover.png")
    rig.seed("100xxcover.png")
    assert ids(get(rig, {"q": "STRASSE_神社"})) == [folded["id"]]
    assert ids(get(rig, {"q": "%_"})) == [literal["id"]]


def test_maximum_keyword_length_is_accepted(rig):
    name = "x" * 255
    saved = rig.seed(name)
    assert ids(get(rig, {"q": name, "limit": 1})) == [saved["id"]]


def test_creation_time_precedes_id_in_sort_order(rig):
    rows = sorted([rig.seed("chronology-a.png"), rig.seed("chronology-b.png")], key=lambda row: row["id"])
    # Deliberately put the lexically larger ID first in time. A global ID sort
    # cannot accidentally satisfy this assertion; the separate tie test covers
    # the converse requirement for the secondary sort key.
    with rig.workspace._asset_scope(rig.nid, rig.scope):
        for row, stamp in zip(rows, ("2026-02-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00")):
            row["created_at"] = stamp
            rig.assets._write_meta(row)
    assert ids(get(rig, {"q": "chronology", "limit": 1})) == [rows[1]["id"]]
    assert ids(get(rig, {"q": "chronology", "limit": 1, "offset": 1})) == [rows[0]["id"]]


def test_corrupt_metadata_is_excluded_by_real_owner_before_total(rig):
    visible = rig.seed("needle-visible.png")
    damaged = rig.seed("needle-damaged.png")
    (rig.assets.root / (damaged["id"] + ".json")).write_text("{invalid-json", encoding="utf-8")
    assert ids(get(rig)) == [visible["id"]]
    response = get(rig, {"q": "needle", "limit": 1})
    assert ids(response) == [visible["id"]]
    assert response.json()["total"] == 1 and response.json()["has_more"] is False


@pytest.mark.parametrize("kind", ["image", "video", "audio", "model", "text", "prompt"])
def test_existing_stored_kinds_can_be_selected(rig, kind):
    selected = rig.seed("kind-fixture.bin", kind)
    rig.seed("different.bin", "audio" if kind != "audio" else "image")
    assert ids(get(rig, {"kind": kind, "limit": 10})) == [selected["id"]]


@pytest.mark.parametrize("query", ["", "   ", "\u3000"])
def test_empty_keyword_means_no_filter(rig, query):
    saved = rig.seed("anything.png")
    assert ids(get(rig, {"q": query})) == [saved["id"]]


def test_pagination_total_stable_ties_and_boundaries(rig):
    stamp = "2026-01-01T00:00:00+00:00"
    rows = [rig.seed(f"cover-{i}.png", stamp=stamp) for i in range(5)]
    expected = sorted(row["id"] for row in rows)
    rig.seed("other.wav", "audio", stamp=stamp)
    actual = []
    for offset in (0, 2, 4):
        response = get(rig, {"q": "cover", "kind": "image", "limit": 2, "offset": offset})
        actual.extend(ids(response))
        body = response.json()
        assert body["total"] == 5 and body["limit"] == 2 and body["offset"] == offset
        assert body["has_more"] is (offset < 4)
        assert ids(get(rig, {"q": "cover", "kind": "image", "limit": 2, "offset": offset})) == ids(response)
    assert actual == expected and len(set(actual)) == 5
    for offset in (5, 6, 1_000_000):
        response = get(rig, {"kind": "image", "limit": 100, "offset": offset})
        assert ids(response) == []
        assert response.json()["total"] == 5 and response.json()["has_more"] is False
    only_offset = get(rig, {"offset": 0}).json()
    assert only_offset["limit"] == 50 and only_offset["offset"] == 0 and only_offset["total"] == 6
    assert get(rig, {"limit": 1}).json()["offset"] == 0


@pytest.mark.parametrize("params", [
    {"kind": "unknown"}, {"kind": "IMAGE"}, {"kind": ""}, {"kind": "../private"},
    {"q": "x" * 256}, {"q": "secret\x00path"}, {"q": "secret\npath"}, {"q": "\x7f"},
    {"limit": 0}, {"limit": -1}, {"limit": 101}, {"limit": "1.5"}, {"limit": ""},
    {"offset": -1}, {"offset": 1_000_001}, {"offset": "1.5"}, {"offset": ""},
    {"offset": "9" * 100}, {"include_deleted": "not-a-bool"},
])
def test_invalid_query_returns_fixed_safe_error(rig, params):
    response = get(rig, params)
    assert response.status_code == 422
    body = response.json()
    assert body["detail"] == {"code": "EXPERIMENTAL_INVALID", "message": "ASSET_QUERY_INVALID"}
    assert body["code"] == "EXPERIMENTAL_INVALID" and body["message"] == "ASSET_QUERY_INVALID"
    assert "input" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert str(rig.root) not in response.text


def test_filter_total_respects_project_private_deleted_and_feature_visibility(rig, monkeypatch):
    visible = rig.seed("needle-visible.png")
    rig.seed("needle-owner.png", owner="other-actor")
    deleted = rig.seed("needle-deleted.png", deleted=True)
    hidden = rig.seed("needle-feature.png", required_features=("narrative_production_v2", "asset_lineage_v2"))
    other = rig.project()
    rig.seed("needle-other-project.png", project_id=other)
    assert set(ids(get(rig, {"q": "needle", "limit": 100}))) == {visible["id"], hidden["id"]}
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "narrative_production_v2")
    response = get(rig, {"q": "needle", "limit": 100})
    assert ids(response) == [visible["id"]] and response.json()["total"] == 1
    with_deleted = get(rig, {"q": "needle", "include_deleted": True, "limit": 100})
    assert set(ids(with_deleted)) == {visible["id"], deleted["id"]}
    assert with_deleted.json()["total"] == 2
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "")
    assert get(rig, {"q": "needle", "limit": 100}).status_code == 404


def test_recreated_project_does_not_adopt_old_bound_assets(rig):
    old = rig.seed("needle-old.png")
    rig.novels.delete(rig.nid)
    rig.project(rig.nid)
    new = rig.seed("needle-new.png")
    response = get(rig, {"q": "needle", "limit": 100})
    assert ids(response) == [new["id"]]
    assert response.json()["total"] == 1
    assert old["id"] not in response.text


def shared_scope(rig):
    from app.actor_context import SessionContext
    from app.authorization import AuthorizationScope, ModalityDomain, PermissionAssignment, ScopeKind
    from app.collaboration import Branch, Storyline, Workspace
    from app.identity import User, WorkspaceMembership

    object.__setattr__(rig.settings, "enable_collaboration_runtime", True)
    rig.scopes.create_workspace(Workspace("query-workspace", "Synthetic workspace"))
    rig.scopes.link_project("query-workspace", rig.nid)
    rig.scopes.create_storyline(Storyline("query-story", "query-workspace", rig.nid, "Story"))
    for bid in ("query-branch-a", "query-branch-b"):
        rig.scopes.create_branch(Branch(bid, "query-workspace", rig.nid, "query-story", bid))
    for user in ("reader", "no-grants"):
        rig.identities.create_user(User(user, user))
        rig.identities.add_membership(WorkspaceMembership("member-" + user, user, "query-workspace"))
        rig.sessions.register("token-" + user, SessionContext("session-" + user, "client", user, "query-workspace"))
    grant_scope = AuthorizationScope(ScopeKind.PROJECT, "query-workspace", rig.nid)
    rig.grants.assign_permission(PermissionAssignment("query-read", "reader", "domain.read",
        ModalityDomain.NOVEL, grant_scope, "fixture"))
    scope = {"mode": "collaboration", "novel_id": rig.nid, "workspace_id": "query-workspace",
        "storyline_id": "query-story", "branch_id": "query-branch-a"}
    return scope, {"X-Session-Token": "token-reader", "X-Branch-Id": "query-branch-a"}


def test_real_authority_session_membership_and_branch_boundaries(rig):
    from app.identity import IdentityStatus

    scope, headers = shared_scope(rig)
    first = rig.seed("needle-a.png", scope_value=scope)
    second_scope = {**scope, "branch_id": "query-branch-b"}
    second = rig.seed("needle-b.png", scope_value=second_scope)
    query = {"q": "needle", "kind": "image", "limit": 1}
    response = get(rig, query, headers=headers)
    assert ids(response) == [first["id"]] and response.json()["total"] == 1
    other_branch = get(rig, query, headers={**headers, "X-Branch-Id": "query-branch-b"})
    assert ids(other_branch) == [second["id"]] and other_branch.json()["total"] == 1
    assert get(rig, query, headers={"X-Branch-Id": "query-branch-a"}).status_code == 401
    assert get(rig, query, headers={**headers, "X-Session-Token": "invalid-token"}).status_code == 401
    assert get(rig, query, headers={"X-Session-Token": "token-reader"}).status_code == 400
    assert get(rig, query, headers={**headers, "X-Session-Token": "token-no-grants"}).status_code == 403
    other_project = rig.project()
    denied = get(rig, query, nid=other_project, headers=headers)
    assert denied.status_code == 403 and first["id"] not in denied.text
    rig.identities.set_membership_status("reader", "query-workspace", IdentityStatus.INACTIVE)
    revoked = get(rig, query, headers=headers)
    assert revoked.status_code == 403 and first["id"] not in revoked.text

