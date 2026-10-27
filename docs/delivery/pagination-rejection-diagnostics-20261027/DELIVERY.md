# Asset pagination rejection diagnostics

Status: **PARTIAL — original intermittent rejection remains unexplained.**

This package adds only opt-in test-server observation and tests. It does not
change production code, budgets, locks, permissions, response payloads, cursor
TTL, or acceptance expectations. It is not a repair of the original 409.

## Fixed baseline and scope

Baseline 6bced268539cee6938f346a27f945a9a290ee4f6,
tree 3c9a3c2684f2ba42581a72f717441922aea4670b. The app tree stays
775a084c75dd5cfd7ccf0189060b056bf8f1c309. Test/helper freeze:
99258ef5b2dbc4b20065e4b624a42deee9306f94.

- `tests/usage_endpoint_diagnostics.py`: safe static-code exception-chain
  observation, original outcome preservation, lazy-router installation.
- `tests/file_safety_http_server.py`: default-off observer, enabled only by
  `FILE_SAFETY_DIAGNOSE_USAGE=1`. This is a test host, not application middleware.
- Two test modules validate original result/exception identity, cancellation,
  observer failure, clock failure, code redaction, recursive route installation,
  and a deterministic synthetic exhausted-deadline exception chain.

## What the old evidence establishes

The prior final failure occurred on `/api/v1` warm strict **first page**, without
a cursor. Old-token TTL/load therefore cannot explain that specific failure.
Its final counters were 402 reads and 11,686,930 bytes, below the 8192 / 256 MiB
limits. Repeated identical final counters are compatible with a deadline
rejection before the next read increment, but are not proof of one.

The original graph route collapses many exception categories to
`STUDIO_ASSET_USAGE_UNAVAILABLE`. These include owner changes, missing data,
resource errors, and remapped HTTP 404/409/422. Observing only
`UsageBudgetError.__init__` could miss another underlying cause. The new tool
records the retained exception context chain even after `raise ... from None`.

## New observations and limits

The first exploratory full `/api/v1` run passed, but its route hook did not
attach under the installed FastAPI lazy routing. It is recorded as a failed
diagnostic installation, not evidence about the rejection's cause. The next
exploratory run correctly attached and passed the complete scenario, recording:

- expected cold strict missing-facility rejection;
- successful asset reads around 5–6 seconds, with 1505 reads / 43,465,442 bytes;
- expected stale-source rejection after a lawful owner mutation;
- intentionally reduced-byte-budget rejection with its original exception.

These expected negatives prove diagnostic visibility, not that the earlier
intermittent warm strict rejection was fixed. No diagnostic event from a new
unexpected warm strict 409 was captured in those exploratory runs.

An intermediate observer revision failed independent transparency tests:
emitter/getter cancellation or exception properties could mask the original
outcome. Only the test observer was corrected. Static error-code allowlisting
replaced prefix-only filtering. All historical red logs are retained.

The later exploratory run crossed a helper edit boundary and is not immutable
acceptance, regardless of its pass result. Final acceptance uses a detached
99258ef5 worktree; final receipts and results are recorded separately.

## Work handoff

Do not reimplement or weaken asset query business logic merely to turn this
rejection green. In a bounded test run on the environment that exhibits the
failure, enable `FILE_SAFETY_DIAGNOSE_USAGE=1` for the unchanged synthetic
`test_file_backend_safety_http.py` scenario. Preserve the complete process log,
JUnit, exit code, app/source hashes and receipt alongside the original
uninstrumented failure. `USAGE_ENDPOINT_INSTALLED` must be nonzero. A passing
diagnostic rerun does not replace failed frozen acceptance.

The observer emits only a small static set of known error codes, exception
types, source basenames/function locations, counters and monotonic durations.
It never intentionally emits request arguments, arbitrary exception messages,
headers, credentials, file contents or actual request/project identifiers.
Use only the established synthetic host and data; it is not a production
telemetry API or authorization to export private data.

No frontend/SDK, Work integration branch, main, CI, release, or published branch
was changed. F37 and the old Windows asset-list 503 remain separate observations.
No Windows, PostgreSQL, browser or real-model verification is claimed.

## Final immutable diagnostic-tool acceptance

On detached 99258ef5, 22 tests passed with exit 0 and no timeout: 20 diagnostic
unit/independent cases and the two API aliases of the original full synthetic
32-consumer / 540-reference business scenario. Independent 10 tests overlap and
must not be added. All 601 production source hashes were unchanged; the loaded
module receipt contains no foreign application files. The detached checkout
remained clean. Final raw logs, JUnit, module receipts and original HTTP audit
receipts are in `evidence/raw-evidence.tar.gz`, indexed by `raw-manifest.json`.

This is acceptance of the diagnostic tool in this environment. It does not
supersede the baseline's prior 3-pass / 1-fail uninstrumented final result.
No original intermittent warm strict failure occurred in this final diagnostic
run, so its root cause remains unknown.
