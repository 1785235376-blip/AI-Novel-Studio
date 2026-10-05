# Provider Runtime 2.1D read-only routing service

`app.provider_runtime_v2_routing_service.route_provider_request(request)` is an
internal production entrypoint for an already-initialized Host. It accepts only
the existing strict `ProviderRoutingRequest`; there is no API, frontend, existing
generation-router, provider adapter, or execution integration in this change.

## Owner boundary

The service reads the already-loaded `app.dependencies` module, obtaining its
existing runtime registries, execution-node identity store and Model Center.
It deliberately does **not import dependencies**: importing that module could
initialize repositories, provision identities and consult Vault. Before Host
initialization the report says `HOST_NOT_INITIALIZED`; the service never starts,
repairs, migrates, or initializes those owners. This is an in-process boundary,
not authentication against malicious Python code with module access.

The private `_route_with_owners` seam exists for isolated tests. It is not a
client injection contract. Neither production entrypoint nor request can supply
candidates, inventory, authorization, compatibility, credentials, or trust.
The request's local node must exactly match the existing Host-owned identity;
the service rejects a mismatch rather than rewriting the request. Request user
and workspace UUIDs remain request context, never candidate ownership facts.
Budget ceilings remain restrictions. Nonempty `budget.approvals` is rejected as
`REQUEST_AUTHORITY_UNSUPPORTED`: the existing pure contract supports approval
facts, but this service has no Host approval owner and cannot trust client claims.

## Snapshot profile and policy

The service invokes the existing Model Center snapshot builder with Host owners,
then the existing hardware collector, then the unchanged `evaluate_routing`.
The bridge version must be exactly `2.1A-snapshot-1`. Each item must contain
exactly one valid candidate or a closed-enum rejection. Duplicate source keys,
malformed items and wrong node bindings invalidate the whole snapshot. Duplicate
route identities with distinct source keys reach the existing evaluator and
produce its `DENY / CONFLICTING_FACTS`, independent of enumeration order.

This version accepts only the current bridge's local profile: `DEVICE`, no
ownership/workspace attribution, no trust/self-hosting, no credential or ranking
estimates, `authorized=False` and `compatible=False`. Unexpected positive facts
produce `SNAPSHOT_PROFILE_UNSUPPORTED`; a future authority integration must be
reviewed explicitly. The service never copies user/workspace IDs into candidates,
sets cost to zero, turns healthy into compatible, or invents trust or approvals.

Consequently this is useful diagnostic orchestration, **not executable routing**.
Current accepted candidates remain `NO_COMPATIBLE_ROUTE`; empty/rejected snapshots
produce the evaluator's empty-source result. Missing source owners include:

- Exact model/runtime positive compatibility and execution authorization
- Execution-node user/workspace ownership, trust and self-hosting authority
- Authoritative per-request costs and, where needed, cloud budget approval
- Credential availability/authorization facts (no resolver is introduced)
- Production runtime requirements where absent from Model Center

These gaps are not repaired with defaults. An `ALLOW` from the independent pure
policy would still be advisory metadata, never an execution permission token.

## Diagnostics and failure semantics

`RoutingReport` and nested contracts are frozen strict Pydantic models. Reports
contain the unchanged routing decision, closed service codes, hardware status,
and bounded source counts/rejection-code aggregates. They contain no raw source
keys, rejection details, paths, endpoints, prompts, input payloads or exception
messages. `to_dict()` returns a detached JSON-ready copy. This excludes those
fields rather than promising arbitrary secret detection in opaque identifiers.

At most 1024 source items are accepted per report. A larger source is rejected
in full with `SNAPSHOT_LIMIT_EXCEEDED`, not truncated into a misleading routing
result. This bounds validation and diagnostics after the bridge returns; it does
not claim to bound the existing bridge's acquisition cost or registry size.
Aggregate entries are deterministically ordered by the existing rejection enum.
No source item count is guessed on failure: `snapshot_complete=False` distinguishes
unknown counts from a valid empty snapshot. Hardware failures retain validated
snapshot counts, but provide no hardware capability facts to policy.

Known inventory failures are allowlisted into hardware status. In particular
Linux retains `UNSUPPORTED_PLATFORM`; it is not replaced with host requirements,
Model Center profiles or fabricated RAM/VRAM. Unknown hardware exception codes
become `UNAVAILABLE`, and exception text is never serialized. A wrong-node
hardware snapshot is discarded and explicitly reported. Invalid requests or
source failures yield an unavailable empty-source decision plus service codes;
they are not presented as an evaluated valid candidate set.

## Side effects and verification

Orchestration performs no provider/model calls, credential or Vault lookup,
network/discovery/download, subprocess launch, runtime start/stop, persistence,
identity creation, policy mutation, plugin execution, or telemetry. The existing
hardware producer may read native Windows hardware and poll already-owned live
processes. Existing snapshot/identity owners may perform their normal read-only
reads; this is not a claim that native inventory collection is zero observation.
The composition over supplied test snapshots is independently tested with file,
network and subprocess traps.

Focused tests cover request/profile/version validation, explicit privacy settings,
request/bridge/hardware node mismatch, duplicate source and route facts, bounded
rejections, source failures and secret-canary exclusion, immutable reports, no Host
bootstrap, no new request authority, and unchanged identity/config files through
a real Model Center/registry bridge integration. Integration setup provisions
registries before the read-only operation and supplies a test-only runtime
architecture requirement and hardware facts; these are not production fallbacks.

Run:

```sh
.venv/bin/python -m pytest -q tests/test_provider_runtime_v2_routing_service.py
```
