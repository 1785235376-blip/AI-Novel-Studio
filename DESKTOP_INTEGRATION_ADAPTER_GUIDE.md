# Desktop Integration Adapter Guide

## Scope and frozen baseline

This is Local Interop V1 **Desktop Integration Preparation**, not a claim that QingJian Desktop has been integrated. Creative Studio starts at `bcd60afb96cc69bdfd81db619cb0121d8712f074`; QingJian Cloud starts at `7f5cc4252a9c1ab078e0ace509a4d12012c1dc76`. Both new branches are `work/local-interop-desktop-prep`; historical PRs are not modified.

The protocol is **PoemSeed Local Interop 1.0**. Product IDs stay `poemseed.creative.studio` and `poemseed.tutor.desktop`. All 37 original shared files and their manifest stay byte-identical: SHA-256 `77c1f82f0aec0ef385d95cacf6fe04530b83fb62d2403bc7341cbe6bf19c858c`. The seven existing protocol/security/capability/context/Tutor/testing/compatibility documents continue to define the wire boundary.

The additional Python `local_interop_desktop` package and Windows `native/local_interop_desktop` library are newly authored shared integration code. They do not import the other product's business implementation. Private QingJian adapters are kept in the private repository.

## Composition

```text
Frozen V1 DTOs / semantic validators
    → InteropTransport, trust, lifecycle, event registry
    → product-owned Context / Tutor / Verifier / Case / Model / Handoff adapters
    → platform byte I/O and connected-handle facts
    → existing product owners
```

Transport does not read a business database. Studio context continues to read its existing project, chapter, task, Model Center and runtime owners. Context is not replicated into another state database. Settings, credentials, trust approvals and application lifecycle are independently owned by each product.

## Callable SDK ports

- `InteropTransport(adapter, product, attestation, enabled=False, acceptance_mode=False, ...)`: async start, connect, request, send, subscribe, unsubscribe, cancel, disconnect, stop and shutdown; typed health, peer identity and observable snapshots.
- A platform adapter supplies async `start`, `stop`, `connect`, `disconnect`, `exchange` and `refresh_peer_facts`. Exchanges use the unchanged V1 `TransportRequest` / `TransportResponse`; connected-handle facts travel only through trusted in-process calls, never in peer JSON.
- `InteropPeerDiscovery` reads bounded, explicitly registered installation/running-instance/pipe sources. It performs no filesystem or process-content search and launches nothing.
- `ProductionPeerAttestation` joins current-user facts, matching installation identity, binary/path hashes, publisher/signature policy and explicit local trust approval. `InteropPeerTrustStore` serializes only allowlisted non-secret trust records and revocation. An executable-path hash or claimed product ID alone is never authentication.
- `InteropLifecycleCoordinator` records app/bridge/peer/session/sleep/shutdown/restart transitions and closes under a fixed deadline. Restart constructs a new instance and never reloads sessions, requests, cancellation tokens or standing grants.
- `InteropContextProvider` exposes current product/project/surface/task/model/runtime, selected-content metadata and scope-bound capsule construction. The product remains the authorization owner.
- `InteropEventSourceRegistry` registers PROJECT, CHAPTER, TASK, MODEL, RUNTIME, EXPORT and WORKFLOW sources; direct and bounded polling sources have explicit provenance. Enqueue and delivery both check live authorization. Coalescing, queue limits, idle backoff, expiry, pause/resume and subscriber-specific revoke are implemented.
- `InteropModelRegistryCache` reparses strict V1 metadata and reports STALE after TTL or refresh failure. No credentials, endpoint secrets, prompts, input or model-directory scan.
- `UserPresenceGate.issue_target` binds one short-lived local click/dialog token to the complete semantic target and optional session; `InteropHandoffHandler` consumes it once and checks current host resolution. Peer advice cannot mint this token. Studio supports existing generation-task navigation. Exact export/workflow task-ID navigation is PARTIAL because those panels expose no existing selected-task route; such targets fail with HANDOFF_TARGET_NOT_FOUND. OPEN_FEATURE navigation still works, and no shadow task UI is created.
- `InteropAudit` and `InteropDiagnosticSnapshot` accept bounded enumerated metadata, not arbitrary exception text, source content or absolute private paths.

The five connection facts are distinct: physical connection, protocol handshake, peer authentication, session establishment and capability negotiation. Capability negotiation represents supported operations, not user consent. Sensitive requests need a fresh, product-owned authorization callback immediately around dispatch/delivery. UI must use typed states, never infer state from an exception string.

## Studio runtime and UI

`app/local_interop` composes these ports with existing authorization and actual owners. PROJECT/CHAPTER/TASK notifications are hooked at successful owner writes; MODEL/RUNTIME/EXPORT/WORKFLOW retain explicitly labelled polling where no complete native producer is available. Business producers do not import or call Tutor.

The existing lazy-loaded Tutor Integration area exposes product identity/version/protocol/trust/transport, session age/expiry, capabilities, standing permissions, formal stages and seven-part health. Permission categories are independently revocable: app status, task status, model metadata, diagnostics, selection, current chapter, specific context, standing metadata events and deep link. Emergency Disconnect & Revoke requires the complete backend receipt; failed or uncertain acknowledgement remains unknown. It never deletes projects, Tutor memory or cases.

Development HTTP remains an **UNVERIFIED reference path** and is not promoted into a production installation identity. Native Desktop composition remains LOCAL_REQUIRED. Direct sources are not falsely labelled as full real-time coverage; polling evidence remains visible.

The frontend keeps its ordinary entry hook small and defers integration/dialog code until needed. Initial/deferred production bundle bytes are measured in the UI receipt. Bundle size does not prove user-machine startup latency; actual desktop startup/CPU measurements remain NOT_RUN.

