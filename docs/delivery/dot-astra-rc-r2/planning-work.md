# D05 / D06 / D07 structured planning review

## Delivered

- `AIPlanningService` is a bounded, persistent planning-to-review path for STYLE, PLOT, HISTORY, GEOGRAPHY, CIVILIZATION, ABILITY and PSYCHOLOGY proposals. It calls the existing registered `runtime.prepare_text_route` / `TextModelNode` execution contract. There is no fake success, hidden fallback, automatic retry, or paid-provider call in verification.
- Requests accept one to three source chapter IDs with optimistic versions. The host captures SHA-256 plus version and branch scope. Model context is limited to the first 16,000 Unicode characters of each chapter, explicitly marked when truncated. Model JSON is limited to 80,000 characters, one to three candidates, strict workbench fields, and exact quote/start/end evidence validation. Model-supplied entity links are rejected; chapter IDs and LOCAL_ONLY candidate privacy are host-assigned.
- Runs persist request configuration, source manifest, status, candidates, evidence, usage-known/unknown, actual execution mode/provider identity, safe error code, and timestamps in the existing durable capability sidecar (`planning_runs`). Reopen is supported. Interrupted work is marked FAILED instead of replaying a possibly billed request. Cancellation/timeouts discard late responses; an already-dispatched provider request cannot be recalled.
- Before dispatch and after inference, the captured authorization is rechecked. Actual provider egress, persisted same-branch/hash/version chapter privacy, and independent project-source policies are authoritative. Cloud permission cannot come from a client `target`, `allow_cloud` Boolean or model output. Restrictive/unknown knowledge policies and explicitly restrictive novel/outline policies block raw cloud excerpts.
- Results are suggestions. Explicitly selecting “保存此候选为草稿” creates one idempotent DRAFT in `creation_records`, retaining run/candidate/provider provenance and exact evidence. A lost run checkpoint cannot duplicate the creation record. Existing user editing, comparison, approval, history and restore remain required. No manuscript or Canon write occurs here. Workbench approval and generation now also verify source content hashes, guarding same-version changes.
- A separate local extractor recognizes explicit `世界规则：`, `能力规则：`, `规则：`, `World rule:` and `Ability rule:` lines. Exact duplicate rules are deduplicated only within one chapter. Complete Chinese/English Act 1/2/3, Conflict, Climax, Ending markers produce a PLOT draft. Missing or duplicate plot fields produce review findings, never invented filler. This does not change the existing four-group character/location/timeline/foreshadow import journal.

## API and UI contracts

Authenticated with existing workbench authorizer; all data is scoped to the same novel/branch:

- GET /novels/{nid}/planning-runs
- POST /novels/{nid}/planning-runs
- GET /novels/{nid}/planning-runs/{rid}
- POST /novels/{nid}/planning-runs/{rid}/cancel
- POST /novels/{nid}/planning-runs/{rid}/candidates/{cid}/save-draft

Action bodies require `expected_version`; current conflicts are 409. Reads require `domain.read`, mutations require `domain.write`. Source IDs, expected versions, mode, type and registered model route comprise the creation body; no client privacy override is accepted.

`AIPlanningPanel.tsx` is embedded in `CreationWorkbenchPanel` beneath “AI 结构化方案与明确规则提取”. It reuses DS-v1.0 primitives, tokens, existing comparison layout, and passes the captured collaboration context to every API request. Local extraction is the default. It covers request loading, empty, failed, pending, cancelled, ready, candidate evidence, saved Draft, configuration reuse and reopened history. Changing project/branch suppresses late UI responses; duplicate submissions are blocked. The existing manual form keeps unsaved input when a candidate is saved.

## Verification performed

Environment: Linux isolated runtime-data root; stub provider adapters only. No user material, credentials or remote inference used.

- `r2-run.sh python -m pytest -q tests/test_r2_ai_planning.py tests/test_r2_planning_app_routes.py tests/test_r2_creation_workbench.py`: **40 passed**, including 27 planning cases, two real mounted app route flows and 11 existing workbench cases.
- Frontend Vitest invocation ran the full available suite: **101 files, 481 tests passed**, including six new planning UI cases and four existing workbench UI cases.
- `pnpm exec tsc -b`: **PASS** after frontend additions.
- `pnpm lint`: **PASS** (UI token guard, 39 checked files).
- Local browser visual/geometry run: **BLOCKED** by the integration environment (bundled browser download invalid; system Chrome socket EPERM, independently confirmed by integration workers). Hosted CI owns these checks. No local visual acceptance is claimed.

The two integration flows verify both `/api` and `/api/v1` against the actual mounted application with an isolated File repository: queued → ready → explicit Draft save → manual approval → persisted reopen, without manuscript or Canon changes.

Coverage includes Draft-only promotion, persistence/reopen, duplicate-promotion checkpoint retry, same-version hash change, source version change, missing/revoked/wrong-branch cloud review, restricted project facts, reauthorization denial, forged evidence/IDs, invalid JSON, cancellation and timeout late responses, interrupted recovery without replay, scope isolation, corrupt-store preservation, bilingual explicit markers, missing/duplicate fields, and long-source offsets.

## Remaining limits and user acceptance

- Real local/cloud provider inference, output quality, actual billing/usage, GPU, Windows execution and user-machine acceptance: **NOT_RUN** here. Synthetic adapters are labeled `mock_standin`.
- Native PostgreSQL storage for planning/workbench is not claimed. These features use the existing durable sidecar in both profiles and the existing single-host process model; distributed multi-host task ownership is not provided.
- This is structured proposal generation and exact evidence validation, not a semantic truth/continuity engine. Correct quotes do not prove model conclusions. Whole-book hierarchical outline/volume/chapter/scene generation, inferred rule extraction from arbitrary prose, and automatic promotion into Canon are not implemented by this path.
- Local rule extraction is deliberately explicit-marker-only. World rules are stored as the existing typed ABILITY records. Partial plot fields are review findings; authors complete the source markers or use the manual PLOT editor.
- The UI currently starts from one selected chapter; the API supports up to three. Model excerpts are deliberately truncated, and the UI exposes this fact. Full-book chunk scheduling is not claimed.
- On a configured machine: create local marked rule/plot examples, save Draft, edit, compare, approve, archive/restore, reload; run a real local model and check its valid strict JSON/evidence; cancel a slow run; edit a source and verify failure; for cloud separately review source privacy and confirm independent private knowledge still blocks egress.
