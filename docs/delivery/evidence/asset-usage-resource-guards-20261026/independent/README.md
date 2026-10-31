# Independent resource counterexamples

All fixtures are synthetic. This unit has its own worktree and authors only
`tests/test_studio_asset_usage_resource_independent.py` and this evidence folder.
It does not edit shared owners, product readers, authorization decisions,
frontend or SDK. Original mounted `app.main:app`, original File repositories and
the isolated File/Mock runner are retained.

## Baseline

Product origin is `c6ec9529043dd63e4b96a34de558939bf2efd848`, tree
`d3d39ce5dbd602f7fabc7fab4357709af61da8f5`. Python is 3.11.9 on Windows.
The first minimal original-budget run passed 6 tests. The separate original
budget plus old independent suites passed 57 tests in 120.68 seconds; its raw
output is `baseline-m0.log`. The latter raw run began before this unit's new test
file was authored, and does not serve as a clean frozen-source receipt.

`baseline-budget-frozen.*` retains an early 6-pass run whose receipt honestly
records its then-dirty new test file. It is superseded for clean-source evidence
by `baseline-budget-clean.*`, a distinct 6-pass run after the test-only commits.
That clean receipt binds product sources to the original baseline and includes
the unexecuted new independent test file in its manifest. The overlapping
groups are not summed as a unique test total.

## Independently authored expectations

- Reject excessive nesting, a long field, a long number and many tiny objects
  before the original allocating JSON decoder.
- Count repeated and nested reads cumulatively, then reset between requests.
- At explicit `before_open` / `after_chunk` barriers, reject growth, atomic path
  replacement and same-size in-place changes without relying on sleeps.
- Repeated first/continuation/replay requests must refuse resource failures,
  preserve `no-store`, return neither cached rows nor a fabricated empty page,
  and avoid creating tokens on failure.
- Reauthorization at observation barriers retains the same request budget and
  real Host revocation returns original 401 `SESSION_REQUIRED`.
- The 30 copied valid saved Graphs plus 2 Timelines remain an explicitly labeled
  synthetic scale fixture exceeding the normal Graph create cap: 32 consumers,
  540 positions, six pages at limit 100, both API aliases.
- Compatibility GET over initialized files may have zero actual write calls
  while still opening writable coordinator lock handles. A first-lock fixture
  preserves the original operational lock creation and compares directories,
  business hashes, cursor registry and coordinator registry separately.

The one inspected token that detects cumulative JSON excess is charged; the
test allows that sentinel and requires the rejected document not to count as an
admitted document. This was aligned with the documented counter semantics
before the new tests were first run.

At initial authoring, strict read-only positive support was **unimplemented /
PARTIAL**: the original coordinator always called `mkdir` and opened `a+b`.
Shared-owner modification was paused until the user explicitly approved the
precise owner proposal. The final source now supplies an opt-in strict mode
using initialized original coordinator facilities; it does not claim that
initialized compatibility queries alone constitute strict acceptance.

## Final independent frozen runs

This unit detached its separate worktree at the exact published source freeze
`18731becb0060d3006dd3f5ab8fe0c6cc00c0266`, tree
`a40cc8e58c304cd77072f31ca98703a439c860cc`, then used the original isolated
runner through `record_asset_usage_validation.py --require-clean-code`.

| Independent group | Actual result | Receipt |
| --- | --- | --- |
| New independently authored resource, read-boundary, authorization and strict-mode cases | 39 passed, 3 warnings, 69.37 seconds pytest time | [resource receipt](final-independent-resource.receipt.json) |
| Original independently authored pagination, permissions, lifecycle, resources and mixed-owner cases | 51 passed, 3 warnings, 115.16 seconds pytest time | [legacy receipt](final-independent-legacy.receipt.json) |

Both receipts have exit code zero, empty before/after source status and
`source_unchanged_during_run=true`. The unit independently recomputed every
manifest source hash and each raw log hash after completion. These overlapping
groups are reported separately, not added as a new unique acceptance total.

The 39-case frozen run proves the following within its synthetic File scope:

- Four hostile JSON shapes fail before the original allocating decoder, plus
  mounted scope/hidden-consumer variants fail without private diagnostics.
- Actual original HTTP file bytes equal the one fresh request budget's charged
  bytes on first, continuation and replay requests. Nested reads reuse the same
  budget; different HTTP requests receive different budgets.
- First/continuation/replay budget failures return sanitized no-store refusals,
  neither cached results nor empty success pages, without token issuance.
- Both API aliases preserve the original 32 saved consumers / 540 positions /
  six-page result, without duplicate or missing positions.
- Explicit strict queries succeed on existing initialized facilities on both
  aliases, including replay and the final page. The tests observe zero mutation
  attempts, zero actual write calls, equal full directory/file snapshots and
  unchanged original coordination registry. Cursor registry changes correspond
  only to successfully delivered continuation tokens.
- Missing original lock files or a cold coordination registry produce the
  stable strict refusal, no initialization, no filesystem changes and no new
  coordination or cursor registry entries. Original Host denial remains 401 on
  the tested initialized paths.
- Compatibility mode still opens original writable lock handles and can create
  an original operational lock on first use. Its business files remain equal;
  this physical write is retained as a compatibility fact.

The independently authored same-size-write counterexample exposed a real
Windows product problem in preliminary coordinator execution: `fstat` metadata
could remain stale after a write changed already-read bytes. The assertion was
preserved. Its original failure and the native-reader correction are retained
under [core evidence](../core/pre-native-same-size-failure.receipt.json).
Windows growth/overwrite/replacement attempts can themselves be denied by the
OS while a protected read handle is open; these cases are reported as denied
writer attempts followed by a sanitized query refusal, not as successful
in-place mutations. Native handle safety observations are in the core folder.

Final source review confirmed that strict lock acquisition, unlock and close
errors map to the strict unavailable result and that failure cleanup retains the
original lock/depth protocol. No further blocker was found in this review.
The middleware's all-File-chain claim is limited to its exact canonical paged
GET routes and the mixed endpoint. Original typed nonpaged routes remain under
their compatibility contract.

POSIX, PostgreSQL, browser, real model and GPU are **NOT_RUN**. There is no RSS
hard limit claim, strong ABA claim or cross-worker snapshot claim.
