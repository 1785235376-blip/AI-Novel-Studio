from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import v1_capability_service
from app.main import app
from app.plugin_catalog import plain_text
from app.plugin_contracts import PLUGIN_ID_DUPLICATE, PLUGIN_MANIFEST_DRIFT, PLUGIN_RESOURCE_HASH_MISMATCH


REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "plugins" / "story-workflow-pack"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, payload) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    path.write_bytes(raw)
    return raw


def _resource(kind: str, relative: str, data: bytes) -> dict:
    return {
        "kind": kind,
        "relative_path": relative,
        "sha256": _sha(data),
        "media_type": "application/json",
        "schema_version": "1.0",
    }


def write_plugin(root: Path, plugin_id: str, *, resources: list[tuple[str, str, dict]] | None = None,
                 requested_permissions: list[str] | None = None, version: str = "1.0.0",
                 capabilities: list[str] | None = None) -> Path:
    plugin = root / plugin_id
    plugin.mkdir(parents=True, exist_ok=True)
    declared = []
    for kind, relative, payload in resources or []:
        data = _write_json(plugin / Path(*relative.split("/")), payload)
        declared.append(_resource(kind, relative, data))
    manifest = {
        "id": plugin_id,
        "name": plugin_id,
        "version": version,
        "capabilities": capabilities or ["writing_tool"],
        "requested_permissions": requested_permissions or [],
        "resources": declared,
    }
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


def _client() -> TestClient:
    return TestClient(app)


def _register(client: TestClient, plugin_id: str, *, enable: bool = True, review: bool = True, grant=None):
    manifest = json.loads(((settings.data_path() / "plugins" / plugin_id / "manifest.json")).read_text(encoding="utf-8"))
    created = client.post("/api/plugins", json=manifest)
    assert created.status_code == 201, created.text
    requested = created.json().get("requested_permissions") or []
    if review and (grant is not None or requested):
        reviewed = client.put(f"/api/plugins/{plugin_id}/permissions", json={
            "granted_permissions": grant if grant is not None else requested,
            "reviewed_by": "local-user",
        })
        assert reviewed.status_code == 200, reviewed.text
    if enable:
        enabled = client.post(f"/api/plugins/{plugin_id}/enable")
        assert enabled.status_code == 200, enabled.text
    return created.json()


def test_plain_text_strips_html_and_schemes():
    assert plain_text("<script>alert(1)</script>hello") == "alert(1)hello"
    assert "javascript" not in plain_text("javascript:alert(1)").casefold()
    assert plain_text(12) == ""


def test_active_plugin_resources_are_visible(plugin_root):
    write_plugin(plugin_root, "good-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "节奏", "description": "声明式预设"}),
        ("workflow_templates", "resources/flow.json", {"name": "清单", "schema_version": "1.0"}),
    ])
    client = _client()
    _register(client, "good-pack")
    listed = client.get("/api/plugins/good-pack/resources")
    assert listed.status_code == 200
    body = listed.json()
    assert body["visible"] is True
    assert body["execution_supported"] is False
    assert body["isolation"] == "DENY_ALL"
    assert {item["kind"] for item in body["items"]} == {"writing_presets", "workflow_templates"}
    assert all(item["validated"] is True for item in body["items"])
    assert all(item["plugin_id"] == "good-pack" for item in body["items"])
    detail = client.get("/api/plugins/good-pack/resources/resources:preset.json")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["data"]["name"] == "节奏"
    assert payload["sha256"]
    assert payload["summary"]["sha256_short"] == payload["sha256"][:12]


def test_disabled_plugin_resources_are_hidden(plugin_root):
    write_plugin(plugin_root, "off-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "hidden"}),
    ])
    client = _client()
    _register(client, "off-pack", enable=True)
    disabled = client.post("/api/plugins/off-pack/disable")
    assert disabled.status_code == 200
    listed = client.get("/api/plugins/off-pack/resources")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["visible"] is False
    detail = client.get("/api/plugins/off-pack/resources/resources:preset.json")
    assert detail.status_code == 404


def test_unreviewed_plugin_resources_are_hidden(plugin_root):
    write_plugin(plugin_root, "pending-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "pending"}),
    ], requested_permissions=["project.read"])
    client = _client()
    _register(client, "pending-pack", enable=False, review=False)
    # Register only — permissions still empty, not active.
    listed = client.get("/api/plugins/pending-pack/resources")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["visible"] is False