## QingJian source mapping and write gates

The private Cloud repository has functional reference policy and Context V2/Tutor/Verifier/Case contracts. It does not contain the complete real QingJian Desktop runtime. The prepared private composition requires host-owned Recall Gate, ContextAssembler, live source/permission snapshots, Memory Gate and Case Gate callbacks. Missing required owners fail closed. It does not invent an `InteropMemoryStore`, write imported context automatically, or send local cases to Cloud CaseDB.

Context ingress retains authority, privacy, evidence, source version and task/project scope. It maps appropriate existing Context V2 categories without promoting observations into VERIFIED_CASE. Memory is always candidate → policy → explicit approval/trusted bounded rule → existing Memory Gate → existing Store. Cases similarly require exact preview → approval → current gate → store. Context reception alone is not a candidate approval.

Verifier re-reads the current host source and permission revision before executing and again before accepting a result. Changed project, chapter version, source evidence or permissions produce a stale/UNKNOWN/denied result; advice never repairs business state. Studio does not learn which internal Tutor model is used.

## Windows boundary

The callable library is `native/local_interop_desktop/PoemSeed.LocalInterop.Pipes`. The original eight-check reference runner remains in `interop-reference/PoemSeed.LocalInterop.Pipes` and references that library rather than owning an isolated copy. The new acceptance runner adds bounded I/O and identity/trust checks.

```sh
dotnet build native/local_interop_desktop/PoemSeed.LocalInterop.Pipes -c Release
dotnet run --project native/local_interop_desktop/PoemSeed.LocalInterop.Pipes.Acceptance -c Release
```

The server uses current-user SID ACL, network-logon denial, remote-client rejection and non-inheritable handles; clients cannot provide a remote host or arbitrary pipe path. The library supplies framed bounded JSON, malformed-frame rejection, finite timeouts, cancellation, connection limits and backpressure. Connected-handle PID/SID and executable/signature/install evidence are separate from claimed product fields. The host owns installation registration and user-approved trust.

Portable compilation or same-user Windows tests do not prove a different user cannot connect. Use the committed native cross-user harness under two genuine Windows identities. Do not fabricate signing/install evidence, weaken Windows policy, enter credentials into the harness, or substitute synthetic SID comparison for the hostile cross-user test.

## Acceptance and evidence

```sh
python -m pytest -q tests/test_local_interop*.py
python -m local_interop_desktop.acceptance --mock-only --output receipts/desktop-acceptance.json
python scripts/check_desktop_integration.py
```

`DesktopInteropAcceptanceHarness` executes all A01–A24 procedures with an injected `DesktopAcceptanceAdapter`; the compiled-in `SyntheticAcceptanceAdapter` uses actual SDK operations over in-memory frozen V1 messages. No dynamic plugin loader, provider/model call, listener, product launch or real content is involved. A future Desktop test host supplies seeded synthetic fixture controls at the prepared ports and runs the same procedures. Real platform probes, real product-owner integration tests and actual two-product acceptance must accompany it; the bundled report always keeps native acceptance LOCAL_REQUIRED and A21 NOT_RUN.

See `DESKTOP_INTEROP_ACCEPTANCE_MATRIX.md/json` and all 69 rows of `DESKTOP_INTEGRATION_READINESS_MATRIX.md/json`. Original File/PostgreSQL/frontend/browser/Windows/Interop and private Cloud/UI/SDK/browser gates remain applicable. Counts overlap; do not sum them as unique tests. Final exact-head source/tree/CI receipt belongs in the Draft PR metadata to avoid a documentation-only retest loop.

Historical independent security review remains BLOCKED and is not resumed, replaced or closed by these new implementation tests. Raw private hosted logs and internal notes are not copied into public artifacts.

## Compatibility findings: no V1 wire change

1. OS identity and local trust are not peer claims. They are injected by the trusted platform adapter rather than added to the V1 wire.
2. Connection stages, UI health, permission center state and event-source provenance are local adapter metadata. They do not alter authority/privacy/evidence semantics.
3. Existing V1 capsules carry readonly context. Memory/Case submission uses prepared local gate ports; no interop write capability is added.
4. A future product advertising `1.0` and `1.1` can select existing `1.0`. A `1.1`-only peer cannot be silently interpreted as 1.0; a future optional-extension proposal is needed. Unknown breaking versions fail closed.
5. A compatible product version change at the same approved identity/installation, unchanged trust and unchanged capability scope does not revoke an active permission solely for its version string. Identity, installation, publisher/signature or scope changes invalidate sensitive use. Restart/reconnect is a separate event and always requires a fresh session and explicit standing grants; no persisted grant restoration is introduced.

## Future real Desktop integration sequence

1. Inspect the real Desktop source and current owner contracts.
2. Map existing owners using `QINGJIAN_DESKTOP_MAPPING_CHECKLIST.md`.
3. Implement the prepared product/platform adapters; do not replace owner systems.
4. Preserve protocol parity, content consent, Memory/Case gates and independent settings.
5. Run original and new contract/product integration tests.
6. Run real Windows Named Pipe, signature/installation and distinct-user tests.
7. Run actual two-product A01–A24 acceptance, restart/crash/offline and user-machine UI checks using synthetic fixtures.
8. Only after review and separate authorization, consider the Beta flag. It remains OFF here; V1 acceptance mode forces OFF.

Observe != Control. Context != Permission. Advice != Action. Verification != Mutation. Model Metadata != Credential. Connection != Authorization. Product ID != Product Authentication. Reference Implementation != Desktop Integration. CI Green != Real Desktop Acceptance.
