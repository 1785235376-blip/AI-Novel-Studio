# Round-3 evidence corrections (2026-10-19 closeout)

This file records corrections to the machine receipt in this directory. The original JSON is
recoverable from Git history (commit that added this directory); nothing is silently rewritten
into another run.

1. `verification-summary.json` `junit`/`console` fields previously stored the runner-side labels
   (`d24-full-file-pg.xml` etc.) although the archived copies are prefixed (`junit-d24-full-file-pg.xml`,
   `console-d24-full-file-pg.log`). Fields now point at the archived filenames; `console` is `null`
   where no console was archived, instead of a path that looks openable but does not exist.
2. `pool-regression-file` was recorded as `PASS` with an empty summary. The recovered original
   JUnit/console show **5 skipped, 0 failed, exit 0**; in the File profile this PostgreSQL-only file
   is `SKIPPED_NOT_APPLICABLE`, not a pool-behaviour PASS. The exit code is recorded separately.
3. `head` is the execution SHA `415cbcc2` of the working tree; the last commit of that round was
   `68b5e0c8` (docs/evidence only).
4. Round-3 closeout evidence (new runs at a new execution SHA, diagnostics, index check):
   `docs/v2/engineering/evidence/local-ci/20261019-r3-closeout/`.
