# App navigation intent — implementation and regression evidence

Base: `87408f6881fd2dc2f22038c36643ed2e0a743f33`. This report concerns the original App module navigation owner; real File/PostgreSQL browser results are separate evidence.

## Change and boundaries

`frontend/src/App.tsx` retains its original `studioModule` state. One `navigateStudioModule` records an explicit choice synchronously, including clicking the already selected NOVEL tab. The original AppShell, ModuleWorkspaceRoutes, IndependentStudioWorkspace, CreativeWorkspace, authorized interop routes, global search, and “打开 V2 创作工作台” entry use this handler. Automatic overview defaults, local saved hints, and project creation keep the original setter and do not create user intent.

The existing entry ref now binds intent and one-time default initialization to session, project, actor/workspace and the four scope IDs. Chapter changes do not replace that entry. The original store subscription observes identity transitions synchronously, so even batched A → B → A retires callbacks from the first A. First unknown → resolved actor within the same connection preserves this entry, intent and legitimate callbacks; its request epoch still changes to refresh the original captured transport. A known actor replacement or a changed base connection creates a new entry.

The overview query retains `['independent-project', namespace, projectId]` as its invalidation prefix. Its suffix contains only the opaque React instance and request epoch; raw bearer tokens are not added to query keys. Exact project decoding remains in the original Studio client. Wrong-project reads cannot consume initialization. A refetch cannot reapply the default after initialization or override explicit navigation.

The original requested project/asset state is fenced by its entry object. A previous project's or branch's saved asset hint is not passed into a new IndependentStudio owner when the new user choice skips automatic defaulting. A current-entry hint remains available during its normal module navigation. The original return-to-project-list action clears this origin and retires the entry; reopening starts a new default lifetime.

The previous local connection-authority guard remains unchanged. No new global store, router, transport, permission owner, API, adoption write path or production flag is introduced. Only App product source and one independent mounted regression file change. Original tests, adoption components, shell/primitives, design tokens, canonical references and baselines are not edited by this slice.

## Final candidate source

| Path | Raw SHA256 |
| --- | --- |
| `frontend/src/App.tsx` | `ab211c5c61014ab617fcd3e320a03cfd7b92467f419ce9bf45e0ae5b78200bf3` |
| `frontend/src/AppModuleNavigationIntent.test.tsx` | `99bd7e33b7595eae8638cb8cc9ae7994d55380fd8a59106b648731c433f5e710` |

App diff against the round base is 51 added / 20 removed lines. New regression collection: 34 nodes. The final round source freeze is [source-freeze-final-r1.json](source-freeze-final-r1.json), containing 2305 paths and canonical map SHA256 `73cc97473c56824881b0274d19783152d161e7547680c0401009225058bf78da`.

## Causal regression evidence

The new tests mount real App, ModuleSwitcher and workspace components. Call-through spies capture original component/interop callback boundaries without replacing them. Controlled API promises expose ordering. A mounted `useIsFetching` probe waits for actual React Query notifications before checking the selected tab; cache changes alone are not treated as rendered navigation. These are regression tests, not real backend/browser acceptance.

| Check | Observed result |
| --- | --- |
| Original App + initial stable RED, `navigation-intent-mounted-red-r3` | 10 failed / 10 passed: same-value NOVEL, rapid switching, Creative module choice, old callback, actor boundaries and delayed overview reproduce defects |
| First candidate, `navigation-intent-mounted-green-r1` | 20 passed |
| Actor hydration / batched ABA RED, `navigation-intent-mounted-hydration-red-r2` | 2 failed / 23 passed |
| Hydration / ABA corrected, `navigation-intent-mounted-green-r2` | 25 passed |
| Requested target RED, `navigation-intent-mounted-target-red-r1` | 2 failed / 26 passed; project case directly exposes the old asset ID; branch case is retained as a multiple-request timing diagnostic |
| Requested target corrected, `navigation-intent-mounted-green-r3` | 28 passed |
| Explicit Creative entry RED, `navigation-intent-mounted-creative-entry-red-r2` | 1 failed / 33 passed; opening the original workbench alone is overridden by IMAGE |
| Final related regression, `navigation-intent-related-r4` | 128 passed across 7 files, including all 34 new nodes and unchanged original local-entry, resume, shell, Creative, Independent and interop tests |
| Final candidate type check, `navigation-intent-tsc-r4` | PASS |

Original runner receipts/logs are under `../v2-development/<label>.json` and `.log`; Vitest JSON is retained in this folder as `<label>.vitest.json`. Earlier RED setup revisions and every failed diagnostic remain present. In particular, `creative-entry-red-r1` used a nonexistent button label and is a test setup failure, superseded by the causal `red-r2`; `tsc-r1` caught an unsupported `getByRole` option in the new test, corrected only in that new file. No old assertion was changed or skipped.

