# Original PostgreSQL Director terminal and pending-review lifecycle

Status: PRIMARY_CHECKED bounded backend integration. Independent review remains
unavailable; this is not full product, real-model or release acceptance.

## Actual gap and implemented owner

The former opt-in terminal/pending gate accepted only the original File generation
repository. A fresh real PostgreSQL baseline failed at that gate before admission.
The same DirectorModelCoordinator now accepts the original PostgreSQL repository
only when its real Database engine URL matches the original ExperimentalStore
endpoint. A different repository/database still fails before job admission.
No fallback to File, second job store, workflow engine, schema/table or migration.

PostgresGenerationRepository publishes passive terminal evidence only from the
original live worker/capability, at the exact publication thread/state/binding.
The same closed evidence validation, original job/output/request/route identity,
zero-settled accounting and precommit authority semantics are retained. The
publication transaction locks the original project row KEY SHARE, then the
original generation_jobs row FOR UPDATE; it writes the reserved envelope only
inside that existing row's repository payload. Acknowledgment is returned only
after the database session commits.

Generic saves still reject explicitly supplied reserved evidence before database
access, including the unchanged original no-database rejection test. Normal saves
now take the same generation-row lock and preserve any existing validated immutable
evidence. Omission cannot erase evidence; generic saves cannot mint it. This keeps
normal Job.public persistence and output clearing compatible without exposing a
new public reserved-field write path.

The private generation snapshot leaf locks the same row and yields detached data.
Original pending/review code holds that leaf through the original scoped JSONB
transaction's commit. Authority/source/policy callbacks occur before leaf entry;
no second owner or callback is acquired underneath the leaf. Current project
incarnation, source, Host/session, actor/scope, route, license and budget remain
required. Canonical UUID validation replaces File-path validation for this owner.

## Working lifecycle

A terminal result can become a pending proposal, survive coordinator/repository
restart and fresh Host identity, then be reviewed into exactly one original
DIRECTOR DRAFT and reopened. Expired live execution is not resurrected. Pending
parsed notes remain reviewable after original output is cleared; passive evidence
remains immutable. Two independent coordinators serialize concurrent prepare and
review against the same original database, without duplicate adoption.

A failure before the terminal transaction commits leaves no envelope. A lost
acknowledgment after commit preserves the actual envelope. In both cases the live
job remains FAILED with publication UNKNOWN and no automatic retry; current fresh
authority may read the actual durable outcome. Historical evidence never itself
becomes execution authority. No global lock-wait or power-loss guarantee is added.

## Exact evidence and limits

Original runners, original tests and workflow definitions were not edited.
All provider responses use the existing mocked wire with the real LocalTextAdapter
and original worker; no live model, paid API, GPU or external process was called.

- baseline-r1: 1 real failure, BACKEND_UNSUPPORTED, fresh RED database
  v2_director_pending_red_20261018, OID 29964, empty-before-20-migrations probe.
- development-r1: 1 positive lifecycle PASS on RED reuse.
- development-r2: 13 PASS / 1 FAIL. The new independent-coordinator fixture shared
  one broker and replaced its store; corrected only the new fixture to construct
  separate original broker instances. The original store-identity guard remains.
- development-r3: 14 PASS on RED reuse.
- fresh-r1: 23 PASS / 10 File cases deselected on fresh GREEN database
  v2_director_pending_green_20261018, OID 31303, empty-before-original-migrations.
  Includes 14 new lifecycle/boundary cases and 9 unchanged generation-incarnation
  tests: reused slug, missing project, immutable binding and real delete/save locks.
- file-regression-r1: 159 unchanged File terminal/pending/lifecycle/race tests PASS.
- http-r1: 1 PASS on GREEN reuse: original mounted ASGI HTTP actions, explicit
  preview/dispatch, pending/review, duplicate denial, restart/reconcile/read,
  actual saved human edit, revoked session. This is original-router TestClient
  with real PostgreSQL, not full application TCP/browser acceptance.
- commit-boundary-r2: 2 PASS on GREEN reuse, actual transaction rollback and
  postcommit acknowledgment loss. r1's helper incorrectly required live COMPLETED
  even under injected publication failure; the new tests now explicitly require
  original FAILED/UNKNOWN semantics and exactly one attempt. Failed logs retained.
- Every PostgreSQL run confirms owned startup and terminal server stop.

No frontend source changed, so no repeated TypeScript/production UI build. No
full-suite, public distribution rebuild, Windows, browser, real model quality or
all-V2 readiness claim. Earlier File-only reports remain historical; this report
adds current bounded PostgreSQL evidence without rewriting old outcomes.

## Structured SCREENPLAY V2 transport follow-through

The existing two V2 SCREENPLAY HTTP scenarios also pass with genuine PostgreSQL
owners: model-v2 preview/dispatch, restart, pending review, human edit, DRAFT
adoption/reopen, and rejection of wrong source kind or missing Host. The original
scenario assertions are reused unchanged; only their File persisted-byte helper
is replaced by canonical reads of actual PostgreSQL JSONB and their restart helper
constructs fresh original PostgreSQL owners. This is not a mocked persistence
view. The original model response remains a test wire.

Receipt director-pending-postgres-screenplay-http-r1: 2 PASS on the existing GREEN
OID 31303, server stopped. No production changes were needed after 80b42c8. As with
the Storyboard route check, this is mounted ASGI transport, not a full product
browser, real model or Windows acceptance result.
