"""Run V2 verification in an owned profile and retain the real result."""
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--postgres-url', default='')
    parser.add_argument("label")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9-]+", args.label):
        parser.error("label must be a simple lowercase identifier")
    root = Path(__file__).resolve().parents[1]
    profile = root / ".runtime" / "v2-checks" / args.label
    evidence = root / "docs" / "delivery" / "v2-development"
    evidence.mkdir(parents=True, exist_ok=True)
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        parser.error("provide a command after --")
    if command[0] == "python":
        command[0] = sys.executable
    env = os.environ.copy()
    for key in list(env):
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")) or key in {
            "DATABASE_URL", "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL",
            "COLLABORATION_DEV_SESSIONS_JSON", "PACKAGED_CONTROL_PIPE",
        }:
            env.pop(key, None)
    isolated = {
        "PROJECT_ROOT": str(root), "PYTHONPATH": str(root),
        "NOVEL_DATA_PATH": str(profile / "data"),
        "LOCALAPPDATA": str(profile / "Local"),
        "CREDENTIAL_VAULT_BACKEND": "memory",
        "CREDENTIAL_VAULT_SERVICE": "AI-Novel-Studio-V2-Verification",
        "STORAGE_BACKEND": "file", "PYTHONDONTWRITEBYTECODE": "1",
        "ENABLE_PACKAGED_RUNTIME": "false", "ENABLE_COLLABORATION_RUNTIME": "false",
    }
    env.update(isolated)
    if args.postgres_url:
        endpoint = urlparse(args.postgres_url)
        if endpoint.hostname not in {'127.0.0.1', 'localhost'} or not endpoint.path.startswith('/v2_'):
            parser.error('PostgreSQL checks require a loopback, V2-owned database')
        env.update(STORAGE_BACKEND='postgres', DATABASE_URL=args.postgres_url,
                   TEST_POSTGRES_DATABASE_URL=args.postgres_url)
        isolated['STORAGE_BACKEND'] = 'postgres'
        isolated['postgres_endpoint'] = f'{endpoint.hostname}:{endpoint.port}{endpoint.path}'
    started = datetime.now(timezone.utc).isoformat()
    result = subprocess.run(command, cwd=root, env=env, text=True,
                            encoding="utf-8", errors="replace", capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    finished = datetime.now(timezone.utc).isoformat()
    output = result.stdout + result.stderr
    for key, value in os.environ.items():
        if key.endswith(("_API_KEY", "_TOKEN", "_SECRET")) and len(value) >= 8:
            output = output.replace(value, "[REDACTED]")
    log = evidence / f"{args.label}.log"
    log.write_text(output, encoding="utf-8")
    sources = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
               for folder in (root / "app" / "creative", root / "frontend" / "src" / "creative")
               for p in folder.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    receipt = {"command": command, "cwd": str(root), "started_utc": started,
               "finished_utc": finished, "exit_code": result.returncode,
               "status": "PASS" if result.returncode == 0 else "FAIL",
               "isolated_environment": isolated,
               "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
               "source_sha256": sources, "log": log.relative_to(root).as_posix(),
               "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    (evidence / f"{args.label}.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)
    print(json.dumps({"receipt": f"docs/delivery/v2-development/{args.label}.json", "status": receipt["status"]}, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
