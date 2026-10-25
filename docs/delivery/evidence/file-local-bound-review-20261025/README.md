# File-local bound manual-review evidence

Base: `5eb983fd620ef905aa4dc1afae80b756ee7e7078`.

`commands.txt` contains the exact implementation test commands. `run_tests.py`
uses this worktree's cwd/import root and the existing dependency interpreter,
isolated HOME/XDG/data/tmp and blocked socket connection/name resolution. Tests
are synthetic File-owner exercises; PostgreSQL tests are offline protocols only.
No external models, paid providers, installs, frontend or new task infrastructure.

## Iteration evidence

- `initial-input.sha256`, `initial.log/xml`: first focused slice, 12 passed.
  This narrow result did not prove legacy compatibility; independent preflight
  caught undefined `_review` names accidentally introduced in other paths. They
  were removed before the revised compatibility run.
- `revised-input.sha256`, `revised.log/xml`: 195 passed, including original
  worker/restart/idempotency and passive File behavior.
- `expanded-input.sha256`, `expanded.log/xml`: 25 passed, two test assertion-type
  failures. Real VersionConflict and normalized authorization RuntimeError were
  correct refusals; test expectations were corrected, not production behavior.
- `final-input.sha256`, `focused-final.log/xml`: 32 focused cases passed, before
  adding the stale-restore lock-order test.
- `regression-final.log/xml`, `frozen-regression.log/xml`: broad runs revealed
  43 real offline PostgreSQL compatibility failures. New File pin initialization
  touched unsupported downstream sentinel metadata. The fix inspects only exact
  supported service/repository types and refuses unsupported ports before access.
- `frozen-input.sha256`: includes File interrupted-restore lock alignment.
- `final-frozen-input.sha256`, `final-frozen-regression.log/xml`: definitive
  frozen production/test hashes and final selected regression result.

Repeated suite runs are not additional unique coverage. The frozen inputs include
all changed production owners and the new tests. Historical logs retain the actual
workspace paths and failure text rather than being rewritten as clean evidence.

## What the cases establish

- Cold internally bound File manual accept and reject, retaining original binding.
- Original continue/chapter/summary/pending Canon and nonempty Mock memory chain.
- Zero replacement writes after initial-read, reentrant chapter/summary/Canon
  replacement; real competing deletion blocks through old-owner review effects.
- Pinned facade/root/memory composition, no missing-record fallback, original
  version/accounting/current authorization checks and unsupported scope refusal.
- Durable claim, source/Canon/terminal failures, uncertain status and no replay.
- Single-use helper capability, cross-thread/expired callback refusal.
- Partial-effect notifications delivered after lock release even on exceptions.
- Original independent memory enqueue failure does not undo author acceptance.
- Other bound mutation gates remain closed with fully composed real ports.
- Stale interrupted restore does not hold a review lock while waiting on owner.

The bound draft is an explicit trusted synthetic persistence fixture, not new
admission capture or bound model execution. Legacy Mock worker execution is tested
separately. Previous unbound replacement counterexamples are deliberately still
positive observations; this slice does not reinterpret or fix legacy history.

## Final results and independent review

Final implementation-selected regression: **460 passed, 1 skipped, 3 existing
warnings, 36.08 seconds**. The skipped test is the real PostgreSQL two-client CAS
check, explicitly unavailable without TEST_POSTGRES_DATABASE_URL. No real
PostgreSQL concurrency is claimed. The final selected run includes 33 manual
review cases; it is not a full-project test run.

`independent/` preserves the reviewer's exact original commands, raw preflight,
provisional and final stdout/XML, target and whole-app hashes, and final changed
source/test copies. Final independent frozen run: **365 passed, 3 existing
warnings, 37.07 seconds**, including 33 independent probes. Whole-app before/after
hashes and the final target manifest stayed unchanged. Overlapping implementation
and independent suites are not additive unique coverage.

The independent broader compatibility run also found **three adaptation-
authorization failures**, reproduced identically on the unchanged canonical base.
Both changed-tree and baseline raw results are retained, not hidden or described
as new regressions fixed by this slice. This is not a full-project-green claim.

The reviewer ran an original unbound Mock writer, copied its result into a NEW
UUID internal bound record, then cold-restored and reviewed that synthetic record.
That is not a bound dispatch bypass or an upgrade of the original unbound row.
Both existing accept/reject HTTP routes are exercised for eligible pre-existing
internal records; only new API capture/admission remains closed.

Historical absolute paths in raw commands are preserved as evidence. To rerun
portable independent probes, use this worktree's isolated runner with an existing
dependency interpreter:

    python docs/delivery/evidence/file-local-bound-review-20261025/run_tests.py docs/delivery/evidence/file-local-bound-review-20261025/independent/test_independent.py -q

No production changes followed the final frozen hashes. Final source snapshots
contain the changed owners/tests; whole-app hashes plus the canonical base identify
unchanged files. Runtime directories, HOME/XDG data and model output stores are not
included in the delivery.

Whitespace: production, tests and backend documentation pass the diff check.
Full staged diff checking flags pytest traceback separator/E lines in the raw
failure stdout/XML. These exact evidence bytes are deliberately preserved; they
are not edited to manufacture a clean historical failure capture. The independent
report mentions its original full source tarball retained in reviewer runtime;
the portable delivery instead includes exact changed source copies and complete
app hashes anchored to the canonical base, not runtime caches/data.
