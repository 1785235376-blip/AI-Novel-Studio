# M4 Text — source-aware screenplay adaptation checkpoint

Continues `899d40df5273413d987f9ee98d41a7405ed16d0a` under the overnight
Master Roadmap authorization. This is a bounded TEXT-13 slice following the
published TEXT-15 screenplay export and TEXT-17 generic Script increments.

Status: **PARTIAL — selected final-source checks verified; new hosted CI pending**.

## Implemented scope

One saved chapter or its exact selected substring can be previewed, dispatched
through original AuthorPreparer/ModelRouter/ModelBroker/JobManager, reviewed with
an explicit source-linked difference report, then adopted as an independent
SCREENPLAY v1. The existing Creative UI hosts this flow. Source novel/Canon are
not modified. No second core, graph, provider registry, queue or asset store.

This first slice does not yet archive proposals through AssetLibrary. The
original asset owner currently requires an authentic Graph source tuple; a new
adapter must not forge one. Tagged original-owner archival, idempotent recovery
and real-model adaptation verification remain follow-on work. Single-chapter
scope does not claim the roadmap's full multi-chapter range functionality.

[API, lifecycle and limitations](docs/v2/source-aware-adaptation.md).

## Browser failure diagnosed from original 899d evidence

Both original Cloud events failed the same two Creative live tests: screenplay
format selection and generic Script purpose selection. Each reached its original
180-second test deadline; nine other Creative tests passed. The controls and
options were visible in all four traces. Installed Playwright 1.62.1's actual
accessible-label calculation included the select option text in an enclosing
label, so the existing exact labels did not match.

Three additive regression cases failed before the correction. Explicit
`aria-label` attributes on the two product selects fix the accessible names;
the original browser assertions, timeouts and previous journey bodies remain
unchanged. Trace-based label calculation and new jsdom tests do not substitute
for executing the next SHA's hosted browser journeys.

## Integrated engineering worktree change

B commit `4d45acb6a274dc3d19ff797bded83f51591474f3` is serially integrated.
The staged catalog wrapper has an optional conservative `--compact` mode which
excludes only delivery evidence, verifies retained staged blobs and import
origins, and blocks actual reads of excluded inputs. Default full mode and the
original catalog generator remain unchanged. Two exact staged-tree comparisons
produced byte-identical four catalog outputs. Details and limitations are in
[the compact snapshot report](docs/delivery/ci-capacity/COMPACT_STAGED_CATALOG_20261010.md).

## Development evidence retained

Initial new-contract iterations exposed incorrect assumptions in the new typed
binding and synthetic preparation guard, followed by two incorrectly configured
collaboration test fixtures. All failing receipts and source maps are retained;
none is relabeled as a pass. Latest new-module File check: **40 passed / 40
opposite-profile skips**. Initial focused frontend **9 passed**; a new optional
model-flag-disabled draft recovery case is being added. The first new test mock
TypeScript check failed, its optional RequestInit typing was corrected, and the
subsequent check passed. Final-tree and adjacent-owner results follow below.

## Inherited boundaries

- 899d complete File jobs reached their unchanged 20-minute budget and were
  cancelled without final JUnit/completeness receipts. No full File pass claimed.
- 899d Creative browser failures above remain FAILED_OBSERVED, even after a local
  correction. Other browser, Windows smoke and PG results are reported separately.
- c491 retains its 16 local PG failures and zero-job Cloud configuration failure;
  the latter was corrected in 899d, not retroactively relabeled.
- e6ff retains an observed hosted PG call failure without final traceback plus
  incomplete File execution. Passing neighboring runs do not erase that evidence.
- Windows interactive/GPU/quality acceptance and historical independent security
  review remain unperformed or BLOCKED. This checkpoint is not release acceptance.

### Pre-publication races reproduced and corrected

A normal same-round read-only code review found two gaps in this new path. It
was not the historical independent security audit. Both findings were reproduced
with deterministic Event barriers before fixing production code:

