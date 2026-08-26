from __future__ import annotations

from pathlib import Path

import pytest

from scripts.pytest_temp_isolation import cleanup_pytest_temp, pytest_environment, pytest_temp_root
from scripts.run_real_postgres_full import command


def test_pytest_invocation_receives_run_scoped_repository_basetemp(tmp_path):
    target = pytest_temp_root(tmp_path, "v061-run-a")
    invocation = command(Path("python.exe"), target)
    assert f"--basetemp={target}" in invocation
    assert target == (tmp_path / ".runtime" / "pytest-temp" / "v061-run-a").resolve()


def test_two_run_ids_have_distinct_temp_roots(tmp_path):
    assert pytest_temp_root(tmp_path, "run-a") != pytest_temp_root(tmp_path, "run-b")


def test_temp_environment_does_not_require_windows_user_temp(tmp_path):
    target = pytest_temp_root(tmp_path, "run-a")
    environment = pytest_environment({"TMP": r"C:\Users\user\AppData\Local\Temp"}, target)
    assert environment["TMP"] == environment["TEMP"] == str(target)


@pytest.mark.parametrize("run_id", ["../pgdata-main", "", "bad/run"])
def test_invalid_or_pgdata_like_run_id_is_rejected(tmp_path, run_id):
    with pytest.raises(ValueError):
        pytest_temp_root(tmp_path, run_id)


def test_cleanup_removes_only_current_run_tree(tmp_path):
    current = pytest_temp_root(tmp_path, "current")
    other = pytest_temp_root(tmp_path, "other")
    current.mkdir(parents=True); other.mkdir(parents=True)
    (current / "owned.txt").write_text("owned")
    (other / "unrelated.txt").write_text("keep")
    cleanup_pytest_temp(tmp_path, "current")
    assert not current.exists()
    assert (other / "unrelated.txt").read_text() == "keep"
