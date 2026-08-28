"""Secure local discovery of declarative plugin packages.

Discovery only reads files under a host-controlled plugins root. It never
executes plugin code, follows escaped symlinks, returns absolute paths, or
surfaces raw exception text.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .plugin_contracts import (
    MAX_MANIFEST_BYTES,
    MAX_RESOURCE_BYTES,
    MAX_RESOURCE_COUNT,
    MAX_TOTAL_RESOURCE_BYTES,
    PLUGIN_MANIFEST_INVALID,
    PLUGIN_RESOURCE_HASH_MISMATCH,
    PLUGIN_RESOURCE_INVALID_JSON,
    PLUGIN_RESOURCE_PATH_INVALID,
    PLUGIN_RESOURCE_SYMLINK_REJECTED,
    PLUGIN_RESOURCE_TOO_LARGE,
    PluginContractError,
    PluginManifestV1,
    PluginResourceRef,
    SAFE_ERROR_MESSAGES,
    parse_plugin_manifest,
    resource_id_for,
    safe_error,
    validate_declarative_relative_path,
)

_SAFE_DIR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")


def safe_plugin_dir_id(name: str) -> str:
    if _SAFE_DIR_RE.fullmatch(name or ""):
        return name
    digest = hashlib.sha256((name or "").encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"invalid-{digest}"


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _reject_symlink_escape(path: Path, root: Path) -> None:
    """Fail closed on symlink/reparse points that leave the plugin root."""
    try:
        resolved_root = root.resolve()
    except OSError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID) from exc
    current = path
    seen: set[Path] = set()
    while True:
        if current in seen:
            raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
        seen.add(current)
        try:
            if current.is_symlink():
                try:
                    resolved = current.resolve()
                except OSError as exc:
                    raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED) from exc
                if not _is_within(resolved_root, resolved):
                    raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
                # Resource files themselves must not be symlinks, even in-tree.
                if current == path:
                    raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
        except PluginContractError:
            raise
        except OSError as exc:
            raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID) from exc
        if current == resolved_root or current.parent == current:
            break
        current = current.parent


def resolve_plugin_file(plugin_root: Path, relative_path: str) -> Path:
    validate_declarative_relative_path(relative_path)
    try:
        resolved_root = plugin_root.resolve()
    except OSError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID) from exc
    candidate = plugin_root.joinpath(*relative_path.split("/"))
    _reject_symlink_escape(candidate, resolved_root)
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID) from exc
    if not _is_within(resolved_root, resolved):
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    if resolved.is_symlink() or candidate.is_symlink():
        raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
    return resolved


def read_declarative_json(path: Path, *, max_bytes: int) -> tuple[bytes, Any]:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID) from exc
    if size > max_bytes:
        raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID) from exc
    if len(data) > max_bytes:
        raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
    try:
        parsed = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PluginContractError(PLUGIN_RESOURCE_INVALID_JSON) from exc
    if not isinstance(parsed, (dict, list)):
        raise PluginContractError(PLUGIN_RESOURCE_INVALID_JSON)
    return data, parsed


def verify_resource(plugin_root: Path, resource: PluginResourceRef) -> dict[str, Any]:
    path = resolve_plugin_file(plugin_root, resource.relative_path)
    if not path.is_file() or path.is_symlink():
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    data, parsed = read_declarative_json(path, max_bytes=MAX_RESOURCE_BYTES)
    digest = hashlib.sha256(data).hexdigest()
    if digest != resource.sha256.lower():
        raise PluginContractError(PLUGIN_RESOURCE_HASH_MISMATCH)
    if resource.media_type and resource.media_type != "application/json":
        raise PluginContractError(PLUGIN_RESOURCE_TYPE_UNSUPPORTED)
    return {
        "resource_id": resource_id_for(resource.relative_path),
        "kind": resource.kind,
        "relative_path": resource.relative_path,
        "sha256": digest,
        "schema_version": resource.schema_version,
        "media_type": resource.media_type or "application/json",
        "size": len(data),
        "data": parsed,
    }


def verify_manifest_resources(plugin_root: Path, manifest: PluginManifestV1) -> list[dict[str, Any]]:
    if len(manifest.resources) > MAX_RESOURCE_COUNT:
        raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
    verified: list[dict[str, Any]] = []
    total = 0
    for resource in manifest.resources:
        item = verify_resource(plugin_root, resource)
        total += int(item["size"])
        if total > MAX_TOTAL_RESOURCE_BYTES:
            raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
        verified.append(item)
    return verified


def load_plugin_package(plugin_root: Path) -> tuple[PluginManifestV1, list[dict[str, Any]]]:
    manifest_path = plugin_root / "manifest.json"
    if manifest_path.is_symlink():
        raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
    _reject_symlink_escape(manifest_path, plugin_root)
    data, parsed = read_declarative_json(manifest_path, max_bytes=MAX_MANIFEST_BYTES)
    if not isinstance(parsed, dict):
        raise PluginContractError(PLUGIN_MANIFEST_INVALID)
    # Never execute, import, or evaluate strings inside the JSON document.
    del data
    manifest = parse_plugin_manifest(parsed)
    verified = verify_manifest_resources(plugin_root, manifest)
    return manifest, verified


def _public_item(plugin_dir: str, *, manifest: PluginManifestV1 | None = None,
                 error_code: str | None = None) -> dict[str, Any]:
    item: dict[str, Any] = {
        "plugin_dir": plugin_dir,
        "path": plugin_dir,
        "publisher_verified": False,
        "execution_supported": False,
        "isolation": "DENY_ALL",
    }
    if manifest is not None:
        item["manifest"] = manifest.public_dump()
        item["resource_count"] = len(manifest.resources)
        item["resource_kinds"] = sorted({resource.kind for resource in manifest.resources})
        item["publisher_trust"] = "unverified"
    if error_code is not None:
        item.update(safe_error(error_code))
    return item


def discover_installed_plugins(root: Path) -> dict[str, Any]:
    """Scan one controlled plugins root. A single bad package cannot block others."""
    empty = {
        "items": [],
        "execution_supported": False,
        "sandbox": "NOT_CONFIGURED",
        "isolation": "DENY_ALL",
    }
    configured = Path(root)
    if not configured.exists():
        return empty
    try:
        resolved_root = configured.resolve()
    except OSError:
        return empty
    if configured.is_symlink() and not _is_within(configured.parent.resolve(), resolved_root):
        return empty
    items: list[dict[str, Any]] = []
    try:
        candidates = sorted(configured.glob("*/manifest.json"))
    except OSError:
        return empty
    for manifest_path in candidates:
        plugin_dir = safe_plugin_dir_id(manifest_path.parent.name)
        try:
            package_root = manifest_path.parent
            if package_root.is_symlink():
                try:
                    resolved_package = package_root.resolve()
                except OSError as exc:
                    raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED) from exc
                if not _is_within(resolved_root, resolved_package):
                    raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
            manifest, _verified = load_plugin_package(package_root)
            items.append(_public_item(plugin_dir, manifest=manifest))
        except PluginContractError as exc:
            items.append(_public_item(plugin_dir, error_code=exc.code))
        except Exception:
            items.append(_public_item(plugin_dir, error_code=PLUGIN_MANIFEST_INVALID))
    return {**empty, "items": items, "total": len(items)}
