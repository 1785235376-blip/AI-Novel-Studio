# Work integration handoff

Apply the new reconstruction commit to the e5 safe base, not the lost prior
bf0bbdb2 object. The five mixed TaskCenter production files are byte-identical to
published f6473e30. The other three production files add only independent-request
budget/strict-context isolation, approved by the owner. Preserve these changes
when later integrating with the frontend; do not overwrite whole backend files.

Exact supported cursor pair: actual File, local, nonpackaged,
`semantic_import + exports`. Original authority canonicalization, registered
reader order and actual reader instances remain authoritative. Semantic imports
retain their 200 bound; exports retain100; mixed observed window is at most300.
Actual aggregate reader receipts, scoped lifecycle/nonce, source incarnation
including empty documents, query/auth/process binding and reauthorization remain.
Original local/collaboration singles remain; collaboration mixed/exports and
other pairs remain unsupported. No cross-owner atomic snapshot/full ABA claim.

Every independently entered ASGI scope clears an inherited asset budget and
strict marker using ContextVar tokens, then restores the caller in finally.
Matched asset GET establishes the original fresh budget and original strict
selection; nonmatched routes and websockets have no inherited budget. Nested
operations in the same request retain budget reuse and monotonic strict mode.
The transport test deliberately uses h11 real pipelined requests without a
server reset-context option; its endpoint reports middleware scope, not full
business behavior. Separate combined TCP tests use original application owners.
TaskCenter does NOT automatically enter asset-usage budget coverage.

Tests change the former local-pair501 expectation only. Original collaboration
refusals remain. The synthetic observer clears non-GET attribution to prevent a
following request's writes being assigned to an earlier GET. It does not erase
completed records or unattribute a true GET-owned background task.

Protected Store physical snapshot/bytes/CAS and duplicate-key logic, identity,
scope, original writer/lock protocol, canvas adoption authorization, frontend
and SDK retain the safe base implementation except the explicit context helper
additions. No Work branch, main or external service is changed here.

Later unified browser verification remains Work's scope; this backend-only
package does not certify fe4 frontend browser adoption/reopen acceptance.

Blocking unified acceptance: final uninstrumented combined HTTP is3PASS/1FAIL,
/api/v1 warm strict asset first page returns409 after ordinary first/next/replay.
Root cause remains unknown. One separately instrumented rerun passed, not a fix.
Keep this blocker with Work; do not replace final evidence with the diagnostic.
