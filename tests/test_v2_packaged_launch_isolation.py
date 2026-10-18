"""Read-only import probes and process-boundary doubles, not native Host proof."""
from __future__ import annotations

import io
import hashlib
from dataclasses import replace
import os
from pathlib import Path
import subprocess
import sys
import stat
from types import SimpleNamespace

import pytest

from windows_test_support import symlink_or_skip

from app.packaged_profile import DEFAULT_PROFILE, V2_PROFILE
from app.packaging import packaged_desktop_host as host_module
from app.packaging import launch_profiles
from app.packaging.desktop_bridge import DesktopHostLaunch
from app.packaging.launch_profiles import validate_profile_paths
from test_v2_packaged_launch_profile import config


@pytest.mark.parametrize("relative", [
    "UserData/identity-foundation.json", "UserData/identity-foundation.json.lock",
    "Config/asset-providers.json", "Config/audio-providers.json", "Config/asset-worker.json",
    "Cache/WebView2", "UserData/NovelData/nested/document.json",
])
def test_linked_files_or_nested_dirs_cannot_alias_v1_state(tmp_path, relative):
    value = config(tmp_path, V2_PROFILE)
    old = tmp_path / "original-state"
    directory = relative == "Cache/WebView2"
    if directory:
        old.mkdir()
    else:
        old.write_text("original state")
    link = value.paths.user_data.parent / relative
    link.parent.mkdir(parents=True, exist_ok=True)
    symlink_or_skip(link, old, target_is_directory=directory)
    with pytest.raises(ValueError, match="PACKAGED_V2_LINKED_PATH"):
        validate_profile_paths(V2_PROFILE, value.paths)
    if not directory:
        assert old.read_text() == "original state"


@pytest.mark.parametrize("relative", ["UserData/identity-foundation.json", "Config/asset-providers.json",
                                      "UserData/NovelData/document.json"])
def test_hardlinked_v2_files_are_rejected_without_reading_or_changing_original(tmp_path, relative):
    value = config(tmp_path, V2_PROFILE)
    original = tmp_path / "original-data.json"
    original.write_text("original data")
    linked = value.paths.user_data.parent / relative
    linked.parent.mkdir(parents=True, exist_ok=True)
    os.link(original, linked)
    with pytest.raises(ValueError, match="PACKAGED_V2_MULTILINK_FILE"):
        validate_profile_paths(V2_PROFILE, value.paths)
    assert original.read_text() == "original data"
    assert original.stat().st_nlink == 2


@pytest.mark.parametrize("limit", ["entries", "depth", "time"])
def test_v2_tree_validation_fails_closed_at_a_bounded_scan_limit(tmp_path, monkeypatch, limit):
    value = config(tmp_path, V2_PROFILE)
    folder = value.paths.user_data / "nested" / "deeper"
    folder.mkdir(parents=True)
    (folder / "safe.txt").write_text("safe")
    if limit == "entries":
        monkeypatch.setattr(launch_profiles, "MAX_V2_STATE_ENTRIES", 1)
    elif limit == "depth":
        monkeypatch.setattr(launch_profiles, "MAX_V2_STATE_DEPTH", 1)
    else:
        ticks = iter([0.0, 11.0])
        monkeypatch.setattr(launch_profiles, "monotonic", lambda: next(ticks))
    with pytest.raises(ValueError, match="PACKAGED_V2_STATE_SCAN_LIMIT"):
        validate_profile_paths(V2_PROFILE, value.paths)


def test_v1_path_resolution_does_not_apply_v2_link_or_scan_policy(tmp_path):
    original = config(tmp_path)
    original.paths.config.mkdir(parents=True)
    elsewhere = tmp_path / "existing-default-config"
    elsewhere.write_text("existing behavior")
    symlink_or_skip(original.paths.config / "asset-providers.json", elsewhere)
    validate_profile_paths(DEFAULT_PROFILE, original.paths)
    assert config(tmp_path).paths == original.paths


@pytest.mark.parametrize("variation", ["exact", "wrong-target", "wrong-digest", "wrong-name", "state-root", "symbolic-link"])
@pytest.mark.parametrize("same_base", [False, True])
def test_only_exact_original_unicode_postgres_executable_junction_is_allowed(tmp_path, monkeypatch, variation, same_base):
    value = config(tmp_path, V2_PROFILE)
    user_base = tmp_path / ("Local" if same_base else "User")
    if same_base:
        value = replace(value, paths=launch_profiles.resolve_profile_paths(V2_PROFILE,
            local_app_data=tmp_path / "Local", user_profile=user_base))
    target = tmp_path / "中文安装" / "Application" / "PostgreSQL"
    target.mkdir(parents=True)
    digest = hashlib.sha256(str(target.resolve()).encode("utf-8")).hexdigest()[:12]
    alias = value.paths.runtime / f"PostgreSQL-{digest}"
    if variation == "wrong-digest":
        alias = value.paths.runtime / "PostgreSQL-000000000000"
    elif variation == "wrong-name":
        alias = value.paths.runtime / f"Other-{digest}"
    elif variation == "state-root":
        alias = value.paths.user_data / f"PostgreSQL-{digest}"
    alias.mkdir(parents=True)
    actual_target = tmp_path / "v1-data" if variation == "wrong-target" else target
    actual_target.mkdir(exist_ok=True)
    # Simulated junction metadata only. No native junction/Windows API is used.
    original_lstat, original_resolve = Path.lstat, Path.resolve
    def lstat(path):
        if path == alias:
            return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400, st_nlink=1)
        return original_lstat(path)
    def resolve(path, *args, **kwargs):
        return actual_target if path == alias else original_resolve(path, *args, **kwargs)
    monkeypatch.setattr(Path, "lstat", lstat)
    monkeypatch.setattr(Path, "resolve", resolve)
    monkeypatch.setattr(os.path, "isjunction", lambda path: Path(path) == alias and variation != "symbolic-link", raising=False)
    if variation == "exact":
        validate_profile_paths(V2_PROFILE, value.paths, postgres_root=target)
        # The resolver must also tolerate a pre-existing valid runtime alias on
        # restart; full target-aware validation remains the config owner's job.
        assert launch_profiles.resolve_profile_paths(V2_PROFILE, local_app_data=tmp_path / "Local",
            user_profile=user_base) == value.paths
    else:
        with pytest.raises(ValueError, match="PACKAGED_V2_LINKED_PATH"):
            validate_profile_paths(V2_PROFILE, value.paths, postgres_root=target)


