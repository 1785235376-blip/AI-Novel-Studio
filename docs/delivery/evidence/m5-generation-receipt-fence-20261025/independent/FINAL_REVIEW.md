# Independent M5 receipt-fence follow-up

Verdict: PASS for this narrow corrective slice at the frozen code hash below; no remaining reproduced blocker. This does not activate a new generation entry or assert full-project correctness.

## Exact inputs and reproducible evidence

- Held baseline: e7f2eaec2a5010a98cad6aa1d48df8e0ffc3b459, clean main worktree for actual red reproduction.
- Fix worktree: studio-m5-receipt-fence, same baseline, uncommitted fix during review.
- Only changed production file: app/repositories/generation_repository.py.
- Frozen production SHA256: beff4db407e0eef0920695dfc6750ac89d8a30a292e290ff850d556f5bcb133d.
- Frozen implementer test SHA256: c9a4212e371a03504a1ee2a5ae2d65fc28132036e787cc542cc2ea08a6ef0485.
- target-freeze.sha256 verifies both entries before and after final run.
- Red source snapshot prefix: 20261025T114123133690284. Final source snapshot prefix: 20261025T114343195865320. Both have exact source tarball, patch, and before/after hashes; all app hashes stable within both runs. app-hash-diff.txt confirms only the generation repository differs between baseline and fix.
- run.sh/run.py preserve exact commands, source, raw stdout and XML; existing venv, isolated HOME/XDG/data/tmp, socket connections blocked. No network model, live PG, install, production edits by reviewer, or GitHub action.

## Actual red, not inferred weakness

red.stdout/red.xml: four failures on held baseline, each at an unchanged-byte assertion. Original _graph_owner is entered first; wrapper then uses original NovelService delete/recreate for same ID before yielding back to original save.

- Manual ACCEPTING overwrites the prior global COMPLETED receipt.
- Manual ACCEPTED overwrites the prior global ACCEPTING receipt.
- Bound memory GENERATING creates a stale global receipt where none existed.
- Bound memory COMPLETED overwrites the prior global GENERATING receipt.

In all four, replacement project file bytes remain unchanged. Thus this was specifically a late global receipt write after owner replacement, not a claim of replacement chapter/Lore corruption. Raw failures are retained, not converted into passing counterexample assertions.

## Final independent proof

final.stdout/final.xml: 341 passed, 3 ordinary warnings, 37.73 seconds. Eight independent probes, five focused implementation tests, 328 original compatibility tests. Includes 43 offline PG protocol checks, 69 original worker/Graph authority checks, 58 passive File-manager checks, 55 idempotency checks, 43 bound-memory-owner checks, 33 manual-review checks, 15 memory final-port checks, 11 memory agent checks, and restart recovery.

The same four red probes now pass without changing their byte assertions. Additional independent probes establish:

- Repository root rotation after owner entry preserves the original receipt and writes no foreign receipt; no foreign project or generation-leaf lock is acquired.
- Memory generation-root rotation and replacement same-root Lore facade are rejected before terminal receipt write.
- Positive manual acceptance and original asynchronous memory completion invoke the final fence while both original project lifecycle and original generation-write leaf locks are held.

Source review confirms the final expected-root/incarnation/_file_memory check occurs after serialization and immediately before the existing atomic_write. Opted-in saves pin their original leaf root before owner entry. Root mismatch is rejected before reacquiring an owner; a valid root only reenters the already-held same-owner lock. Memory reuses original exact-port validation. No new owner, queue, registry, schema, or migration is introduced.

No-expectation saves retain original leaf-root behavior and the new helper is a no-op for them. The specialized terminal-publication implementation is unchanged; selected original compatibility controls pass. No M6 writer/v2 binding/API capture code was copied. app-hash-diff.txt independently confirms all other production Python files are byte-identical to held M5.

## Boundaries and limitations

Manual records here are synthetic trusted internal v1 COMPLETED records, not newly generated bound writer jobs. Memory uses original local Mock runtime with synthetic output. This proves M5 manual/memory receipt boundaries, not activated bound generation E2E or live PostgreSQL concurrency.

The seam is after original owner entry and before original receipt save body, not a monkeypatch of atomic_write or arbitrary hostile server/filesystem modification. Existing common owner lease remains; final checks complement it. No multi-file rollback or recall of prior lawful responses is claimed.

Earlier broader adaptation-authorization baseline failures remain outside this narrow selection and are not repaired or relabeled by this PASS. The new generation entry remains excluded. Publication decisions and approved upload are owned by the parent; reviewer performed no GitHub action.
