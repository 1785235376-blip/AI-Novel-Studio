"""Read-only catalog of declarative plugin resources.

Every read re-validates path, type, size and SHA-256 against the live files
under the host-controlled plugins root. Sidecar rows are never trusted as a
substitute for that check. This module does not execute plugin code, cache
unverified bytes, fetch URLs, render HTML, or write plugin files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import settings
from .plugin_contracts import (
    PLUGIN_ID_DUPLICATE,
    PLUGIN_ID_RE,
    PLUGIN_MANIFEST_DRIFT,
    PLUGIN_MANIFEST_INVALID,
    PLUGIN_RESOURCE_PATH_INVALID,
    PLUGIN_RESOURCE_TOO_LARGE,
    PluginContractError,
    PluginManifestV1,
    resource_id_for,
    safe_error,
)
from .plugin_discovery import (
    identity_matches,
    preflight_resource_budget,
    sidecar_has_identity,
    unique_package_for_plugin_id,
    verify_resource,
    verify_manifest_resources,
)

_HTML_TAG_RE = re.compile(r"<[^>]*>")
_RESOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
_UNSAFE_SCHEME_RE = re.compile(r"(javascript|data|vbscript)\s*:", re.IGNORECASE)

ACTIVE_PLUGIN_STATUS = "MANIFEST_ACTIVE"
REVIEW_REQUIRED_STATUS = "REVIEW_REQUIRED"
MANIFEST_DRIFT_STATUS = "MANIFEST_DRIFT"


def _plugins_root() -> Path:
    return settings.data_path() / "plugins"


def _capability_service():
    from .dependencies import v1_capability_service
    return v1_capability_service


def _empty_catalog(plugin_id: str, *, visible: bool = False, status: str | None = None,
                   error_code: str | None = None, validation_status: str = "UNAVAILABLE") -> dict[str, Any]:
    payload: dict[str, Any] = {
        "plugin_id": plugin_id,
        "items": [],
        "total": 0,
        "visible": visible,
        "validated": False,
        "validation_status": validation_status,
        "invalid_resource_count": 0,
        "execution_supported": False,
        "isolation": "DENY_ALL",
        "publisher_verified": False,
    }
    if status:
        payload["status"] = status
    if error_code:
        payload.update(safe_error(error_code))
    return payload


def resolve_active_package(plugin: dict[str, Any]) -> tuple[Path, PluginManifestV1]:
    plugin_id = _validate_plugin_id(str(plugin.get("id") or ""))
    if not sidecar_has_identity(plugin) or plugin.get("status") == REVIEW_REQUIRED_STATUS:
        raise PluginContractError(PLUGIN_MANIFEST_INVALID)
    package_root, manifest = unique_package_for_plugin_id(plugin_id, _plugins_root())
    if not identity_matches(manifest, plugin):
        raise PluginContractError(PLUGIN_MANIFEST_DRIFT)
    return package_root, manifest


def assert_activation_identity(plugin: dict[str, Any]) -> None:
    """Fail closed unless exactly one on-disk package matches the reviewed identity."""
    package_root, manifest = resolve_active_package(plugin)
    verify_manifest_resources(package_root, manifest)


def find_plugin_package(plugin_id: str, root: Path | None = None) -> Path | None:
    """Locate the unique package whose manifest id matches. Live scan; no path cache."""
    plugin_id = _validate_plugin_id(plugin_id)
    try:
        package_root, _manifest = unique_package_for_plugin_id(plugin_id, root or _plugins_root())
    except PluginContractError:
        return None
    return package_root


def plain_text(value: Any, limit: int = 240) -> str:
    """Coerce a JSON field into plain text. Tags are stripped, not rendered."""
    if not isinstance(value, str):
        return ""
    text = value.replace("\x00", "")
    text = _HTML_TAG_RE.sub("", text)
    text = _UNSAFE_SCHEME_RE.sub("", text)
    return text.strip()[:limit]


def _summary_name(resource_id: str, data: Any) -> str:
    if isinstance(data, dict):
        name = plain_text(data.get("name"), 160)
        if name:
            return name
    leaf = resource_id.rsplit(":", 1)[-1]
    if leaf.lower().endswith(".json"):
        leaf = leaf[:-5]
    return plain_text(leaf, 160)


def _summary_description(data: Any) -> str:
    if isinstance(data, dict):
        return plain_text(data.get("description"), 400)
    return ""


def _schema_version(resource_schema: str, data: Any) -> str:
    if resource_schema:
        return plain_text(resource_schema, 40)
    if isinstance(data, dict):
        return plain_text(data.get("schema_version"), 40)
    return ""


def public_resource(plugin_id: str, verified: dict[str, Any], *, include_data: bool) -> dict[str, Any]:
    data = verified.get("data")
    name = _summary_name(verified["resource_id"], data)
    description = _summary_description(data)
    schema_version = _schema_version(str(verified.get("schema_version") or ""), data)
    digest = str(verified.get("sha256") or "")
    payload: dict[str, Any] = {
        "plugin_id": plugin_id,
        "resource_id": verified["resource_id"],
        "kind": verified["kind"],
        "name": name,
        "description": description,
        "schema_version": schema_version,
        "sha256": digest,
        "validated": True,
        "summary": {
            "kind": verified["kind"],
            "name": name,
            "description": description,
            "schema_version": schema_version,
            "sha256_short": digest[:12],
        },
        "execution_supported": False,
    }
    if include_data:
        payload["data"] = data
    return payload


def _validate_plugin_id(plugin_id: str) -> str:
    if not isinstance(plugin_id, str) or not PLUGIN_ID_RE.fullmatch(plugin_id):
        raise FileNotFoundError(plugin_id or "plugin")
    return plugin_id


def _validate_resource_id(resource_id: str) -> str:
    if not isinstance(resource_id, str) or not _RESOURCE_ID_RE.fullmatch(resource_id):
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    if ".." in resource_id or "/" in resource_id or "\\" in resource_id:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    return resource_id


def _registered_plugin(plugin_id: str) -> dict[str, Any]:
    return _capability_service().get_plugin(plugin_id)


def _is_active(plugin: dict[str, Any]) -> bool:
    return plugin.get("status") == ACTIVE_PLUGIN_STATUS and sidecar_has_identity(plugin)


def _verify_live_resources(plugin_id: str, package_root: Path, manifest: PluginManifestV1) -> tuple[list[dict[str, Any]], int]:
    """Re-verify each resource independently. One failure cannot hide others."""
    items: list[dict[str, Any]] = []
    invalid = 0
    for resource in manifest.resources:
        try:
            verified = verify_resource(package_root, resource)
        except (PluginContractError, OSError, RecursionError, ValueError):
            invalid += 1
            continue
        items.append(public_resource(plugin_id, verified, include_data=False))
    return items, invalid


def list_plugin_resources(plugin_id: str) -> dict[str, Any]:
    plugin_id = _validate_plugin_id(plugin_id)
    plugin = _registered_plugin(plugin_id)
    if plugin.get("status") == REVIEW_REQUIRED_STATUS or not sidecar_has_identity(plugin):
        return _empty_catalog(plugin_id, visible=False, status=REVIEW_REQUIRED_STATUS, validation_status="REVIEW_REQUIRED")
    if not _is_active(plugin):
        return _empty_catalog(plugin_id, visible=False, status=str(plugin.get("status") or "REGISTERED"))
    try:
        package_root, manifest = resolve_active_package(plugin)
    except PluginContractError as exc:
        if exc.code == PLUGIN_ID_DUPLICATE:
            return _empty_catalog(
                plugin_id, visible=True, status=PLUGIN_ID_DUPLICATE,
                error_code=PLUGIN_ID_DUPLICATE, validation_status="DUPLICATE",
            )
        if exc.code == PLUGIN_MANIFEST_DRIFT:
            return _empty_catalog(
                plugin_id, visible=True, status=MANIFEST_DRIFT_STATUS,
                error_code=PLUGIN_MANIFEST_DRIFT, validation_status="DRIFT",
            )
        return _empty_catalog(plugin_id, visible=True, validation_status="MISSING")
    try:
        preflight_resource_budget(package_root, manifest)
    except PluginContractError as exc:
        return _empty_catalog(
            plugin_id, visible=True, status=ACTIVE_PLUGIN_STATUS,
            error_code=exc.code, validation_status="BUDGET",
        )
    items, invalid = _verify_live_resources(plugin_id, package_root, manifest)
    if invalid:
        status = "PARTIAL" if items else "FAILED"
        return {
            "plugin_id": plugin_id,
            "items": items,
            "total": len(items),
            "visible": True,
            "validated": False,
            "validation_status": status,
            "invalid_resource_count": invalid,
            "execution_supported": False,
            "isolation": "DENY_ALL",
            "publisher_verified": False,
            "resource_kinds": sorted({item["kind"] for item in items}),
            "resource_count": len(items),
            "status": ACTIVE_PLUGIN_STATUS,
        }
    return {
        "plugin_id": plugin_id,
        "items": items,
        "total": len(items),
        "visible": True,
        "validated": True,
        "validation_status": "VALIDATED",
        "invalid_resource_count": 0,
        "execution_supported": False,
        "isolation": "DENY_ALL",
        "publisher_verified": False,
        "resource_kinds": sorted({item["kind"] for item in items}),
        "resource_count": len(items),
        "status": ACTIVE_PLUGIN_STATUS,
    }


def get_plugin_resource(plugin_id: str, resource_id: str) -> dict[str, Any]:
    plugin_id = _validate_plugin_id(plugin_id)
    resource_id = _validate_resource_id(resource_id)
    plugin = _registered_plugin(plugin_id)
    if plugin.get("status") == REVIEW_REQUIRED_STATUS or not sidecar_has_identity(plugin):
        raise FileNotFoundError(plugin_id)
    if not _is_active(plugin):
        raise FileNotFoundError(plugin_id)
    try:
        package_root, manifest = resolve_active_package(plugin)
        preflight_resource_budget(package_root, manifest)
    except PluginContractError as exc:
        if exc.code in {PLUGIN_MANIFEST_DRIFT, PLUGIN_ID_DUPLICATE}:
            raise
        if exc.code == PLUGIN_RESOURCE_TOO_LARGE:
            raise
        raise FileNotFoundError(resource_id) from None
    target = next((resource for resource in manifest.resources
                   if resource_id_for(resource.relative_path) == resource_id), None)
    if target is None:
        raise FileNotFoundError(resource_id)
    verified = verify_resource(package_root, target)
    return public_resource(plugin_id, verified, include_data=True)


class DeclarativePluginCatalog:
    """Facade kept for callers that prefer an object over module functions."""

    def list_resources(self, plugin_id: str) -> dict[str, Any]:
        return list_plugin_resources(plugin_id)

    def get_resource(self, plugin_id: str, resource_id: str) -> dict[str, Any]:
        return get_plugin_resource(plugin_id, resource_id)


plugin_catalog = DeclarativePluginCatalog()
