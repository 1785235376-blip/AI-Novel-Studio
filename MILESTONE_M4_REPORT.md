# M4 AI Execution Layer

**M4 implementation was published as `a880c22509091e1f085a06ad6ef0360cedce57c5`.
Full M4 remains PARTIAL. Narrow route-selector accessibility and new-test
synchronization corrections are ready; corrected-source hosted CI remains
pending publication. No
real-model quality acceptance is claimed.**

## Final correction source and targeted verification — 09:05 UTC

Current 1,711-input source map:
`07806b50d62bde0300dee44285d126147eab60760deda309ccbe4ea004b8115e`.
There are exactly three changed runner inputs against `a880c225`: the route
component, its additive UI regression and the new M4 runtime test module.
Production backend owners and original CI/gate/runner sources are unchanged.
[Correction publication verification](docs/delivery/v2-development/stage-m4-corrections-publish-verification.json)
records each check's actual source identity; it does not combine earlier
whole-tree maps into a claim of a rerun full suite.

The entire affected `test_v2_ai_execution_runtime.py` passes **31 / 30 profile
skips in File (26.35 s)** and **31 / 30 profile skips on new empty PostgreSQL
17.11 (90.92 s)**. PostgreSQL applied all 20 unchanged migrations, stopped
normally, and its new database is retained. These are selected-module results;
the corrected source's full backend CI remains pending. The route correction's
full frontend **2,165 pass / 8 old skips**, build/token checks and browser
inventory bind the unchanged final UI inputs, but precede the unrelated Python
test-only change; they are not described as whole-tree reruns.

The push failure was a test-control error: one six-second transport hold
incorrectly covered 31 real refresh transactions. The corrected new fixture
uses 32 explicit progress checkpoints, each capped at six seconds, with a
**120-second overall fixture cutoff**, failure propagation and finally-release,
original cancellation/completion and bounded actual worker joins. **Its overall
fixture waiting budget changed**; this is not a production performance
relaxation. The product's 180-second model deadline, existing eight-second
completion tests, all 30 full-snapshot equalities, history/version invariants,
and original cancellation assertions remain. Final CANCELLED/empty-output/no-error
assertions and a negative deadline/cleanup test are additive.

The archived diagnostic script adds 0.25 seconds before each real refresh.
With identical diagnostic latency, the original fixture fails after 22 calls
(9.66 s), while the correction passes all 31 calls (12.58 s). A separate negative
check proves the six-second per-step cap, its truncation by remaining time,
deadline failure propagation, release and actual thread join without changing
the product clock. These synthetic contracts do not measure model quality.

The final separate inventory has **10,728 nodes**, one additive negative
controller test, with the original 10,727-node order and exact skip/gate maps
preserved. Manifest SHA256:
`dd845e0714269306356d0600d66700751dd4efbc24eddb88eb8e7f41e98add1b`.
All four API catalogue files and the frozen V1 manifest remain byte-identical
to `a880c225`. The failed first initdb command used a relative share path and
stopped before creating a cluster; its error and the corrected absolute-path
initialization are retained as setup evidence, not test results.

## Route-selector correction — earlier UI verification source

The first hosted M4 browser journey reached graph execution and capability
inspection, then failed the unchanged exact label lookup for the populated
local-text route selector. Its nested option text changed the computed label.
The correction adds the existing visible label as an explicit `aria-label` on
that selector. One new unit regression covers its populated options, exact
label/role, initial empty selection, both route changes and absence of implicit
preview, dispatch or refresh. Browser assertions, waits, retries, skip rules and
all runtime safety boundaries are unchanged.

The corrected 1,711-input source map is
`823c74e9b2394e392bbb72cdb76c96a71771a26211ccc56fdcbf5d23d3c2e642`.
[Publication verification](docs/delivery/v2-development/stage-m4-route-label-publish-verification.json)
binds all six successful current-tree checks and their raw hashes:

| Actual corrected-source scope | Result |
|---|---|
| Focused component regression | Red reproduced: 17 pass / 1 fail; corrected: 18 pass |
| Full frontend | 2,165 passed / 8 existing skips |
| TypeScript / Vite / design-token guard | PASS / PASS / 52 files PASS |
| API catalogue and infrastructure | 279 passed |
| Browser collection only | Original 7; additive 16, no inventory/skip change |

