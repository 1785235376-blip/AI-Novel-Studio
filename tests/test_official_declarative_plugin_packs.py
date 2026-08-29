from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.dependencies import v1_capability_service
from app.main import app
from app.plugin_contracts import (
    EXECUTION_MODE_DECLARATIVE,
    FORBIDDEN_EXECUTION_FIELDS,
    MAX_RESOURCE_BYTES,
    MAX_RESOURCE_COUNT,
    MAX_TOTAL_RESOURCE_BYTES,
    PLUGIN_CAPABILITIES,
    PLUGIN_PERMISSIONS,
    canonical_manifest_schema,
    parse_plugin_manifest,
    validate_declarative_relative_path,
)
from app.plugin_discovery import discover_installed_plugins, load_plugin_package


REPO = Path(__file__).resolve().parents[1]
PACKS_ROOT = REPO / "examples" / "plugins"

OFFICIAL_PACK_IDS = (
    "novel-craft-pack",
    "genre-fiction-pack",
    "revision-editor-pack",
    "continuity-audit-pack",
    "worldbuilding-character-pack",
    "screenplay-adaptation-pack",
    "storyboard-planning-pack",
    "author-export-profile-pack",
)

ALLOWED_KINDS = frozenset({"writing_presets", "workflow_templates", "export_profiles"})
ALLOWED_PACK_FILES = frozenset({".json", ".md"})

REQUIRED_RESOURCE_NAMES = {
    "novel-craft-pack": {
        "Scene Draft", "Dialogue Pass", "Action Scene", "Suspense Build",
        "Emotional Scene", "Description Control", "POV Lock", "Pacing Control",
    },
    "genre-fiction-pack": {
        "Science Fiction", "Fantasy", "Mystery", "Thriller", "Horror",
        "Romance", "Historical Fiction",
    },
    "revision-editor-pack": {
        "Tighten", "Expand", "Dialogue Polish", "Description Polish",
        "Pacing Repair", "Clarity Rewrite", "Chapter Revision", "Developmental Edit",
    },
    "continuity-audit-pack": {
        "Character Continuity Audit", "Timeline Audit", "World Rule Audit",
        "Location Continuity Audit", "Prop Continuity Audit", "Foreshadowing / Payoff Audit",
    },
    "worldbuilding-character-pack": {
        "World Bible Builder", "Character Builder", "Faction Builder",
        "Location Builder", "Character Arc Planner", "Relationship Planner",
    },
    "screenplay-adaptation-pack": {
        "Novel to Beat Sheet", "Beat Sheet to Scene List", "Scene to Screenplay Outline",
        "Screen Dialogue", "Visual Action Description", "Scene Compression",
        "Adaptation Fidelity Control",
    },
    "storyboard-planning-pack": {
        "Scene to Shot List", "Image Prompt Preparation",
        "Motion Prompt Preparation", "Transition Planning",
    },
    "author-export-profile-pack": {
        "Novel Markdown", "Manuscript Plain Text",
        "Screenplay Outline JSON", "Production Handoff JSON",
    },
}


def official_pack_dir(plugin_id: str) -> Path:
    return PACKS_ROOT / plugin_id


def load_manifest_payload(plugin_id: str) -> dict:
    return json.loads((official_pack_dir(plugin_id) / "manifest.json").read_text(encoding="utf-8"))


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pack_file_digest(pack: Path) -> dict[str, str]:
    return {
        str(path.relative_to(pack)): file_sha256(path)
        for path in sorted(pack.rglob("*"))
        if path.is_file()
    }


def copy_pack(plugin_root: Path, plugin_id: str) -> Path:
    dest = plugin_root / plugin_id
    shutil.copytree(official_pack_dir(plugin_id), dest)
    return dest


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


def _register(client: TestClient, plugin_id: str) -> dict:
    manifest = json.loads((settings.data_path() / "plugins" / plugin_id / "manifest.json").read_text(encoding="utf-8"))
    created = client.post("/api/plugins", json=manifest)
    assert created.status_code == 201, created.text
    enabled = client.post(f"/api/plugins/{plugin_id}/enable")
    assert enabled.status_code == 200, enabled.text
    return created.json()


