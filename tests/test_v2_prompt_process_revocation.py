"""Independent-process authority serialization over original Prompt owners.

Only IPC pauses at actual persistence boundaries are injected. Sessions are
issued by LocalSessionBootstrap in each API worker; membership and assignments
are changed by a different process through the original production services.
The adoption gate is enabled only in the explicitly isolated test child and is
restored there; the shipped source and the ordinary runtime gate remain false.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from uuid import uuid4

import pytest


def _write(path, value):
    path = Path(path)
    temporary = path.with_name(path.name + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _wait(path, process=None, seconds=45):
    deadline = time.monotonic() + seconds
    while not Path(path).exists():
        if process is not None and process.poll() is not None:
            raise AssertionError(f"worker exited {process.returncode} before {Path(path).name}")
        if time.monotonic() >= deadline:
            raise AssertionError(f"IPC deadline: {Path(path).name}")
        time.sleep(.02)


def _boundary(config, role):
    root = Path(config["ipc"])
    _write(root / f"{role}-persistence.json", {"pid": os.getpid(), "role": role})
    if config.get("pause_" + role):
        _wait(root / f"{role}-release", seconds=45)


def _observe_authority(config, role, e):
    """Observe, never replace, the original cross-process persistence lock."""
    folder = Path(config["ipc"])

    def event(state, **facts):
        path = folder / f"{role}-authority-{state}.json"
        if not path.exists():
            _write(path, {"pid": os.getpid(), **facts})

    if config["backend"] == "file":
        from app.repositories.file import mutation_coordinator
        root = e.authorization.repository.path.parent.resolve()
        # Role/permission revoke validates Novel.get before its auth mutation.
        # A first writer already holds that project's original lifecycle lock.
        project_first = config["pause_writer"] and config["revocation"] in {"role", "permission"}
        key = f"project-lifecycle:{(root / 'novels' / config['nid']).resolve()}" if project_first else "authorization-store"
        kind = "FILE_OS_PROJECT_LIFECYCLE" if project_first else "FILE_OS_AUTHORIZATION_STORE"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        original = mutation_coordinator._lock_file
        original_unlock = mutation_coordinator._unlock_file
        sequence = 0

        def observed_state(state, path):
            nonlocal sequence
            sequence += 1
            facts = {"pid": os.getpid(), "state": state, "sequence": sequence,
                     "kind": kind, "lock_path": str(path), "monotonic_ns": time.monotonic_ns()}
            with (folder / f"{role}-authority-events.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps(facts) + "\n")
            _write(folder / f"{role}-authority-current.json", facts)

        def targeted(handle):
            path = Path(handle.name).resolve()
            return path if path.parent == root / ".workspace-mutation-locks" and path.stem == digest else None

        def observed(handle):
            path = targeted(handle)
            if path is not None:
                observed_state("WAITING", path)
                original(handle)
                observed_state("HELD", path)
            else:
                original(handle)

        def observed_unlock(handle):
            path = targeted(handle)
            original_unlock(handle)
            if path is not None:
                observed_state("RELEASED", path)
        mutation_coordinator._lock_file = observed
        mutation_coordinator._unlock_file = observed_unlock
    else:
        repository = e.identity.repository if role == "revoker" and config["revocation"] == "membership" else e.authorization.repository
        original = repository._lock_workspace

        def observed(connection, workspace):
            facts = {"kind": "POSTGRES_ADVISORY_AUTHORIZATION", "workspace_id": workspace,
                     "backend_pid": connection.info.backend_pid}
            event("attempt", **facts)
            original(connection, workspace)
            event("acquired", **facts)
        repository._lock_workspace = observed


def _blocked_witness(config, folder, leader, follower, process):
    if config["backend"] == "file":
        follower_state = folder / f"{follower}-authority-current.json"
        holder_state = folder / f"{leader}-authority-current.json"
        _wait(follower_state, process)
        waiting = json.loads(follower_state.read_text(encoding="utf-8"))
        holding = json.loads(holder_state.read_text(encoding="utf-8"))
        assert holding["state"] == "HELD", "paused leader must currently hold the original OS lock"
        assert waiting["state"] == "WAITING", "follower must enter the original OS lock acquisition"
        assert holding["lock_path"] == waiting["lock_path"], "both processes must reach the same original OS lock"
        time.sleep(.35)
        assert json.loads(holder_state.read_text(encoding="utf-8")) == holding, "holder released its original OS lock before IPC release"
        assert json.loads(follower_state.read_text(encoding="utf-8")) == waiting, "follower acquired the original OS authority lock before release"
        witness = {"kind": holding["kind"], "same_lock_path": holding["lock_path"],
                   "holder_pid": holding["pid"], "waiter_pid": waiting["pid"],
                   "holder_state": holding, "waiter_state": waiting, "acquired_before_release": False}
    else:
        _wait(folder / f"{follower}-authority-attempt.json", process)
        holding = json.loads((folder / f"{leader}-authority-acquired.json").read_text(encoding="utf-8"))
        waiting = json.loads((folder / f"{follower}-authority-attempt.json").read_text(encoding="utf-8"))
        acquired = folder / f"{follower}-authority-acquired.json"
        import psycopg
        assert holding["workspace_id"] == waiting["workspace_id"] == config["workspace"]
        deadline = time.monotonic() + 5
        with psycopg.connect(os.environ["TEST_POSTGRES_DATABASE_URL"], connect_timeout=5, autocommit=True,
                            options="-c statement_timeout=3000") as connection:
            while True:
                assert not acquired.exists(), "follower acquired the original advisory lock before release"
                row = connection.execute(
                    "SELECT wait_event_type,pg_blocking_pids(pid) FROM pg_stat_activity WHERE pid=%s",
                    (waiting["backend_pid"],)).fetchone()
                if row and row[0] == "Lock" and holding["backend_pid"] in row[1]:
                    break
                assert time.monotonic() < deadline, "real PostgreSQL did not confirm the authority lock wait"
                time.sleep(.02)
        witness = {"kind": holding["kind"], "holder_pid": holding["pid"], "waiter_pid": waiting["pid"],
            "holder_postgres_pid": holding["backend_pid"], "waiter_postgres_pid": waiting["backend_pid"],
            "wait_event_type": row[0], "pg_blocking_pids": row[1], "acquired_before_release": False}
    _write(folder / "authority-lock-witness.json", witness)
    return witness


def _runtime(backend):
    from r3i_authorized_shared import make_env
    return make_env(backend)()


def _session(e, actor, workspace):
    from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
    from app.packaging.runtime_identity import RuntimeIdentity
    manager = LocalSessionBootstrap(runtime=RuntimeIdentity.create(), sessions=e.sessions,
        trusted_identity=TrustedLocalIdentity(actor, workspace), expected_origin="http://127.0.0.1:4173")
    return manager.exchange(bootstrap_secret=manager.take_launcher_secret(),
        runtime_instance_id=manager.runtime.runtime_instance_id,
        origin=manager.expected_origin, remote_host="127.0.0.1").session_token


def _writer(config):
    e = _runtime(config["backend"])
    import app.experimental.api as experimental
    import app.creative.prompt_adoption_api as adoption_api
    token = _session(e, config["actor"], config["workspace"])
    _observe_authority(config, "writer", e)
    headers = {"X-Session-Token": token, "X-Branch-ID": config["branch"]}
    nid = config["nid"]
    if config["operation"] == "adopt":
        original = experimental.independent_workspace_service.store.store.transaction

        @contextmanager
        def persistence(nid_arg, scope):
            with original(nid_arg, scope) as state:
                yield state
                if nid_arg == nid:
                    _boundary(config, "writer")
        experimental.independent_workspace_service.store.store.transaction = persistence
    else:
        assets = experimental.independent_workspace_service.assets
        original = assets._write_meta
        entered = False

        def persistence(meta):
            nonlocal entered
            if meta.get("novel_id") == nid and not entered:
                entered = True
                _boundary(config, "writer")
            return original(meta)
        assets._write_meta = persistence
    _write(Path(config["ipc"]) / "writer-attempt.json", {"pid": os.getpid()})
    old_gate = adoption_api.PROMPT_ADOPTION_WRITE_ENABLED
    assert old_gate is False, "production adoption gate must remain closed"
    try:
        if config["operation"] == "adopt":
            adoption_api.PROMPT_ADOPTION_WRITE_ENABLED = True
        with e.client:
            response = e.client.request(config.get("method", "POST"), config["url"], headers=headers, json=config["body"])
            first = {"pid": os.getpid(), "status": response.status_code, "body": response.json()}
            _write(Path(config["ipc"]) / "writer-first-response.json", first)
            # Keep this same original resolver and bootstrap-issued token alive
            # until the independent revoker has actually committed.
            _wait(Path(config["ipc"]) / "revocation-committed")
            denied = e.client.post(f"/api/projects/{nid}/studio/prompts", headers=headers,
                json={"text": "PRIVATE revoked token must not persist", "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex})
        return {"pid": os.getpid(), "status": response.status_code, "body": response.json(),
                "negative_status": denied.status_code, "negative_body": denied.json(),
                "same_issued_token_reused_after_revocation": True,
                "real_session_owner": "LocalSessionBootstrap", "isolated_adoption_gate": config["operation"] == "adopt"}
    finally:
        adoption_api.PROMPT_ADOPTION_WRITE_ENABLED = old_gate


def _revoker(config):
    e = _runtime(config["backend"])
    _observe_authority(config, "revoker", e)
    kind = config["revocation"]
    repository = e.identity.repository if kind == "membership" else e.authorization.repository
    if config.get("pause_revoker"):
        if config["backend"] == "file":
            original = repository._write

            def persistence(value):
                _boundary(config, "revoker")
                return original(value)
            repository._write = persistence
        else:
            original = repository.connection_factory

            class RealConnection:
                def __init__(self, connection):
                    self.connection = connection
                def __getattr__(self, name):
                    return getattr(self.connection, name)
                def commit(self):
                    _boundary(config, "revoker")
                    return self.connection.commit()

            @contextmanager
            def persistence():
                with original() as connection:
                    yield RealConnection(connection)
            repository.connection_factory = persistence
    _write(Path(config["ipc"]) / "revoker-attempt.json", {"pid": os.getpid()})
    if kind == "membership":
        from app.identity import IdentityStatus
        e.identity.set_membership_status(config["actor"], config["workspace"], IdentityStatus.INACTIVE)
    else:
        getattr(e.authorization, "revoke_" + kind)(config["assignment"], config["admin"])
    return {"pid": os.getpid(), "revocation": kind, "committed": True}


def _child(mode, config_path):
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    target = Path(config["ipc"]) / f"{mode}-result.json"
    try:
        _write(target, (_writer if mode == "writer" else _revoker)(config))
    except BaseException:
        _write(target, {"pid": os.getpid(), "error": traceback.format_exc()})
        raise


def _spawn(mode, config, folder, processes):
    config_path = folder / f"{mode}-config.json"
    _write(config_path, config)
    log = (folder / f"{mode}.log").open("w", encoding="utf-8")
    process = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker", mode, str(config_path)],
        cwd=Path(__file__).resolve().parents[1], stdout=log, stderr=subprocess.STDOUT,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    processes.append((process, log))
    return process


def _result(folder, mode, process):
    _wait(folder / f"{mode}-result.json", process)
    result = json.loads((folder / f"{mode}-result.json").read_text(encoding="utf-8"))
    assert "error" not in result, result.get("error")
    assert process.wait(timeout=15) == 0
    return result


def _private_state(e):
    import app.experimental.api as experimental
    workspace = experimental.independent_workspace_service
    return {"document": deepcopy(workspace.store.store.read(e.nid, e.scope)),
        "assets": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in workspace.assets.root.iterdir() if p.is_file() and p.suffix in {".json", ".bin"}}}


@pytest.mark.parametrize("backend", [pytest.param("file", marks=pytest.mark.file_backend_only),
                                   pytest.param("postgres", marks=pytest.mark.postgres_backend_only)])
@pytest.mark.parametrize("operation", ["create", "revise", "delete", "adopt"])
@pytest.mark.parametrize("revocation", ["membership", "role", "permission"])
@pytest.mark.parametrize("first", ["writer", "revoker"])
def test_independent_process_revocation_serializes_prompt_commit(tmp_path, backend, operation, revocation, first):
    assert os.environ.get("PROJECT_ROOT"), "use the original isolated V2 runner"
    from app.authorization import DomainRole, DomainRoleAssignment, ModalityDomain, PermissionAssignment
    from r3i_authorized_shared import build_authorized, chain
    e = build_authorized(_runtime(backend))
    e.scope = {"mode": "collaboration", "novel_id": e.nid, "workspace_id": e.workspace,
               "storyline_id": e.storyline, "branch_id": e.branch}
    flow = chain(e, "/api", e.headers)
    assignment = e.writer_role
    if revocation == "permission":
        e.authorization.revoke_role(e.writer_role, e.init_user)
        assignment = "write-" + uuid4().hex
        for permission, identity in [("domain.read", "read-" + uuid4().hex), ("domain.write", assignment)]:
            e.authorization.assign_permission(PermissionAssignment(identity, e.writer, permission,
                ModalityDomain.NOVEL, e.auth_scope, e.init_user))
    url = flow["studio"] + "/prompts"
    body = {"text": "PRIVATE process authoring 中文 🙂\n", "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex}
    if operation == "revise":
        url += "/" + flow["prompt"]["family_id"] + "/revisions"
        body.update(expected_revision=1, expected_previous_asset_id=flow["prompt"]["asset_id"])
    elif operation == "delete":
        # chain() deliberately approves its adoption source, which promotes it
        # to a shared asset. Deletion here must target an actually private one.
        private = e.client.post(flow["studio"] + "/prompts", headers=e.headers,
            json={"text": "PRIVATE unapproved deletion target", "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex})
        assert private.status_code == 201, private.text
        receipt = private.json()
        url = flow["studio"] + f"/assets/{receipt['asset_id']}?expected_version={receipt['asset_version']}"
        body = None
    elif operation == "adopt":
        url, body = flow["adopt_url"], flow["dto"]
    folder = tmp_path / f"process-{backend}-{operation}-{revocation}-{first}"
    folder.mkdir()
    config = {"backend": backend, "operation": operation, "revocation": revocation, "nid": e.nid,
        "workspace": e.workspace, "branch": e.branch, "actor": e.writer, "admin": e.init_user,
        "assignment": assignment, "url": url, "method": "DELETE" if operation == "delete" else "POST", "body": body, "ipc": str(folder),
        "pause_writer": first == "writer", "pause_revoker": first == "revoker"}
    before = _private_state(e)
    processes = []
    try:
        leader = _spawn(first, config, folder, processes)
        _wait(folder / f"{first}-persistence.json", leader)
        second = "revoker" if first == "writer" else "writer"
        follower = _spawn(second, config, folder, processes)
        _wait(folder / f"{second}-attempt.json", follower)
        # Observe its actual original OS/advisory lock acquisition, beyond the
        # API's initial authorization reads. PostgreSQL itself proves blockers.
        witness = _blocked_witness(config, folder, first, second, follower)
        assert not (folder / f"{second}-result.json").exists(), "revocation and Prompt commit were not serialized"
        assert not (folder / f"{second}-persistence.json").exists(), "the follower reached persistence before authority release"
        (folder / f"{first}-release").touch()
        workers = {first: leader, second: follower}
        revoked = _result(folder, "revoker", workers["revoker"])
        (folder / "revocation-committed").touch()
        results = {"revoker": revoked, "writer": _result(folder, "writer", workers["writer"])}
        assert results["writer"]["pid"] != results["revoker"]["pid"]
        assert os.getpid() not in {item["pid"] for item in results.values()}
        assert results["revoker"]["committed"] is True
        response = results["writer"]
        assert response["same_issued_token_reused_after_revocation"] is True
        assert response["negative_status"] == 403, response
        assert response["negative_body"]["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN", response
        assert "PRIVATE" not in json.dumps(response["negative_body"])
        if first == "writer":
            assert response["status"] == (200 if operation in {"adopt", "delete"} else 201), response
            assert _private_state(e) != before, "authorized first writer must commit"
        else:
            assert response["status"] == 403, response
            assert response["body"]["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN", response
            assert _private_state(e) == before, "revoked writer must leave all private owners unchanged"
        settled = _private_state(e)
        denied = e.client.post(flow["studio"] + "/prompts", headers=e.headers,
            json={"text": "PRIVATE must not persist", "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex})
        assert denied.status_code == 403, denied.text
        assert denied.json()["detail"]["code"] == "PROJECT_SCOPE_FORBIDDEN", denied.text
        assert "PRIVATE" not in denied.text
        assert _private_state(e) == settled
        e.authorization.assign_role(DomainRoleAssignment(uuid4().hex, e.reader, DomainRole.DOMAIN_LEAD,
            ModalityDomain.NOVEL, e.auth_scope, e.init_user))
        text = "Fresh authorized positive 中文 🙂\n"
        positive = e.client.post(flow["studio"] + "/prompts", headers=e.reader_headers,
            json={"text": text, "purpose": "IMAGE", "origin": "MANUAL", "request_id": uuid4().hex})
        assert positive.status_code == 201, positive.text
        row = positive.json()
        read = e.client.get(flow["studio"] + f"/prompts/{row['family_id']}/revisions/{row['asset_id']}/body", headers=e.reader_headers)
        assert read.status_code == 200 and read.json()["value"] == text, read.text
        _write(folder / "assertions.json", {"status": "PASS", "backend": backend, "operation": operation,
            "revocation": revocation, "first": first, "writer_pid": results["writer"]["pid"],
            "revoker_pid": results["revoker"]["pid"], "parent_pid": os.getpid(), "production_gate": False,
            "same_issued_token_reused_after_revocation": True, "negative_status": 403,
            "negative_code": "PROJECT_SCOPE_FORBIDDEN", "authority_lock_witness": witness})
    finally:
        for name in ("writer", "revoker"):
            (folder / f"{name}-release").touch()
        for process, log in processes:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)
            log.close()
        e.client.delete(f"/api/novels/{e.nid}", headers=e.init_headers)


if __name__ == "__main__":
    assert sys.argv[1] == "--worker"
    _child(sys.argv[2], sys.argv[3])
