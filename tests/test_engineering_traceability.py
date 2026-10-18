"""Engineering traceability guard: the committed matrix must stay valid and current.

This runs in the default backend suite. It performs no app import, no model call and no scan.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "v2" / "engineering" / "requirements-traceability.json"
REQUIRED_DOCS = [
    "docs/v2/engineering/README.md",
    "docs/v2/engineering/BASELINE_20261019_r1.md",
    "docs/v2/engineering/REQUIREMENTS_TRACEABILITY.md",
    "docs/v2/engineering/RUNBOOK.md",
    "docs/v2/engineering/EXECUTION_AND_DATA_CONTRACTS.md",
    "docs/v2/engineering/SECURITY_AND_ISOLATION.md",
    "docs/v2/engineering/MEDIA_AND_COMIC_CONTRACTS.md",
    "docs/v2/engineering/RELEASE_GATES.md",
]


def _run(script: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / script), *args],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def test_traceability_matrix_is_valid_and_covered() -> None:
    result = _run("validate_requirements_traceability.py")
    assert result.returncode == 0, result.stdout + result.stderr
    document = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    ids = {entry["id"] for entry in document["requirements"]}
    assert {f"DIF-{index:02d}" for index in range(1, 13)} <= ids
    assert {f"IMAGE-COMIC-{index:02d}" for index in range(1, 21)} <= ids
    assert len([item for item in ids if len(item) == 3 and item[0].isalpha()]) == 40


def test_traceability_matrix_matches_generator() -> None:
    if not (ROOT / "scripts" / "build_requirements_traceability.py").exists():
        return
    result = _run("build_requirements_traceability.py", "--check")
    assert result.returncode == 0, result.stdout + result.stderr


def test_engineering_documents_exist() -> None:
    missing = [path for path in REQUIRED_DOCS if not (ROOT / path).exists()]
    assert not missing, missing
