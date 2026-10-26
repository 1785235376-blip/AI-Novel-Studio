# HTTP compatibility evidence

## Independent fixed-A Windows baseline

- Worktree: `D:\PoemSeed\Worktrees\file-safety-http-20261026`.
- Branch: `work/file-safety-http-tests-20261026`.
- Source A: `856d1ed3341fe0c24df1daff9a8bc1242c260e6c`.
- Command: `python scripts/run_studio_backend_tests.py tests/test_studio_asset_query_cursor.py -q -x`.
- Process exit: **1**, normal completion (no timeout), pytest elapsed **6.03 s**.
- Result: first stable asset metadata cursor traversal returns HTTP **503 ASSET_QUERY_CURSOR_UNAVAILABLE**. This independently reproduced baseline failure is distinct from integration acceptance.
- Full failure output: `baseline-A-asset-cursor.log`.

## New combined socket coverage

`tests/test_file_backend_safety_http.py` uses original application assembly and temporary File repositories through real loopback TCP. `tests/file_safety_http_server.py` is a test-only ASGI observation wrapper delegating requests to `app.main.app`; transparent method counters call the original implementations and record loaded module paths/hashes, GET command/model entrypoints, filesystem mutations/write opens and cumulative asset budget counters. It blocks external network connections. No application source is edited. Business-file snapshots include content hashes and mtimes. Existing Windows coordinator lock handles may be opened read/write, including beneath `assets/.workspace-mutation-locks`; opening such a handle is not an observed business-file write.

Coverage is synthetic only: existing 32 saved consumers / 540 direct references / 6 pages; both API aliases; strict-read-only cold refusal and initialized success; three separately supported TaskCenter combinations; replay, owner lifecycle changes, membership revocation/restore, application restart, and actual cumulative resource admission refusal. TaskCenter is explicitly not asserted to satisfy the asset-only budget contract.

Development target: immutable production commit `f6ae6c5fb2bda8b875bdbd1f32b5bafd18d9d070` in this tester's own worktree. All development invocations use `python scripts/run_studio_backend_tests.py tests/test_file_backend_safety_http.py -q -x`, separate `.runtime/http-dev-N` roots, and `development-candidate-N.log` files here.

| Run | Exit / elapsed | Interpretation |
| --- | --- | --- |
| 1 | 1 / 16.91 s | Harness sent `strict_read_only=false`; original admission treats presence as strict and correctly rejects cold state. Fixed harness to omit optional parameter. |
| 2 | 1 / 16.85 s | Harness omitted original local-author Studio session. Correct `401 SESSION_REQUIRED`; synthetic original session added, removed only for File/local TaskCenter reads. |
| 3 | 1 / 87.04 s | Harness switched strict mode while reusing a non-strict token. Correct binding rejection; fresh strict traversal now uses its own token chain. |
| 4 | 1 / 129.86 s | Tester deliberately terminated only its own child PID 103268 at 2026-10-26T23:24:19+08:00 to replace an expensive whole-interpreter profiler. Connection reset is not a production failure or timeout. Windows termination is not POSIX SIGKILL. |
| 5 | 1 / 61.84 s | Full first-process `/api` behavior passed; final harness audit misclassified existing nested asset coordinator lock handles. Fixed lock classification by exact path component; business mutations remain forbidden. |
| 6 | 1 / 160.86 s; 2 passed | Both complete File/local alias cases passed, including restart and exhaustion. Collaboration Studio correctly refused a development session with `403 LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE`; this positive-path harness assumption was removed without changing the Host gate. |
| 7 | 0 / 44.11 s; 2 passed, 2 deselected | Command adds `-k collaboration`. Both collaboration team cases passed; explicit Studio Host-authority refusal remains asserted. |
| 8 | 1 / 64.30 s | Added actual write-call observation found one original compatible-mode coordinator lock initialization. This is permitted only outside strict mode; the harness now separately asserts zero business writes and zero strict writes/creation. |
| 9 | 1 / 20.65 s | Tester terminated only child PID 104036 at 2026-10-26T23:31:58+08:00 before exports, to correct the executor fixture per the storage-only requirement. |
| 10 | 0 / 200.61 s; 4 passed, 3 warnings | Entire four-case suite completed with deterministic stub executor. Development only: final audit completion and decorated-method observation were strengthened afterward at independent review. |

The positive combined Asset + TaskCenter TCP flow is proved for File/local semantic_import and File/local exports on the same synthetic project. File/collaboration agent_team has positive TCP paging/lifecycle/revocation/reopen evidence in the original no-chapter source window. Positive combined collaboration Asset + TaskCenter TCP remains **PARTIAL / NOT COVERED** because development sessions are not packaged Host authority; the exact 403 is a retained boundary, not positive Asset acceptance.

Host receipts now summarize GET count, command calls, observed actual Python write calls split into business/coordinator/strict, strict file creation, and strict directory creation. They flush before the final HTTP response body so the final GET cannot be lost when the child is terminated. Existing coordinator read/write lock opens are recorded separately. Application business-file snapshots remain unchanged across tested reads.

The final host appends a receipt before the first body chunk (including Content-Length streaming), records `completed=false`, then marks it completed and always saves again after the original ASGI call returns. The harness waits up to 10 seconds for all recorded GETs to be completed before process termination. Command observers match method attribute names and wrapped names as well as code names, and assert that Export cancel/retry/submit/startup-recovery are registered. Original singleton stub call counts must be exactly 3 in each local normal process and 0 in reopened/exhaustion/collaboration processes. These final instrumentation changes require the independent frozen run; run 10 is not reused as final evidence.

Command-call claims are limited to the explicitly registered methods listed in each receipt, including semantic-import `commit` and `review_batch`; they are not a claim about every possible future command. TCP audit observes filesystem operations. Zero strict disk creation does not prove an unchanged in-memory lock registry; registry invariants belong to the separate original strict-coordination and independent tests. Raw diagnostic logs retain original whitespace through the local `.gitattributes` rule.

The final fixture configures a deterministic text stub on the original singleton ExportJobService's `exporter` attribute. Its original provider-free input snapshotter, `_submit`, `_run`, persistence and locks remain active. This tests storage and source lifecycle, not real export rendering. Development runs 1-8 used the original synthetic-project TXT renderer; those retained diagnostic runs are **not final M5 evidence** and are not claimed as compliant storage-only acceptance. Runs from 10 onward use the explicit stub, reported in each host receipt.

Final frozen execution pending. No browser, PostgreSQL, real model, hosted CI, GPU, Windows DesktopHost, or POSIX SIGKILL evidence is claimed. GraphFlow `gf_read` was used first; exposed tools contain no index operation, so graph refresh is NOT_RUN.
