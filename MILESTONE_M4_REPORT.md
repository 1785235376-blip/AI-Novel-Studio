# M4 AI Execution Layer

**Bounded M4 execution checkpoint ready for publication. Full M4 remains PARTIAL;
new-SHA hosted CI is pending publication. No real-model quality acceptance is claimed.**

## Final current-tree verification — 07:45 UTC

All following final runners bind the same 1,711-input source map:
`4bdd24881be53dec5454739eb29de28369260f66574bab853b83d44dbcc444d4`.
Receipt/log/JUnit hashes and complete before/after source maps are verified in
[the publication verification](docs/delivery/v2-development/stage-m4-publish-verification.json).

| Actual scope | Result |
|---|---|
| Complete 13-file M4 + adjacent-owner File selection | 485 passed / 368 existing profile skips, 237.93 s |
| Same 13 files, new empty PostgreSQL 17.11 database | 484 passed / 369 existing profile skips, 483.93 s |
| Full frontend | 2,164 passed / 8 existing skips |
| TypeScript / Vite / design-token guard | PASS / PASS / 52 files PASS |
| API catalogue and infrastructure | 279 passed |
| Browser collection only | Original 7; additive 16, including one M4 journey |

PG applied all 20 unchanged migrations and shut down normally; its new database
and raw evidence are retained. The previously failing mounted `/api/v1` worker
case passes with the original new eight-second wait unchanged. The 79-file
previous File result (2,538 pass / 1,264 skip) and PG result (2,501 pass / 1 fail /
1,300 skip) remain tied to source `27cbca78…17c7`; they are **not** claimed as
whole-range acceptance for the final tree. All earlier failures remain below.

Separate generated inventory: 2,119 API operations (+8 / -0) and 10,727 collected
nodes (+258 over the parent), original node order/skips/gates preserved. Manifest
SHA256 `1d83d2a656a4bd27d3c9aee8220e77a110414da354883983b4673ecf4faf2761`.
[Generated-input proof](docs/delivery/v2-development/stage-m4-generated-input-verification.json)
and [same-round preservation](docs/delivery/v2-development/stage-m4-preservation-final5.json)
verify bound source bytes without claiming runtime or independent certification.

Local browser execution remains blocked before page creation by Chromium EPERM;
geometry/screenshots are NOT_RUN. APIProvider is RESERVED, actual model inference
and quality are NOT_RUN, user Windows/GPU acceptance is LOCAL_REQUIRED, broader
hardware/global scheduling is incomplete. Historical independent audit remains
BLOCKED and M3-C's PARTIAL_PR_CI_CAPACITY remains recorded. Exact new-SHA hosted
results will be reported in PR 47, not manufactured into this precommit report.


The user's 2026-10-10 instruction supersedes the older roadmap's M4 label with
AI Execution Layer. The six requested modules, original owners, HTTP/UI
contracts and bounded local-text slice are described in
[the execution design](docs/v2/ai-execution.md). Creative Core, Model Center and
the frozen V1 acceptance baseline remain the existing owners.

## Baseline and inherited evidence

Local and remote `feature/v2-narrative-platform` were independently verified at
`0bf79fb2d3b8be3ff7c3034371c4bc7642500d44` with a clean worktree before this
milestone. [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47)
remains the delivery target. No main/merge/release/deployment is authorized.

M3-C's exact-commit hosted evidence is retained in that PR and the delivered
terminal evidence package. Push Cloud CI
[38024123467](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38024123467)
passed both original strict backend joins. PR Cloud CI
[38024127486](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38024127486)
was cancelled at the File execution's original capacity limit; its two strict
joins failed their prerequisite and did not reach reconciliation. All 29 jobs
were terminal: 26 success, one cancelled and two failed. Each event's independent
browser 15 and protected original browser 7 + geometry 8 passed. These events are
separate; push does not replace PR acceptance. Inherited status remains
**PARTIAL_PR_CI_CAPACITY**; full M3 remains PARTIAL.

## Current implementation slice

- Explicit schema-2 `text_generate` node; original schema-1 seven-node catalog
  and local-rule behavior retained.
- One exact local model request over original ModelBroker, WorkflowRun,
  JobManager and TextModelNode, without a chapter or new scheduler/registry.
- Default-off `ai_execution_v2`, exact source/host/route/receipt fencing,
  proposal-only output and separate human review.
- Original external Ollama/llama.cpp interfaces and explicit synthetic protocol;
  managed auto-start and remote/API invocation are unavailable.
- Reserved APIProvider interface and explicit UI state, not paid-provider use.
- Capability/admission matching and finite original scheduling limits; no claim
  of GPU allocation, global fairness or measured model quality.

## Verification status

Development receipts and failures are being retained under
`docs/delivery/v2-development/`. Final frozen-source File/PostgreSQL selection,
complete frontend/build/token checks, API catalog/inventory extension, browser
collection and hosted exact-commit results will be recorded before closure.
Current intermediate runs must not be summed into an aggregate acceptance.

