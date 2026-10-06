# A01 configured-model candidates: bounded original execution

## Scope and honest claims

The simulator retains the original manual deterministic mode. Configured model
suggestions are optional, require a completed manual rule check, and run once per
saved source run. No model is silently selected or started when the feature opens.
Default-OFF and V1 force-OFF behavior remains unchanged.

Production composition uses the existing `AuthorPreparer`, `ModelBrokerService`
and `JobManager`. It creates no alternative executor, adapter registry, prompt
builder, provider credential, automatic fallback or autonomous expansion loop.
Real inference quality, literary accuracy, GPU equivalence and independent model
review remain **NOT_RUN**. Synthetic and captured-transport tests verify protocol,
authority, persistence and review plumbing only.

## Source and approval map

1. The saved simulation fixes chapter versions, selected viewpoint character and
   time/calendar, current reviewed graph/knowledge digest, planning node/ancestors,
   assumptions, resources, hard constraints and user step/branch limits.
2. `POST /runs/{id}/model/preview` selects an actual registered LOCAL_ONLY TEXT
   route and calls the original author preview in A05 character mode. Its request
   contains the current character-visible reviewed projection, the author's
   hypotheses/constraints, selected visible evidence IDs/text and a JSON response
   contract. It contains no chapter manuscript, omniscient graph records, approved
   plan/style enrichment or credentials. A05 includes the full current *character*
   projection; the simulator's selected knowledge IDs remain the narrower set
   permitted by deterministic event preconditions and model evidence references.
3. The broker records a CUSTOM route preview with an explicit zero USD provider
   fee bound. Dispatch is allowed only with the exact reviewed request receipt,
   current route and a known zero price: a labeled synthetic fee, or a current
   non-synthetic price record with zero reserve and both input/output rates zero.
   Unknown cost is unavailable. Local hardware/electricity is not claimed free.
4. Explicit `model/dispatch` durably claims one job ID before reserving the original
   ledger and starting the exact prepared job. The trusted origin is
   `story_simulator_model`; the original whole-generation acceptance endpoint
   rejects this draft-only origin. A05 requirements are retained with that stamp.
5. `model/refresh` checks the original live job and terminal ledger. Only a fully
   settled, zero-fee COMPLETED receipt with live original authorization can import
   candidate data. It does not send, retry or replay anything.
6. Candidate JSON is parsed as strict bounded data, not executable instructions.
   Duplicate JSON keys/route IDs, unknown fields/evidence, incorrect types,
   overlong content and exceeded user step/branch counts are rejected. Every
   candidate carries an explicit evidence-ID list; empty means speculative.
   The exact original simulator transition round checks prerequisites, time,
   character knowledge, visible graph links, resources, hard constraints, loops
   and final goals. Failed events never mutate hypothetical state.
7. `model/select` requires exact preview and candidate digests and an explicit
   candidate ID. It atomically creates one separate READY simulation, retaining
   model/evidence provenance. The person must still advance that run, choose the
   route and save it into the original R3 REVIEW process. There is no automatic
   planning approval, manuscript mutation or Canon update. The R3 proposal keeps
   its model-candidate source provenance and checks it again on review.

## Bounds and revocation

- User bounds remain at most 32 steps × 8 branches, 256 deterministic expansions.
- Original JobManager enforces 64,000 UTF-8 output bytes and a 120-second deadline.
- One admission and at most one selected candidate run per source run; CAS and the
  original broker idempotency key prevent duplicate admission/selection.
- Actor/session/branch, flags, source content/version/privacy, selected character
  projection/time, graph/planning target, route identity, price and budget are
  rechecked before send and result adoption. The original author and broker
  last-hop guards remain active.
- Cancelled, invalid, unknown-admission and restarted tasks never replay or append
  late candidates. Cancellation is durable before original job cancellation.
  Unknown admission retains conservative accounting rather than guessing a
  provider never ran. Restart loses transient original authorization and blocks
  importing or approving old model results.
- Stale source/knowledge hides all simulation output. Changed model policy/session
  hides its preview/candidates while preserving usable manual rules. A dependent
  selected route and its planning review fail closed when model authority is lost.

## Verification and reproduction

Backend suite: `tests/test_r4_story_simulator_model.py`, plus original
`tests/test_r4_story_simulator.py` and `tests/test_r4_story_simulator_mounted.py`.
Fixtures cover both `/api` and `/api/v1`, File and marked real PostgreSQL.
Run with the existing isolated `r2-run.sh` harness; locally exclude
`postgres_backend_only` because no local PostgreSQL is available. The marked
PostgreSQL cases require actual `TEST_POSTGRES_DATABASE_URL` and are not substitutes
for File tests or mocks.

Coverage includes exact A05 adapter serialization, villain-only secret exclusion,
registered local discovery/Ollama adapter with captured HTTP and real zero-price
configuration, route/price/budget changes, schema/evidence/bounds, concurrent
admissions, cancellation, unknown admission, restart, planning review and the
original generic accept fence. The shipped MockProvider has one exact-marker,
explicitly labeled synthetic candidate response. This helper is never invoked as
a fallback for another registered model.

UI regression: `frontend/src/experimental/StorySimulatorPanel.test.tsx` covers
explicit preview/consent, double clicks, manual result refresh, exact candidate
selection, cancellation/unknown state and replaced-scope late responses. Existing
manual authoring/review/recovery tests remain applicable. DS-v1.0 primitives and
tokens are reused without shell changes.

Hosted browser journey: `frontend/tests/e2e/r4-story-simulator-model.spec.ts`,
collected under `frontend/playwright.r4.config.ts`. It uses the real React/File
API and original shipped synthetic provider, checks all three desktop widths,
manual candidate-to-review flow, one ledger admission, source staleness and no
manuscript write. No HTTP business-response mocks. Local browser/visual execution
is **NOT_RUN** because Chromium launch is denied; no retry was attempted. Hosted
CI must supply actual browser/geometry and real PostgreSQL receipts before those
gates can be reported passed.

### Local receipt (2026-10-05)

- Combined original simulator, mounted simulator-model and A05 context/API suites:
  **128 passed**; **128 real PostgreSQL cases deselected**, not claimed passed.
- Focused catalog/default-OFF/shipped-fixture rerun after the final catalog
  availability correction: **6 passed**.
- React simulator tests: **13 passed**. Full frontend TypeScript build check:
  **PASS**. UI token guard: **PASS**. Diff whitespace check: **PASS**.
- Playwright collection: **2 journeys collected** (original manual + new model).
  Collection is not browser execution. Browser screenshots/geometry and actual
  PostgreSQL remain **NOT_RUN locally**, awaiting the parent's hosted CI gate.
- No paid inference, real model quality evaluation, merge, release or deployment.
