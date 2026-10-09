"""Cross-platform isolation and evidence coverage for the V2 check runner."""
from pathlib import Path

from scripts.run_v2_checks import isolated_environment, source_snapshot


def test_v2_runner_owns_posix_and_windows_state_directories(tmp_path):
    profile = tmp_path / ".runtime" / "v2-checks" / "test"
    environment = isolated_environment(tmp_path, profile)
    for key in ("NOVEL_DATA_PATH", "LOCALAPPDATA", "APPDATA", "HOME", "USERPROFILE",
                "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        path = Path(environment[key])
        assert path.is_absolute() and path.is_dir() and path.is_relative_to(profile)
    assert environment["PROJECT_ROOT"] == str(tmp_path)
    assert environment["CREDENTIAL_VAULT_BACKEND"] == "memory"
    assert environment["ENABLE_CLOUD"] == "false"
    assert environment["MOCK_PROVIDER"] == "true"


def test_v2_runner_receipt_hashes_runtime_tests_and_frontend(tmp_path):
    sources = (
        "app/creative/service.py", "app/model_center/discovery.py", "app/broker/service.py",
        "tests/test_creative.py", "scripts/run_v2_checks.py", "frontend/src/creative/App.tsx",
        "frontend/tests/creative.test.ts", "frontend/package.json", "pyproject.toml",
        ".github/ci/python-constraints.txt",
    )
    for name in (*sources, "app/__pycache__/service.pyc", "frontend/node_modules/dependency.js"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("before", encoding="utf-8")
    before = source_snapshot(tmp_path)
    assert set(before) == set(sources)
    path = tmp_path / "app/model_center/discovery.py"
    path.write_text("after", encoding="utf-8")
    assert before[path.relative_to(tmp_path).as_posix()] != source_snapshot(tmp_path)[path.relative_to(tmp_path).as_posix()]


def test_v2_snapshot_omits_only_untracked_fixture_runtime_state(tmp_path, monkeypatch):
    import hashlib
    from scripts.extend_v2_coverage_manifest import current_sources
    genuine = {"tests/fixtures/novels/sample_novel/chapter_1.txt", "tests/fixtures/new_fixture.json"}
    tracked = {"tests/fixtures/reference/chapter_identity.json",
               "tests/fixtures/reference/.workspace-mutation-locks/fixture.lock"}
    generated = {"tests/fixtures/novels/sample_novel/chapter_identity.json",
                 "tests/fixtures/.workspace-mutation-locks/runtime.lock"}
    historical = "tests/fixtures/historical/chapter_identity.json"
    for name in genuine | tracked | generated | {historical}:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr("scripts.run_v2_checks.tracked_source_paths", lambda root: tracked)
    assert set(source_snapshot(tmp_path)) == genuine | tracked
    digest = hashlib.sha256(b"fixture").hexdigest()
    # Historical source entries are always retained even if Git metadata does
    # not list them; the immutable baseline remains authoritative for them.
    baseline = {"source_files": {historical: digest}}
    assert set(current_sources(tmp_path, baseline)) == genuine | tracked | {historical}
    assert all((tmp_path / name).is_file() for name in generated)


def test_v2_snapshot_does_not_guess_untracked_status_without_git(tmp_path, monkeypatch):
    name = "tests/fixtures/reference/chapter_identity.json"
    path = tmp_path / name
    path.parent.mkdir(parents=True)
    path.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr("scripts.run_v2_checks.tracked_source_paths", lambda root: None)
    assert name in source_snapshot(tmp_path)


def test_staged_catalog_imports_cannot_write_to_host_home_or_use_host_secrets(tmp_path, monkeypatch):
    from scripts.refresh_v2_staged_catalog import staged_environment

    for key in ("HOME", "USERPROFILE", "XDG_DATA_HOME", "LOCALAPPDATA", "APPDATA"):
        monkeypatch.setenv(key, "/host-state-not-owned")
    sensitive = ("OPENAI_API_KEY", "MODEL_TOKEN", "PROVIDER_SECRET", "DATABASE_URL",
                 "TEST_POSTGRES_DATABASE_URL", "E2E_DATABASE_URL",
                 "COLLABORATION_DEV_SESSIONS_JSON", "PACKAGED_CONTROL_PIPE")
    for key in sensitive:
        monkeypatch.setenv(key, "synthetic-do-not-inherit")
    environment = staged_environment(tmp_path)
    assert not set(sensitive).intersection(environment)
    for key in ("HOME", "USERPROFILE", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
                "XDG_CACHE_HOME", "LOCALAPPDATA", "APPDATA", "NOVEL_DATA_PATH"):
        path = Path(environment[key])
        assert path.is_dir() and path.is_relative_to(tmp_path / ".profile")
    assert environment["PROJECT_ROOT"] == environment["PYTHONPATH"] == str(tmp_path)
    assert environment["MOCK_PROVIDER"] == "true"
    assert environment["ENABLE_CLOUD"] == "false"
    assert environment["STORAGE_BACKEND"] == "file"
