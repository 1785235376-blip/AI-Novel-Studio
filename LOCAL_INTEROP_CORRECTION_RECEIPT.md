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
