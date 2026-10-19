#!/usr/bin/env python3
"""PoemSeed Studio V2 - Local minimum CI (LOCAL-01 .. LOCAL-05).

This runner is a *test-only* developer tool. It does not install dependencies,
does not download models/browsers/resources, does not start or migrate user
projects, and it is NOT a one-click installer / launcher / deployment script.

Each step is an explicit developer-invoked command. --all merely executes the
same five documented steps in order and keeps one receipt per step.

    python scripts/run_local_ci.py --step LOCAL-01
    python scripts/run_local_ci.py --step LOCAL-02
    python scripts/run_local_ci.py --step LOCAL-03
    python scripts/run_local_ci.py --step LOCAL-04
    python scripts/run_local_ci.py --step LOCAL-05
    python scripts/run_local_ci.py --all --label 20261019-a

Result vocabulary (independent axes, never mixed with product release status):

    PASS / FAIL / PARTIAL / BLOCKED_ENVIRONMENT / NOT_RUN

Evidence is written below docs/v2/engineering/evidence/local-ci/<run-id>/ and
every receipt is bound to the current Git HEAD. Isolated runtime data lives
below .runtime/local-ci/<run-id>/ and is removed by LOCAL-05.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
# Reuse the single isolated-profile contract already owned by run_v2_checks.py.
from run_v2_checks import isolated_environment  # noqa: E402

EVIDENCE_ROOT = ROOT / "docs" / "v2" / "engineering" / "evidence" / "local-ci"
RUNTIME_ROOT = ROOT / ".runtime" / "local-ci"
SCHEMA = "poemseed-local-ci/1"

PASS = "PASS"
FAIL = "FAIL"
PARTIAL = "PARTIAL"
BLOCKED = "BLOCKED_ENVIRONMENT"
NOT_RUN = "NOT_RUN"

STEPS = ("LOCAL-01", "LOCAL-02", "LOCAL-03", "LOCAL-04", "LOCAL-05")

# LOCAL-02 is a representative *fast* correctness slice, not the full suite.
# The complete File suite and the PostgreSQL suite stay independent layers.
LOCAL_02_TARGETS = (
    "tests/test_v2_creative_project_lifecycle.py",
    "tests/test_structured_record_cas.py",
    "tests/test_surface_pending_canon_review.py",
    "tests/test_shared_project_route_authority.py",
)
LOCAL_02_SCOPE_NOTE = (
    "Focused correctness slice (not a full regression): project lifecycle, CAS, "
    "pending-canon review promotion fence, shared route authority. The complete "
    "File/PostgreSQL suites remain independent acceptance layers."
)
LOCAL_04_GREP = "real File V2 authoring|real HTTP File V2 lifecycle"
# Ports owned by frontend/playwright.v2-live.config.ts (two server pairs).
WEB_SERVER_PORTS = (8017, 8018, 5177, 5178)

SECRET_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET")
SECRET_KEYS = {
    "DATABASE_URL",
    "TEST_POSTGRES_DATABASE_URL",
    "E2E_DATABASE_URL",
    "COLLABORATION_DEV_SESSIONS_JSON",
    "PACKAGED_CONTROL_PIPE",
}
CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def tool_version(args: list[str]) -> str | None:
    try:
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60, cwd=ROOT)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or "").strip() or (result.stderr or "").strip()
    return text.splitlines()[0] if text else None


def size_tree(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def port_open(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def wait_port_closed(port: int, seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not port_open(port):
            return True
        time.sleep(0.2)
    return not port_open(port)


def http_json(url: str, timeout: float = 3.0) -> tuple[int, object]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read().decode("utf-8", errors="replace")
        return int(response.status), json.loads(payload)


def tail(path: Path, lines: int = 20) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    return "\n".join(text[-lines:])


def stop_process(process) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def run_command(args: list[str], cwd: Path, env: dict[str, str], log_path: Path,
                timeout_seconds: int) -> dict:
    """Run one step command, capturing combined output into log_path."""
    started = time.monotonic()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8", errors="replace") as log:
        log.write("$ " + " ".join(args) + "\n\n")
        log.flush()
        try:
            completed = subprocess.run(args, cwd=cwd, env=env, stdout=log,
                                       stderr=subprocess.STDOUT, timeout=timeout_seconds,
                                       creationflags=CREATE_NO_WINDOW)
            exit_code = completed.returncode
            timed_out = False
        except subprocess.TimeoutExpired:
            exit_code = None
            timed_out = True
    return {
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_s": round(time.monotonic() - started, 1),
        "log": rel(log_path),
    }


def parse_junit(path: Path) -> dict:
    if not path.exists():
        return {"tests": None, "failures": None, "errors": None, "skipped": None,
                "junit_missing": True}
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        return {"tests": None, "failures": None, "errors": None, "skipped": None,
                "junit_unreadable": str(exc)}
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    total = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    if not suites:
        return {**total, "junit_empty": True}
    for suite in suites:
        for key in total:
            total[key] += int(suite.get(key, 0) or 0)
    return total


def resolve_pnpm() -> str | None:
    pnpm = shutil.which("pnpm")
    if pnpm:
        return pnpm
    for name in ("pnpm.cmd", "pnpm.exe"):
        candidate = shutil.which(name)
        if candidate:
            return candidate
    return None


def pnpm_version() -> str | None:
    pnpm = resolve_pnpm()
    if pnpm is None:
        return None
    try:
        result = subprocess.run([pnpm, "--version"], cwd=ROOT / "frontend",
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError):
        return None
    text = (result.stdout or "").strip()
    return text.splitlines()[0] if text else None


def detect_browser_executable() -> str | None:
    override = os.environ.get("LOCAL_CI_BROWSER_EXECUTABLE", "").strip()
    if override and Path(override).exists():
        return override
    candidates_by_platform = {
        "win32": (
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ),
        "darwin": (
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        ),
    }
    for candidate in candidates_by_platform.get(sys.platform, ()):
        if Path(candidate).exists():
            return candidate
    for candidate in ("microsoft-edge", "google-chrome", "chromium", "chromium-browser"):
        found = shutil.which(candidate)
        if found:
            return found
    return None


def playwright_chromium_present(frontend: Path) -> bool:
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright",
        Path(os.environ.get("HOME", "")) / ".cache" / "ms-playwright",
    ]
    return any(root.exists() and any(root.glob("chromium-*")) for root in roots)


def _process_table() -> dict[int, tuple[int, str]]:
    """Return {pid: (parent_pid, command_line)} for the current host."""
    if os.name == "nt":
        script = ("Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | "
                  "Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress")
        try:
            result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", timeout=120)
            payload = json.loads(result.stdout or "null")
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return {}
        rows = payload if isinstance(payload, list) else [payload] if payload else []
        table: dict[int, tuple[int, str]] = {}
        for row in rows:
            try:
                table[int(row["ProcessId"])] = (int(row.get("ParentProcessId") or 0),
                                                str(row.get("CommandLine") or ""))
            except (KeyError, TypeError, ValueError):
                continue
        return table
    try:
        result = subprocess.run(["ps", "-eo", "pid,ppid,args"], capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=60)
    except (OSError, subprocess.SubprocessError):
        return {}
    table = {}
    for line in result.stdout.splitlines()[1:]:
        parts = line.strip().split(None, 2)
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = (int(parts[1]), parts[2])
    return table


def owned_processes(run_id: str) -> list[str]:
    """Return leaked command lines owned by this run.

    The runner itself, its ancestors and its own short-lived probe helpers
    naturally contain the run id in their command lines; they are not leaks.
    """
    table = _process_table()
    if not table:
        return []
    excluded: set[int] = set()
    pid = os.getpid()
    while pid and pid not in excluded and pid in table:
        excluded.add(pid)
        pid = table[pid][0]
    changed = True
    while changed:
        changed = False
        for candidate, (parent, _command) in table.items():
            if candidate not in excluded and parent in excluded:
                excluded.add(candidate)
                changed = True
    return [f"{candidate} {command}" for candidate, (_parent, command) in sorted(table.items())
            if candidate not in excluded and run_id in command and command.strip()]


# --------------------------------------------------------------------------- #
# runner
# --------------------------------------------------------------------------- #
class LocalCi:
    def __init__(self, label: str) -> None:
        self.run_id = label or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.run_id):
            raise SystemExit("--label must match [A-Za-z0-9._-]+")
        self.evidence = EVIDENCE_ROOT / self.run_id
        self.runtime = RUNTIME_ROOT / self.run_id
        self.evidence.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.receipt = self.evidence / "LOCAL_CI_RESULTS.json"

    # -- receipts ---------------------------------------------------------- #
    def host(self) -> dict:
        return {
            "os": platform.platform(),
            "windows": os.name == "nt",
            "python": sys.version.split()[0],
            "python_executable": sys.executable,
            "node": tool_version(["node", "--version"]),
            "pnpm": pnpm_version(),
            "git_head": git("rev-parse", "HEAD"),
            "git_branch": tool_version(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
            "project_root": str(ROOT),
        }

    def load(self) -> dict:
        if self.receipt.exists():
            return json.loads(self.receipt.read_text(encoding="utf-8"))
        return {
            "schema": SCHEMA,
            "run_id": self.run_id,
            "head": git("rev-parse", "HEAD"),
            "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
            "started_utc": utc_now(),
            "finished_utc": None,
            "host": self.host(),
            "steps": [],
            "overall_status": NOT_RUN,
        }

    def save(self, document: dict) -> None:
        statuses = [step["status"] for step in document["steps"]]
        if any(status == FAIL for status in statuses):
            document["overall_status"] = FAIL
        elif any(status in (BLOCKED, PARTIAL) for status in statuses):
            document["overall_status"] = PARTIAL
        elif statuses and all(status == PASS for status in statuses):
            document["overall_status"] = PASS
        else:
            document["overall_status"] = NOT_RUN
        document["finished_utc"] = utc_now()
        self.receipt.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n",
                                encoding="utf-8")

    def record(self, step: str, status: str, started: str, started_monotonic: float,
               **fields) -> None:
        duration = round(time.monotonic() - started_monotonic, 1)
        document = self.load()
        entry = {"step": step, "status": status, "started_utc": started,
                 "finished_utc": utc_now(), "duration_s": duration, **fields}
        document["steps"] = [s for s in document["steps"] if s["step"] != step] + [entry]
        document["steps"].sort(key=lambda s: STEPS.index(s["step"]))
        self.save(document)
        print(f"[{step}] {status} ({duration}s)")

    # -- environment ------------------------------------------------------- #
    def sealed_env(self, step: str) -> dict:
        env = {k: v for k, v in os.environ.items()
               if not (k.endswith(SECRET_SUFFIXES) or k in SECRET_KEYS)}
        profile = self.runtime / step
        env.update(isolated_environment(ROOT, profile))
        directories = {
            "TMP": profile / "tmp",
            "TEMP": profile / "tmp",
            "TMPDIR": profile / "tmp",
            "HOME": profile / "home",
            "USERPROFILE": profile / "home",
            "XDG_STATE_HOME": profile / "state",
        }
        for variable, directory in directories.items():
            directory.mkdir(parents=True, exist_ok=True)
            env[variable] = str(directory)
        env.update({
            "PYTHONIOENCODING": "utf-8",
            "ENABLE_COLLABORATION_RUNTIME": "false",
            "ENABLE_PACKAGED_RUNTIME": "false",
        })
        return env

    # -- LOCAL-01: real backend boot, health HTTP, clean shutdown ---------- #
    def step_local_01(self) -> str:
        step, started, clock = "LOCAL-01", utc_now(), time.monotonic()
        env = self.sealed_env(step)
        port = free_port()
        log = self.evidence / f"{step}-backend.log"
        command = [sys.executable, "-m", "uvicorn", "app.main:app",
                   "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"]
        release_version = json.loads((ROOT / "release" / "version.json").read_text(encoding="utf-8"))["version"]
        health = None
        api_health_status = None
        process = None
        boot_error = None
        try:
            with open(log, "w", encoding="utf-8", errors="replace") as stream:
                stream.write("$ " + " ".join(command) + "\n\n")
                stream.flush()
                process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stream,
                                           stderr=subprocess.STDOUT, creationflags=CREATE_NO_WINDOW)
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    boot_error = f"backend exited early with code {process.returncode}"
                    break
                try:
                    status, body = http_json(f"http://127.0.0.1:{port}/health")
                    if status == 200:
                        health = (status, body)
                        break
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
                    pass
                time.sleep(0.5)
            if health is None and boot_error is None:
                boot_error = "backend /health did not answer 200 within 120s"
            if health is not None:
                try:
                    api_health_status = http_json(f"http://127.0.0.1:{port}/api/health")[0]
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
                    api_health_status = None
        finally:
            alive_before_stop = process is not None and process.poll() is None
            stop_process(process)
            process_exited = process is not None and process.poll() is not None
            port_released = wait_port_closed(port, seconds=20)

        body = health[1] if health else None
        checks = {
            "command": " ".join(command),
            "port": port,
            "boot_error": boot_error,
            "health_http_status": health[0] if health else None,
            "health_body": body,
            "health_status_ok": bool(isinstance(body, dict) and body.get("status") == "ok"),
            "release_version_matches": bool(isinstance(body, dict) and body.get("version") == release_version),
            "api_health_http_status": api_health_status,
            "process_was_alive_before_stop": alive_before_stop,
            "process_exited": process_exited,
            "port_released": port_released,
        }
        healthy = all([checks["health_http_status"] == 200, checks["health_status_ok"],
                       checks["release_version_matches"], checks["process_exited"],
                       checks["port_released"]])
        status = PASS if healthy else FAIL
        self.record(step, status, started, clock, checks=checks, log=rel(log),
                    notes=["Real uvicorn process, isolated profile, no model/cloud; "
                           "/health is the authoritative route defined in app/main.py."])
        return status

    # -- LOCAL-02: representative correctness slice ------------------------ #
    def step_local_02(self) -> str:
        step, started, clock = "LOCAL-02", utc_now(), time.monotonic()
        env = self.sealed_env(step)
        junit = self.evidence / f"{step}-junit.xml"
        log = self.evidence / f"{step}-pytest.log"
        basetemp = self.runtime / step / "pytest"
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
                   f"--basetemp={basetemp}", f"--junitxml={junit}", "--durations=5",
                   *LOCAL_02_TARGETS]
        result = run_command(command, ROOT, env, log, timeout_seconds=1200)
        counts = parse_junit(junit)
        executions_ok = all([result["exit_code"] == 0, not result["timed_out"],
                             bool(counts.get("tests")), counts.get("failures") == 0,
                             counts.get("errors") == 0])
        checks = {
            "command": " ".join(command),
            "exit_code": result["exit_code"],
            "timed_out": result["timed_out"],
            "junit": rel(junit),
            "counts": counts,
            "scope_note": LOCAL_02_SCOPE_NOTE,
            "tail": tail(log, 12),
        }
        status = PASS if executions_ok else FAIL
        self.record(step, status, started, clock, checks=checks, log=rel(log))
        return status

    # -- LOCAL-03: frontend typecheck/build, vitest, design tokens ---------- #
    def step_local_03(self) -> str:
        step, started, clock = "LOCAL-03", utc_now(), time.monotonic()
        frontend = ROOT / "frontend"
        if not (frontend / "node_modules").exists():
            self.record(step, BLOCKED, started, clock, checks={
                "reason": "frontend/node_modules missing; prepare dependencies first",
                "command": "cd frontend; pnpm install --frozen-lockfile",
            })
            return BLOCKED
        pnpm = resolve_pnpm()
        if pnpm is None:
            self.record(step, BLOCKED, started, clock,
                        checks={"reason": "pnpm executable not found on PATH"})
            return BLOCKED
        env = self.sealed_env(step)
        commands = (
            ("vitest", [pnpm, "run", "test"]),
            ("build", [pnpm, "run", "build"]),
            ("design-tokens", [pnpm, "run", "lint"]),
        )
        results = {}
        for name, command in commands:
            log = self.evidence / f"{step}-{name}.log"
            results[name] = run_command(command, frontend, env, log, timeout_seconds=1200)
            results[name]["log"] = rel(log)
        exit_ok = all(item["exit_code"] == 0 and not item["timed_out"] for item in results.values())
        vitest_log = (self.evidence / f"{step}-vitest.log").read_text(encoding="utf-8", errors="replace")
        match = re.search(r"Tests\s+(\d+) passed", vitest_log)
        tests_passed = int(match.group(1)) if match else None
        checks = {
            "pnpm": pnpm,
            "pnpm_version": pnpm_version(),
            "commands": results,
            "vitest_passed": tests_passed,
            "scope_note": "Frontend gate: full Vitest run, real tsc/vite build, design-token lint.",
        }
        status = PASS if exit_ok and tests_passed else FAIL
        self.record(step, status, started, clock, checks=checks,
                    log=rel(self.evidence / f"{step}-vitest.log"))
        return status

    # -- LOCAL-04: real backend + Vite + browser save/reload journey -------- #
    def step_local_04(self) -> str:
        step, started, clock = "LOCAL-04", utc_now(), time.monotonic()
        frontend = ROOT / "frontend"
        if not (frontend / "node_modules").exists():
            self.record(step, BLOCKED, started, clock, checks={
                "reason": "frontend/node_modules missing; prepare dependencies first"})
            return BLOCKED
        pnpm = resolve_pnpm()
        if pnpm is None:
            self.record(step, BLOCKED, started, clock,
                        checks={"reason": "pnpm executable not found on PATH"})
            return BLOCKED
        browser = detect_browser_executable()
        chromium = playwright_chromium_present(frontend)
        if browser is None and not chromium:
            self.record(step, BLOCKED, started, clock, checks={
                "reason": "no system Edge/Chrome and no downloaded Playwright Chromium; "
                          "browser resources are never auto-downloaded",
                "hint": "set LOCAL_CI_BROWSER_EXECUTABLE or install a browser for the user"})
            return BLOCKED

        env = self.sealed_env(step)
        env.update({
            "V2_PYTHON": sys.executable,
            "CI_RECEIPTS": str(self.evidence),
            "V2_LIVE_RUN_ID": self.run_id,
        })
        if browser:
            env["PLAYWRIGHT_CHROMIUM_EXECUTABLE"] = browser
        log = self.evidence / f"{step}-playwright.log"
        command = [pnpm, "exec", "playwright", "test",
                   "--config", "playwright.v2-live.config.ts",
                   "--project", "v2-live-chromium",
                   "--grep", LOCAL_04_GREP]
        result = run_command(command, frontend, env, log, timeout_seconds=1500)
        junit = parse_junit(self.evidence / "junit.xml")
        executed = all([result["exit_code"] == 0, not result["timed_out"],
                        bool(junit.get("tests")), junit.get("failures") == 0,
                        junit.get("errors") == 0])
        checks = {
            "command": " ".join(command),
            "browser_executable": browser,
            "web_server_ports": sorted(WEB_SERVER_PORTS),
            "playwright_chromium_present": chromium,
            "exit_code": result["exit_code"],
            "timed_out": result["timed_out"],
            "junit": junit,
            "scope_note": "Real uvicorn + real File persistence + Vite + system browser; "
                          "synthetic fixture only, no model calls and no paid APIs.",
            "tail": tail(log, 12),
        }
        status = PASS if executed else FAIL
        self.record(step, status, started, clock, checks=checks, log=rel(log))
        return status

    # -- LOCAL-05: cleanup and residual-state proof ------------------------ #
    def step_local_05(self) -> str:
        step, started, clock = "LOCAL-05", utc_now(), time.monotonic()
        document = self.load()
        ports = set()
        for entry in document["steps"]:
            checks = entry.get("checks") or {}
            if isinstance(checks.get("port"), int):
                ports.add(checks["port"])
            if isinstance(checks.get("api_port"), int):
                ports.add(checks["api_port"])
            if isinstance(checks.get("web_port"), int):
                ports.add(checks["web_port"])
            for port in checks.get("web_server_ports") or []:
                if isinstance(port, int):
                    ports.add(port)
        stale_ports = sorted(port for port in ports if port_open(port))
        leaked = owned_processes(self.run_id)
        runtime_bytes_before = size_tree(self.runtime)
        evidence_bytes = size_tree(self.evidence)
        shutil.rmtree(self.runtime, ignore_errors=True)
        runtime_removed = not self.runtime.exists()
        checks = {
            "tracked_ports": sorted(ports),
            "stale_ports": stale_ports,
            "leaked_processes": leaked,
            "runtime_bytes_before": runtime_bytes_before,
            "evidence_bytes_retained": evidence_bytes,
            "runtime_removed": runtime_removed,
            "evidence_files": sorted(path.name for path in self.evidence.iterdir() if path.is_file()),
            "scope_note": "Removed only .runtime/local-ci/<run-id> created by this run; "
                          "logs/JUnit/hashes in the evidence directory are retained.",
        }
        status = PASS if not stale_ports and not leaked and runtime_removed else FAIL
        self.record(step, status, started, clock, checks=checks)
        return status

    def dispatch(self, step: str) -> str:
        handler = {
            "LOCAL-01": self.step_local_01,
            "LOCAL-02": self.step_local_02,
            "LOCAL-03": self.step_local_03,
            "LOCAL-04": self.step_local_04,
            "LOCAL-05": self.step_local_05,
        }[step]
        try:
            return handler()
        except Exception as exc:  # noqa: BLE001 - a crashing step must be a recorded failure
            self.record(step, FAIL, utc_now(), time.monotonic(),
                        checks={"exception": f"{type(exc).__name__}: {exc}"})
            return FAIL


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="AI-Novel-Studio V2 local minimum CI (LOCAL-01..05)")
    parser.add_argument("--step", help="LOCAL-01..LOCAL-05 (comma separated)")
    parser.add_argument("--all", action="store_true", help="run the five documented steps in order")
    parser.add_argument("--label", default="", help="run id (default: UTC timestamp)")
    args = parser.parse_args(argv)

    if args.all:
        requested = list(STEPS)
    elif args.step:
        requested = [item.strip().upper() for item in args.step.split(",") if item.strip()]
        unknown = [item for item in requested if item not in STEPS]
        if unknown:
            parser.error(f"unknown step(s): {', '.join(unknown)}; expected {', '.join(STEPS)}")
    else:
        parser.error("provide --step LOCAL-0X or --all")

    ci = LocalCi(args.label)
    print(f"run id  : {ci.run_id}")
    print(f"head    : {git('rev-parse', 'HEAD')}")
    print(f"evidence: {rel(ci.evidence)}")
    statuses = {}
    for step in requested:
        statuses[step] = ci.dispatch(step)
    document = ci.load()
    print("\n--- local CI summary ---")
    for entry in document["steps"]:
        print(f"{entry['step']}  {entry['status']:<20} {entry['duration_s']:>8}s  {entry.get('log', '')}")
    print(f"overall: {document['overall_status']}")
    print(f"receipt: {rel(ci.receipt)}")
    if FAIL in statuses.values():
        return 1
    if any(status in (PARTIAL, BLOCKED) for status in statuses.values()):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())