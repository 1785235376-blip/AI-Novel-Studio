# Final navigation intent frontend and visual review

**PASS for this bounded navigation slice.** Reviewed against the round base `87408f6881fd2dc2f22038c36643ed2e0a743f33`, final implementation source `7893cd027433e165b4035eac0f744c27cb93310a`, and frozen 2305-source map SHA256 `73cc97473c56824881b0274d19783152d161e7547680c0401009225058bf78da`. No blocking navigation regression was found in the reviewed states. This is not a full V2 release claim.

## Verification and preservation

| Evidence | Actual result |
| --- | --- |
| Final complete `frontend/src` | 4242 passed, 6 retained skips, 0 failed; 391 files |
| Build | TypeScript + Vite PASS |
| Original canonical visual/geometry tests | 7 passed; bundled Chromium, no baseline refresh |
| Original token guard | PASS, 52 files |
| Ordinary real File Edge browser | 6 passed, 39.595 seconds |
| Ordinary real PostgreSQL Edge browser | 6 passed, 514.757 seconds; fresh OID 28822, original 20 migrations |

[frontend-verification.json](frontend-verification.json) records the four frontend receipt/log hashes. Each before/after source dictionary equals the full frozen 2305-path map and reports no drift. Original captured receipt HEADs remain unchanged: File `87408f6`, frontend `5f87b9d`, PostgreSQL `7893cd0`. Their identical runtime bytes are bound to final Git by the [2305-source](source-git-binding-final.json) and [2367-source](manifest-source-git-binding-final.json) proofs; receipt metadata has not been rewritten to simulate a later launch.

App is the authorized changed owner: 51 added / 20 removed lines and 34 new independent mounted regression nodes. The original local connection guard remains preserved; there is no claim that App itself is unchanged. [frontend-preservation-review.json](frontend-preservation-review.json) independently recomputes the 61 original adoption baseline sources and compares 14 protected visual paths byte-for-byte with the base Git blobs, including AppShell, tokens, original visual config/spec/baselines and DS documents. The original protected 750 test/gate and 752 artifact boundary is recorded by the round's independent protection audit; preserving those bytes does not establish new V1 runtime acceptance.

## Actual screenshot and DOM inspection

Inspected **30 final-state PNGs**: five phases × three viewports × File/PostgreSQL. The [image review index](visual-image-review.json) lists exact paths, dimensions and raw SHA values. Held-state images are also retained by the browser runner but are not counted in these 30 inspected final-state images.

| Viewport | File final states inspected | PostgreSQL final states inspected |
| --- | --- | --- |
| 1366 × 768 | cold, reload, no-intent default, new project, new branch | same five phases |
| 1440 × 900 | same five phases | same five phases |
| 1920 × 1080 | same five phases | same five phases |

The corresponding original run folders are [File](nav-intent-browser-file-final-r1/test-results) and [PostgreSQL](nav-intent-browser-pg-final-r1/test-results). Each final-state filename is one of:

- `cold-late-overview-preserved-real-workbench.png`
- `reload-late-overview-preserved-real-workbench.png`
- `no-intent-default-image-positive-control.png`
- `cross-project-new-scope-last-novel-preserved.png`
- `cross-branch-new-scope-last-novel-preserved.png`

In cold and reload views, the original top-level NOVEL tab stays selected after the delayed neutral overview, the original Storyboard stage and document remain visible, and the document title/version agree across the sidebar, canvas and inspector. New project views show the new project's board; new branch views show the other branch's board and scope. The independent no-click page selects IMAGE and shows the existing IndependentStudio/Prompt workspace, rather than inheriting another page's explicit NOVEL intent.

The original header, context bar, sidebars, inspector and status bar remain aligned in all inspected viewports. At 1366 the canvas and inspector use their existing internal scroll regions; some lower document fields are outside the visible area. Long scope labels use existing ellipsis. The screenshots prove the visible module, document identity/version and layout; they do not display every document/body field or full breadcrumb suffix. Exact unchanged document fields are supported by original owner readbacks and browser assertions, not inferred from cropped pixels. The neutral test projects have no original manuscript chapters, so the status text about opening a chapter is not treated as proof of manuscript-editor readiness. The 1920 inspector's local AI state remains “尚未检测”; no runtime/model availability is inferred from it.

The PG 1920 cross-branch image also contains the original footer's creative-draft status language. The canvas's saved v1 and unchanged persisted-owner readback establish the bounded navigation result; they do not prove that every in-memory Creative form is clean, or that all draft-status UI is consistent. This review does not broaden the navigation change into that original owner's form-state behavior.

Independently decoded all **12** `navigation-intent-evidence` attachments. [File DOM review](visual-dom-review-file.json) and [PG DOM review](visual-dom-review-pg.json) record actual selected-tab attributes and document-region visibility/text. Per backend, 21 delivered original HTTP body hashes match the retained raw strings, six old-scope requests have the original `net::ERR_ABORTED` cancellation, and recorded browser/cleanup errors are empty. Explicit navigation precedes continuation of the held current request; no response is fabricated.

## Runtime and causal limits

The new browser flow uses original trusted `LocalSessionBootstrap`, original connection/project/branch UI, ordinary backend processes and real File or PostgreSQL adapters. PostgreSQL uses `v2_navigation_intent_browser_20261017_final_r1` on the owned loopback server, OID 28822. Asset persistence remains the original File `AssetLibraryService`; this is not an all-assets-in-PG claim.

The dispatch gate pauses a real client GET before dispatch, then invokes `route.continue()` without changing URL, method, body or headers. It is controlled latency scheduling, not server-side in-flight response replay. Browser cold/reload selection begins after original bootstrap actor resolution while the parent overview remains held. User intent before first actor installation is specifically covered by the mounted bootstrap-promise regression, rather than silently claimed as browser coverage.

Cross-project/branch browser cases prove original child-owner cancellation and the new current scope's real GET/navigation. Independent old-owner readbacks do not mean a canceled old callback was delivered. App parent ABA and batched ABA rejection are mounted regression evidence. Local saved hints are tested through their original mounted persistence path; authenticated browser pages are not injected with local hints.

The previous overview-default override is repaired for the covered explicit App module entry paths. Automatic default IMAGE, legitimate local hint recovery and return/reopen defaults remain intact. Other future navigation owners or arbitrary UI interactions outside these paths are not implicitly certified.

Production `PROMPT_ADOPTION_WRITE_ENABLED` remains False; ordinary GET capability is false, with no process override, development sessions, response mocks, model-provider mock or adoption POST. Exact model status remains `NOT_REQUESTED` / `NOT_INSTRUMENTED`, rather than an instrumented zero-call claim. This round does not repeat the prior adoption write acceptance or establish generation/render/GPU quality.

The original runner retains all failed RED/setup/typecheck diagnostics and prior evidence. [final-runtime-cleanup.json](final-runtime-cleanup.json) reports original wrapper cleanup complete, PostgreSQL stopped (`pg_ctl` exit 3), closed owned ports, and no owned worker processes. No source/test changes, new test runs, commits or pushes were performed during this final visual review.
