# Local Interop V1 integration corrections

The first implementation commit `bbd6e65e3334c213d91a2343208817a9106298ff`
(tree `44c3ed1fdbf5d3e5ae9d1c1a8cc8fbdc5ec4f5e7`) remains historical evidence.
This is a correction within the new Interop task, not a restart or closure of any
historical independent review.

## Reproduced on the unchanged first implementation

Two negative checks failed before the correction:

1. Connecting without an event-sharing preview/approval sent a metadata event.
2. The canonical DIAGNOSTICS transport wrapper rejected the correlated
   TutorRequest envelope used by the actual HTTP endpoints.

The original code snapshot, failing tests and raw logs are retained privately.
No existing R1/R2/R3 assertion or historical failed evidence was changed.

## Consent correction

- Connect establishes handshake/session/liveness only and emits no context/events.
- Ongoing events require their own exact preview, positive approval, chosen field
  groups and session/peer/scope/source binding. Preview receipts are expiring,
  single-use and invalid after cancellation or changed source.
- The approved projection governs payload fields, event types and change
  detection. An excluded task cannot leak through a TASK_FAILED event label.
- Unsubscribe/revoke/disable/reconnect clears the grant and queue, cancels unsent
  dispatch and checks authority immediately before yielding HTTP body bytes.
- Diagnostics preparation pauses the existing grant and prepared receipts before
  the minimized preview; no implicit resume occurs. Already-sent bytes cannot be
  recalled. A separately visible standing grant and an ordinary one-shot Ask
  preview are distinct permissions, with an explicit Stop control always shown.

## Canonical diagnostics correction

DIAGNOSTICS requires TutorRequest with request/session identity, a non-null
DiagnosticCapsule and metadata-only context (content NONE). Bare diagnostic
payloads and content-bearing wrappers fail strict DTO/schema validation. Both
HTTP reference implementations apply the same canonical wrapper validation.

Both repositories share protocol manifest SHA-256
`77c1f82f0aec0ef385d95cacf6fe04530b83fb62d2403bc7341cbe6bf19c858c`.
All 36 manifest payloads also match the generated Python wheels.

## PostgreSQL readiness regression

The first hosted Interop PostgreSQL lane failed only its new peer-event readiness
check: a fixed 120 ms sleep ended before real PostgreSQL authorization/snapshot
work and event acknowledgement finished. It did not demonstrate an authorization
bypass or data inconsistency. The corrected test waits, with a finite 10-second
bound, for the actual peer receipt and fails if the session is revoked. Exact
sequence, delivery, queue and revocation assertions remain unchanged. The final
hosted PostgreSQL result must be read at the corrected commit, not inferred from
local File tests.

## Local corrected verification

- Shared contracts: 184 passed in each repository; strict TS, Ruff, schema and
  wheel parity checks passed.
- Combined Studio contract/Host/transport tests: 251 passed; 43 marked PostgreSQL
  variants remain NOT_RUN locally and are required in hosted CI.
- Actual loopback Host APIs and transport/diagnostics paths: 16 passed, one marked
  PostgreSQL variant NOT_RUN locally.
- Frontend full suite: 1094 passed, seven optional tests skipped; focused Interop
  DOM/client suite 46 passed, with the real TypeScript-client/Studio/separate
  Synthetic Tutor path passing separately.
- Application and test/config TypeScript checks, production build, token guards
  and whitespace checks passed. Nine browser journeys are authored; local
  Chromium remains OS-blocked before execution. Hosted browser checks are required.

Synthetic peers remain MOCK_ONLY. Development HTTP peer identity is self-declared;
actual current-user/installed-product mutual attestation and Tutor Desktop wiring
remain LOCAL_REQUIRED. Windows smoke verifies the standalone transport reference,
not actual Tutor Desktop integration or a hostile cross-user attempt.

## Hosted modal focus and finite PostgreSQL capacity

