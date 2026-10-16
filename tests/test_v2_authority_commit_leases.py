"""Bounded behavioral probes for original session and File authority leases.

Threaded lock-order probes run in owned child processes. A regression cannot
strand pytest behind a blocked thread; the parent retains logs and terminates
only the exact child it launched on a bounded timeout.
"""
from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Thread, current_thread

import pytest


def _session_probe(operation, exception_exit):
    from app.actor_context import SessionContext
    from app.trusted_sessions import TrustedSessionResolver

    sessions = TrustedSessionResolver()
    token = "lease-test-opaque-token"
    first = SessionContext("first-session", "first-client", "first-actor", "first-workspace")
    second = SessionContext("second-session", "second-client", "second-actor", "second-workspace")
    sessions.register(token, first)
    generation = sessions.binding_generation(token)
    attempted, finished = Event(), Event()
    outcomes = {}

    def change():
        attempted.set()
        try:
            if operation == "revoke":
                sessions.revoke(token)
            else:
                sessions.register(token, second)
            outcomes["changed"] = True
        except BaseException as exc:
            outcomes["error"] = type(exc).__name__ + ": " + str(exc)
        finally:
            finished.set()

    worker = Thread(target=change, name="session-mutator", daemon=True)

    class ExpectedExit(Exception):
        pass

    try:
        try:
            with sessions.binding_lease(token) as actor:
                worker.start()
                assert attempted.wait(3), "session mutation did not attempt the original owner"
                assert not finished.wait(.15), "session mutation crossed the held binding lease"
                assert actor.actor_id == first.actor_id and actor.session == first
                assert sessions.resolve(token).session == first
                assert sessions.binding_generation(token) == generation
                if exception_exit:
                    raise ExpectedExit("bounded callback failure")
        except ExpectedExit:
            assert exception_exit
    finally:
        if worker.ident is not None:
            worker.join(3)
        if worker.is_alive():
            print(json.dumps({"deadlock": True, "operation": operation, "outcomes": outcomes}), flush=True)
            os._exit(2)
    assert finished.is_set() and outcomes == {"changed": True}, outcomes
    if operation == "revoke":
        for read in (sessions.resolve, sessions.binding_generation):
            try:
                read(token)
            except KeyError:
                pass
            else:
                raise AssertionError("revoked binding remained usable after the lease exited")
    else:
        assert sessions.resolve(token).session == second
        assert sessions.binding_generation(token) > generation
    return {"operation": operation, "exception_exit": exception_exit,
            "mutation_completed": True, "generation_stable_inside": True, "deadlock": False}


