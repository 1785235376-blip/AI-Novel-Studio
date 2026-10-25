# TaskCenter consistent-query independent review

Review status: `STATIC_REVIEW_NO_OPEN_P1_P2`. Runtime status at this review:
`NOT_RUN`. Product cursor status: `UNSUPPORTED`.

This is a source and test-semantics review, not a substitute for execution.
The TaskCenter HTTP endpoint does not issue or accept a working consistency
cursor. The independent engine is deliberately unmounted. Synthetic digests
and identity epochs in its tests do not establish original-owner lifecycle
binding, membership ABA protection, or cross-owner atomicity.

## Reviewed sources

Baseline commit: `ffe1937911cff32d4ebd4770b350674627501d3a`.
Baseline tree: `447bfefcee8393b9b0907fe7daff2d5b044709da`.

The complete fixed tree contained only the root `AGENTS.md`; no nested
instructions were present under app, tests, or docs. The root rules were read.

| Path | Reviewed Git blob |
| --- | --- |
| app/experimental/ux.py | af6d36b66b2f500534deb6524b1f12e212bcf1f1 |
| app/experimental/ux_api.py | 629b8361262116740501b26598d95c4a4c939235 |
| app/experimental/taskcenter_query.py | 71735ef2543748b2dcc83789de8e977f3721df00 |
| app/experimental/taskcenter_cursor.py | c7fabb00ad82f7dac9af638607cda551e334e87f |
| tests/test_taskcenter_consistent_query.py | b9387f2cf7e53cd3b1c38bdd3e90a6314183b8bf |
| tests/test_taskcenter_cursor_independent.py | f132302639695cb2aca1ab7afbc7e554a5f7a576 |
| tests/test_taskcenter_query_measurements.py | e86b190d82c93e00e3dc975c8ccf469f08281344 |
| .github/workflows/taskcenter-consistent-query.yml | 2c47bf8bbcb174105d2e917d752d5690522a968e |
| scripts/verify_taskcenter_consistent_query.py | bb23cf8c059b376aba7534d8eae40e8c903b7c65 |

The shared ux sources were compared with fixed-baseline content: code before
and after the tasks method/route was unchanged except for the necessary new
query imports. Cancellation, diagnostics, search, scope fences, and original
projection functions were not modified.

The final OpenAPI additions were also reviewed: examples describe legacy,
authority-only, and explicit-offset success plus cursor refusal. They advertise
no successful HTTP cursor. The refusal example shows the detail portion; the
existing global error handler also supplies its standard envelope metadata.

## Findings and corrections

### P2-1: HTTP errors lost the new no-store policy — corrected in source

The first route candidate set Cache-Control on FastAPI's injected Response.
Both parser errors and the unsupported cursor path raise HTTPException.
The existing app.main.unified_http_error constructs a fresh JSONResponse and
preserves only exception headers, so the injected header was lost.

The final reviewed ux_api blob catches HTTPException after the original access
check, preserves its status/detail/headers, and explicitly adds no-store only
when the raw request opts in with authority or page_mode. This fixes the
identified error-response path without changing the global handler or legacy
requests. File/HTTP tests retain assertions on both 422 and 501 error headers.
This correction has been statically rechecked; runtime verification is pending.

### P2-2: inherited engine reset could race child threads — corrected in source

The initial engine rebuilt its lock, key, and FIFO after detecting a new PID.
Two first calls in a forked child's new threads could both enter reset, replacing
state and locks while another call was using them. FIFO operations could then
be protected by different locks, with a risk of unexpected errors or resource
bound violations.

The final reviewed engine rejects a PID mismatch with the fixed restart error
before acquiring, replacing, or mutating inherited locks, keys, or observations.
The child must construct a new engine. The independent tests include repeated
PID-mismatch refusal and a separate-process cold-token refusal.
This correction has been statically rechecked; runtime verification is pending.

## Security and compatibility assessment

- Explicit authority values come from the existing 17-reader catalogue and
  must also exist in the actual service registry. Repeated selections use OR
  without changing reader order or widening an owner's scan window.
- With no new authority/page_mode parameter, the legacy envelope, response
  cap, limit/offset behavior, and diagnostics call path remain in place.
  An isolated cursor continues to be ignored under the old contract.
- Counts are computed only after the existing reader and row scope fences.
  The original per-reader 200-row inspection bound remains unchanged.
  A visible source's truncation hint survives an empty q-filtered result.
- Capabilities are static implementation facts, not a dynamic denied-reader
  list. Empty/final results keep BOUNDED_AUTHORIZED_PROJECTION and NOT_ASSERTED;
  costs remain UNKNOWN.
- The HTTP cursor path rechecks original current authority and returns a fixed
  501 without reading task owners, minting a token, or provisioning a project
  marker. That is an honest unsupported path, not completed cursor integration.
- The standalone engine keeps bounded process-local digest metadata and
  fixed deadlines, signs opaque handles and page positions, checks the full
  caller-supplied observation binding, and does not store task rows or query
  text. TTL is not extended by continuation or replay. Mismatched binding
  probes do not delete the original valid observation.
- Source review found no new model/provider dispatch, business persistence,
  task transition, credential storage, database schema, or owner mutation.
  The absence of runtime writes still requires the authored snapshot tests
  to run; it is not claimed as an executed result.

