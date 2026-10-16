# A04 semantic graph evidence review

Baseline: local `7b241bebdf4385ab200e6e01f3de6268e87d2a73`. Audit before implementation.

Existing original owners: `app/experimental/story_graph.py`, `story_graph_api.py`, `frontend/src/experimental/StoryGraphPanel.tsx`, mounted by ExperimentalWorkbench. Relation/concept/knowledge records already support creation, CAS edits, explicit review, history and affected-subgraph recompute. Author and character queries already filter chapter/scene/world time/calendar. Character beliefs are separate from approved world facts; projections intentionally omit quotes and hidden endpoints. Production GraphCanvas is a different execution graph and is untouched.

Confirmed gap: relation-query evidence only opens a chapter and displays versions. It does not inspect the exact original semantic record or source digests, nor hand that evidence to the existing editable candidate form. Planned bounded slice: explicit author-only original GET, exact record/version/source-map checks, recorded quotation inspection and original edit/copy handoff, with unsaved form preservation. Character queries must never acquire author record reads. No new model, graph owner, queue, crawler, permissions, Canon merge or backend/lifecycle change.

Limits: current chapter navigation is not historical replay; source maps are recorded snapshots, not independently rehashed current text. Query results are filtered approved visible relations, not a complete project inventory or inferred causality. Full scale/browser/literary quality remains unverified. P0 BLOCKED, R3-GATE HOLD, Prompt Adoption disabled. No browser workaround, user computer, GPU/provider, push or unknown-cost CI.

## Implemented bounded workflow

1. In the existing author time query, explicitly choose “核对原关系证据”. Only this action GETs the original encoded record ID. Character mode does not mount this inspector or expose this action.
2. The inspector compares exact record ID/version/chapter and the complete recorded source version/digest map. Missing, stale, changed, malformed or unavailable records withhold the editable target. Current service reads do not establish historical manuscript replay or independently recomputed text hashes.
3. It shows original layer, bounded source pins and original authored quotation offsets. Approved relations can only be copied into the original pending-record form; other supported records use existing CAS edits. Human save/review remains separate; no automatic fact promotion occurs.
4. Dirty or saving original forms block loading another target, refresh, original record actions, chapter departure and author→character switching. Explicit cancel resets the original form. The inspector can be read without discarding typed inputs. Scope replacement aborts/ignores pending source reads. The candidate load is single-use and unmounted/blocked retained callbacks are fenced.

This is not general application-wide draft persistence/navigation protection. Switching through unrelated outer workspace controls remains the existing App behavior. Crash recovery, complete impact inventory, semantic inference/large-graph reliability and actual native accessibility/browser acceptance remain open.

## Verification

Final indexed commands, exit codes, exact source/log hashes and isolated profiles are in `semantic-graph-evidence-review-20261016.json`.

- 45 selected mocked React/UI tests pass: exact source handoff and explicit candidate save, dirty preservation, malformed/missing/stale/denied source, late owner replacement, existing temporal/viewpoint and workbench navigation contracts, PUBLIC placeholder.
- Three nonsecurity original File cases pass: durable original review/reopen with no manuscript writes; unknown world time/flashback/valid intervals; CAS edits/history and affected-only recompute. These are existing owner tests, not a new HTTP or PG authorization proof.
- 30 PUBLIC package tests, forced TypeScript/Vite build, discovery, global/scoped token checks, diff whitespace and 487-file PUBLIC source closure pass.
- Exploratory pnpm invocation failed because installed pnpm 11.25.0 differs from the pinned 10.6.5; no dependency change was made. Existing installed test binaries were used directly. An initial JSX closing-brace error was caught and fixed before passing tests. Failed logs remain alongside final receipts.
- Browser/visual/native IME/HTTP integration, PG/P0, user-machine/Windows/GPU/provider/literary quality/full RC: NOT_RUN. No push or hosted CI; unknown-cost restriction preserved. P0 BLOCKED, R3-GATE HOLD, production Prompt Adoption disabled.

Local containing commit is the deliverable; independent parent review is required before further tracked feature edits. A04 remains PARTIAL.

Independent review corrections: query changes/ABA/requery and original directory reload invalidate inspection; requery hides prior result buttons while pending. Runtime receipt/record validation precedes GET/handoff, including explicit freshness, source-pinned quotes, known endpoint/relation kinds and original temporal/event form bounds. Regression tests cover these changes; earlier passing receipts are superseded by final unchanged-source checks.
