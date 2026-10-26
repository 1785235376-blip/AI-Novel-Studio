# Independent File backend safety merge review

Status: PASS for this independent 23-case File/Windows scope at the final common
freeze G `d24458225be78f3cbe804b2e325a2f02c3e95568`, tree
`f17fe2b160606c660bca6c0d400c21aff29b30ef`.

All 23 cases passed in one final run; process exit 0, no timeout, no skipped,
xfail, or xpass cases. Tracked app/tests/scripts SHA256 manifests are unchanged,
and all 482 recorded loaded modules came from the independent detached final
worktree. The final pytest duration was 9.24 s; subprocess wall time was
11.12 s under an explicit 600 s timeout. The final acceptance result is this
single run, not a sum of development results.

The prior F report remains byte-preserved as `REPORT-F1-66e5c97c.md`; its
receipts remain under `final-66e5c97c/`. G supersedes F for the current
independent result. A passing independent group does not resolve separate
refusals or override the coordinator's broader PARTIAL classification.

## Scope and independence

The reviewer wrote `tests/test_file_backend_safety_independent.py` independently
from fixed parents A `856d1ed3341fe0c24df1daff9a8bc1242c260e6c` and
B `31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f`. Only tests, their receipt helper,
and this evidence directory were edited on the independent author branch.
Production changes belonged to the integration owner. Every runtime run below
used a separate detached worktree at its recorded immutable commit.

The suite exercises real File owners with synthetic records. Mounted API cases
use the application's TestClient and original authority fixtures. The native
reader cases hold a real Windows write handle open, causing the production
CreateFileW read admission to reject it. No model, paid API, external network,
PostgreSQL, browser, or hosted CI acceptance is asserted.

## Independently authored checks

- Budgeted local semantic-import and collaboration team-run capture must return
  committed rows and lifecycle proofs while another transaction has dirty
  buffers, including rollback. Subsequent original writes on another thread
  must succeed.
- Budgeted and strict coordinated cross-instance writes must retain the inner
  committed update and reject the outer stale transaction, including an outer
  no-op. Physical byte changes with equivalent JSON must still fail CAS.
- A missing strict lock or exhausted budget must leave filesystem contents and
  coordination inventory unchanged. Both context variables must reset, and a
  different thread must retain ordinary original-owner write behavior.
- Equal duplicate lifecycle keys must be rejected by the experimental,
  identity, scope, authorization, and export owners after budget admission.
- Current actor observations must remain stable after unrelated user writes.
  Selected source proofs must ignore unselected collections. The export
  owner's original 100-row window must remain stable after an excluded actor
  or a row outside that window changes.
- Export resource refusal must raise instead of returning an empty success;
  an original writer on another thread must work afterward.
- Both `/api` mounts must reject a missing original lock in strict mode without
  initialization, then recover after an ordinary original write.
- Both mounts and both coordination modes must return the original graph
  route's 409 contract after actual native reader refusal, without page data,
  next cursor, token-cache changes, or filesystem changes; a later original
  write and fresh query must succeed.

## Receipts and test correction

| Frozen commit | Classification | Result | Process exit | Timeout | Source unchanged |
| --- | --- | --- | --- | --- | --- |
| `136686a4db95b120d96f14b34098b4298d59e14c` | First development run | 19 passed, 4 failed | 1 | No, 600 s limit | Yes |
| `dd1a70b510bc11bfe7b914b7fca5abc1c4777fb7` | Corrected development run | 23 passed, 3 warnings | 0 | No, 600 s limit | Yes |
| `66e5c97c22ff719aa75f036988073bc24ebf9c57` | Historical common freeze F, superseded | 23 passed, 3 warnings | 0 | No, 600 s limit | Yes |
| `d24458225be78f3cbe804b2e325a2f02c3e95568` | Final common freeze G | 23 passed, 3 warnings | 0 | No, 600 s limit | Yes |

The four first-run failures were an independent test assumption error. The
test asserted the internal `STUDIO_USAGE_RESOURCE_UNAVAILABLE` label; fixed A's
`app/creative/graph_api.py` already deliberately exposed
`STUDIO_GRAPH_USAGE_UNAVAILABLE` for this route. Requests returned 409 as
expected. Test-only commit `e4c99ccb3fa02fb50413288fa92d628373c9b115`
corrected the public error-code assertion. No production code was changed for
this correction. The complete 23-case suite was rerun on the new freeze;
19 and 4 are never summed into a passing result.

