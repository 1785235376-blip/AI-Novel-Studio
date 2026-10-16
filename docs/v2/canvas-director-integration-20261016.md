# Optional canvas × Director authoring slice — 2026-10-16

## Identity and release boundary

Baseline local `69162fdc75328291f5b944de172bd8b69be29a4f` has the same tree as published PR48 `58bbaad11360330d51f49fc2bb78a955a26469f0`. Live read-only verification found PR47 Draft at `045b865e5a003cac3333462d055f22099f6368d6`, PR48 Draft at the preceding published SHA. This slice is a local development commit only; its containing Git commit provides the exact identity. No push: hosted CI cost has not been established as free. No merge, tag or release.

P0 lifecycle reproduction/repair remains platform-BLOCKED and was not attempted, edited or tested. R3-GATE remains HOLD; production Prompt Adoption POST stays disabled. No user machine, GPU, provider, model download, paid API or QingJian activity.

## Real bounded behavior

1. Open independent Studio → Graph → optional Director console. Opening alone reads original Creative capability; it performs no model or document write.
2. Use the existing CreativeCanvas fields for title, visual intent, scenes, camera/motion/duration, emotion, performance and other existing Director fields. Save explicitly through original CreativeService create/update. Update uses the original expected-version CAS. Saving does not approve anything.
3. Read the original document directory or inspect a selected `director_plan` node. Original Creative export returns the document and its measured digest. The console shows current source and selected graph pin separately.
4. Use the already existing production-node catalog/document picker to add the saved Director snapshot. Save Graph normally. The original graph stores ID/version/digest, spatial positions, connections and viewport. Reopen Graph and read the selected Director node's original source in the same workspace.
5. Edit that source explicitly. Its version advances, while the old graph pin remains unchanged and a source-change warning appears. No automatic rebinding or downstream execution. Original preflight rejects stale source use.

The console is optional/collapsible. Multiple normal Director nodes and independent other modules retain their original behavior. This is an integrated authoring/source-read slice, not completion of the professional spatial canvas or all Director coordination.

## Ownership and recovery

- No backend, queue, permission store, review owner or execution schema was added or modified. Existing Creative, Graph and Review authorities are reused. No model controls were reimplemented.
- Graph mutation/run controls lock while the Director author draft or write outcome is pending. Parent workspace supplies the original read guards and mutation semaphore.
- Reads are fenced by source-client/lifetime and selected-node generations, including A→B→A and distinct nodes with identical pins. In-flight writes stay uncertain if their lifetime changes. Invalid successful-write identity/version receipts do not mark a draft saved.
- Conflict/UNKNOWN retains author text and blocks further writes. Read the original directory/source and explicitly adopt the verified version. Alternatively, explicitly abandon local input, with a warning that the remote write may have succeeded and is not cancelled. No automatic retry or repeat create occurs.
- Unsaved author text is session-local, with the original beforeunload/navigation warning. Saved documents/graphs reopen through their owners. Browser crash/offline automatic draft recovery is not claimed.
- Existing 16 ordinary /24 media /40 edge execution budgets, spatial coordinate/zoom bounds, PUBLIC source closure, disabled mature-content placeholder and protected UI shell/tokens remain unchanged.

## Verification

Final command results are recorded in `canvas-director-integration-20261016.json`. Selected coverage is not whole-product acceptance.

- Final related frontend: 258 tests across 12 files, zero failures/skips; jsdom/mock transport, not browser screenshots. Includes mounted author→source save→exact pin→Graph save→reopen, stale version, conflict/UNKNOWN, original-directory recovery, generation fences, invalid receipt and explicit global abandonment.
- Independent final review: 23 tests across 3 actual discovered files, zero failures; overlaps the final related suite and is not additive.
- Existing File owner selection: 18 passed, 2 PostgreSQL applicability skips, 15 deselected. Actual File persistence/Director→Storyboard typed execution/reopen/stale-source tests; no actual model inference. PostgreSQL was NOT_RUN in this slice.
- PUBLIC packaging contract: 30 passed. PUBLIC source closure: 487 files, exit 0. These are offline closure checks, not actual Windows installer/Docker/wheel/sdist acceptance.
- TypeScript, production Vite build, design-token guard (52 original guarded files) and implementation/delivery-doc whitespace checks pass (the verbatim frozen TXT intentionally retains its original final blank line). Vite retains its large-chunk warning. New component has no new CSS/raw style/color; it consumes existing tokens/primitives and CreativeCanvas.
- Browser screenshots/visual acceptance remain BLOCKED/NOT_RUN due the previously established browser runtime restriction; no alternate route was attempted. Windows/GPU/live model/whole-product RC remain LOCAL_REQUIRED/NOT_RUN.

Initial failed checks are preserved separately: first new test lacked jsdom setup (5 failures before assertions); then one whitespace-normalizing test query failed (product preserved whitespace); both test premises were corrected. Default Python lacked pytest, so the first File invocation executed no product assertions; rerun used the existing test interpreter against this checkout only. A subsequent broad UI run caught a changed generic Graph navigation message; the original message was restored for graph-only drafts while the new uncertainty notice is limited to Director drafts. The existing assertion was retained. No existing failing regression/assertion was deleted or weakened.

## Remaining scope

Full CONSOLE-01..06 and Graph product requirements remain PARTIAL. Persistent canvas-only view state, real grouping/collapse integration, MiniMap/culling/1000-display-object measurement and general reviewed multi-target suggestions→tasks→results are still open. The [capability ledger](frozen-capability-ledger-20261016.md) preserves all A/B/U/Graph/Console and other FS/CORE rows with owner/mount/dependency gaps. The [new frozen anchor](frozen-product-anchor-20261016.txt) is verbatim; historical reports are untouched. The original referenced 904-line roadmap was not found/read and exhaustive reconciliation is not claimed.
