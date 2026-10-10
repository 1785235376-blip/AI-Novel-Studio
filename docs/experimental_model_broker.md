# Experimental Model Broker and bounded benchmark evidence

Flags: `model_broker_v2` depends on `author_context_inspector_v2`;
`model_benchmark_v2` depends on `model_broker_v2`. The host composition owns the
allowlist. No candidate scan, hardware probe, benchmark, thread, or transport is
started by these service constructors.

## Existing authorities

The broker reads the active Runtime provider/model registries and the Model
Center's exact model/runtime configuration evidence. The media registry supplies
only installed runnable adapters; family definitions do not become candidates.
A discovered legacy Ollama name alone is excluded until explicitly verified and
enabled through the existing Model Center discovery bridge. Credentials remain in
the existing vault. An in-memory opaque credential-rotation fence invalidates old
receipts without serializing credentials or secret-derived hashes.

The project/branch resolver and host Model Center session are both required.
Preview and execution consult current chapter/project privacy. A broker quote
never authorizes sending. Author generation additionally needs the exact existing
AuthorRequestPreview receipt. The injected author coordinator constructs the
prepared Job; `JobManager.start_prepared` and final-hop/terminal callbacks provide
the actual existing execution path. The broker never creates a second author
executor or silently falls back after a failed or ambiguous dispatch.

Hardware limits use the existing host inventory only when explicitly requested.
They refer to total host capacity, not currently free memory or a guarantee that
a model will fit. Missing hardware, context, price, or latency evidence cannot
satisfy a corresponding hard constraint. Literature quality remains unranked.

## Atomic budget accounting

`ExperimentalStore.transaction` protects all ledger and budget operations using
the existing File cross-process lock or PostgreSQL transaction/row lock.
Reservations are scoped to project/branch, actor, caller idempotency key, exact
quote, and original task ID. Author receipts also bind the exact request digest.
Repeated callbacks do not reserve or settle twice. Aggregate admission counts all
actors in the scope, including ambiguous upstream holds.

Prices use integer micro-USD, explicit source and timestamps, expiry, and an exact
route fingerprint. Unknown cost is never zero. Strict amount limits require a
configured per-request reservation estimate. A reservation limit is not a promise
that a provider cannot charge more than its estimate. Usage-derived costs are
labelled calculations, not independently checked invoices; overrun blocks further
admission until explicitly reconciled.

Transitions:

- RESERVED → DISPATCHED at the final guard (idempotent)
- Not dispatched → RELEASED
- Known deterministic provider fee or reported usage plus configured rates → SETTLED
- Dispatched cancellation, unknown result or unknown usage → UNKNOWN_UPSTREAM;
  retain the estimate and concurrency hold
- Explicit versioned user confirmation of upstream termination and bill →
  RECONCILED, labelled USER_REPORTED_UPSTREAM_BILL; keep prior versions

A process restart never automatically replays a job. Persisted orphaned
reservations remain visible and are not silently released. The scoped task
projection detects missing transient callbacks or failed settlement, stops polling
as if an orphan were still progressing, and explains that no automatic replay is
possible. An explicit CAS reconciliation additionally requires confirmation that
the original executor stopped. An active in-process job cannot use that path.

## Benchmarks

Users create/edit versioned test sets with at most six total samples, one to three
repetitions, bounded output tokens, cancellation deadline, and total estimated
cost cap. Each explicit step runs one saved input through the existing TextModelNode.
No startup benchmark, paid/cloud benchmark, model download, tool execution, or
arbitrary workflow execution exists.

Current text test kinds: Chinese continuation, structured extraction, short review,
and textual tool protocol. Image/video workflow definitions can be managed and
results imported; execution is **NOT INTEGRATED**. A real local model still needs
existing validated and enabled registration. An unavailable real model is not
replaced by synthetic success.

Evidence stores exact route/adapter/model/runtime/workflow fingerprints, host
execution-node identity, input hashes, parameters, rule checks, measured wall time,
error counts, and ledger references. Missing quantization/hardware/runtime facts
stay null. Cold/warm state, tokens/s, GPU memory and literary quality are never
inferred from HTTP success. Imported evidence is unverified and cannot influence
routing. Changes to the test set, model/runtime/adapter/credential or explicit
invalidation make old evidence historical; only current executed error-free
latency observations influence speed ordering.

A/B preference review hides model labels until an explicit vote. It requires two
current, own completed runs with matching test sets/parameters. Preferences are
versioned, scoped, persisted and labelled small-sample personal evidence; they do
not become global model scores.

Cancellation fences all later output/evidence publication. Cancellation requests
cannot recall a dispatched input; a synchronous upstream call may finish only at
its own bounded transport timeout. Interrupting the browser does not imply the
upstream task was cancelled. Restarted RUNNING benchmarks require explicit
cancellation/reconciliation, never automatic replay.

## Verification boundaries

`tests/test_r4_model_broker.py` is parametrized for File and real PostgreSQL; it
covers actual registry binding, concurrent/idempotent budget reservation, source
and actor revocation, changed model/adapter/credentials, local-only enforcement,
unknown costs, actual usage settlement/overrun, CAS reconciliation, protocol
execution request capture, cancelled-result suppression, current evidence
invalidation and hidden-label preferences. `ModelBrokerPanel.test.tsx` captures
real frontend fetch URLs/headers/bodies and checks the author receipt path,
late-response fences, budget conflicts, fresh-authority navigation into the
existing draft review, test management and import boundaries. Mounted tests in
`tests/test_r4_broker_mounted.py` run the production router composition across
`/api` and `/api/v1`, including the real author JobManager and ledger hooks.
`frontend/tests/e2e/r4-broker.spec.ts` defines the real browser journey against the
dedicated synthetic-session profile (API 8022 / UI 5182); collection/type checks
are not claims that Chromium executed.

These deterministic tests establish software contracts. They do not establish real
model quality, actual GPU performance, commercial pricing, vendor licensing, or
user acceptance. No paid endpoint or real user credential is used for development.
