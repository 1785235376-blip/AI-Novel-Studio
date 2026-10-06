# Local Interop 1.0 wire boundary

Status: **CONTRACT_VERIFIED**. These newly authored, product-neutral files and
`local_interop_protocol/` are mirrored byte-for-byte in the two participating
repositories. The parity manifest records SHA-256 hashes. No product internals,
credentials, runtime state, real manuscript, or private legacy contract files
are copied into this boundary.

## Consumers and regeneration

- Python: `from local_interop_protocol import ...`; validate untrusted messages
  with `parse_wire(Model, payload)` rather than `model_construct` or `model_copy`.
- TypeScript: import DTOs from `protocol.ts`; readonly types are compile-time
  aids, not runtime permission or schema validation.
- Rust: `protocol.rs` is a serde interface draft, not a Desktop runtime. It has
  typed payload variants and denies unknown fields. Validate the matching JSON
  Schema and semantic invariants before use. Rust compilation is **NOT_RUN** in
  the current environment, where no Rust toolchain is installed.
- Regenerate with `python -m local_interop_protocol.generate_contracts`.
- Test with `python -m pytest tests/test_local_interop_contracts.py`.
- `common.schema.json` consolidates the definitions; individual schemas are
  self-contained Draft 2020-12 documents. Their `$id` values are identifiers,
  not a requirement to fetch anything from the network.

## Stable identities and version negotiation

The wire identity is `PoemSeed Local Interop`, version `1.0`; software versions
are separate. Current stable product IDs are `poemseed.creative.studio` and
`poemseed.tutor.desktop`. Display names and URI schemes are not identities.

Every protocol message on the wire, including nested protocol messages, must
include `protocol_name` and `protocol_version`. Constructors provide defaults
for trusted local code; `parse_wire` does not supply missing wire identity.
Future stable dotted capabilities may be advertised without breaking discovery.
Only the sixteen known V1 capabilities can be granted. Unknown required
capabilities fail with `CAPABILITY_NOT_SUPPORTED`; no execution/write capability
exists. HELLO precedes negotiation and session creation. The hello result echoes
the initiating nonce; the host must correlate nonce, products, instances, local
user identity and negotiated capabilities, then expire/revoke the session.

## Canonical hashing

The V1 hash profile is lowercase SHA-256 over UTF-8 JSON with sorted object keys,
compact separators, Unicode preserved, finite JSON numbers only, UTC RFC3339
timestamps, and fully hydrated defaults. All wire object keys are ASCII. This
profile is intentionally specified here and does not claim general RFC 8785
compliance. Cross-language implementations must hydrate defaults and normalize
timestamps before hashing.

- `capsule_hash` covers all `AppContextCapsule` fields except `capsule_hash`.
- A diagnostic's `content_hash` covers all its fields except `content_hash`.
- `selection_hash` equals `canonical_hash(shared_text)`, including the JSON
  string encoding. It is not the SHA-256 of the unquoted raw text bytes.
- Use `create_capsule` and `create_diagnostic` to hydrate, validate and seal.
- IDs, source versions and hashes are immutable. Rebuilding a changed snapshot
  requires a fresh capsule ID; the adapter additionally enforces replay history.
- `project_version` is an opaque version/fingerprint string. `chapter_version`
  is a nonnegative strict integer bounded by JavaScript's safe integer limit.
  Version `GTE` comparisons are available only for numeric chapter versions.
- Context and diagnostic lifetimes are positive and at most one hour. Checking
  that a snapshot is current requires `validate_capsule` and real host versions.

## Trust, content and privacy

`NONE` content is the default. Other content levels require an explicit scoped
consent receipt and the associated source identifiers. A wire `consent_id` is
not proof of user consent: a host must match its own receipt to the exact
request, session, scope and selected source. Event messages cannot carry text.

Privacy is `LOCAL_ONLY`, `REDACTION_REQUIRED`, or `CONSENTED_CLOUD`, from most to
least restrictive. Derived content inherits the strictest source; summaries do
not change this. No consent/redaction upgrade is implemented by a wire label.

Authority is `AUTHORITATIVE`, `CONSTRAINING`, `SUPPORTING`, or `ADVISORY`.
Authority labels are untrusted until checked against independently captured
`TrustedSourceProvenance`. That dataclass is local-only and must never be built
from incoming JSON or an LLM claim. All guidance and model recommendations are
advisory. `VERIFIED` requires authoritative evidence plus independent host
validation; merely parsing a result does not establish truth.

Evidence locators are bounded opaque labels such as `task:task-1` or
`runtime:runtime-1`. They are never dereferenced. File paths, URL locators,
credentials, screenshots, arbitrary logs and free-form diagnostic mappings are
not supported. Diagnostic metadata can be omitted in a preview. Structural
allowlists and a defense-in-depth secret-pattern check do not replace host
projection, sanitization and user preview.

## Transport boundary

`TransportRequest` and `TransportResponse` bind operations to exact typed
payloads; the response may instead carry `InteropError`. A byte transport may
frame their JSON with an unsigned little-endian 32-bit byte length, at most
1 MiB. The frame handler owns cancellation, authentication, replay protection,
heartbeats, disconnection and liveness. No DTO opens a socket or another app.

Development HTTP uses only an explicit `http://127.0.0.1:PORT` origin, no proxy,
no redirects, no LAN addresses and no token in a URL. The only session-token DTO
is the ephemeral `SessionOpenResult`; tokens never appear in model metadata,
discovery or logs. Current-user Named Pipe enforcement belongs in the Windows
transport, not caller-provided identity fields.

JSON Schema validates shape, bounds and declarative cross-field invariants.
Hashes, time freshness, provenance, real permissions, user gestures, transport
identity, source changes and cross-session response correlation require the
Python validators and the corresponding host adapters. Contract tests do not
constitute live Desktop integration or a claim of Windows runtime acceptance.
