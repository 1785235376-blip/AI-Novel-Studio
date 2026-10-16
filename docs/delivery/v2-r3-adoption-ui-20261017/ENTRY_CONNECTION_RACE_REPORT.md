# Original connection entry race: bounded repair

Base at diagnosis: `6aed517611117771d767eb275a54773b24ba0300`. The new File browser `r3-adoption-ui-browser-file-final-r2` retained two complete passes and one cold-entry failure before adoption. Its failed viewport showed the precreated local production-control novel instead of the requested collaborative scope. That failed run is not relabelled as passing.

## Cause and original owner boundary

`EntryExperience.recover` installs the user-entered candidate token through original `setCollaborationContext`, then awaits the original workspace inventory. The StudioStore intentionally receives the selected token/scope only later, when the user enters a chosen project. During this interval, the parent App's original local-novel query can retry using the new API authority while the store still appears anonymous. When that inventory resolves, the original App automatic-entry effect previously selected its first local novel (or a local saved hint), unmounting the actual connection UI. The observed unavailable feature state takes the legacy branch before the later project-choice guard.

The classic local shell has no universal recovery button: its “切换本机作品” control is itself gated by `workspaceTools`. In the failed snapshot that gate was unavailable, so adding an assumed button click to the new spec could not repair this flow. No feature flag, control project, persistent credential, permission or response was removed or fabricated to bypass it.

The repair changes only `frontend/src/App.tsx`: before any automatic local-novel selection, it reads the original `getCollaborationContext` and compares its session token plus workspace/project/storyline/branch IDs with the effect's StudioStore context. A mismatch returns without selecting a novel. This is a synchronous navigation guard using the original authority; it does not authorize the candidate token, grant scope, persist a session, perform API requests or alter the Entry/auth/API owners. Their existing successful project-entry path remains responsible for committing the selected session/scope.

## Retained causal RED/GREEN regression

New independent file: `frontend/src/AppLocalEntryAuthorityRace.test.tsx`, four collected nodes. It mounts the real App and real EntryExperience. No mock entry component or direct state injection initiates the connection. Controlled original API promises expose the relevant ordering; this is component regression evidence, not real-backend acceptance.

For each unavailable-feature, empty-hint and saved-hint case, the test:

1. Clicks the real connection disclosure, fills the real credential field and clicks the real connect button.
2. Observes that the original API context now carries the candidate token while StudioStore has not yet entered a session/project.
3. Rejects the original local-inventory request with 401, lets the real React Query retry run, and asserts the observed API-context tokens are exactly anonymous then candidate.
4. Resolves that late inventory with the preexisting control novel, asserts the connection remains mounted and no local novel was selected, then triggers an unrelated query render and checks the candidate context remains intact.
5. Resolves the workspace inventory and clicks the real workspace/project controls, requiring the original store token/scope and original bootstrap request to reflect that explicit project.

The fourth companion case confirms the original first-local-novel behavior remains available when authority has not changed.

`frontend-local-entry-authority-red-r1.log` was captured before changing App: three connection cases failed, one unchanged-authority case passed. The failed DOM is the real Novel AppShell; the actual workspace button could no longer appear after the local auto-entry unmounted Entry. `frontend-local-entry-authority-green-r1.log` records all four passing after the guard. `frontend-local-entry-authority-broader-r1.log` records six affected modules / 60 passed, including the unchanged EntryExperience, workspace-selection and App workspace-resume tests. `frontend-local-entry-authority-tsc-r1.log` retains the initial TypeScript failure in the new test only (an omitted mock receipt field and two unsupported RTL option keys); the candidate guard had no diagnostic. The new test's types were corrected without changing its expected behavior. `frontend-local-entry-authority-green-r2.log` then records four passed, and `frontend-local-entry-authority-tsc-r2.log` exited 0 with no diagnostics. Source was frozen only after this green boundary and the independent review.

Candidate raw SHA-256 at handoff:

