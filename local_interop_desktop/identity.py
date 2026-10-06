"""Local-only identity facts. Peer JSON never proves installation or publisher trust.

OS adapters must obtain facts from the connected handle, inspect its executable,
verify signatures and consult explicit installation records. No scanning or launch
is performed here. Real Windows evidence remains LOCAL_REQUIRED.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Iterable, Mapping, Protocol

from local_interop_protocol import (
    PROTOCOL_VERSION,
    ProductDescriptor,
    ProtocolViolation,
)

# Local persistence/audit guard, deliberately more conservative than identity syntax.
# Do not retain the offending value or an exception containing it.
_SECRET_SHAPE = re.compile(
    r"(?i)(?:\b(?:api[ _-]?key|provider[ _-]?secret|access[ _-]?token|oauth[ _-]?token|"
    r"password|vault[ _-]?secret|authorization|cookie|dsn)\s*[:=]\s*\S+|"
    r"\bsk-[A-Za-z0-9_-]{16,}|\bsk_proj_[A-Za-z0-9_-]{16,}|"
    r"\bgh[pousr]_[A-Za-z0-9]{16,}|\bgithub_pat_[A-Za-z0-9_]{16,}|"
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}|"
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}|"
    r"\bBearer[ ._:-][A-Za-z0-9._~-]{12,})"
)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def opaque(value: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9._:-]{0," + str(maximum - 1) + "}", value
    ):
        raise ValueError("Expected bounded non-content identity")
    if _SECRET_SHAPE.search(value):
        raise ValueError("Credentials cannot be identity metadata")
    return value


def version(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}", value):
        raise ValueError("Expected bounded version")
    if _SECRET_SHAPE.search(value):
        raise ValueError("Credentials cannot be version metadata")
    return value


def digest(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected SHA-256 digest")
    return value


class AttestationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    SAME_USER = "SAME_USER"
    KNOWN_PRODUCT = "KNOWN_PRODUCT"
    SIGNED_PRODUCT = "SIGNED_PRODUCT"
    TRUSTED_INSTALLATION = "TRUSTED_INSTALLATION"
    REJECTED = "REJECTED"
    MOCK_ONLY = "MOCK_ONLY"


@dataclass(frozen=True)
class PeerIdentity:
    process_id: int
    user_sid: str
    executable_path_hash: str
    product_id: str
    instance_id: str
    product_version: str
    attestation_state: AttestationState
    installation_id: str | None = None

    def __post_init__(self):
        if type(self.process_id) is not int or self.process_id <= 0:
            raise ValueError("Peer process identity required")
        opaque(self.user_sid)
        digest(self.executable_path_hash)
        opaque(self.product_id)
        opaque(self.instance_id)
        version(self.product_version)
        if self.installation_id is not None:
            opaque(self.installation_id)
        if not isinstance(self.attestation_state, AttestationState):
            raise ValueError("Explicit attestation state required")


@dataclass(frozen=True)
class PeerOSFacts:
    """Obtain from the actual connection handle, never deserialize peer payloads."""

    process_id: int
    user_sid: str
    executable_path_hash: str
    executable_hash: str
    installation_id: str | None = None
    registered_product_id: str | None = None
    publisher_id: str | None = None
    signature_valid: bool = False
    local_connection: bool = True

    def __post_init__(self):
        if type(self.process_id) is not int or self.process_id <= 0:
            raise ValueError("Peer process identity required")
        opaque(self.user_sid)
        digest(self.executable_path_hash)
        digest(self.executable_hash)
        for value in (self.installation_id, self.registered_product_id, self.publisher_id):
            if value is not None:
                opaque(value)
        if type(self.signature_valid) is not bool or type(self.local_connection) is not bool:
            raise ValueError("OS fact booleans must be explicit")


@dataclass(frozen=True)
class InstallationRecord:
    installation_id: str
    product_id: str
    executable_path_hash: str
    executable_hash: str
    publisher_id: str | None = None
    require_signature: bool = True

    def __post_init__(self):
        opaque(self.installation_id)
        opaque(self.product_id)
        digest(self.executable_path_hash)
        digest(self.executable_hash)
        if self.publisher_id is not None:
            opaque(self.publisher_id)
        if type(self.require_signature) is not bool:
            raise ValueError("Signature policy must be explicit")


@dataclass(frozen=True)
class TrustRecord:
    """Strict allowlist for persistence; contains no sessions, grants or credentials."""

    approved_product_identity: str
    approved_installation_identity: str
    trust_level: str
    first_approved_time: datetime
    last_verified_time: datetime
    product_version: str
    protocol_version: str
    revoked: bool = False

    def __post_init__(self):
        for value in (self.approved_product_identity, self.approved_installation_identity):
            opaque(value)
        version(self.product_version)
        version(self.protocol_version)
        if self.trust_level not in {"KNOWN_PRODUCT", "SIGNED_PRODUCT", "TRUSTED_INSTALLATION"}:
            raise ValueError("Mock and unverified trust cannot enter production store")
        for value in (self.first_approved_time, self.last_verified_time):
            if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Trust times must include a timezone")
        if self.last_verified_time < self.first_approved_time or type(self.revoked) is not bool:
            raise ValueError("Invalid trust record")


class InteropPeerTrustStore:
    """Explicit approval store. Transport never calls approve on behalf of the user."""

    def __init__(self, *, limit: int = 128):
        if not 1 <= limit <= 1024:
            raise ValueError("Invalid trust store bound")
        self.limit = limit
        self._records: dict[tuple[str, str], TrustRecord] = {}

    def approve(self, record: TrustRecord, *, user_approved: bool = False) -> None:
        if user_approved is not True or not isinstance(record, TrustRecord):
            raise ProtocolViolation("PERMISSION_DENIED", "Explicit local trust approval required")
        key = (record.approved_product_identity, record.approved_installation_identity)
        if key not in self._records and len(self._records) >= self.limit:
            raise ProtocolViolation("TRANSPORT_ERROR", "Trust store capacity reached")
        self._records[key] = record

    def get(self, product_id: str, installation_id: str) -> TrustRecord | None:
        return self._records.get((product_id, installation_id))

    def revoke(self, product_id: str, installation_id: str) -> None:
        key = product_id, installation_id
        if key in self._records:
            self._records[key] = replace(self._records[key], revoked=True)

    def verified(
        self, product_id: str, installation_id: str, product_version: str, now: datetime
    ) -> None:
        key = product_id, installation_id
        record = self._records.get(key)
        if record is not None and not record.revoked:
            self._records[key] = replace(
                record, last_verified_time=now, product_version=product_version
            )

    def dumps(self) -> str:
        from dataclasses import asdict

        rows = []
        for key in sorted(self._records):
            row = asdict(self._records[key])
            for field in ("first_approved_time", "last_verified_time"):
                row[field] = row[field].isoformat()
            rows.append(row)
        return json.dumps(rows, separators=(",", ":"), sort_keys=True)

    @classmethod
    def loads(cls, raw: str, *, limit: int = 128) -> InteropPeerTrustStore:
        if not isinstance(raw, str) or len(raw.encode()) > 1024 * 1024:
            raise ValueError("Trust data exceeds bound")

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate trust field")
                result[key] = value
            return result

        rows = json.loads(raw, object_pairs_hook=unique)
        if not isinstance(rows, list) or len(rows) > limit:
            raise ValueError("Invalid trust record collection")
        store = cls(limit=limit)
        fields = set(TrustRecord.__dataclass_fields__)
        for row in rows:
            if not isinstance(row, dict) or set(row) != fields:
                raise ValueError("Only approved trust record fields may be persisted")
            row = dict(row)
            for field in ("first_approved_time", "last_verified_time"):
                row[field] = datetime.fromisoformat(row[field])
            record = TrustRecord(**row)
            key = record.approved_product_identity, record.approved_installation_identity
            if key in store._records:
                raise ValueError("Duplicate trust record")
            store._records[key] = record
        return store


class InteropPeerAttestation(Protocol):
    mock_only: bool

    def attest(self, product: ProductDescriptor, facts: PeerOSFacts) -> PeerIdentity: ...


class ProductionPeerAttestation:
    mock_only = False

    def __init__(
        self,
        *,
        current_user_sid: str,
        installations: Mapping[str, InstallationRecord],
        trust_store: InteropPeerTrustStore,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.current_user_sid = opaque(current_user_sid)
        self.installations = dict(installations)
        self.trust_store = trust_store
        self.clock = clock

    def attest(self, product: ProductDescriptor, facts: PeerOSFacts) -> PeerIdentity:
        if not isinstance(facts, PeerOSFacts) or not isinstance(product, ProductDescriptor):
            raise ProtocolViolation("PERMISSION_DENIED", "Trusted OS facts are required")
        state = AttestationState.REJECTED
        record = self.installations.get(facts.installation_id or "")
        if facts.local_connection and facts.user_sid == self.current_user_sid:
            state = AttestationState.SAME_USER
            if record is not None and (
                record.installation_id == facts.installation_id
                and record.product_id == facts.registered_product_id == product.product_id
                and record.executable_path_hash == facts.executable_path_hash
                and record.executable_hash == facts.executable_hash
            ):
                state = AttestationState.KNOWN_PRODUCT
                signed = (
                    facts.signature_valid
                    and record.publisher_id is not None
                    and facts.publisher_id == record.publisher_id
                )
                if signed:
                    state = AttestationState.SIGNED_PRODUCT
                if (record.require_signature or record.publisher_id is not None) and not signed:
                    state = AttestationState.REJECTED
                elif facts.signature_valid and record.publisher_id != facts.publisher_id:
                    state = AttestationState.REJECTED
                else:
                    trust = self.trust_store.get(product.product_id, record.installation_id)
                    if (
                        trust is not None
                        and not trust.revoked
                        and trust.protocol_version == PROTOCOL_VERSION
                        and trust.trust_level == "TRUSTED_INSTALLATION"
                    ):
                        state = AttestationState.TRUSTED_INSTALLATION
                        self.trust_store.verified(
                            product.product_id,
                            record.installation_id,
                            product.product_version,
                            self.clock(),
                        )
            else:
                # Claimed product names, even familiar ones, are not authentication.
                state = AttestationState.REJECTED
        return PeerIdentity(
            facts.process_id,
            facts.user_sid,
            facts.executable_path_hash,
            product.product_id,
            product.instance_id,
            product.product_version,
            state,
            facts.installation_id,
        )


class MockPeerAttestation:
    """Only explicitly selected synthetic paths can construct a MOCK_ONLY transport."""

    mock_only = True

    def attest(self, product: ProductDescriptor, facts: PeerOSFacts) -> PeerIdentity:
        return PeerIdentity(
            facts.process_id,
            facts.user_sid,
            facts.executable_path_hash,
            product.product_id,
            product.instance_id,
            product.product_version,
            AttestationState.MOCK_ONLY,
            facts.installation_id,
        )


@dataclass(frozen=True)
class DiscoveredPeer:
    product_id: str
    instance_id: str
    product_version: str
    protocol_versions: tuple[str, ...]
    transport: str
    trust_state: AttestationState = AttestationState.UNVERIFIED
    endpoint_id: str | None = None

    def __post_init__(self):
        for value in (self.product_id, self.instance_id):
            opaque(value)
        version(self.product_version)
        if (
            not isinstance(self.protocol_versions, tuple)
            or not 1 <= len(self.protocol_versions) <= 16
        ):
            raise ValueError("Bounded protocol versions required")
        for value in self.protocol_versions:
            version(value)
        if self.transport not in {"NAMED_PIPE", "LOOPBACK_HTTP"}:
            raise ValueError("Only existing local transports allowed")
        if self.endpoint_id is not None:
            opaque(self.endpoint_id)
        if not isinstance(self.trust_state, AttestationState):
            raise ValueError("Invalid discovery trust state")


class InteropPeerDiscovery:
    """Reads explicitly supplied OS registration/running-instance sources only.

    No enumeration, path search, port probing, or application start exists here.
    Discovered trust labels are advisory; connect always re-attests actual handle.
    """

    def __init__(
        self,
        *,
        registered: Callable[[], Iterable[DiscoveredPeer]] | None = None,
        running: Callable[[], Iterable[DiscoveredPeer]] | None = None,
        named_pipe: Callable[[], Iterable[DiscoveredPeer]] | None = None,
        limit: int = 32,
    ):
        if not 1 <= limit <= 256:
            raise ValueError("Invalid discovery bound")
        self.sources = tuple(x for x in (registered, running, named_pipe) if x is not None)
        self.limit = limit

    def discover(self) -> tuple[DiscoveredPeer, ...]:
        result = {}
        for source in self.sources:
            for index, peer in enumerate(source()):
                if index >= self.limit or len(result) >= self.limit:
                    break
                if not isinstance(peer, DiscoveredPeer):
                    raise ProtocolViolation("INVALID_MESSAGE", "Invalid discovery adapter result")
                key = peer.product_id, peer.instance_id, peer.transport
                result.setdefault(key, peer)
        return tuple(result.values())
