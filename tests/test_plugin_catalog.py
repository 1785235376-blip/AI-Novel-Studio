from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import v1_capability_service
from app.main import app
from app.plugin_catalog import plain_text
from app.plugin_contracts import PLUGIN_RESOURCE_HASH_MISMATCH


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
                 requested_permissions: list[str] | None = None) -> Path:
    plugin = root / plugin_id
    plugin.mkdir(parents=True, exist_ok=True)
    declared = []
    for kind, relative, payload in resources or []:
        data = _write_json(plugin / Path(*relative.split("/")), payload)
        declared.append(_resource(kind, relative, data))
    manifest = {
        "id": plugin_id,
        "name": plugin_id,
        "version": "1.0.0",
        "capabilities": ["writing_tool"],
        "requested_permissions": requested_permissions or [],
        "resources": declared,
    }
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return plugin


@pytest.fixture
def plugin_root(tmp_path):
    original = v1_capability_service.root
    object.__setattr__(settings, "novel_data", tmp_path)
    v1_capability_service.reconfigure_root(tmp_path)
    root = tmp_path / "plugins"
    root.mkdir()
    yield root
    v1_capability_service.reconfigure_root(original)


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
    assert listed.json()["items"] == []
    detail = client.get("/api/plugins/gone-pack/resources/resources:preset.json")
    assert detail.status_code == 404


def test_one_bad_resource_does_not_hide_others(plugin_root):
    plugin = write_plugin(plugin_root, "mixed-pack", resources=[
        ("writing_presets", "resources/good.json", {"name": "good"}),
        ("export_profiles", "resources/bad.json", {"name": "bad"}),
    ])
    manifest = json.loads((plugin / "manifest.json").read_text(encoding="utf-8"))
    manifest["resources"][1]["sha256"] = "0" * 64
    (plugin / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    client = _client()
    _register(client, "mixed-pack")
    items = client.get("/api/plugins/mixed-pack/resources").json()["items"]
    assert [item["resource_id"] for item in items] == ["resources:good.json"]
    assert client.get("/api/plugins/mixed-pack/resources/resources:bad.json").status_code == 404


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
    assert detail.status_code == 404
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