def test_hash_drift_drops_resource_immediately(plugin_root):
    plugin = write_plugin(plugin_root, "drift-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "original"}),
    ])
    client = _client()
    _register(client, "drift-pack")
    assert client.get("/api/plugins/drift-pack/resources").json()["total"] == 1
    (plugin / "resources" / "preset.json").write_text('{"name":"tampered"}', encoding="utf-8")
    listed = client.get("/api/plugins/drift-pack/resources")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["validated"] is False
    assert listed.json()["validation_status"] == "FAILED"
    detail = client.get("/api/plugins/drift-pack/resources/resources:preset.json")
    assert detail.status_code == 404
    payload = detail.json()
    assert payload["detail"]["error_code"] == PLUGIN_RESOURCE_HASH_MISMATCH
    assert str(plugin) not in detail.text


def test_missing_file_invalidates_catalog(plugin_root):
    plugin = write_plugin(plugin_root, "gone-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "temp"}),
    ])
    client = _client()
    _register(client, "gone-pack")
    (plugin / "resources" / "preset.json").unlink()
    listed = client.get("/api/plugins/gone-pack/resources")
    body = listed.json()
    assert body["items"] == []
    assert body["validated"] is False
    assert body["validation_status"] == "FAILED"
    assert body["invalid_resource_count"] == 1
    assert body.get("error_code") != "PLUGIN_RESOURCE_TOO_LARGE"
    detail = client.get("/api/plugins/gone-pack/resources/resources:preset.json")
    assert detail.status_code == 404


def test_one_bad_resource_does_not_hide_others(plugin_root):
    plugin = write_plugin(plugin_root, "mixed-pack", resources=[
        ("writing_presets", "resources/good.json", {"name": "good"}),
        ("export_profiles", "resources/bad.json", {"name": "bad"}),
    ])
    client = _client()
    _register(client, "mixed-pack")
    (plugin / "resources" / "bad.json").write_text('{"name":"tampered"}', encoding="utf-8")
    items = client.get("/api/plugins/mixed-pack/resources").json()["items"]
    assert [item["resource_id"] for item in items] == ["resources:good.json"]
    assert client.get("/api/plugins/mixed-pack/resources/resources:bad.json").status_code == 404
    listed = client.get("/api/plugins/mixed-pack/resources").json()
    assert listed["validated"] is False
    assert listed["validation_status"] == "PARTIAL"
    assert listed["invalid_resource_count"] == 1


def test_cross_plugin_isolation_and_same_resource_id(plugin_root):
    write_plugin(plugin_root, "alpha-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "alpha", "owner": "alpha-pack"}),
    ])
    write_plugin(plugin_root, "beta-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "beta", "owner": "beta-pack"}),
    ])
    client = _client()
    _register(client, "alpha-pack")
    _register(client, "beta-pack")
    alpha = client.get("/api/plugins/alpha-pack/resources/resources:preset.json").json()
    beta = client.get("/api/plugins/beta-pack/resources/resources:preset.json").json()
    assert alpha["plugin_id"] == "alpha-pack"
    assert beta["plugin_id"] == "beta-pack"
    assert alpha["data"]["owner"] == "alpha-pack"
    assert beta["data"]["owner"] == "beta-pack"
    assert alpha["resource_id"] == beta["resource_id"] == "resources:preset.json"


def test_invalid_json_is_not_returned(plugin_root):
    plugin = write_plugin(plugin_root, "json-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "ok"}),
    ])
    client = _client()
    _register(client, "json-pack")
    (plugin / "resources" / "preset.json").write_text("{", encoding="utf-8")
    # Hash will also fail; either way the resource must not appear.
    listed = client.get("/api/plugins/json-pack/resources").json()
    assert listed["items"] == []
    detail = client.get("/api/plugins/json-pack/resources/resources:preset.json")
    assert detail.status_code in {400, 404}
    assert "{" not in json.dumps(detail.json().get("data", ""))


