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


@pytest.mark.file_backend_only
def test_navigation_keeps_legacy_linked_project_without_novel_metadata_reachable(tmp_path):
    bundle=create_repository_bundle(data_root=tmp_path)
    scopes=CollaborationScopeService(bundle.scope,bundle.novels)
    scopes.create_workspace(Workspace("w","Workspace"))
    bundle.scope.link_project("legacy-project","w")
    scopes.create_storyline(Storyline("story","w","legacy-project","Legacy Story"))
    scopes.create_branch(Branch("branch","w","legacy-project","story","main"))
    paths=scopes.navigation_paths("w")
    assert paths[0]["project_name"]=="未命名小说"
    assert paths[0]["project_id"]=="legacy-project"
