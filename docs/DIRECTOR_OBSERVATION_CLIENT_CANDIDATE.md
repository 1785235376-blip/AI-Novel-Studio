# Staged read-only Director observation client

The typed client is not mounted in the application. It has GET-only status and exact adopted-DRAFT reads through the injected existing Studio transport. It does not obtain credentials, dispatch, review, cancel or retry operations.

Responses use a closed, versioned schema, exact proposal identity, captured project/branch scope, safe integer versions, bounded identifiers and digests. Preview/adoption/cancellation consistency is checked. In particular UNKNOWN_UPSTREAM cannot become confirmed cancellation, an adopted receipt must match the status Job/request/evidence/version, and an aborted response is discarded even if transport ignores AbortSignal. Returned nested objects are detached from the transport response.

The JSON fixture was captured through the real original Creative router/invoker, File owners and trusted Host resolver in an isolated test application. Provider wire content is mocked. The frontend fixture is an exact byte copy of the captured file; its paired SHA-256 receipt is retained. This is contract integration evidence, not browser or live-model acceptance.

Primary results:

- 30 new decoder/transport tests passed.
- Corrected combined scope: 81 passed in five files, including existing Graph Director client, review and canvas handoff tests.
- Forced TypeScript, production Vite build and token guard passed.
- The capture test passed before and after adding its explicit File-only marker.
- Backend source and PUBLIC inputs remained unchanged. Four existing actual archives were reread and their included payloads matched current files; no fresh packaging test or build is claimed for this frontend-only slice.

The initial combined UI command referenced a nonexistent handoff filename. Vitest ran only three matching files (53 passed). That result is retained but does not cover the omitted handoff tests. The corrected second command first checked all five exact filenames, then ran 81 tests. No test or product behavior was changed to produce the correction.

Independent second-agent review was unavailable. The user permits serial development; unavailable peer review is an evidence limitation, not an invented requirement to stop all work. Current frozen instructions and repository rules require proportional primary checks and honest applicable acceptance. Public activation and complete end-to-end work remain separate unfinished steps.

Evidence: `delivery/v2-development/director-observation-client-20261017`, adjacent `director-observation-client-*.json/.log`, and `director-observation-wire-fixture-r1/r2` receipts.
