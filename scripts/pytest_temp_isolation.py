from __future__ import annotations

import re
import shutil
from pathlib import Path


RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def pytest_temp_root(project_root: Path, run_id: str) -> Path:
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("invalid verification run_id")
    runtime = (project_root / ".runtime").resolve()
    root = (runtime / "pytest-temp").resolve()
    target = (root / run_id).resolve()
    if target.parent != root:
        raise ValueError("pytest temp root escapes the repository runtime")
    pgdata = (runtime / "pgdata-main").resolve()
    if target == pgdata or pgdata in target.parents:
        raise ValueError("PostgreSQL data cannot be used as pytest temp")
    return target


def pytest_environment(environment: dict[str, str], target: Path) -> dict[str, str]:
    value = str(target)
    return {**environment, "TMP": value, "TEMP": value}


def cleanup_pytest_temp(project_root: Path, run_id: str) -> None:
    target = pytest_temp_root(project_root, run_id)
    if target.exists():
        shutil.rmtree(target)

