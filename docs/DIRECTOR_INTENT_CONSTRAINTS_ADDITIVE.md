# Director authored intent constraints

Scope: bounded additive implementation of audience/platform/production-budget intent under CONSOLE-01. The complete V2 requirements remain PARTIAL; this is not a release or acceptance claim.

## Original owner integration

`DirectorVisualTarget` now accepts optional strict text fields `target_audience`, `target_platform`, and `production_budget_constraints`, each limited to 2,000 Unicode code points. Missing, null, empty and whitespace-only extensions serialize as absent. Existing target payloads retain their original serialized shape and digest.

The existing `DirectorTargetPanel` exposes these under a collapsed detail section in the original graph Director console and original proposal/review editors. Existing document save, CAS, source snapshots, readback and approval remain authoritative. Discard comparison includes all three extensions. No new store, endpoint, execution queue, provider call or model admission route was added.

Original screenplay and storyboard model-analysis prompt builders already carry the full typed `visual_target`. The new values therefore reach the reviewed model input without changing the model output schema. Five independently captured response-schema hashes (legacy, production, planning, storyboard and screenplay) are regression-pinned. Changed intent invalidates the original exact-preview guard before dispatch; editing a saved Director changes its document digest and leaves derived old pins stale.

Production constraints are authored advisory text. They do not supply cost estimates, payment authorization, resource admission, or verified feasibility. The read-only intent projection carries explicit UNKNOWN cost/feasibility states and no execution authority. Original required seven intent dimensions remain intact.

## Verification

- `director-intent-constraints-file-r3.json/.log`: 70 passed, three PostgreSQL cases from other regression suites deselected. This historical run did not exercise the new lifecycle against PostgreSQL. Real File owner save/proposal/manual review/reopen, prompt context, stale source, optional clearing, Unicode bounds, strict rejection, response schemas and pre-dispatch changed-intent rejection. No external model/provider calls.
- `director-intent-constraints-file-param.json/.log`: the renamed, backend-parametrized lifecycle also reran successfully on File (1 passed).
- `director-intent-constraints-postgres.json/.log`: 2 passed: the new lifecycle on the original PostgreSQL fixture plus all five legacy model-output schema hashes. Reused PostgreSQL 17.11, UTF8, database OID 16384; no database creation, migrations or collaboration flag. Full original `novels` and `experimental_scope_documents` row snapshots match exactly before/after (one existing row each, no new/modified/orphan rows); see `director-intent-constraints-postgres-cleanup.json`. Runner shutdown and independent pg_ctl/TCP/PID-file checks confirm the server stopped; see `director-intent-constraints-postgres-postgres-runtime.json` and `director-intent-constraints-postgres-stop-proof.json`.
- `director-intent-constraints-ui-r2.json/.log`: 48 passed across six component/contract suites, including save/reopen and frozen UI contract checks.
- `director-intent-constraints-type-r2.json/.log`: final no-emit TypeScript run; consult retained receipt for its actual result.
- Earlier File run (`director-intent-constraints-file`) retained unchanged: fixture-owned basetemp assertion errors; corrected in r2/r3.
- Earlier type run (`director-intent-constraints-type`) retained unchanged: new test mock widened a literal to string; corrected in r2.

Receipts live under `docs/delivery/v2-development`. Shared-tree receipts bind the actual concurrent workspace snapshot, not a committed standalone SHA. PostgreSQL coverage is limited to the explicitly named original-owner lifecycle and schema regression above. No browser visual, packaged/public build, real model-quality or user-machine acceptance is claimed by this slice. Root owns final integrated checks.
