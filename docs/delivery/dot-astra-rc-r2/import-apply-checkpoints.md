# Knowledge acceptance checkpoints

`ImportApplyService(novel_service, data_root)` adds a durable per-review apply
journal around the existing File/PostgreSQL entity upserts. It is a resumable
multi-step operation, not a claim of one atomic multi-entity transaction.

`apply(review_id, novel_id, selected_candidates, actor_id=server_actor)`:

- Validates the entire selection before any entity mutation; bounds to 1,000 rows
- Assigns deterministic target IDs, including candidates with non-Latin names
- Serializes competing journal users with the established thread/OS lock
- Persists an APPLYING preimage checkpoint before each upsert and a DONE readback
  checkpoint afterward; completed steps are not duplicated on replay
- Reuses a failed-before-write step only if its previous entity state is unchanged
- Stops with REVIEW_REQUIRED if an interrupted write is ambiguous, a completed
  entity changed afterward, or a new selection targets an existing entity without
  version-bound replacement authority
- Rejects a changed selection once acceptance began; never rolls back by restoring
  broad file snapshots that could erase someone else's newer edits
- Reports COMPLETED only after every checkpoint and the final journal are durable

The caller must resolve authorization and review scope before calling it. On
`ImportApplyInterrupted`, return the structured detail (`PARTIAL` or
`REVIEW_REQUIRED`, applied rows, completed/total counts, candidate ID), and keep
the original review pending. A journaled operation may have committed some rows;
it must not be displayed as an all-or-nothing failure or a complete acceptance.
The original review can be decided ACCEPTED only after COMPLETED. `status` exposes
checkpoint progress for the same authorized project/review.

Focused evidence: `tests/test_r2_import_apply_journal.py`, six passing isolated
checks, including an actual File repository roundtrip/reopen, injected before/after
write failures, no duplicate steps, selection mismatch, existing-target conflict
and preservation of a user's later edit. Real PostgreSQL acceptance integration
and Windows file locking remain separate test gates.
