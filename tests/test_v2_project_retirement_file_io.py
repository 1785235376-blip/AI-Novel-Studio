"""Additive File retirement IO/notification checks; frozen tests remain unchanged."""
import errno
import pytest
from app.repositories.chapter_repository import ChapterRepository
from test_file_project_lifecycle import project, _audit_ports

def test_partial_reclaim_failure_never_restores_damaged_project_or_authority(project, monkeypatch):
    backend, novel_id, chapter_id = project
    authorization, paths, _, actor = _audit_ports(backend, novel_id)
    old = {"id": "old-project-grant", "principal_id": "old-actor", "role": "DOMAIN_LEAD", "domain": "NOVEL",
           "scope": {"kind": "PROJECT", "workspace_id": actor.workspace_id, "project_id": novel_id}}
    authorization.save_role_assignment(old)
    def partially_remove(path):
        next((path / "chapters").glob("*.md")).unlink()
        raise OSError(errno.EACCES, "synthetic locked remaining file")
    with monkeypatch.context() as patch:
        from app import project_retirement
        patch.setattr(project_retirement.shutil,"rmtree",partially_remove)
        paths.delete_project(actor.workspace_id,novel_id,actor)
    assert not (backend.novels / novel_id).exists()
    assert paths.scopes.project_workspace(novel_id) is None
    assert old not in authorization.list_role_assignments()
    assert any(row["action"] == "PROJECT_DELETED" for row in authorization.list_audit_events())
    assert backend.list_novels() == []
    with pytest.raises(FileNotFoundError):
        ChapterRepository(backend).get(chapter_id)

def test_failed_link_and_partial_cleanup_cannot_leave_public_orphan(project, monkeypatch):
    backend, original_id, _ = project
    authorization, paths, _, actor = _audit_ports(backend, original_id)
    target = original_id + "-failed-create"
    scope_before = paths.scopes._read()
    auth_before = authorization._read()
    original_link = paths.scopes.link_project
    def failed_link(*args):
        original_link(*args)
        raise ValueError("SYNTHETIC_LINK_FAILURE_AFTER_WRITE")
    def partially_remove(path):
        (path / "novel.json").unlink()
        raise OSError(errno.EACCES, "synthetic locked creation file")
    with monkeypatch.context() as patch:
        from app import project_retirement
        patch.setattr(paths.scopes,"link_project",failed_link)
        patch.setattr(project_retirement.shutil,"rmtree",partially_remove)
        with pytest.raises(ValueError,match="SYNTHETIC_LINK_FAILURE_AFTER_WRITE"):
            paths.create_linked_novel({"id":target,"title":"Failed new owner"},actor.workspace_id)
    assert not (backend.novels / target).exists()
    assert paths.scopes._read() == scope_before
    assert authorization._read() == auth_before
    assert [row["id"] for row in backend.list_novels()] == [original_id]
    assert paths.create_linked_novel({"id":target,"title":"Legitimate retry"},actor.workspace_id)["id"] == target
    assert paths.scopes.project_workspace(target) == actor.workspace_id

def test_linked_project_notification_observes_only_committed_binding(project, monkeypatch):
    from app.runtime_events import runtime_events
    backend, original_id, _ = project
    _, paths, _, actor = _audit_ports(backend, original_id)
    events=[]
    def observed(change):
        events.append((change.project_id,paths.scopes.project_workspace(change.project_id)))
    unsubscribe=runtime_events.subscribe(observed)
    try:
        target=original_id+"-committed-create"
        paths.create_linked_novel({"id":target,"title":"Committed owner"},actor.workspace_id)
        assert events == [(target,actor.workspace_id)]
        def fail(*args):raise ValueError("SYNTHETIC_LINK_FAILURE")
        with monkeypatch.context() as patch:
            patch.setattr(paths.scopes,"link_project",fail)
            with pytest.raises(ValueError,match="SYNTHETIC_LINK_FAILURE"):
                paths.create_linked_novel({"id":target+"-failed","title":"Failed owner"},actor.workspace_id)
        assert events == [(target,actor.workspace_id)]
    finally:
        unsubscribe()
