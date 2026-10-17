# CreativeDirector passive binding foundation

Status: **implemented as inert contracts and persistence fences; scoped independent verification passed**.

This slice does **not** enable standalone Director model preview or dispatch. It does not claim model quality, a live model result, or full Director feature completion.

## Source and scope

- Worktree: `studio-creative-binding`
- Branch: `work/dot-creative-binding-20261017`
- Unchanged source baseline: `e011a0de0a21ddb2833b2689d76caf917165e706`
- Existing Timeline/NLE, Graph, anchored Director, SCREENPLAY/adaptation, Author request builder, broker, provider registry, and public coordinator/API remain their original owners.
- No second execution engine, fake chapter, synthetic Graph identity, executable preparer, public route, provider activation, schema migration, or PostgreSQL lock-class change was added.

## Implemented contract

`app/creative/director_binding.py` defines `CreativeDirectorBinding` and separate frozen local/collaboration scopes. All are strict and reject extra fields. Nested scope data contains no mutable dictionaries or lists. The required literals are `contract=CREATIVE_DIRECTOR_SOURCE_V1` and `source_kind=STORYBOARD`; omitted markers are not repaired with defaults.

The binding identifies the project, canonical original project incarnation, actor, exact scope, saved source document, bounded integer source version, source digest and reviewed-preview digest. File incarnation retains the original `file:<canonical UUIDv4>` convention; PostgreSQL retains `postgres:<canonical UUID>`. The preview digest is passive evidence, never consent or execution authority.

The new Job operation `creative_director_text` and origin `creative_director_source_model` are distinct from the original anchored `creative_director_model`. The optional `creative_director_binding` is omitted from legacy Job serialization; present values are deep-detached when exported.

### Saved-source validation

The initial supported source is an actual saved, nonarchived STORYBOARD with `source_independent is True`, exactly empty chapter IDs, chapter evidence, ancestry bindings and source privacy. Unsupported source classes fail before chapter or ancestor reads.

Validation holds the **original raw scope transaction**, then the original project owner, in the established scope→project order. It rejects pre-held project ownership or nested raw transactions. File validation holds `project_operation`, reads the existing canonical marker without provisioning it, then enters the original Creative owner lease. PostgreSQL uses the original owner lease. The original `CreativeService.get/assert_current` performs source validation against the active locked snapshot; a detached old snapshot is not treated as current evidence.

The exact saved source version/digest, project incarnation, actor and scope are checked. A final canonical comparison rejects accidental mutation of the raw scope snapshot. Missing File sources/markers do not create them. For a missing PostgreSQL scope/source, the mandatory exception rolls back the original transaction, including its possible `INSERT ON CONFLICT`; this behavior remains unverified against a live PostgreSQL database in this slice.

A successful return is a detached source snapshot, not a capability. Later source edits require fresh validation. The File serialization test uses the original `CreativeService.update` and verifies that it waits behind the held source scope lock.

### Passive request identity

`creative_director_request_payload_digest` uses its own `creative-director-request/1` domain. It covers the exact adapter payload, binding, job/project/actor/scope/operation/origin/profile, provider/model, explicit route fingerprint, synthetic-data flag, output-byte bound and deadline. It prepares no invocation and consults no provider.

Persisted new-domain records require a canonical 64-lowercase-hex `expected_request_digest`, immutable thereafter. Persistence validates digest syntax and identity only: it cannot prove equality with an unavailable request payload and does not reconstruct execution authority.

The original Graph and Author/SCREENPLAY hash functions remain unchanged. Before core edits, the actual original request builders produced a frozen fixture:

- Fixture: `tests/fixtures/creative_binding_legacy_requests.json`
- Fixture SHA-256: `640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac`
- Graph request digest: `c4543d9eb1914c395d38e08088642f407a20fec9c2345d6d01c039972ddf280c`
- SCREENPLAY request digest: `103b4c3fb49325ec39c4dca51e08ecb216e6ee76cdf6407f8715d2a0a9b0fe48`

Tests compare both the actual payloads and literal prechange hashes. They do not derive an expected hash from the modified implementation during the same test.

### Deny-by-default isolation and persistence

Any new binding, operation or origin independently marks the domain. A raw dictionary's reserved binding-key presence also marks it when null or malformed; normal legacy `Job` objects with the new field unset remain unchanged. All three persisted identifiers must agree, and mixed Graph/adaptation/Creative identities reject.

