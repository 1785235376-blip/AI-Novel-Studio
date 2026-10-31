# File bound memory prerequisite evidence

Canonical base: `f4ed62a1d2d8c7cce876745d92e0ec95b4b15ec7`.

- `commands.txt`: exact test commands, worktree cwd.
- `recorded-runner.py`: exact isolated/socket-blocking runner used for the
  recorded implementation test commands. `run_tests.py` adds the tests directory
  to imports for portable independent-probe reruns; production is unchanged.
- `tested-input.sha256`, `focused.log/xml`: initial unchanged-production review
  port counterexamples and gates, **7 passed**. These intentionally characterize
  unsafe legacy adoption; they are not bound accept success evidence.
- `memory-tested-input.sha256`, `memory-focused.log/xml`: first memory prerequisite
  run, **49 passed**, before final callback deferral and retry repairs.
- `memory-final-input.sha256`, `memory-final.log/xml`: frozen production memory
  prerequisite and legacy runner cases, **54 passed**, 3 existing warnings.
- `regression.log/xml`: broader selected original-owner, passive-manager, memory,
  restart, worker-authority and idempotency compatibility suite: **387 passed**,
  3 existing warnings, 36.13 seconds.

Synthetic-only real File owners use original service/repository writes. New memory
positive/race tests use the existing contract MockProvider subclass with fixed
JSON, through the real normalized adapter/runtime/local verifier chain. The legacy
writer positive test uses original MockProvider worker execution. Deletion races
at evidence/proposal/relation/terminal boundaries use actual competing threads;
replacement is blocked through the lease and produces no surviving replacement
effects. Other deterministic scheduling seams replace the owner before enqueue,
after enqueue before its thread runs, before dispatch and during inference.

The prerequisite is **not bound manual review activation**. Ordinary gates remain
closed. PostgreSQL tests are offline protocol controls only. No live PostgreSQL,
external models/network, frontend, new queue or migration is exercised or claimed.

No commit or push was performed. Independent review artifacts are maintained
separately until review finishes. See the backend document for exact limitations.

## Independent review and baseline separation

`independent/` preserves the reviewer's final source copies/hashes, original exact
command, 19 passing independent probes, and the initial two genuine red defects
and fixes' rerun evidence. It excludes runtime data, HOME and XDG directories.
The original temporary path/collection failures are explicitly separate from real
product failures. Final independent opinion is PASS only for this prerequisite.

`legacy-baseline/` preserves the separate canonical-base two original JobManager
MockProvider writer → accept → original memory enqueue/extract counterexamples.
Both demonstrate real replacement-owner Lore writes, including stale evidence
absent from the replacement chapter in the final-write race. These are pre-change
legacy behavior evidence, not proof of bound-path repair. The new opt-in path does
not silently change that legacy contract. Original commands/logs are retained
verbatim, so historical workspace paths in them are not portability instructions.

Portable reruns from this worktree (select an existing dependency interpreter):

    python docs/delivery/evidence/bound-review-port-blockers-20261025/run_tests.py docs/delivery/evidence/bound-review-port-blockers-20261025/independent/test_independent.py -q
    python docs/delivery/evidence/bound-review-port-blockers-20261025/run_tests.py docs/delivery/evidence/bound-review-port-blockers-20261025/legacy-baseline/test_delayed_memory.py -q

The first command needs `tests` on PYTHONPATH because the independent file uses
its explicitly hashed helper fixtures. The portable runner now adds the tests
directory. Neither rerun is needed to count the already captured evidence again.

Whitespace check: production/test/backend-document diffs pass. A full staged diff
check flags whitespace inside the verbatim independent unified diff and two initial
failure captures (pytest's `E` lines). Those raw evidence bytes are intentionally
preserved, not edited to manufacture a clean evidence check.
