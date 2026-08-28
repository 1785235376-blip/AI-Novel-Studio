from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import v1_capability_service
from app.main import app
from app.plugin_contracts import (
    MAX_RESOURCE_BYTES,
    MAX_RESOURCE_COUNT,
    PLUGIN_ID_DUPLICATE,
    PLUGIN_MANIFEST_INVALID,
    PLUGIN_RESOURCE_HASH_MISMATCH,
    PLUGIN_RESOURCE_INVALID_JSON,
    PLUGIN_RESOURCE_PATH_INVALID,
    PLUGIN_RESOURCE_SYMLINK_REJECTED,
    PLUGIN_RESOURCE_TOO_LARGE,
    PLUGIN_RESOURCE_TYPE_UNSUPPORTED,
    PluginContractError,
)
from app.plugin_discovery import discover_installed_plugins, load_plugin_package, verify_resource
from app.release_readiness import build_release_readiness
from app.services.v1_capability_service import PluginManifestIn, PluginPermissionIn


REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "plugins" / "story-workflow-pack"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(raw)
    return raw


def _resource(kind: str, relative: str, data: bytes, **extra) -> dict:
    body = {
        "kind": kind,
        "relative_path": relative,
        "sha256": _sha(data),
        "media_type": "application/json",
        "schema_version": "1.0",
    }
    body.update(extra)
    return body


def write_plugin(root: Path, plugin_id: str, *, resources: list[tuple[str, str, dict]] | None = None,
                 manifest_extra: dict | None = None, raw_manifest: dict | None = None) -> Path:
    plugin = root / plugin_id
    plugin.mkdir(parents=True, exist_ok=True)
    declared = []
    for kind, relative, payload in resources or []:
        data = _write_json(plugin / Path(*relative.split("/")), payload)
        declared.append(_resource(kind, relative, data))
    if raw_manifest is not None:
        (plugin / "manifest.json").write_text(json.dumps(raw_manifest), encoding="utf-8")
        return plugin
    manifest = {
        "id": plugin_id,
        "name": plugin_id,
        "version": "1.0.0",
        "capabilities": ["writing_tool"],
        "requested_permissions": [],
        "resources": declared,
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return plugin


@pytest.fixture
def plugin_root(tmp_path):
    original_root = v1_capability_service.root
    original_data = settings.novel_data
    object.__setattr__(settings, "novel_data", tmp_path)
    v1_capability_service.reconfigure_root(tmp_path)
    root = tmp_path / "plugins"
    root.mkdir()
    try:
        yield root
    finally:
        object.__setattr__(settings, "novel_data", original_data)
        v1_capability_service.reconfigure_root(original_root)


def test_valid_relative_resource_is_verified(plugin_root, tmp_path):
    plugin = write_plugin(plugin_root, "good-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "preset", "schema_version": "1.0"}),
    ])
    manifest, verified = load_plugin_package(plugin)
    assert manifest.id == "good-pack"
    assert verified[0]["sha256"]
    assert verified[0]["data"]["name"] == "preset"


def test_dotdot_traversal_rejected(plugin_root):
    secret = plugin_root.parent / "secret.json"
    secret.write_text("{}", encoding="utf-8")
    plugin = write_plugin(plugin_root, "trav", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    manifest = json.loads((plugin / "manifest.json").read_text())
    manifest["resources"][0]["relative_path"] = "../secret.json"
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PluginContractError) as caught:
        load_plugin_package(plugin)
    assert caught.value.code == PLUGIN_RESOURCE_PATH_INVALID


