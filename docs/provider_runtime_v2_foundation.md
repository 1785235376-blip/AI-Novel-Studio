# Provider Runtime 2.0 contract foundation

This is an independent, unwired metadata boundary. Nothing imports these modules
from an existing Provider, Model Center, plugin, API, frontend or DesktopHost.
No generation, downloads, model loading, runtime launching, credential lookup,
billing, scheduling, discovery, RPC or artifact transfer is implemented.

## Architecture and identities

Model Registry → Runtime facts → Provider Runtime 2.0 → Routing Policy → Execution target.
The final target is a **decision descriptor**, not an executed action.

| Contract | Meaning |
| --- | --- |
| ProviderIdentity | Registry identity of the service/adapter supplying capabilities |
| ModelIdentity | Registry identity of the model/version, independent of provider |
| RuntimeIdentity | Registry identity of a configured serving runtime/deployment |
| ExecutionNodeIdentity | Registry identity of the device or hosted execution target |
| CredentialScope | Authority boundary: SYSTEM, WORKSPACE, USER, EXECUTION_NODE |

Identities have different frozen types and UUID fields. A future normalizer maps
existing string registry IDs to these identities; no migration is performed here.
Runtime family, architecture, vendor and quantization also use registry UUIDs.
They are facts, not deductions from model names. These UUID namespaces and their
registries must be established by future integration; no universal hardware
compatibility is claimed by this phase.

The closed modality enum contains TEXT, IMAGE, VIDEO, TTS, AUDIO, EMBEDDING.
TTS means speech synthesis; AUDIO covers other audio generation/processing.
Capabilities declare modalities, input/output asset categories, streaming, batch,
context/output token limits, memory estimates and runtime requirements.
Unknown token limits cannot satisfy an explicit token requirement.

## Immutable, sanitized inputs

Contracts use strict, frozen Pydantic models, immutable tuples/frozensets and
forbid extra fields. JSON must enter through model_validate_json; Python callers
supply enum/UUID objects and immutable collections. Do not use model_construct,
unchecked model_copy updates or object.__setattr__ on untrusted input. These
Pydantic escape hatches bypass validation and are outside the supported boundary.

There are no arbitrary content, extension-map, URL, path, endpoint, command,
prompt or credential-value fields. A CredentialReference accepts only a UUID
handle, enum scope and UUID scope binding. The handle is an opaque lookup ID,
not a secret or an authorization grant. SYSTEM has no scope_id; all other scopes
require the matching workspace/user/target-node UUID. Credential facts must also
match the provider and affirm both availability and authorization.

Serialization tests reject API-key/token/password/secret fields and raw strings
in credential handles. This is schema exclusion, not a claim to detect all
possible secrets: a malicious caller can encode data in any identifier, including
a UUID. Producers must supply registry-issued opaque IDs, never transformed
secrets. Validation error objects can include rejected input; do not log them
unredacted. The evaluator never reads Vault, environment variables or secrets.

Availability separates configured, installed, healthy, reachable, authorized and
compatible. All six must be true. For hosted API candidates, installed means the
required adapter/deployment is provisioned, not that a local model was downloaded.
For non-cloud targets, a matching sanitized node hardware snapshot is required:
architecture, runtime family, optional GPU vendor and sufficient RAM/VRAM. Memory
checks use the greater of minimum requirements and supplied estimates. Cloud
compatibility relies on normalized remote availability, never the client's GPU.
Unknown hardware cannot establish local compatibility; no probing occurs.

All availability, ownership, trust, compatibility, credential and approval facts
must come from an authenticated trusted producer. This pure function cannot
verify their provenance or freshness. ALLOW is advisory metadata, not an execution
permission token. A future executor must revalidate current authorization,
approval, health, budget and resources atomically before invoking anything.

## Privacy and execution order

| Policy | Eligible locations |
| --- | --- |
| DEVICE_ONLY | Exact request local node only |
| SELF_HOSTED_ONLY | Local/trusted nodes additionally marked self_hosted; never CLOUD |
| TRUSTED_WORKSPACE_NODES | Local device, trusted same-user nodes, trusted nodes in request workspace |
| CLOUD_ALLOWED | Those locations plus cloud |

The request's candidate_locations is an additional restriction, never a privacy
override. DEVICE must match local_node and user ownership. SAME_USER_NODE needs
matching user ownership and trust. WORKSPACE_NODE needs matching workspace and
trust. Non-device locations cannot reuse the local node identity. CLOUD with a
self_hosted claim is rejected as contradictory. Here self-hosted describes control
of a trusted non-cloud target, not the physical location of a rented server.

Unavailable local execution never broadens privacy. If nothing qualifies, return
NO_COMPATIBLE_ROUTE; duplicate route/node/credential-provider facts return DENY
with CONFLICTING_FACTS rather than accepting order-dependent facts.

