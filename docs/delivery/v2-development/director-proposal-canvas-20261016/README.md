# Original director proposal → canvas draft loop

Local implementation on isolated `work/dot-director-integration-20261016`, following merge `79e74ad517686b57bc6f842e2d3adcb3d94cb606` and relationship-refresh correction/checkpoint `bf7f893ed49f5a199c3c403b2acce15ce4fd97ff`. Both preserved local history and Codex `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3` remain ancestors. No publication or hosted workflow was triggered.

## Functional boundary

- The optional editable graph director console explicitly opens the original saved SCREENPLAY source list, original `AIDirectorPanel` proposal queue, original proposal review and original Creative draft. The existing read-only pinned DirectorWorkspace remains available. Independent modules still do not require Director.
- The adapter uses the workspace's existing read/mutation owners. No parallel proposal store or API was added. Pending review edits, checkbox/goal changes, reads and uncertain writes feed existing graph/workspace dirty-navigation guards. Source-client/active lifetime checks reject stale adapter replies.
- Human acceptance creates the original separate DIRECTOR document in DRAFT through the existing proposal service. It does not approve production content. The graph is untouched until the user explicitly verifies the original document, chooses the exact original version/digest in the production catalog, adds the node and saves the graph.
- Accepted proposals can reopen their linked draft after a fresh mount: GET the exact original proposal, then GET its linked document, verify source ID/version/digest and current DRAFT. Changed-source failures remain with the original owner; old graph pins are never silently rebound.
- Original optional model controls retain their existing consent, local/zero-cost and source-anchor gates. This verification made no model calls. The deterministic rule-assisted checks prove workflow and persistence, not model-analysis quality. STORYBOARD input is not part of this proposal API contract.
- A small adjacent console correction distinguishes actual save activity from read activity, preserving Codex save-state semantics.

## Verified checks

- `node node_modules/typescript/bin/tsc --noEmit`: exit 0.
- `node node_modules/vite/bin/vite.js build`: exit 0; existing large-bundle warning retained.
- `node ../scripts/check_ui_design_tokens.mjs`: PASS, 52 files.
- Original File-owner verification: 94 passed, 13 PostgreSQL cases deselected. Exact selected tests and source hashes are in `../director-proposal-integration-final.json` and `.log`; `sources_changed_during_check=false`. This combines the earlier 91 original graph/director persistence cases and 3 new original proposal/draft/graph restart cases.
- The new real File graph case exercises actual saved screenplay → original proposal → edited human review → APPROVED proposal / DRAFT document → explicit graph snapshot → reconstructed stores/services → graph reference CURRENT / exact document digest / linked proposal. It also proves no graph run and unchanged screenplay. The two proposal cases additionally prove accepted-draft reopen and changed-source refusal.
- Focused mounted graph UI: 9 passed at unchanged default timeout (`proposal-graph-ui-r4.log`), including the complete mocked-transport original-panel review, explicit pin/save and fresh-mount reopen. This is component evidence, separate from the real File tests.
- Wider nonsecurity frontend: `node node_modules/vitest/vitest.mjs run src/creative src/canvasops src/director --no-cache --maxWorkers=2 --minWorkers=1 --exclude '**/StudioProductionGraphEditor.test.tsx' --exclude '**/GraphDirectorProposalReview.test.tsx'`: 117 files / 2233 passed, exit 0. The two exclusions are assigned to separate independent verification below, not hidden failures. This also closes the earlier inherited refresh failure at the wider-selection level.
- Adapter tests: 9 passed. Independent original panel/reopen verification: 38 passed in 2 files (`studio-director-reopen-independent.log`). Worker-owned related model-control/fast-receipt selection: 44 passed, overlapping counts.

Initial newly written UI test selector failures and test-spy typing failures are retained in the earlier logs. Independent graph rerun during concurrent broad UI/build load passed 17 tests and timed out the new long mounted case at the default 5000 ms, without an assertion failure. Its failed receipt is retained; the clear-load same-timeout rerun passed all 18 tests in both files, with the new full mounted case taking 3715 ms (`studio-graph-director-independent-clear-load.log`). No timeout or product assertion was weakened.

## Remaining limits and next seam

The pre-existing proposal panel can replace unsaved review fields when selecting another proposal or clearing uncertain state before reread. This slice adds the outer graph departure guard, but does not claim that all internal queue draft-loss paths are solved. A separate explicit-discard/read-then-adopt correction is assigned next; it must preserve original proposal/store ownership.

Browser/geometry was not rerun because the prior own-cloud socket EPERM block remains unresolved; historical Codex browser receipts are not acceptance of this integrated source. PostgreSQL, paid/live models, device/GPU and hosted CI were not run. The blocked lifecycle/security candidate/tests were not implemented or executed. Production `PROMPT_ADOPTION_WRITE_ENABLED = False` remains unchanged. These checks do not establish whole V2 or release acceptance. Publication is still blocked on cost/authorization and was not attempted.

Independent static review found no blocking defect in the scoped panel/reopen/graph adapter changes. Final related frontend evidence totals 2251 passing cases across 119 files in two non-overlapping selections; the historical concurrent-load timeout is still recorded. Source hashes for this implementation are in `source-sha256.json`.
