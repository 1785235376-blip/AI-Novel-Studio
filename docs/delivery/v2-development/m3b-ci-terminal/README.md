# M3-B terminal hosted evidence

**Overall acceptance: FAIL. Strict backend aggregate: FAIL.** This is normal
read-only evidence capture for Draft PR 47, not an independent audit or a new
execution. The [manifest](../m3b-ci-terminal.json) records all **29 jobs**, all
terminal on **attempt 1**, with separate event/run/job identities and timestamps.

## Exact source identity

- Feature head: `c386b0608ae92d18c351b5cb6e367380808a45cf`
- PR checkout: `ec342fe9b69ba45d850d971ce2e15d1b12046096`
- Both trees: `2ec6365e1f1f183f029c9f0a94d040d134e22b47`
- The run/job API declares the feature head; checkout logs and PR coverage
  environment identify the distinct synthetic merge commit. Equal trees do not
  make those commit identities interchangeable.
- Shared R123 also checks out historical source
  `c6f2126115b52e17839d48efea091dc21ec08c61`, tree
  `eb80a9fa5f5aa6b8c2cbd0e1e67f7b7a48ac522f`.

## Terminal runs

| Workflow/event | Run, attempt 1 | GitHub result | Job results |
| --- | --- | --- | --- |
| Cloud / push | [37962531356](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37962531356) | failure | 6 success, 3 failure, 2 cancelled |
| Cloud / PR | [37962541363](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37962541363) | failure | 7 success, 3 failure, 1 cancelled |
| Local Interop / push | [37962531267](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37962531267) | success | 3 success |
| Local Interop / PR | [37962541535](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37962541535) | success | 3 success |
| Shared R123 / PR | [37962541295](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37962541295) | success | Historical RED reproduction only |

Events and overlapping suites are never added into a product pass total.

## Failed and incomplete gates

- **File execution is CANCELLED_INCOMPLETE in each event.** Last logged backend
  progress: push **93%**, PR **50%**. Neither has a final backend count. The
  **174 infrastructure passes** per job are separate from full File execution.
  The PR media-tools installation lasted **631 seconds**, versus **16 seconds**
  on push; its execution step ran **517 seconds**, versus **1,127 seconds** on
  push. These are recorded step intervals, not a verified causal diagnosis.
- **Both mandatory Backend / file and Backend / postgres jobs fail in each
  event.** Their execution prerequisite logs `EXECUTION_RESULT: cancelled` and
  `TCP_RESULT: success`, then exits 1. Receipt downloads, provenance join and
  exact complete-collection reconciliation are **NOT_REACHED** (GitHub marks
  the steps skipped). No strict PostgreSQL aggregate pass follows from shards.
- **PostgreSQL execution shards succeed**, separately in each event: shard 0
  **3,447 passed / 1,740 skipped / 5,193 deselected**; shard 1 **3,393 passed /
  1,800 skipped / 5,187 deselected**. They remain individual execution results.
- **Independent media is 11 PASS / 3 FAIL in each event.** Logged JUnit is
  14 tests, 1 failure, 2 errors, 0 skips. The metadata-file journey fails at
  `v2-local-ai-files-live.spec.ts:82:77`: scope-preview button not enabled within
  15 seconds (disabled resolution, then element not found). Both legacy
  default-off and acceptance-mode journeys time out after 180 seconds during
  the second `bindAndOpen`, at `v2-local-ai-legacy-host-live.spec.ts:97:9` calling
  line 15's feature-navigation click. Root cause is not established by this
  capture; screenshot/trace paths printed in logs were not opened.

## Frontend scope differs by event

Both events pass **2,040 unit tests / 8 existing skips**, TS/production build and
**49-file token guard**, **9 geometry**, **12 MOCK_ONLY Interop browser**,
**2 business browser**, and **2 actual TypeScript-client** tests.

- **Push frontend: CANCELLED_INCOMPLETE.** Cancellation occurs while installing
  media validators, after those earlier successes. Experimental, R4, export,
  functional-surface and branch-surface browser stages are all **NOT_REACHED**.
- **PR frontend: SUCCESS.** Its later stages separately pass **7 experimental**,
  **63 R4**, **1 export**, **9 functional-surface**, and **1 branch-surface** tests.
  PR completion does not supply the missing push stages or erase other failures.

## Other bounded successes

Per event, original V2 browser jobs pass **7 live + 8 geometry**; original File
TCP passes **2 actual + 102 harness**. Cloud Windows passes **59 native + 3
environment contracts**, host/package smoke, embedded Python **3.12.9**, and
PostgreSQL **16.15** recovery checks. These are not interactive desktop acceptance
or model inference.

Each Local Interop event separately passes File **345 / 68 skips** and PostgreSQL
**345 / 68 skips**; Windows reference **8** and native-boundary **33** checks remain
**MOCK_ONLY**, with real signed-binary trust, install registration and desktop
integration **LOCAL_REQUIRED**, cross-user attempt **NOT_RUN**. Shared R123 success
means all three historical defects were reproduced **RED**, not current-head
acceptance.

## Evidence and integrity

The manifest includes saved run-attempt/job metadata, Git commit objects, each
job's checkout SHA/tree, step outcomes, logged JSON receipts, exact log line
references, byte counts and SHA256 hashes. All 29 connector-decoded log strings
were saved as UTF-8 with BOM/newlines preserved. This does not assert preservation
of original HTTP/compressed archive bytes. Log hashes verify saved bytes; logged
JUnit/coverage counts are not independent artifact reconciliation.

The two pre-existing media files remain untouched. Each has exactly one extra
terminal LF relative to the connector string; every other byte is identical.
Their exact versions are `job-113928707575-connector-exact.log` and
`job-113928741339-connector-exact.log`; both originals and their hashes are retained.

No artifacts, traces, screenshots or Library files were downloaded. Historical
artifact **11615127270 download 403** and **11618169199 Library 403** restrictions
remain respected, with no alternate route. No cancellation annotation was
retrieved; timing is only consistent with unchanged File 20-minute / frontend
25-minute budgets. No visual approval, independent-audit claim, rerun, cancellation,
product/test/workflow edit, commit, push, PR write, merge or release was performed.
Existing M3-B report, M3-A terminal manifest and older outcomes are preserved.
