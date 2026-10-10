"""Package download caching must not reuse application state or skip validation."""
from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / "workflows/cloud-ci.yml"


def job(name):
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [\w-]+:\n|\Z)",
        WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE | re.DOTALL,
    )
    assert match is not None, name
    return match.group(0)


@pytest.mark.parametrize("name", ["backend-execution", "backend-tcp"])
def test_cache_is_download_only_and_keyed_by_all_python_dependencies(name):
    source = job(name)
    assert "PIP_CACHE_DIR: ${{ runner.temp }}/novel-pip-download-cache" in source
    assert "cache: pip" in source
    assert "cache-dependency-path: |\n            pyproject.toml\n            .github/ci/python-constraints.txt" in source
    assert "cache-hit" not in source  # A hit never bypasses installation or tests.
    assert "python -m pip install -c .github/ci/python-constraints.txt -e '.[dev,fontbuild,otio,comic]'" in source
    assert "python -m pip check" in source
    assert 'python -m pip freeze --exclude-editable > "$CI_RECEIPTS/python-packages.txt"' in source
    assert 'python -m pip cache info > "$CI_RECEIPTS/pip-cache-info.txt"' in source
    assert "actions/cache" not in source  # Do not restore a venv, database or HOME.


def test_explicit_pip_download_cache_survives_application_home_isolation(tmp_path):
    cache = tmp_path / "download-cache"
    cache.mkdir()
    observed = []
    for name in ("runner", "ci-sandbox", "v2-owned-checkout"):
        home = tmp_path / name / "home"
        xdg = tmp_path / name / "xdg-cache"
        home.mkdir(parents=True)
        xdg.mkdir(parents=True)
        env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home),
               "XDG_CACHE_HOME": str(xdg), "PIP_CACHE_DIR": str(cache),
               "PIP_CONFIG_FILE": os.devnull}
        result = subprocess.run(
            [sys.executable, "-m", "pip", "cache", "dir"],
            env=env, text=True, capture_output=True, check=True,
        )
        observed.append(Path(result.stdout.strip()).resolve())
    assert observed == [cache.resolve()] * 3


def test_cache_checks_execute_in_existing_independent_tcp_budget():
    source = job("backend-tcp")
    assert ".github/ci/test_tcp_evidence.py .github/ci/test_backend_dependency_cache.py" in source
    assert "timeout-minutes: 10" in source
    assert "continue-on-error" not in source
    assert ".github/ci/test_backend_dependency_cache.py" not in job("backend-execution")