Both `a1b42cf` frontend jobs passed 1102 unit tests (7 optional skips), all 64 original browser tests, the real-client roundtrip and eight of nine Interop scenarios. The remaining unavailable-Tutor Escape failure was reproduced locally: an asynchronously disabled button can leave focus on `document.body`, outside the modal handler. A narrow capture-phase Escape/Tab fallback now retains the active modal boundary when focus escapes its subtree. The hosted assertions remain unchanged. Local verification: 1104 passed / 7 skipped; 56 focused tests; TypeScript, production build and token checks passed. No local browser retry was attempted. The successor must run its own hosted tests.

The full PostgreSQL job's outer limit is adjusted from 45 to a finite 55 minutes: its measured repaired baseline is approximately 42 minutes and the added Interop PostgreSQL suite takes 6–7 minutes. This is a capacity adjustment, not a claim that the current run timed out. All test commands, assertions, individual test timeouts, and the strict PostgreSQL skip gate remain unchanged. Other job limits are unchanged; a failure at 55 minutes requires investigation rather than automatic limit increases.

## Observed readiness on loaded editor and PostgreSQL

At source `9591396`, both full File lanes passed 4644 tests (2035 expected opposite-profile skips), both Windows application lanes passed, and the PR frontend passed 1104 unit tests (7 optional skips), all 64 original browser tests, all 9 Interop browser cases and the real-client roundtrip. Two same-tree counterpart failures were retained and diagnosed individually:

- Push browser selection setup sampled an empty `window.getSelection()` before opening Ask Tutor or sending any Interop request. The other eight Interop cases passed. The test now waits for the saved synthetic chapter, uses actual editor focus and keyboard selection, and observes the nonempty exact Unicode selection anchored in the current editor within a finite 10-second bound. Exact displayed selection, capsule text, content level and hash assertions remain; no programmatic range fabrication or fixed sleep is used.
- PR Interop PostgreSQL passed 250 tests and failed only a two-second wait for the synthetic unsent-event barrier, before unsubscribe assertions. The same push suite passed 251 tests. A deterministic 2.2-second storage delay reproduced that readiness failure on the unchanged source; the existing 10-second observation helper made the same probe pass. Every unsubscribe, cancellation, no-outbound and old-SSE-grant assertion remains unchanged. Focused Host/real-process tests passed 52 tests locally; 43 PostgreSQL variants remain NOT_RUN locally.

These are test-only readiness changes, with no production behavior, security assertion, original R1/R2/R3 test, skip gate or production timeout changed. Test/config TypeScript and all nine browser test collections pass locally. Local Chromium remains blocked; the successor requires its own ordinary hosted browser and PostgreSQL validation. Superseded full PostgreSQL runs are recorded by their actual concurrency-cancelled outcome, never as a timeout or a pass.

## Full PostgreSQL baseline fixture port collisions

Both full PostgreSQL runs at `3c6642c` completed with one failure each before the finite 55-minute job cap; neither was cancelled or labelled a timeout. Each passed 4644 tests and skipped 2034 expected opposite-profile cases. The PR suite took 42m27s and failed the unchanged owned-runtime stop fixture's fixed `127.0.0.1:54322`. The push suite took 49m13s and failed the adjacent unchanged double-start fixture's fixed `127.0.0.1:54324`. In each case production correctly rejected `EADDRINUSE` as `PORT_IN_USE`; available logs do not identify the socket holder. No other full-backend failure appeared.

The two tests now select OS-assigned available IPv4 loopback ports instead of assuming those fixed ports are free. Each original fixed-port defect was reproduced safely against an owned synthetic listener (RED); the repaired fixture passes while the same listener remains alive and connectable (GREEN). Only these two fixtures and a socket import changed. Every original stop, same-PID, exactly-one-owned-process and cleanup assertion remains intact. No production socket behavior, unrelated listener, other fixed-port fixture, test command, skip gate or timeout was changed.

Combined local focused Model Center phase1/phase2a and Interop Host tests: 168 passed, 42 expected PostgreSQL-profile skips, one warning. Local PostgreSQL is still NOT_RUN. The successor requires its own complete hosted CI; passing focused fixtures does not certify full-suite success. The finite 55-minute full PostgreSQL job limit remains unchanged.