Barriers deny raw Author preparation/create before marker stripping or chapter reads, `start_prepared` before admission/thread creation, direct `_run` before persistence/router/terminal hooks, direct Author/Graph preparation guards, and `PreparedTextInvocation.bind/validate_job` before adapter work. Content, events, generic accept/reject/diff remain unavailable even with forged completed output, callbacks, or a prepared invocation.

File and PostgreSQL generation repositories consume the same original classifier. The existing project-owner persistence fence and nonprovisioning marker behavior are reused. New-domain discriminator/binding transitions are immutable, including complete removal on an existing job ID. Extra discriminator immutability is scoped to the new domain; legacy Graph/adaptation update semantics are preserved. Recovery may retain passive records and terminalize interrupted statuses but strips transient authority and never replays, dispatches or settles a broker reservation.

## PUBLIC packaging

`packaging/public-build.json` adds exactly the standard `app/creative/director_binding.py` module needed by the existing Jobs import. All other allowlist entries and PUBLIC/private isolation remain unchanged. Actual offline wheel and sdist builds include the module with its exact source hash; existing closure, standard safety inputs, private/forbidden payload and archive-integrity contracts pass. Artifact construction is not installed-package runtime acceptance.

## Primary verification

All checks ran in the dedicated worktree with source frozen, the original `scripts/run_v2_checks.py`, owned profile/basetemp paths, and the previously established clean backend interpreter. Startup origin checks were stdlib-only. The subsequent authorized baseline capture imported the original request-builder/data-model modules; it did not instantiate a JobManager, prepare or invoke a provider, or contact a database/network.

| Check | Result | Evidence stem under `docs/delivery/v2-development/` |
|---|---|---|
| Unchanged baseline actual payload/hash capture and frozen-fixture recheck | PASS | `creative-binding-baseline-{capture,fixture}-r1` |
| Foundation + persistence + protected backend suites | 496 passed; 390 deselected | `creative-binding-backend-r1` |
| Actual offline PUBLIC wheel/sdist and closure contracts | 87 passed; zero skipped | `creative-binding-packaging-r1` |
| Forced TypeScript build | PASS | `creative-binding-types-r1` |
| Production Vite build | PASS | `creative-binding-build-r1` |
| Original UI token guard | PASS, 52 files | `creative-binding-tokens-r1` |
| Focused existing Director/Graph UI suites | 100 passed across 6 files | `creative-binding-ui-r1` |

The backend set includes original model execution, generation incarnation, shared terminal protocol, origin guards/regression, broker cancellation/mounted behavior, source adaptation, and storyboard model contracts. Existing Starlette deprecation and Vite chunk-size warnings are retained. No primary failure was suppressed or repaired.

All primary before/after source maps are unchanged. The separately hashed PUBLIC manifest is also unchanged across packaging. Original baseline capture had 2,544 source entries; the only between-run fixture addition produced 2,545 for its recheck. Exact source maps, scripts, commands, raw logs, actual artifact receipts and checksums are linked by the [evidence index](delivery/v2-development/creative-binding-origin/evidence-index.json). Actual generated archives remain at the owned `.runtime` paths recorded in [artifact hashes](delivery/v2-development/creative-binding-origin/artifact-hashes.json).

## Independent verification

The independent baseline gate checked actual startup/module origins, all frozen baseline source hashes, literal canonical request hashes and exact fixture bytes before core edits. Final independent execution passed **134 cases, with 77 PostgreSQL-marked cases excluded and zero skips**, covering the new foundation/persistence and the previously omitted original `test_r4_model_broker.py` suite. Foundation/persistence reruns overlap primary coverage and must not be added as unique tests.

The independent review verified all **2,549** current runner-tracked source hashes, every primary log/receipt/source bracket, the unchanged literal golden fixture, and the separately checked PUBLIC manifest. It independently read and hashed the new module in the two actual wheels and two actual sdists; those artifacts were **inspected, not rebuilt** in the independent window. No scoped blocker remains. Report: [creative-binding-independent-review.json](delivery/v2-development/creative-binding-independent-review.json), SHA-256 `fb69dc5d8f899d270d85211f273b63a88db5ec80b051ff1e3f6a41673f55e735`.

## Still unavailable or unverified

Standalone source-independent Director preview/dispatch, executable preparation, live provider/model quality, and final user-facing feature acceptance remain unavailable. PostgreSQL execution, browser/geometry, native desktop, Windows, packaged runtime and full product/release acceptance were not performed. No installation, live provider, remote push, merge, tag or release was performed by this slice.
