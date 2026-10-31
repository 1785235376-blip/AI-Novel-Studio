# Passive JobManager binding evidence

Base: `07d525a6220893109975ea984eaefc060dd61aac`.
Independent worktree; no frontend/SDK edits, migration, deletion, admission/capture
activation or ordinary bound execution/review implementation.

## Verified implementation

- Final corrected broad selection: **482 passed, 2 skipped, 3 existing warnings**,
  81.51 seconds. `final-regression.log` / `.xml` retain the result.
- The two skips are existing live-PostgreSQL-only snapshot cases at
  `tests/test_generation_snapshot_runtime_v056.py:106,125`. They are not passes.
- New File manager suite: **58 passed**, real File project/chapter replacement,
  original mounted API and TaskCenter reader, genuine MockProvider legacy
  retry/accept, registered branch composition, SSE condition-lock checks.
- New PostgreSQL manager suite: **43 passed**, **offline protocol only** using
  original repositories, real ORM/Database.session code and recording session
  factories that reject nested sessions. No real DB locking/isolation claim.
- Existing original repository, generation worker, idempotency/admission,
  recovery/variants/snapshots, TaskCenter and production projection cases are in
  the broad selection. Counts overlap; do not sum separate reruns as coverage.
- Independent final review on the corrected production hashes: **28 probes +
  11 selected regressions passed**. These include 6 original legacy cases and 5
  real branch positive/mismatch/preview cases. See `independent/VERDICT.md`,
  source, actual commands, stdout/XML and before/after production hashes.
- `tested-input.sha256` lists exact production/test/document bytes checked before
  and after the broad run; `frozen-verification.log` records those matches.
  `frozen.sha256` records final delivery bytes. Production and tests are unchanged.
  A documentation-only final correction removed our appended note from the
  historical foundation document (restoring its original byte identity) and
  put chronology in the new document instead. Earlier manifests are untouched.
  `git diff --check` passed. No commit or push was made by this worktree.

Live PostgreSQL: **NOT_RUN**. External model/network calls: **NOT_RUN**.
The runner blocks sockets and clears provider/database credentials; cwd,
PROJECT_ROOT/PYTHONPATH, HOME/XDG/data/tmp are worktree-isolated. Only synthetic
fixtures were used. Runtime project data, credentials, fixtures and caches are
not part of this evidence delivery.

## Audit trail and correction

The preliminary 99-pass compatibility run and 44-pass new-File run were earlier
subsets. The draft broad run produced **430 passed / 2 skipped / 1 failed**.
This was a real production composition lookup error, not a test-fixture error:
the first branch verifier looked for `NovelService.repository`, while the real
service exposes its original novel repository as `NovelService.novels`. A later
focused run showed **54 passed / 4 failed**, all valid real-branch reads affected.
`regression-draft.*` and `before-novel-service-fix.*` preserve those failures.

The correction uses the real NovelService type and actual `.novels` attribute.
No fixture attributes were invented and no production type/root check was
weakened. The corrected final 58-case focused and 482-case broad runs are green.
`before-branch-fix.sha256` is explicitly superseded, not final proof.

## Reproduction and portability

`commands.txt` contains the actual primary commands; `file-commands.txt` and
`pg-command.txt` retain the focused-run commands. `run_tests.py` is the portable
isolated primary runner, deriving the worktree from its delivered location.
`file-runner.original.py` preserves the exact original focused-run runner; it is
an audit artifact, not a directly relocated executable. Likewise, the unchanged
`independent/run.py` and `independent/regressions.py` retain their original runtime
layout. `run_independent.py` is the portable replay entrypoint for the unchanged
28 independent probes; its replay is duplicate verification, not new coverage. To rerun focused cases,
use the portable primary runner with either new test filename.

Set your existing dependency-complete interpreter path and run from the checkout:

    "$PYTHON_BIN" docs/delivery/evidence/passive-manager-fences-20261025/run_tests.py -q tests/test_passive_generation_manager_binding.py tests/test_passive_generation_manager_postgres.py

Stdout and XML are the actual outputs, with only machine-local absolute checkout
and dependency-venv prefixes replaced by `$WORKTREE` / `$EXISTING_VENV` for
portable delivery. Raw original outputs remain in the implementation worktree's
runtime evidence area. No pass counts, failures or diagnostics are rewritten.

See [implementation boundary](../../../backend/passive-generation-manager-binding.md)
for precise unsupported mutation/capture and PostgreSQL branch limitations.
