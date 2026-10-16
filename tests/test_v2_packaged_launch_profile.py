"""V2 packaging composition contracts; no Windows runtime or vault is executed.

Process/Windows boundaries below are doubles. Existing independent bootstrap
and Host-authority suites supply their separate authorization regressions.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

from app.experimental.flags import enabled_flags, require_flag
from app.packaged_profile import DEFAULT_PROFILE, PROFILE_ENV, V2_PROFILE, validate_profile
from app.packaging import packaged_desktop_launcher as desktop
from app.packaging import packaged_launcher as launcher
from app.packaging import packaged_processes as processes
from app.packaging.launch_profiles import (
    V2_DIRECTORY, V2_FEATURES, resolve_profile_paths, validate_profile_paths,
)
from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_identity import RuntimeRole
from fastapi import HTTPException


def config(tmp_path, profile=DEFAULT_PROFILE):
    paths = resolve_profile_paths(profile, local_app_data=tmp_path / "Local", user_profile=tmp_path / "User")
    layout = SimpleNamespace(application=tmp_path / "Application", postgres=tmp_path / "Application" / "PostgreSQL", backend=tmp_path / "Backend",
                             python=tmp_path / "Python" / "python.exe", frontend_dist=tmp_path / "Frontend")
    return processes.PackagedProcessConfig(layout=layout, paths=paths, version="0.7.0", launch_profile=profile)


def test_default_environment_and_paths_keep_exact_original_contract(tmp_path):
    value = config(tmp_path)
    assert value.paths == WindowsPackagingPaths.resolve(local_app_data=tmp_path / "Local", user_profile=tmp_path / "User")
    assert value.environment(database_port=55432, backend_port=58123) == {
        "APP_VERSION": "0.7.0", "PROJECT_ROOT": str(value.layout.backend),
        "NOVEL_DATA_PATH": str(value.paths.novel_data),
        "PROMPT_PATH": str(value.layout.backend / "prompts"),
        "WORKFLOW_PATH": str(value.layout.backend / "workflows"),
        "STORAGE_BACKEND": "postgres", "DATABASE_URL": "postgresql://novel_studio@127.0.0.1:55432/ai_novel_studio",
        "FRONTEND_ORIGIN": "http://127.0.0.1:58123", "ENABLE_PACKAGED_RUNTIME": "true",
        "ENABLE_COLLABORATION_RUNTIME": "true", "EXPERIMENTAL_FEATURES": "branch_manuscript_v1",
        "COLLABORATION_DEV_SESSIONS_JSON": "", "ENABLE_PROVIDER_FALLBACK": "false",
        "PACKAGED_WINDOWS_MODE": "true", "PACKAGED_LOGS_ROOT": str(value.paths.logs),
        "PACKAGED_FRONTEND_DIST": str(value.layout.frontend_dist), "PYTHONUTF8": "1", "PYTHONNOUSERSITE": "1",
    }
    assert "launch_profile" not in value.public_runtime_metadata(database_port=55432, backend_port=58123)


@pytest.mark.parametrize("value", ["", "V2", " v2", "v2 ", "*", "unknown", "../default", None, []])
def test_unknown_profile_is_rejected_before_paths_or_runtime(tmp_path, monkeypatch, value):
    monkeypatch.setattr(WindowsPackagingPaths, "resolve", lambda **kw: pytest.fail("paths reached"))
    monkeypatch.setattr(processes.PackagedRuntimeLayout, "resolve", lambda *a: pytest.fail("runtime reached"))
    with pytest.raises(ValueError, match="PACKAGED_PROFILE_UNSUPPORTED"):
        validate_profile(value)
    with pytest.raises(ValueError, match="PACKAGED_PROFILE_UNSUPPORTED"):
        resolve_profile_paths(value)


@pytest.mark.parametrize("inherited", ["", "*", "unknown", "declarative_agents_v2,realtime_collaboration_v1"])
def test_v2_has_only_explicit_supported_dependencies(tmp_path, monkeypatch, inherited):
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", inherited)
    monkeypatch.delenv("V1_ACCEPTANCE_MODE", raising=False)
    value = config(tmp_path, V2_PROFILE)
    environment = value.environment(database_port=55432, backend_port=58123)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", environment["EXPERIMENTAL_FEATURES"])
    assert enabled_flags() == frozenset(V2_FEATURES)
    for flag in V2_FEATURES:
        require_flag(flag)
    assert environment[PROFILE_ENV] == V2_PROFILE
    assert environment["ENABLE_CLOUD"] == "false"
    assert environment["MOCK_PROVIDER"] == "false"
    assert environment["CREATION_PROFILE"] == "LOCAL_ONLY"
    assert environment["ENABLE_PROVIDER_FALLBACK"] == "false"
    assert environment["COLLABORATION_DEV_SESSIONS_JSON"] == ""
    assert value.public_runtime_metadata(database_port=55432, backend_port=58123)["launch_profile"] == "v2"


@pytest.mark.parametrize("acceptance", ["1", "true", "yes", "on", " TRUE "])
def test_v1_acceptance_overrides_every_v2_flag_without_reverting_data_owner(tmp_path, monkeypatch, acceptance):
    value = config(tmp_path, V2_PROFILE)
    environment = value.environment(database_port=55432, backend_port=58123)
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", environment["EXPERIMENTAL_FEATURES"])
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", acceptance)
    assert enabled_flags() == frozenset()
    for flag in V2_FEATURES:
        with pytest.raises(HTTPException) as rejected:
            require_flag(flag)
        assert rejected.value.status_code == 404
    assert environment[PROFILE_ENV] == V2_PROFILE
    assert V2_DIRECTORY in value.paths.database.parts


def test_v2_state_owners_are_disjoint_and_keep_webview_shape(tmp_path, monkeypatch):
    original, v2 = config(tmp_path), config(tmp_path, V2_PROFILE)
    original.paths.user_data.mkdir(parents=True)
    marker = original.paths.user_data / "untouched.txt"
    marker.write_text("original data")
    for old in asdict(original.paths).values():
        for new in asdict(v2.paths).values():
            assert old != new and old not in new.parents and new not in old.parents
    assert v2.paths.cache.parts[-2:] == ("AI-Novel-Studio", "Cache")
    assert marker.read_text() == "original data"
    assert not v2.paths.user_data.exists(), "configuration must not create user data"
    environment = v2.environment(database_port=55432, backend_port=58123)
    for name, value in environment.items():
        monkeypatch.setenv(name, value)
    from app.stable_identity import _canonical_host_data_root
    from app import asset_provider_config, audio_provider_config, asset_worker_config
    assert _canonical_host_data_root("nt") == v2.paths.user_data
    assert asset_provider_config.config_path() == v2.paths.config / "asset-providers.json"
    assert audio_provider_config.config_path() == v2.paths.config / "audio-providers.json"
    assert asset_worker_config.config_path() == v2.paths.config / "asset-worker.json"


@pytest.mark.parametrize("field", list(WindowsPackagingPaths.__dataclass_fields__))
def test_v2_rejects_any_mixed_original_path_owner(tmp_path, field):
    original, v2 = config(tmp_path), config(tmp_path, V2_PROFILE)
    mixed = replace(v2.paths, **{field: getattr(original.paths, field)})
    with pytest.raises(ValueError):
        validate_profile_paths(V2_PROFILE, mixed)
    with pytest.raises(ValueError):
        replace(v2, paths=mixed)


def test_linked_v2_root_never_aliases_original_storage(tmp_path):
    local = tmp_path / "Local"
    local.mkdir()
    old = local / "AI-Novel-Studio"
    old.mkdir()
    (local / V2_DIRECTORY).symlink_to(old, target_is_directory=True)
    with pytest.raises(ValueError, match="PACKAGED_V2_LINKED_PATH"):
        resolve_profile_paths(V2_PROFILE, local_app_data=local, user_profile=tmp_path / "User")


def test_late_linked_data_owner_is_rejected_before_backend_or_postgres(tmp_path, monkeypatch):
    value = config(tmp_path, V2_PROFILE)
    value.paths.user_data.mkdir(parents=True)
    target = tmp_path / "v1-database"
    target.mkdir()
    value.paths.database.symlink_to(target, target_is_directory=True)
    factory = processes.PackagedProcessFactory(value, object())
    monkeypatch.setattr(factory, "_start_postgres", lambda *a: pytest.fail("postgres launched"))
    with pytest.raises(ValueError, match="PACKAGED_V2_LINKED_PATH"):
        factory.start(RuntimeRole.POSTGRESQL, 55432, object(), value.paths)


def test_windows_reparse_attribute_is_rejected_without_windows_api(tmp_path, monkeypatch):
    local = tmp_path / "Local"
    flagged = local / V2_DIRECTORY
    original = Path.lstat
    def controlled(path):
        if path == flagged:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        return original(path)
    monkeypatch.setattr(Path, "lstat", controlled)
    with pytest.raises(ValueError, match="PACKAGED_V2_LINKED_PATH"):
        resolve_profile_paths(V2_PROFILE, local_app_data=local, user_profile=tmp_path / "User")


def test_v2_factory_refuses_original_paths_before_layout_or_process_creation(tmp_path, monkeypatch):
    monkeypatch.setattr(processes.PackagedRuntimeLayout, "resolve", lambda *a: pytest.fail("runtime inspected"))
    with pytest.raises(ValueError, match="PACKAGED_V2_ISOLATED_ROOT_REQUIRED"):
        launcher.create_packaged_backend_runtime(paths=config(tmp_path).paths, launch_profile=V2_PROFILE)


@pytest.mark.parametrize("profile", [DEFAULT_PROFILE, V2_PROFILE])
def test_original_factory_lifecycle_and_profile_specific_mutex_are_reused(tmp_path, monkeypatch, profile):
    value = config(tmp_path, profile)
    seen = []
    monkeypatch.setattr(processes.PackagedProcessConfig, "create", lambda app, paths, **kw:
                        seen.append((app, paths, kw)) or value)
    monkeypatch.setattr(launcher, "WindowsNamedMutex", lambda name: name)
    runtime, factory = launcher.create_packaged_backend_runtime(application=value.layout.application,
        paths=value.paths, launch_profile=profile, job=object(), inspector=object(), port_allocator=object())
    assert seen == [(value.layout.application, value.paths, {"launch_profile": profile})]
    assert isinstance(factory, processes.PackagedProcessFactory)
    assert runtime.process_factory is factory
    assert runtime.startup_order == (RuntimeRole.POSTGRESQL, RuntimeRole.BACKEND)
    assert runtime.paths == value.paths
    assert (V2_DIRECTORY in runtime.mutex) == (profile == V2_PROFILE)


@pytest.mark.parametrize("profile", [DEFAULT_PROFILE, V2_PROFILE])
def test_backend_process_gets_only_launcher_selected_profile_and_existing_bootstrap(tmp_path, monkeypatch, profile):
    value = config(tmp_path, profile)
    monkeypatch.setenv(PROFILE_ENV, "unknown-inherited-profile")
    monkeypatch.setenv("EXPERIMENTAL_FEATURES", "*")
    monkeypatch.setenv("COLLABORATION_DEV_SESSIONS_JSON", "must-not-inherit")
    monkeypatch.setenv("CREDENTIAL_VAULT_BACKEND", "memory")
    monkeypatch.setenv("CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK", "true")
    monkeypatch.setenv("V1_ACCEPTANCE_MODE", "true")
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "original-asset-config"))
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-only-forbidden-key")
    captured = []
    monkeypatch.setattr(processes.subprocess, "Popen", lambda argv, **kw: captured.append((argv, kw)) or object())
    monkeypatch.setattr(processes, "PackagedManagedChild", lambda **kw: kw)
    # Unit-only bootstrap value stays inside the captured environment, not a real registry.
    monkeypatch.setattr(processes.secrets, "token_urlsafe", lambda size: "unit-only-bootstrap")
    factory = processes.PackagedProcessFactory(value, object())
    factory.database_port = 55432
    factory._start_backend(58123, SimpleNamespace(runtime_instance_id="unit-runtime"))
    argv, kwargs = captured[0]
    kwargs["stdout"].close()
    environment = kwargs["env"]
    assert environment.get(PROFILE_ENV) == (V2_PROFILE if profile == V2_PROFILE else None)
    assert environment["PACKAGED_RUNTIME_INSTANCE_ID"] == "unit-runtime"
    assert environment["PACKAGED_BOOTSTRAP_SECRET"] == "unit-only-bootstrap"
    assert environment["CREDENTIAL_VAULT_BACKEND"] == "auto"
    assert environment["CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK"] == "false"
    assert environment["COLLABORATION_DEV_SESSIONS_JSON"] == ""
    assert "DEEPSEEK_API_KEY" not in environment
    assert environment["V1_ACCEPTANCE_MODE"] == "true"
    if profile == V2_PROFILE:
        assert environment["ASSET_PROVIDER_CONFIG_PATH"] == str(value.paths.config / "asset-providers.json")
    assert argv[1:5] == ["-B", "-I", "-m", "uvicorn"]
    assert argv[argv.index("--host") + 1] == "127.0.0.1"
    assert factory.take_bootstrap_secret() == "unit-only-bootstrap"
    with pytest.raises(RuntimeError, match="unavailable"):
        factory.take_bootstrap_secret()


@pytest.mark.parametrize("profile", ["unknown", "V2", "*", "../default"])
def test_desktop_cli_rejects_unknown_profile_before_runtime(tmp_path, monkeypatch, profile):
    monkeypatch.setattr(sys, "argv", ["desktop", "--profile", profile])
    monkeypatch.setattr(desktop, "create_packaged_backend_runtime", lambda **kw: pytest.fail("runtime reached"))
    with pytest.raises(SystemExit) as rejected:
        desktop.main()
    assert rejected.value.code == 2


@pytest.mark.parametrize("stop", [False, True])
def test_v2_cli_propagates_profile_and_uses_original_close_restart_contract(tmp_path, monkeypatch, capsys, stop):
    from test_packaged_native_rc_lifecycle import launcher_fixture
    for attempt in range(2):
        events, children = launcher_fixture(tmp_path, monkeypatch, requested_stop=stop)
        create = desktop.create_packaged_backend_runtime
        seen = []
        monkeypatch.setattr(desktop, "create_packaged_backend_runtime", lambda **kw: seen.append(kw) or create(**kw))
        monkeypatch.setattr(sys, "argv", ["desktop", "--profile", "v2", "--application-root", str(tmp_path / "Application"),
            "--local-app-data", str(tmp_path / "Local"), "--user-profile", str(tmp_path / "User")])
        assert desktop.main() == 0
        assert seen[0]["launch_profile"] == V2_PROFILE
        validate_profile_paths(V2_PROFILE, seen[0]["paths"])
        assert children[0].poll() is not None
        assert events[-3:] == ["host.block_actions", "host.close", "runtime.shutdown"]
        assert "unit-only-bootstrap" not in capsys.readouterr().out


def test_powershell_selector_is_finite_and_does_not_shadow_user_profile():
    source = (Path(__file__).resolve().parents[1] / "scripts/installer/Launch-AI-Novel-Studio.ps1").read_text()
    assert "[ValidateSet('default', 'v2')]" in source
    assert "[Alias('Profile')]" in source
    assert "[string]$LaunchProfile = 'default'" in source
    assert "if ($LaunchProfile -eq 'v2') { $launcherArgs += @('--profile', 'v2') }" in source
    assert "'--user-profile', $profile" in source
