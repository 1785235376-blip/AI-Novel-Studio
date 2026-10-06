# Local Interop V1 testing and evidence

This file is a test-plan and evidence index. Do not interpret a listed test as
passed until the final receipt names its command, result and exact revision.
LOCAL_INTEROP_REQUIREMENTS.json records all 65 requirement sections; final PR
receipts supply immutable source SHA/tree and hosted check links.

## Required validation

- Strict schema/DTO invalid values: unknown field, version, missing capability,
  invalid ID/hash/authority/privacy, stale version and expiry.
- No credential or token-in-URL transfer; LAN/proxy/redirect fail closed.
- Existing host authorization: unauthorized project, changed membership,
  project/scope/chapter changes, revoked sessions and replayed previews.
- Host-authoritative FAILED cannot be overwritten by LLM SUCCESS.
- Subscribe, receive, revoke, then no later events; independent allowed subscriber
  continues. Disable/shutdown clears all bridge subscriptions and pending work.
- Explicit-click handoff checks invalid product/project/chapter/task, stale task,
  absent target, unauthorized scope and fabricated gesture.
- Empty/default metadata capsule, selected-content opt-in, diagnostic field removal,
  credential-free model projection, strict derived privacy and no locator fetch.
- Cancellation, deadline, bounded/coalescing queues, late old-session response
  isolation, repeated UI actions and interrupted/changed-source preview flows.
- Both products remain usable with peer absent; flags default off and forced off
  under V1_ACCEPTANCE_MODE. No paid provider or real manuscript fixture.
- Real local transport subprocess roundtrip against a labelled synthetic peer;
  independent reference adapter conformance in the cloud repository.
- Original Studio R1 project scope, R2 live observer revocation and R3 generation
  terminal regressions, full applicable backend/frontend/native hosted suites.

## Evidence labels

DONE means the stated functional slice and its required tests are implemented and
verified, not a whole-product release. CONTRACT_VERIFIED covers exact contracts or
reference behavior. MOCK_ONLY names synthetic peers. PARTIAL states missing
functional slices. LOCAL_REQUIRED means unavailable actual desktop integration.
NOT_RUN is not a pass. BLOCKED states the actual blocker and is never rephrased as
an approval. Historical frozen feature and independent-review boundaries remain.

Windows Named Pipe reference tests are scoped to current-user local transport,
framing, separate-process exchange and cancellation. Actual cross-user hostile
connection attempts, real tutor desktop integration and user hardware are
separate acceptance gates. The reference is never auto-started in production.

Raw hosted logs are retained privately; public delivery should contain only
non-sensitive compact counts, source hashes, commands and official CI links.
No historical failed evidence is rewritten or weakened by this new feature work.

## Local source-freeze receipt (2026-10-06)

- Strict shared contracts: 177 passed; both repository protocol bytes and wheel
  manifests agree (manifest SHA-256
  `9e3f77de6f169782c3fd25dfb298eda927832abfca2dd6210e871e73b37919b2`).
- Host plus actual separate-process Host API suite: 42 passed, 33 marked
  PostgreSQL variants NOT_RUN locally. The separate transport suite: 14 passed.
- Preserved original R1/R2/R3 plus project authorization subset: 657 passed,
  638 marked PostgreSQL variants NOT_RUN locally. Original assertions unchanged.
- Frontend full suite: 1081 passed, 7 optional HTTP tests skipped; new real-client
  HTTP path passed separately (1 test). Type/build/token checks passed.
- Seven new browser journeys: local launch BLOCKED by an OS IPC socket restriction
  before test execution. Hosted CI executes them in its ordinary browser lane.
- New Windows current-user pipe reference: local execution NOT_RUN; dedicated
  hosted Windows job compiles and executes the transport-only synthetic smoke.
- Independent two-repository/process probe passed with each repository's own
  package/environment. Initial FAILED stayed unchanged after ADVISORY guidance;
  verification FAILED. Only an independently enrolled newer READY/COMPLETED source
  satisfied verification. Unenrolled self-hashed authority was rejected.

These are local source-freeze results, not claims of future hosted success. Full
File/PostgreSQL/frontend/browser/Windows results must be read at the exact current
head of Draft PR #41. Earlier c6 baseline failure evidence and historical review
BLOCKED status remain unchanged. No universal all-workflows-green claim is made.

Full local File suite subsequently completed: **4624 passed, 2027 expected
skips, 3 warnings**, 433.53 seconds. This is local File evidence only; PostgreSQL,
Windows and hosted browser results remain separate exact-head gates.
