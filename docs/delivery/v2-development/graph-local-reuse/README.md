# GRAPH-20 bounded local dependency reuse

This is a partial schema-1 local-text capability, not full GRAPH-20 and not a measured speed improvement.

## Contract and owners

`GraphRunCreate.reuse_reviewed_local_dependencies` is an optional strict boolean. False/omitted preserves the original request serialization, idempotency digest and exact-version behavior. True selects `OPT_IN_REVIEWED_SCHEMA1_LOCAL_DEPENDENCIES_V1`. The run-panel checkbox defaults off and is available only for whole schema-1 graphs containing text_input, text_reference, draft_prepare, manual_transform, director_note and human_review. Changing policy invalidates preflight consent and captured callbacks; uncertain creation retains its exact policy/request.

Graph definitions/history and RUNS remain the only stores. Original WorkflowRun trigger, claim, complete and explicit approval transitions still own every destination result. Every cache hit writes a fresh exact destination-version key and still waits for new human review. The exact admitted graph-version fence is unchanged. Persisted opt-in/mode/schema disagreement fails closed.

## Historical proof

Candidate proof locates the exact source graph version in existing graph history and verifies canonical definition/execution digests, project/incarnation/scope/actor, complete typed topology and closure using original validation against a private historical read view. That view never grants execution/read/review authority. Missing or corrupt proof is a miss. Schema 2–5, asset/model/media nodes, external execution and cached approval are excluded.

Every local source output is revalidated against original host result ports and exact receipt key/digest, then recomputed through the original trusted local runner with its input/output/capability/time limits. Historical human approval requires exact actor evidence, matching preapproval history envelope/engine/inputs, a nonempty trace prefix and its immediate original single-review approval transition. Reviewed ancestors are recomputed rather than trusted from reviewed_nodes.

A separately versioned recursive dependency signature includes project/incarnation/scope/actor/graph/schema/adapter identity, node ID/type/version/enabled/parameters, canonical incoming node/port bindings, recursive upstream signatures, resolved inputs and output digests. Display/title/layout/edge-list ordering and unrelated branches do not invalidate equivalent dependencies. Ancestor changes invalidate descendants even when output bytes are equal. Persisted signatures are never trusted instead of recomputation.

Lookups and original destination completion stay in the existing scope→project transaction. Live authority failures propagate, including one-shot ValueError/StaleSourceError failures. The original host deadline is checked throughout proofs and persists its own timeout transition. Existing run/history/output/scope limits remain; no workers, model calls, paid operations, async recovery, services or second engine were added.

## Verification

- Final File regression: **378 passed**, 117 PostgreSQL cases deselected; original runner receipt `../graph-local-reuse-file-r6.json` and log.
- Frontend: **409 passed** across 13 suites, TypeScript `--noEmit`, UI token guard and diff checks passed.
- Dedicated File/PostgreSQL-parametrized tests: `tests/test_v2_graph_local_reuse.py`.
- Original execution/persistence/contracts/API and capacity-continuation suites are included in the File regression.
- Independent backend authority and frontend lifecycle reviews were requested before commit.
- PostgreSQL execution is reserved for the parent task using the prepared existing cluster; this worker did not start or access PostgreSQL.
- Frontend browser visual/geometry verification was attempted without a server but Chromium startup was blocked by sandbox socket restrictions. No visual pass is claimed.
- See adjacent runner receipts and the parent integration report for final verified counts. Early failed receipts record sparse-checkout dependency setup and corrected test-fixture mistakes; they are not acceptance evidence.

### Preserved earlier check evidence

- `graph-local-reuse-file`: 55 setup errors because sparse checkout omitted `local_interop_desktop`; restored that tracked package.
- `graph-local-reuse-file-r2`: 15 passed / 40 setup errors because `local_interop_protocol` was initially absent; restored that tracked package. No application change was needed.
- `graph-local-reuse-file-r3`: 54 passed / 1 failure because the corruption test tried to write a foreign incarnation through the protected CreativeProjectStore, which correctly rejected it. Test now injects corrupt persisted data through the original raw-store fixture.
- `graph-local-reuse-file-r4`: 334 passed / 2 failures because schema-4/5 exclusion fixtures incorrectly used schema-1-only draft/review nodes. Replaced those fixtures with supported local text nodes to reach the intended opt-in rejection.
- `graph-local-reuse-file-r5`: 361 passed before independent-review hardening. It is superseded by r6.
- `graph-local-reuse-file-r6`: final reviewed backend, 378 passed. All raw JSON/log evidence is retained unchanged.

Source/test diff whitespace checks passed. Staging the unchanged raw failure logs exposes pytest traceback trailing spaces and final runner blank lines under `git diff --cached --check`; those evidence bytes are intentionally preserved rather than cleaned.