- Terminal persistence: **4 failed / 4 profile skips**. Blocking either the
  settlement save or final notification save allowed refresh and actual screenplay
  adoption before an injected storage failure. The original Job condition spans
  both writes. Adaptation now acquires it strictly nonblocking and verifies the
  durable terminal record. A busy publication remains pending without changing
  proposal/history; no new readiness state or blocking scope/Job lock is added.
- Cancellation during admission: **2 failed / 2 profile skips**. The original
  reservation committed before its ID reached the proposal; cancellation stranded
  an undispatched RESERVED hold. The failure path now retains its pointer and uses
  the original finalizer only when this Job is not registered and the exact ledger
  confirms no dispatch. Unconfirmed finalization remains explicit, with no replay.

The same six regression cases then passed. Added successful-publication and
persistent-output-disagreement cases also pass. Current complete new-module
File result: **50 passed / 50 profile skips**. Earlier eight adjacent modules
passed **307 / 304 skips** before this new-module-only correction; they are not
silently called final-tree execution. Final shared-owner and PG checks follow.

[Review record](docs/delivery/v2-development/stage-m4-adaptation-code-review.md)
and all red/green logs, JUnit and source maps remain available. No previous test
body, assertion, skip rule or timeout was relaxed.

### Selected real PostgreSQL checkpoint before Host-capability correction

New empty `v2_m4_adaptation_final1_20261010`, PostgreSQL 17.11, original sorted
20 migrations, loopback port 55453, retained database and normal stop receipt:
**316 passed / 315 original profile skips**, eight selected modules, 414.13 seconds.
This covers the 50 new adaptation cases and adjacent original generation,
incarnation, origin, terminal, Graph/runtime and text-asset receipt owners.
The source map stayed unchanged throughout execution. No simultaneous local
frontend or Cargo/PG workload was scheduled in this window.

A subsequent UI integration check identified a missing Host capability gate:
ordinary Creative development sessions must not mount private adaptation reads
and turn their expected 401 into a whole-workspace lock. The next correction
exposes HOST_SESSION_REQUIRED while retaining manual Creative functionality;
private API authority is not loosened. Results on this preceding tree remain
separate from that correction's verification.

The Host gate has its own retained red evidence: two API cases and one workspace
case failed before correction. Capabilities now distinguish trusted versus
ordinary Host-less sessions. The private endpoint still returns 401; the manual
screenplay editor remains enabled. Two API cases pass after correction. A new
hosted draft/reopen journey uses the existing isolated trusted Host fixture; the
ordinary Creative journey verifies the 401 gate without initiating model work.
The complete previous browser test bodies/configuration remain unchanged.

The first full frontend invocation preserved **2,435 passed / 8 original skips**,
but one original four-case suite failed to load: `--root frontend` did not change
process cwd, and its existing file-based browser-contract check resolved a path
from the repository root. No original test is edited to accommodate this runner
error. The failed full log/JUnit/source map is retained; the next run uses the
original `cd frontend && vitest run` command. Build did not start after this
nonzero result and is not claimed as passed.

### Captured Host authority, including token ABA

A further same-round owner-boundary review found that repeating the old Host-token
validity check alone did not capture its registry binding generation. Revoke and
re-register of the same token could restore validity while an already-admitted
adaptation retained an old closure. Six deterministic new API cases reproduced
this before correction: same-session rebind, replacement-session rebind during a
blocked provider, and rotation immediately after Author preparation, across both
aliases. Their original failed receipts are retained.