@pytest.mark.parametrize("ambient_profile", ["default", "v2", "unknown"])
def test_fresh_launcher_import_and_help_never_import_or_initialize_vault(tmp_path, ambient_profile):
    root = Path(__file__).resolve().parents[1]
    script = """
import importlib.abc, sys
class DenyVault(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, *args):
        if fullname == 'app.credential_vault':
            raise RuntimeError('launcher tried to initialize a vault')
sys.meta_path.insert(0, DenyVault())
from app.packaging import packaged_desktop_launcher as launcher
assert 'app.credential_vault' not in sys.modules
sys.argv = ['packaged-desktop', '--profile', 'v2', '--help']
try:
    launcher.main()
except SystemExit as error:
    assert error.code == 0
else:
    raise AssertionError('help did not exit')
assert 'app.credential_vault' not in sys.modules
"""
    environment = {**os.environ, "AI_NOVEL_PACKAGED_PROFILE": ambient_profile,
                   "CREDENTIAL_VAULT_BACKEND": "keyring", "ENABLE_PACKAGED_RUNTIME": "false",
                   "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-B", "-c", script], cwd=root, env=environment,
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


def host(tmp_path, monkeypatch, profile):
    value = config(tmp_path, profile)
    executable = value.layout.application / "DesktopHost" / "AI-Novel-Studio.DesktopHost.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"not an executable; process boundary is mocked")
    runtime = SimpleNamespace(runtime_instance_id="unit-runtime")
    captures = []
    process = SimpleNamespace(pid=4242, stdin=io.StringIO(), stdout=io.StringIO(), stderr=io.StringIO())
    monkeypatch.setattr(host_module.subprocess, "Popen", lambda args, **kwargs: captures.append(kwargs) or process)
    monkeypatch.setattr(host_module, "validate_process_ownership", lambda *a: None)
    monkeypatch.setattr(host_module.threading, "Thread", lambda **kw: SimpleNamespace(start=lambda: None))
    inspector = SimpleNamespace(register=lambda *a: None, inspect=lambda pid: object())
    job = SimpleNamespace(assign_pid=lambda pid: None)
    result = host_module.PackagedDesktopHost(application=value.layout.application, runtime=runtime,
        inspector=inspector, job=job, launch_profile=profile, paths=value.paths if profile == V2_PROFILE else None)
    launch = DesktopHostLaunch("http://127.0.0.1:58123", "http://127.0.0.1:58123", "unit-runtime",
        "unit-only-bootstrap", str(value.paths.cache / "WebView2" / "unit-runtime"))
    return value, result, launch, captures


@pytest.mark.parametrize("profile", [DEFAULT_PROFILE, V2_PROFILE])
def test_webview_child_profile_defeats_ambient_storage_override_only_for_v2(tmp_path, monkeypatch, profile):
    value, instance, launch, captures = host(tmp_path, monkeypatch, profile)
    poisoned = {
        "WEBVIEW2_USER_DATA_FOLDER": str(tmp_path / "v1-cache"),
        "WEBVIEW2_BROWSER_EXECUTABLE_FOLDER": str(tmp_path / "unexpected-browser"),
        "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": "--remote-debugging-port=9876",
        "WEBVIEW2_PIPE_FOR_SCRIPT_DEBUGGER": "unexpected-debugger",
    }
    for name, val in poisoned.items():
        monkeypatch.setenv(name, val)
    instance.start(launch)
    environment = captures[0]["env"]
    if profile == V2_PROFILE:
        assert environment["WEBVIEW2_USER_DATA_FOLDER"] == launch.webview_profile_directory
        assert all(name not in environment for name in poisoned if name != "WEBVIEW2_USER_DATA_FOLDER")
    else:
        assert {name: environment[name] for name in poisoned} == poisoned
    assert environment["PACKAGED_HOST_WEBVIEW_ROOT"] == str(value.paths.cache / "WebView2")
    assert not (tmp_path / "v1-cache").exists()


def test_v2_host_rejects_mismatched_webview_owner_before_files_or_processes(tmp_path, monkeypatch):
    value, instance, launch, captures = host(tmp_path, monkeypatch, V2_PROFILE)
    mismatched = DesktopHostLaunch(launch.frontend_origin, launch.backend_origin, launch.runtime_instance_id,
                                   launch.bootstrap_secret, str(tmp_path / "original-cache"))
    with pytest.raises(ValueError, match="PACKAGED_V2_WEBVIEW_OWNER_MISMATCH"):
        instance.start(mismatched)
    assert captures == []
    assert not value.paths.cache.exists()
    assert not (tmp_path / "original-cache").exists()


def test_ping_framing_reuses_exact_original_wire_and_export():
    from app.packaging.control_pipe import encode_ping as original
    from app.packaging.host_uplink import encode_ping as pure
    assert original is pure
    assert pure("unit-runtime") == b'{"protocol":"packaged-control/v1","type":"ping","runtime_instance_id":"unit-runtime"}\n'