Only the component and its unit test changed among runner-bound source inputs.
All 1,017 backend/test/workflow/runner inputs and four generated API catalogue
files are byte-identical to `a880c225`; no new whole-tree backend execution is
claimed from that equivalence. The separate V2 inventory still contains 10,727
nodes, preserving node order and skip/gate contracts, and now binds the two
corrected frontend hashes: SHA256
`706912e6df88fee3366e0b797a8ac315d1f07b995f9185f52edd15c2be5fcd62`.
The frozen V1 inventory is unchanged. The earlier source-consistency report that
conservatively reported a concurrent generated-manifest delta is retained;
the final verification distinguishes that manifest from runner source inputs.

The corrected live-browser journey and its three viewport checks are **NOT_RUN**
locally because the earlier Chromium EPERM restriction remains in effect. They
must be evaluated by the original hosted job after publication. Earlier hosted
or local results below are retained with their original source identities and
do not establish acceptance for this corrected full tree.

## Published `a880c225` hosted CI — all terminal at 08:54 UTC

[Exact workflow/job records](docs/delivery/v2-development/stage-m4-a880-hosted-ci-terminal.json)
and the [hashed original decoded-log/archive package](docs/delivery/v2-development/stage-m4-a880-hosted-ci-evidence.zip)
retain all five workflows and 29 jobs: **23 success / 6 failure / 0 cancelled**.
Every result is attempt 1. Feature tree is `2bc7e4d8cf1c7523b2ed43031bba36fbee60b546`;
the PR merge checkout `c8f9ee2292a954bf016fe11c2be7fb0974f03dcc` has that same tree.

- [PR Cloud run 38036271715](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38036271715):
  both original strict backend joins actually report `complete`, bound to the
  exact merge checkout, tree, run, attempt and original 10,727-node manifest.
  File: **7,126 pass / 3,601 skip / 1 shard**. PostgreSQL: **7,094 pass /
  3,633 skip / 2 shards**. Both original File TCP cases are joined. This is
  complete collected coverage, not monolithic PostgreSQL interaction equivalence.
- [Push Cloud run 38036268462](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38036268462):
  File **7,126 pass / 3,601 skip**; PG shard 0 **3,570 pass / 1,784 skip**;
  PG shard 1 **3,523 pass / 1 fail / 1,849 skip**. The new M4 repeated-refresh
  test observed its worker changing from RUNNING to FAILED during an assumed
  unchanged interval. Both strict joins failed the successful-execution
  prerequisite; reconciliation was **NOT_REACHED**, not a capacity timeout.
  The same test passed in the separately bound PR event. That pass does not
  replace or excuse this push failure; diagnosis and correction are recorded
  separately.
- Each event's protected original V2 browser **7 live + 8 geometry** passed.
  Each additive browser had **15 pass / 1 fail**, exactly the route-label issue
  above. M4 preview/dispatch/review, its geometry, reopen/cancel/revoke checks
  were **NOT_REACHED** in those failed journeys.
- Each event's full frontend had **2,164 pass / 8 old skips**, plus the separate
  two actual TypeScript client cases and **104** original browser cases
  (9 geometry, 12 Interop, 2 business, 7 experimental, 63 R4, 1 export,
  9 surface, 1 branch). TypeScript/Vite/token checks passed.
- Both Interop workflows passed their distinct File and PostgreSQL scopes
  (**345 pass / 68 opposite-profile skips each**) and Windows pipe reference.
  Original Windows host/fresh-base packaging passed within its hosted scope;
  user-machine acceptance remains **LOCAL_REQUIRED**.
- [Shared R123 run 38036271722](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38036271722)
  failed its unchanged assertion against fixed historical source `c6f2126`:
  `/api` had in-memory/final HTTP COMPLETED but persisted REJECTED; `/api/v1`
  had both COMPLETED. All three reproduction commands exited zero, but the
  final `baseline-red.json` was not produced. The original assertion and
  baseline remain unchanged. Allowed artifact 11663926647 was verified and
  retained; no earlier denied artifacts were retrieved.

No cross-event aggregate is substituted for either failed Cloud workflow.
Historical M3-C **PARTIAL_PR_CI_CAPACITY** stays historical; this M4 source's
observed failures above are recorded by their actual cause, not relabelled as
capacity failures. Real-model quality and independent security certification
remain outside these results.

## Published `a880c225` local verification — 07:45 UTC

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