No real model weights, paid API, user Windows machine or GPU inference have been
used. Real inference/quality and broader scheduling remain NOT_RUN. Original
CI timeouts, assertions, skips, collectors and strict reconciliation gates are
not relaxed to improve this milestone's result.

Historical independent-audit status remains **BLOCKED**. This round’s code
boundary checks and peer rereads are ordinary engineering verification; they do
not restart, replace or certify that historical audit.

## Frozen-source checks available at 06:06 UTC

The final source map currently contains **1,711 inputs**, SHA256
`f3021f6c6f961c0502283207eb55b238a4afe97a44da7b59b340a619c4b4e654`.
Complete frontend: **2,164 passed / 8 existing skipped**, 270 passing files and
two existing skipped files. TypeScript/Vite production build and 52-file token
guard pass; the existing large-chunk warning is retained. Infrastructure and
API catalogue selection: **279 passed**. Each completed runner's before/after
map equals that current source map and its raw log hash was verified.

Browser collection is **7 original + 16 additive**; the previous fifteen
additive names and order are retained, and one M4 original-HTTP/MockProvider
journey adds three viewport assertions. This remains **INVENTORY_ONLY**.
The attempted local Chromium launch failed before page creation with EPERM.
Raw available error-context, trace and extracted test.trace bytes are preserved
under `docs/delivery/v2-development/m4-browser-launch-blocked-original/`.
Screenshots, geometry assertions and canonical visual comparison are NOT_RUN.
No workaround or denied artifact route was used.

The staged-tree catalogue has **2,119 operations (+8 / -0)**, generated from
`8c1b697bdb21` snapshot (not a final commit identity). The separate V2 manifest
contains **10,708 collected nodes**, retaining the previous 10,469 in exact
order and adding 239 new backend cases. Exact skips/external gates and the
original frozen V1 manifest remain unchanged. Manifest generation is inventory,
not execution or coverage acceptance.

The first complete-owner File/PG attempts began before a final two-file frontend
fix for a committed dispatch with a malformed HTTP-200 response. Those attempts
are retained unchanged with their actual source drift; no whole-source pass is
claimed from them. A separate same-selection final attempt uses a different new
empty PostgreSQL cluster/database. Neither running attempt is interrupted.
Final backend counts and normal-stop proof will be recorded after termination.

## Retained full-selection regression and correction

Both first File owner selections finished with **2,532 passed / 1 failed /
1,259 skipped**. The unchanged original
`test_variant_jobs_can_be_cancelled_independently` exposed a new early lookup in
the generic cancellation route. The correction preserves the original
`cancel(jid)` owner contract and checks the graph fence while holding the
original JobManager registration lock through cancellation. Missing IDs still
fail in the original owner; concurrent graph registration cannot bypass the
fence. Projection happens after releasing the lock.

The unchanged original generation-variant cases and model API selection passed
**45 tests** after correction. Two additional mounted regressions (both original
API prefixes) passed **4 cases**, proving active graph tasks cannot be cancelled
through generic URLs and the legacy cancel owner runs inside the registration
lock while projection runs outside. These focused results do not replace the
complete owner rerun. Both earlier PostgreSQL attempts continue naturally;
subsequent final verification uses another distinct empty cluster/database.

The corrected-source frontend/build/token and two browser inventories passed
again with unchanged frontend totals. Current source-map SHA256 is
`c20c47525472e842c1c25b8e49b0b8659b6712e9d7cf3df52cdbd8f6b40afafe`.
Catalogue was regenerated from `24dca9ec0bd0` staged tree (2,119 operations,
+8/-0 against the published parent). A collection attempt overlapped that
regeneration and correctly recorded **REJECTED** source drift. Its next stable
review passed **10,716 collected nodes**, +247 over the 10,469 parent, preserving
all old order/skips/gates; generated V2 manifest SHA256
`822b02aa03aef436135da01b0f39ca7c7e0f39b8386a327c867579e20af47ee2`.
No failed, rejected or earlier-source receipt is replaced.

## Corrected-source File owner result — 06:30 UTC

The complete selected **79-file owner range** now passes on File:
**2,537 passed / 1,263 existing profile skips**, 649.70 seconds, exit 0.
`stage-m4-owner-file-final3.json` binds the current 1,711-input
`c20c47525472e842c1c25b8e49b0b8659b6712e9d7cf3df52cdbd8f6b40afafe`
map before and after execution; its original log hash is verified.
The unchanged cancellation regression is now included in this full-range pass.
The first two File failures remain retained. Final PostgreSQL verification and
new-SHA hosted full-product/browser acceptance are still pending at this timestamp.

## First real-PG full-selection outcomes — 06:35 UTC

Both initial real PostgreSQL 17.11 attempts ended naturally with verified normal
shutdown and retained, separate databases. Their original migrations/timeouts
were unchanged. They did **not pass**:

- final1: **2,443 passed / 54 failed / 1,295 skipped**, 1775.346 s JUnit.
- final2: **2,445 passed / 52 failed / 1,295 skipped**, 1691.881 s JUnit.

