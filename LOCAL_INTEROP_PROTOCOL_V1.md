# Local Interop Protocol V1

Protocol name: **PoemSeed Local Interop**. Protocol version: **1.0**.
Product versions are independent. Stable identities are `poemseed.creative.studio`
and `poemseed.tutor.desktop`; display names and URI registrations may change without
changing identity. Product roles are extensible through explicit protocol revision.
No role grants authority by itself.

## Boundary

Observe is not control. Context reading is not project writing. A recommendation
is not execution. A handoff is not automation. Model metadata is not a credential.
Tutor advice is not canon; verification never silently mutates a project.
Applications depend only on the separately versioned contract. Neither imports
another product's internal Python, TypeScript, Rust, database, or credential store.
The duplicated protocol source is freshly authored shared code; parity is checked
using the checked-in manifest. It is not a transfer of private application code.

## Handshake and lifetime

The order is HELLO, CAPABILITY_NEGOTIATION, SESSION. Exchange product and instance
identity, software and protocol versions, transport, nonce, privacy mode and the
intersection of supported capabilities. A session binds both instances, trusted
local user identity, negotiated version, nonce, capabilities and finite lifetime.
An application restart creates a new instance and invalidates previous sessions.
No capability is inferred from model output, an arbitrary request field or a URI.
An incompatible version fails with PROTOCOL_INCOMPATIBLE; no unknown fallback.

All protocol messages, including nested protocol messages, carry explicit
protocol_name and protocol_version on the wire. Strict models
reject unknown fields and invalid identities, hashes, enums and bounded values.
JSON Schema describes structural validation; Python validators additionally check
hash integrity, time, source version, content consent and privacy. Host provenance
and live authorization are not facts that wire JSON can attest for itself.

## Transport

The development HTTP transport is explicit opt-in on literal 127.0.0.1 only.
It does not resolve arbitrary hosts, use proxies, follow redirects, accept LAN
addresses, put authentication in a URL, install software or launch another app.
Discovery reads a bounded configured local endpoint; it does not scan files or
networks. The integration remains off on normal startup and in acceptance mode.

Windows framing reference: 4-byte unsigned little-endian JSON UTF-8 byte length,
maximum 1 MiB, followed by exactly that many bytes. Truncated, malformed, oversized
or non-object frames fail closed. The reference denies network logons, uses an
explicit current-user SID ACL, PIPE_REJECT_REMOTE_CLIENTS, non-inheritable handles,
local client server name and peer-user verification. It is not wired into either
real desktop runtime. Canonical payload validation and handshake authorization
must be applied above the transport before any data exchange.

Waits have deadlines and cancellation; late responses must match the still-live
request/session/instance and source versions. Disable/disconnect clears sessions,
subscriptions and pending operations. Event queues are bounded and coalesce state
updates. Failure of the optional bridge must not prevent either app's normal use.

## Artifacts and proof

Schemas and Python/TypeScript/Rust DTOs: contracts/local-interop/v1 and
local_interop_protocol. See LOCAL_INTEROP_TESTING.md and
LOCAL_INTEROP_REQUIREMENTS.json for exact implementation/evidence status.
A schema alone is not DONE. A synthetic peer is MOCK_ONLY. Actual tutor desktop
integration remains LOCAL_REQUIRED until real desktop source and runtime exist.
