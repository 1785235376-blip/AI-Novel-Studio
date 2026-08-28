from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.plugin_contracts import (
    EXECUTION_MODE_DECLARATIVE,
    FORBIDDEN_EXECUTION_FIELDS,
    HOST_API_VERSION,
    MAX_RESOURCE_COUNT,
    PLUGIN_MANIFEST_INVALID,
    PLUGIN_MANIFEST_UNSUPPORTED_VERSION,
    PLUGIN_MANIFEST_VERSION,
    PLUGIN_RESOURCE_PATH_INVALID,
    PLUGIN_RESOURCE_TYPE_UNSUPPORTED,
    PluginContractError,
    PluginManifestV1,
    canonical_manifest_schema,
    canonical_manifest_sha256,
    parse_plugin_manifest,
    validate_declarative_relative_path,
)
from app.plugin_discovery import load_plugin_package
from app.services.v1_capability_service import PluginManifestIn


REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "examples" / "plugins" / "story-workflow-pack"
SCHEMA_PATH = REPO / "schemas" / "plugin-manifest-v1.schema.json"


def example_manifest() -> dict:
    return json.loads((EXAMPLE / "manifest.json").read_text(encoding="utf-8"))


def test_legacy_minimal_manifest_gets_safe_defaults():
    manifest = parse_plugin_manifest({"id": "old-plugin", "name": "旧插件", "version": "1.0.0"})
    assert manifest.manifest_version == PLUGIN_MANIFEST_VERSION
    assert manifest.host_api_version == HOST_API_VERSION
    assert manifest.execution_mode == EXECUTION_MODE_DECLARATIVE
    assert manifest.capabilities == []
    assert manifest.requested_permissions == []
    assert manifest.resources == []
    assert manifest.publisher == ""
    assert PluginManifestIn is PluginManifestV1


def test_legal_contract_v1_and_example_package():
    parsed = parse_plugin_manifest(example_manifest())
    assert parsed.id == "story-workflow-pack"
    assert parsed.execution_mode == "declarative"
    assert parsed.requested_permissions == []
    assert {item.kind for item in parsed.resources} == {"writing_presets", "workflow_templates"}
    loaded, verified = load_plugin_package(EXAMPLE)
    assert loaded.id == parsed.id
    assert len(verified) == 2
    assert all(item["data"] for item in verified)


@pytest.mark.parametrize("version", ["1", "1.0", "v1.0.0", "", "1.0.0.0"])
def test_illegal_semver_is_rejected(version):
    with pytest.raises(PluginContractError) as caught:
        parse_plugin_manifest({"id": "ab", "name": "n", "version": version})
    assert caught.value.code == PLUGIN_MANIFEST_INVALID


def test_unknown_capability_is_rejected():
    with pytest.raises(PluginContractError) as caught:
        parse_plugin_manifest({
            "id": "ab", "name": "n", "version": "1.0.0",
            "capabilities": ["context"],
        })
    assert caught.value.code == PLUGIN_MANIFEST_INVALID


def test_unknown_permission_is_rejected():
    with pytest.raises(PluginContractError) as caught:
        parse_plugin_manifest({
            "id": "ab", "name": "n", "version": "1.0.0",
            "requested_permissions": ["novel.read"],
        })
    assert caught.value.code == PLUGIN_MANIFEST_INVALID


def test_unknown_fields_are_rejected():
    with pytest.raises(PluginContractError) as caught:
        parse_plugin_manifest({"id": "ab", "name": "n", "version": "1.0.0", "extra_hook": True})
    assert caught.value.code == PLUGIN_MANIFEST_INVALID


@pytest.mark.parametrize("field", sorted(FORBIDDEN_EXECUTION_FIELDS))
def test_execution_entry_fields_are_rejected(field):
    payload = {"id": "ab", "name": "n", "version": "1.0.0", field: "payload"}
    with pytest.raises(PluginContractError) as caught:
        parse_plugin_manifest(payload)
    assert caught.value.code == PLUGIN_MANIFEST_INVALID


@pytest.mark.parametrize("version", ["2.0", "0.9", 2, "1"])
def test_unsupported_manifest_version(version):
    with pytest.raises(PluginContractError) as caught:
        parse_plugin_manifest({"id": "ab", "name": "n", "version": "1.0.0", "manifest_version": version})
    assert caught.value.code == PLUGIN_MANIFEST_UNSUPPORTED_VERSION


def test_publisher_is_unverified_metadata_not_a_signature():
    manifest = parse_plugin_manifest({
        "id": "ab", "name": "n", "version": "1.0.0", "publisher": "Someone",
    })
    dumped = manifest.public_dump()
    assert dumped["publisher"] == "Someone"
    assert "signed" not in json.dumps(dumped).casefold()
    assert dumped.get("publisher_verified") is None