@pytest.mark.parametrize("plugin_id", OFFICIAL_PACK_IDS)
def test_official_pack_passes_plugin_contract_v1(plugin_id):
    payload = load_manifest_payload(plugin_id)
    parsed = parse_plugin_manifest(payload)
    schema = canonical_manifest_schema()
    assert set(payload) <= set(schema["properties"])
    assert parsed.id == plugin_id
    assert parsed.version == "1.0.0"
    assert parsed.manifest_version == "1.0"
    assert parsed.host_api_version == "1"
    assert parsed.execution_mode == EXECUTION_MODE_DECLARATIVE
    loaded, verified = load_plugin_package(official_pack_dir(plugin_id))
    assert loaded.id == plugin_id
    assert len(verified) == len(parsed.resources)
    assert all(item["data"] for item in verified)


def test_official_pack_ids_are_unique_and_stable():
    example_id = json.loads((PACKS_ROOT / "story-workflow-pack" / "manifest.json").read_text(encoding="utf-8"))["id"]
    ids = [load_manifest_payload(plugin_id)["id"] for plugin_id in OFFICIAL_PACK_IDS]
    assert ids == list(OFFICIAL_PACK_IDS)
    assert len(set(ids)) == len(ids)
    assert example_id not in set(ids)


@pytest.mark.parametrize("plugin_id", OFFICIAL_PACK_IDS)
def test_official_pack_has_no_execution_fields_or_entrypoints(plugin_id):
    payload = load_manifest_payload(plugin_id)
    assert FORBIDDEN_EXECUTION_FIELDS.intersection(payload) == set()
    assert payload.get("execution_mode") == "declarative"
    dumped = json.dumps(payload)
    for field in FORBIDDEN_EXECUTION_FIELDS:
        assert f'"{field}"' not in dumped


@pytest.mark.parametrize("plugin_id", OFFICIAL_PACK_IDS)
def test_official_pack_contains_only_declarative_json_resources(plugin_id):
    pack = official_pack_dir(plugin_id)
    assert not any(path.is_symlink() for path in pack.rglob("*"))
    for path in pack.rglob("*"):
        if not path.is_file():
            continue
        assert path.suffix in ALLOWED_PACK_FILES, path
        assert not (path.stat().st_mode & 0o111), path
        if path.name != "README.md":
            assert path.suffix == ".json"
    payload = load_manifest_payload(plugin_id)
    parsed = parse_plugin_manifest(payload)
    for resource in parsed.resources:
        assert resource.kind in ALLOWED_KINDS
        validate_declarative_relative_path(resource.relative_path)
        resource_path = pack / Path(*resource.relative_path.split("/"))
        assert resource_path.is_file()
        assert resource_path.suffix == ".json"
        assert file_sha256(resource_path) == resource.sha256
        data = json.loads(resource_path.read_text(encoding="utf-8"))
        assert isinstance(data, (dict, list))


@pytest.mark.parametrize("plugin_id", OFFICIAL_PACK_IDS)
def test_official_pack_stays_within_resource_budget_and_requests_no_permissions(plugin_id):
    parsed = parse_plugin_manifest(load_manifest_payload(plugin_id))
    assert parsed.requested_permissions == []
    assert set(parsed.capabilities) <= PLUGIN_CAPABILITIES
    assert set(parsed.requested_permissions) <= PLUGIN_PERMISSIONS
    assert len(parsed.resources) <= MAX_RESOURCE_COUNT
    pack = official_pack_dir(plugin_id)
    total = 0
    for resource in parsed.resources:
        size = (pack / Path(*resource.relative_path.split("/"))).stat().st_size
        assert size <= MAX_RESOURCE_BYTES
        total += size
    assert total <= MAX_TOTAL_RESOURCE_BYTES


@pytest.mark.parametrize("plugin_id", OFFICIAL_PACK_IDS)
def test_official_pack_publisher_is_unverified_metadata(plugin_id):
    payload = load_manifest_payload(plugin_id)
    parsed = parse_plugin_manifest(payload)
    dumped = parsed.public_dump()
    assert dumped["publisher"] == "AI Novel Studio Official"
    assert "signed" not in json.dumps(dumped).casefold()
    assert dumped.get("publisher_verified") is None
    readme = (official_pack_dir(plugin_id) / "README.md").read_text(encoding="utf-8").casefold()
    assert "unverified" in readme
    assert "not a signature" in readme