Each run directory includes `receipt.json`, its complete command, the process
exit code and timeout, `run.log`, JUnit XML, `loaded-modules.json`, and complete
SHA256 manifests of tracked `app/`, `tests/`, and `scripts/` files before and
after. Acceptance requires all of these checks together. Both development
runs loaded 482 relevant modules from their own detached worktree, with no
foreign source import. The second run completed its pytest suite in 8.85 s.

Final evidence is in `final-G-d2445822/`. The final source root is
`D:\PoemSeed\Worktrees\file-safety-independent-final-G-d2445822`.
The reviewer also verified that the final app tree is unchanged from production
merge `f6ae6c5fb2bda8b875bdbd1f32b5bafd18d9d070`.

After F, the coordinator observed three Windows GBK decoding failures outside
this group. `gbk-portability/REPORT.md` records the independent fixed-B
reproduction (3 failures) and a test-only fix (3 passes), both retaining the
machine's real cp936 default and unchanged production source. The correction
is in G. This report's complete 23-case group was rerun on G rather than reused
from F; the focused portability counts are not added to 23.

The three warnings concern the installed TestClient dependency and two existing
Pydantic `schema` field names. They are recorded in the logs. No warning was
converted to a passing test or used to excuse a failure.

## Read-only review of HTTP acceptance instrumentation

The reviewer separately inspected the HTTP helper and tests, first as explicitly
provided by the coordinator and then again at freeze F. The two reviewed HTTP
files are byte-identical between F and final G. This static review
does not add HTTP tests to the 23-case result above; the coordinator owns the
separate final TCP test run.

The helper asserts that `dependencies.export_job_service` and
`api.export_job_service` are the same original owner instance and replaces only
that instance's renderer callable. It retains the original snapshotter, queue,
storage, and writers. The final tests assert three actual stub calls for the
local normal run and zero calls for reopen, exhausted-budget, and collaboration
runs. This establishes synthetic storage/queue testing, not real rendering.

The initial review found that command matching by `code.co_name` alone could miss
decorated methods, and saving only before the final response body could omit
post-body command/write observations. Final freeze matches the attribute name,
wrapped name, or code name, includes semantic-import commit/review_batch, and
asserts key original export methods are watched. It always flushes the receipt
after the original ASGI application completes; a recorded completion barrier
must finish before process termination. The first body is recorded before it is
sent, so a Content-Length client cannot outrun the receipt registration.

Actual Python writes are counted separately from writable Windows lock opens.
The original atomic_write's `os.fdopen(...).write(...)` and coordinator lock
byte writes are observed. Strict file/directory creation and actual writes must
be zero. Compatibility-mode disk lock initialization may differ from in-memory
lock-cache initialization; this observer does not claim a zero in-memory
allocation count or exhaustive kernel-level I/O tracing.

The collaboration asset request explicitly expects
`403 LOCAL_AI_HOST_AUTHORITY_UNAVAILABLE` before and after reopen. It is a
denied Host-authority boundary, never a positive collaboration asset test. The
allowed collaboration team TaskCenter window has separate positive assertions.
No additional actionable defect was found in the final static checks of these
specified helper boundaries.

## Findings and limits

Fixed-B source review identified plain JSON decoding in the scope/authorization
lifecycle reader as a duplicate-key merge seam. The integration owner already
added strict duplicate-key decoding to these owners and export before the
first frozen run. The independent guarded duplicate-key tests passed. No
remaining production defect was reproduced by the final 23-case suite.

This review covers only the three allowed single sources: local semantic
imports, local exports, and collaboration agent teams without chapters. It does
not establish mixed-source querying, whole-history ABA detection, atomicity
across independent owners, persistent cursor guarantees, or hard RSS bounds.
Windows process termination is not described as POSIX SIGKILL. This suite's
native sharing check is an actual Windows file-handle test; it does not claim
cross-platform native behavior.

GraphFlow context and brief were attempted before source exploration. The
available `gf_read` returned unrelated current-index anchors; old
context/plan/index tools were unavailable. Fixed parent source and bounded
changed-file reads supplied the needed context. No claim of a successful
post-change graph index is made.

Synthetic runtime directories are excluded from published evidence; they are
not test results. No source history was reset, cleaned, rewritten, or force
pushed by this reviewer.
