"""Phase 7 (unified production workflow projection + UI/UX consolidation) checks.

Runs the frozen phase-7 acceptance checks, records every real result as a
receipt in the existing `docs/delivery/v2-development/phase6-*` style, and never
fabricates a pass. A check whose target source does not exist yet is recorded as
NOT_YET_AVAILABLE with the exact reason and the owning line (A or B); the
PostgreSQL check is recorded as SKIPPED / NOT_CONFIGURED when no V2-owned
loopback database URL is configured (there is no PostgreSQL server on the
development machine).

This runner deliberately reuses `scripts/run_v2_checks.py` for the isolated
profile environment and the source snapshot, so receipts bind to the same
source set and the same SHA256 map format as the phase 4/5/6 receipts.

Usage (from the worktree root):

    python scripts/run_phase7_workflow_checks.py                # every check
    python scripts/run_phase7_workflow_checks.py --checks types,build,tokens
    python scripts/run_phase7_workflow_checks.py --list
    python scripts/run_phase7_workflow_checks.py --postgres-url postgresql://.../v2_phase7

Exit codes: 0 = every executed check PASS; 1 = at least one FAIL;
2 = no FAIL but at least one NOT_YET_AVAILABLE or SKIPPED result.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "docs" / "delivery" / "v2-development"
FRONTEND = ROOT / "frontend"

# Same isolated environment / source binding as the existing check runner, plus
# the repository's own pytest temp-isolation rule (tests assert that tmp_path
# stays inside the owned runtime profile).
sys.path.insert(0, str(ROOT / "scripts"))
from run_v2_checks import isolated_environment, source_snapshot  # noqa: E402
from pytest_temp_isolation import cleanup_pytest_temp, pytest_environment, pytest_temp_root  # noqa: E402

PYTHON = os.environ.get("PHASE7_PYTHON") or sys.executable

# The frozen Phase 7 API contract lives on the existing router factory; these
# pre-existing tests prove the seam this phase extends still holds at HEAD.
SEAM_TESTS = ["tests/test_v2_independent_workspace_api.py"]
BACKEND_GLOBS = ["test_v2_production_workflow*.py", "test_v2_workflow_projection*.py"]
FRONTEND_FOLDER = "src/production"
PYTEST_FLAGS = ["-p", "no:cacheprovider", "-q"]

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


def pnpm_version() -> str:
    """The corepack-pinned pnpm version as resolved from the frontend folder."""
    try:
        result = subprocess.run(shell_command(["corepack", "pnpm", "--version"]),
                                cwd=FRONTEND, text=True, encoding="utf-8",
                                errors="replace", capture_output=True, timeout=180)
        text = (result.stdout or "") + (result.stderr or "")
        return text.strip().splitlines()[-1] if text.strip() else "UNKNOWN"
    except Exception as exc:  # pragma: no cover - diagnostic only
        return f"UNKNOWN ({exc})"


def discover_backend_tests() -> list[str]:
    found: list[str] = []
    for pattern in BACKEND_GLOBS:
        found.extend(p.relative_to(ROOT).as_posix() for p in (ROOT / "tests").glob(pattern))
    return sorted(set(found))


def discover_frontend_tests() -> tuple[bool, list[str]]:
    folder = FRONTEND / FRONTEND_FOLDER
    if not folder.is_dir():
        return False, []
    tests = sorted(p.relative_to(FRONTEND).as_posix() for p in folder.rglob("*")
                   if p.is_file() and re.search(r"\.test\.tsx?$", p.name))
    return True, tests


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
        return None, ("TEST_POSTGRES_DATABASE_URL is not set; no PostgreSQL server is configured "
                      "on this machine (the check is NOT_CONFIGURED, not a pass).")
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
        # The Phase 7 tests (like the earlier phases) assert that pytest's own
        # tmp_path stays inside the repository runtime profile; reuse the
        # existing rule instead of letting it land in the machine temp folder.
        target = pytest_temp_root(ROOT, label)
        cleanup_pytest_temp(ROOT, label)
        target.mkdir(parents=True, exist_ok=True)
        env = pytest_environment(env, target)
        isolated = {**isolated, "TMP": str(target), "TEMP": str(target), "TMPDIR": str(target)}
    if check["check"] == "postgres" and postgres:
        endpoint = urlparse(postgres)
        env.update(STORAGE_BACKEND="postgres", DATABASE_URL=postgres, TEST_POSTGRES_DATABASE_URL=postgres)
        isolated = {**isolated, "STORAGE_BACKEND": "postgres",
                    "postgres_endpoint": f"{endpoint.hostname}:{endpoint.port}{endpoint.path}"}
    return env, isolated


def pytest_argv(targets: list[str]) -> list[str]:
    return [PYTHON, "-m", "pytest", *PYTEST_FLAGS, *targets]


def backend_check(kind: str, targets: list[str]) -> dict:
    if not targets:
        return {"check": kind, "kind": "pytest", "status": NOT_YET, "line": "LINE_A",
                "reason": "No Phase 7 backend test module exists yet (looked for "
                          + ", ".join(f"tests/{g}" for g in BACKEND_GLOBS) + ").",
                "targets": [], "logical_command": None}
    return {"check": kind, "kind": "pytest", "status": None, "line": "LINE_A",
            "targets": targets, "logical_command": pytest_argv(targets), "argv": pytest_argv(targets)}


def plan_checks(args) -> list[dict]:
    backend_tests = args.backend_tests or discover_backend_tests()
    frontend_exists, frontend_tests = discover_frontend_tests()
    postgres, postgres_reason = postgres_target(args.postgres_url)

    checks: list[dict] = [backend_check("file", backend_tests)]

    if postgres is None:
        checks.append({"check": "postgres", "kind": "pytest", "status": SKIPPED, "line": "LINE_A",
                       "reason": postgres_reason, "targets": backend_tests, "logical_command": None,
                       "configuration": "STORAGE_BACKEND=postgres"})
    else:
        check = backend_check("postgres", backend_tests)
        check["configuration"] = "STORAGE_BACKEND=postgres"
        checks.append(check)

    if not frontend_exists:
        checks.append({"check": "frontend", "kind": "vitest", "status": NOT_YET, "line": "LINE_B",
                       "reason": f"frontend/{FRONTEND_FOLDER} does not exist yet.", "targets": [],
                       "logical_command": None})
    elif not frontend_tests:
        checks.append({"check": "frontend", "kind": "vitest", "status": NOT_YET, "line": "LINE_B",
                       "reason": f"frontend/{FRONTEND_FOLDER} exists but contains no *.test.ts(x) file.",
                       "targets": [], "logical_command": None})
    else:
        checks.append({"check": "frontend", "kind": "vitest", "status": None, "line": "LINE_B",
                       "targets": frontend_tests, "cwd": FRONTEND,
                       "logical_command": ["corepack", "pnpm", "exec", "vitest", "run", FRONTEND_FOLDER]})

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

    seam = [p for p in SEAM_TESTS if (ROOT / p).is_file()]
    if seam:
        checks.append({"check": "seam", "kind": "pytest", "status": None, "line": "PRE_EXISTING_SEAM",
                       "targets": seam, "logical_command": pytest_argv(seam), "argv": pytest_argv(seam),
                       "note": "Pre-existing router-factory/admission tests; not the new Phase 7 tests."})

    if args.checks:
        wanted = {name.strip() for name in args.checks.split(",") if name.strip()}
        unknown = wanted - {c["check"] for c in checks}
        if unknown:
            raise SystemExit(f"unknown check(s): {', '.join(sorted(unknown))}")
        checks = [c for c in checks if c["check"] in wanted]
    return checks


def write_receipt(check, label, output, exit_code, started, finished, isolated, sources, extra):
    log = EVIDENCE / f"{label}.log"
    log.write_text(output, encoding="utf-8")
    after = source_snapshot(ROOT) if sources is not None else None
    receipt = {
        "check": check["check"], "kind": check["kind"],
        "phase": "phase7-production-workflow",
        "status": check["status"], "exit_code": exit_code,
        "logical_command": check.get("logical_command"),
        "command": check.get("argv") or check.get("logical_command"),
        "cwd": str(check.get("cwd", ROOT)),
        "targets": check.get("targets", []),
        "started_utc": started, "finished_utc": finished,
        "isolated_environment": isolated,
        "python": PYTHON if check["kind"] == "pytest" else None,
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
    label = f"phase7-workflow-{check['check']}-r{args.revision or next_revision('phase7-workflow-' + check['check'])}"
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    if check["status"] in {NOT_YET, SKIPPED}:
        return write_receipt(check, label, "", None, None, None, {}, None,
                             {"reason": check["reason"], "pending_dependency": check.get("line"),
                              "configuration": check.get("configuration")})
    env, isolated = environment_for(check, label, args.postgres_url)
    argv = check.get("argv") or shell_command(check["logical_command"])
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
    finished = datetime.now(timezone.utc).isoformat()
    for key, value in os.environ.items():
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")) and len(value) >= 8:
            output = output.replace(value, "[REDACTED]")
    check["status"] = PASS if exit_code == 0 else FAIL
    return write_receipt(check, label, output, exit_code, started, finished, isolated, sources_before,
                         {"reason": None, "pending_dependency": None if exit_code == 0 else check.get("line"),
                          "configuration": check.get("configuration")})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checks", default="", help="comma-separated subset of check names")
    parser.add_argument("--postgres-url", default="")
    parser.add_argument("--revision", type=int, default=0, help="force one revision number for every receipt")
    parser.add_argument("--timeout", type=int, default=7200)
    parser.add_argument("--backend-tests", default="", help="explicit backend test files (space or comma separated)")
    parser.add_argument("--list", action="store_true", help="list the planned checks and exit")
    args = parser.parse_args()
    args.backend_tests = [p for p in re.split(r"[,\s]+", args.backend_tests) if p]

    checks = plan_checks(args)
    if args.list:
        for check in checks:
            emit(f"{check['check']:<9} {check['status'] or 'READY':<18} {check.get('logical_command')}")
        return 0

    receipts = [run_check(check, args) for check in checks]
    failed = [r for r in receipts if r["status"] == FAIL]
    pending = [r for r in receipts if r["status"] in {NOT_YET, SKIPPED}]
    summary = {"phase": "phase7-production-workflow",
               "results": [{"check": r["check"], "status": r["status"], "exit_code": r["exit_code"],
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
