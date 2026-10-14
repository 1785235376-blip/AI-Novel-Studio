"""UX-PRODUCT batch acceptance checks (batch 1: UX-01 entry/intent + UX-02 task center).

Runs the UX-PRODUCT acceptance surface, records every real result as a receipt in
the existing `docs/delivery/v2-development/phase6-*` / `phase7-*` style, and never
fabricates a pass. A check whose target source does not exist yet is recorded as
NOT_YET_AVAILABLE with the exact reason and the owning line (A or B); the
PostgreSQL check is recorded as SKIPPED / NOT_CONFIGURED when no V2-owned loopback
database URL is configured.

This runner deliberately reuses `scripts/run_v2_checks.py` for the isolated profile
environment and the source snapshot, so receipts bind to the same source set and
the same SHA256 map format as the phase 4/5/6/7 receipts, and it reuses
`scripts/pytest_temp_isolation.py` so pytest's own tmp_path stays inside the owned
runtime profile.

Frontend interpreter resolution
-------------------------------
The repo's existing cross-platform convention is an environment variable resolved
by the consumer, e.g. `process.env.PYTHON || 'python3'` in
`frontend/src/novel/FountainParser.test.ts`, `frontend/src/creative/
screenplayFountainParser.test.ts` and `frontend/playwright.export.config.ts`, and
`process.env.INTEROP_PYTHON || 'python'` / `R3_PYTHON` / `R4_PYTHON` /
`SURFACE_PYTHON` / `V2_PYTHON` in the other Playwright configs. CI exports those
names (`.github/workflows/cloud-ci.yml`) and runs the unit suite on ubuntu-24.04
where `python3` exists, which is why the `'python3'` fallback is correct there but
fails on a Windows host that only has `python`.

This runner therefore exports, for the frontend check only:

* `PYTHON`      = the verified interpreter (see `resolve_python`)
* `PYTHONUTF8`  = `1`

`PYTHONUTF8=1` is also an established repository convention for this Windows host
(see `docs/delivery/full-recovery/WINDOWS_RUNTIME_FIXES.md`), because the host's
ANSI code page is GBK/cp936 while the node tests speak UTF-8 over the child
process pipes. Without it a child that writes raw bytes
(`sys.stdout.buffer.write`) corrupts non-ASCII text. Both settings adjust test
harness resolution only: no test case is deleted or skipped, no assertion changes,
no interpreter is copied or renamed, and PATH is not modified.

Usage (from the worktree root):

    python scripts/run_ux_product_checks.py                     # every check
    python scripts/run_ux_product_checks.py --checks types,build,tokens
    python scripts/run_ux_product_checks.py --list
    python scripts/run_ux_product_checks.py --revision 1
    python scripts/run_ux_product_checks.py --backend-tests tests/test_a.py,tests/test_b.py
    python scripts/run_ux_product_checks.py --postgres-url postgresql://postgres@127.0.0.1:55432/v2_uxproduct

Exit codes: 0 = every executed check PASS; 1 = at least one FAIL;
2 = no FAIL but at least one NOT_YET_AVAILABLE or SKIPPED result.
"""
from __future__ import annotations

import sys

# Importing the sibling runners below must not leave scripts/__pycache__ behind,
# and every check subprocess also runs with PYTHONDONTWRITEBYTECODE=1.
sys.dont_write_bytecode = True

import argparse  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
from pathlib import Path  # noqa: E402
import re  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
from urllib.parse import urlparse  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "delivery" / "v2-development"
FRONTEND = ROOT / "frontend"

sys.path.insert(0, str(ROOT / "scripts"))
from run_v2_checks import isolated_environment, source_snapshot  # noqa: E402
from pytest_temp_isolation import (  # noqa: E402
    cleanup_pytest_temp,
    pytest_environment,
    pytest_temp_root,
)

PHASE = "ux-product-batch1"
PREFIX = "ux-product"

