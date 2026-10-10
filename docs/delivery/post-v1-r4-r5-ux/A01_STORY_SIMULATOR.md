# A01 Story Simulator: bounded manual planning

Status: EXTEND. This is an engineering-complete deterministic/manual slice, with real-model suggestions intentionally unavailable. It is not a literary-quality or release-acceptance claim.

## User-visible loop

Open the experimental workbench’s 剧情推演 tab. Select saved chapter versions, one focal character, a narrative chapter and optional world time, and an existing R3 planning node. Explicitly read the character’s reviewed A05 knowledge. Select permitted knowledge IDs, enter author assumptions, a character goal, motivation hypotheses, resource quantities and hard constraints. Enter up to eight manual routes with at most 32 events each.

Creating a run saves immutable inputs without expanding events. “推进一步” checks one next event per unfinished route. Compare observed violations, route-specific motivation hypotheses, explicitly linked character-visible A04 records and unresolved questions. Cancel stops further expansion. Completed or bounded routes may be saved, after explicit UI review, only as an original R3 planning proposal with status REVIEW. A route with violations remains visibly unverified and may be saved for human correction; it is never silently accepted.

Saved run inputs can be restored into the form, with an explicitly labelled replacement action. A new character-context read is still required. Failed requests preserve form values, require refresh, and do not automatically retry. Stale receipts hide their routes, input, provenance and old content. Reopen requires selecting current versions and creating a new run.

## Reuse and storage

- Existing ExperimentalStore File / PostgreSQL scope transactions store `story_simulation_runs`; there is no new manuscript or Canon store and no schema migration.
- R3 PlanningService remains the sole proposal/approval authority. The simulator calls its proposal-row validation inside the same scope transaction. Saving and the handoff receipt commit atomically and an already-saved route is not duplicated.
- A04 StoryGraphService and A05 CHARACTER_KNOWLEDGE_V1 are queried in the selected character/chapter/time scope. Knowledge-event and graph-relation IDs and versions are preserved. No author-omniscient graph is loaded as a fallback.
- Source content digests, chapter versions, branch, source privacy and metadata, evidence sources, reviewed knowledge/graph digest, focal-character entity digest, planning target/ancestor/entity capture and input/result hashes fence each run.
- Provenance uses existing canonical-digest/source-receipt conventions consistent with A13. This is a manual transition receipt, not a media-production manifest or a claim of cross-model/GPU numerical equality.
- Step audit history contains bounded version/status/input/result-hash receipts; immutable input and current route state are stored once, rather than copied into every history item.

## Actual deterministic behavior

Exact labels define hypothetical facts. Rules check unmet prerequisites, nondecreasing event time, required knowledge restricted to explicitly selected reviewed facts/secrets, unavailable graph links, forbidden resulting facts, negative resources and resource-cap overflow. A violating event is recorded but does not apply its state change. Final required facts are checked when a route stops. Repeated identical fact/resource/time state stops that route; remaining unexpanded events are explicitly unresolved. No probability, quality score, hidden automatic expansion, model call, timer or autonomous execution occurs.

All limits are enforced server-side: 32 steps, eight routes, 256 event examinations; 20 source chapters and 100,000 selected source characters; 200 retained simulation runs per scope. Model budget is exactly zero. Any requested model ID is refused with SIMULATOR_MODEL_NOT_CONFIGURED. Real model support remains a future authorized integration through the existing broker and author-context boundaries.

## Authority and recovery

Exact default-off flag: `story_simulator_v2`, requiring `advanced_planning_v2`, `temporal_story_graph_v2`, and `character_mind_v2` (including their transitive dependencies). V1 acceptance mode overrides all. Every simulator HTTP operation uses the captured session/branch and current domain.write authority with no-store responses. Mutations recheck current authority and source capture at their final transaction boundary. CAS serializes simultaneous step/cancel/save operations. Cancellation may stop a stale active run without disclosing its old inputs.

Simulation-origin planning proposals carry a provenance pointer. Planning list/inbox counts omit them when the validator is unavailable, their sources are stale, or the simulator/A04/A05 flags are disabled. Direct proposal/history/review/restore paths fail closed before raw values or version-conflict payloads are returned. Review/restore additionally accept a final-authority callback, preserving ordinary proposal compatibility. Explicitly approved planning content becomes the existing planning node, and never modifies manuscript text or Canon.

## Verification boundaries

Local isolated File tests cover rules, reproducibility, 8×32 maximum expansion, cycle/cancel bounds, selected knowledge privacy, source/privacy/deletion/branch invalidation, restart, concurrent CAS, rollback on final authority/source change, original planning handoff and legacy acceptance/projection fences. Mounted tests use the real application composition, both `/api` and `/api/v1`, and actual File repositories. Every backend contract is also parametrized for an actual PostgreSQL endpoint; that endpoint was not available locally and PostgreSQL was not claimed as passed.

Frontend behavior tests cover StrictMode, no automatic execution, captured session/branch headers, explicit step/cancel/save, violating-route review, failed-request input retention, source rebasing, stale-result suppression and late-scope response suppression. TypeScript and design-token checks run locally.

`frontend/tests/e2e/r4-story-simulator.spec.ts` authors J05 against real File API/React, with synthetic fixtures, route comparison, pending review, cancellation, source edits and 1366×768/1440×900/1920×1080 screenshot/overflow assertions. Local Chromium launch is prohibited by the environment; only collection was run. Real browser geometry/screenshots remain NOT_RUN until hosted CI completes. No screenshots, real PostgreSQL, model quality, GPU, Windows IME or screen-reader compatibility are claimed here.

## Remaining scope

Single focal-character viewpoint per run; authors can create separate runs for other viewpoints. Events and motivations are authored manually. The engine does not infer missing causal facts, generate open-ended branches, adjudicate motivation, infer literary quality or automatically understand resource names. Untimed graph records are visible with chapter-only time; specifying world time intentionally excludes unknown-time records under A04 rules. Historical stale inputs are hidden rather than copied into a new authorized context automatically. No automatic cleanup of the 200-run retention boundary is provided in this slice.

## Local checkpoint evidence (2026-10-05 UTC)

- Isolated backend command: `python -m pytest -q tests/test_r4_story_simulator.py tests/test_r4_story_simulator_mounted.py tests/test_r4_planning_authority.py tests/test_r3_planning.py -m file_backend_only --disable-warnings`: **42 passed**, 42 actual-PG parameters deselected, one existing dependency warning; 6.82 seconds in the final local run.
- Pinned pnpm/Vitest `src/experimental/StorySimulatorPanel.test.tsx`: **9 passed**.
- Pinned pnpm `tsc -b`: passed.
- Design token guard: passed (42 inspected production files).
- Playwright `--config playwright.r4.config.ts r4-story-simulator.spec.ts --list`: one authored browser journey collected. **Browser NOT_RUN**, not one passed test.
- Actual PostgreSQL, native Windows/IME, real model/GPU and target-user acceptance: **NOT_RUN** locally.
- Local execution receipts retained outside the repository: `r4-a01-final-file.log`, `r4-a01-final-file.xml`, `r4-a01-final-ui.log`, `r4-a01-browser-collection.log`. They contain isolated synthetic test evidence and were not added to Git.
- Shared planning compatibility was committed separately as `518b2e9`; this A01 implementation and tests are committed together. Root integration must record its final combined SHA and run the shared required gates before publishing.
