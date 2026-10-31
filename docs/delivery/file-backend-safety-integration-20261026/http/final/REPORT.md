# Frozen original-application TCP HTTP result

**PASS within the tested synthetic File scope; broader integration remains PARTIAL.**

- Frozen commit: `66e5c97c22ff719aa75f036988073bc24ebf9c57`.
- Frozen tree: `50c1ef09896dc94ad097e806ce9805bacef935ea`.
- Independent detached source: `D:\PoemSeed\Worktrees\file-safety-http-final-20261026`.
- Real process exit **0**, **not timed out**, runner `complete_pass=true`.
- Pytest: **4 passed, 3 warnings**, **239.75 s**. Full runner elapsed **241.628 s** with a **900 s** deadline.
- Source hashes and source/test/script status unchanged before/after. Parent process has no app modules loaded outside the frozen copy. All app module hashes from all ten TCP child processes independently match the frozen tracked source manifest.

Exact command, run from the detached source:

```powershell
python scripts/run_file_backend_safety_validation.py --label frozen-http --output-dir D:/PoemSeed/Worktrees/file-safety-http-20261026/docs/delivery/file-backend-safety-integration-20261026/http/final --run-root D:/PoemSeed/Validation/file-safety-http-final-20261026 --timeout 900 -- tests/test_file_backend_safety_http.py -q --junitxml=D:/PoemSeed/Worktrees/file-safety-http-20261026/docs/delivery/file-backend-safety-integration-20261026/http/final/frozen-http.xml
```

## Verified behavior

Both `/api` and `/api/v1` retain the original saved fixture: **32 consumers, 540 direct references, six pages**, with no lost or duplicate reference. Cold strict-only access returns the original 409 without business mutation; initialized strict traversal succeeds. Repeat pages preserve their items. Legal timeline mutation invalidates the earlier asset cursor. Reopened processes read current persisted sources and reject process-local old TaskCenter cursors.

File/local **semantic_import** and **exports** are separately queried on the same project as the asset fixture. Each source proves first/continuation/replay/last, original owner lifecycle mutation and old-token 409, followed by fresh reads after process restart. Imports use original HTTP job creation/cancellation. Exports retain the original singleton queue, snapshotter, worker, locks and file writer, with an explicitly configured **deterministic stub executor**. Private ABA goes through the original export writer. Mixed authority requests remain 501.

File/collaboration **agent_team** uses original HTTP team-run creation with no chapters, model calls or external calls. Both aliases prove pagination, replay, cancellation invalidation, membership revocation 403, restored-membership old-token 409, and reopened reads. Collaboration exports and mixed sources remain rejected. Collaboration Studio asset GET remains the exact **403 LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE** for development sessions. Positive combined collaboration Asset + TaskCenter TCP is **NOT COVERED**, not silently promoted to success.

Real asset budget admission is exercised with a test-only **4096-byte cumulative request ceiling**: both aliases charge **2528 physical bytes** before rejecting the next read with 409 and no partial items. Business snapshots remain unchanged. TaskCenter semantic-import paging still succeeds in that process, confirming it is not enrolled in the asset-only budget contract. This does not claim exhaustion of the default 256 MiB ceiling.

## Transparent audit and provenance

Ten original-app child process receipts contain **142 GETs**, all marked completed before child termination. Recorded command calls are **0** across the explicitly registered methods, including decorated Export cancel/retry/submit/recovery and semantic-import commit/review_batch. Claims do not extend to arbitrary future methods.

Observed actual Python write calls are **2**, both original compatible-mode coordinator lock initialization writes. **Business writes: 0. Strict writes: 0. Strict file creation: 0. Strict directory creation: 0.** Existing Windows lock read/write opens are recorded separately. These are disk observations; in-memory lock registry invariants are handled by the separate original strict and independent groups.

The exporter stub ran exactly three times in each local initial process and zero times in all reopened, exhausted-budget and collaboration processes. No real rendering, real model, PostgreSQL, browser, hosted CI, GPU, DesktopHost or POSIX SIGKILL acceptance is claimed. The independently reproduced fixed-A Windows asset-list cursor 503 remains a separate baseline result in `../baseline-A-asset-cursor.log`.

Evidence: `frozen-http.receipt.json` (source/exit/hash manifest), `frozen-http.xml`, `frozen-http.log`, `frozen-http-loaded-modules.json`, `child-audit-summary.json`, ten `child-receipts/*.json`, and `SHA256SUMS.txt`. Synthetic project data remains outside this archive.
