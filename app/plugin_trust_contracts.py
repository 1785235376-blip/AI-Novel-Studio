"""Plugin Trust / Signing Foundation — contracts only.

This module is the Host-owned vocabulary for publisher identity, signature
metadata, revocation records, verification provenance, and trust decisions.

It never executes plugin code, never verifies a cryptographic signature,
never reads the filesystem or network, never opens the Credential Vault,
and never grants execution. A signature field existing is not trust.
`execution_supported` is structurally false on every decision.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.plugin_contracts import PLUGIN_ID_RE, SEMVER_RE, SHA256_HEX_RE


PLUGIN_TRUST_CONTRACT_VERSION = "trust.v1"
PLUGIN_SIGNATURE_POLICY_VERSION = "trust.v1"
SUPPORTED_POLICY_VERSIONS = frozenset({PLUGIN_SIGNATURE_POLICY_VERSION})
SUPPORTED_EVIDENCE_VERSIONS = frozenset({"1"})
DEFAULT_EVIDENCE_VERSION = "1"
VERIFIED_REASON_CODES = frozenset({"VERIFICATION_EVIDENCE_VALID"})
# Scheme identifier vocabulary only. This is not an Ed25519 (or any) crypto implementation.
SUPPORTED_SIGNATURE_SCHEMES = frozenset({"ed25519-detached-v1"})
EXECUTION_SUPPORTED: Literal[False] = False

PLUGIN_TRUST_CONTRACT_INVALID = "PLUGIN_TRUST_CONTRACT_INVALID"
PLUGIN_TRUST_UNKNOWN_FIELD = "PLUGIN_TRUST_UNKNOWN_FIELD"
PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN = "PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN"
PLUGIN_TRUST_COMMAND_FORBIDDEN = "PLUGIN_TRUST_COMMAND_FORBIDDEN"
PLUGIN_DIGEST_MALFORMED = "PLUGIN_DIGEST_MALFORMED"

ALLOWED_DIGEST_ALGORITHMS = frozenset({"sha256"})
DENIED_DIGEST_ALGORITHMS = frozenset({
    "md5", "sha1", "sha-1", "sha0", "sha224", "sha-224",
    "ripemd160", "ripemd-160", "adler32", "crc32", "none", "identity",
    "blake2s", "md4", "sha512_256",
})

SECRET_FIELD_NAMES = frozenset({
    "secret", "api_key", "apikey", "password", "token", "access_token",
    "refresh_token", "private_key", "public_key", "public_key_pem", "pem",
    "credential", "credentials", "dsn", "token_value", "raw_secret",
    "vault_secret", "plaintext", "signature_bytes",
    "signature_blob", "raw_signature", "detached_signature", "cms_signature",
    "pkcs7", "certificate", "cert", "cert_chain", "x509", "ocsp", "crl",
    "log", "logs", "plugin_log", "debug_log",
})
COMMAND_FIELD_NAMES = frozenset({
    "command", "shell", "executable", "python_code", "js_code", "javascript",
    "entrypoint", "script", "module", "powershell", "subprocess", "argv",
    "host_path", "absolute_path", "cwd",
})
FORBIDDEN_TRUST_FIELDS = SECRET_FIELD_NAMES | COMMAND_FIELD_NAMES

ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
PUBLISHER_ID_RE = PLUGIN_ID_RE
KEY_ID_TOKEN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,119}$")
SCHEME_TOKEN_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*-v[1-9][0-9]*$")
SOURCE_TOKEN_RE = re.compile(r"^[a-z][a-z0-9_]{1,39}$")
REASON_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9_]{1,63}$")
RECORD_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,39}$")
DIGEST_COMPACT_RE = re.compile(r"^sha256:[a-f0-9]{64}$")

SAFE_TRUST_ERROR_MESSAGES = {
    PLUGIN_TRUST_CONTRACT_INVALID: "插件信任契约无效。",
    PLUGIN_TRUST_UNKNOWN_FIELD: "插件信任契约包含未知字段。",
    PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN: "插件信任契约禁止承载密钥、证书链或原始签名材料。",
    PLUGIN_TRUST_COMMAND_FORBIDDEN: "插件信任契约禁止承载可执行命令或代码。",
    PLUGIN_DIGEST_MALFORMED: "摘要格式无效。仅允许 sha256:<64 hex>。",
}


class PluginTrustContractError(ValueError):
    def __init__(self, code: str, message: str | None = None):
        self.code = code
        self.message = message or SAFE_TRUST_ERROR_MESSAGES.get(
            code, SAFE_TRUST_ERROR_MESSAGES[PLUGIN_TRUST_CONTRACT_INVALID],
        )
        super().__init__(f"{self.code}: {self.message}")


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def new_uuid() -> str:
    return str(uuid.uuid4())


def _normalize_key(key: str) -> str:
    return str(key).casefold().replace("-", "_")


def parse_digest(value: str) -> str:
    """Return canonical `sha256:<hex>`. Reject missing algorithm, weak algorithms, and bad hex."""
    if not isinstance(value, str):
        raise PluginTrustContractError(PLUGIN_DIGEST_MALFORMED)
    text = value.strip()
    if not text or "\x00" in text or "\\" in text or "/" in text or " " in text:
        raise PluginTrustContractError(PLUGIN_DIGEST_MALFORMED)
    if text.count(":") != 1:
        raise PluginTrustContractError(PLUGIN_DIGEST_MALFORMED)
    algo, hexpart = text.split(":")
    algo_norm = algo.casefold()
    if algo_norm in DENIED_DIGEST_ALGORITHMS or algo_norm not in ALLOWED_DIGEST_ALGORITHMS:
        raise PluginTrustContractError(PLUGIN_DIGEST_MALFORMED)
    hex_norm = hexpart.casefold()
    if not SHA256_HEX_RE.fullmatch(hex_norm):
        raise PluginTrustContractError(PLUGIN_DIGEST_MALFORMED)
    compact = f"{algo_norm}:{hex_norm}"
    if not DIGEST_COMPACT_RE.fullmatch(compact):
        raise PluginTrustContractError(PLUGIN_DIGEST_MALFORMED)
    return compact


def inspect_forbidden_payload(payload: Any) -> str | None:
    """Return a stable error code if the payload carries secrets, certs, commands, or raw signatures."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            normalized = _normalize_key(key)
            if normalized in SECRET_FIELD_NAMES or "api_key" in normalized or normalized.endswith("_secret"):
                return PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN
            if normalized in COMMAND_FIELD_NAMES:
                return PLUGIN_TRUST_COMMAND_FORBIDDEN
            nested = inspect_forbidden_payload(value)
            if nested:
                return nested
        return None
    if isinstance(payload, (list, tuple)):
        for item in payload:
            nested = inspect_forbidden_payload(item)
            if nested:
                return nested
        return None
    return None


