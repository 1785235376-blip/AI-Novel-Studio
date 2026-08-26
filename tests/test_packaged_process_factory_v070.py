from __future__ import annotations

import json
import signal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.packaging.packaged_processes import (
    DATABASE_INVALID,
    RUNTIME_INCOMPLETE,
    PackagedProcessConfig,
    PackagedRuntimeLayout,
    initialize_cluster,
)
from app.packaging.packaged_launcher import _install_stop_handlers
from app.packaging.paths import WindowsPackagingPaths
from app.packaging.runtime_identity import RuntimeRole
from app.packaging.runtime_lifecycle import RuntimeLifecycle


TOOLS = (
    "initdb.exe", "postgres.exe", "pg_ctl.exe", "pg_isready.exe",
    "pg_dump.exe", "pg_restore.exe", "psql.exe", "createdb.exe",
)


def layout(tmp_path: Path) -> Path:
    root = tmp_path / "AI 小说 Studio Test" / "Application"
    (root / "Runtime/Python").mkdir(parents=True)
    (root / "Runtime/Python/python.exe").write_bytes(b"python")
    (root / "Backend/app").mkdir(parents=True)
    (root / "Backend/app/main.py").write_text("", encoding="utf-8")
    (root / "Frontend/dist/assets").mkdir(parents=True)
    (root / "Frontend/dist/index.html").write_text(
        '<script type="module" src="/assets/index.js"></script>', encoding="utf-8",
    )
    (root / "Frontend/dist/assets/index.js").write_text("export {};", encoding="utf-8")
    (root / "PostgreSQL/bin").mkdir(parents=True)
    for name in TOOLS:
        (root / "PostgreSQL/bin" / name).write_bytes(b"tool")
    (root / "release").mkdir()
    (root / "release/version.json").write_text(
        json.dumps({"product":"AI-Novel-Studio","version":"0.7.0","channel":"beta","display_version":"0.7.0 Beta"}),
        encoding="utf-8",
    )
    return root


def paths(tmp_path: Path) -> WindowsPackagingPaths:
    return WindowsPackagingPaths.resolve(
        local_app_data=tmp_path / "Local App 数据", user_profile=tmp_path / "User Name",
    )


def test_missing_packaged_python_fails_closed_without_system_fallback(tmp_path, monkeypatch):
    root = layout(tmp_path); (root / "Runtime/Python/python.exe").unlink()
    monkeypatch.setenv("PATH", str(tmp_path / "system-python"))
    with pytest.raises(RuntimeError, match="应用运行组件不完整"):
        PackagedRuntimeLayout.resolve(root)


def test_wrong_python_or_postgres_version_fails_closed(tmp_path, monkeypatch):
    root = layout(tmp_path)
    monkeypatch.setattr("app.packaging.packaged_processes._run", lambda *a, **k: SimpleNamespace(stdout="(3, 11)", returncode=0))
    with pytest.raises(RuntimeError, match="应用运行组件不完整"):
        PackagedRuntimeLayout.resolve(root)


def test_packaged_config_uses_only_approved_paths_and_loopback(tmp_path, monkeypatch):
    root = layout(tmp_path)
    outputs = iter(("(3, 12)", "postgres (PostgreSQL) 16.4"))
    monkeypatch.setattr("app.packaging.packaged_processes._run", lambda *a, **k: SimpleNamespace(stdout=next(outputs), returncode=0))
    config = PackagedProcessConfig.create(root, paths(tmp_path))
    env = config.environment(database_port=55432, backend_port=58123)
    assert env["DATABASE_URL"] == "postgresql://novel_studio@127.0.0.1:55432/ai_novel_studio"
    assert env["PACKAGED_WINDOWS_MODE"] == "true"
    assert env["COLLABORATION_DEV_SESSIONS_JSON"] == ""
    assert "DEEPSEEK" not in json.dumps(env)
    assert str(root / "Runtime/Python/python.exe") not in env.values()


def test_public_metadata_contains_no_security_material(tmp_path, monkeypatch):
    root = layout(tmp_path)
    outputs = iter(("(3, 12)", "postgres (PostgreSQL) 16.4"))
    monkeypatch.setattr("app.packaging.packaged_processes._run", lambda *a, **k: SimpleNamespace(stdout=next(outputs), returncode=0))
    value = PackagedProcessConfig.create(root, paths(tmp_path)).public_runtime_metadata(database_port=1, backend_port=2)
    text = json.dumps(value)
    assert all(word not in text for word in ("secret", "session", "nonce", "DEEPSEEK"))


