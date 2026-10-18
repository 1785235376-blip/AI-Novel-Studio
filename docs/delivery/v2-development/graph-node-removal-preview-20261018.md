# Studio Graph node-removal structural preview

## Scope and behavior

Implemented one shared removal preview for the GraphCanvas toolbar, Delete/Backspace shortcuts, and the original node inspector. Opening a preview makes no draft change. Applying requires a separate acknowledgement and explicit button press.

The preview identifies the exact removable nodes, incident connections, protected saved references retained, surviving reachable downstream nodes, new and remaining required-input gaps, unaffected retained nodes, and changed/removed visual groups. It explains that this is structural analysis only and does not infer model semantics or cost.

The helper reuses `graphReachableNodes` and `graphMissingInputs` without changing their shared implementation. Actual draft removal uses the existing `removeGraphNodes`, preserving its empty-group cleanup and orphan-group promotion. The original controller still owns editing, one-step history, explicit save/CAS, execution and source protections. There are no automatic saves, runs, external requests, asset deletions or changes to backend ownership.

## Safety and interruptions

- Exact versioned catalog data is required; missing nodes, unknown definitions/versions and protected-only selections fail closed.
- Canvas receives the controller's versioned catalog explicitly through `removalDefinitions`; geometry-only descriptors are not treated as authoritative catalog data.
- Candidate and consent are fenced to draft identity, owner/interaction scope, original record, target/whole selection, protected IDs, catalog contents, permission/busy/form state and the live current-scope check.
- Production entry points also reuse the existing controller verification callback (`isPlanningForkCurrent`) for its live draft/base refs and selection/navigation epochs. This rejects edits or selection changes even in the same synchronous turn before React rerenders.
- At the root's request, the adjacent node enable-state and connection-disconnect controls receive that same stronger live verifier from the view. Their shared helpers and control implementations remain unchanged.
- Apply consumes its candidate before calling the original mutation callback. Repeated or retained callbacks, revoked consent, cancellation, unmount, stale preview replacement and owner/selection/permission round trips cannot apply old removal intent.
- Inline preview receives focus, prevents Delete/arrow events from editing the canvas, and supports Escape/cancel with focus restoration. This is an inline review surface, not a new modal or workflow engine.

## Changed implementation and test paths

- `frontend/src/creative/GraphCanvas.tsx`
- `frontend/src/creative/studioGraphEditorView.tsx`
- `frontend/src/creative/GraphNodeRemovalControl.tsx` (new shared hook, preview and inspector trigger)
- `frontend/src/creative/graphNodeRemovalImpact.ts` (new structural helper)
- `frontend/src/creative/GraphNodeRemovalControl.additive.test.tsx` (new safety/integration coverage)
- `frontend/src/creative/GraphCanvas.test.tsx` (existing deletion assertions retained after explicit consent)
- `frontend/src/creative/IndependentStudioGraphWorkspace.test.tsx` (existing inspector removal flow now confirms)
- `frontend/src/creative/IndependentStudioGraphWorkspace.presentation.additive.test.tsx` (existing group cleanup/removal flows now confirm)

No shared design-system primitives, shell, tokens, CSS, graph-state helpers, execution engine or backend contracts were modified. Existing tests were adjusted narrowly to prove no removal before consent and preserve their assertions afterward.

## Verification evidence

- PASS: isolated focused debug run `graph-node-removal-debug-20261018-1534.json` / `.log`: 67 tests across the initial 42-test removal suite and the 25-test GraphCanvas suite. Its source snapshot was stable during the run.
- PASS: isolated integration debug run `graph-node-removal-integration-debug-20261018-1535.json` / `.log`: 71 tests across the final 44-test removal suite and the existing independent-workspace suites (9 and 18). The subsequent two-line strengthening of adjacent node-state/disconnect live-verifier props is reserved for root's final combined check.
- Final combined TypeScript, production Vite build and broader regression verification are coordinated by the root against both active slices after sources are stable. Focused receipts are not represented as a full frontend/backend pass.
- Browser visual/geometry acceptance: **NOT_RUN**. The available actual-browser route was already verified unavailable for this session. No browser package was downloaded and no alternate route was used to bypass that limitation. No visual baselines were updated.

## Remaining validation limits

Real-browser inspection of focus, long preview text and 1366/1440/1920 layout remains outstanding. DOM-level focus/keyboard safety is tested; it is not evidence of browser geometry. Reachability and required-port checks are advisory and do not replace the original save/run validation or authorization.

No Git commit or push was made by this worker. Root owns final combined verification, commits and archive receipts.
