# Canvas director → original storyboard handoff — 2026-10-16

Baseline `9958852998530ffb392ca435100c48fbc0165820`; containing local commit identifies delivery. No push or hosted CI (cost unknown).

## Audit and bounded implementation

`CreativeService.derive` already creates a separate DRAFT storyboard using `DIRECTOR_NOTES`, source version/CAS, exact source digest and human-review-required provenance. `CreativeWorkspace` already exposes the operation. `AIDirectorPanel` already owns model proposal preview and explicit review; graph planning nodes already check director→storyboard source ancestry. None of those are rebuilt, changed or bypassed.

The missing seam was the mounted GraphDirectorConsole: after author/save/read it offered no explicit handoff to that owner and no return view of related Shot drafts. `GraphDirectorStoryboardHandoff` now provides:

1. Save human-authored direction through the existing console, then explicitly read its current version and digest.
2. View the exact source, count and destination. Confirm creation of a new independent storyboard draft, then invoke the original `client.derive(source, 'STORYBOARD', 'DIRECTOR_NOTES')` through the existing workspace mutation semaphore.
3. Validate the receipt's distinct identity, DRAFT status, version, shots container and exact source ancestry. Display Shot IDs, text, camera summary and duration; this is document status, not media-task completion or approval.
4. Explicitly list related storyboards and reopen their original export/version/digest/status. Older source bindings show a warning; no overwrite or graph rebind occurs. Subsequent editing/review/production remains in the existing storyboard workspace and graph-node directory.

The source remains the independently loaded console document when canvas selection changes, matching prior console authoring semantics. The selected-node pin and loaded-source preview are separately labeled. Selecting another node does not silently replace or discard author work. Explicit loading changes the source and invalidates confirmation and late reads. No automatic selection-driven read is introduced.

This is deterministic transfer of human-authored or already reviewed direction, not new model reasoning. Model reasoning remains primary in the existing proposal/review owner; no actual model/provider is called here. A full multi-target director coordination loop, diff/adoption across Prompt/media/Timeline, and target-machine model quality remain PARTIAL/LOCAL_REQUIRED.

## Failure and lifecycle behavior

Unsaved director edits, absent checked digest, unavailable storyboard capability, read-only/busy state and pending handoff disable creation. Confirmation is cleared after edits or source replacement. The original owner performs authoritative version/source checks. Rejected 4xx operations can be reconsidered explicitly; timeout/transport/server failures and invalid success receipts retain UNKNOWN and cannot retry automatically.

UNKNOWN participates in the original workspace dirty/navigation lock. Cancelling navigation preserves the pending state and blocks graph save. Listing or opening an older sibling cannot establish whether the uncertain request created another draft, so it cannot clear UNKNOWN. The original explicitly acknowledged navigation-discard flow remains available with its warning that abandoning local state does not undo a remote write. No durable transaction-reconciliation service is claimed. After reopening, the user must inspect original records before intentionally creating again.

Client/source/active A→B→A transitions invalidate pending reads. Original guarded reads/mutations handle authoritative denial; no authorization/lifecycle platform code is modified.

## Verification

Final command/receipt/source hashes are in `director-storyboard-handoff-20261016.json`.

- 254 targeted mocked UI/controller/transport/geometry tests across 10 files pass, including console save→checked-source→derive→unmount/reopen and actual IndependentStudioWorkspace UNKNOWN navigation cancellation/acknowledged discard. Fixtures are human-authored/synthetic; no model execution.
- Three explicit nonsecurity File owner tests pass: derive per-note copying, independent persistence, and new actual File derive→service restart→export→edit/re-export preserving source and DRAFT status. No PostgreSQL/P0 tests run.
- 30 PUBLIC contracts, TypeScript project build, Vite, discovery, token guard, scoped no-raw-color check, diff check and 487-file PUBLIC source closure pass. Existing bundle-size/deprecation warnings remain.
- An initial File assertion incorrectly expected internal history in public export. Corrected to assert exact public fields with history omitted and full internal get equality; failed receipt retained. Initial focused UI fixtures also corrected unsupported matcher/text expectations and avoided an unsolicited initial dirty callback. The final unchanged-source receipts supersede earlier runs.

Browser/visual/native input/accessibility/device performance, Windows/GPU/provider and full RC NOT_RUN. No browser workaround or user computer access. P0 stays platform-BLOCKED and untouched, R3-GATE HOLD, Prompt Adoption writes disabled. No new backend/schema/store/queue, budgets, protected shell/tokens, permissions or PUBLIC manifest changes. Parent review precedes further tracked feature work.