## Ranking, budget and decisions

1. Exclude candidates failing availability, location/privacy, credential,
   capability, hardware or budget requirements.
2. Unknown estimated cost is excluded, not assumed free. Cost uses integer
   micro-USD per request; default maximum is zero. All targets obey the ceiling.
3. Paid cloud requires a supplied approval bound to the full route identity,
   user, workspace and a sufficient cost ceiling. Cloud privacy permission alone
   is not cost approval. Missing approval produces REQUIRES_APPROVAL if no
   otherwise executable route exists. Free cloud still needs CLOUD_ALLOWED.
4. Prefer executable routes over approval-pending routes. Within either pool:
   DEVICE → SAME_USER_NODE → WORKSPACE_NODE → CLOUD.
5. Within a location, apply request.preferences lexicographically. QUALITY is
   descending; COST and LATENCY are ascending. Unknown quality/latency ranks last.
   Default is COST, LATENCY, QUALITY. There are no weights; dimensions may be
   omitted, but cannot repeat. Preferences never override privacy or location.
6. Final tie-break is provider/model/runtime/node UUID numeric order. Candidate
   enumeration order has no effect. Quality is a caller-normalized 0–100 estimate,
   not a model-name ranking or a benchmark claim.

Budget approvals are sanitized current facts, not durable approval records.
The future cost authority must enforce expiry, revocation, consumption and price
changes. No clock or billing state exists in this evaluator. A decision's policy
version is `2.0-contract-1`; unsupported versions are rejected.

ALLOW carries selected identity and optional opaque credential handle.
REQUIRES_APPROVAL carries identity but no credential handle. DENY and
NO_COMPATIBLE_ROUTE carry neither. Reasons are closed enums. Empty candidate sets
use NO_CANDIDATES; filtered sets use NO_ELIGIBLE_CANDIDATE. This version deliberately
does not expose per-candidate rejection telemetry or arbitrary diagnostic strings.

## Future boundaries

- Model Center supplies normalized registry/runtime/hardware facts. Provider
  Runtime consumes them and decides routing. No Phase 2A or current registry code
  is changed or imported; an integration adapter is future work.
- Team Compute Fabric may later resolve execution nodes and revalidate/execute
  decisions. No scheduler, network discovery, LAN RPC or transfer is included.
- Plugin Platform may later register Provider capabilities through a validated
  normalizer. No dependency on AppContainer, Trust/Signing or plugin execution.
- TEXT/IMAGE/VIDEO/TTS and AUDIO/EMBEDDING use the same explicit metadata boundary.
  Existing adapters remain unchanged; no frontend or real multimodal calls exist.

## Verification

Run the two new test files with pytest. Their local autouse fixture deliberately
shadows the root fixture to avoid initializing application runtime and Vault.
Adversarial tests exercise privacy, each availability dimension, credential scopes,
missing/incompatible hardware, modality/capability mismatch, cost approvals,
deterministic permutations and no-candidate decisions. Static import checks limit
the production dependencies; dynamic traps reject filesystem/network/subprocess
operations while evaluating decisions. Test setup and Git/dependency operations
are not part of the evaluator's zero-I/O guarantee.

### Recorded verification (2026-08-30)

Base: `b31b97d1263e1d492d131e9e9d3d09ffa54c19ab` (origin/main fetched before branching).
Python 3.12.13, pytest 8.4.2, Pydantic 2.13.5; isolated test environment.

- New targeted tests: **44 passed**.
- Existing Provider tests (retry, OpenAI-compatible v0.7.0, asset config/adapter/
  contract/catalog API, audio providers/config, runtime status, credential
  lifecycle): **55 passed**.
- Model Center Phase 1: **83 passed**.
- Final full backend: **1208 passed, 4 failed, 28 skipped**.
- Unmodified base full backend in separate worktree, same interpreter/dependencies:
  **1164 passed, 4 failed, 28 skipped**.
- New regressions: **0**; identical four failure node IDs on both trees.
- `git diff --check` and staged diff check: **PASS**.

Existing failures, left unchanged and outside this branch's ownership:

1. `test_plugin_runtime_phase2a_worker_isolation.py::test_spawned_worker_environ_has_no_inherited_python_star`
2. `test_plugin_runtime_phase2a_worker_isolation.py::test_hostile_cwd_does_not_replace_host_worker`
3. `test_user_preference_service.py::test_preferences_are_explicit_and_separate`
4. `test_world_rule_payload.py::test_world_rule_payload_normalizes_terms`

The first two encounter missing child-process `/proc` state in this environment;
the latter two are expectation mismatches reproduced on the base. Full backend
is therefore **not green**, despite zero new regressions. Both suites also emit
the same Starlette/httpx deprecation warning. No baseline failures were fixed.
