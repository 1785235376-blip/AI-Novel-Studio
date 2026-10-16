# Broker cancellation / dispatch transition repair

Hosted browser run 37353115930 at source-equivalent head 4364613 exposed an actual 409 cancellation response: the displayed RESERVED ledger version 1 advanced to DISPATCHED version 2 during the author’s click. The original compare-and-set rejected the stop and the original executor completed. This was reproduced deterministically across both mounted API prefixes, with four failing checks before repair.

Cancellation now accepts only the same owned reservation’s exact RESERVED→DISPATCHED single-version transition. Immutable job/project/scope/actor/route/price/authorization identity must match its recorded history. It does not overwrite or roll back financial state, loosen current host/project authorization, retry generation or accept arbitrary stale edits. Future versions, other bindings and other state transitions fail closed with a bounded error that does not return the historical source-bound ledger.

The production executor is paused at its actual synthetic provider stream boundary in the regression. Explicit cancellation succeeds, late synthetic output is discarded and the original terminal hook settles the ledger. The browser also asserts the real cancel HTTP response before polling the terminal state.

Focused implementation regression: 75 passed; 70 real-PG parameter cases deselected locally. This is an implementation repair, not independent review closure. Real paid-provider cancellation/settlement quality is not claimed. No backend delay was increased to hide the race.

Full immutable File-compatible rerun at `c6c99ab`: 3,063 passed, 9 skipped, 748 actual-PG-only deselected. Hosted execution is still required for the new regression’s PostgreSQL variants and the cancellation browser journey.