## Independently authored counterexamples

The independent test file was written separately from the engine implementation.
It checks cross-context probes that must not poison a valid cursor; changes
outside the requested page; same-size replacement, insertion, deletion, order,
and revision changes; supplied original lifecycle epochs A1 to B to A2; replay
and complete traversal at capacity one; FIFO eviction without read refresh;
fixed TTL inherited by successors; expiry during the final page; malformed raw
tokens; no whitespace rescue; valid-shape MAC/position/handle tampering; strict
internal resource limits; cold and separate-process refusal; clock rollback;
and absence of visible or hidden durable engine files.

The File/HTTP tests were also independently reviewed for assertion strength.
Their snapshot enumerates all files and excludes only the existing
.workspace-mutation-locks directory, rather than excluding every dot path.
The two-reader OR/order case uses synthetic rows in the original File
semantic-import and media owners and invokes their original read paths.
Injected reader failures are explicitly synthetic; they do not prove every
one of the 17 real owners has been exercised.

## Unresolved integration dependencies

The original TrustedSessionResolver.binding_generation can establish a session
incarnation. CreativeProjectStore.existing_owner_only/incarnation can observe
an existing project incarnation without writing a missing marker. They do not
by themselves establish a complete original authority lifecycle observation.

IdentityService.set_membership_status has an unaudited mutation path.
Its updated_at string is not a reliable monotonic incarnation. The current
ReadContext equality check also cannot detect revoke/register of an identical
session binding. Branch scope has no independent general incarnation API.
Hashing reusable strings would not repair these gaps.

For those reasons the current actual HTTP modes must remain cursor-unsupported.
Completing M2 and the real authority/ABA portions of M5 requires a separately
reviewed minimal original-authority observation port; a new parallel permission
registry would be incorrect. The project lock must not be held across all
reader calls because it would reverse established lock ordering.

## Final small changes and verification harness

The final route sends the authorities keyword only for a non-None explicit
selection. Legacy route calls retain their original limit/offset keyword shape,
including compatibility with overrides that do not accept the new keyword.

The final File/HTTP tests explicitly cover both absent and present original
project markers. Marker creation/removal occurs only in synthetic setup before
the query snapshot. A filtered read-mid-revocation test covers both API prefixes
and both a reader returning normally and raising 403 after the real membership
revocation. It verifies that the original read made no business write, records
the test's deliberate revocation delta, and rejects the whole query without any
further business delta. These are reviewed assertions, not executed results.

The measurement source wraps the real File semantic-import reader, its scope
document read, and the original central fence. Samples use source sizes
0, 3, 199, 200, 201, and 2000 with explicit response-offset pages. Metrics
distinguish source rows/bytes from the unchanged central 200-row bound and
label tracemalloc overhead. They do not call themselves database pagination,
do not prefill values, and do not claim cursor support.

The workflow is scoped to the task branch and public repository, uses the
standard Ubuntu runner, read-only contents permission, pinned action commits,
and checkout without persisted credentials. It configures no secrets, database
service, paid API, model, user desktop, or self-hosted runner. It installs only
the project's declared development dependencies into an ephemeral environment.
The Python harness puts HOME, data, XDG, temporary files, and caches in separate
synthetic directories, removes common provider/database credential variables,
uses MOCK_PROVIDER=true and ENABLE_CLOUD=false, and does not upload its isolated
business-data directories.

The harness verifies the exact fixed baseline tree, archives it separately,
runs original tests before overlaying only the new red test file, records loaded
module paths/hashes and collected nodeids, compares baseline/candidate failures
and messages, and checks source hashes before/after. Focused pytest uses -s to
preserve real measurement output. It retains raw synthetic logs and JUnit
rather than inferring a pass from an unchanged failure budget.

## Execution and evidence boundary

At review time no confirmed permitted cloud runner had executed the new or
baseline tests. No red counts, green counts, timing, memory, or scale numbers
are inferred from source. Baseline failures have not been reproduced this round.
Real PostgreSQL, Windows runtime, frontend, browser, and models are NOT_RUN.

The fixed baseline tree has no .github/workflows directory. Historical runs on
other branches do not verify this candidate.

A new dedicated workflow was independently reviewed as listed above. Its actual
attempt was independently read back through GitHub:

| Evidence | Observed result |
| --- | --- |
| Candidate commit | d227d3e0c7a17eda47d9d456c33775d9b27dfe6a |
| Candidate tree | aa58fc7ceb9cb241e0ce29176025ec3dd48cd200 |
| Run | 40206566004, completed / failure |
| Job | 121208653993, verify, completed / failure |
| Job steps | jobs API: null; dedicated steps API: empty list |
| Job logs URL | null |
| Run timestamps | 2026-10-25 15:21:43Z to 15:21:46Z |

Run URL: https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/40206566004

The supported conclusion is BLOCKED_BEFORE_TEST_EXECUTION. No dependency
installation, baseline red reproduction, focused test, regression comparison,
snapshot proof, or performance measurement is established by this failed run.
The precise platform annotation reason was unavailable; this review does not
guess billing, quota, runner provisioning, or another specific cause.

The static-review result remains separate from this blocked runtime result.
Actual HTTP consistency cursor integration remains unsupported and the user's
complete M0-M7 goal is not yet fulfilled.