# UX batch 1 backend surface: the production workflow contract the entry/intent
# panel reuses, plus the studio seam the task center consumes. `--backend-tests`
# lets later batches extend or replace this list without editing the runner.
DEFAULT_BACKEND_TESTS = [
    "tests/test_v2_production_workflow.py",
    "tests/test_v2_production_workflow_api.py",
    "tests/test_v2_independent_workspace_api.py",
]
# The protected-surface / seam regression: pre-existing router-factory and
# admission tests that prove the studio seam UX batch 1 extends still holds.
SEAM_TESTS = ["tests/test_v2_independent_workspace_api.py"]
# UX-01 (LINE_A) and UX-02 (LINE_B) frontend folders.
FRONTEND_FOLDERS = ["src/onboarding", "src/taskcenter"]
PYTEST_FLAGS = ["-p", "no:cacheprovider", "-q"]

# Python cache directories this runner must never leave behind in the repository.
CACHE_NAMES = {"__pycache__", ".pytest_cache"}
CACHE_SCAN_DIRS = ("app", "tests", "scripts", ".github", "frontend/src", "frontend/tests", "database")

PASS, FAIL, NOT_YET, SKIPPED = "PASS", "FAIL", "NOT_YET_AVAILABLE", "SKIPPED"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(text: str = "") -> None:
    """Console output must never abort a check on a Windows GBK console."""
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = getattr(sys.stdout, "encoding", None) or "ascii"
        print(text.encode(encoding, "replace").decode(encoding, "replace"))


def shell_command(argv: list[str]) -> list[str]:
    """Run a shim (corepack/pnpm) through cmd.exe; corepack is a .cmd script."""
    if os.name == "nt":
        comspec = os.environ.get("COMSPEC", "cmd.exe")
        return [comspec, "/d", "/s", "/c", subprocess.list2cmdline(argv)]
    return argv


def resolve_python() -> str:
    """The verified interpreter, resolved by the repository's existing convention.

    An explicit override wins only when it names an existing file, so a bare
    `python3` inherited from a POSIX-oriented environment cannot win on Windows.
    """
    for key in ("UX_PRODUCT_PYTHON", "PHASE7_PYTHON", "PYTHON"):
        value = os.environ.get(key)
        if value and Path(value).is_file():
            return str(Path(value).resolve())
    return sys.executable


PYTHON = resolve_python()


def python_version(interpreter: str) -> str:
    """Prove the resolved interpreter really runs, for the receipt."""
    try:
        result = subprocess.run([interpreter, "-c", "import sys;print(sys.version.split()[0])"],
                                text=True, encoding="utf-8", errors="replace",
                                capture_output=True, timeout=60)
        return (result.stdout or result.stderr or "").strip().splitlines()[-1] if result.returncode == 0 \
            else f"UNUSABLE (exit {result.returncode})"
    except Exception as exc:  # pragma: no cover - diagnostic only
        return f"UNUSABLE ({exc})"


def pnpm_version() -> str:
    """The pnpm version as resolved from the frontend folder."""
    try:
        result = subprocess.run(shell_command(["corepack", "pnpm", "--version"]),
                                cwd=FRONTEND, text=True, encoding="utf-8",
                                errors="replace", capture_output=True, timeout=180)
        text = (result.stdout or "") + (result.stderr or "")
        return text.strip().splitlines()[-1] if text.strip() else "UNKNOWN"
    except Exception as exc:  # pragma: no cover - diagnostic only
        return f"UNKNOWN ({exc})"


def python_cache_dirs() -> set[str]:
    """Every `__pycache__` / `.pytest_cache` directory currently in the repository."""
    found: set[str] = set()
    for name in CACHE_SCAN_DIRS:
        base = ROOT / name
        if not base.is_dir():
            continue
        if base.name in CACHE_NAMES:
            found.add(base.relative_to(ROOT).as_posix())
        for path in base.rglob("*"):
            if path.is_dir() and path.name in CACHE_NAMES:
                found.add(path.relative_to(ROOT).as_posix())
    for path in ROOT.glob("*"):
        if path.is_dir() and path.name in CACHE_NAMES:
            found.add(path.relative_to(ROOT).as_posix())
    return found


