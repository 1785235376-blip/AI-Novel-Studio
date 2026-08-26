from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import dotenv_values

try:
    from .prepare_acceptance import acceptance_url, ensure_database, ensure_schema, seed
    from .v061_acceptance_environment import build_child_environment, build_manifest, validate
    from .v061_process_ownership import ProcessEvidence, WindowsProcessHandle, classify_owner, identity_matches, inspect_process, process_identity, terminate_if_still_owned
except ImportError:
    from prepare_acceptance import acceptance_url, ensure_database, ensure_schema, seed
    from v061_acceptance_environment import build_child_environment, build_manifest, validate
    from v061_process_ownership import ProcessEvidence, WindowsProcessHandle, classify_owner, identity_matches, inspect_process, process_identity, terminate_if_still_owned


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
STATE = RUNTIME / "v061-stack-state.json"
ENVIRONMENT = RUNTIME / "v061-acceptance-environment.json"
SESSIONS = RUNTIME / "acceptance-sessions.json"
RUN_MANIFEST = RUNTIME / "v061-browser-run.json"
SUPERVISOR_IDENTITY = RUNTIME / "v061-supervisor-identity.json"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def tcp_ready(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def wait_http(url: str, process: subprocess.Popen[bytes], timeout: float, target: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"{target} exited before ready: {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError(f"bounded wait expired for {target}: {timeout}s")


def wait_process_identity(pid: int, *, port: int | None, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        evidence = inspect_process(pid, port=port)
        if evidence is not None:
            return evidence
        time.sleep(0.05)
    return None


def cleanup_targets(state: dict[str, object]) -> list[int]:
    services = state.get("services")
    if not isinstance(services, dict):
        return []
    result: list[int] = []
    for name in ("preview", "fastapi"):
        service = services.get(name)
        if not isinstance(service, dict) or service.get("run_id") != state.get("run_id"):
            continue
        for key in ("listener_pid", "launcher_pid"):
            value = service.get(key)
            if isinstance(value, int) and value > 0 and value not in result:
                result.append(value)
    return result


def verified_cleanup_targets(state: dict[str, object]) -> tuple[list[int], list[dict[str, object]]]:
    run_id = state.get("run_id")
    services = state.get("services")
    if not isinstance(run_id, str) or not isinstance(services, dict):
        return [], [{"reason": "INSUFFICIENT_STATE"}]
    targets: list[int] = []
    rejected: list[dict[str, object]] = []
    expected_roles = {
        "supervisor": {"process": "supervisor"},
        "postgres": {"process": "postgres"},
        "preview": {"listener": "preview", "launcher": "preview"},
        "fastapi": {"listener": "fastapi_listener", "launcher": "fastapi_launcher"},
    }
    for service_name in ("preview", "fastapi", "postgres", "supervisor"):
        service = services.get(service_name)
        if not isinstance(service, dict) or service.get("run_id") != run_id:
            continue
        identities = service.get("identities")
        if not isinstance(identities, dict):
            rejected.append({"service": service_name, "reason": "INSUFFICIENT_IDENTITY"})
            continue
        for role, expected_role in expected_roles[service_name].items():
            recorded = identities.get(role)
            if not isinstance(recorded, dict):
                continue
            pid = recorded.get("pid")
            port = recorded.get("port")
            current = inspect_process(pid, port=port) if isinstance(pid, int) else None
            matched, reason = identity_matches(
                recorded,
                current,
                expected_run_id=run_id,
                expected_role=expected_role,
            )
            if matched and isinstance(pid, int):
                if pid not in targets:
                    targets.append(pid)
            elif current is not None:
                rejected.append({"service": service_name, "role": role, "pid": pid, "reason": reason})
    return targets, rejected


def cleanup_records(state: dict[str, object]) -> tuple[list[tuple[dict[str, object], str]], list[dict[str, object]]]:
    run_id = state.get("run_id")
    services = state.get("services")
    if not isinstance(run_id, str) or not isinstance(services, dict):
        return [], [{"reason": "INSUFFICIENT_STATE"}]
    expected_roles = {
        "preview": (("listener", "preview"), ("launcher", "preview")),
        "fastapi": (("listener", "fastapi_listener"), ("launcher", "fastapi_launcher")),
        "postgres": (("process", "postgres"),),
        "supervisor": (("process", "supervisor"),),
    }
    records: list[tuple[dict[str, object], str]] = []
    rejected: list[dict[str, object]] = []
    seen: set[int] = set()
    for service_name in ("preview", "fastapi", "postgres", "supervisor"):
        service = services.get(service_name)
        if not isinstance(service, dict) or service.get("run_id") != run_id:
            continue
        identities = service.get("identities")
        if not isinstance(identities, dict):
            rejected.append({"service": service_name, "reason": "INSUFFICIENT_IDENTITY"})
            continue
        for key, expected_role in expected_roles[service_name]:
            record = identities.get(key)
            if not isinstance(record, dict):
                continue
            pid = record.get("pid")
            if not isinstance(pid, int) or pid in seen:
                continue
            seen.add(pid)
            records.append((record, expected_role))
    return records, rejected


def update(run_state: dict[str, object], checkpoint: str, **values: object) -> None:
    run_state.update(values)
    run_state["checkpoint"] = checkpoint
    run_state["updated_at"] = now()
    atomic_json(STATE, run_state)
    print(checkpoint, flush=True)


def supervise(run_id: str, api_port: int, preview_port: int) -> int:
    self_handle = WindowsProcessHandle(os.getpid())
    supervisor_evidence = self_handle.evidence_with_known_command(
        parent_pid=os.getppid(),
        argv=(sys.executable, *sys.argv),
        port=None,
    )
    self_handle.close()
    if supervisor_evidence is None:
        raise RuntimeError("Supervisor process identity is unavailable")
    supervisor_identity = process_identity(run_id=run_id, role="supervisor", evidence=supervisor_evidence)
    atomic_json(SUPERVISOR_IDENTITY, supervisor_identity)
    state: dict[str, object] = {
        "run_id": run_id,
        "supervisor_pid": os.getpid(),
        "started_at": now(),
        "checkpoint": "L0_LAUNCHER_STARTED",
        "services": {
            "supervisor": {
                "run_id": run_id,
                "identities": {
                    "process": supervisor_identity
                },
            }
        },
        "ports": {"postgres": 54329, "fastapi": api_port, "preview": preview_port},
    }
    atomic_json(STATE, state)
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    node = Path.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "node" / "bin" / "node.exe"
    pg_ctl = RUNTIME / "postgresql-16.4" / "pgsql" / "bin" / "pg_ctl.exe"
    fastapi: subprocess.Popen[bytes] | None = None
    preview: subprocess.Popen[bytes] | None = None
    try:
        update(state, "L1_POSTGRES_SPAWN_REQUESTED")
        subprocess.run(
            [str(pg_ctl), "start", "-D", str(RUNTIME / "pgdata-main"), "-l", str(RUNTIME / "v061-supervisor-postgres.log"), "-o", "-p 54329"],
            cwd=ROOT,
            timeout=20,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        postgres_pid = int((RUNTIME / "pgdata-main" / "postmaster.pid").read_text().splitlines()[0])
        postgres_handle = WindowsProcessHandle(postgres_pid)
        postgres_argv = tuple((RUNTIME / "pgdata-main" / "postmaster.opts").read_text(encoding="utf-8").strip().replace('"', '').split())
        postgres_evidence = postgres_handle.evidence_with_known_command(parent_pid=0, argv=postgres_argv, port=54329)
        postgres_handle.close()
        if postgres_evidence is None:
            raise RuntimeError("PostgreSQL process identity is unavailable")
        services = state["services"]
        assert isinstance(services, dict)
        services["postgres"] = {
            "run_id": run_id,
            "identities": {
                "process": process_identity(run_id=run_id, role="postgres", evidence=postgres_evidence)
            },
        }
        update(state, "L2_POSTGRES_PID_KNOWN", postgres_pid=postgres_pid)
        deadline = time.monotonic() + 15
        while not tcp_ready(54329) and time.monotonic() < deadline:
            time.sleep(0.2)
        if not tcp_ready(54329):
            raise TimeoutError("bounded wait expired for PostgreSQL listener: 15s")
        update(state, "L3_POSTGRES_LISTENER_READY")

        base = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value is not None}
        url = acceptance_url(str(base.get("DATABASE_URL", "")))
        ensure_database(url)
        ensure_schema(url)
        update(state, "L4_DB_PREFLIGHT_PASS")
        seed(url)
        update(state, "L5_ACCEPTANCE_DB_PREP_PASS")

        os.environ["V061_RUN_ID"] = run_id
        manifest = build_manifest()
        validate(manifest)
        atomic_json(ENVIRONMENT, manifest)
        atomic_json(SESSIONS, {"items": manifest["sessions"]})
        # Preserve the historical array contract consumed by Playwright.
        SESSIONS.write_text(json.dumps(manifest["sessions"], ensure_ascii=False), encoding="utf-8")
        environment = build_child_environment(manifest["environment"])
        environment["V061_RUN_ID"] = run_id
        environment["V061_API_PORT"] = str(api_port)
        update(state, "L6_SESSION_ENV_MANIFEST_CREATED")

        services = state["services"]
        assert isinstance(services, dict)
        services["fastapi"] = {"run_id": run_id, "state": "SPAWNING", "port": api_port, "started_at": now()}
        update(state, "L7_FASTAPI_SPAWN_REQUESTED")
        ownership_path = RUNTIME / "v061-process-ownership.json"
        ownership_path.unlink(missing_ok=True)
        fastapi_out = (RUNTIME / "v061-supervisor-fastapi.out").open("wb")
        fastapi_err = (RUNTIME / "v061-supervisor-fastapi.err").open("wb")
        fastapi_argv = (str(python), str(ROOT / "scripts" / "v061_fastapi_server.py"))
        fastapi = subprocess.Popen(list(fastapi_argv), cwd=ROOT, env=environment, stdout=fastapi_out, stderr=fastapi_err)
        launcher_handle = WindowsProcessHandle(fastapi.pid)
        launcher_evidence = launcher_handle.evidence_with_known_command(parent_pid=os.getpid(), argv=fastapi_argv, port=None)
        launcher_handle.close()
        if launcher_evidence is None:
            raise RuntimeError("FastAPI launcher identity is unavailable")
        services["fastapi"].update({"launcher_pid": fastapi.pid, "state": "LAUNCHED", "identities": {"launcher": process_identity(run_id=run_id, role="fastapi_launcher", evidence=launcher_evidence)}})
        update(state, "L8_FASTAPI_LAUNCHER_PID_KNOWN")
        deadline = time.monotonic() + 15
        while not ownership_path.exists() and time.monotonic() < deadline:
            if fastapi.poll() is not None:
                raise RuntimeError(f"FastAPI exited before ownership manifest: {fastapi.returncode}")
            time.sleep(0.1)
        ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
        if ownership.get("schema_version") != 2 or ownership.get("run_id") != run_id:
            raise RuntimeError("FastAPI ownership manifest run identity mismatch")
        server = ownership["fastapi"]
        if server.get("run_id") != run_id or server.get("role") != "fastapi_listener" or int(server["selected_port"]) != api_port:
            raise RuntimeError("FastAPI listener ownership claim mismatch")
        listener_pid = int(server["listener_pid"])
        listener_handle = WindowsProcessHandle(listener_pid)
        listener_argv = (str(getattr(sys, "_base_executable", sys.executable)), str(ROOT / "scripts" / "v061_fastapi_server.py"))
        listener_evidence = listener_handle.evidence_with_known_command(parent_pid=int(server["parent_pid"]), argv=listener_argv, port=api_port)
        listener_handle.close()
        if listener_evidence is None:
            raise RuntimeError("FastAPI listener identity is unavailable")
        ownership_kind, lineage = classify_owner(
            launcher_pid=fastapi.pid,
            listener=listener_evidence,
            processes={fastapi.pid: launcher_evidence, listener_pid: listener_evidence},
            launch_time=datetime.fromisoformat(str(services["fastapi"]["started_at"])),
            selected_port=api_port,
            expected_executable=listener_evidence.executable or "",
            expected_entrypoint="v061_fastapi_server.py",
        )
        if ownership_kind not in {"DIRECT", "DESCENDANT"}:
            raise RuntimeError(f"FastAPI listener ownership rejected: {ownership_kind}")
        services["fastapi"]["identities"]["listener"] = process_identity(run_id=run_id, role="fastapi_listener", evidence=listener_evidence)
        services["fastapi"].update({"listener_pid": listener_pid, "parent_pid": int(server["parent_pid"]), "state": "OWNED", "ownership": ownership_kind, "lineage": list(lineage)})
        update(state, "L9_FASTAPI_LISTENER_PID_KNOWN")
        update(state, "L10_FASTAPI_OWNERSHIP_MANIFEST_WRITTEN")
        wait_http(f"http://127.0.0.1:{api_port}/health", fastapi, 15, "FastAPI health")
        update(state, "L11_FASTAPI_HEALTH_PASS")
        smoke_env = os.environ.copy()
        smoke_env["V061_RUN_ID"] = run_id
        smoke_env["V061_API_BASE_URL"] = f"http://127.0.0.1:{api_port}"
        subprocess.run([str(python), str(ROOT / "scripts" / "v061_trusted_session_smoke.py")], cwd=ROOT, env=smoke_env, timeout=20, check=True)
        services["fastapi"]["state"] = "READY"
        update(state, "L12_TRUSTED_SESSION_SMOKE_PASS")

        services["preview"] = {"run_id": run_id, "state": "SPAWNING", "port": preview_port, "started_at": now()}
        update(state, "L13_PREVIEW_SPAWN_REQUESTED")
        preview_env = os.environ.copy()
        preview_env["V061_API_URL"] = f"http://127.0.0.1:{api_port}"
        preview_out = (RUNTIME / "v061-supervisor-preview.out").open("wb")
        preview_err = (RUNTIME / "v061-supervisor-preview.err").open("wb")
        preview_argv = (str(node), "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port", str(preview_port), "--strictPort")
        preview = subprocess.Popen(list(preview_argv), cwd=ROOT / "frontend", env=preview_env, stdout=preview_out, stderr=preview_err)
        preview_handle = WindowsProcessHandle(preview.pid)
        preview_evidence = preview_handle.evidence_with_known_command(parent_pid=os.getpid(), argv=preview_argv, port=preview_port)
        preview_handle.close()
        if preview_evidence is None:
            raise RuntimeError("Preview process identity is unavailable")
        preview_identity = process_identity(run_id=run_id, role="preview", evidence=preview_evidence)
        services["preview"].update({"launcher_pid": preview.pid, "listener_pid": preview.pid, "state": "OWNED", "ownership": "DIRECT", "identities": {"launcher": preview_identity, "listener": preview_identity}})
        update(state, "L14_PREVIEW_OWNERSHIP_MANIFEST_WRITTEN")
        wait_http(f"http://127.0.0.1:{preview_port}/", preview, 15, "Preview HTTP")
        services["preview"]["state"] = "READY"
        update(state, "L15_PREVIEW_HTTP_PASS", state="READY", api_url=f"http://127.0.0.1:{api_port}", preview_url=f"http://127.0.0.1:{preview_port}")
        while True:
            time.sleep(1)
    except Exception as exc:
        update(state, "FAILED", state="FAILED", error=f"{type(exc).__name__}: {exc}")
        return 1


def start() -> int:
    run_id = "v061-" + uuid.uuid4().hex
    api_port, preview_port = free_port(), free_port()
    while preview_port == api_port:
        preview_port = free_port()
    flags = 0
    if os.name == "nt":
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    log = (RUNTIME / "v061-supervisor.log").open("ab")
    SUPERVISOR_IDENTITY.unlink(missing_ok=True)
    supervisor_argv = (sys.executable, __file__, "supervise", "--run-id", run_id, "--api-port", str(api_port), "--preview-port", str(preview_port))
    supervisor = subprocess.Popen(list(supervisor_argv), cwd=ROOT, stdout=log, stderr=log, creationflags=flags)
    supervisor_handle = WindowsProcessHandle(supervisor.pid)
    supervisor_evidence = supervisor_handle.evidence_with_known_command(parent_pid=os.getpid(), argv=supervisor_argv, port=None)
    supervisor_handle.close()
    if supervisor_evidence is None:
        raise RuntimeError("Supervisor process identity is unavailable")
    atomic_json(SUPERVISOR_IDENTITY, process_identity(run_id=run_id, role="supervisor", evidence=supervisor_evidence))
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if STATE.exists():
            state = json.loads(STATE.read_text(encoding="utf-8"))
            if state.get("run_id") == run_id and state.get("state") == "READY":
                print(json.dumps(state, ensure_ascii=True))
                return 0
            if state.get("run_id") == run_id and state.get("state") == "FAILED":
                print(json.dumps(state, ensure_ascii=True), file=sys.stderr)
                return 1
        if supervisor.poll() is not None:
            return supervisor.returncode or 1
        time.sleep(0.2)
    raise TimeoutError("supervisor did not reach READY within 60s")


def stop() -> int:
    cleanup_failed = False
    if STATE.exists():
        state = json.loads(STATE.read_text(encoding="utf-8"))
        run_id = state.get("run_id")
        records, rejected = cleanup_records(state)
        if isinstance(run_id, str):
            for record, expected_role in records:
                def recorded_command_inspector(pid: int, *, port: int | None = None):
                    argv = record.get("argv")
                    if not isinstance(argv, list):
                        return None
                    return ProcessEvidence(
                        pid,
                        int(record.get("parent_pid") or 0),
                        None,
                        None,
                        tuple(str(value) for value in argv),
                        port,
                    )
                result = terminate_if_still_owned(record, expected_run_id=run_id, expected_role=expected_role, inspector=recorded_command_inspector)
                print(json.dumps({"role": expected_role, "pid": result.pid, "termination": result.status, "reason": result.reason}), flush=True)
                if result.status not in {"TERMINATED", "ALREADY_EXITED"}:
                    cleanup_failed = True
        else:
            cleanup_failed = True
        if rejected:
            print(json.dumps({"cleanup_rejected": rejected}, ensure_ascii=False), file=sys.stderr)
            cleanup_failed = True
    if cleanup_failed:
        return 1
    for path in (ENVIRONMENT, SESSIONS, RUN_MANIFEST, RUNTIME / "v061-process-ownership.json", SUPERVISOR_IDENTITY):
        path.unlink(missing_ok=True)
    STATE.unlink(missing_ok=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("start")
    sub.add_parser("stop")
    supervise_parser = sub.add_parser("supervise")
    supervise_parser.add_argument("--run-id", required=True)
    supervise_parser.add_argument("--api-port", required=True, type=int)
    supervise_parser.add_argument("--preview-port", required=True, type=int)
    args = parser.parse_args()
    if args.command == "start":
        return start()
    if args.command == "stop":
        return stop()
    return supervise(args.run_id, args.api_port, args.preview_port)


if __name__ == "__main__":
    raise SystemExit(main())