def test_api_does_not_disclose_paths_or_stacks(plugin_root, tmp_path):
    write_plugin(plugin_root, "path-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    _register(client, "path-pack")
    listed = client.get("/api/plugins/path-pack/resources")
    detail = client.get("/api/plugins/path-pack/resources/resources:preset.json")
    missing = client.get("/api/plugins/path-pack/resources/resources:missing.json")
    blob = listed.text + detail.text + missing.text
    assert str(plugin_root) not in blob
    assert str(tmp_path) not in blob
    assert str(plugin_root.resolve()) not in blob
    assert "Traceback" not in blob
    assert ":\\" not in blob
    for payload in (listed.json(), detail.json()):
        dumped = json.dumps(payload)
        assert "relative_path" not in dumped or "resources/preset.json" in dumped
        assert "entrypoint" not in dumped


def test_html_and_script_are_plain_data(plugin_root):
    write_plugin(plugin_root, "html-pack", resources=[
        ("writing_presets", "resources/preset.json", {
            "name": "<img src=x onerror=alert(1)>Title",
            "description": "<script>document.cookie</script>note",
        }),
    ])
    client = _client()
    _register(client, "html-pack")
    listed = client.get("/api/plugins/html-pack/resources").json()["items"][0]
    assert "<img" not in listed["name"]
    assert "<script" not in listed["description"]
    assert "Title" in listed["name"]
    detail = client.get("/api/plugins/html-pack/resources/resources:preset.json").json()
    # Raw JSON remains data; it is not executed or marked as HTML.
    assert detail["data"]["name"].startswith("<img")
    assert "<script>" not in detail["name"]
    assert "<script>" not in detail["summary"]["description"]
    assert detail["summary"]["name"] == listed["name"]


def test_external_url_is_not_fetched(plugin_root):
    write_plugin(plugin_root, "url-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n", "url": "https://example.invalid/hook"}),
    ])
    client = _client()
    _register(client, "url-pack")

    def boom(*_args, **_kwargs):
        raise AssertionError("network forbidden")

    from app.plugin_catalog import get_plugin_resource, list_plugin_resources
    with patch("socket.create_connection", boom), patch("urllib.request.urlopen", boom), \
            patch("httpx.Client.request", boom), patch("httpx.Client.get", boom):
        listed = list_plugin_resources("url-pack")
        detail = get_plugin_resource("url-pack", "resources:preset.json")
    assert listed["total"] == 1
    assert detail["data"]["url"] == "https://example.invalid/hook"