def test_canonical_manifest_hash_ignores_whitespace_and_key_order():
    first = parse_plugin_manifest({
        "version": "1.2.3", "id": "story-tools", "name": "故事工具",
        "capabilities": ["writing_tool"], "requested_permissions": ["project.read"],
    })
    second = parse_plugin_manifest(json.loads('{"name":"故事工具","requested_permissions":["project.read"],"id":"story-tools","capabilities":["writing_tool"],"version":"1.2.3"}'))
    assert canonical_manifest_sha256(first) == canonical_manifest_sha256(second)
    assert first.canonical_json() == json.dumps(first.public_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def test_legal_relative_resource_path():
    assert validate_declarative_relative_path("resources/writing-preset.json") == "resources/writing-preset.json"


@pytest.mark.parametrize("path", [
    "../secret.json",
    "resources/../secret.json",
    "..%2fsecret.json",
    "%2e%2e/secret.json",
    "%2e%2e%2fsecret.json",
    "resources/%2e%2e/x.json",
])
def test_dotdot_and_encoded_traversal_rejected(path):
    with pytest.raises(PluginContractError) as caught:
        validate_declarative_relative_path(path)
    assert caught.value.code == PLUGIN_RESOURCE_PATH_INVALID


@pytest.mark.parametrize("path", [
    "..\\secret.json",
    "resources\\writing-preset.json",
    "resources/..\\secret.json",
])
def test_backslash_traversal_rejected(path):
    with pytest.raises(PluginContractError) as caught:
        validate_declarative_relative_path(path)
    assert caught.value.code == PLUGIN_RESOURCE_PATH_INVALID


@pytest.mark.parametrize("path", [
    "C:\\Windows\\file.json",
    "C:/Windows/file.json",
    "\\\\server\\share\\file.json",
    "//server/share/file.json",
    "/tmp/file.json",
    "/etc/passwd.json",
])
def test_windows_drive_unc_and_absolute_rejected(path):
    with pytest.raises(PluginContractError) as caught:
        validate_declarative_relative_path(path)
    assert caught.value.code in {PLUGIN_RESOURCE_PATH_INVALID, PLUGIN_RESOURCE_TYPE_UNSUPPORTED}


def test_unsupported_resource_file_type():
    with pytest.raises(PluginContractError) as caught:
        validate_declarative_relative_path("resources/run.py")
    assert caught.value.code == PLUGIN_RESOURCE_TYPE_UNSUPPORTED


def test_schema_is_generated_from_pydantic_and_rejects_drift():
    generated = canonical_manifest_schema()
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert generated == committed
    assert committed["additionalProperties"] is False
    fields = set(PluginManifestV1.model_fields)
    assert fields == set(committed["properties"])
    assert "entrypoint" not in committed["properties"]
    for field in FORBIDDEN_EXECUTION_FIELDS:
        assert field not in committed["properties"]


def test_example_manifest_satisfies_pydantic_and_json_schema_shape():
    payload = example_manifest()
    parse_plugin_manifest(payload)
    schema = canonical_manifest_schema()
    for key in payload:
        assert key in schema["properties"]
    extra = set(payload) - set(schema["properties"])
    assert extra == set()
    for required in schema["required"]:
        assert required in payload


def test_schema_detects_added_or_removed_model_field():
    schema_fields = set(canonical_manifest_schema()["properties"])
    model_fields = set(PluginManifestV1.model_fields)
    assert schema_fields == model_fields


def test_resource_count_limit_is_enforced_by_contract():
    resources = [
        {
            "kind": "writing_presets",
            "relative_path": f"resources/p{i}.json",
            "sha256": "a" * 64,
            "media_type": "application/json",
        }
        for i in range(MAX_RESOURCE_COUNT + 1)
    ]
    with pytest.raises(PluginContractError) as caught:
        parse_plugin_manifest({"id": "ab", "name": "n", "version": "1.0.0", "resources": resources})
    assert caught.value.code in {PLUGIN_MANIFEST_INVALID, "PLUGIN_RESOURCE_TOO_LARGE"}


def test_resource_limit_constants():
    assert MAX_RESOURCE_COUNT == 100
    assert PluginManifestV1.model_fields["resources"] is not None


def test_plugin_contract_modules_contain_no_code_execution_hooks():
    for relative in ("app/plugin_contracts.py", "app/plugin_discovery.py"):
        source = (REPO / relative).read_text(encoding="utf-8")
        stripped = source.replace("re.compile(", "")
        assert "subprocess" not in stripped
        assert "os.system" not in stripped
        assert "importlib" not in stripped
        assert "eval(" not in stripped
        assert "exec(" not in stripped
        assert "compile(" not in stripped