- `frontend/src/App.tsx`: `ede1d8adf0d7ce960cc5783b288abfe023b854c7c8137520d437f078af878074`
- `frontend/src/AppLocalEntryAuthorityRace.test.tsx`: `72aaa0c9de38cce9554dfecae48f52ef2fd517ae5d73793ee23ecbbd12f2bde3`

No existing test, frozen 750/752 evidence, shared shell/token/primitive, baseline, EntryExperience, API, authorization service or production adoption False literal was edited by this repair. The source count and final suite totals must come from the next frozen runner receipts, rather than reuse the previous 2,300/4,204 totals.

## Separate limitations and next evidence

This repair addresses the connection UI being unmounted by a late local inventory. It does not change the separate existing neutral-project overview effect that can apply Image after an early user module selection. The new adoption browser spec waits for that real initial Image/IndependentStudio destination before starting its Novel/Storyboard navigation; this limits acceptance to navigation after initialization rather than claiming that earlier interaction race is fixed.

The earlier `src-final-r3` preparation run passed on the previous snapshot and remains retained. At candidate handoff, product acceptance still required subsequent real File and PostgreSQL browser workflows plus the new final source-frozen checks; RED/GREEN component results alone did not establish runtime PASS. Commits and final evidence binding are owned by the root.

## Subsequent frozen File and frontend evidence

The root committed the guard/new test as `2d96d90`, the additive readiness spec as `71d0b1c`, with final implementation HEAD `db1f687108fac6e45a577196494dfac01cc63aca`. Source remained frozen thereafter.

`runner-receipts/r3-adoption-ui-browser-file-final-r3.json` is PASS with no source drift and three real Edge viewport passes. Its 2,301-entry source map exactly matches all four final frontend runner maps, including the guard and new regression; its actual earlier capture HEAD `6aed5176` is retained unchanged. The real connection, workspace/project selection, explicit approval, UI adoption POST200 and reopened original pin succeeded in all three File viewports, with original before/after production 503 controls and no response mocks. Its launcher and decoded receipts remain under `r3-adoption-ui-browser-file-final-r3/`.

Final frontend `src-final-r4` records 4,208 passed / 6 skipped / 390 files. Original build, seven canonical visual/geometry checks and 52-file token guard final-r3 all pass at the same 2,301-source snapshot. `frontend-verification.json` binds raw receipt/log hashes; `FINAL_FRONTEND_VISUAL_REVIEW.md` records the six actually reopened final-r3 File images and the retained visual/model limits.

## Final PostgreSQL confirmation

After the original security owner reported FINAL READY/ALL_STOPPED, [the final PostgreSQL browser runner](runner-receipts/r3-adoption-ui-browser-pg-final-r3.json) independently reads PASS/exit 0, actual HEAD `db1f6871`, no drift and the identical 2,301-source map. Three real Edge viewport workflows passed in 333.81 seconds, using fresh PostgreSQL workspace/document database OID 27943 and the original File AssetLibraryService. This is actual runtime evidence after the guard, not a promotion of mocked component tests into product PASS.

The real token connection, authorized workspace/project selection, explicit source approval, adoption POST200, original main-frame synchronization, same-request replay and whole-page reopen all completed. Each original decoded receipt retains source r1 and target v1 → committed/reopened v2; advancing the source family does not repin history. The reviewer actually opened all nine new PG checkbox/commit/reopened images across the three viewports, recorded in `FINAL_FRONTEND_VISUAL_REVIEW.md`. The [launcher](r3-adoption-ui-browser-pg-final-r3/launcher.json) retains ordinary before/after production 503 controls, literal False, no development sessions or response mocks and stopped backend/Vite fields; the security owner separately confirmed PostgreSQL wrapper cleanup, `pg_ctl` exit 3 and no remaining owned processes/listeners.

The isolated acceptance child is the only enabled adoption process. This does not enable production adoption, instrument a zero-model-call count, verify GPU/model generation, resolve all historical upstream dependencies or fix the separate initial-overview module-selection race. Old File/PG failures, component RED and TypeScript failure receipts remain untouched. The final scope is the frozen original-owner connection and isolated adoption closure, with those explicit limits.
