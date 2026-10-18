# Accepted-generation Canon source provenance

Date: 2026-10-18 UTC. Status: **IMPLEMENTED bounded producer/source-review repair; PARTIAL semantic extraction**.

## Contract and ownership

The existing mainline `JobManager.accept` paths now create pending Canon through the pure `app/canon_extraction.py` builder, retaining the original deterministic pending UUID and Canon repositories. New records carry `producer_contract: ACCEPTED_CANON_SOURCE_V1`, `chapter_id`, `source_version`, `source_digest` (SHA-256 of canonical persisted content), `source_job`, and `review_owner: PENDING_CANON_REVIEW_V1`.

Each proposed fact includes exact `source_evidence`: chapter identity/version, content SHA-256, Unicode character start/end offsets and literal quote. Fact and quote are identical. Quoted proposals are `LOCAL_ONLY`. Acceptance only saves pending candidates; Canon promotion still requires the original human-review/CAS flow. The review-owner stamp prevents legacy approve/reject methods from bypassing versioned review. No parallel table, repository, migration or automatic Canon promotion was added.

## Honest extraction boundary

`EXPLICIT_SOURCE_MARKER` recognizes line-start `Canon fact:` and `设定事实：` markers, with ASCII/full-width colon support. It does not infer durable facts from ordinary prose, use sentence heuristics, interpret structured model proposals, or call a model. Ordinary prose produces an empty `NO_EXPLICIT_FACTS` result. `semantic_extraction: NOT_PERFORMED` and `model_called: false` are explicit. The former literal placeholder fact is removed from both mainline acceptance paths.

Limits are 2,000,000 source characters, 4,000 characters per marked fact, 100 distinct candidates and a 450,000-byte proposal representation budget. A normal limit overflow returns no proposals and an explicit `LIMIT_EXCEEDED`, `complete: false`, and `limit_reason` outcome. It does not silently claim complete extraction or turn successfully accepted prose into an uncertain acceptance. Invalid accepted-revision identity/content provenance remains a hard failure.

Broad semantic extraction and a dedicated fresh-extraction action remain gaps. Stale new candidates are reject-only; a later accepted generation can create fresh candidates. This implementation does not claim comprehensive durable-fact detection.

## Exact accepted revision and races

The save-returned canonical chapter snapshot is authoritative; it is not replaced by a later current read. Document/content agreement is checked when a document is returned. The File create API returns an unversioned raw initial Markdown projection: the resolver canonicalizes that exact return, obtains revision 1 from the current chapter only when it is still v1 or from original chapter history after a concurrent edit, and requires exact canonical-content equality. Missing or mismatching original revision fails closed. It never labels a newer concurrent edit as the accepted generation. Numeric and durable identities are retained explicitly. Accepted-output overrides are extracted from saved content, not the original model draft. Independent continuation memory enqueue uses the same accepted version.

Provenance failures remain inside the original `ACCEPTANCE_UNCERTAIN` manual-review behavior; the lifecycle was not broadened. Tests verify that the already saved continuation is not duplicated by retry. Normal budget limits instead preserve `ACCEPTED`.

## Review compatibility and safety

Strict generated-source comparison is activated only by the explicit new producer contract. Historical rows, including rows with `source_version` but no new contract/digest, retain their existing explicit-current-source review semantics; lineage is not retroactively invented. New rows compare source identity/version/hash and validate exact quote offsets before allowing approval. Source edits, same-version changed bytes, archived/unavailable sources and corrupted evidence cannot be approved. Rejection remains possible. Preview CAS, operation receipts, original recovery behavior and branch review restrictions are preserved. The branch-generation acceptance path remains unchanged and bypasses mainline Canon production.

The existing Canon panel now explains explicit extraction, limits and stale-source re-extraction requirements using existing primitives. No layout, token or shared-shell changes were made.

## Evidence and source-snapshot stability

All receipts/logs below are in this directory. No actual model invocation, paid service, local Windows execution, commit or push occurred.

- `canon-source-producer-red.json` / `.log`: 7 expected failures, 18 passed, 22 deselected before producer integration (missing chapter identity/provenance and missing exact-revision resolver). The receipt reports `sources_changed_during_check: true`; only concurrent timeline frontend files changed: `StudioTimelineCaptionStyle.tsx`, `StudioTimelineEditor.tsx`, `studioTimelineTypes.ts`, and `nle/timelineOps.ts`. The Canon producer/test sources did not change during this run.
- `canon-source-final2.json` / `.log`: **86 passed**, 80 deselected, File-focused producer, original Canon review/recovery, Inbox and jobs-v03 tests. The receipt reports `sources_changed_during_check: true`; only concurrent `frontend/src/experimental/PlanningModelPanel.test.tsx` and `PlanningPanel.tsx` changed. Canon implementation/tests remained stable. This is not claimed as whole-tree-stable evidence; root's final combined checks can establish that.
- `canon-source-pg-final.json` / `.log`: **62 passed**, 66 deselected, exclusively `postgres_backend_only` selection from the producer and original review tests. `sources_changed_during_check: false`.
- `canon-source-pg-final-postgres-runtime.json`: real PostgreSQL 17.11, existing database `v2_recovered_ocr_export_20261018`, OID 16384, loopback port 55439; no database creation, migrations not requested; `server_stop: stopped`, `cleanup_status: completed`.
- `canon-source-ui-final.json` / `.log`: **9 passed** in `PendingCanonReviewPanel.test.tsx`; `sources_changed_during_check: false`.
- Changed-file `git diff --check` passed. Shared builds, full-suite checks and visual/geometry runs were not performed by this worker; root owns combined verification.

Earlier `canon-source-red` (default interpreter missing pytest) and `canon-source-product-red` (fixture-registration errors plus absent resolver) receipts remain retained as failed setup/intermediate attempts. They are not substituted for the clean producer regression evidence above.

## Changed source files

- `app/canon_extraction.py`
- `app/jobs.py` (preserves the other owner's layered-planning origin/acceptance fence)
- `app/services/pending_canon_review_service.py`
- `tests/test_canon_generation_source.py`
- `frontend/src/novel/PendingCanonReviewPanel.tsx`
- `frontend/src/novel/pendingCanonReviewClient.ts`
- `frontend/src/novel/PendingCanonReviewPanel.test.tsx`

Code and tests remained frozen during report preparation.