def purge_new_python_caches(before: set[str]) -> list[str]:
    """Remove only cache directories this run created, restoring the prior state."""
    removed: list[str] = []
    root = ROOT.resolve()
    for relative in sorted(python_cache_dirs() - before):
        target = ROOT / relative
        if not target.is_dir() or target.name not in CACHE_NAMES:
            continue
        try:
            if not target.resolve().is_relative_to(root):
                continue
        except OSError:
            continue
        shutil.rmtree(target, ignore_errors=True)
        removed.append(relative)
    return removed


def existing_tests(targets: list[str]) -> list[str]:
    return [t for t in targets if (ROOT / t).is_file()]


def next_revision(label: str) -> int:
    highest = 0
    for path in EVIDENCE.glob(f"{label}-r*.json"):
        match = re.fullmatch(re.escape(label) + r"-r(\d+)\.json", path.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def head_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "UNKNOWN"


def postgres_target(requested: str) -> tuple[str | None, str | None]:
    """Return (url, refusal_reason); only a loopback V2-owned database is used."""
    url = requested or os.environ.get("TEST_POSTGRES_DATABASE_URL") or os.environ.get("DATABASE_URL") or ""
    if not url:
        return None, ("NOT_CONFIGURED: TEST_POSTGRES_DATABASE_URL is not set and --postgres-url was not "
                      "given; no V2-owned loopback PostgreSQL endpoint is configured on this machine. "
                      "The check is SKIPPED / NOT_CONFIGURED, never a pass.")
    endpoint = urlparse(url)
    if endpoint.hostname not in {"127.0.0.1", "localhost"} or not endpoint.path.startswith("/v2_"):
        return None, "Refused: PostgreSQL checks require a loopback, V2-owned (/v2_*) database."
    return url, None


def environment_for(check: dict, label: str, postgres: str | None) -> tuple[dict, dict]:
    env = os.environ.copy()
    for key in list(env):
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")) or key in {
            "DATABASE_URL", "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL",
            "COLLABORATION_DEV_SESSIONS_JSON", "PACKAGED_CONTROL_PIPE",
        }:
            env.pop(key, None)
    profile = ROOT / ".runtime" / "v2-checks" / label
    isolated = isolated_environment(ROOT, profile)
    env.update(isolated)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if check["kind"] == "pytest":
        # These tests assert that pytest's own tmp_path stays inside the repository
        # runtime profile; reuse the existing rule instead of the machine temp folder.
        target = pytest_temp_root(ROOT, label)
        cleanup_pytest_temp(ROOT, label)
        target.mkdir(parents=True, exist_ok=True)
        env = pytest_environment(env, target)
        isolated = {**isolated, "TMP": str(target), "TEMP": str(target), "TMPDIR": str(target)}
    if check["kind"] == "vitest":
        # Test-harness interpreter resolution only: the existing convention used by
        # FountainParser.test.ts / screenplayFountainParser.test.ts /
        # playwright.export.config.ts is `process.env.PYTHON || 'python3'`, and CI
        # supplies it. PYTHONUTF8=1 stops the GBK/cp936 host code page from
        # corrupting UTF-8 over the child process pipes.
        env["PYTHON"] = PYTHON
        env["PYTHONUTF8"] = "1"
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        isolated = {**isolated, "PYTHON": PYTHON, "PYTHONUTF8": "1"}
    if check["check"] == "postgres" and postgres:
        endpoint = urlparse(postgres)
        env.update(STORAGE_BACKEND="postgres", DATABASE_URL=postgres, TEST_POSTGRES_DATABASE_URL=postgres)
        isolated = {**isolated, "STORAGE_BACKEND": "postgres",
                    "postgres_endpoint": f"{endpoint.hostname}:{endpoint.port}{endpoint.path}"}
    return env, isolated


