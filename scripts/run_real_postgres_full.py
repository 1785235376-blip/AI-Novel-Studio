from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

try:
    from .pytest_temp_isolation import cleanup_pytest_temp, pytest_environment, pytest_temp_root
except ImportError:
    from pytest_temp_isolation import cleanup_pytest_temp, pytest_environment, pytest_temp_root


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / ".runtime" / "v061-acceptance-environment.json"


def command(python: Path, target: Path) -> list[str]:
    return [str(python), "-m", "pytest", "-p", "no:cacheprovider", f"--basetemp={target}", "-q"]


def main() -> int:
    if not MANIFEST.is_file():
        print("Acceptance environment manifest is unavailable", file=sys.stderr)
        return 2
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    run_id = str(manifest.get("run_id") or "")
    values = manifest.get("environment")
    if not isinstance(values, dict):
        print("Acceptance environment manifest is invalid", file=sys.stderr)
        return 2
    target = pytest_temp_root(ROOT, run_id)
    try:
        target.mkdir(parents=True, exist_ok=False)
        probe = target / ".write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
    except OSError as exc:
        print(f"RUN-SCOPED PYTEST TEMP DIRECTORY UNAVAILABLE: {type(exc).__name__}", file=sys.stderr)
        return 2
    environment = pytest_environment(os.environ.copy(), target)
    environment.update({key: str(value) for key, value in values.items()})
    environment["STORAGE_BACKEND"] = "postgres"
    environment["TEST_POSTGRES_DATABASE_URL"] = str(values.get("DATABASE_URL", ""))
    python = ROOT / ".venv" / "Scripts" / "python.exe"
    try:
        return subprocess.run(command(python, target), cwd=ROOT, env=environment, check=False).returncode
    finally:
        try:
            cleanup_pytest_temp(ROOT, run_id)
        except OSError as exc:
            print(f"PYTEST TEMP CLEANUP FAILED: {type(exc).__name__}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())

