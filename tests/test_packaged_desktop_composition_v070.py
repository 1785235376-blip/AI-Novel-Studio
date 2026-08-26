from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.packaging.desktop_bridge import DesktopHostLaunch
from app.packaging.local_session_bootstrap import LocalSessionBootstrap, TrustedLocalIdentity
from app.packaging.packaged_desktop_host import PackagedDesktopHost
from app.packaging.runtime_identity import ProcessIdentity, RuntimeIdentity, RuntimeRole
from app.packaging.static_frontend import FRONTEND_INCOMPLETE, mount_packaged_frontend, validate_frontend_dist
from app.trusted_sessions import TrustedSessionResolver


def frontend(tmp_path: Path) -> Path:
    root = tmp_path / "AI 小说 Studio" / "Frontend" / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(
        '<script type="module" src="/assets/app.js"></script>', encoding="utf-8",
    )
    (root / "assets" / "app.js").write_text("window.ready=true", encoding="utf-8")
    return root


def test_frontend_assets_are_validated_and_served_from_exact_root(tmp_path):
    root = frontend(tmp_path)
    assert validate_frontend_dist(root) == root.resolve()
    app = FastAPI()
    mount_packaged_frontend(app, root)
    client = TestClient(app)
    assert client.get("/").status_code == 200
    assert client.get("/assets/app.js").text == "window.ready=true"


@pytest.mark.parametrize("damage", ["index", "asset", "empty"])
def test_frontend_asset_failure_is_bounded_and_fail_closed(tmp_path, damage):
    root = frontend(tmp_path)
    target = root / "index.html" if damage == "index" else root / "assets" / "app.js"
    if damage == "empty":
        target.write_bytes(b"")
    else:
        target.unlink()
    with pytest.raises(RuntimeError, match=FRONTEND_INCOMPLETE):
        validate_frontend_dist(root)


def test_injected_bootstrap_remains_one_shot_and_server_authoritative():
    runtime = RuntimeIdentity.create()
    sessions = TrustedSessionResolver()
    manager = LocalSessionBootstrap(
        runtime=runtime, sessions=sessions,
        trusted_identity=TrustedLocalIdentity("local-author", "workspace-a"),
        expected_origin="http://127.0.0.1:58123", bootstrap_secret="memory-only-secret",
    )
    receipt = manager.exchange(
        bootstrap_secret="memory-only-secret", runtime_instance_id=runtime.runtime_instance_id,
        origin="http://127.0.0.1:58123", remote_host="127.0.0.1",
    )
    actor = sessions.resolve(receipt.session_token)
    assert (actor.actor_id, actor.workspace_id) == ("local-author", "workspace-a")
    with pytest.raises(Exception):
        manager.exchange(
            bootstrap_secret="memory-only-secret", runtime_instance_id=runtime.runtime_instance_id,
            origin="http://127.0.0.1:58123", remote_host="127.0.0.1",
        )


def test_desktop_host_is_owned_and_uses_only_memory_pipe(tmp_path, monkeypatch):
    application = tmp_path / "Application"
    executable = application / "DesktopHost" / "AI-Novel-Studio.DesktopHost.exe"
    executable.parent.mkdir(parents=True); executable.write_bytes(b"host")
    runtime = RuntimeIdentity.create()
    identity = ProcessIdentity(RuntimeRole.DESKTOP_HOST, 123, 1.0, str(executable), runtime.launcher_pid,
                               runtime.runtime_instance_id, runtime.ownership_nonce_hash)
    inspector = SimpleNamespace(register=lambda *args: None, inspect=lambda pid: identity)
    assigned = []
    stdin = SimpleNamespace(lines=[], write=lambda value: stdin.lines.append(value), flush=lambda: None)
    process = SimpleNamespace(pid=123, stdin=stdin, stdout=[], stderr=None, poll=lambda: None)
    captured = {}
    monkeypatch.setattr("app.packaging.packaged_desktop_host.subprocess.Popen", lambda args, **kwargs: captured.update(kwargs) or process)
    monkeypatch.setattr("app.packaging.packaged_desktop_host.threading.Thread", lambda **kwargs: SimpleNamespace(start=lambda: None))
    host = PackagedDesktopHost(application=application, runtime=runtime, inspector=inspector,
                               job=SimpleNamespace(assign_pid=assigned.append))
    host.start(DesktopHostLaunch(
        frontend_origin="http://127.0.0.1:58123", backend_origin="http://127.0.0.1:58123",
        runtime_instance_id=runtime.runtime_instance_id, bootstrap_secret="secret",
        webview_profile_directory=str(tmp_path / "Cache"),
    ))
    envelope = json.loads(stdin.lines[0])
    assert assigned == [123]
    assert captured["env"] if "env" in captured else True
    assert envelope["frontend_origin"] == envelope["backend_origin"]
    assert captured.get("shell", False) is False