def pytest_argv(targets: list[str]) -> list[str]:
    return [PYTHON, "-m", "pytest", *PYTEST_FLAGS, *targets]


def pytest_check(kind: str, targets: list[str], line: str, note: str | None = None) -> dict:
    """A pytest check, or NOT_YET_AVAILABLE when none of its modules exist yet."""
    present = existing_tests(targets)
    if not present:
        return {"check": kind, "kind": "pytest", "status": NOT_YET, "line": line,
                "reason": "No UX-PRODUCT " + kind + " backend test module exists yet (looked for "
                          + ", ".join(targets) + ").",
                "targets": [], "logical_command": None, "note": note}
    return {"check": kind, "kind": "pytest", "status": None, "line": line,
            "targets": present, "logical_command": pytest_argv(present), "argv": pytest_argv(present),
            "note": note}


def frontend_targets() -> tuple[list[str], list[str]]:
    """(existing folders, missing folders) for the UX batch 1 frontend surface."""
    return ([f for f in FRONTEND_FOLDERS if (FRONTEND / f).is_dir()],
            [f for f in FRONTEND_FOLDERS if not (FRONTEND / f).is_dir()])


def frontend_test_files(folders: list[str]) -> list[str]:
    """The *.test.ts(x) files inside the existing UX batch 1 folders."""
    found: list[str] = []
    for folder in folders:
        base = FRONTEND / folder
        found.extend(p.relative_to(FRONTEND).as_posix() for p in base.rglob("*")
                     if p.is_file() and re.search(r"\.test\.tsx?$", p.name))
    return sorted(set(found))


def plan_checks(args) -> list[dict]:
    backend_tests = args.backend_tests or DEFAULT_BACKEND_TESTS
    postgres, postgres_reason = postgres_target(args.postgres_url)
    present_folders, missing_folders = frontend_targets()

    checks: list[dict] = [pytest_check(
        "file", backend_tests, "LINE_A+LINE_B",
        "Focused UX batch-1 backend surface (production workflow contract + studio seam).")]

    if postgres is None:
        checks.append({"check": "postgres", "kind": "pytest", "status": SKIPPED, "line": "LINE_A+LINE_B",
                       "reason": postgres_reason, "targets": existing_tests(backend_tests),
                       "logical_command": None, "configuration": "STORAGE_BACKEND=postgres"})
    else:
        check = pytest_check("postgres", backend_tests, "LINE_A+LINE_B",
                             "Same focused surface against a real loopback V2-owned PostgreSQL database.")
        check["configuration"] = "STORAGE_BACKEND=postgres"
        checks.append(check)

    if not present_folders:
        checks.append({"check": "frontend", "kind": "vitest", "status": NOT_YET, "line": "LINE_A+LINE_B",
                       "reason": "Neither frontend/" + " nor frontend/".join(FRONTEND_FOLDERS)
                                 + " exists yet; the UX batch-1 frontend surface is not written.",
                       "targets": [], "logical_command": None})
    elif not frontend_test_files(present_folders):
        checks.append({"check": "frontend", "kind": "vitest", "status": NOT_YET, "line": "LINE_A+LINE_B",
                       "reason": "frontend/" + " and frontend/".join(present_folders)
                                 + " exist but contain no *.test.ts(x) file yet.",
                       "targets": present_folders, "logical_command": None})
    else:
        checks.append({"check": "frontend", "kind": "vitest", "status": None,
                       "line": "LINE_A+LINE_B" if len(present_folders) == len(FRONTEND_FOLDERS) else
                               ("LINE_A" if "src/onboarding" in present_folders else "LINE_B"),
                       "targets": present_folders, "cwd": FRONTEND,
                       "frontend_test_files": frontend_test_files(present_folders),
                       "logical_command": ["corepack", "pnpm", "exec", "vitest", "run", *present_folders],
                       "note": ("Runs only the folders that exist"
                                + (f"; still missing: {', '.join(missing_folders)}" if missing_folders else "")
                                + ". PYTHON/PYTHONUTF8 resolve the interpreter for the existing "
                                  "FountainParser-style suites.")})

    checks.append({"check": "types", "kind": "pnpm", "status": None, "line": "LINE_B",
                   "targets": ["frontend/tsconfig.json"], "cwd": FRONTEND,
                   "logical_command": ["corepack", "pnpm", "exec", "tsc", "-b"],
                   "note": "tsc -b writes only the gitignored frontend/tsconfig.tsbuildinfo."})
    checks.append({"check": "build", "kind": "pnpm", "status": None, "line": "LINE_B",
                   "targets": ["frontend/package.json"], "cwd": FRONTEND,
                   "logical_command": ["corepack", "pnpm", "run", "build"],
                   "note": "The frozen script is `tsc -b && vite build`; output goes to the gitignored, "
                           "pre-existing frontend/dist. No tracked file is written."})
    checks.append({"check": "tokens", "kind": "pnpm", "status": None, "line": "LINE_B",
                   "targets": ["frontend/package.json"], "cwd": FRONTEND,
                   "logical_command": ["corepack", "pnpm", "run", "lint"],
                   "note": "Frozen design-token checker scripts/check_ui_design_tokens.mjs."})

    checks.append(pytest_check("seam", SEAM_TESTS, "PRE_EXISTING_SEAM",
                               "Pre-existing router-factory/admission tests; the protected-surface "
                               "regression UX batch 1 must not break."))

    if args.checks:
        wanted = {name.strip() for name in args.checks.split(",") if name.strip()}
        known = {c["check"] for c in checks}
        unknown = wanted - known
        if unknown:
            raise SystemExit(f"unknown check(s): {', '.join(sorted(unknown))}; known: {', '.join(sorted(known))}")
        checks = [c for c in checks if c["check"] in wanted]
    return checks


