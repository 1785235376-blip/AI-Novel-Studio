# Exact simulator → original planning review handoff

Baseline: local `92cc5184f900631c8fae71373f0373e8ebf76efe`. The containing commit identifies this delivery. Frozen A01/A05 goals remain PARTIAL; this is a bounded original-owner workflow closure, not model-quality acceptance.

## Source audit and exact gap

- `StorySimulatorService.save` already saves one original R3 REVIEW proposal, persistently links the route through `saved_proposal_id`, and stores run/route/input/result provenance. Original `PlanningService` GET/review/history validates source, target and simulation freshness. No new save, approval, queue, schema, authorization or persistence owner is needed.
- The existing simulator save success button supplied an ID but no target authority. App/Workbench discarded that ID for PlanningPanel; the panel displayed its default node's proposals instead. Persisted routes displayed their proposal IDs without a reopen action. A user reopening a run could not reliably reach the actual original review.
- A05 already has reviewed StoryGraph mind projection → explicit character/scene selection → original author-context generation binding (`character_author_context.py`, `StoryGraphPanel`, `App`, `AiWritingPanel`). Known facts, beliefs and false beliefs are separate; unsupported enrichment is excluded. This implementation was inspected and not duplicated. Broader cross-chapter writing constraints and actual model/POV/literary quality remain unverified.

## Delivered behavior

1. Newly saved and previously persisted simulator routes explicitly navigate with `planning_proposal` authority. Original App/Workbench now retain exact proposal/run references even when the unrelated Workspace Tools feature is off. Each destination's own feature still gates access.
2. PlanningPanel reads the exact proposal through the existing GET, independently of the default node. Missing, denied or wrong-ID responses never fall back to a neighboring proposal. The original review card, CAS approval/rejection/archive/reopen and history owner are reused. No approval or manuscript change happens on navigation.
3. The card exposes original graph/node/target version, chapter source versions/digests, simulation route, and input/result digests. Its explicit source button opens the original run. A disabled simulator feature disables that button with an explanation.
4. Simulator opens that exact run through its original GET, shows persisted source digests and saved input constraints separately from the editable form, and can reopen the original saved proposal after remount. Knowledge IDs and context digest are not reconstructed into missing evidence text. Author hypotheses, motives and character beliefs remain explicitly distinct from facts.
5. Exact target transitions clear route choice, review consent and temporary save receipts. Client/target/chapter epochs, original abort behavior and identity checks prevent old responses from reviving after A → B → A. An explicit new run or model-candidate selection leaves the old target. A failed reread hides prior exact review evidence; an explicit reread can recover.
6. Incoming exact review temporarily hides but preserves the currently mounted planning node draft. Returning to the node list restores it unchanged. This is session-local preservation, not crash-proof or cross-module unsaved-draft recovery.

## Verification and limits

Final command/exit/source/log receipts: `simulator-planning-handoff-20261016.json`.

- 69 selected mocked UI checks across eight files: original save/review navigation, restored route reopening, exact target outside default graph/node, no accidental writes, explicit original CAS approval/history, stale/denied/mismatched targets, failed reread recovery, target/owner ABA, unchanged editor drafts, same-route-ID consent and temporary receipt reset, disabled feature navigation, App routing without Workspace Tools, and existing Character Mind and PUBLIC UI checks.
- Four nonsecurity File owner tests and 30 PUBLIC tests: deterministic run restart, original REVIEW/approval without chapter/Canon writes, existing planning restart, and a new durable simulator save → reconstruct original services → exact proposal/run/digest/constraint reads → original review/history loop. The latter compares the shared chapter version/digest projection, not equality of different owners' richer source envelopes.
- Forced TypeScript/Vite build, test discovery, shared token guard, scoped raw-color guard, diff check and 487-file PUBLIC source closure. Existing Vite chunk-size and Starlette deprecation warnings remain.
- Retained intermediate failures: old navigation expectation lacked the now-required authority; a test clicked while asynchronous original graph hydration temporarily disabled the button; the new File test initially compared unequal source-envelope shapes rather than their exact shared version/digest identities. Original assertions were not weakened; corrected new fixtures and final results are recorded. Independent review found the target-consent carryover, which was fixed and regressed.

Important original-owner limit: after a proposal is approved, the target node changes. The original simulator run GET can therefore become STALE and redact old routes/input. This slice preserves that fail-closed behavior and does not claim post-approval replay of the old run's full evidence. The original proposal/history remains the review record. No historical-context privilege or bypass was invented.

Actual browser/native input/visual/accessibility/performance, HTTP integration, PostgreSQL/P0/security lifecycle, Windows/GPU/user-machine/provider/full RC: NOT_RUN. Real model/literary/POV quality: NOT_RUN. Only mocked model-protocol UI tests ran; no provider or model was invoked. P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled. No new permissions, grants, backend/lifecycle changes or PUBLIC inclusion changes. No push or hosted CI because costs remain unknown.

Next: independent parent review of the containing commit before any further tracked feature edits. Durable post-approval evidence replay would require an explicit original-owner contract; do not weaken current freshness gates to manufacture it. Broader A01/A05 quality and cross-chapter authoring integration remain open.