def test_existing_cluster_is_preserved_and_invalid_cluster_fails_closed(tmp_path, monkeypatch):
    root = layout(tmp_path); data = tmp_path / "数据库 数据"
    data.mkdir(); marker = data / "novel.keep"; marker.write_text("keep")
    config = SimpleNamespace(layout=SimpleNamespace(postgres_bin=root / "PostgreSQL/bin"), database_user="novel_studio")
    with pytest.raises(RuntimeError, match="本地数据库无法安全启动"):
        initialize_cluster(config, data)
    assert marker.read_text() == "keep"
    (data / "PG_VERSION").write_text("16", encoding="ascii")
    assert initialize_cluster(config, data) is False
    assert marker.read_text() == "keep"


def test_first_cluster_initialization_uses_bundled_initdb_and_loopback(tmp_path, monkeypatch):
    root = layout(tmp_path); data = tmp_path / "数据库 数据"; calls=[]
    config = SimpleNamespace(layout=SimpleNamespace(postgres_bin=root / "PostgreSQL/bin"), database_user="novel_studio")
    def run(args, **_):
        calls.append([str(x) for x in args]); data.mkdir(parents=True); (data / "postgresql.conf").write_text("", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="")
    monkeypatch.setattr("app.packaging.packaged_processes._run", run)
    assert initialize_cluster(config, data) is True
    assert calls[0][0] == str(root / "PostgreSQL/bin/initdb.exe")
    assert "--auth-host" in calls[0]
    assert "listen_addresses = '127.0.0.1'" in (data / "postgresql.conf").read_text()


def test_runtime_lifecycle_accepts_postgres_backend_subset(tmp_path):
    lifecycle = RuntimeLifecycle(
        paths=SimpleNamespace(runtime=tmp_path), mutex=SimpleNamespace(), job=SimpleNamespace(),
        port_allocator=SimpleNamespace(), process_factory=SimpleNamespace(),
        inspector=SimpleNamespace(), startup_order=(RuntimeRole.POSTGRESQL, RuntimeRole.BACKEND),
    )
    assert lifecycle.startup_order == (RuntimeRole.POSTGRESQL, RuntimeRole.BACKEND)
    assert lifecycle.shutdown_order == (RuntimeRole.BACKEND, RuntimeRole.POSTGRESQL)


def test_runtime_lifecycle_rejects_duplicate_role_subset(tmp_path):
    with pytest.raises(ValueError):
        RuntimeLifecycle(
            paths=SimpleNamespace(runtime=tmp_path), mutex=SimpleNamespace(), job=SimpleNamespace(),
            port_allocator=SimpleNamespace(), process_factory=SimpleNamespace(),
            inspector=SimpleNamespace(), startup_order=(RuntimeRole.POSTGRESQL, RuntimeRole.POSTGRESQL),
        )


def test_packaged_launcher_registers_windows_break_for_graceful_shutdown(monkeypatch):
    registered = []
    monkeypatch.setattr("app.packaging.packaged_launcher.signal.signal", lambda value, handler: registered.append((value, handler)))
    handler = object()

    _install_stop_handlers(handler)

    expected = [signal.SIGINT, signal.SIGTERM]
    if hasattr(signal, "SIGBREAK"):
        expected.append(signal.SIGBREAK)
    assert registered == [(value, handler) for value in expected]


def test_backend_process_group_can_receive_windows_break(tmp_path, monkeypatch):
    root = layout(tmp_path)
    outputs = iter(("(3, 12)", "postgres (PostgreSQL) 16.4"))
    monkeypatch.setattr("app.packaging.packaged_processes._run", lambda *a, **k: SimpleNamespace(stdout=next(outputs), returncode=0))
    config = PackagedProcessConfig.create(root, paths(tmp_path))
    factory = __import__("app.packaging.packaged_processes", fromlist=["PackagedProcessFactory"]).PackagedProcessFactory(
        config, SimpleNamespace(register=lambda *a: None, inspect=lambda pid: SimpleNamespace(executable_path=str(root / "Runtime/Python/python.exe")))
    )
    factory.database_port = 55432
    captured = {}
    process = SimpleNamespace(pid=123, send_signal=lambda value: captured.setdefault("signal", value))
    monkeypatch.setattr("app.packaging.packaged_processes.subprocess.Popen", lambda *a, **k: captured.update(k) or process)
    monkeypatch.setattr("app.packaging.packaged_processes.PackagedManagedChild", lambda **kwargs: kwargs)

    child = factory._start_backend(58123, SimpleNamespace(runtime_instance_id="runtime-a"))

    assert captured["creationflags"] == getattr(__import__("subprocess"), "CREATE_NEW_PROCESS_GROUP", 0)
    assert not captured["creationflags"] & getattr(__import__("subprocess"), "CREATE_NO_WINDOW", 0)
    child["graceful"]()
    assert captured["signal"] == getattr(__import__("subprocess"), "CTRL_BREAK_EVENT", 1)