def parse_trust_model(cls: type[BaseModel], payload: Any) -> Any:
    if not isinstance(payload, dict):
        raise PluginTrustContractError(PLUGIN_TRUST_CONTRACT_INVALID)
    forbidden_code = inspect_forbidden_payload(payload)
    if forbidden_code:
        raise PluginTrustContractError(forbidden_code)
    unknown = set(payload) - set(cls.model_fields)
    if unknown:
        secretish = {_normalize_key(name) for name in unknown} & FORBIDDEN_TRUST_FIELDS
        if secretish & SECRET_FIELD_NAMES:
            raise PluginTrustContractError(PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN)
        if secretish & COMMAND_FIELD_NAMES:
            raise PluginTrustContractError(PLUGIN_TRUST_COMMAND_FORBIDDEN)
        raise PluginTrustContractError(PLUGIN_TRUST_UNKNOWN_FIELD)
    try:
        return cls.model_validate(payload)
    except PluginTrustContractError:
        raise
    except Exception as exc:
        text = str(exc)
        for code in (
            PLUGIN_DIGEST_MALFORMED,
            PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN,
            PLUGIN_TRUST_COMMAND_FORBIDDEN,
            PLUGIN_TRUST_UNKNOWN_FIELD,
        ):
            if code in text:
                raise PluginTrustContractError(code) from None
        folded = text.casefold()
        if "extra inputs are not permitted" in folded:
            raise PluginTrustContractError(PLUGIN_TRUST_UNKNOWN_FIELD) from None
        raise PluginTrustContractError(PLUGIN_TRUST_CONTRACT_INVALID) from None


class StrictFrozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    @classmethod
    def parse(cls, payload: Any):
        return parse_trust_model(cls, payload)

    def public_dump(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def canonical_json(self) -> bytes:
        return json.dumps(self.public_dump(), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _require_plugin_id(value: str) -> str:
    if not PLUGIN_ID_RE.fullmatch(value):
        raise ValueError("plugin_id is invalid")
    return value


def _require_semver(value: str) -> str:
    if not SEMVER_RE.fullmatch(value):
        raise ValueError("version is invalid")
    return value


def _require_publisher_id(value: str) -> str:
    if not PUBLISHER_ID_RE.fullmatch(value):
        raise ValueError("publisher_id is invalid")
    return value


def parse_trust_timestamp(value: str) -> datetime:
    """Parse a timezone-aware ISO-8601 timestamp with a real calendar.

    Regex shape is not enough: `2026-99-99T99:99:99Z` must fail.
    Naive timestamps are rejected. Wall-clock `now` is never consulted.
    """
    if not isinstance(value, str) or not ISO_TIMESTAMP_RE.fullmatch(value):
        raise ValueError("timestamp must be ISO-8601")
    text = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError("timestamp must be a valid calendar datetime") from None
    if parsed.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed


def timestamp_not_after(left: str, right: str) -> bool:
    return parse_trust_timestamp(left) <= parse_trust_timestamp(right)


def _require_timestamp(value: str) -> str:
    parse_trust_timestamp(value)
    return value


def _require_scheme(value: str) -> str:
    if not SCHEME_TOKEN_RE.fullmatch(value):
        raise ValueError("signature_scheme is invalid")
    return value


def parse_key_id(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("key_id is invalid")
    if ":" in value:
        return parse_digest(value)
    if not KEY_ID_TOKEN_RE.fullmatch(value):
        raise ValueError("key_id is invalid")
    return value


class PluginTrustState(StrEnum):
    """Closed trust state machine. UNVERIFIED and INVALID are distinct."""

    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REVOKED = "REVOKED"
    INVALID = "INVALID"
    UNSUPPORTED = "UNSUPPORTED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class PublisherIdentityKind(StrEnum):
    OFFICIAL = "official"
    REGISTERED = "registered"
    SELF_ASSERTED = "self_asserted"


class RevocationSubjectType(StrEnum):
    PUBLISHER = "publisher"
    KEY = "key"
    PACKAGE = "package"


class VerificationOutcome(StrEnum):
    """Host-owned fact produced by a future verifier. Not a cryptographic result in this phase."""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"


class PluginPublisherIdentity(StrictFrozen):
    """Publisher identity metadata. Never stores secrets, keys, or certificates."""

    publisher_id: str
    display_name: str = Field(min_length=1, max_length=160)
    identity_kind: PublisherIdentityKind
    identity_version: str

    @field_validator("publisher_id")
    @classmethod
    def valid_publisher_id(cls, value: str) -> str:
        return _require_publisher_id(value)

    @field_validator("identity_version")
    @classmethod
    def valid_identity_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("display_name")
    @classmethod
    def no_secret_display_name(cls, value: str) -> str:
        folded = value.casefold()
        if any(token in folded for token in ("begin private", "api_key", "-----begin")):
            raise PluginTrustContractError(PLUGIN_TRUST_SECRET_FIELD_FORBIDDEN)
        return value


class PluginSignatureDescriptor(StrictFrozen):
    """Signature *metadata*. Presence never implies verification or trust.

    This object records that a signature claim was supplied. It does not
    carry signature bytes and does not mean the claim was checked.
    """

    signature_scheme: str
    key_id: str
    signature_version: str
    signed_manifest_digest: str
    signed_package_digest: str
    created_at: str

    @field_validator("signature_scheme")
    @classmethod
    def valid_scheme(cls, value: str) -> str:
        return _require_scheme(value)

    @field_validator("key_id")
    @classmethod
    def valid_key_id(cls, value: str) -> str:
        return parse_key_id(value)

    @field_validator("signature_version")
    @classmethod
    def valid_signature_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("signed_manifest_digest", "signed_package_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        return parse_digest(value)

    @field_validator("created_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @property
    def metadata_present(self) -> Literal[True]:
        return True


class PluginVerificationEvidence(StrictFrozen):
    """Host-owned verification facts. Produced by a future verifier, consumed as data.

    This phase does not compute these facts with cryptography. A MATCH outcome
    is an input assertion, not a proof that this module verified a signature.
    """

    plugin_id: str
    plugin_version: str
    publisher_id: str
    key_id: str
    scheme: str
    manifest_digest: str
    package_digest: str
    outcome: VerificationOutcome
    verified_at: str
    policy_version: str = PLUGIN_SIGNATURE_POLICY_VERSION
    evidence_version: str = DEFAULT_EVIDENCE_VERSION
    expires_at: str | None = None

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("publisher_id")
    @classmethod
    def valid_publisher_id(cls, value: str) -> str:
        return _require_publisher_id(value)

    @field_validator("key_id")
    @classmethod
    def valid_key_id(cls, value: str) -> str:
        return parse_key_id(value)

    @field_validator("scheme")
    @classmethod
    def valid_scheme(cls, value: str) -> str:
        return _require_scheme(value)

    @field_validator("manifest_digest", "package_digest")
    @classmethod
    def valid_digest(cls, value: str) -> str:
        return parse_digest(value)

    @field_validator("verified_at")
    @classmethod
    def iso_verified_at(cls, value: str) -> str:
        return _require_timestamp(value)

    @field_validator("expires_at")
    @classmethod
    def optional_expiry(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_timestamp(value)

    @field_validator("policy_version")
    @classmethod
    def valid_policy_version(cls, value: str) -> str:
        if not RECORD_VERSION_RE.fullmatch(value):
            raise ValueError("policy_version is invalid")
        return value

    @field_validator("evidence_version")
    @classmethod
    def valid_evidence_version(cls, value: str) -> str:
        if not RECORD_VERSION_RE.fullmatch(value):
            raise ValueError("evidence_version is invalid")
        return value

    @model_validator(mode="after")
    def expiry_interval_is_ordered(self):
        if self.expires_at is not None and not timestamp_not_after(self.verified_at, self.expires_at):
            raise ValueError("verified_at must not be after expires_at")
        return self


class PluginRevocationRecord(StrictFrozen):
    """Deterministic Host-owned revocation input. No CRL/OCSP/network lookup in this phase."""

    subject_type: RevocationSubjectType
    subject_id: str = Field(min_length=1, max_length=200)
    effective_at: str
    reason_code: str
    source: str
    record_version: str

    @field_validator("effective_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @field_validator("reason_code")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not REASON_TOKEN_RE.fullmatch(value):
            raise ValueError("revocation reason_code is invalid")
        return value

    @field_validator("source")
    @classmethod
    def host_owned_source(cls, value: str) -> str:
        folded = value.casefold()
        if "://" in folded or "/" in value or "\\" in value or "." in value:
            raise ValueError("revocation source must be a host-owned token, not a URL or path")
        if not SOURCE_TOKEN_RE.fullmatch(value):
            raise ValueError("revocation source is invalid")
        return value

    @field_validator("record_version")
    @classmethod
    def valid_record_version(cls, value: str) -> str:
        if not RECORD_VERSION_RE.fullmatch(value):
            raise ValueError("record_version is invalid")
        return value

    @field_validator("subject_id")
    @classmethod
    def valid_subject_id(cls, value: str) -> str:
        if "\x00" in value or "://" in value or "\\" in value or "/" in value:
            raise ValueError("revocation subject_id is invalid")
        if value.count(":") == 1 and value.split(":", 1)[0].casefold() in (
            ALLOWED_DIGEST_ALGORITHMS | DENIED_DIGEST_ALGORITHMS
        ):
            return parse_digest(value)
        if "@" in value:
            plugin_id, _, version = value.partition("@")
            if not PLUGIN_ID_RE.fullmatch(plugin_id) or not SEMVER_RE.fullmatch(version):
                raise ValueError("revocation package subject_id is invalid")
            return value
        if not (PLUGIN_ID_RE.fullmatch(value) or KEY_ID_TOKEN_RE.fullmatch(value)):
            raise ValueError("revocation subject_id is invalid")
        return value


class VerificationProvenance(StrictFrozen):
    """Enough to answer what was checked, against which digest, with which policy and scheme.

    Must not contain private keys, credentials, API keys, or plugin-controlled logs.
    """

    evaluator: Literal["plugin_signature_policy"] = "plugin_signature_policy"
    policy_version: str = PLUGIN_SIGNATURE_POLICY_VERSION
    verification_scheme: str
    manifest_digest: str | None = None
    package_digest: str | None = None
    signature_metadata_present: bool = False
    evidence_present: bool = False

    @field_validator("verification_scheme")
    @classmethod
    def valid_scheme_or_none(cls, value: str) -> str:
        if value == "none":
            return value
        return _require_scheme(value)

    @field_validator("manifest_digest", "package_digest")
    @classmethod
    def optional_digest(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return parse_digest(value)

    @field_validator("policy_version")
    @classmethod
    def valid_policy_version(cls, value: str) -> str:
        if not RECORD_VERSION_RE.fullmatch(value):
            raise ValueError("policy_version is invalid")
        return value


class PluginTrustDecision(StrictFrozen):
    """Immutable trust decision. VERIFIED is not executable, not sandbox-ready, not authorization."""

    plugin_id: str
    plugin_version: str
    publisher_id: str | None = None
    trust_state: PluginTrustState
    reason_code: str
    verification_provenance: VerificationProvenance
    verified_manifest_digest: str | None = None
    verified_package_digest: str | None = None
    signature_metadata_present: bool = False
    execution_supported: Literal[False] = False
    sandbox_ready: Literal[False] = False
    broker_ready: Literal[False] = False
    worker_ready: Literal[False] = False
    evaluated_at: str
    policy_version: str = PLUGIN_SIGNATURE_POLICY_VERSION

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("publisher_id")
    @classmethod
    def optional_publisher(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_publisher_id(value)

    @field_validator("reason_code")
    @classmethod
    def valid_reason(cls, value: str) -> str:
        if not REASON_TOKEN_RE.fullmatch(value):
            raise ValueError("reason_code is invalid")
        return value

    @field_validator("verified_manifest_digest", "verified_package_digest")
    @classmethod
    def optional_verified_digest(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return parse_digest(value)

    @field_validator("evaluated_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @field_validator("policy_version")
    @classmethod
    def valid_policy_version(cls, value: str) -> str:
        if not RECORD_VERSION_RE.fullmatch(value):
            raise ValueError("policy_version is invalid")
        return value

    @model_validator(mode="after")
    def fail_closed_execution_and_verified_consistency(self):
        if self.execution_supported is not False:
            raise ValueError("execution_supported must remain false")
        if self.sandbox_ready or self.broker_ready or self.worker_ready:
            raise ValueError("trust must not claim sandbox, broker, or worker readiness")
        if self.signature_metadata_present != self.verification_provenance.signature_metadata_present:
            raise ValueError("signature metadata presence must match provenance")
        if self.trust_state is PluginTrustState.VERIFIED:
            if self.publisher_id is None:
                raise ValueError("VERIFIED decisions require publisher identity")
            if not self.signature_metadata_present:
                raise ValueError("VERIFIED decisions require signature metadata")
            if not self.verification_provenance.evidence_present:
                raise ValueError("VERIFIED decisions require verification evidence")
            if self.verification_provenance.verification_scheme not in SUPPORTED_SIGNATURE_SCHEMES:
                raise ValueError("VERIFIED decisions require a supported verification scheme")
            if self.reason_code not in VERIFIED_REASON_CODES:
                raise ValueError("VERIFIED reason_code is incompatible")
            if self.policy_version not in SUPPORTED_POLICY_VERSIONS:
                raise ValueError("VERIFIED decisions require a supported policy version")
            if self.verification_provenance.policy_version not in SUPPORTED_POLICY_VERSIONS:
                raise ValueError("VERIFIED provenance requires a supported policy version")
            if not self.verified_manifest_digest or not self.verified_package_digest:
                raise ValueError("VERIFIED decisions must bind verified digests")
            if self.verified_manifest_digest != self.verification_provenance.manifest_digest:
                raise ValueError("verified manifest digest must match provenance")
            if self.verified_package_digest != self.verification_provenance.package_digest:
                raise ValueError("verified package digest must match provenance")
        else:
            if self.verified_manifest_digest is not None or self.verified_package_digest is not None:
                raise ValueError("unverified decisions must not populate verified_* digests")
        return self


class PluginTrustEvaluationInput(StrictFrozen):
    """Already-parsed Host-owned facts for the pure policy evaluator."""

    plugin_id: str
    plugin_version: str
    evaluated_at: str
    publisher: PluginPublisherIdentity | None = None
    signature: PluginSignatureDescriptor | None = None
    evidence: PluginVerificationEvidence | None = None
    revocations: tuple[PluginRevocationRecord, ...] = ()
    known_publisher_ids: tuple[str, ...] = ()

    @field_validator("plugin_id")
    @classmethod
    def valid_plugin_id(cls, value: str) -> str:
        return _require_plugin_id(value)

    @field_validator("plugin_version")
    @classmethod
    def valid_version(cls, value: str) -> str:
        return _require_semver(value)

    @field_validator("evaluated_at")
    @classmethod
    def iso_time(cls, value: str) -> str:
        return _require_timestamp(value)

    @field_validator("known_publisher_ids")
    @classmethod
    def valid_known_publishers(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for item in value:
            publisher_id = _require_publisher_id(item)
            if publisher_id not in seen:
                cleaned.append(publisher_id)
                seen.add(publisher_id)
        return tuple(cleaned)

    @model_validator(mode="after")
    def temporal_order_is_deterministic(self):
        if self.evidence is not None and not timestamp_not_after(self.evidence.verified_at, self.evaluated_at):
            raise ValueError("verified_at must not be after evaluated_at")
        return self


def dump_without_secrets(model: StrictFrozen) -> dict[str, Any]:
    payload = model.public_dump()
    code = inspect_forbidden_payload(payload)
    if code:
        raise PluginTrustContractError(code)
    return payload