@pytest.mark.parametrize("plugin_id", OFFICIAL_PACK_IDS)
def test_official_pack_ships_required_named_resources(plugin_id):
    _loaded, verified = load_plugin_package(official_pack_dir(plugin_id))
    names = {item["data"]["name"] for item in verified}
    assert REQUIRED_RESOURCE_NAMES[plugin_id] <= names
    for item in verified:
        assert item["kind"] in ALLOWED_KINDS
        assert item["data"].get("schema_version") == "1.0"
        if item["kind"] == "workflow_templates":
            assert item["data"].get("execution") in {"not_supported", "not_implemented"}
            assert item["data"].get("execution_supported") is False
        if item["kind"] == "export_profiles":
            blob = json.dumps(item["data"])
            assert "NOT IMPLEMENTED" in blob
            assert item["data"].get("execution_supported") is False


def test_discovery_identifies_all_official_packs_without_path_leak(plugin_root):
    for plugin_id in OFFICIAL_PACK_IDS:
        copy_pack(plugin_root, plugin_id)
    result = discover_installed_plugins(plugin_root)
    assert result["execution_supported"] is False
    assert result["isolation"] == "DENY_ALL"
    assert result["total"] == len(OFFICIAL_PACK_IDS)
    discovered = {item["manifest"]["id"] for item in result["items"]}
    assert discovered == set(OFFICIAL_PACK_IDS)
    payload = json.dumps(result)
    assert str(plugin_root) not in payload
    assert str(PACKS_ROOT) not in payload
    for item in result["items"]:
        assert item["execution_supported"] is False
        assert item["publisher_verified"] is False
        assert item["manifest"]["requested_permissions"] == []
        assert FORBIDDEN_EXECUTION_FIELDS.intersection(item["manifest"]) == set()


def test_catalog_reads_official_packs_read_only_without_side_effects(plugin_root):
    for plugin_id in OFFICIAL_PACK_IDS:
        copy_pack(plugin_root, plugin_id)
    before = {plugin_id: pack_file_digest(plugin_root / plugin_id) for plugin_id in OFFICIAL_PACK_IDS}

    def boom(*_args, **_kwargs):
        raise AssertionError("side effect forbidden")

    client = _client()
    with (
        patch("subprocess.Popen", boom),
        patch("subprocess.run", boom),
        patch("os.system", boom),
    ):
        with patch("app.credential_vault.credential_vault.resolve", boom):
            discovered = client.get("/api/plugins/discover").json()
            assert discovered["execution_supported"] is False
            assert {item["manifest"]["id"] for item in discovered["items"]} == set(OFFICIAL_PACK_IDS)
            for plugin_id in OFFICIAL_PACK_IDS:
                created = _register(client, plugin_id)
                assert created["execution_supported"] is False
                assert created["granted_permissions"] == []
                listed = client.get(f"/api/plugins/{plugin_id}/resources")
                assert listed.status_code == 200, listed.text
                body = listed.json()
                assert body["visible"] is True
                assert body["validated"] is True
                assert body["execution_supported"] is False
                assert body["isolation"] == "DENY_ALL"
                assert body["publisher_verified"] is False
                assert body["total"] == len(load_manifest_payload(plugin_id)["resources"])
                assert str(plugin_root) not in json.dumps(body)
                assert {item["kind"] for item in body["items"]} <= ALLOWED_KINDS
                detail = client.get(f"/api/plugins/{plugin_id}/resources/{body['items'][0]['resource_id']}")
                assert detail.status_code == 200, detail.text
                assert detail.json()["validated"] is True
                assert "data" in detail.json()
                assert detail.json()["execution_supported"] is False

    after = {plugin_id: pack_file_digest(plugin_root / plugin_id) for plugin_id in OFFICIAL_PACK_IDS}
    assert after == before


def test_loading_official_packs_does_not_touch_process_network_or_credentials(plugin_root):
    for plugin_id in OFFICIAL_PACK_IDS:
        copy_pack(plugin_root, plugin_id)

    def boom(*_args, **_kwargs):
        raise AssertionError("side effect forbidden")

    with (
        patch("subprocess.Popen", boom),
        patch("subprocess.run", boom),
        patch("os.system", boom),
        patch("socket.create_connection", boom),
        patch("httpx.Client.request", boom),
    ):
        with patch("app.credential_vault.credential_vault.resolve", boom):
            for plugin_id in OFFICIAL_PACK_IDS:
                load_plugin_package(official_pack_dir(plugin_id))
            result = discover_installed_plugins(plugin_root)
    assert {item["manifest"]["id"] for item in result["items"]} == set(OFFICIAL_PACK_IDS)
    assert result["execution_supported"] is False
