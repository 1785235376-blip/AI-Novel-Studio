# Passive ordinary project-owner foundation evidence

Synthetic-only local test evidence. No actual user runtime records, project data,
credentials, database exports, provider outputs, or live PostgreSQL data are included.
No model, provider, or network execution is claimed. Real PostgreSQL: NOT_RUN.

## Results and exact files

- `final-regression-tests.log`: exact final implementation run output, **260 passed**,
  3 warnings, 64.45 seconds. Includes the final ordinary-only mainline chapter-owner
  guard. Not a filtered success excerpt.
- `final-focused-tests.log`: exact final focused output, **96 passed**, 2 warnings.
- `run_tests.original.py`: byte-identical runner used for both final runs.
- `run_tests.py`: portable runner; only the root locator changes from parents[2] to
  parents[4], and creation of its four isolated runtime directories is added.
  This copied portable location was not separately executed; no extra test claim.
- `test_independent.py`: exact final reviewer probe source, 48 probes, including
  equivalence with the original specialized classifier.
- `chapter_boundary.py`: exact final reviewer narrow PostgreSQL guard probe source;
  checks foreign-owner rejection, same-session matched owner, unchanged legacy
  behavior, and the deliberately unsupported read-side chapter reconciliation case.
- `baseline_generation.py`: exact original generation_repository.py at base
  d070c9f6354b76a1594e388cb0825fb280933c63, used ONLY by the independent equivalence
  probe. SHA256 81d670bacddaf0055673f9d54b2fb86e9b4a86f61ad93df64879b462bf8ad2a7.
- `before.sha256`: reviewer production hashes before final narrow PG guard.
- `final.sha256`: reviewer final production hashes including that guard.
- `run_evidence.sh`: exact reviewer command/environment wrapper. Called with
  PYTHON_BIN pointing to the existing shared venv and the worktree as its argument.
- `independent-results.log` and `independent-results.xml`: exact frozen-source
  reviewer rerun, **48 passed in 1.05s**. This repeats the same probes for portable
  evidence; it is not additional unique test coverage.
- `chapter-boundary-results.log`: exact final guard output, three PASS checks and
  the explicitly unsupported read-side boundary CONFIRMED.
- `evidence-before.sha256` and `source-verification.log`: final frozen source
  hashes and verification after the reviewer evidence rerun, all three files OK.
  Use these as the final reviewer source proof, not the historical before.sha256.
  The earlier 100-test reviewer combination was terminal-only and is not reconstructed.
- `MANIFEST.sha256`: repository-relative SHA256 of all delivered production, test,
  documentation and evidence files other than the manifest itself.

## Original implementation command

Original cwd:
/workspace/scratch/20a0022d2b33/studio-passive-owner-foundation

Original shared interpreter:
../studio-backend-20261025/.venv/bin/python

Command arguments:
.runtime/passive-owner-foundation/run_tests.py -q
tests/test_ordinary_project_binding.py
tests/test_ordinary_project_binding_postgres.py
tests/test_generation_restart_recovery.py
tests/test_generation_admission_receipts.py
tests/test_generation_worker_authority.py
tests/test_generation_idempotency_contracts.py

The focused command used the first two test files only. Both exact logs were copied
without path substitutions. Absolute warning paths identify the synthetic worktree
and the shared virtualenv; they are not runtime data.

## Portability and path substitution

From another checkout, substitute its available compatible Python interpreter for
the shared interpreter above and use
`docs/delivery/evidence/passive-job-owner-foundation-20261025/run_tests.py`
as the runner path, retaining the same test paths/arguments. The portable runner
resolves the checkout root from its saved location and uses that checkout's
.runtime/passive-owner-foundation/{home,xdg,data,tmp}; it sets cwd/PYTHONPATH/PROJECT_ROOT,
removes provider/database environment values, sets File storage and an in-memory
credential backend, and blocks socket connections and DNS resolution. The main guard
supports multiprocessing imports without recursively invoking pytest.

The independent pytest source needs baseline_generation.py in its same directory,
which is preserved here. Original independent commands/results are recorded in the
reviewer evidence delivered alongside this README; no unperformed rerun is implied.

## Product boundary

This is repository storage capability only. Existing JobManager serialization and
restart restore do NOT preserve the binding yet. No API stamps it, no ordinary new
job protection is activated, no HTTP shape changes, and no historical accept/retry
repair is claimed. Bound chapter ID is immutable data, not full source-lifecycle or
read-side SQL chapter reconciliation. See the linked delivery document for all limits.