Each has 46 newly added M4 failures caused by an invalid test-fixture assumption:
PostgreSQL generation `load_all()` is database-wide, and an earlier original
workflow-isolation test legitimately leaves two planner jobs. The correction
compares exact before/after persisted rows and preserves unrelated records;
it does not filter production storage, delete prior tests' data, or remove
no-side-effect checks. The original persistence owner remains under test.

The runs also contain respectively seven and five original creative-workflow
five-second wait failures, with differing cases. One first-run job is proven to
have completed after 6,156 ms; the other causes are not established by these
artifacts. These concurrent-run timing failures remain failures, and no timeout,
assertion, guard or skip is relaxed. Each run additionally contains the already
corrected original cancellation failure. All nine PG incarnation-fence cases
and 33 standalone JobManager seam cases passed in the first run, but those
subsets do not override the whole-selection failures.

## Shared-database diagnostic correction — 06:46 UTC

A separate new empty PostgreSQL database ran the original workflow that leaves
planner rows, original creative workflows, all new M4 runtime/API/contracts and
incarnation/JobManager cases, and the original generation-variant tests together:
**221 passed / 153 existing profile skips**, 425.19 seconds. The original five-
second waits all passed unchanged. All 20 original migrations, initial empty
state, normal shutdown and retained data are verified in
`stage-m4-shared-postgres-diagnostic1-postgres-runtime.json`.

Only three newly added M4 test files changed: exact global deep-baseline checks
now prove zero delta or the exact intended new project jobs and preserve every
foreign row. An explicit unrelated completed planner-row regression verifies
this on original storage; mutation/addition detection is tested on snapshot
copies. Production code, old tests, guards and timing limits are unchanged.
New File focused checks are **103 passed / 83 PG deselected**. This diagnostic
is not the full 79-file owner range and does not erase either earlier failure.

Current 1,711-input source-map SHA256 is
`27cbca78c09c0818b04097cc1e99cf135e0f60eb3d355959bb9d4597065817c7`.
The complete collection adds the two new backend-profile cases:
**10,718 nodes**, +249 over the published parent, preserving original order,
skips and gates. Manifest SHA256 is
`f0cdaae4869e7d7b388642dbe85d723b7ed543278c980e08526fdc9258961038`.
Final full File and PG owner executions will bind this corrected test source.

## Final corrected-test File verification — 06:56 UTC

Complete selected **79-file File owner range: 2,538 passed / 1,264 existing
profile skips**, 573.38 seconds, exit 0. The source map before/after/current is
exactly the 1,711-input `27cbca78…17c7` map above. Final frontend remains
**2,164 passed / 8 existing skips**; TypeScript/Vite, 52-file token checks,
279 infrastructure/catalog checks and original 7 / additive 16 collection all
bind that same map. The final full PostgreSQL run uses a separate new empty
database after every other test/build process has completed. No original
command, assertion, timeout, skip policy or gate was weakened.

## Final solo PostgreSQL result — 07:23 UTC

The complete selected 79-file owner run ended normally with **2,501 passed /
1 failed / 1,300 existing profile skips**, 1,575.201 seconds. The separate fresh
PostgreSQL 17.11 cluster applied all 20 original migrations, retained its data
and shut down normally. This run **did not pass**.

The only failure is the newly added mounted `/api/v1` test
`test_mounted_real_worker_review_preserves_existing_chapter_and_canon`: its new
eight-second test wait saw the original Mock worker still GENERATING, with a
full output and no terminal-hook receipt yet. This is not proof of completion.
The original workflow, cancellation and shared-global-row checks passed in this
run. No timing limit or assertion is relaxed; the new wait is being diagnosed.
Raw XML, log, normal-shutdown receipt and PostgreSQL server log are retained as
`stage-m4-owner-postgres-final3*`. Real-model quality remains NOT_RUN; same-round
code review does not clear the historical independent-security-review BLOCKED.

## Graph-guard correction — 07:31 UTC

Same-round source review found redundant full live-authority/database reads
inside the newly introduced graph guard, with no intervening I/O. The bounded
correction removes that duplication, retains an explicit exact-origin fence,
and revalidates full authority **and bounds after broker I/O**. Every original
dispatch, event, delta/completion, publication and settlement boundary remains
freshly checked. No test wait, production deadline, assertion or skip changed.
The original eight-chunk Mock worker path now performs 26 rather than 51 full
authority passes. Logs do not establish that duplication explains every wall-
clock delay; the retained failed run is not reclassified.

Focused original runtime/dispatch plus new guard regressions: **69 passed**,
including nine additions for before/after authority order, source revocation,
origin changes, cancellation, bounds mutation, output overflow and actual
deadline expiry during the broker callback. This is engineering verification,
not historical independent-security certification.

Final current-tree verification is a complete 13-file M4/adjacent-owner File
and new PostgreSQL selection. The earlier 79-file File pass and PostgreSQL
failure remain explicitly bound to their earlier source; neither is presented
as this final tree's whole-range pass. Original full hosted CI and strict joins
will run on the published SHA without changed capacity limits.