def write_receipt(check, label, output, exit_code, started, finished, isolated, sources, extra):
    log = EVIDENCE / f"{label}.log"
    log.write_text(output, encoding="utf-8")
    after = source_snapshot(ROOT) if sources is not None else None
    receipt = {
        "check": check["check"], "kind": check["kind"],
        "phase": PHASE,
        "status": check["status"], "exit_code": exit_code,
        "logical_command": check.get("logical_command"),
        "command": check.get("argv") or check.get("logical_command"),
        "cwd": str(check.get("cwd", ROOT)),
        "targets": check.get("targets", []),
        "frontend_test_files": check.get("frontend_test_files"),
        "started_utc": started, "finished_utc": finished,
        "isolated_environment": isolated,
        "python": PYTHON if check["kind"] == "pytest" else None,
        "python_version": python_version(PYTHON) if check["kind"] == "pytest" else None,
        "frontend_interpreter": {"PYTHON": PYTHON, "PYTHONUTF8": "1",
                                 "resolved_version": python_version(PYTHON)}
                                if check["kind"] == "vitest" else None,
        "pnpm": pnpm_version() if check.get("cwd") == FRONTEND else None,
        "head": head_sha(),
        "source_sha256": sources or {},
        "source_sha256_before": sources or {},
        "sources_changed_during_check": (sources != after) if sources is not None else None,
        "log": log.relative_to(ROOT).as_posix(),
        "log_sha256": _sha256(log),
        "note": check.get("note"),
        **extra,
    }
    (EVIDENCE / f"{label}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
                                            encoding="utf-8")
    emit("=" * 78)
    emit(f"{label}: {receipt['status']}" + (f" (exit {exit_code})" if exit_code is not None else ""))
    if receipt.get("reason"):
        emit(f"  reason: {receipt['reason']}")
    if output:
        emit(output.rstrip()[-4000:])
    emit(f"  receipt: docs/delivery/v2-development/{label}.json")
    return receipt


