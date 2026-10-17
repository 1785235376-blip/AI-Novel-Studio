# Private Director lifecycle owner candidate

Status: PRIMARY_CHECKED_CANDIDATE; independent review unavailable. This is not a public API, a completed intelligent director workbench, or end-to-end product acceptance.

Base: `5a6f697bccf2127b1bbfd62bb422311edc8c4afe`.

## Implemented scope

The existing DirectorModelCoordinator now supports private current-authorized status observation, an exact reviewed-DRAFT receipt, read-only reconciliation of an uncertain human-review response, and cooperative cancellation of the exact live independent Director job. These use the original proposal, document, JobManager, generation repository, broker ledger and File transaction owners. No second workflow engine, public routes or frontend activation were added.

The adoption receipt is committed in the original proposal/DRAFT transaction. It pins source version and digest, request and terminal evidence, candidate output, exact submitted human review including omitted versus explicit-null fields, and the created DRAFT's identity/version/digest. Reopening requires fresh current authority and exact original owner data. Reconciliation never repeats review or creates another DRAFT. Failure before atomic replace leaves no adoption; failure after replace can be reconciled read-only.

A cancellation request signals only the original live worker. Persisted job data cannot restore the live capability or process-local signal. The original worker performs terminal status and ledger settlement. A queued, undispatched job can produce a confirmed local cancellation with RELEASED and zero actual cost. A dispatched request with UNKNOWN_UPSTREAM remains unconfirmed, even when the local job has stopped. The receipt always reports upstream_cancellation_guaranteed=false and automatic_retry=false.

Explicit cancellation previously became GENERATION_AUTHORITY_REVOKED during generic bound checking. The candidate classifies the authorized signal as CANCELLED, including a signal arriving during a current-authority callback. Existing recorded bound failures retain precedence. Legacy non-opt-in paths remain covered by unchanged tests.

## Primary verification

Evidence directory: `docs/delivery/v2-development/director-lifecycle-parent-check-20261017` plus the original runner's adjacent `director-lifecycle-*.json` and `.log` receipts.

- New targeted tests: 20 passed on the final targeted run.
- Combined original-owner backend regression: 655 passed; 120 PostgreSQL-only cases deselected. Real File persistence, restart and atomic replace tests are included.
- Forced TypeScript check, production Vite build, design-token guard: passed.
- Natural clean-Python startup and unchanged original-runner child origins checked before and after the combined run.
- PUBLIC packaging: 87 passed. Two actual wheels and two actual sdists were read back without installation; all included source payloads matched the current checkout. Original packaging tests verify wheel RECORD. The single manifest addition is the passive director_lifecycle module. Receipt: director-lifecycle-packaging-r1.json; retained archive inventories: director-lifecycle-parent-check-20261017/packaging-evidence/index.json.
- Existing tests, frontend sources, original runner and workflows were not modified.
- Canonical V2 inventory has not been regenerated for this unaccepted candidate.

Earlier failed new-test runs are retained. One exposed the cancellation classification defect. Another had an incorrect new-test expectation that a local cancellation also confirmed upstream settlement; it was corrected to require the original broker's actual UNKNOWN_UPSTREAM result. No old tests or ledger rules were weakened.

## Outstanding work and limits

Independent review workers stopped at the platform preview limit. Continued primary checks are not represented as independent review. This candidate remains isolated from the accepted integration branch and has not been uploaded as accepted work.

No real PostgreSQL, browser, live provider, Windows or GPU acceptance was performed. No paid resources were requested. The source constraint remains the existing independent Storyboard contract; direct screenplay and lineage-bearing source support are not implied.

A later versioned, opt-in public transport must bind fresh request authority, explicit prompt/route review, read-only status, exact review reconciliation and cancellation to these same original owners. Existing public projections must remain closed until that separate transport and its negative tests are completed.
