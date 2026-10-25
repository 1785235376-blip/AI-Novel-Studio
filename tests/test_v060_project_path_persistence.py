import json

import pytest

from app.actor_context import ActorContext, SessionContext
from app.application.persistence import AtomicPathMutationPort
from app.collaboration import Branch, Storyline, Workspace
from app.repositories.factory import create_repository_bundle
from app.services.collaboration_scope_service import CollaborationScopeService


@pytest.mark.file_backend_only
def test_file_project_path_creation_is_linked_named_audited_and_navigable(tmp_path):
    bundle=create_repository_bundle(data_root=tmp_path)
    scopes=CollaborationScopeService(bundle.scope,bundle.novels)
    scopes.create_workspace(Workspace("w","Workspace"))
    actor=ActorContext("alice","w",SessionContext("session","client","alice","w"))
    mutations=AtomicPathMutationPort(bundle.novels,bundle.scope,bundle.authorization)

    project=mutations.create_project("w","My Novel","fantasy",actor)
    paths=scopes.navigation_paths("w")
    assert project["title"]=="My Novel" and project["genre"]=="fantasy"
    assert paths[0]["project_name"]=="My Novel"
    assert paths[0]["storyline_name"]=="Default Storyline" and paths[0]["branch_name"]=="main"

    storyline=mutations.create_storyline("w",project["id"],"Alternate",actor)
    branch=mutations.create_branch("w",project["id"],storyline["id"],"experiment",actor)
    assert branch["storyline_id"]==storyline["id"]
    actions=[row["action"] for row in bundle.authorization.list_audit_events()]
    assert set(actions)=={"PROJECT_CREATED","STORYLINE_CREATED","BRANCH_CREATED"}


@pytest.fixture
def legacy_scope_storage(tmp_path):
    # A synthetic historical File snapshot, not a new project created through
    # today's mutation APIs. This is the original collaboration_scope.json
    # shape (already present in ddf7997), with no matching novel.json.
    timestamp = "2026-01-01T00:00:00+00:00"
    data = {
        "workspaces": [
            {"id": "w", "name": "Workspace", "created_at": timestamp, "updated_at": timestamp},
            {"id": "other", "name": "Other", "created_at": timestamp, "updated_at": timestamp},
        ],
        "project_workspaces": [{"id": "legacy-project", "workspace_id": "w"}],
        "storylines": [{
            "id": "story", "workspace_id": "w", "project_id": "legacy-project",
            "name": "Legacy Story", "description": "", "created_at": timestamp,
            "updated_at": timestamp,
        }],
        "branches": [{
            "id": "branch", "workspace_id": "w", "project_id": "legacy-project",
            "storyline_id": "story", "name": "main", "parent_branch_id": None,
            "created_at": timestamp, "updated_at": timestamp, "revision": 3,
        }],
    }
    path = tmp_path / "collaboration_scope.json"
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
    return path


LEGACY_NAVIGATION_PATH = {
    "workspace_id": "w", "project_id": "legacy-project", "storyline_id": "story",
    "branch_id": "branch", "project_name": "未命名小说",
    "storyline_name": "Legacy Story", "branch_name": "main",
}


@pytest.mark.file_backend_only
@pytest.mark.parametrize("project_directory_exists", [False, True], ids=["missing-project", "missing-metadata"])
def test_navigation_keeps_legacy_linked_project_without_novel_metadata_reachable(
    tmp_path, legacy_scope_storage, project_directory_exists,
):
    project_root = tmp_path / "novels" / "legacy-project"
    if project_directory_exists:
        project_root.mkdir(parents=True)
    before = legacy_scope_storage.read_bytes()

    # Reconstruct the real File owners twice. Navigation must rely only on the
    # persisted old scope, never the former setup service or an in-memory cache.
    for _ in range(2):
        bundle = create_repository_bundle(data_root=tmp_path)
        scopes = CollaborationScopeService(bundle.scope, bundle.novels)
        if project_directory_exists:
            assert bundle.novels.get("legacy-project") == {}
        else:
            with pytest.raises(FileNotFoundError):
                bundle.novels.get("legacy-project")
        assert scopes.navigation_paths("w") == [LEGACY_NAVIGATION_PATH]
        assert scopes.navigation_paths("other") == []
        with pytest.raises(ValueError, match="^project does not belong to workspace$"):
            scopes.list_storylines("other", "legacy-project")
        assert legacy_scope_storage.read_bytes() == before
        assert project_root.exists() is project_directory_exists
        assert not (project_root / "novel.json").exists()


@pytest.mark.file_backend_only
@pytest.mark.parametrize("operation", ["link_project", "create_storyline", "create_branch"])
def test_legacy_navigation_does_not_allow_new_scope_writes_for_missing_project(
    tmp_path, legacy_scope_storage, operation,
):
    before = legacy_scope_storage.read_bytes()
    bundle = create_repository_bundle(data_root=tmp_path)
    scopes = CollaborationScopeService(bundle.scope, bundle.novels)
    assert scopes.navigation_paths("w") == [LEGACY_NAVIGATION_PATH]

    with pytest.raises(ValueError, match="^project does not exist$"):
        if operation == "link_project":
            scopes.link_project("w", "legacy-project")
        elif operation == "create_storyline":
            scopes.create_storyline(Storyline("new-story", "w", "legacy-project", "New Story"))
        else:
            scopes.create_branch(Branch("new-branch", "w", "legacy-project", "story", "new"))

    # The existing link/storyline cannot authorize writes to an absent owner,
    # but rejecting those writes must not delete or repair the old read path.
    assert legacy_scope_storage.read_bytes() == before
    assert not (tmp_path / "novels" / "legacy-project").exists()
    reloaded = create_repository_bundle(data_root=tmp_path)
    assert CollaborationScopeService(reloaded.scope, reloaded.novels).navigation_paths("w") == [LEGACY_NAVIGATION_PATH]
    assert legacy_scope_storage.read_bytes() == before
