# Local Interop V1 security boundary

## Trust and authorization

Studio's existing trusted local session, workspace membership and exact
project/storyline/branch authorization remain the source of access decisions.
The bridge must reuse those gates at snapshot creation, content confirmation,
event delivery, target navigation and after every awaited remote response.
A frontend permission label, a capsule's AUTHORITATIVE string, a claimed user ID,
a model completion or a user_gesture_id supplied by a peer is not authority.

Context evidence is matched to locally obtained TrustedSourceProvenance. Host
state may be AUTHORITATIVE; model advice is ADVISORY. Source IDs, versions and hashes must match; derived privacy must preserve or
strengthen source privacy. Evidence locators are opaque references and never trigger
file reads, URL requests, filesystem enumeration or private-path disclosure.

## Content consent

Level 0 contains app/feature/status/error/IDs/versions/runtime/model metadata.
Selected text, a chapter or specifically selected project context requires a
separate preview and explicit confirmation for that immutable scope/version.
Asking for advice does not consent to sending a manuscript. Dirty selection or a
changed chapter/project/version invalidates the preview rather than widening it.
Revoked permission invalidates cached previews, sessions and subsequent delivery.
A second independently authorized subscriber must continue after the first loses
access; revocation must not accidentally become either global denial or a leak.

## Data minimization

Diagnostics are allowlisted structured fields and permit per-field removal before
confirmation. They exclude manuscript, prompt, screenshot, arbitrary log dumps,
full local paths, DSN, API keys, cookies, OAuth/provider/vault tokens and secrets.
Model descriptors are explicit metadata projections; credential stores remain
separate and are never serialized or queried for interop. Model execution is not
a negotiated capability. Session authentication exists only in the bounded local
transport authentication channel, never model metadata or URL parameters.

Derived guidance, summaries, verification and case candidates inherit the most
restrictive source privacy. LOCAL_ONLY cannot turn into cloud permission because
a model paraphrased it. Redaction/consent must be independently established; this
bridge does not provide a cloud upload shortcut. Case candidates remain local
preview objects until explicit user approval plus the existing memory/case gate.

## Navigation and lifecycle

Handoff action semantics are OPEN_FEATURE/OPEN_PROJECT/OPEN_TASK (with explicit
chapter/session variants), independent of UI URI scheme. Only a local explicit
click can initiate navigation after host target-existence, source-version and
live authorization checks. Peer advice never auto-opens projects or runs models.

Sessions bind product, instance, trusted user, version, capabilities, nonce and
creation time. Restart, revoke, membership/scope/project change or disable stops
future events and rejects stale results. Requests are bounded, cancellable and
time-limited; queues coalesce. No arbitrary executable plugin or remote MCP.

## Evidence limits

Synthetic security tests prove tested boundary behavior only. The Windows pipe
reference is not a deployed desktop transport, and same-user smoke does not prove
a cross-user/native release gate. Historical security-review blocks remain
historical; new contract/security regressions do not close those prior reviews.
See the testing matrix for PASS, NOT_RUN, MOCK_ONLY and LOCAL_REQUIRED evidence.

## Development peer identity limitation

The development HTTP peer is an explicitly selected loopback endpoint. Its
ProductDescriptor is self-declared; nonce/session/capability validation does not
authenticate an installed product or prove the peer process has the current OS
user identity. Studio binds its own trusted host user/session and authorization;
that is distinct from mutual peer attestation. The standalone Windows transport
reference enforces current-user pipe ACLs, but is not wired into either product.
Real desktop mutual identity, native discovery and production transport binding
remain LOCAL_REQUIRED. Do not describe the HTTP reference as authenticated native
Desktop interoperability.

The current Studio event publisher polls authorized snapshots on a bounded timer;
it is not a direct hook into every application event source. Its emitted
project/task/chapter/model/runtime changes are exercised. Other protocol event
types remain contract-level until their owning sources are connected.

## Event consent correction

Ongoing events require their own positive, session/peer/scope-bound preview
approval. Merely connecting, viewing permissions, confirming one Ask request or
requesting a preview grants no continuous sharing. Chosen field groups apply to
payload, event names and change detection. In-flight delivery is guarded just
before yielding HTTP body bytes; cancellation cannot recall bytes already sent.
Preparing diagnostics pauses existing sharing and invalidates queued/prepared
grants. No silent auto-resume occurs. The ordinary one-shot context preview does
not erase an independently approved standing grant; its active categories and
Stop control remain visible.

See LOCAL_INTEROP_LIFECYCLE_LIMITS.md for exact expiry/heartbeat limits and the
acknowledged-disable versus best-effort UI-close boundary. A failed disconnect
can never be used as evidence that sharing stopped.
