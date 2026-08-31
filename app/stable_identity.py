"""Authoritative, durable identities for Provider Runtime owners.

This module deliberately stores opaque UUIDs separately from display slugs and
configuration.  It is a registry primitive, not a routing or authorization
layer.
"""

from __future__ import annotations

import json
import math
import os
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from .storage import atomic_write


ZERO_UUID = uuid.UUID(int=0)
SCHEMA_VERSION = 1


class IdentityIntegrityError(ValueError):
    """Persisted identity data is malformed, ambiguous, or unsafe."""


class IdentityMutationError(IdentityIntegrityError):
    """An ordinary update attempted to mutate an authoritative identity."""


@dataclass(frozen=True, slots=True)
class TrustedLegacySource:
    """Explicit server/Host-owned boundary for legacy backfill input."""

    entries: tuple[Mapping[str, Any], ...]

    @classmethod
    def from_entries(cls, entries: Iterable[Mapping[str, Any]]) -> "TrustedLegacySource":
        return cls(tuple(entries))


def validate_uuid(value: uuid.UUID | str, *, field: str = "identity") -> uuid.UUID:
    """Parse an authoritative UUID and reject malformed and zero values."""

    if isinstance(value, uuid.UUID):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = uuid.UUID(value)
        except (ValueError, AttributeError, TypeError) as exc:
            raise IdentityIntegrityError(f"{field}_MALFORMED") from exc
    else:
        raise IdentityIntegrityError(f"{field}_MALFORMED")
    if parsed == ZERO_UUID:
        raise IdentityIntegrityError(f"{field}_ZERO")
    return parsed


@dataclass(frozen=True, slots=True)
class ProviderIdentity:
    provider_id: uuid.UUID

    def __post_init__(self) -> None:
        _validate_wrapper_uuid(self.provider_id, "provider_id")


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    model_id: uuid.UUID

    def __post_init__(self) -> None:
        _validate_wrapper_uuid(self.model_id, "model_id")


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    runtime_id: uuid.UUID

    def __post_init__(self) -> None:
        _validate_wrapper_uuid(self.runtime_id, "runtime_id")


@dataclass(frozen=True, slots=True)
class ExecutionNodeIdentity:
    execution_node_id: uuid.UUID

    def __post_init__(self) -> None:
        _validate_wrapper_uuid(self.execution_node_id, "execution_node_id")


@dataclass(frozen=True, slots=True)
class TaxonomyIdentity:
    taxonomy_id: uuid.UUID
    key: str
    display_name: str

    def __post_init__(self) -> None:
        if not isinstance(self.taxonomy_id, uuid.UUID) or self.taxonomy_id == ZERO_UUID:
            raise IdentityIntegrityError("taxonomy_id_INVALID")
        if not isinstance(self.key, str) or not self.key.strip() or not isinstance(self.display_name, str) or not self.display_name.strip():
            raise IdentityIntegrityError("taxonomy_VALUE_INVALID")


# Explicit, centrally-owned literals.  They are intentionally not UUID5/hash
# outputs and are stable across processes, reloads, and installations.
RUNTIME_FAMILY_LLAMA_CPP = TaxonomyIdentity(uuid.UUID("7c8b4e2a-1b0d-4d8f-9e64-0b5b3f0d1a11"), "llama.cpp", "llama.cpp")
RUNTIME_FAMILY_COMFYUI = TaxonomyIdentity(uuid.UUID("7c8b4e2a-1b0d-4d8f-9e64-0b5b3f0d1a12"), "ComfyUI", "ComfyUI")
ARCHITECTURE_X86_64 = TaxonomyIdentity(uuid.UUID("3f0c9d12-66a4-4f2a-a4b5-4df8c7e10101"), "x86_64", "x86_64")
ARCHITECTURE_ARM64 = TaxonomyIdentity(uuid.UUID("3f0c9d12-66a4-4f2a-a4b5-4df8c7e10102"), "arm64", "arm64")
GPU_VENDOR_NVIDIA = TaxonomyIdentity(uuid.UUID("b2d4a2f1-9c6e-4f08-9d15-5ab2d6a20101"), "NVIDIA", "NVIDIA")
GPU_VENDOR_AMD = TaxonomyIdentity(uuid.UUID("b2d4a2f1-9c6e-4f08-9d15-5ab2d6a20102"), "AMD", "AMD")
GPU_VENDOR_INTEL = TaxonomyIdentity(uuid.UUID("b2d4a2f1-9c6e-4f08-9d15-5ab2d6a20103"), "Intel", "Intel")