Coverage includes original default IMAGE, local VIDEO/asset hint, same-value NOVEL, fast IMAGE → VIDEO → NOVEL, workbench entry and module navigation, authorized interop project/features, chapter continuity, refresh-equivalent remount, StrictMode, session/actor/workspace/project/storyline/branch isolation, batched and rendered ABA, rejected wrong-project responses, transport renewal, original project-list reopen, and stale/current asset origins. The before-actor user-click window is specifically proven by the mounted bootstrap-promise test; it must not be inferred from a browser flow that begins after bootstrap.

## Design and final verification

Loaded `.codex/skills/ai-novel-studio-ui/SKILL.md`, `docs/ui/design_system.md`, `docs/ui/protected_ui_surfaces.md`, and the layout/component/visual short references; inspected `docs/ui/reference/image_workspace.png`. No visual-system modification is requested. GraphFlow `gf_read` was used before code exploration. Legacy context/plan/index tools are not exposed in this session; a later changed-source skeleton read stalled and was terminated, so no graph reindex completion is claimed.

Final frozen verification is complete. [frontend-verification.json](frontend-verification.json) records each original receipt SHA and actual captured HEAD (`5f87b9dfa550cd870975cd5a24b89ef05a5d3236`). All four before/after maps equal the exact frozen 2305-path map; `sources_changed_during_check` is false and each saved log's SHA was independently recomputed.

| Final check | Result | Original receipt |
| --- | --- | --- |
| All `frontend/src`, maximum 4 workers, actual frontend cwd | 4242 passed / 6 retained skips / 0 failed, 391 files | [src](../v2-development/nav-intent-src-final-r1.json), [Vitest JSON](frontend-src-final-r1.json) |
| TypeScript + Vite build | PASS | [build](../v2-development/nav-intent-build-final-r1.json) |
| Original bundled Chromium visual/geometry suite | 7 passed: NOVEL/IMAGE/VIDEO baseline comparisons and four geometry sizes | [visual](../v2-development/nav-intent-visual-final-r1.json) |
| Original UI token guard | PASS, 52 files | [tokens](../v2-development/nav-intent-tokens-final-r1.json) |

The build's existing chunk-size notice remains in its raw log. No baseline was regenerated, no test was skipped to pass this slice, and no test was repeated without a source/setup reason. Canonical output is isolated under `visual-results-final-r1`. The Playwright-owned 5174 web server exited normally; a later read-only listener query found no listener on that port.

Runtime acceptance is complete and is separate from these checks: File **6 passed / 39.595 seconds**; fresh PostgreSQL **6 passed / 514.757 seconds**, with no skips, unexpected results or flaky cases in either result. The PG run uses PostgreSQL 16.15, original fresh database `v2_navigation_intent_browser_20261017_final_r1`, OID `28822`, and the original 20-migration wrapper. Its workspace/document persistence is PostgreSQL; the asset owner remains the original File `AssetLibraryService`.

The real browser runner uses ordinary `uvicorn app.main:app` and original `LocalSessionBootstrap`. No adoption gate override, production environment toggle, development session or response mock is used. Production adoption is False before/after, and this navigation suite makes no adoption POST. The schedule holds client GET dispatch and then uses original `route.continue()`; it does not claim that the server already received the request while held.

All File/PG before/after 2305-source maps equal the same freeze, with no drift. Captured receipt HEADs are retained honestly: File `87408f6`, frontend checks `5f87b9d`, PG `7893cd0`; later commits stage identical frozen bytes. [source-git-binding-final.json](source-git-binding-final.json) and [manifest-source-git-binding-final.json](manifest-source-git-binding-final.json) bind the final 2305 / 2367 source sets to Git. These are byte-binding claims, not a claim that every earlier process was launched after the final commit.

The [final visual review](FINAL_FRONTEND_VISUAL_REVIEW.md) covers 15 final-state screenshots per backend and the six evidence attachments per backend. [visual-dom-review-file.json](visual-dom-review-file.json), [visual-dom-review-pg.json](visual-dom-review-pg.json) and [visual-image-review.json](visual-image-review.json) retain the independent review. Per backend, 21 delivered original HTTP response bodies have matching raw SHA values and six scope-owned requests are canceled; cancellation is not presented as old callback delivery. The before-actor click window and parent ABA remain specifically mounted-regression evidence, as described above.

The original wrapper and launchers report cleanup complete; [final-runtime-cleanup.json](final-runtime-cleanup.json) records `pg_ctl` exit 3, no listeners and no owned workers. No product or test source was changed after freeze, and no acceptance test was rerun after its passing terminal result. `model_execution=NOT_REQUESTED` and `model_counter=NOT_INSTRUMENTED` remain the exact model boundary. Production adoption remains closed; this is not a whole V2 release or a model/GPU generation claim.