def test_catalog_does_not_touch_vault_or_start_processes(plugin_root):
    write_plugin(plugin_root, "safe-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    _register(client, "safe-pack")

    def boom(*_args, **_kwargs):
        raise AssertionError("forbidden side effect")

    with patch("subprocess.Popen", boom), patch("subprocess.run", boom), \
            patch("os.system", boom), patch("builtins.exec", boom), patch("builtins.eval", boom):
        with patch("app.credential_vault.credential_vault.resolve", boom):
            listed = client.get("/api/plugins/safe-pack/resources")
            detail = client.get("/api/plugins/safe-pack/resources/resources:preset.json")
    assert listed.status_code == 200
    assert detail.status_code == 200


def test_catalog_does_not_modify_plugin_files(plugin_root):
    plugin = write_plugin(plugin_root, "ro-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    _register(client, "ro-pack")
    target = plugin / "resources" / "preset.json"
    before = target.read_bytes()
    mtime = target.stat().st_mtime_ns
    client.get("/api/plugins/ro-pack/resources")
    client.get("/api/plugins/ro-pack/resources/resources:preset.json")
    assert target.read_bytes() == before
    assert target.stat().st_mtime_ns == mtime


def test_missing_package_directory_returns_empty_not_cache(plugin_root):
    plugin = write_plugin(plugin_root, "vanish-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    _register(client, "vanish-pack")
    assert client.get("/api/plugins/vanish-pack/resources").json()["total"] == 1
    for child in sorted(plugin.rglob("*"), reverse=True):
        if child.is_file() or child.is_symlink():
            child.unlink()
        elif child.is_dir():
            child.rmdir()
    if plugin.exists():
        plugin.rmdir()
    listed = client.get("/api/plugins/vanish-pack/resources")
    assert listed.status_code == 200
    assert listed.json()["items"] == []
    assert listed.json()["validated"] is False
    assert client.get("/api/plugins/vanish-pack/resources/resources:preset.json").status_code == 404


def test_catalog_source_has_no_execution_hooks():
    source = (REPO / "app" / "plugin_catalog.py").read_text(encoding="utf-8")
    stripped = source.replace("re.compile(", "")
    assert "subprocess" not in stripped
    assert "os.system" not in stripped
    assert "importlib" not in stripped
    assert "eval(" not in stripped
    assert "exec(" not in stripped
    assert "compile(" not in stripped


def test_example_pack_catalog_roundtrip(plugin_root):
    dest = plugin_root / "story-workflow-pack"
    dest.mkdir()
    dest.joinpath("manifest.json").write_bytes((EXAMPLE / "manifest.json").read_bytes())
    resources = dest / "resources"
    resources.mkdir()
    for name in ("writing-preset.json", "workflow-template.json"):
        (resources / name).write_bytes((EXAMPLE / "resources" / name).read_bytes())
    client = _client()
    _register(client, "story-workflow-pack")
    listed = client.get("/api/plugins/story-workflow-pack/resources").json()
    assert listed["total"] == 2
    assert listed["execution_supported"] is False
    assert str(plugin_root) not in json.dumps(listed)
    detail = client.get("/api/plugins/story-workflow-pack/resources/resources:writing-preset.json")
    assert detail.status_code == 200
    assert detail.json()["validated"] is True
    assert "宿主不会自动应用" in detail.json()["data"]["description"]


def test_plugin_semver_is_independent_of_sidecar_revision(plugin_root):
    write_plugin(plugin_root, "semver-pack", version="1.2.3", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    created = _register(client, "semver-pack")
    assert created["version"] == 1
    assert created["plugin_version"] == "1.2.3"
    assert len(created["manifest_sha256"]) == 64
    loaded = client.get("/api/plugins/semver-pack").json()
    assert loaded["version"] == 2 or loaded["version"] >= 1
    assert loaded["plugin_version"] == "1.2.3"
    assert loaded["manifest_sha256"] == created["manifest_sha256"]


def test_duplicate_plugin_id_is_not_trusted_by_catalog(plugin_root):
    write_plugin(plugin_root, "dup-a", resources=[
        ("writing_presets", "resources/preset.json", {"name": "a"}),
    ])
    first = plugin_root / "dup-a" / "manifest.json"
    manifest = json.loads(first.read_text(encoding="utf-8"))
    manifest["id"] = "shared-pack"
    first.write_text(json.dumps(manifest), encoding="utf-8")
    client = _client()
    created = client.post("/api/plugins", json=json.loads((plugin_root / "dup-a" / "manifest.json").read_text(encoding="utf-8")))
    assert created.status_code == 201
    enabled = client.post("/api/plugins/shared-pack/enable")
    assert enabled.status_code == 200
    write_plugin(plugin_root, "dup-b", resources=[
        ("writing_presets", "resources/preset.json", {"name": "b"}),
    ])
    second = plugin_root / "dup-b" / "manifest.json"
    other = json.loads(second.read_text(encoding="utf-8"))
    other["id"] = "shared-pack"
    second.write_text(json.dumps(other), encoding="utf-8")
    listed = client.get("/api/plugins/shared-pack/resources")
    assert listed.status_code == 200
    body = listed.json()
    assert body["items"] == []
    assert body["validated"] is False
    assert body["error_code"] == PLUGIN_ID_DUPLICATE
    detail = client.get("/api/plugins/shared-pack/resources/resources:preset.json")
    assert detail.status_code == 409
    assert detail.json()["detail"]["error_code"] == PLUGIN_ID_DUPLICATE
    assert str(plugin_root) not in listed.text + detail.text
    blocked = client.post("/api/plugins/shared-pack/enable")
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["error_code"] == PLUGIN_ID_DUPLICATE


def _rewrite_manifest(plugin: Path, **changes):
    manifest = json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))
    manifest.update(changes)
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


def test_manifest_field_changes_are_drift(plugin_root):
    plugin = write_plugin(plugin_root, "drift-id", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ], requested_permissions=["project.read"])
    client = _client()
    _register(client, "drift-id")
    for changes in (
        {"version": "9.9.9"},
        {"capabilities": ["exporter"]},
        {"requested_permissions": ["project.read", "project.write"]},
    ):
        _rewrite_manifest(plugin, **changes)
        listed = client.get("/api/plugins/drift-id/resources")
        assert listed.status_code == 200
        body = listed.json()
        assert body["items"] == []
        assert body["validated"] is False
        assert body["status"] == "MANIFEST_DRIFT"
        assert body["error_code"] == PLUGIN_MANIFEST_DRIFT
        detail = client.get("/api/plugins/drift-id/resources/resources:preset.json")
        assert detail.status_code == 409
        assert detail.json()["detail"]["error_code"] == PLUGIN_MANIFEST_DRIFT
        original = json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))
        original["version"] = "1.0.0"
        original["capabilities"] = ["writing_tool"]
        original["requested_permissions"] = ["project.read"]
        (plugin / "manifest.json").write_text(json.dumps(original), encoding="utf-8")
    resource_path = plugin / "resources" / "preset.json"
    resource_path.write_text('{"name":"changed"}', encoding="utf-8")
    digest = hashlib.sha256(resource_path.read_bytes()).hexdigest()
    _rewrite_manifest(plugin, resources=[{
        "kind": "writing_presets",
        "relative_path": "resources/preset.json",
        "sha256": digest,
        "media_type": "application/json",
        "schema_version": "1.0",
    }])
    listed = client.get("/api/plugins/drift-id/resources")
    assert listed.json()["error_code"] == PLUGIN_MANIFEST_DRIFT
    assert listed.json()["items"] == []


