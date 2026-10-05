"""Native Windows smoke of packaged Python/PostgreSQL, using only fresh synthetic data.

No DesktopHost/WebView2 window is started. Evidence does not imply interactive,
IME, installer, code-signing, real-provider, or user acceptance passed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def native_environment(root: Path) -> dict[str, str]:
    windows = os.environ.get("SystemRoot")
    if not windows:
        raise RuntimeError("Windows SystemRoot is required")
    temp = root / "temp"
    temp.mkdir()
    # Deliberately exclude developer PATH, PG settings, credentials and Python
    # search paths. Only application-local and actual Windows system DLLs may
    # satisfy runtime dependencies. No existing user config is consumed.
    return {
        "SystemRoot": windows, "WINDIR": windows,
        "PATH": str(Path(windows) / "System32"),
        "TEMP": str(temp), "TMP": str(temp),
        "USERPROFILE": str(root / "profile"), "APPDATA": str(root / "appdata"),
        "LOCALAPPDATA": str(root / "localappdata"), "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "PGCLIENTENCODING": "UTF8",
        "MOCK_PROVIDER": "true", "ENABLE_CLOUD": "false",
        "CREDENTIAL_VAULT_BACKEND": "memory", "CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK": "true",
        "NOVEL_DATA_PATH": str(root / "novel-data"), "STORAGE_BACKEND": "file",
    }


def progress(stage: str, **details: object) -> None:
    """Print only stage names, executable basenames and synthetic counters."""
    print("NATIVE_BASE_PROGRESS " + json.dumps({"stage": stage, **details}, sort_keys=True), flush=True)


def log_tail(path: Path, limit: int = 5000) -> str:
    with path.open("rb") as stream:
        stream.seek(max(0, path.stat().st_size - limit))
        return stream.read(limit).decode("utf-8", errors="replace")


def terminate_owned_command(process, environment: dict[str, str], stdout, stderr) -> dict:
    """Bound cleanup to this invocation's still-live PID, never executable name.

    Windows taskkill reports on a PID tree; its success is recorded as reported
    success rather than independent proof that every descendant was enumerated.
    The owned cluster still has its separate data-directory shutdown in finally.
    """
    evidence: dict = {"pid": process.pid, "tree_cleanup": "NOT_VERIFIED"}
    if process.poll() is not None:
        evidence["parent_exited"] = True
        return evidence
    if sys.platform == "win32":
        taskkill = Path(environment["SystemRoot"]) / "System32/taskkill.exe"
        try:
            terminated = subprocess.run(
                [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                env=environment, stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            evidence["taskkill_exit_code"] = terminated.returncode
            if terminated.returncode == 0:
                evidence["tree_cleanup"] = "TASKKILL_REPORTED_SUCCESS"
        except (OSError, subprocess.TimeoutExpired) as error:
            evidence["taskkill_error"] = type(error).__name__
    # A non-Windows call is only used by isolated tests. Preserve the explicit
    # NOT_VERIFIED tree status rather than claiming POSIX descendant cleanup.
    if process.poll() is None:
        process.kill()  # Popen's handle, not a guessed or globally selected PID
    try:
        process.wait(timeout=5)
        evidence["parent_exited"] = True
    except subprocess.TimeoutExpired:
        evidence["parent_exited"] = False
    return evidence


def run_native_command(arguments: list[str | Path], *, root: Path,
                       environment: dict[str, str], commands: list[dict], timeout: int = 60) -> str:
    arguments = [str(value) for value in arguments]
    executable = Path(arguments[0]).name
    logs = root / "command-logs"
    logs.mkdir(exist_ok=True)
    index = len(commands) + 1
    stdout_path = logs / f"{index:03d}.stdout.log"
    stderr_path = logs / f"{index:03d}.stderr.log"
    entry: dict = {"executable": executable, "arguments": arguments[1:], "status": "RUNNING",
                   "stdout_file": stdout_path.relative_to(root).as_posix(),
                   "stderr_file": stderr_path.relative_to(root).as_posix()}
    commands.append(entry)
    progress("command_start", executable=executable, number=index)
    began = time.monotonic()
    try:
        # Regular files avoid inherited PIPE handles held by Windows CMD /
        # postgres descendants. Waiting for the direct process is sufficient;
        # reading a finite file never waits for descendant pipe EOF.
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            process = subprocess.Popen(
                arguments, cwd=root, env=environment, stdin=subprocess.DEVNULL,
                stdout=stdout, stderr=stderr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                entry.update({"status": "TIMEOUT", "timeout_seconds": timeout, "exit_code": None})
                progress("command_timeout", executable=executable, number=index, timeout_seconds=timeout)
                entry["timeout_cleanup"] = terminate_owned_command(process, environment, stdout, stderr)
                raise
            entry.update({"status": "PASS" if code == 0 else "FAILED", "exit_code": code})
            progress("command_complete", executable=executable, number=index, exit_code=code)
        if code:
            raise RuntimeError(f"Native command failed: {executable}: {log_tail(stderr_path)[-1500:]}")
        return log_tail(stdout_path, limit=1_000_000).strip()
    except BaseException:
        if entry["status"] == "RUNNING":
            entry["status"] = "FAILED_TO_START"
            progress("command_failed", executable=executable, number=index)
        raise
    finally:
        entry["elapsed_seconds"] = round(time.monotonic() - began, 3)
        entry["stdout"] = log_tail(stdout_path) if stdout_path.exists() else ""
        entry["stderr"] = log_tail(stderr_path) if stderr_path.exists() else ""


def verify(base: Path, root: Path) -> dict:
    if sys.platform != "win32":
        raise RuntimeError("Native base verification requires Windows; it is not a cross-platform mock")
    if root.exists():
        raise ValueError("Native smoke work root must be fresh")
    if not root.is_absolute() or not base.is_absolute():
        raise ValueError("Application and smoke paths must be absolute")
    if root == base or root.is_relative_to(base) or base.is_relative_to(root):
        raise ValueError("Native smoke and application must be separate trees")
    from prepare_windows_base import reject_links
    reject_links(root)
    reject_links(base)
    root.mkdir(parents=True)
    environment = native_environment(root)
    provenance = json.loads((base / "base-input-provenance.json").read_text(encoding="utf-8"))
    progress("inventory_start", files=len(provenance["files"]))
    for item in provenance["files"]:
        path = base / item["path"]
        reject_links(path)
        if not path.resolve().is_relative_to(base.resolve()):
            raise ValueError("Base inventory escapes the application root")
        if not path.is_file() or path.stat().st_size != item["size"] or digest(path) != item["sha256"]:
            raise ValueError(f"Base inventory changed: {item['path']}")
    progress("inventory_complete", files=len(provenance["files"]))
    commands: list[dict] = []

    def run(arguments: list[str | Path], timeout: int = 60) -> str:
        return run_native_command(arguments, root=root, environment=environment, commands=commands, timeout=timeout)

    result = {"kind": "native-windows-base-smoke", "status": "RUNNING", "public_release": False,
              "interactive_desktop": "NOT_RUN", "user_acceptance": "NOT_RUN", "commands": commands}
    pg = base / "PostgreSQL/bin"
    data = root / "postgres-data"
    started = False
    try:
        python = base / "Runtime/Python/python.exe"
        expected = {item["name"]: item["version"] for item in provenance["inputs"]["wheels"]}
        probe = (
            "import json,sys,importlib.metadata as m; "
            "import fastapi,uvicorn,psycopg,sqlalchemy,httpx,pydantic_settings,reportlab,PIL; "
            "from psycopg import pq; "
            "from reportlab.pdfgen.canvas import Canvas; "
            f"names={list(expected)!r}; "
            "print(json.dumps({'python':list(sys.version_info[:3]),'isolated':sys.flags.isolated,"
            "'psycopg_impl':pq.__impl__,'packages':{n:m.version(n) for n in names}}))"
        )
        python_result = json.loads(run([python, "-I", "-c", probe]))
        if python_result["python"] != [3, 12, 9] or python_result["packages"] != expected or python_result["psycopg_impl"] != "binary" or not python_result["isolated"]:
            raise ValueError("Embedded Python version/dependency/isolation probe failed")
        result["python"] = python_result
        system = Path(environment["SystemRoot"]) / "System32"
        result["vc_runtime"] = {name: {"location": str((pg / name) if (pg / name).exists() else system / name),
                                     "sha256": digest((pg / name) if (pg / name).exists() else system / name)}
                                for name in ("msvcp140.dll", "vcruntime140.dll")}
        result["postgres_version"] = run([pg / "postgres.exe", "--version"])
        if " 16.15" not in result["postgres_version"]:
            raise ValueError("Unexpected PostgreSQL version")
        run([pg / "initdb.exe", "-D", data, "-U", "novel_ci", "--encoding=UTF8", "--locale=C", "--auth=trust"])
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        # pg_ctl owns exactly this freshly initialized synthetic directory.
        run([pg / "pg_ctl.exe", "-D", data, "-l", root / "postgres.log", "-w", "-t", "60",
             "-o", f"-h 127.0.0.1 -p {port}", "start"], timeout=75)
        started = True
        connection = ["-h", "127.0.0.1", "-p", str(port), "-U", "novel_ci"]
        sql = (
            "CREATE EXTENSION pgcrypto; CREATE TABLE r2_package_smoke (id integer PRIMARY KEY, body text); "
            "INSERT INTO r2_package_smoke VALUES (1, convert_from(decode('e4b8ade69687e9aa8ce8af81','hex'),'UTF8')); "
            "SELECT encode(digest(body, 'sha256'),'hex') FROM r2_package_smoke;"
        )
        run([pg / "psql.exe", *connection, "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql])
        archive = root / "synthetic.backup"
        run([pg / "pg_dump.exe", *connection, "-d", "postgres", "--format=custom", "--no-owner", "--file", archive])
        run([pg / "createdb.exe", *connection, "r2_restore"])
        run([pg / "pg_restore.exe", *connection, "-d", "r2_restore", "--exit-on-error", "--no-owner", archive])
        text = run([pg / "psql.exe", *connection, "-d", "r2_restore", "-v", "ON_ERROR_STOP=1", "-tAc", "SELECT body FROM r2_package_smoke WHERE id=1"])
        if text != "中文验证":
            raise ValueError("PostgreSQL UTF-8 dump/restore round trip failed")
        result.update({"pgcrypto": "PASS", "custom_dump_restore": "PASS", "utf8_roundtrip": "PASS"})
        if (base / "Backend/app/main.py").is_file():
            environment["PROJECT_ROOT"] = str(base / "Backend")
            run([python, "-I", "-c", "import app.main; print('PACKAGED_APP_IMPORT_PASS')"])
            result["packaged_app_import"] = "PASS"
        result["status"] = "PASS"
    except BaseException as error:
        result["status"] = "FAILED"
        result["error"] = str(error)
        raise
    finally:
        try:
            if started or (data / "postmaster.pid").exists():
                run([pg / "pg_ctl.exe", "-D", data, "-w", "-t", "30", "-m", "fast", "stop"], timeout=40)
        except BaseException as shutdown_error:
            result["status"] = "FAILED"
            result["shutdown_error"] = str(shutdown_error)
            raise
        finally:
            (root / "native-base-smoke.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.base.absolute(), args.work_root.absolute())
    print(json.dumps({key: value for key, value in result.items() if key != "commands"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