def run_check(check: dict, args) -> dict:
    revision = args.revision or next_revision(f"{PREFIX}-{check['check']}")
    label = f"{PREFIX}-{check['check']}-r{revision}"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if check["status"] in {NOT_YET, SKIPPED}:
        return write_receipt(check, label, "", None, None, None, {}, None,
                             {"reason": check["reason"], "pending_dependency": check.get("line"),
                              "configuration": check.get("configuration"),
                              "python_caches_removed_by_this_run": [],
                              "python_caches_left_behind": sorted(python_cache_dirs())})
    env, isolated = environment_for(check, label, args.postgres_url)
    argv = check.get("argv") or shell_command(check["logical_command"])
    caches_before = python_cache_dirs()
    sources_before = source_snapshot(ROOT)
    started = datetime.now(timezone.utc).isoformat()
    try:
        result = subprocess.run(argv, cwd=check.get("cwd", ROOT), env=env, text=True,
                                encoding="utf-8", errors="replace", capture_output=True,
                                timeout=args.timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        output, exit_code = result.stdout + result.stderr, result.returncode
    except subprocess.TimeoutExpired as exc:
        output = ((exc.stdout or "") if isinstance(exc.stdout, str) else "")
        output += ((exc.stderr or "") if isinstance(exc.stderr, str) else "")
        output += f"\n[timeout after {args.timeout}s]\n"
        exit_code = -1
    except FileNotFoundError as exc:
        output = f"[could not start the check command: {exc}]\n"
        exit_code = -2
    finished = datetime.now(timezone.utc).isoformat()
    for key, value in os.environ.items():
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")) and len(value) >= 8:
            output = output.replace(value, "[REDACTED]")
    removed_caches = purge_new_python_caches(caches_before)
    if removed_caches:
        output += f"\n[removed python cache directories created by this run: {', '.join(removed_caches)}]\n"
    check["status"] = PASS if exit_code == 0 else FAIL
    return write_receipt(check, label, output, exit_code, started, finished, isolated, sources_before,
                         {"reason": None, "pending_dependency": None if exit_code == 0 else check.get("line"),
                          "configuration": check.get("configuration"),
                          "python_caches_removed_by_this_run": removed_caches,
                          "python_caches_left_behind": sorted(python_cache_dirs())})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--checks", default="",
                        help="comma-separated subset of: file,postgres,frontend,types,build,tokens,seam")
    parser.add_argument("--postgres-url", default="",
                        help="loopback V2-owned (/v2_*) PostgreSQL URL for the postgres check")
    parser.add_argument("--revision", type=int, default=0,
                        help="force one revision number for every receipt (default: per-check auto-increment)")
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--backend-tests", default="",
                        help="explicit backend test files (space or comma separated); default is the "
                             "UX batch-1 surface")
    parser.add_argument("--list", action="store_true", help="list the planned checks and exit")
    args = parser.parse_args()
    args.backend_tests = [p for p in re.split(r"[,\s]+", args.backend_tests) if p]

    checks = plan_checks(args)
    if args.list:
        emit(f"{'interpreter':<12} {PYTHON} ({python_version(PYTHON)})")
        for check in checks:
            emit(f"{check['check']:<9} {check['status'] or 'READY':<18} {check.get('logical_command')}")
        return 0

    if not Path(PYTHON).is_file():
        emit(f"ERROR: resolved interpreter does not exist: {PYTHON}")
        return 1

    receipts = [run_check(check, args) for check in checks]
    failed = [r for r in receipts if r["status"] == FAIL]
    pending = [r for r in receipts if r["status"] in {NOT_YET, SKIPPED}]
    summary = {"phase": PHASE,
               "results": [{"check": r["check"], "status": r["status"], "exit_code": r["exit_code"],
                            "receipt": re.sub(r"\.log$", ".json", r["log"]),
                            "log": r["log"]} for r in receipts],
               "failed": len(failed), "pending": len(pending)}
    emit("=" * 78)
    emit(json.dumps(summary, ensure_ascii=False, indent=2))
    return 1 if failed else (2 if pending else 0)


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    raise SystemExit(main())