def _asset_read_probe(root, token_relation, exception_exit):
    from app.actor_context import SessionContext
    from app.creative.project_store import CreativeProjectStore
    from app.experimental.store import ExperimentalStore
    from app.repository import FileRepository
    from app.services.asset_library_service import AssetLibraryService
    from app.trusted_sessions import TrustedSessionResolver

    root.mkdir(parents=True, exist_ok=True)
    nid = FileRepository(root).create_novel({"id": "asset-session-lease", "title": "Lease owner"})["id"]
    store, assets = CreativeProjectStore(ExperimentalStore(root)), AssetLibraryService(root)
    scope = {"mode": "local", "novel_id": nid}
    key = store.key(nid, scope)
    sessions = TrustedSessionResolver()
    write_token, read_token = "write-token", "write-token" if token_relation == "same" else "read-token"
    write_session = SessionContext("write-session", "write-client", "write-actor", "workspace")
    read_session = write_session if token_relation == "same" else SessionContext(
        "read-session", "read-client", "read-actor", "workspace")
    sessions.register(write_token, write_session)
    if read_token != write_token:
        sessions.register(read_token, read_session)
    write_generation = sessions.binding_generation(write_token)
    read_generation = sessions.binding_generation(read_token)
    asset_held, binding_held = Event(), Event()
    outcomes = {}

    class ExpectedExit(Exception):
        pass

    def owner_read():
        try:
            # Actual original asset/project owner, not a replacement test lock.
            with assets.project_scope(nid, None, lambda: store.owner_lease(nid), scope_key=key):
                asset_held.set()
                assert binding_held.wait(4), "commit never acquired its session binding lease"
                # These are the original reads used by owner-held authority guards.
                assert sessions.resolve(read_token).session == read_session
                assert sessions.binding_generation(read_token) == read_generation
                outcomes["owner_read"] = "completed"
        except BaseException as exc:
            outcomes["owner_error"] = type(exc).__name__ + ": " + str(exc)

    def commit():
        try:
            assert asset_held.wait(4), "asset owner never acquired the actual project scope"
            try:
                with sessions.binding_lease(write_token) as actor:
                    assert actor.session == write_session
                    assert sessions.binding_generation(write_token) == write_generation
                    binding_held.set()
                    with assets.project_scope(nid, None, lambda: store.owner_lease(nid), scope_key=key):
                        assert assets.list(nid, actor_id=actor.actor_id) == []
                        assert store.incarnation(nid).startswith("file:")
                        if exception_exit:
                            raise ExpectedExit("bounded storage callback failure")
                outcomes["commit"] = "completed"
            except ExpectedExit:
                assert exception_exit
                outcomes["commit"] = "expected_exception"
        except BaseException as exc:
            outcomes["commit_error"] = type(exc).__name__ + ": " + str(exc)

    workers = [Thread(target=owner_read, name="asset-held-reader", daemon=True),
               Thread(target=commit, name="session-bound-commit", daemon=True)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(2)
    if any(worker.is_alive() for worker in workers):
        print(json.dumps({"deadlock": True, "asset_held": asset_held.is_set(),
            "binding_held": binding_held.is_set(), "token_relation": token_relation,
            "exception_exit": exception_exit, "outcomes": outcomes}), flush=True)
        os._exit(2)
    assert outcomes == {"owner_read": "completed", "commit": "expected_exception" if exception_exit else "completed"}, outcomes
    # Both the session mutation fence and original owner must be released even
    # when the storage callback raises. Parent still bounds this entire child.
    replacement = SessionContext("replacement-session", "replacement-client", "replacement-actor", "workspace")
    sessions.register(write_token, replacement)
    assert sessions.resolve(write_token).session == replacement
    assert sessions.binding_generation(write_token) > write_generation
    with assets.project_scope(nid, None, lambda: store.owner_lease(nid), scope_key=key):
        assert assets.list(nid, actor_id=replacement.actor_id) == []
    return {"deadlock": False, "token_relation": token_relation, "exception_exit": exception_exit,
            "owner_read_completed": True, "binding_and_asset_released": True}


def _file_workspace_probe(root, operation):
    from app.repositories.file.identity import FileIdentityRepository
    from app.repositories.file.mutation_coordinator import workspace_mutation
    from app.repositories.file.scope import FileAuthorizationRepository, FileScopeRepository

    root.mkdir(parents=True, exist_ok=True)
    scopes, authorization = FileScopeRepository(root), FileAuthorizationRepository(root)
    workspace, actor = "bounded-workspace", "bounded-actor"
    if operation == "rename":
        scopes.provision_initial_workspace(actor, workspace, "Before rename", "Original actor")
    elif operation == "create":
        FileIdentityRepository(root).save_user({"id": actor, "display_name": "Original actor",
            "status": "ACTIVE", "created_at": "2026-10-16T00:00:00+00:00",
            "updated_at": "2026-10-16T00:00:00+00:00", "metadata": None})

    authority_held, admin_attempt, workspace_held, release, admin_done = (Event() for _ in range(5))
    outcomes = {}
    original_mutation = FileAuthorizationRepository.mutation

    @contextmanager
    def observe_original_authority(self):
        if current_thread().name == "workspace-admin":
            # Observe the actual authority acquisition boundary. With the old
            # inverted order, this thread already held the workspace lease here.
            admin_attempt.set()
        with original_mutation(self):
            yield

    FileAuthorizationRepository.mutation = observe_original_authority

    def holder():
        try:
            with authorization.mutation():
                authority_held.set()
                assert admin_attempt.wait(4), "workspace operation never attempted authority"
                with workspace_mutation(root, workspace):
                    workspace_held.set()
                    assert release.wait(5), "test did not release its bounded authority lease"
            outcomes["holder"] = "released"
        except BaseException as exc:
            outcomes["holder_error"] = type(exc).__name__ + ": " + str(exc)

    def administer():
        try:
            assert authority_held.wait(4), "bounded holder never acquired original authority"
            if operation == "rename":
                result = scopes.rename_workspace(workspace, "After rename", actor)
            elif operation == "create":
                result = scopes.create_workspace(workspace, "Created workspace", actor)
            else:
                result = scopes.provision_initial_workspace(actor, workspace, "Provisioned workspace", "Original actor")
            outcomes["workspace"] = result["id"]
        except BaseException as exc:
            outcomes["admin_error"] = type(exc).__name__ + ": " + str(exc)
        finally:
            admin_done.set()

    workers = [Thread(target=holder, name="bounded-authority-holder", daemon=True),
               Thread(target=administer, name="workspace-admin", daemon=True)]
    try:
        for worker in workers:
            worker.start()
        assert workspace_held.wait(5), "authority holder could not progress to the workspace lease"
        assert not admin_done.is_set(), "workspace operation bypassed the held authority lease"
    finally:
        release.set()
        for worker in workers:
            worker.join(3)
        FileAuthorizationRepository.mutation = original_mutation
        if any(worker.is_alive() for worker in workers):
            print(json.dumps({"deadlock": True, "operation": operation, "outcomes": outcomes}), flush=True)
            os._exit(2)
    assert outcomes == {"holder": "released", "workspace": workspace}, outcomes
    stored = scopes.get("workspaces", workspace)
    assert stored["name"] == {"rename": "After rename", "create": "Created workspace",
                              "provision": "Provisioned workspace"}[operation]
    identity = FileIdentityRepository(root)
    members = identity.list_memberships(user_id=actor, workspace_id=workspace)
    assert len(members) == 1 and members[0]["status"] == "ACTIVE"
    roles = authorization.list_role_assignments(actor)
    assert len(roles) == 1 and roles[0]["scope"]["workspace_id"] == workspace
    events = authorization.list_audit_events()
    expected = "WORKSPACE_RENAMED" if operation == "rename" else "WORKSPACE_CREATED"
    assert any(item["action"] == expected for item in events)
    return {"operation": operation, "workspace_persisted": True, "audit_retained": True, "deadlock": False}


def _run_probe(tmp_path, mode, operation, exception_exit=False):
    log = tmp_path / "owned-child.log"
    with log.open("w", encoding="utf-8") as output:
        process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).resolve()),
            "--owned-probe", mode, operation, str(tmp_path / "data"), str(int(exception_exit))],
            cwd=Path(__file__).resolve().parents[1], stdout=output, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        timed_out = False
        try:
            process.wait(timeout=22)
        except subprocess.TimeoutExpired:
            timed_out = True
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=3)
    receipt = {"pid": process.pid, "mode": mode, "operation": operation,
               "returncode": process.returncode, "timed_out": timed_out,
               "child_stopped": process.poll() is not None}
    (tmp_path / "owned-child-receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    assert not timed_out, f"owned probe timed out and was stopped: {receipt}\n{log.read_text(encoding='utf-8')}"
    assert process.returncode == 0, log.read_text(encoding="utf-8")
    result = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert result["deadlock"] is False and receipt["child_stopped"] is True
    return result


@pytest.mark.parametrize("operation", ["revoke", "rebind"])
@pytest.mark.parametrize("exception_exit", [False, True])
def test_original_session_binding_lease_blocks_mutation_and_releases_on_exit(tmp_path, operation, exception_exit):
    result = _run_probe(tmp_path, "session", operation, exception_exit)
    assert result["generation_stable_inside"] and result["mutation_completed"]


@pytest.mark.file_backend_only
@pytest.mark.parametrize("operation", ["rename", "create", "provision"])
def test_original_file_workspace_operation_progresses_after_authority_then_workspace_lease(tmp_path, operation):
    result = _run_probe(tmp_path, "workspace", operation)
    assert result["workspace_persisted"] and result["audit_retained"]


@pytest.mark.file_backend_only
@pytest.mark.parametrize("token_relation", ["same", "different"])
@pytest.mark.parametrize("exception_exit", [False, True])
def test_asset_held_session_read_progresses_while_binding_commit_waits(tmp_path, token_relation, exception_exit):
    result = _run_probe(tmp_path, "asset-read", token_relation, exception_exit)
    assert result["owner_read_completed"] and result["binding_and_asset_released"]


if __name__ == "__main__":
    assert sys.argv[1] == "--owned-probe"
    _, _, mode, operation, root, exception = sys.argv
    if mode == "session":
        result = _session_probe(operation, bool(int(exception)))
    elif mode == "asset-read":
        result = _asset_read_probe(Path(root), operation, bool(int(exception)))
    else:
        result = _file_workspace_probe(Path(root), operation)
    print(json.dumps(result), flush=True)
