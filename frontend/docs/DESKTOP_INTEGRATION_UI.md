# Desktop Integration Preparation UI

Scope: existing Creative Studio Tutor Integration only. No second state database, protocol/schema changes, new shell, model launch, real manuscript, paid API, deployment, or production trust claim.

## Actual integration path

`App.tsx → interop/entry.tsx → deferred LocalTutorIntegration.tsx → same-origin client.ts → existing authenticated Studio host`.

The lightweight entry remains in existing shell slots. The dialog, permission center, desktop details and their CSS load only after the user opens Tutor. A load failure preserves the Studio editor, offers retry, and does not connect or share. Cancelling a pending module load prevents its late result from opening a dialog. Identity changes close the current dialog. No startup peer discovery or Tutor request is performed.

`desktop.ts` describes product-host HTTP DTOs, not additions to the frozen PoemSeed 1.0 protocol. All state and permissions are host projections. React state is transient request/view state; nothing persists to localStorage or a separate store.

## Formal state and connection details

The UI directly renders `desktop.state`: Not Installed, Detected, Untrusted, Ready, Connected, Authorized, Degraded, Disconnected, Unknown. Absent/unrecognized state or pending confirmation displays Unknown. Error-message strings never determine connection state. A connected reference peer remains Untrusted because it is not production-authenticated.

The details panel shows product display name, stable Product ID, version, protocol version, trust, transport, negotiated capabilities, host-measured session age, expiry and the exact current standing metadata allowlist. Only the current host `session_id` is selected. Another session or duplicate session rows cannot provide permission authority.

Five independent stages are displayed: transport connection, handshake, peer authentication, session establishment and capability negotiation. `Product ID != Product Authentication` and `Connection != Authorization` are explicit. Missing native/signature/install evidence stays LOCAL_REQUIRED; synthetic peers stay MOCK_ONLY.

## Permission Center

Nine independent categories are rendered from host receipts:

- App Status
- Task Status
- Model Metadata
- Diagnostics
- Selection
- Current Chapter
- Specific Context
- Standing Metadata Events
- Deep Link

AVAILABLE means the capability can be requested. It is not content consent. Selection, chapter and specific context keep the existing version-bound preview and explicit send confirmation. Standing metadata retains its separate opt-in/preview/confirm flow and never authorizes prose. Navigation remains user-click initiated.

`POST /permissions/revoke` correlates request/session/category, checks the targeted REVOKED state and complete permission set, rejects broadened/restored permissions, clears stale review material, and accepts only a host-confirmed stopped standing grant. A failed/ambiguous receipt leaves the authority display Unknown and blocks new content sharing until a valid refresh. Other session state is never used. Revoking task/model metadata also removes the corresponding selected outgoing fields.

## Emergency disconnect

`Disconnect & Revoke` cancels the current frontend request immediately and calls the host's combined cleanup route. Success requires the matching request/session, DISCONNECTED, revoked, subscriptions_stopped, pending_cancelled, standing_grants_cleared and transport_disconnected acknowledgments. Missing/false fields remain Unknown with an explicit retry. A physical close cannot be inferred from local authority revocation alone. If local close is proven but peer acknowledgment is absent, the UI says so separately.

Late Tutor, permission and state responses cannot restore a revoked session. A new connection does not restore old content reviews or standing grants. Master OFF and ordinary Close retain their original fail-closed acknowledgment rules. Cleanup is bounded; Close does not wait for an unnecessary post-revocation status refresh. No project, memory or case data is deleted.

## Task-owner and handoff boundary

The App never lends its generation job ID to Export or Workflow adapters when switching surfaces. Those panels currently own selection internally, so Tutor receives no invented current task ID there. Actual owner-bound export/workflow metadata remains available at the adapter seam. Exact export/workflow OPEN_TASK navigation remains unavailable until those existing owners expose a safe selected-target interface; the host must return HANDOFF_TARGET_NOT_FOUND. Explicit OPEN_FEATURE navigation to their existing surfaces and the existing read-only generation task receipt continue working. No shadow task store or automatic launch is introduced.

## Health and evidence

Transport, peer, session, capabilities, events, tutor and verifier are shown separately. Tutor/Verifier unavailability does not claim Studio failed. Event source provenance is DIRECT_EVENT, POLLING or SYNTHETIC, with meanings shown. Polling is not labelled realtime.

## Tests and visual boundary

- Existing consent, request/session identity, source-version, project/chapter switch, focus, master-OFF and failed-disconnect assertions are preserved.
- Added formal-state, all nine revoke, scoped/duplicate session, incomplete emergency acknowledgment, late status, load-cancel, same-origin client and narrower-permission tests.
- The opt-in actual frontend-client → real Studio host → Synthetic Tutor HTTP harness verifies the DTO seam and cleanup using synthetic data only. This is MOCK_ONLY contract evidence, not native Desktop acceptance.
- Playwright's existing interop suite retains geometry/focus checks at 1366×768, 1440×900 and 1920×1080; three additional scenarios cover deferred loading, formal details/permissions, independent revoke, acknowledged emergency cleanup and a failed acknowledgment retry.
- Browser cases are prepared for the authorized hosted CI lane. Local browser execution was not retried because that Chromium OS IPC lane was already denied. Test collection is not browser execution or screenshot approval. No new local screenshots or startup timings are claimed.
- No protected shell layout, tokens or primitives changed. Existing DS-v1.0 references and consumer rules apply.

## Reproduce verification

From `frontend` with the existing lockfile dependency environment:

```sh
npm test
npm run build
npm run lint
LOCAL_INTEROP_REAL_HOST_TEST=1 INTEROP_PYTHON=/path/to/test-python npm test -- --run tests/localInteropRealHost.test.ts
node node_modules/@playwright/test/cli.js test --config playwright.interop.config.ts --list
node scripts/measure_interop_bundle.mjs dist docs/desktop-bundle-baseline.json docs/desktop-bundle-comparison.json
```

Actual browser execution belongs to the hosted CI lane. It additionally uses the existing Playwright interop configuration and the isolated synthetic host fixtures.

## Bundle evidence

Baseline is exact `bcd60afb96cc69bdfd81db619cb0121d8712f074`, built before frontend edits with the same existing lockfile/toolchain. `desktop-bundle-baseline.json` and `desktop-bundle-comparison.json` contain measured artifact bytes and gzip bytes; `measure_interop_bundle.mjs` regenerates the comparison.

The HTML bootstrap group is index + React/query preloads. App-route JS/CSS are reported separately because App itself loads at normal application startup. Editor and other unchanged vendor chunks are not mislabelled as free or deferred. Previously Tutor was embedded in App; now Tutor has a separate user-opened JS/CSS chunk. A zero baseline standalone Tutor chunk does not mean the old integration had zero code.

Runtime startup impact is NOT_RUN. Built size and module-boundary checks are not a measured startup latency benchmark. Vite's existing >500 kB chunk warning remains, and no assertion of overall startup improvement is made.
