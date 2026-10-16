# Same-project cross-graph selection copy — 2026-10-16

Baseline: `98318fbe18f3927dd1a4fe8771371bf5086eb44c`. The containing local commit identifies this delivery. Frozen P1 remains PARTIAL; this delivers a bounded same-project cross-canvas flow, not cross-project transfer or arbitrary clipboard import.

## Audit and original owners

The existing IndependentStudioSession captures project/session/actor/workspace/storyline/branch and owns the Graph editor controller across graph switches. Its original scope/client/current-owner fences and guarded graph picker already exist. Graph service `create` / `save` in `app/creative/graph.py` revalidate newly added asset/planning pins, exact source state and timeline definitions through their existing owners; original target CAS remains unchanged. No authorization, lifecycle, backend, schema, queue, store, execution or budget expansion was needed or made.

The source buffer lives only in the existing editor controller. It is explicitly captured from a clean, saved, editable source graph with selected readable/current references. Its exact source graph ID/version/definition digest and deep-copied nodes/parameters remain stable if the source later changes. This is a historical authored snapshot, not a live-source authorization receipt. No foreign data or source graph is automatically fetched, and no system clipboard API/storage is used.

## Mounted flow and boundaries

1. Save the source, select nodes and explicitly capture them for same-project cross-graph copy.
2. Choose another saved graph using the original graph picker and dirty/UNKNOWN navigation guard. Capture itself does not discard drafts; unsaved source changes after capture still require the original navigation confirmation.
3. Explicitly preview on the target. Require identical project/scope/client/identity and schema version; check kinds/definition versions and internal typed connections against the target's existing catalog. Different schemas fail closed without automatic migration, pin rewriting or loading another catalog.
4. Review stable source ID/version/digest, exact reference bindings, target counts/budgets, internal edges and excluded external-edge count. Missing boundary inputs must be reconnected explicitly. Target title/camera/presentation and existing nodes remain intact. Groups, execution receipts and results are not copied.
5. Explicit paste applies all nodes/internal edges or none through the original draft change/history. IDs are fresh relative to source and target. Original node/edge/media-generator/definition-byte limits and bounded coordinate offsets remain unchanged. One undo reverses the paste; original save/CAS/reopen and source revalidation apply.

The buffer survives only graph switches inside the exact existing scope. Owner/client/identity/permission/inactive changes, a mismatched target scope or a read-only target clear it. Explicit clearing or recapture invalidates retained handlers synchronously. Target edits, undo/redo, navigation, catalog replacement and dirty/UNKNOWN transitions invalidate target previews; retained old paste callbacks cannot resurrect an edited-and-restored preview. Busy/current-owner checks are repeated at application time. The existing same-graph copy remains available for local unsaved drafts with its original semantics.

Preview/paste never invokes preflight, run creation, provider/model calls, approval or cloud transmission. Original saved source pins are preserved exactly. The preview does not grant permission to read sources, execute models or send data; the original save/execution owners remain authoritative.

## Verification

- 254 selected mocked UI/controller/pure geometry/contract tests PASS. Mounted capture → select target → preview → paste → one undo/redo → save/reopen, unchanged source graph and no dispatch; same-graph regression, owner/client/permission/scope resets, saved-only capture, dirty navigation, UNKNOWN, stale callbacks/edit-undo, schema/catalog/typed-edge incompatibility, exact bounds and atomic budget rejection.
- Three nonsecurity File checks plus 30 PUBLIC contracts PASS. Original owner persists/reopens cross-graph topology, retains the source, rejects stale target CAS and restores the target; added asset pins with an invalid source version fail atomically and exact valid pins save/reopen. No lifecycle/security mutation test was introduced or run.
- TypeScript, Vite, test discovery, original token guard, scoped color guard, diff check and 487-file PUBLIC source closure PASS. Existing large-chunk Vite warning remains. Canonical IMAGE reference inspected; no protected shell, token or CSS changes.
- Initial build caught a test-only TypeScript indexed-assignment error; corrected with the assertion unchanged. Early controller test async warnings were corrected by awaiting completed guarded navigation. Independent review identified retained-handler and live-clean-capture gaps; fixed with synchronous epochs/live-draft checks and regression tests before the final reviewed suites. Failed and superseded receipts are retained.
- Exact commands/times/exit codes/source and log hashes are in [evidence](canvas-cross-graph-copy-20261016.json). Final reviewed UI/File/build/token receipts all confirm unchanged sources during execution and match final changed-source hashes. UI tests are mocked and File tests are separate owner integration; neither is a browser-to-backend acceptance claim.

Browser/visual/native keyboard/IME/assistive technology/performance, PostgreSQL/P0/security, Windows/GPU/provider/user-machine/full RC NOT_RUN. No browser fallback, user computer, saved environment, paid provider or hosted CI used. P0 remains BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled. No push because CI cost remains unknown.

## Independent review

Separate read-only review found no remaining blocking issues in the frozen production diff. Its initial 60-test planner/controller/workspace UI check and post-fix 58-test planner/controller/geometry check passed; these overlap the 254-test delivery suite and are not added to its total. Reviewer made no tracked edits.

## Handoff

Independent parent review before further tracked feature edits. Cross-project/user/scope copy, cross-schema migration, operating-system clipboard interchange, durable copy/undo or unsaved recovery, nested subcanvases and full browser/large-display acceptance remain open. Preserve prior receipts and all denial/environment/cost boundaries; this slice does not complete the full frozen cross-canvas/project goal.
