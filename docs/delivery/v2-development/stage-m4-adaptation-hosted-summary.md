# e29e4329 original hosted CI: final receipt

All five original attempt-1 runs reached terminal states without rerun, cancellation, source/index/workflow edits, push or PR changes by this collector. Overall: FAILED_OBSERVED and incomplete hosted backend acceptance.

## Run outcomes
- Cloud push 38086668258: FAILURE
- Cloud PR 38086673970: FAILURE
- Interop push 38086668257 and PR 38086674000: SUCCESS
- R123 PR 38086673979: SUCCESS, meaning the historical c6f2126 defects were reproduced RED, not repaired

Head e29e4329c895e72a79c7c1c2a40a8efcbb90f4d6 and PR merge checkout 395d66570bfd7f8a0e39673619448553e646fa50 share tree c592ef05396427a7f4da9bff4cf2818e6b6a14f5. Raw commit metadata, checkout logs and all six full-backend receipt identities agree. PR47 remains open and Draft. Later working-tree edits are outside this checkpoint.

## Exact backend boundaries
Frozen inventory is 11,533; original File 1 shard / PostgreSQL 2 shards, 20/55 minute job budgets and strict joins are unchanged. Each execution shard passed 174 coverage-harness tests.
- File push: CANCELLED/incomplete. Raw 6,678 call passes and 3,445 setup skips; complete=false, no final backend JUnit or pytest exit.
- File PR: CANCELLED/incomplete. Raw 6,895 call passes and 3,516 setup skips; complete=false, no final backend JUnit or pytest exit.
- PG0 push: SUCCESS, complete=true, pytest0. JUnit 5,768 = 3,848 passed / 1,920 skipped, 3,046.324 seconds.
- PG1 push: SUCCESS, complete=true, pytest0. JUnit 5,765 = 3,777 passed / 1,988 skipped, 2,906.440 seconds.
- PG0 PR: CANCELLED/incomplete. Raw 3,796 call passes and 1,898 setup skips; complete=false, no final backend JUnit or pytest exit.
- PG1 PR: SUCCESS, complete=true, pytest0. JUnit 5,765 = 3,777 passed / 1,988 skipped, 2,633.466 seconds.
- No failed phase event was observed in these six original full-backend shards. Partial raw counts do not prove unseen tests passed or erase historical failures.
- Both original File TCP jobs passed 2 original tests plus 110 harness tests.
- All four strict aggregate jobs FAILED at “Require every execution job including original File TCP gate”, with EXECUTION_RESULT=cancelled and TCP_RESULT=success. Artifact download, provenance validation, exact full-coverage join and proof upload were skipped. Even the complete push PG pair has no official strict-join proof.

## Creative and other scoped results
- Both Creative live browser runs: 11 passed / 1 failed; following geometry suite 8/8.
- Failure remains the generic Script reload assertion at spec490: exact getByLabel("通用脚本内容") cannot resolve for 15 seconds. Both original trace DOMs contain the selected saved v1 document and textarea with correct value; reload GET documents is 200 with the exact whitespace/newline-preserved body.
- Static trace and same-version Playwright code point to wrapping-label text including the reloaded textarea child text. This is a read-only diagnosis, not a tested fix. Later browser restore/export steps were not reached. See creative-failure-diagnosis.json.
- Legacy frontend both SUCCESS: 2,439 unit passes / 8 old skips; type/build/token checks and original browser suites passed.
- Independent Media both: 18 passed; synthetic/mock providers, real inference NOT_RUN.
- Interop File/PG on both events: 413 tests = 345 passed / 68 skipped. Named-pipe 8 checks remain MOCK_ONLY; native desktop/hostile cross-user acceptance is not claimed.
- Windows compile/contracts and bounded package smoke passed; interactive_desktop and user_acceptance remain NOT_RUN. No Windows executable/package ZIP was downloaded.

## Warm-cache evidence
All eight backend execution jobs show the primary c7fc125e… cache HIT and successful restore, followed by actual constrained pip install and “No broken requirements found.” Five successful post steps explicitly do not save because the primary key hit; three cancelled-job post steps are skipped. No new cache-save success or causal speedup is claimed. Exact lines/timings: cache-observations.json.

## Integrity and delivery
- 29 original decoded job logs; 23 new artifact ZIPs, 43,731,483 bytes, 606 members. All downloaded size/SHA-256, ZIP CRC and safe member paths verified.
- Both failure traces additionally have verified member hashes/CRC. No old ZIP was copied. No denied historical artifact or denied session path was read or rerouted.
- Windows binary and large/full frontend artifacts have verified GitHub metadata indexes/sizes/digests only; their payload bytes were not downloaded or verified.
- Historical failures, incomplete runs, local browser limitations and independent audit BLOCKED remain separate and unchanged. Full-source acceptance remains false.

Primary files: terminal.json, terminal-detail.json, runs-terminal.json, run-*-terminal.json, SUMMARY.md, artifact-index.json, artifact-integrity.json, trace-integrity.json, archive-files.sha256.json, backend-execution-observations.json, cache-observations.json, source-verification.json and collector-crosscheck.json.

Final verification: 2026-10-10T22:09:44.802856+00:00
