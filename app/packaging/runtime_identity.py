from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from .paths import validate_destructive_target


class RuntimeRole(StrEnum):
    POSTGRESQL = "postgresql"
    BACKEND = "backend"
    FRONTEND = "frontend"
    DESKTOP_HOST = "desktop_host"


class RuntimeState(StrEnum):
    NEW = "NEW"
    STARTING = "STARTING"
    READY = "READY"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


def nonce_digest(nonce: str) -> str:
    return hashlib.sha256(nonce.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RuntimeIdentity:
    runtime_instance_id: str
    ownership_nonce: str = field(repr=False)
    launcher_pid: int = field(default_factory=os.getpid)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    executable_identity: str = field(default_factory=lambda: str(Path(sys.executable).resolve()))

    @classmethod
    def create(cls) -> "RuntimeIdentity":
        return cls(runtime_instance_id=str(uuid.uuid4()), ownership_nonce=secrets.token_urlsafe(32))

    @property
    def ownership_nonce_hash(self) -> str:
        return nonce_digest(self.ownership_nonce)

    def public_metadata(self) -> dict[str, object]:
        return {
            "runtime_instance_id": self.runtime_instance_id,
            "launcher_pid": self.launcher_pid,
            "created_at": self.created_at,
            "executable_identity": self.executable_identity,
            "ownership_nonce_hash": self.ownership_nonce_hash,
        }


@dataclass(frozen=True)
class ProcessIdentity:
    role: RuntimeRole
    pid: int
    creation_timestamp: float
    executable_path: str
    parent_pid: int
    runtime_instance_id: str
    ownership_nonce_hash: str


class ProcessInspector(Protocol):
    def inspect(self, pid: int) -> ProcessIdentity | None: ...


def validate_process_ownership(
    expected: ProcessIdentity, actual: ProcessIdentity | None, runtime: RuntimeIdentity
) -> None:
    if actual is None:
        raise ValueError("Owned process is not running")
    checks = {
        "pid": (expected.pid, actual.pid),
        "role": (expected.role, actual.role),
        "parent_pid": (runtime.launcher_pid, actual.parent_pid),
        "runtime_instance_id": (runtime.runtime_instance_id, actual.runtime_instance_id),
        "ownership_nonce_hash": (runtime.ownership_nonce_hash, actual.ownership_nonce_hash),
        "executable_path": (_normal_path(expected.executable_path), _normal_path(actual.executable_path)),
    }
    mismatches = [name for name, (wanted, found) in checks.items() if wanted != found]
    if abs(expected.creation_timestamp - actual.creation_timestamp) > 0.001:
        mismatches.append("creation_timestamp")
    if mismatches:
        raise ValueError(f"Process ownership mismatch: {', '.join(mismatches)}")


@dataclass
class RuntimeMetadata:
    runtime_instance_id: str
    state: RuntimeState
    launcher: dict[str, object]
    ports: dict[str, int] = field(default_factory=dict)
    children: list[dict[str, object]] = field(default_factory=list)
    schema_version: int = 1

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RuntimeMetadataStore:
    def __init__(self, runtime_directory: Path):
        self.runtime_directory = runtime_directory.resolve(strict=False)
        self.path = self.runtime_directory / "runtime-ownership.json"

    def save(self, metadata: RuntimeMetadata) -> None:
        self.runtime_directory.mkdir(parents=True, exist_ok=True)
        temporary = self.runtime_directory / f".{self.path.name}.{os.getpid()}.tmp"
        payload = json.dumps(metadata.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.path)

    def load(self) -> RuntimeMetadata | None:
        if not self.path.exists():
            return None
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != 1:
            raise ValueError("Unsupported runtime metadata schema")
        return RuntimeMetadata(
            runtime_instance_id=str(raw["runtime_instance_id"]),
            state=RuntimeState(raw["state"]),
            launcher=dict(raw["launcher"]),
            ports={str(key): int(value) for key, value in raw.get("ports", {}).items()},
            children=list(raw.get("children", [])),
            schema_version=1,
        )

    def clear(self) -> None:
        if not self.path.exists():
            return
        safe = validate_destructive_target(self.path, allowed_roots=(self.runtime_directory,))
        safe.unlink()


class StaleRecoveryResult(StrEnum):
    NO_STATE = "NO_STATE"
    CLEARED = "CLEARED"
    OWNED_PROCESS_STILL_RUNNING = "OWNED_PROCESS_STILL_RUNNING"
    OWNERSHIP_MISMATCH = "OWNERSHIP_MISMATCH"


def recover_stale_runtime_state(
    store: RuntimeMetadataStore, inspector: ProcessInspector
) -> StaleRecoveryResult:
    metadata = store.load()
    if metadata is None:
        return StaleRecoveryResult.NO_STATE
    for child in metadata.children:
        actual = inspector.inspect(int(child["pid"]))
        if actual is None:
            continue
        expected = _process_from_mapping(child)
        if _same_process(expected, actual):
            return StaleRecoveryResult.OWNED_PROCESS_STILL_RUNNING
        return StaleRecoveryResult.OWNERSHIP_MISMATCH
    store.clear()
    return StaleRecoveryResult.CLEARED


def process_metadata(process: ProcessIdentity) -> dict[str, object]:
    value = asdict(process)
    value["role"] = process.role.value
    return value


def _process_from_mapping(value: dict[str, object]) -> ProcessIdentity:
    return ProcessIdentity(
        role=RuntimeRole(str(value["role"])), pid=int(value["pid"]),
        creation_timestamp=float(value["creation_timestamp"]),
        executable_path=str(value["executable_path"]), parent_pid=int(value["parent_pid"]),
        runtime_instance_id=str(value["runtime_instance_id"]),
        ownership_nonce_hash=str(value["ownership_nonce_hash"]),
    )


def _same_process(expected: ProcessIdentity, actual: ProcessIdentity) -> bool:
    return (
        expected.pid == actual.pid
        and expected.role == actual.role
        and abs(expected.creation_timestamp - actual.creation_timestamp) <= 0.001
        and _normal_path(expected.executable_path) == _normal_path(actual.executable_path)
        and expected.parent_pid == actual.parent_pid
        and expected.runtime_instance_id == actual.runtime_instance_id
        and expected.ownership_nonce_hash == actual.ownership_nonce_hash
    )


def _normal_path(value: str) -> str:
    return os.path.normcase(str(Path(value).resolve(strict=False)))