def _sidecar_text() -> str:
    path = v1_capability_service.root / "v1_capabilities" / "plugins.json"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _audit_actions() -> list[str]:
    return [str(row.get("action")) for row in v1_capability_service._read("audit")]


def test_duplicate_id_cannot_register_without_sidecar(plugin_root):
    write_plugin(plugin_root, "copy-a", resources=[
        ("writing_presets", "resources/preset.json", {"name": "a"}),
    ])
    write_plugin(plugin_root, "copy-b", resources=[
        ("writing_presets", "resources/preset.json", {"name": "b"}),
    ])
    for name in ("copy-a", "copy-b"):
        manifest = json.loads((plugin_root / name / "manifest.json").read_text(encoding="utf-8"))
        manifest["id"] = "shared-pack"
        (plugin_root / name / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    client = _client()
    body = json.loads((plugin_root / "copy-a" / "manifest.json").read_text(encoding="utf-8"))
    sidecar_before = _sidecar_text()
    audit_before = _audit_actions()
    created = client.post("/api/plugins", json=body, headers={"Idempotency-Key": "dup-register-1"})
    assert created.status_code == 409
    detail = created.json()["detail"]
    assert detail["error_code"] == PLUGIN_ID_DUPLICATE
    assert str(plugin_root) not in created.text
    assert "Traceback" not in created.text
    missing = client.get("/api/plugins/shared-pack")
    assert missing.status_code == 404
    assert _sidecar_text() == sidecar_before
    assert _audit_actions() == audit_before


def test_duplicate_after_register_does_not_mutate_sidecar(plugin_root):
    write_plugin(plugin_root, "dup-a", resources=[
        ("writing_presets", "resources/preset.json", {"name": "a"}),
    ])
    first = plugin_root / "dup-a" / "manifest.json"
    manifest = json.loads(first.read_text(encoding="utf-8"))
    manifest["id"] = "shared-pack"
    first.write_text(json.dumps(manifest), encoding="utf-8")
    client = _client()
    created = client.post("/api/plugins", json=json.loads(first.read_text(encoding="utf-8")))
    assert created.status_code == 201, created.text
    enabled = client.post("/api/plugins/shared-pack/enable")
    assert enabled.status_code == 200, enabled.text
    write_plugin(plugin_root, "dup-b", resources=[
        ("writing_presets", "resources/preset.json", {"name": "b"}),
    ])
    second = plugin_root / "dup-b" / "manifest.json"
    other = json.loads(second.read_text(encoding="utf-8"))
    other["id"] = "shared-pack"
    second.write_text(json.dumps(other), encoding="utf-8")
    before = client.get("/api/plugins/shared-pack").json()
    sidecar_before = _sidecar_text()
    audit_before = _audit_actions()
    again = client.post("/api/plugins", json=json.loads(first.read_text(encoding="utf-8")))
    assert again.status_code == 409
    assert again.json()["detail"]["error_code"] == PLUGIN_ID_DUPLICATE
    after = client.get("/api/plugins/shared-pack").json()
    assert after["version"] == before["version"]
    assert after["status"] == before["status"]
    assert after["granted_permissions"] == before["granted_permissions"]
    assert after.get("permission_review") == before.get("permission_review")
    assert _sidecar_text() == sidecar_before
    assert _audit_actions() == audit_before
    assert created.json()["id"] == "shared-pack"


def test_client_manifest_drift_is_rejected_without_sidecar_write(plugin_root):
    write_plugin(plugin_root, "drift-reg", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    body = json.loads((plugin_root / "drift-reg" / "manifest.json").read_text(encoding="utf-8"))
    body["version"] = "9.9.9"
    sidecar_before = _sidecar_text()
    audit_before = _audit_actions()
    response = client.post("/api/plugins", json=body)
    assert response.status_code == 409
    assert response.json()["detail"]["error_code"] == PLUGIN_MANIFEST_DRIFT
    assert str(plugin_root) not in response.text
    assert client.get("/api/plugins/drift-reg").status_code == 404
    assert _sidecar_text() == sidecar_before
    assert _audit_actions() == audit_before


def test_unique_matching_plugin_still_registers(plugin_root):
    write_plugin(plugin_root, "solo-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    created = _register(client, "solo-pack", enable=False, review=False)
    assert created["id"] == "solo-pack"
    assert created["status"] == "REGISTERED"
    assert created["granted_permissions"] == []
    loaded = client.get("/api/plugins/solo-pack").json()
    assert loaded["plugin_version"] == "1.0.0"
    assert loaded["execution_supported"] is False


def _assert_partial_good(plugin_root, plugin_id: str, mutate, *, invalid=1):
    client = _client()
    _register(client, plugin_id)
    mutate()
    listed = client.get(f"/api/plugins/{plugin_id}/resources")
    assert listed.status_code == 200
    body = listed.json()
    assert body["validated"] is False
    assert body["validation_status"] == "PARTIAL"
    assert body["invalid_resource_count"] == invalid
    assert [item["resource_id"] for item in body["items"]] == ["resources:good.json"]
    assert body["resource_count"] == 1
    assert body["resource_kinds"] == ["writing_presets"]
    assert str(plugin_root) not in listed.text
    assert "Traceback" not in listed.text
    good = client.get(f"/api/plugins/{plugin_id}/resources/resources:good.json")
    assert good.status_code == 200
    assert good.json()["data"]["name"] == "good"
    assert str(plugin_root) not in good.text


def test_good_plus_missing_is_partial_and_good_detail_ok(plugin_root):
    plugin = write_plugin(plugin_root, "mix-missing", resources=[
        ("writing_presets", "resources/good.json", {"name": "good"}),
        ("export_profiles", "resources/gone.json", {"name": "gone"}),
    ])
    _assert_partial_good(plugin_root, "mix-missing", lambda: (plugin / "resources" / "gone.json").unlink())
    bad = _client().get("/api/plugins/mix-missing/resources/resources:gone.json")
    assert bad.status_code in {400, 404}
    assert str(plugin) not in bad.text
    assert "Traceback" not in bad.text


def test_good_plus_symlink_invalid_is_partial(plugin_root, tmp_path):
    plugin = write_plugin(plugin_root, "mix-link", resources=[
        ("writing_presets", "resources/good.json", {"name": "good"}),
        ("export_profiles", "resources/gone.json", {"name": "gone"}),
    ])
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret":"nope"}', encoding="utf-8")

    def mutate():
        target = plugin / "resources" / "gone.json"
        target.unlink()
        os.symlink(outside, target)

    _assert_partial_good(plugin_root, "mix-link", mutate)


def test_good_plus_hash_invalid_is_partial(plugin_root):
    plugin = write_plugin(plugin_root, "mix-hash", resources=[
        ("writing_presets", "resources/good.json", {"name": "good"}),
        ("export_profiles", "resources/gone.json", {"name": "gone"}),
    ])
    _assert_partial_good(
        plugin_root, "mix-hash",
        lambda: (plugin / "resources" / "gone.json").write_text('{"name":"tampered"}', encoding="utf-8"),
    )


def test_good_plus_invalid_json_is_partial(plugin_root):
    plugin = write_plugin(plugin_root, "mix-json", resources=[
        ("writing_presets", "resources/good.json", {"name": "good"}),
        ("export_profiles", "resources/gone.json", {"name": "gone"}),
    ])
    _assert_partial_good(
        plugin_root, "mix-json",
        lambda: (plugin / "resources" / "gone.json").write_text("{", encoding="utf-8"),
    )


def test_all_invalid_resources_are_failed_with_count(plugin_root):
    plugin = write_plugin(plugin_root, "all-bad", resources=[
        ("writing_presets", "resources/one.json", {"name": "one"}),
        ("export_profiles", "resources/two.json", {"name": "two"}),
    ])
    client = _client()
    _register(client, "all-bad")
    (plugin / "resources" / "one.json").unlink()
    (plugin / "resources" / "two.json").write_text('{"name":"tampered"}', encoding="utf-8")
    listed = client.get("/api/plugins/all-bad/resources")
    body = listed.json()
    assert listed.status_code == 200
    assert body["items"] == []
    assert body["validated"] is False
    assert body["validation_status"] == "FAILED"
    assert body["invalid_resource_count"] == 2
    assert str(plugin) not in listed.text


def test_catalog_per_file_budget_fail_closed(plugin_root, monkeypatch):
    plugin = write_plugin(plugin_root, "file-budget", resources=[
        ("writing_presets", "resources/one.json", {"name": "one", "pad": "x" * 80}),
        ("writing_presets", "resources/two.json", {"name": "two"}),
    ])
    client = _client()
    _register(client, "file-budget")
    monkeypatch.setattr("app.plugin_discovery.MAX_RESOURCE_BYTES", 40)
    listed = client.get("/api/plugins/file-budget/resources")
    body = listed.json()
    assert listed.status_code == 200
    assert body["items"] == []
    assert body["validated"] is False
    assert body["error_code"] == "PLUGIN_RESOURCE_TOO_LARGE"
    assert body["validation_status"] == "BUDGET"
    detail = client.get("/api/plugins/file-budget/resources/resources:two.json")
    assert detail.status_code in {400, 404}
    assert str(plugin) not in listed.text + detail.text


def test_ten_thousand_layer_json_does_not_return_500(plugin_root):
    plugin = write_plugin(plugin_root, "deep10k", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    target = plugin / "resources" / "preset.json"
    text = '{"leaf":true}'
    for _ in range(10000):
        text = '{"child":' + text + "}"
    target.write_text(text, encoding="utf-8")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))
    manifest["resources"][0]["sha256"] = digest
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    client = _client()
    created = client.post("/api/plugins", json=json.loads((plugin / "manifest.json").read_text(encoding="utf-8")))
    assert created.status_code in {201, 400, 409}
    if created.status_code == 201:
        enabled = client.post("/api/plugins/deep10k/enable")
        assert enabled.status_code in {200, 400, 409}
        listed = client.get("/api/plugins/deep10k/resources")
        assert listed.status_code != 500
        assert "Traceback" not in listed.text
        assert "artificial" not in listed.text
        detail = client.get("/api/plugins/deep10k/resources/resources:preset.json")
        assert detail.status_code != 500
        assert "Traceback" not in detail.text
        assert str(plugin) not in listed.text + detail.text


def test_legacy_sidecar_without_identity_is_review_required(plugin_root):
    write_plugin(plugin_root, "legacy-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    created = _register(client, "legacy-pack")
    sidecar = v1_capability_service.root / "v1_capabilities" / "plugins.json"
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    for item in payload["items"]:
        item.pop("plugin_version", None)
        item.pop("manifest_sha256", None)
        item["status"] = "MANIFEST_ACTIVE"
        item["granted_permissions"] = []
    sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    loaded = client.get("/api/plugins/legacy-pack").json()
    assert loaded["status"] == "REVIEW_REQUIRED"
    listed = client.get("/api/plugins/legacy-pack/resources").json()
    assert listed["items"] == []
    assert listed["validated"] is False
    assert listed["visible"] is False
    assert client.get("/api/plugins/legacy-pack/resources/resources:preset.json").status_code == 404
    enabled = client.post("/api/plugins/legacy-pack/enable")
    assert enabled.status_code == 400
    assert created["id"] == "legacy-pack"


def test_identity_change_requires_reregister_and_does_not_keep_activation(plugin_root):
    plugin = write_plugin(plugin_root, "rebind-pack", version="1.0.0", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    _register(client, "rebind-pack")
    first = client.get("/api/plugins/rebind-pack").json()
    assert first["status"] == "MANIFEST_ACTIVE"
    _rewrite_manifest(plugin, version="2.0.0")
    listed = client.get("/api/plugins/rebind-pack/resources").json()
    assert listed["error_code"] == PLUGIN_MANIFEST_DRIFT
    updated = json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))
    again = client.post("/api/plugins", json=updated)
    assert again.status_code == 200 or again.status_code == 201
    body = again.json()
    assert body["status"] == "REGISTERED"
    assert body["granted_permissions"] == []
    assert body["plugin_version"] == "2.0.0"
    assert body["manifest_sha256"] != first["manifest_sha256"]
    assert client.get("/api/plugins/rebind-pack/resources").json()["items"] == []


def test_catalog_total_budget_fail_closed(plugin_root, monkeypatch):
    plugin = write_plugin(plugin_root, "budget-pack", resources=[
        ("writing_presets", "resources/one.json", {"name": "one", "pad": "x" * 20}),
        ("writing_presets", "resources/two.json", {"name": "two", "pad": "x" * 20}),
    ])
    client = _client()
    _register(client, "budget-pack")
    monkeypatch.setattr("app.plugin_discovery.MAX_TOTAL_RESOURCE_BYTES", 40)
    listed = client.get("/api/plugins/budget-pack/resources")
    assert listed.status_code == 200
    body = listed.json()
    assert body["items"] == []
    assert body["validated"] is False
    assert body["error_code"] == "PLUGIN_RESOURCE_TOO_LARGE"
    assert body["validation_status"] == "BUDGET"
    detail = client.get("/api/plugins/budget-pack/resources/resources:one.json")
    assert detail.status_code in {400, 404}
    assert str(plugin) not in listed.text + detail.text


def test_deep_json_does_not_return_500(plugin_root, monkeypatch):
    nested: dict = {"leaf": True}
    for _ in range(12):
        nested = {"child": nested}
    write_plugin(plugin_root, "deep-pack", resources=[
        ("writing_presets", "resources/preset.json", nested),
    ])
    client = _client()
    _register(client, "deep-pack")
    monkeypatch.setattr("app.plugin_discovery.MAX_JSON_DEPTH", 8)
    listed = client.get("/api/plugins/deep-pack/resources")
    assert listed.status_code == 200
    body = listed.json()
    assert body["validated"] is False
    assert body["items"] == []
    assert "Traceback" not in listed.text
    detail = client.get("/api/plugins/deep-pack/resources/resources:preset.json")
    assert detail.status_code != 500
    assert detail.status_code in {400, 404}
    assert detail.json()["detail"]["error_code"] == "PLUGIN_RESOURCE_INVALID_JSON"
    assert str(plugin_root) not in listed.text + detail.text


def test_recursion_error_is_normalized(plugin_root, monkeypatch):
    write_plugin(plugin_root, "recur-pack", resources=[
        ("writing_presets", "resources/preset.json", {"name": "n"}),
    ])
    client = _client()
    _register(client, "recur-pack")

    def boom(*_args, **_kwargs):
        raise RecursionError("artificial")

    monkeypatch.setattr("app.plugin_discovery.json.loads", boom)
    listed = client.get("/api/plugins/recur-pack/resources")
    assert listed.status_code != 500
    assert "artificial" not in listed.text
    assert "Traceback" not in listed.text
    if listed.status_code == 200:
        assert listed.json()["validated"] is False
        assert listed.json()["items"] == []
    detail = client.get("/api/plugins/recur-pack/resources/resources:preset.json")
    assert detail.status_code != 500
    assert "artificial" not in detail.text
    assert "Traceback" not in detail.text
