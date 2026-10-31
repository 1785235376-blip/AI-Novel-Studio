# Independent review of NEW export integrity rebuild

This is newly executed evidence. It does not recover or reproduce the old 40-file delivery's identity or historical logs.

- Baseline: public commit 395ac26dd2de3d473e56964dbeb9ac9806facb85, clean `git archive`.
- Fixed: 78dad87b4fbf3bb8f10a7abbdcfdf65027175df9, tree c2608d4bb99720243faf5adea49d9fd69728d262, separate clean `git archive`.
- Original independently written 16-test suite: **9 failed, 7 passed**, exit 1.
- Same 16 tests plus 2 fixed-helper descriptor-closure tests: **18 passed**, exit 0. The two helper-specific tests are additional coverage, not a baseline defect count.
- Baseline failures: receipt mismatch on missing-file fallback (2 service + 2 actual API prefixes), legacy encoded-content predecode admission (1), FIFO/directory and stat-to-FIFO/directory replacement window (4).
- Positive controls: unchanged valid inline fallback, legacy no-receipt reads, named encoded pre-limit, valid 0/1/3/4-byte legacy results.
- Two descriptor setup errors (`fstat`, `fdopen`) prove opened descriptors close even when setup fails.
- Every special-file test runs in a subprocess with a 3-second watchdog; stalled baseline children are killed and reaped. Synthetic paths only, no system permissions or Windows ACL/junction changes.
- 601 production Python files have identical SHA256 manifests before and after the fixed test run. Only `app/**/*.py` is claimed by this manifest, not all tracked files. Module provenance is recorded separately; pytest warning paths also identify the fixed archive.
- No production changes by the reviewer. No GitHub publication.

## Limits

POSIX/File service and real mounted FastAPI routes, not Windows, browser UI, PostgreSQL or distributed exactly-once. The new file reader is not a full ancestor-path race security guarantee. This review does not validate later lost XML/parity/idempotency or other cumulative changes.

## Execution

Python: retained `studio-overnight/.venv/bin/python`; explicit temporary XDG_DATA_HOME and NOVEL_DATA_PATH. Tests executed from each archive with `python -m pytest -q ... --tb=short --junitxml=...`. Exact terminal logs and JUnit XML accompany this file. No dependencies installed.
