"""Authoritative, durable identities for Provider Runtime owners.

This module deliberately stores opaque UUIDs separately from display slugs and
configuration.  It is a registry primitive, not a routing or authorization
layer.
"""

from __future__ import annotations

import json
import threading
import uuid
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


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    model_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class RuntimeIdentity:
    runtime_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class ExecutionNodeIdentity:
    execution_node_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class TaxonomyIdentity:
    taxonomy_id: uuid.UUID
    key: str
    display_name: str


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

    def _empty(self) -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "entities": {kind: [] for kind in self.KINDS}}

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._empty()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise IdentityIntegrityError("IDENTITY_STORE_UNREADABLE") from exc
        if not isinstance(raw, dict) or raw.get("schema_version") != SCHEMA_VERSION:
            raise IdentityIntegrityError("IDENTITY_STORE_SCHEMA_INVALID")
        entities = raw.get("entities")
        if not isinstance(entities, dict):
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
            if not isinstance(row, dict) or not isinstance(row.get("key"), str) or not row["key"].strip():
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
            validated.append({"key": key, "identity_id": str(identity), "metadata": dict(metadata)})
        return validated

    def _write(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        atomic_write(self.path, payload)

    def list(self, kind: str) -> tuple[dict[str, Any], ...]:
        if kind not in self.KINDS:
            raise ValueError(f"unknown identity kind: {kind}")
        with self._lock:
            return tuple(self._read()["entities"][kind])

    def get(self, kind: str, key: str) -> uuid.UUID | None:
        return next((validate_uuid(row["identity_id"], field=f"{kind}_id") for row in self.list(kind) if row["key"] == key), None)

    def create(self, kind: str, key: str, *, metadata: Mapping[str, Any] | None = None, supplied_id: Any = None) -> uuid.UUID:
        """Create an entity; caller-supplied IDs are never authoritative."""
        if kind not in self.KINDS or not isinstance(key, str) or not key.strip():
            raise ValueError("identity key is required")
        with self._lock:
            data = self._read()
            rows = data["entities"][kind]
            if any(row["key"] == key for row in rows):
                raise IdentityIntegrityError(f"{kind}_ALREADY_EXISTS")
            identity = uuid.uuid4()
            candidate = dict(data)
            candidate["entities"] = {name: list(values) for name, values in data["entities"].items()}
            candidate["entities"][kind].append({"key": key, "identity_id": str(identity), "metadata": dict(metadata or {})})
            candidate["entities"][kind] = self._validate_rows(kind, candidate["entities"][kind])
            self._write(candidate)
            return identity

    def get_or_create(self, kind: str, key: str, *, metadata: Mapping[str, Any] | None = None) -> uuid.UUID:
        with self._lock:
            existing = self.get(kind, key)
            if existing is not None:
                return existing
            return self.create(kind, key, metadata=metadata)

    def update(self, kind: str, key: str, *, identity_id: Any = None, metadata: Mapping[str, Any] | None = None) -> uuid.UUID:
        with self._lock:
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
            candidate["entities"][kind] = [
                {**item, "metadata": dict(metadata)} if item["key"] == key else item
                for item in rows
            ]
            candidate["entities"][kind] = self._validate_rows(kind, candidate["entities"][kind])
            self._write(candidate)
            return current

    def migrate(self, kind: str, legacy_entries: Iterable[Mapping[str, Any]], *, key_field: str = "key", identity_field: str = "identity_id") -> dict[str, uuid.UUID]:
        """Backfill missing legacy IDs once, preserving and validating existing IDs."""
        if kind not in self.KINDS:
            raise ValueError(f"unknown identity kind: {kind}")
        entries = list(legacy_entries)
        with self._lock:
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
                row = {"key": key, "identity_id": str(identity), "metadata": dict(entry.get("metadata", {}))}
                rows.append(row)
                by_key[key] = row
                result[key] = identity
            candidate = dict(data)
            candidate["entities"] = {name: list(values) for name, values in data["entities"].items()}
            candidate["entities"][kind] = self._validate_rows(kind, rows)
            if candidate["entities"][kind] != data["entities"][kind]:
                self._write(candidate)
            return result


class ProviderIdentityRegistry:
    def __init__(self, store: StableIdentityStore): self.store = store
    def ensure(self, provider_key: str) -> ProviderIdentity: return ProviderIdentity(self.store.get_or_create("provider", provider_key))
    def create(self, provider_key: str, supplied_id: Any = None) -> ProviderIdentity: return ProviderIdentity(self.store.create("provider", provider_key, supplied_id=supplied_id))


class ModelIdentityRegistry:
    def __init__(self, store: StableIdentityStore): self.store = store
    def ensure(self, model_key: str) -> ModelIdentity: return ModelIdentity(self.store.get_or_create("model", model_key))
    def create(self, model_key: str, supplied_id: Any = None) -> ModelIdentity: return ModelIdentity(self.store.create("model", model_key, supplied_id=supplied_id))


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

