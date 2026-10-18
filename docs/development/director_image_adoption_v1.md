# Internal Director IMAGE human accounting and adoption

This unmounted slice extends the original Broker, proposal collection and CreativeService. It adds no public execution/review route or UI, queue, document store, or model invocation. Live quality remains unverified.

## Explicit accounting declaration

Only a durably completed, validated IMAGE V3 result can be declared through the coordinator with current original host and write authority and exact Asset/source/target ownership. The original Broker changes its own ledger under the original transaction. Human declaration is opt-in and reviewed, including a deliberate zero. HUMAN_DECLARED_LOCAL_COST and measurement_verified=false distinguish it from a provider bill or measured hardware cost. Without declaration, UNKNOWN_UPSTREAM remains and adoption is blocked. Interrupted/orphan jobs cannot use this path.

The immutable terminal retains its historical UNKNOWN_UPSTREAM snapshot and hash. A new review projection joins that historical evidence with the Broker's declaration/history. No old pending record is reinterpreted as execution or adoption authority. Generic bill and native OCR reconciliation remain unchanged.

## Explicit human adoption

A strict versioned request selects suggestion indices, supplies human-reviewed bounded note text, and pins proposal version, terminal/accounting digest and original DIRECTOR DRAFT scene/version/digest. The server appends one DirectorSceneNote with a new server ID. It does not synthesize image-derived screenplay/storyboard documents or infer production facts from prose.

Original scope → Asset → project leases are retained through commit, without model I/O. CreativeService.revise_in_state performs canonical revision validation. Server-only source/target/terminal/accounting provenance is appended through existing prompt_adoptions/history; the original proposal receives the exactly-once receipt in the same transaction. Client-forged proofs are rejected. Replays compare the exact request digest and original document proof, return a historical receipt, and never reapply over newer content. A lost commit acknowledgement is resolved by retrying the same request. Missing/pruned proof fails closed. Restart grants no new executor authority and never automatically adopts.

All evidence continues to identify observations as unverified. Human adoption is an editorial choice, not proof that the model interpretation was correct. Accounting declaration is not proof that an upstream process stopped. No orphan recovery is provided.

## Tests

The additive test module reuses real original File/PG fixture owners and injected HTTP only. Actual PG execution belongs to primary integration; File receipts cannot establish PG success. Fixtures retire tracked synthetic project IDs through original owners and delete matching orphan scope documents. Generation jobs use the original cascading project FK.
