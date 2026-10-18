# Layered planning: original-owner local model bridge

Date: 2026-10-18. Status: **PARTIAL**. This slice connects the mounted layered
planning editor to existing local model admission and original proposal review.
It is not real-model quality, Windows/GPU, or browser visual acceptance.

## Source gap and bounded implementation

The original `PlanningService.generate` accepts only the explicitly named
`mock-structured-planner`; the mounted editor previously exposed only its Mock
pair. A separate `AIPlanningService` already has structured PLOT and evidence
validation, but its standalone threaded runtime does not carry this bridge's
original source/branch/admission authority. The bridge reuses that validator,
not that execution path.

The new `LayeredPlanningModelCoordinator` is a narrow adapter over the existing
`NarrativeJudgeModelCoordinator` admission protocol, `AuthorPreparer`,
`ModelRouter`/`ModelBroker`, and `JobManager`. The original `planning_proposals`
collection owns both non-reviewable `MODEL_REQUEST` records and saved REVIEW
proposals. No second queue, registry, planner runtime, or provider transport was
introduced. `jsonschema` was already a production dependency.

Supported path:

1. Select a saved original planning node with 1–3 nonempty linked chapters.
   Saved node/ancestor/linked-entity/source versions are captured; unsaved editor
   fields are not silently substituted.
2. Save a request without sending. Explicitly select an existing registered,
   verified local TEXT route with confirmed license and known zero cost.
3. Inspect the exact original AuthorPreparer request, source ranges, route,
   budget and limits. A separate reviewed preview digest authorizes admission.
4. One original Job and Broker reservation execute the selected route. Results
   pass the advertised closed PLOT schema, original AIPlanning validation, and
   exact preview-visible source/version/digest/quote checks.
5. Explicitly save a reviewed candidate into an original REVIEW proposal.
   Stable identity makes repeated saves idempotent. Existing human approval,
   rejection, CAS, history/reopen/restore remain the only planning write owner.

Only local scope is supported; collaboration branches, cloud routes, paid or
unknown prices, source-free project planning and automatic fallback are refused.
This deliberately does not reuse broader cloud/budget semantics without a
separate approved design. Inputs are bounded to the first 16000 Unicode
characters of each linked chapter and 18000 characters for the combined model
instruction, with no silent total-input truncation. Output is at most 32768 bytes
and the inherited execution deadline is 120 seconds.

Manual editing and deterministic Mock pairs remain usable. The shipped Mock
provider has an explicitly labelled synthetic protocol fixture for this bridge;
it is never a real-route fallback or literary-quality result.

## Authority, recovery and review boundaries

- The new mounted API checks the existing local host session and
  `advanced_planning_v2`, `model_broker_v2`, and
  `author_context_inspector_v2` flags at admission and existing recheck points.
- Original node, ancestor, chapter, linked-entity, template, actor and scope
  fences are retained. Stale request previews/candidates are withheld.
- `MODEL_REQUEST` records cannot enter original proposal review, history,
  restore, comparison or review-inbox projection as reviewable proposals.
- `layered_planning_model` generation origin is registered with its original
  feature gates and blocked from whole-manuscript acceptance. Task/recovery
  navigation points back to the exact original planning model Job.
- Cancellation discards late output; interrupted/unknown admission and restart
  do not authorize automatic replay. Unknown reservations stay unknown.
- Candidates are recorded only after a settled known-zero successful receipt;
  Save checks the exact candidates digest and original source/target baseline.
- No model result automatically changes manuscript, Canon or planning nodes.
  Candidate Save creates only a REVIEW proposal; original human approval changes
  only the original planning node.
- The mounted UI preserves editor drafts, uses lazy model reads, requires
  separate preview and candidate review, and retains saved-proposal navigation
  after the request becomes stale without exposing stale candidate evidence.

The original AIPlanning `excerpt_only=True` already enforced the 16000 boundary.
This slice adds explicit captured-range/digest binding. The additional schema
gap found during review was enforcement of the narrower advertised PLOT schema;
fields from the broader Workbench schema are now rejected at parse time.

## Changed owners

New backend: `app/experimental/planning_model.py`,
`app/experimental/planning_model_api.py`.

Scoped existing owner hooks: `app/experimental/planning.py`,
`app/experimental/api.py`, `app/experimental/ux.py`, `app/providers.py`, and
the origin/whole-acceptance fence in `app/jobs.py`. A separate Canon repair
owns subsequent unrelated `jobs.py` changes.

New mounted UI/test: `frontend/src/experimental/PlanningModelPanel.tsx` and
`PlanningModelPanel.test.tsx`; scoped mounting/navigation edits in
`PlanningPanel.tsx` and `ExperimentalWorkbench.tsx`.

Mounted backend tests: `tests/test_v2_layered_planning_model.py`. Root owns final
PUBLIC manifest/catalog, combined builds, PostgreSQL coordination and packaging.

## Verification and remaining acceptance

- Existing planning/AIPlanning regression: **40 passed, 13 PG skipped**.
  Receipt: `layered-planning-legacy-debug1-20261018.json`.
- Existing Judge/Broker admission regression: **43 passed, 36 PG skipped**.
  Receipt: `layered-planning-admission-debug1-20261018.json`.
- Focused UI: **30/30 passed** across the new model panel and unchanged
  recovery/handoff/workbench suites; token guard passed (52 files). Typecheck
  passed before the final two test additions; root owns combined final TS/Vite.
- Expanded mounted tests cover both API prefixes, exact preview/source slices,
  closed schema, original Job/Broker/navigation, explicit Save/reopen/CAS,
  permissions, stale versions, route/budget changes, cancellation and UNKNOWN.
  Final slice File run: **64 passed, 64 PG skipped**, 31.05 seconds; receipt
  `layered-planning-file-debug4-20261018.json` reports
  `sources_changed_during_check: false`. Final whole-wave File/PostgreSQL
  receipts are owned by coordinated verification. Earlier debug receipts can
  show concurrent source changes and do not establish a frozen package hash.
- A disabled-model negative caught an uncaught `ModelRuntimeError` after
  preview. It already prevented send; the new bridge now maps it to a bounded
  domain error rather than leaking a runtime exception.
- **Browser geometry/visual acceptance: NOT_RUN/BLOCKED.** Root verified the
  bundled browser is absent and the installed browser is sandbox-blocked. No
  alternate browser/download/bypass was attempted.
- **Real local-model execution/quality and Windows/GPU: NOT_RUN / LOCAL_REQUIRED.**
  Tests use only the shipped synthetic adapter or bounded fixture streams.
  No real model/API calls, paid quota, dependencies, user-machine access,
  commits, pushes, tags or release were performed by this slice.
