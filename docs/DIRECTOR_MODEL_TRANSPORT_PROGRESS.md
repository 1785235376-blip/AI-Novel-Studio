# Independent Storyboard Director: versioned action transport

Status: IMPLEMENTED transport candidate, PARTIAL product workflow. Construction options remain disabled by default; the production application call has not been changed. This is not a release or real-model quality acceptance.

## Original-owner flow

The candidate adds explicit preview, dispatch, prepare-review, pending-review read, human review and cancellation routes beside the previously implemented status/adopted-DRAFT/reconciliation reads. The original Creative invoker supplies domain.read or domain.write. The original trusted Host resolver and current session, scope, actor, incarnation, source, policy, price and feature checks still apply. There is no new workflow engine, queue, proposal store, permission system or automatic retry.

Preview returns the exact prompt, parameters, constrained source snapshot and verified local zero-fee route through an allowlisted DTO. It does not call a model. Dispatch requires the original expected version and reviewed preview digest; the server forces terminal evidence and does not accept an input that disables it. Only a non-synthetic, verified local text route is supported. Unsupported persistence is rejected before preview writes; this durable lifecycle currently supports File, not PostgreSQL.

Preparation parses the original completed Job output into a durable human-review candidate. GET pending-review cannot perform that preparation. Review creates the original owner's independent Director DRAFT exactly once. The response contains an exact passive adoption receipt rather than raw private proposal/history state. A lost review response is reconciled read-only with the exact submitted body. No automatic Graph insertion or execution occurs.

Cancellation signals the original live worker. Queued cancellation is distinguished from a dispatched request whose upstream usage remains UNKNOWN_UPSTREAM. Local cancellation never becomes a fabricated upstream-stop or billing guarantee. A missing or retired capability cannot be reconstructed from persisted Job fields.

## Additional defects found and fixed

1. The old private pending read could return a candidate after its generation snapshot changed in the final semantic callback. A new actual-persistence negative test returned HTTP 200 and was retained as RED. The read now acquires the original generation leaf after callbacks, compares the exact snapshot, and holds the leaf through the original scope exit. The same test then passed in the combined scope.
2. The original frontend planning projection rejected the planning evidence in a real model-reviewed Director DRAFT. A new test using captured original-owner data reproduced this rejection. The parser now accepts and strictly validates the existing optional planning schema: rationale, source references, uncertainty, assumptions and bounded alternatives. Unknown claims still fail. The existing optional genre field is also preserved without adding it to old payloads.
3. The initial read-only reconciliation adapter's 1 MiB request limit could reject valid multilingual reviews. Its bound now reuses the original proposal owner's 8,000,000-byte limit, with a timeout and sanitized validation errors. A schema-valid request above 1 MiB reaches the original owner and cannot bypass its review checks.

## Evidence and honest boundaries

The versioned HTTP tests mount the actual Creative router and invoke the original File owners and trusted Host resolver. The provider's wire response is a test fixture, not live inference. Both the true queued RELEASED outcome and dispatched UNKNOWN_UPSTREAM outcome are exercised.

The first action suite passed 38 checks. The second stopped with 18 passed because the new test used a nonexistent TrustedSessionResolver.unregister method; it was corrected to the real revoke method. No original test was changed. The next combined scope passed 164 tests, including the existing durable pending and File race tests. The subsequent action/observation/lifecycle scope passed 67 checks. These scopes overlap and must not be added together.

The planning compatibility RED is retained. Its initial corrected UI command matched only the new test file (10 passed); the named separate contract test file did not exist. The corrected command verified exact filenames and ran 79 tests across the new planning checks and existing Graph/Storyboard clients. Final verification additionally includes the optional-genre regression.

Final combined receipts are under `delivery/v2-development/director-model-transport-20261017` and adjacent `director-model-final-*` / `director-model-packaging-*` files. Only completed PASS receipts establish those results. Actual packaging artifacts are inspected without installation; no fresh PostgreSQL, browser, Windows, GPU or live-model result is implied.

The user permits serial development. Separate-agent review is unavailable and is recorded as a limitation; it is not a newly invented stop condition. Primary review and risk-proportionate tests continue. Source, failed logs, successful evidence and recovery information are retained. Main, PR #47/#48, frozen V1, Prompt Adoption and NSFW/public isolation are unchanged by this candidate.

## Remaining vertical integration

- Finish the typed action client using the versioned responses and exact original source bindings.
- Reuse the original DirectorFields, DirectorTargetPanel, proposal queue, Graph console and explicit reviewed-DRAFT handoff; do not relabel private records as legacy public approvals.
- Keep fresh-read versus write controls separate, retain uncertain submitted review content, and fence late callbacks and identity/selection changes.
- Complete mounted UI and applicable real-browser validation before describing the user-facing model workflow as available.
- Extend PostgreSQL durability and additional source modes separately; do not loosen the current independent Storyboard contract.

## Final primary gate update

The frozen combined backend scope passed 271 tests with 97 PostgreSQL-only cases deselected. The combined frontend scope passed 161 tests across eight files. Forced TypeScript, production Vite build and the token guard passed.

The first packaging run correctly failed PUBLIC_FILE_LIST_INVALID: two newly added safe modules had been inserted out of lexical order. The original packaging checker and tests were not changed. The manifest was sorted, and its complete prior membership was verified unchanged except for those two intended module additions. Backend/frontend/test bytes remained equal to the successful frozen scope. Packaging was rerun under a new label with the failure retained; its terminal receipt and actual artifact inspection determine the packaging result.

Packaging retry completed: 87 passed. Two actual wheels and two actual sdists were read back; all included payloads matched the current source. The existing tests checked wheel RECORD and PUBLIC exclusion. Fresh before/after origin receipts passed. The final freeze differs from the preceding successful runtime/UI freeze only in the manifest's corrected lexical ordering.
