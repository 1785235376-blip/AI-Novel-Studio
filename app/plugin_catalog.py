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
    PLUGIN_ID_RE,
    PLUGIN_RESOURCE_PATH_INVALID,
    PluginContractError,
    PluginManifestV1,
    resource_id_for,
)
from .plugin_discovery import (
    _is_within,
    load_plugin_manifest,
    verify_resource,
)

_HTML_TAG_RE = re.compile(r"<[^>]*>")
_RESOURCE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$")
_UNSAFE_SCHEME_RE = re.compile(r"(javascript|data|vbscript)\s*:", re.IGNORECASE)

ACTIVE_PLUGIN_STATUS = "MANIFEST_ACTIVE"


def _plugins_root() -> Path:
    return settings.data_path() / "plugins"


def _capability_service():
    from .dependencies import v1_capability_service
    return v1_capability_service


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


def _iter_package_roots(root: Path) -> list[Path]:
    if not root.exists():
        return []
    try:
        resolved_root = root.resolve()
    except OSError:
        return []
    try:
        candidates = sorted(root.glob("*/manifest.json"))
    except OSError:
        return []
    packages: list[Path] = []
    for manifest_path in candidates:
        package_root = manifest_path.parent
        try:
            if package_root.is_symlink():
                resolved_package = package_root.resolve()
                if not _is_within(resolved_root, resolved_package):
                    continue
            packages.append(package_root)
        except OSError:
            continue
    return packages


def find_plugin_package(plugin_id: str, root: Path | None = None) -> Path | None:
    """Locate a package whose manifest id matches. Live scan; no path cache."""
    plugin_id = _validate_plugin_id(plugin_id)
    for package_root in _iter_package_roots(root or _plugins_root()):
        try:
            manifest = load_plugin_manifest(package_root)
        except PluginContractError:
            continue
        except Exception:
            continue
        if manifest.id == plugin_id:
            return package_root
    return None


def _registered_plugin(plugin_id: str) -> dict[str, Any]:
    return _capability_service().get_plugin(plugin_id)


def _is_active(plugin: dict[str, Any]) -> bool:
    return plugin.get("status") == ACTIVE_PLUGIN_STATUS


def _verify_live_resources(plugin_id: str, package_root: Path, manifest: PluginManifestV1) -> list[dict[str, Any]]:
    """Re-verify each resource independently. One failure cannot hide others."""
    items: list[dict[str, Any]] = []
    for resource in manifest.resources:
        try:
            verified = verify_resource(package_root, resource)
        except PluginContractError:
            continue
        except OSError:
            continue
        items.append(public_resource(plugin_id, verified, include_data=False))
    return items


def list_plugin_resources(plugin_id: str) -> dict[str, Any]:
    plugin_id = _validate_plugin_id(plugin_id)
    plugin = _registered_plugin(plugin_id)
    empty = {
        "plugin_id": plugin_id,
        "items": [],
        "total": 0,
        "visible": False,
        "validated": False,
        "execution_supported": False,
        "isolation": "DENY_ALL",
        "publisher_verified": False,
    }
    if not _is_active(plugin):
        return empty
    package_root = find_plugin_package(plugin_id)
    if package_root is None:
        return {**empty, "visible": True}
    try:
        manifest = load_plugin_manifest(package_root)
    except PluginContractError:
        return {**empty, "visible": True}
    if manifest.id != plugin_id:
        return {**empty, "visible": True}
    items = _verify_live_resources(plugin_id, package_root, manifest)
    return {
        "plugin_id": plugin_id,
        "items": items,
        "total": len(items),
        "visible": True,
        "validated": True,
        "execution_supported": False,
        "isolation": "DENY_ALL",
        "publisher_verified": False,
        "resource_kinds": sorted({item["kind"] for item in items}),
        "resource_count": len(items),
    }


def get_plugin_resource(plugin_id: str, resource_id: str) -> dict[str, Any]:
    plugin_id = _validate_plugin_id(plugin_id)
    resource_id = _validate_resource_id(resource_id)
    plugin = _registered_plugin(plugin_id)
    if not _is_active(plugin):
        raise FileNotFoundError(plugin_id)
    package_root = find_plugin_package(plugin_id)
    if package_root is None:
        raise FileNotFoundError(resource_id)
    try:
        manifest = load_plugin_manifest(package_root)
    except PluginContractError as exc:
        raise FileNotFoundError(resource_id) from exc
    target = next((resource for resource in manifest.resources
                   if resource_id_for(resource.relative_path) == resource_id), None)
    if target is None:
        raise FileNotFoundError(resource_id)
    try:
        verified = verify_resource(package_root, target)
    except PluginContractError:
        raise
    payload = public_resource(plugin_id, verified, include_data=True)
    return payload


class DeclarativePluginCatalog:
    """Facade kept for callers that prefer an object over module functions."""

    def list_resources(self, plugin_id: str) -> dict[str, Any]:
        return list_plugin_resources(plugin_id)

    def get_resource(self, plugin_id: str, resource_id: str) -> dict[str, Any]:
        return get_plugin_resource(plugin_id, resource_id)


plugin_catalog = DeclarativePluginCatalog()
