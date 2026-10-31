# Fresh original-owner process-boundary verification

Frozen production commit: `97ab69b40435b18b1b5b946ad0e73774aa6da103`.
Frozen production app tree: `0ae3341234aa582b2d0ef6143c04e56e06aa46a5`.
Independent no-hardlinks clone with detached checkout. Only a new test file and evidence are added; production files are unchanged. This is a fresh run, not recovered or reused prior evidence.

## Result

20 passed, 2 existing Pydantic schema-shadowing warnings, 185.38 seconds. Runner exit 0, zero failures/errors, no application module loaded outside the selected clone. See raw log, JUnit, summary and loaded-module hashes.

Four original owners are covered: FileIdentityRepository, FileScopeRepository, FileAuthorizationRepository, and ExperimentalStore collaboration team_runs.

- Eight real child-process SIGKILL tests pause the original os.replace boundary before or after replacement. Fresh original readers validate paired business rows and owner-maintained same-file lifecycle evidence, original unchanged row nonce continuity, and a subsequent successful write.
- Eight fsync/replace injected-error tests verify exact original bytes and lifecycle observations are retained and a subsequent successful commit works. These failures execute in the pytest process, not an extra subprocess.
- Four original-lock contention tests run two real writers. The first is held before replacement while the second signals an original lock-acquisition attempt; releasing the first permits both complete commits. Fresh readers verify no lost rows and distinct lifecycle evidence for all three rows.

Total explicitly launched child processes: 16 (8 killed writers plus 8 contention writers). SIGKILL count: 8. No process counts inferred from pytest's own launcher.

## Scope and limits

This validates each original single-file atomic replace and lock boundary on this POSIX cloud filesystem with synthetic data. It does not certify multi-file compensation crash atomicity, physical power-loss durability, parent-directory fsync, arbitrary byte-for-byte external backup replay, Windows, PostgreSQL or full HTTP acceptance. SIGKILL intentionally can leave a temporary file before replace; the test only promises the authoritative owner file remains whole, not crash-orphan cleanup. No model, background worker, user computer or real user data is used.

The independent test uses original save/create/transaction methods and original capture/read validation; no production API or lifecycle helper is monkeypatched. Only storage fault/boundary and original lock-entry observation are instrumented. Evidence is distinct from the separate mounted HTTP independent review.

## Reproduction

Use tests/test_taskcenter_rebuilt_process_boundaries.py with the unchanged repository verification runner's run_group under isolated HOME/XDG/PROJECT_ROOT/data roots, File backend, mock providers and memory credential vault. Exact invocation and temporary paths are in process-fresh.log. run.py records the actual source/output paths used for this run and is an archival wrapper, not a portable installed runner.
