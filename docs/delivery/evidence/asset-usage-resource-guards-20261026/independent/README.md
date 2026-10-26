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

Strict read-only positive support is **unimplemented / PARTIAL** in this scope.
The original mutation coordinator always calls `mkdir` and opens `a+b`; no
existing-only mechanism exists. Changing that shared owner is paused under the
user's ownership boundary. Initialized compatibility observations are not
relabeled as strict-readonly acceptance.

POSIX, PostgreSQL, browser, real model and GPU are **NOT_RUN**. There is no RSS
hard limit claim, strong ABA claim or cross-worker snapshot claim.
