from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

try:
    from .v061_acceptance_environment import build_child_environment
except ImportError:
    from v061_acceptance_environment import build_child_environment


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime"
MANIFEST = RUNTIME / "v061-acceptance-environment.json"
PORT = int(os.environ.get("V061_PASS5_PORT", "8011"))
OWNERSHIP = RUNTIME / "v061-process-ownership.json"
EVIDENCE = RUNTIME / "v061-process-ownership-evidence.json"


def wait_for_health(process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"FastAPI exited with code {process.returncode}")
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=1) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.2)
    raise TimeoutError("FastAPI health readiness timed out")


def require_port_available(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            raise RuntimeError(f"port {port} is occupied before FastAPI start") from exc


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    require_port_available(PORT)
    environment = build_child_environment(manifest["environment"])
    environment["V061_RUN_ID"] = str(manifest["run_id"])
    environment["V061_API_PORT"] = str(PORT)
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from app.config import settings;"
                "from app.dependencies import trusted_session_resolver;"
                "print('CHILD_SESSION_JSON_PRESENT='+str(bool(settings.collaboration_dev_sessions_json)));"
                "print('CHILD_RESOLVER_SESSION_COUNT='+str(len(trusted_session_resolver._sessions)))"
            ),
        ],
        cwd=ROOT,
        env=environment,
        check=False,
    )
    if probe.returncode != 0:
        return probe.returncode
    output = (RUNTIME / "v061-pass5-backend.out").open("wb")
    error = (RUNTIME / "v061-pass5-backend.err").open("wb")
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "v061_fastapi_server.py")],
        cwd=ROOT,
        env=environment,
        stdout=output,
        stderr=error,
    )
    server: dict[str, object] | None = None
    try:
        deadline = time.monotonic() + 15
        while not OWNERSHIP.exists() and time.monotonic() < deadline:
            if process.poll() is not None:
                raise RuntimeError(f"FastAPI launcher exited with code {process.returncode}")
            time.sleep(0.1)
        ownership = json.loads(OWNERSHIP.read_text(encoding="utf-8"))
        server = ownership["fastapi"]
        if ownership["run_id"] != manifest["run_id"]:
            raise RuntimeError("ownership run_id does not match session manifest")
        if int(server["parent_pid"]) != process.pid:
            raise RuntimeError("listener parent does not match harness launcher")
        if int(server["selected_port"]) != PORT:
            raise RuntimeError("listener port does not match selected port")
        if "v061_fastapi_server.py" not in server["argv"] or str(PORT) not in server["argv"]:
            raise RuntimeError("listener argv does not match expected FastAPI command")
        if Path(server["cwd"]).resolve() != ROOT:
            raise RuntimeError("listener cwd does not match project root")
        wait_for_health(process)
        if process.poll() is not None:
            raise RuntimeError("FastAPI exited after health readiness")
        print(f"FASTAPI_LAUNCHER_PID={process.pid}", flush=True)
        print(f"FASTAPI_LISTENER_PID={server['listener_pid']}", flush=True)
        print("FASTAPI_OWNERSHIP=DESCENDANT", flush=True)
        print("FASTAPI=READY", flush=True)
        smoke_environment = os.environ.copy()
        smoke_environment["V061_RUN_ID"] = f"pass5-{os.getpid()}"
        smoke_environment["V061_API_BASE_URL"] = f"http://127.0.0.1:{PORT}"
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "v061_trusted_session_smoke.py")],
            cwd=ROOT,
            env=smoke_environment,
            check=False,
        )
        EVIDENCE.write_text(
            json.dumps(
                {
                    "run_id": ownership["run_id"],
                    "launcher_pid": process.pid,
                    "listener_pid": server["listener_pid"],
                    "parent_pid": server["parent_pid"],
                    "selected_port": server["selected_port"],
                    "launch_time": server["launch_time"],
                    "executable": server["executable"],
                    "argv": server["argv"],
                    "cwd": server["cwd"],
                    "ownership": "DESCENDANT",
                    "health": "PASS",
                    "trusted_session_smoke": "PASS" if result.returncode == 0 else "FAIL",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return result.returncode
    finally:
        if os.name == "nt" and server is not None:
            subprocess.run(
                ["taskkill", "/PID", str(server["listener_pid"]), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
        elif process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
        output.close()
        error.close()
        OWNERSHIP.unlink(missing_ok=True)
        print("FASTAPI_CLEANUP=PASS", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
