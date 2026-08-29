"""Secure local discovery of declarative plugin packages.

Discovery only reads files under a host-controlled plugins root. It never
executes plugin code, follows escaped symlinks, returns absolute paths, or
surfaces raw exception text.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .plugin_contracts import (
    MAX_JSON_DEPTH,
    MAX_MANIFEST_BYTES,
    MAX_RESOURCE_BYTES,
    MAX_RESOURCE_COUNT,
    MAX_TOTAL_RESOURCE_BYTES,
    PLUGIN_ID_DUPLICATE,
    PLUGIN_MANIFEST_DRIFT,
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
    canonical_manifest_sha256,
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


def json_nesting_depth(value: Any, *, limit: int = MAX_JSON_DEPTH) -> int:
    stack: list[tuple[Any, int]] = [(value, 1)]
    deepest = 0
    while stack:
        current, depth = stack.pop()
        if depth > limit:
            return depth
        deepest = max(deepest, depth)
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)
    return deepest


def parse_declarative_json(data: bytes, *, max_depth: int | None = None) -> Any:
    limit = MAX_JSON_DEPTH if max_depth is None else max_depth
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_INVALID_JSON) from exc
    try:
        parsed = json.loads(text)
    except RecursionError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_INVALID_JSON) from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise PluginContractError(PLUGIN_RESOURCE_INVALID_JSON) from exc
    if not isinstance(parsed, (dict, list)):
        raise PluginContractError(PLUGIN_RESOURCE_INVALID_JSON)
    if json_nesting_depth(parsed, limit=limit) > limit:
        raise PluginContractError(PLUGIN_RESOURCE_INVALID_JSON)
    return parsed


def read_capped_bytes(path: Path, *, max_bytes: int) -> bytes:
    """Read at most max_bytes from a regular file. Does not parse JSON."""
    try:
        if path.is_symlink():
            raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
        with path.open("rb") as handle:
            data = handle.read(max_bytes + 1)
    except PluginContractError:
        raise
    except OSError as exc:
        raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID) from exc
    if len(data) > max_bytes:
        raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
    return data


def read_declarative_json(path: Path, *, max_bytes: int) -> tuple[bytes, Any]:
    data = read_capped_bytes(path, max_bytes=max_bytes)
    parsed = parse_declarative_json(data)
    return data, parsed


def preflight_resource_budget(
    plugin_root: Path,
    manifest: PluginManifestV1,
    *,
    max_file: int | None = None,
    max_count: int | None = None,
    max_total: int | None = None,
) -> int:
    """Stat measurable resources as a fast reject before the read-once snapshot.

    Only count, per-file size and total size may fail the whole package
    (`PLUGIN_RESOURCE_TOO_LARGE`). Missing files, path errors, symlinks and
    other per-resource faults are skipped here so catalog isolation can keep
    valid siblings. Unmeasurable files contribute nothing to the total.
    Stat size is not the security boundary; `snapshot_manifest_resources`
    re-reads actual bytes and accounts them before JSON is parsed.
    """
    file_limit = MAX_RESOURCE_BYTES if max_file is None else max_file
    count_limit = MAX_RESOURCE_COUNT if max_count is None else max_count
    total_limit = MAX_TOTAL_RESOURCE_BYTES if max_total is None else max_total
    if len(manifest.resources) > count_limit:
        raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
    total = 0
    for resource in manifest.resources:
        try:
            path = resolve_plugin_file(plugin_root, resource.relative_path)
            size = path.stat().st_size
        except (PluginContractError, OSError):
            continue
        if size > file_limit:
            raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
        total += size
        if total > total_limit:
            raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
    return total


@dataclass(frozen=True, slots=True)
class ResourceByteSnapshot:
    """Bytes taken from one resource file, or the per-resource fault that blocked the read."""

    resource: PluginResourceRef
    data: bytes | None = None
    error: PluginContractError | None = None


def snapshot_resource_bytes(
    plugin_root: Path,
    resource: PluginResourceRef,
    *,
    max_file: int | None = None,
) -> ResourceByteSnapshot:
    """Resolve and read one resource once. Per-file over-budget fails the package."""
    file_limit = MAX_RESOURCE_BYTES if max_file is None else max_file
    try:
        path = resolve_plugin_file(plugin_root, resource.relative_path)
        if not path.is_file() or path.is_symlink():
            raise PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
        data = read_capped_bytes(path, max_bytes=file_limit)
        return ResourceByteSnapshot(resource=resource, data=data)
    except PluginContractError as exc:
        if exc.code == PLUGIN_RESOURCE_TOO_LARGE:
            raise
        return ResourceByteSnapshot(resource=resource, error=exc)
    except OSError:
        return ResourceByteSnapshot(
            resource=resource,
            error=PluginContractError(PLUGIN_RESOURCE_PATH_INVALID),
        )


def snapshot_manifest_resources(
    plugin_root: Path,
    manifest: PluginManifestV1,
    *,
    max_file: int | None = None,
    max_count: int | None = None,
    max_total: int | None = None,
) -> list[ResourceByteSnapshot]:
    """Read each resource once and account actual bytes before any JSON parse.

    Hash-mismatched and invalid JSON payloads still count. Unreadable files
    (missing, path, symlink) do not. Exceeding the total raises
    `PLUGIN_RESOURCE_TOO_LARGE` without parsing resource JSON.
    """
    file_limit = MAX_RESOURCE_BYTES if max_file is None else max_file
    count_limit = MAX_RESOURCE_COUNT if max_count is None else max_count
    total_limit = MAX_TOTAL_RESOURCE_BYTES if max_total is None else max_total
    if len(manifest.resources) > count_limit:
        raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
    preflight_resource_budget(
        plugin_root, manifest, max_file=file_limit, max_count=count_limit, max_total=total_limit,
    )
    snapshots: list[ResourceByteSnapshot] = []
    total = 0
    for resource in manifest.resources:
        snapshot = snapshot_resource_bytes(plugin_root, resource, max_file=file_limit)
        if snapshot.data is not None:
            total += len(snapshot.data)
            if total > total_limit:
                raise PluginContractError(PLUGIN_RESOURCE_TOO_LARGE)
        snapshots.append(snapshot)
    return snapshots


def verify_resource_snapshot(snapshot: ResourceByteSnapshot) -> dict[str, Any]:
    """Verify identity of already-read bytes. Call only after package budget passed."""
    if snapshot.error is not None or snapshot.data is None:
        raise snapshot.error or PluginContractError(PLUGIN_RESOURCE_PATH_INVALID)
    resource = snapshot.resource
    data = snapshot.data
    digest = hashlib.sha256(data).hexdigest()
    if digest != resource.sha256.lower():
        raise PluginContractError(PLUGIN_RESOURCE_HASH_MISMATCH)
    if resource.media_type and resource.media_type != "application/json":
        raise PluginContractError(PLUGIN_RESOURCE_TYPE_UNSUPPORTED)
    parsed = parse_declarative_json(data)
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
    snapshots = snapshot_manifest_resources(plugin_root, manifest)
    return [verify_resource_snapshot(snapshot) for snapshot in snapshots]


def verify_resource(plugin_root: Path, resource: PluginResourceRef) -> dict[str, Any]:
    snapshot = snapshot_resource_bytes(plugin_root, resource)
    return verify_resource_snapshot(snapshot)


def load_plugin_manifest(plugin_root: Path) -> PluginManifestV1:
    """Load and parse manifest.json without verifying resource payloads."""
    manifest_path = plugin_root / "manifest.json"
    if manifest_path.is_symlink():
        raise PluginContractError(PLUGIN_RESOURCE_SYMLINK_REJECTED)
    _reject_symlink_escape(manifest_path, plugin_root)
    data, parsed = read_declarative_json(manifest_path, max_bytes=MAX_MANIFEST_BYTES)
    if not isinstance(parsed, dict):
        raise PluginContractError(PLUGIN_MANIFEST_INVALID)
    # Never execute, import, or evaluate strings inside the JSON document.
    del data
    return parse_plugin_manifest(parsed)


def load_plugin_package(plugin_root: Path) -> tuple[PluginManifestV1, list[dict[str, Any]]]:
    manifest = load_plugin_manifest(plugin_root)
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


def identity_snapshot(manifest: PluginManifestV1) -> dict[str, Any]:
    dump = manifest.public_dump()
    return {
        "plugin_version": dump["version"],
        "manifest_sha256": canonical_manifest_sha256(manifest),
        "capabilities": list(dump.get("capabilities") or []),
        "requested_permissions": list(dump.get("requested_permissions") or []),
        "resources": list(dump.get("resources") or []),
    }


def identity_matches(manifest: PluginManifestV1, sidecar: dict[str, Any]) -> bool:
    if not sidecar.get("plugin_version") or not sidecar.get("manifest_sha256"):
        return False
    live = identity_snapshot(manifest)
    if live["plugin_version"] != sidecar.get("plugin_version"):
        return False
    if live["manifest_sha256"] != sidecar.get("manifest_sha256"):
        return False
    if live["capabilities"] != list(sidecar.get("capabilities") or []):
        return False
    if live["requested_permissions"] != list(sidecar.get("requested_permissions") or []):
        return False
    if live["resources"] != list(sidecar.get("resources") or []):
        return False
    return True


def sidecar_has_identity(sidecar: dict[str, Any]) -> bool:
    version = sidecar.get("plugin_version")
    digest = sidecar.get("manifest_sha256")
    return isinstance(version, str) and bool(version) and isinstance(digest, str) and len(digest) == 64


def iter_plugin_packages(root: Path) -> list[Path]:
    configured = Path(root)
    if not configured.exists():
        return []
    try:
        resolved_root = configured.resolve()
    except OSError:
        return []
    try:
        candidates = sorted(configured.glob("*/manifest.json"))
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


def load_declared_packages(root: Path) -> list[tuple[str, Path, PluginManifestV1 | None, str | None]]:
    """Return (dir_id, path, manifest|None, error_code|None) for each candidate.

    Identity is taken from the parsed manifest only. Resource bytes are verified
    later so a single hash mismatch cannot hide a duplicate or drift check.
    """
    declared: list[tuple[str, Path, PluginManifestV1 | None, str | None]] = []
    for package_root in iter_plugin_packages(root):
        plugin_dir = safe_plugin_dir_id(package_root.name)
        try:
            manifest = load_plugin_manifest(package_root)
            declared.append((plugin_dir, package_root, manifest, None))
        except PluginContractError as exc:
            declared.append((plugin_dir, package_root, None, exc.code))
        except Exception:
            declared.append((plugin_dir, package_root, None, PLUGIN_MANIFEST_INVALID))
    return declared


def packages_for_plugin_id(plugin_id: str, root: Path) -> list[tuple[Path, PluginManifestV1]]:
    matches: list[tuple[Path, PluginManifestV1]] = []
    for _dir_id, package_root, manifest, error_code in load_declared_packages(root):
        if error_code or manifest is None:
            continue
        if manifest.id == plugin_id:
            matches.append((package_root, manifest))
    return matches


def unique_package_for_plugin_id(plugin_id: str, root: Path) -> tuple[Path, PluginManifestV1]:
    matches = packages_for_plugin_id(plugin_id, root)
    if len(matches) > 1:
        raise PluginContractError(PLUGIN_ID_DUPLICATE)
    if len(matches) != 1:
        raise PluginContractError(PLUGIN_MANIFEST_INVALID)
    return matches[0]


def assert_registerable_package(plugin_id: str, client: PluginManifestV1, root: Path) -> tuple[Path, PluginManifestV1]:
    """Fail closed before any sidecar write if the live package is not uniquely bound."""
    package_root, live = unique_package_for_plugin_id(plugin_id, root)
    if identity_snapshot(live) != identity_snapshot(client):
        raise PluginContractError(PLUGIN_MANIFEST_DRIFT)
    return package_root, live


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
    declared = load_declared_packages(configured)
    counts: dict[str, int] = {}
    for _dir_id, _path, manifest, error_code in declared:
        if error_code or manifest is None:
            continue
        counts[manifest.id] = counts.get(manifest.id, 0) + 1
    items: list[dict[str, Any]] = []
    for plugin_dir, _path, manifest, error_code in declared:
        if manifest is not None and counts.get(manifest.id, 0) > 1:
            items.append(_public_item(plugin_dir, error_code=PLUGIN_ID_DUPLICATE))
            continue
        if error_code:
            items.append(_public_item(plugin_dir, error_code=error_code))
            continue
        try:
            verify_manifest_resources(_path, manifest)
        except PluginContractError as exc:
            items.append(_public_item(plugin_dir, error_code=exc.code))
            continue
        except Exception:
            items.append(_public_item(plugin_dir, error_code=PLUGIN_MANIFEST_INVALID))
            continue
        items.append(_public_item(plugin_dir, manifest=manifest))
    return {**empty, "items": items, "total": len(items)}