def test_backslash_and_drive_and_unc_rejected_on_disk(plugin_root):
    plugin = write_plugin(plugin_root, "slashy", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    for bad in ("..\\secret.json", "C:/Windows/file.json", "\\\\server\\share\\a.json"):
        manifest = json.loads((plugin / "manifest.json").read_text())
        manifest["resources"][0]["relative_path"] = bad
        (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        with pytest.raises(PluginContractError) as caught:
            load_plugin_package(plugin)
        assert caught.value.code == PLUGIN_RESOURCE_PATH_INVALID


def test_encoded_traversal_rejected_on_disk(plugin_root):
    plugin = write_plugin(plugin_root, "encoded", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    manifest = json.loads((plugin / "manifest.json").read_text())
    manifest["resources"][0]["relative_path"] = "%2e%2e/secret.json"
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PluginContractError) as caught:
        load_plugin_package(plugin)
    assert caught.value.code == PLUGIN_RESOURCE_PATH_INVALID


def test_symlink_escape_is_rejected(plugin_root, tmp_path):
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret":"nope"}', encoding="utf-8")
    plugin = write_plugin(plugin_root, "linky", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    target = plugin / "resources" / "escape.json"
    if target.exists():
        target.unlink()
    os.symlink(outside, target)
    manifest = json.loads((plugin / "manifest.json").read_text())
    data = b'{"secret":"nope"}'
    manifest["resources"] = [_resource("writing_presets", "resources/escape.json", data)]
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PluginContractError) as caught:
        load_plugin_package(plugin)
    assert caught.value.code == PLUGIN_RESOURCE_SYMLINK_REJECTED


def test_unsupported_type_and_invalid_json_and_hash(plugin_root):
    plugin = write_plugin(plugin_root, "bad-res", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    (plugin / "resources" / "preset.json").write_text("{", encoding="utf-8")
    with pytest.raises(PluginContractError) as caught:
        load_plugin_package(plugin)
    assert caught.value.code in {PLUGIN_RESOURCE_INVALID_JSON, PLUGIN_RESOURCE_HASH_MISMATCH}

    plugin2 = write_plugin(plugin_root, "mismatch", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    manifest = json.loads((plugin2 / "manifest.json").read_text())
    manifest["resources"][0]["sha256"] = "0" * 64
    (plugin2 / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PluginContractError) as caught:
        load_plugin_package(plugin2)
    assert caught.value.code == PLUGIN_RESOURCE_HASH_MISMATCH


def test_oversized_resource(plugin_root):
    plugin = plugin_root / "huge"
    plugin.mkdir()
    payload = b"{" + b'"k":"' + (b"a" * (MAX_RESOURCE_BYTES + 32)) + b'"}'
    rel = plugin / "resources"
    rel.mkdir()
    (rel / "preset.json").write_bytes(payload)
    manifest = {
        "id": "huge", "name": "huge", "version": "1.0.0",
        "resources": [_resource("writing_presets", "resources/preset.json", payload)],
    }
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PluginContractError) as caught:
        load_plugin_package(plugin)
    assert caught.value.code == PLUGIN_RESOURCE_TOO_LARGE


def test_resource_count_limit(plugin_root, monkeypatch):
    import app.plugin_contracts as contracts
    import app.plugin_discovery as discovery
    monkeypatch.setattr(contracts, "MAX_RESOURCE_COUNT", 2)
    monkeypatch.setattr(discovery, "MAX_RESOURCE_COUNT", 2)
    resources = [
        ("writing_presets", f"resources/p{i}.json", {"i": i})
        for i in range(3)
    ]
    plugin = write_plugin(plugin_root, "many", resources=resources)
    with pytest.raises(PluginContractError) as caught:
        load_plugin_package(plugin)
    assert caught.value.code in {PLUGIN_RESOURCE_TOO_LARGE, PLUGIN_MANIFEST_INVALID}


def test_one_bad_plugin_does_not_block_others(plugin_root):
    write_plugin(plugin_root, "good-pack", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    write_plugin(plugin_root, "bad-pack", raw_manifest={"id": "bad", "not-valid": True})
    result = discover_installed_plugins(plugin_root)
    by_dir = {item["plugin_dir"]: item for item in result["items"]}
    assert "manifest" in by_dir["good-pack"]
    assert by_dir["bad-pack"]["error_code"] == PLUGIN_MANIFEST_INVALID
    assert result["execution_supported"] is False
    assert result["isolation"] == "DENY_ALL"


def test_discover_api_hides_absolute_paths_and_raw_exceptions(plugin_root):
    write_plugin(plugin_root, "good-pack", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    broken = plugin_root / "broken"
    broken.mkdir()
    (broken / "manifest.json").write_text("{not json", encoding="utf-8")
    client = TestClient(app)
    response = client.get("/api/plugins/discover")
    assert response.status_code == 200
    body = response.text
    payload = response.json()
    assert str(plugin_root) not in body
    assert str(plugin_root.resolve()) not in body
    assert ":\\" not in body
    assert "Traceback" not in body
    assert "not json" not in body
    assert "JSONDecodeError" not in body
    for item in payload["items"]:
        assert item["path"] in {"good-pack", "broken"}
        assert not os.path.isabs(item["path"])
        if item.get("error_code"):
            assert item["error_code"].startswith("PLUGIN_")
            assert "error" in item
    assert payload["execution_supported"] is False


def test_register_keeps_permissions_empty_and_activation_requires_review(plugin_root):
    plugin_id = f"plug-{uuid4().hex[:8]}"
    write_plugin(plugin_root, plugin_id, manifest_extra={
        "name": "Demo",
        "requested_permissions": ["project.read"],
        "capabilities": ["writing_tool"],
    })
    client = TestClient(app)
    created = client.post("/api/plugins", json=json.loads((plugin_root / plugin_id / "manifest.json").read_text(encoding="utf-8")))
    assert created.status_code == 201
    body = created.json()
    assert body["granted_permissions"] == []
    assert body["execution_supported"] is False
    assert body["plugin_version"] == "1.0.0"
    assert body["version"] == 1
    assert body["manifest_sha256"]
    denied = client.post(f"/api/plugins/{plugin_id}/enable")
    assert denied.status_code == 400
    reviewed = client.put(f"/api/plugins/{plugin_id}/permissions", json={
        "granted_permissions": ["project.read"],
        "reviewed_by": "local-user",
    })
    assert reviewed.status_code == 200
    enabled = client.post(f"/api/plugins/{plugin_id}/enable")
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "MANIFEST_ACTIVE"
    assert enabled.json()["execution_supported"] is False
    assert enabled.json()["plugin_version"] == "1.0.0"


def test_release_readiness_plugin_runtime_stays_deferred(plugin_root):
    from tests.test_release_readiness import Vault, runtime, settings as readiness_settings
    result = build_release_readiness(
        settings=readiness_settings(allow_fallback=False),
        credential_vault=Vault(persistent=True),
        runtime=runtime(),
        image_registry=__import__("types").SimpleNamespace(_providers={"ddshub": object()}),
        packaged_bootstrap=False,
    )
    assert result["checks"]["plugin_runtime"] == {
        "status": "DEFERRED", "execution_supported": False, "isolation": "DENY_ALL",
    }


def test_discovery_does_not_call_subprocess_exec_importlib_or_vault(plugin_root):
    write_plugin(plugin_root, "good-pack", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])

    def boom(*_args, **_kwargs):
        raise AssertionError("forbidden side effect")

    with patch("subprocess.Popen", boom), patch("subprocess.run", boom), \
            patch("os.system", boom), patch("builtins.exec", boom), \
            patch("builtins.eval", boom):
        with patch("app.credential_vault.credential_vault.resolve", boom):
            result = discover_installed_plugins(plugin_root)
    assert result["items"][0]["manifest"]["id"] == "good-pack"


def test_discovery_does_not_perform_network_requests(plugin_root):
    write_plugin(plugin_root, "good-pack", resources=[
        ("writing_presets", "resources/preset.json", {"url": "https://example.invalid/hook"}),
    ])

    def boom(*_args, **_kwargs):
        raise AssertionError("network forbidden")

    with patch("socket.create_connection", boom), patch("httpx.Client.request", boom):
        result = discover_installed_plugins(plugin_root)
    assert result["items"][0]["manifest"]["id"] == "good-pack"


def test_copied_example_discovers_without_path_leak(plugin_root):
    dest = plugin_root / "story-workflow-pack"
    dest.mkdir()
    dest.joinpath("manifest.json").write_bytes((EXAMPLE / "manifest.json").read_bytes())
    resources = dest / "resources"
    resources.mkdir()
    for name in ("writing-preset.json", "workflow-template.json"):
        (resources / name).write_bytes((EXAMPLE / "resources" / name).read_bytes())
    client = TestClient(app)
    payload = client.get("/api/plugins/discover").json()
    item = payload["items"][0]
    assert item["plugin_dir"] == "story-workflow-pack"
    assert item["manifest"]["id"] == "story-workflow-pack"
    assert str(plugin_root) not in json.dumps(payload)
    registered = client.post("/api/plugins", json=item["manifest"])
    assert registered.status_code == 201
    assert registered.json()["granted_permissions"] == []
    assert registered.json()["execution_supported"] is False


def test_duplicate_manifest_ids_are_not_registerable(plugin_root):
    write_plugin(plugin_root, "copy-a", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    write_plugin(plugin_root, "copy-b", resources=[
        ("writing_presets", "resources/preset.json", {"ok": True}),
    ])
    for name in ("copy-a", "copy-b"):
        manifest = json.loads((plugin_root / name / "manifest.json").read_text(encoding="utf-8"))
        manifest["id"] = "shared-tools"
        (plugin_root / name / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    payload = discover_installed_plugins(plugin_root)
    assert len(payload["items"]) == 2
    for item in payload["items"]:
        assert item["error_code"] == PLUGIN_ID_DUPLICATE
        assert "manifest" not in item
        assert "Traceback" not in json.dumps(item)
        assert str(plugin_root) not in json.dumps(item)
        assert ":\\" not in json.dumps(item)
    client = TestClient(app)
    discovered = client.get("/api/plugins/discover").json()
    assert all(item.get("error_code") == PLUGIN_ID_DUPLICATE for item in discovered["items"])
    assert str(plugin_root) not in json.dumps(discovered)
