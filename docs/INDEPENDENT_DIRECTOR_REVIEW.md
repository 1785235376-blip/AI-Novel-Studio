# Independent Director private live review

Status: **implemented; final primary and independent scoped verification passed**.

This slice adds private, live schema-bound candidate inspection and explicit human adoption into a separate Director DRAFT. It does **not** enable public independent Director preview, dispatch, capability advertisements, content, refresh, candidate adoption or generic generation review. It does not establish live-model quality or full feature completion.

## Source and ownership

- Worktree: `studio-director-review`
- Branch: `work/dot-director-review-20261017`
- Baseline: `586c388b09844d2587043effb4b51955c17f8bb5`
- Runtime changes: `app/creative/generation.py`, `app/creative/proposals.py`, `app/creative/storyboard_model.py`
- Additive tests: `tests/test_v2_creative_director_review_contract.py`, `tests/test_v2_independent_director_adoption.py`

The original DirectorModelCoordinator owns private preview/result access. DirectorProposalService retains the original review commit owner through a shared private adoption core. The original Creative document service, raw scope transaction, project owner lease, source ancestry, version/history and capacity checks remain authoritative. No second review service, execution engine, owner registry or transaction class is added. Jobs, broker, invocation seals, historical internal-domain classifier, public API/UI, assets, Graph, media and workflow owners are unchanged. Existing tests and the actual Graph/SCREENPLAY request fixture remain byte-exact.

## Explicit schema opt-in, unchanged default

The original `_preview_independent` retains its V1 free-text internal draft prompt/request. It is not silently upgraded to a review contract.

A separate private `_preview_independent_review` opts into the original `DirectorStoryboardModelOutput` schema and `STORYBOARD_SHOT_CONTEXT_V1` source mapping/prompt. The internal preview records the output contract, which is covered by the existing preview/request identity and original sealed dispatch. The legacy anchored storyboard prompt data is factored without changing its request content. The old parser preserves its byte-bound → current source → JSON syntax → bound-contract → semantic-validation error order.

The shared pure parser validates bounded UTF-8, duplicate-key-free JSON, strict schema, exact source ID/version/digest, and exact note ID/scene/shot/number association in authored shot order. Every model note requires planning, uncertainty and evidence or explicitly speculative assumptions. Evidence may reference only the associated scene's supported fields and exact excerpts, with a valid dialogue index where required. Shot-field evidence is unsupported. Reference validity is not semantic, spatial, axis, eyeline or continuity verification.

## Detached candidates and explicit review

`_read_independent_candidates` exclusively obtains text through the original `_read_independent_result` live seam, then parses it. It returns detached notes, the exact candidate digest, current proposal version, visual target and whitelisted provenance. It writes no pending candidate, status, version, history, ledger or Job record. A default V1 preview remains ineligible even if its output happens to look like valid strict JSON.

`_review_independent` consumes the existing `DirectorProposalReview`: expected proposal version, reviewed output digest, explicit human-edited notes/title and optional visual-target edit. It rereads/reparses the exact live result, compares the reviewed digest and retains original shot associations. The shared original adoption core validates edited content and preserves the existing omitted-versus-explicit-null visual-target semantics.

The core creates the original document mode `DIRECTOR` with `director_notes`, not a new document mode. The separate document defaults to `DRAFT`, has `source_independent=False`, and has real storyboard `source_documents` ancestry containing exact source version/digest. It survives reopening the original File service. No asset, graph, media or workflow adoption occurs. The original proposal is approved in the same atomic commit, retains its internal marker and original source-shot snapshots, and remains publicly projected as unavailable. There is no unmarked clone or public bypass flag.

Safe adopted provenance includes actual provider/model IDs, model-version evidence, route fingerprint, synthetic flag and bounded request parameters; source identity/version/digest and exact mapping; Job/reservation IDs; request/preview/raw-output/candidate/edited-output digests; and reviewer/time. Raw authored source-shot snapshots stay on the original proposal. The derived provenance contains no prompt, token, execution seal, callback, full route identity or saved verified boolean.

## Lock order and atomic boundary

Candidate reads and adoption reject caller-preheld raw/Creative scope or project-owner leases before routing reads. Routing-only lookup selects a Job; it is not authorization. The new path acquires the original Job condition **before** the original raw scope transaction and project owner, matching terminal settlement's condition → scope → owner order. Waiting is bounded by the remaining captured original generation deadline, and changed bounds fail closed. No manager lock or generic review-mutation lock is added.

Inside those locks, the exact current Job object, proposal, actor/scope, Host authority, incarnation, saved source, selected route, license/price/budget policy, durable completed Job receipt and SETTLED zero-cost accounting are rechecked. Holding the condition through commit prevents adoption from racing the worker's final post-publication execution check.

The shared adoption core mutates the actual active raw state. There is no nested raw transaction or second commit. Quotas use a fresh view from the original Creative store and current owner identity, so retained older-incarnation records do not consume current quotas. All payload/provenance preparation completes before the final full live reread and execution-bound check immediately before insertion. Failures roll back the whole scope transaction. After approval changes the admitted proposal version, checks use current actor/Host/source/incarnation only; the old admitted-version capability is never called again by the adoption path.