RUNTIME_FAMILIES = {item.key: item for item in (RUNTIME_FAMILY_LLAMA_CPP, RUNTIME_FAMILY_COMFYUI)}
ARCHITECTURES = {item.key: item for item in (ARCHITECTURE_X86_64, ARCHITECTURE_ARM64)}
GPU_VENDORS = {item.key: item for item in (GPU_VENDOR_NVIDIA, GPU_VENDOR_AMD, GPU_VENDOR_INTEL)}


def _check_taxonomy_uniqueness() -> None:
    all_items = tuple(RUNTIME_FAMILIES.values()) + tuple(ARCHITECTURES.values()) + tuple(GPU_VENDORS.values())
    ids = [item.taxonomy_id for item in all_items]
    if len(ids) != len(set(ids)) or any(item.taxonomy_id == ZERO_UUID for item in all_items):
        raise RuntimeError("invalid built-in taxonomy identities")


_check_taxonomy_uniqueness()


class StableIdentityStore:
    """A small JSON registry with atomic writes and fail-closed reads."""

    KINDS = ("provider", "model", "runtime", "execution_node")
    _locks: dict[str, threading.RLock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve(strict=False)
        key = str(self.path)
        with self._locks_guard:
            self._lock = self._locks.setdefault(key, threading.RLock())

    @classmethod
    def for_application(cls) -> "StableIdentityStore":
        return cls(canonical_identity_store_path())

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "entities": {kind: [] for kind in self.KINDS}}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            raw = json.loads(
                self.path.read_text(encoding="utf-8"),
                object_pairs_hook=_strict_object,
                parse_constant=_reject_constant,
            )
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IdentityIntegrityError("IDENTITY_STORE_UNREADABLE") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema_version", "entities"}:
            raise IdentityIntegrityError("IDENTITY_STORE_SCHEMA_INVALID")
        if type(raw.get("schema_version")) is not int or raw["schema_version"] != SCHEMA_VERSION:
            raise IdentityIntegrityError("IDENTITY_STORE_SCHEMA_INVALID")
        entities = raw.get("entities")
        if not isinstance(entities, dict) or set(entities) != set(self.KINDS):
            raise IdentityIntegrityError("IDENTITY_STORE_ENTITIES_INVALID")
        result = self._empty()
        for kind in self.KINDS:
            rows = entities.get(kind, [])
            if not isinstance(rows, list):
                raise IdentityIntegrityError(f"{kind}_ENTRIES_INVALID")
            result["entities"][kind] = self._validate_rows(kind, rows)
        return result

    @staticmethod
    def _validate_rows(kind: str, rows: list[Any]) -> list[dict[str, Any]]:
        seen_keys: set[str] = set()
        seen_ids: set[uuid.UUID] = set()
        validated: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict) or set(row) != {"key", "identity_id", "metadata"} or not isinstance(row.get("key"), str) or not row["key"].strip():
                raise IdentityIntegrityError(f"{kind}_ENTRY_INVALID")
            key = row["key"]
            if key in seen_keys:
                raise IdentityIntegrityError(f"{kind}_DUPLICATE_KEY")
            identity = validate_uuid(row.get("identity_id"), field=f"{kind}_id")
            if identity in seen_ids:
                raise IdentityIntegrityError(f"{kind}_DUPLICATE_ID")
            seen_keys.add(key)
            seen_ids.add(identity)
            metadata = row.get("metadata", {})
            if not isinstance(metadata, dict):
                raise IdentityIntegrityError(f"{kind}_METADATA_INVALID")
            _validate_metadata(metadata, field=f"{kind}_METADATA_INVALID")
            validated.append({"key": key, "identity_id": str(identity), "metadata": dict(metadata)})
        return validated

    def _write(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        atomic_write(self.path, payload)
        # Durable-authority invariant: never report success for unreadable state.
        self._read()

    @contextmanager
    def _mutation(self):
        """Serialize read/validate/mutate/persist across threads and processes."""
        with self._lock:
            lock_path = Path(str(self.path) + ".lock")
            lock_path.parent.mkdir(parents=True, exist_ok=True)
            # The lock target is created with O_EXCL so cold-start ownership
            # cannot be observed as available by two processes simultaneously.
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(fd, b"0")
                os.close(fd)
            except FileExistsError:
                pass
            except OSError:
                pass
            with lock_path.open("r+b") as handle:
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if os.name == "nt":
                        import msvcrt
                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def list(self, kind: str) -> tuple[dict[str, Any], ...]:
        if kind not in self.KINDS:
            raise ValueError(f"unknown identity kind: {kind}")
        with self._lock:
            return tuple(self._read()["entities"][kind])

    def get(self, kind: str, key: str) -> uuid.UUID | None:
        lookup = self._lookup_key(kind, key)
        return next((validate_uuid(row["identity_id"], field=f"{kind}_id") for row in self.list(kind) if row["key"] == lookup), None)

    def _lookup_key(self, kind: str, key: str) -> str:
        if kind != "model" or key.startswith("["):
            return key
        matches = []
        for row in self.list(kind):
            try:
                parsed = json.loads(row["key"])
                if isinstance(parsed, list) and len(parsed) == 3 and parsed[0] == "provider_model" and parsed[2] == key:
                    matches.append(row["key"])
            except (TypeError, json.JSONDecodeError):
                continue
        if len(matches) == 1:
            return matches[0]
        return key

    def create(self, kind: str, key: str, *, metadata: Mapping[str, Any] | None = None, supplied_id: Any = None) -> uuid.UUID:
        """Create an entity; caller-supplied IDs are never authoritative."""
        if kind not in self.KINDS or not isinstance(key, str) or not key.strip():
            raise ValueError("identity key is required")
        with self._mutation():
            data = self._read()
            rows = data["entities"][kind]
            if any(row["key"] == key for row in rows):
                raise IdentityIntegrityError(f"{kind}_ALREADY_EXISTS")
            identity = uuid.uuid4()
            candidate = dict(data)
            candidate["entities"] = {name: list(values) for name, values in data["entities"].items()}
            normalized = dict(metadata or {})
            _validate_metadata(normalized, field=f"{kind}_METADATA_INVALID")
            candidate["entities"][kind].append({"key": key, "identity_id": str(identity), "metadata": normalized})
            candidate["entities"][kind] = self._validate_rows(kind, candidate["entities"][kind])
            self._write(candidate)
            return identity

    def get_or_create(self, kind: str, key: str, *, metadata: Mapping[str, Any] | None = None) -> uuid.UUID:
        if kind not in self.KINDS or not isinstance(key, str) or not key.strip():
            raise ValueError("identity key is required")
        with self._mutation():
            data = self._read()
            existing_row = next((row for row in data["entities"][kind] if row["key"] == key), None)
            existing = validate_uuid(existing_row["identity_id"], field=f"{kind}_id") if existing_row else None
            if existing is not None:
                return existing
            identity = uuid.uuid4()
            candidate = dict(data)
            candidate["entities"] = {name: list(values) for name, values in data["entities"].items()}
            normalized = dict(metadata or {})
            _validate_metadata(normalized, field=f"{kind}_METADATA_INVALID")
            candidate["entities"][kind].append({"key": key, "identity_id": str(identity), "metadata": normalized})
            candidate["entities"][kind] = self._validate_rows(kind, candidate["entities"][kind])
            self._write(candidate)
            return identity

    def update(self, kind: str, key: str, *, identity_id: Any = None, metadata: Mapping[str, Any] | None = None) -> uuid.UUID:
        with self._mutation():
            data = self._read()
            rows = data["entities"][kind]
            row = next((item for item in rows if item["key"] == key), None)
            if row is None:
                raise KeyError(key)
            current = validate_uuid(row["identity_id"], field=f"{kind}_id")
            if identity_id is not None and validate_uuid(identity_id, field=f"{kind}_id") != current:
                raise IdentityMutationError(f"{kind}_ID_IMMUTABLE")
            if metadata is None:
                return current
            candidate = dict(data)
            candidate["entities"] = {name: list(values) for name, values in data["entities"].items()}
            normalized = dict(metadata)
            _validate_metadata(normalized, field=f"{kind}_METADATA_INVALID")
            candidate["entities"][kind] = [
                {**item, "metadata": normalized} if item["key"] == key else item
                for item in rows
            ]
            candidate["entities"][kind] = self._validate_rows(kind, candidate["entities"][kind])
            self._write(candidate)
            return current

    def delete(self, kind: str, key: str) -> None:
        if kind not in self.KINDS:
            raise ValueError(f"unknown identity kind: {kind}")
        with self._mutation():
            data = self._read()
            key = self._lookup_key(kind, key)
            rows = data["entities"][kind]
            if not any(item["key"] == key for item in rows):
                raise KeyError(key)
            candidate = dict(data)
            candidate["entities"] = {name: list(values) for name, values in data["entities"].items()}
            candidate["entities"][kind] = [item for item in rows if item["key"] != key]
            self._write(candidate)

    def migrate(self, kind: str, legacy_entries: Iterable[Mapping[str, Any]] | TrustedLegacySource, *, key_field: str = "key", identity_field: str = "identity_id", trusted_source: TrustedLegacySource | None = None) -> dict[str, uuid.UUID]:
        """Backfill missing legacy IDs once, preserving and validating existing IDs."""
        if kind not in self.KINDS:
            raise ValueError(f"unknown identity kind: {kind}")
        if not isinstance(trusted_source, TrustedLegacySource):
            raise IdentityIntegrityError("IDENTITY_MIGRATION_TRUST_REQUIRED")
        entries = list(trusted_source.entries)
        with self._mutation():
            data = self._read()
            rows = list(data["entities"][kind])
            by_key = {row["key"]: row for row in rows}
            seen_input: set[str] = set()
            seen_ids = {validate_uuid(row["identity_id"], field=f"{kind}_id") for row in rows}
            result: dict[str, uuid.UUID] = {}
            for entry in entries:
                if not isinstance(entry, Mapping) or not isinstance(entry.get(key_field), str) or not entry[key_field].strip():
                    raise IdentityIntegrityError(f"{kind}_LEGACY_ENTRY_INVALID")
                key = str(entry[key_field])
                if key in seen_input:
                    raise IdentityIntegrityError(f"{kind}_DUPLICATE_KEY")
                seen_input.add(key)
                existing = by_key.get(key)
                raw_id = entry.get(identity_field)
                if existing is not None:
                    current = validate_uuid(existing["identity_id"], field=f"{kind}_id")
                    if raw_id is not None and validate_uuid(raw_id, field=f"{kind}_id") != current:
                        raise IdentityMutationError(f"{kind}_ID_IMMUTABLE")
                    result[key] = current
                    continue
                identity = uuid.uuid4() if raw_id is None else validate_uuid(raw_id, field=f"{kind}_id")
                if identity in seen_ids:
                    raise IdentityIntegrityError(f"{kind}_DUPLICATE_ID")
                seen_ids.add(identity)
                metadata = dict(entry.get("metadata", {}))
                _validate_metadata(metadata, field=f"{kind}_METADATA_INVALID")
                row = {"key": key, "identity_id": str(identity), "metadata": metadata}
                rows.append(row)
                by_key[key] = row
                result[key] = identity
            candidate = dict(data)
            candidate["entities"] = {name: list(values) for name, values in data["entities"].items()}
            candidate["entities"][kind] = self._validate_rows(kind, rows)
            if candidate["entities"][kind] != data["entities"][kind]:
                self._write(candidate)
            return result


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IdentityIntegrityError("IDENTITY_STORE_DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise IdentityIntegrityError(f"IDENTITY_STORE_CONSTANT_INVALID:{value}")


def _validate_wrapper_uuid(value: Any, field: str) -> uuid.UUID:
    if not isinstance(value, uuid.UUID):
        raise IdentityIntegrityError(f"{field}_MALFORMED")
    if value == ZERO_UUID:
        raise IdentityIntegrityError(f"{field}_ZERO")
    return value


def _validate_metadata(value: Any, *, field: str = "METADATA_INVALID") -> None:
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise IdentityIntegrityError(field)
        for item in value.values():
            _validate_metadata(item, field=field)
        return
    if isinstance(value, list):
        for item in value:
            _validate_metadata(item, field=field)
        return
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise IdentityIntegrityError(field)
        return
    raise IdentityIntegrityError(field)


def canonical_model_identity_key(provider_id: str, model_id: str) -> str:
    """Unambiguous structured key for provider-scoped model identities."""
    if not isinstance(provider_id, str) or not isinstance(model_id, str) or not provider_id or not model_id:
        raise ValueError("provider and model are required")
    return json.dumps(["provider_model", provider_id, model_id], ensure_ascii=False, separators=(",", ":"))


def canonical_identity_store_path() -> Path:
    # Host identity is application state, independent of the opened project,
    # repository, or current working directory.
    return _canonical_host_data_root(os.name) / "identity-foundation.json"


def _canonical_host_data_root(platform: str) -> Path:
    if platform == "nt":
        configured = os.environ.get("LOCALAPPDATA")
        root = Path(configured) if configured else Path.home() / "AppData" / "Local"
        suffix = ("AI-Novel-Studio", "UserData")
    else:
        configured = os.environ.get("XDG_DATA_HOME")
        root = Path(configured) if configured else Path.home() / ".local" / "share"
        suffix = ("AI-Novel-Studio",)
    if not root.is_absolute():
        raise IdentityIntegrityError("HOST_DATA_ROOT_NOT_ABSOLUTE")
    return root.resolve(strict=False).joinpath(*suffix)


def get_host_identity_store() -> StableIdentityStore:
    """Construct the sole production identity store from Host application data."""
    return StableIdentityStore(canonical_identity_store_path())


class ProviderIdentityRegistry:
    def __init__(self, store: StableIdentityStore): self.store = store
    def ensure(self, provider_key: str) -> ProviderIdentity: return ProviderIdentity(self.store.get_or_create("provider", provider_key))
    def create(self, provider_key: str, supplied_id: Any = None) -> ProviderIdentity: return ProviderIdentity(self.store.create("provider", provider_key, supplied_id=supplied_id))


class ModelIdentityRegistry:
    def __init__(self, store: StableIdentityStore): self.store = store
    def ensure(self, provider_id: str, model_id: str | None = None) -> ModelIdentity:
        key = canonical_model_identity_key(provider_id, model_id) if model_id is not None else provider_id
        return ModelIdentity(self.store.get_or_create("model", key))
    def create(self, provider_id: str, model_id: str | None = None, supplied_id: Any = None) -> ModelIdentity:
        key = canonical_model_identity_key(provider_id, model_id) if model_id is not None else provider_id
        return ModelIdentity(self.store.create("model", key, supplied_id=supplied_id))


class RuntimeIdentityRegistry:
    def __init__(self, store: StableIdentityStore): self.store = store
    def ensure(self, runtime_key: str) -> RuntimeIdentity: return RuntimeIdentity(self.store.get_or_create("runtime", runtime_key))
    def create(self, runtime_key: str, supplied_id: Any = None) -> RuntimeIdentity: return RuntimeIdentity(self.store.create("runtime", runtime_key, supplied_id=supplied_id))


class ExecutionNodeIdentityStore:
    """Host-owned local node identity; one durable opaque ID per store."""

    def __init__(self, path: str | Path): self.store = StableIdentityStore(path)
    def get_or_create(self) -> ExecutionNodeIdentity:
        return ExecutionNodeIdentity(self.store.get_or_create("execution_node", "local"))


# Short aliases make the owner boundaries explicit to callers without creating
# parallel registries.
ProviderRegistryIdentity = ProviderIdentityRegistry
ModelRegistryIdentity = ModelIdentityRegistry
RuntimeRegistryIdentity = RuntimeIdentityRegistry