Adaptation now reuses the existing Graph/Host authority resolver, including its
captured principal, binding epoch, local connection and Origin checks. This is
wired only to the new adaptation path; Director authorization is unchanged.
Nonpackaged collaboration membership cannot substitute for Host provenance. The
new branch privacy test now exercises its original owner directly and explicitly
expects HTTP model denial in that unsupported mode. One interim targeted run
passed all eight Host cases but failed two new direct-service exception-type
expectations (`KeyError` versus the owner's `FileNotFoundError`); only those new
fixture expectations were corrected. Final same-source verification follows.

### 899d hosted terminal evidence

Both original Cloud attempts ended naturally with failure. File and PG shard0
were cancelled at their unchanged budgets; both PG shard1 reports contain
3,743 passed / 1,961 skipped. The push shard0 event stream also records a failed
call in the original `test_manual_refresh_completion_boundary_requires_archive_before_review[postgres-settling]`.
Cancellation left no final JUnit or assertion traceback for that shard. This is
explicit **FAILED_OBSERVED plus incomplete execution**, not merely capacity.
The two original Creative label failures are separately retained. Required
execution-job joins failed, so no complete strict coverage pass is claimed.

The corrected full frontend command passed **2,439 tests / 8 original skips**,
with 284 files passed / 2 skipped, in 77.74 seconds. The first subsequent build
command completed TypeScript/Vite but used a nonexistent token-check script path;
its nonzero receipt is retained as a command error. Verification then uses the
project's original `tsc -b`, Vite build and `../scripts/check_ui_design_tokens.mjs`
sequence, without changing source or checks to accommodate the mistake.

B's final docs-only commit `60b19c72e876885d53fba6d0a84776d04bcce4c0` is also
serially integrated. Its [hosted cache/capacity report](docs/delivery/ci-capacity/HOSTED_CACHE_AND_CAPACITY_20261010.md)
uses the sole original CI archive. Cache saves are not called hits or speedups.
The original [899d hosted terminal receipt](docs/delivery/v2-development/stage-m4-script-hosted-terminal.json)
and [summary](docs/delivery/v2-development/stage-m4-script-hosted-summary.md) are retained.

### Final-source selected checks (in progress)

- Complete UI: **2,439 passed / 8 unchanged skips**, 77.74 seconds.
- Original TypeScript project build + Vite build + token guard: **PASS**, 52 token-checked files.
- Six selected backend modules on File: **238 passed / 237 profile skips**,
  144.70 seconds. This includes all 58 new adaptation cases plus original
  Creative foundation/Director workflows, Graph Host API, Script and screenplay export.
  The six Host ABA regressions and corrected branch-private fixture are green.
- Each completed check above has the same final source map and no in-run drift.
  A new empty PostgreSQL run of the same six modules follows; it is not yet claimed.

The final-source fresh PostgreSQL run has now completed normally: **238 passed /
237 profile skips**, the same six modules, **355.75 seconds**. All 58 new
adaptation cases pass on this backend too. Database
`v2_m4_adaptation_final2_20261010` was absent, proven empty before all 20 original
migrations, retained afterwards, and its owned server stopped normally. No local
frontend/Cargo/other PG work was scheduled during this run. These results share
source map `bac96892e14816867570117902ea140361ef9ba4a9079a5b913469df8f3b8ee1`
across 1,765 input files with final File/UI/build checks.

### Final inventory, catalog and infrastructure

- All **352 infrastructure tests pass** in 12.47 seconds; unchanged workflow
  passes the previously SHA-verified official actionlint binary.
- Two independent complete collections agree on **11,533 ordered nodes**, +116
  against 899d. This is inventory, not executed coverage. V1 frozen SHA256
  `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`,
  old product test bodies, prior browser bodies, original skips and gates remain.
- Original catalog generator: **2,145 operations**, +18 aliases, zero removed.
  Actual compact snapshot retains 2,288 files / 31,123,881 blob bytes and omits
  397,459,350 delivery-evidence bytes (92.74%). Retained blob checks, import
  confinement and excluded-input read checks passed. Four generated output
  hashes match the snapshot and current files. No new full snapshot was created;
  exact full/compact comparison on this new tree is NOT_RUN.
- Final V2 inventory SHA256:
  `c57f8890a3274efa02274ce4e9ced3319ac7416dea89b153003266281905d5c7`.
- [Source-bound publish verification](docs/delivery/v2-development/stage-m4-adaptation-publish-verification.json)
  explicitly records full_source_pass=false, Asset archival not implemented in
  this slice, real-model adaptation NOT_RUN and historical independent review BLOCKED.

Next work continues the mandatory original AssetLibrary draft/version archival
and safe restart convergence before broader TEXT-13 completion. This checkpoint
is intentionally recoverable and partial, not completion of that requirement.