## Deadline, restart and deferred durable pending review

Candidates remain available only within the original live execution deadline. The proposal's admitted version/status/receipt/preview/visual target are frozen by the live capability; persisting pending candidates before adoption would invalidate that authority. No new `CANDIDATES`/`NEEDS_REVIEW` transition or durable pending-review authority is introduced. Only an already-adopted DRAFT is reusable after restart.

Capturing or adopting a pending candidate after expiry/restart is **deferred**. That extension requires an explicitly designed, write-once authoritative terminal-evidence contract, including its producer, exact identity/content/accounting bindings, irreversible finalization and review rules. The current mutable persisted Job, its output, a matching hash or a saved `verified` boolean is not review authority. This slice does not reconstruct a seal or extend an execution deadline to support later review.

## Primary verification

Normal interpreter startup and the actual unchanged `scripts/run_v2_checks.py` child import locations were proven before product imports. Runs use the established clean interpreter, current worktree and owned profiles/basetemp paths. Source remained frozen during every run. No primary test failure was suppressed.

| Phase/check | Result | Receipt stem under `docs/delivery/v2-development/` |
|---|---|---|
| Initial r1 combined backend | 966 passed; 551 deselected; zero skipped | `director-review-backend-r1` |
| Final r2 combined backend | 968 passed; 551 deselected; zero skipped | `director-review-backend-r2` |
| Final actual offline PUBLIC wheel/sdist/closure | 87 passed; zero skipped | `director-review-packaging-r2` |
| Forced TypeScript build | PASS | `director-review-types-r2` |
| Production Vite build | PASS | `director-review-build-r2` |
| Original UI token guard | PASS; 52 files | `director-review-tokens-r2` |
| Six unchanged bounded Director/Graph UI suites | 100 passed | `director-review-ui-r2` |

r1 and r2 are separate source brackets, not additive test totals. After r1 passed, an explicit narrow thaw added only actual model-version/route-fingerprint provenance and two new integration cases: strict-looking output under the old default contract, and actual post-adoption public isolation. r2 is the final source. PostgreSQL-marked exclusions use `-m 'not postgres_backend_only'`; they are not passes or skips. The existing Starlette deprecation and Vite chunk-size warnings remain.

The combined suites cover original File owners and real worker threads with mocked transport on the original verified external-local adapter, concurrent reviews, bounded condition waiting, terminal-publication races, cancellation/revocation/deadline, source/route/receipt/accounting changes, preparation-boundary faults, atomic rollback, restart and public isolation. They also retain original proposal/rule-assisted storyboard, model planning/contract, authority-read, source-adaptation, lifecycle/foundation, model-execution, terminal and broker regressions. These tests establish bounded protocol behavior, not model quality.

All **2,554** final source hashes agree across r2 origin/backend/packaging/frontend receipts, and every before/after bracket is unchanged. The original PUBLIC manifest is separately unchanged. Frozen Graph/SCREENPLAY fixture SHA-256 remains `640ca3823d83a378b9018a180957d375b9cef6b524f2e527f7e731236cfd90ac`.

The [primary evidence index](delivery/v2-development/director-review-origin/primary-evidence-index.json) separates r1/r2 commands, exact source maps, receipts and raw logs. [Actual artifact hashes](delivery/v2-development/director-review-origin/artifact-hashes.json) identify two wheels and two sdists built offline, copied build/stage receipts, and reopened archive checks for all three changed runtime modules plus the passive binding module. Archive construction/inspection is not installed-package runtime acceptance.

## Independent verification and remaining gates

Independent scoped verification passed **391 cases with 102 PostgreSQL-marked exclusions and zero skips** in 189.17 seconds. These reruns overlap primary coverage and must not be added as unique test totals. The reviewer verified all **2,554** final source hashes, stable source brackets and exact log hashes, **660** unchanged baseline test files, the frozen fixture, unchanged PUBLIC manifest and seven final primary receipts. Both actual wheels (507 recorded payload entries each) and both actual sdists (508 each) were fully payload-hashed, including the current core modules. These archives were inspected, **not rebuilt**, during independent review. No scoped blocker remains.

The [independent audit report](delivery/v2-development/director-review-independent-audit.json) has SHA-256 `9b4c18ac8b3bc62d5c8c3d89b9eb574c16efdef91770afa90313091f25c4cfb6`. The [complete evidence index](delivery/v2-development/director-review-origin/evidence-index.json) binds primary and independent receipts, raw logs, artifact evidence and this handoff.

Public independent Director activation, durable pending-candidate review after expiry/restart, PostgreSQL execution/lock behavior, live provider/model quality, browser/geometry, native desktop, Windows, installed packaged-runtime execution and full product/release acceptance remain unavailable, deferred or unverified. No installation, live provider, remote push, merge, tag or release was performed by this slice.
