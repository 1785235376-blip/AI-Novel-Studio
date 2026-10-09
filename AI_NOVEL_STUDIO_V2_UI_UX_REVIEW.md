# V2 UI/UX Review and Acceptance Gates

Review date: 2026-10-09 UTC. Inspection baseline: `4350a61fb9f61acccb845fef96b24b9b1275bbd3` on `feature/v2-narrative-platform`, [Draft PR 47](https://github.com/1785235376-blip/AI-Novel-Studio/pull/47). M1 changes are being integrated in the working tree. This document is a source review and an executable acceptance plan, **not a visual PASS for those changes or a declaration that all V2 Studios exist**.

Requirements: the supplied 2026-10-09 V2 Master Roadmap, especially §§1, 7, 15, 21–25 and Appendix C, and its start instructions. All 904 roadmap lines and all 28 start-instruction lines were read. The roadmap's production sequence is an engineering dependency order; it must never become a mandatory user workflow.

## 1. Design authority and review scope

Read before this review:

- [Repository rules](AGENTS.md), `.codex/skills/ai-novel-studio-ui/SKILL.md` and its design-system, layout, component and visual-review references.
- [DS-v1.0](docs/ui/design_system.md), [protected surfaces](docs/ui/protected_ui_surfaces.md), [review checklist](docs/ui/ui_review_checklist.md), [visual-baseline policy](docs/ui/visual_baseline.md).
- [V1 scope freeze](V1_SCOPE_FREEZE.md) and the [approved narrow ContextBar request](docs/ui/design_system_change_request_v2_project_label.md).
- Canonical NOVEL and IMAGE reference images were actually opened and visually inspected. Their quiet borders, blue accent, shared navigation and three-part workspace hierarchy guide review; they are **not browser screenshots or pixel baselines**.

Protected AppShell, GlobalHeader, ModuleSwitcher, ContextBar, sidebar/inspector shells, StatusBar, tokens and primitives remain owned by the Design System owner. New work consumes `ModuleWorkspace`, `frontend/src/ui/tokens.css` and shared primitives. No replacement shell, CSS text substitution or independent Studio theme is permitted.

The approved change is only optional `projectNoun` presentation through the existing AppShell/ContextBar. Omission retains `小说：` and all legacy DOM/accessibility strings. `项目：` is permitted only for the explicitly activated, server-resolved neutral V2 project. Zero chapters, an IMAGE tab or an intent preference alone must not select it. Geometry, tokens and module order are unchanged. Broader Tutor docking, resizable panes or global navigation changes need their own approval. Approval of the noun is not approval of its final rendering.

## 2. What the actual UI currently establishes

| Surface / source | Code evidence and limits | Current milestone conclusion |
| --- | --- | --- |
| `frontend/src/ui/AppShell.tsx`, `ModuleWorkspaceRoutes.tsx`, `moduleRegistry.tsx` | One shared shell; registered order is NOVEL, IMAGE, VIDEO, ASSETS, AUDIO, CONTROL, PLUGIN, WORKFLOW. The older DS document's initial three-module description does not authorize deleting the additional registered modules. | Existing owner; preserve exact current navigation. |
| `frontend/src/creative/CreativeWorkspace.tsx`, `ProjectTimeline.tsx` | Existing five-mode narrative workspace and document selection/recovery. A suggested adaptation route is useful, but does not establish ten independent Studios. | Foundation exists; independent entry is M1 work. |
| `frontend/src/creative/CreativeCanvas.tsx` | Structured scene/dialogue/director/shot forms, save/export/history, scene selection and arrow-based shot reordering. | **PARTIAL** relative to M2: this is not the shared typed, infinite executable node canvas. |
| `frontend/src/creative/ProductionTimeline.tsx` | A shot-based plan with duration/reorder controls; explicitly says `结构化计划 · 尚未渲染媒体`. | Planning exists; M9 real NLE remains pending. No real V1/V2/A1/A2/subtitle editing or decoded playback is proven by these cards. |
| `frontend/src/ui/ModelCenter.tsx`, `LocalAiDiscovery.tsx`, `localAiDiscoveryApi.ts` | Existing settings/discovery lifecycle with separate candidate/registration states and explicit model actions. | Reuse in M3; discovery must never be labelled successful inference. |
| `frontend/src/interop/LocalTutorIntegration.tsx`, `frontend/src/interop/entry.tsx` | Existing optional, permission-aware Tutor dialog and revocation handling. | Reuse trust/privacy identity. A dockable/floating workspace Tutor Slot is not established by the dialog alone. |
| `app/creative/workspace*.py`, `frontend/src/creative/studioClient.ts` | M1 adapters and client are in active integration: neutral project metadata, preferences and manual assets over original owners. | Uncommitted implementation evidence only. End-to-end entry, renderer and browser acceptance remain **NOT_RUN** at this snapshot. |

Changing an intent/preset must neither remove modules nor change authorization, delete assets, start models or execute nodes. Ordinary and professional views must share the same Project/Asset/Job/Model owners. Each Studio must remain useful with manual/imported assets and absent models; unavailable AI controls explain the missing capability without blocking manual save/export.

## 3. Historical evidence, kept separate from the current review

The [99e3c63 failure archive](docs/delivery/v2-development/ci-99e3c63-browser-failure/README.md) contains real browser evidence. Its [Production reopen image](docs/delivery/v2-development/ci-99e3c63-browser-failure/screenshots/failure-production-reopen.png) and [Screenplay reopen image](docs/delivery/v2-development/ci-99e3c63-browser-failure/screenshots/failure-screenplay-reopen.png) were visually inspected for this review: a saved document is present at left while the center shows an unnamed empty draft. The Production image shows zero timeline segments. These are historical failure images; they are never relabelled as current successful screenshots.

At `4350a61`, each event's existing V2 suite later passed **7 live cases (3 HTTP + 4 UI), 8 mocked cases, zero failures/skips/retries**; each frontend passed **1,567 units / 8 existing opt-in skips**. Sources: [PR Cloud 37907528214](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907528214), [push Cloud 37907521986](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37907521986), and the [historical report](AI_NOVEL_STUDIO_V2_FINAL_DEVELOPMENT_REPORT.md). The push workflow itself remained cancelled on backend capacity. These test results do not make the new M1 tree visually approved.

The prior successful browser screenshots depict Production v2 before restoration. Successful restoration/reopen to v3 is supported by assertions and receipts, not by a screenshot of v3. Success traces were not recorded by the original configuration; no claim is made to have inspected them.

| Review item | Current status | Evidence required before promotion |
| --- | --- | --- |
| Canonical NOVEL/IMAGE reference inspection | Completed reference inspection only | No runtime conclusion follows. |
| Existing historical failure screenshot inspection | Completed historical inspection only | Failure remains in history. |
| New neutral-project screenshots at four target sizes | **NOT_RUN** | Exact tree, route, viewport, PNG and actual visual review. |
| M1 AppShell noun unit / caller / live-browser checks | **NOT_RUN** | New-source execution receipts; authored tests alone do not count. |
| New infinite canvas dragging / zoom / large-graph performance | **NOT_RUN**, M2 pending | Real pointer/keyboard operation and measured benchmark. |
| Real multitrack editing / waveform / media preview | **NOT_RUN**, M9 pending | Decoded media and editable track proof, not a planning screenshot. |
| Docked/floating Tutor, high DPI, Chinese IME, multiple monitors | **LOCAL_REQUIRED** for native behavior | Approved Windows execution and actual window evidence. |

## 4. M1 acceptance journey: blank project to independent image export

Execute with a synthetic workspace, local fixture image and no enabled model, external provider or Tutor. Record exact source identity and backend mode before each journey.

1. With `narrative_production_v2` explicitly enabled, create a blank project through its visible entry. Skip intent. Confirm its ID belongs to the original project owner, no chapter is created, and the current authorized scope is selected.
2. Import an external image from the file picker. Show a truthful preview, filename, format/dimensions when measured, version, digest/source information and license state. A missing license is unknown, not commercial permission.
3. Save/reopen by the same project and asset IDs, then refresh/restart as supported. Confirm exact bytes/digest and visible selection; do not initialize an empty draft while list data is still loading.
4. Independently export the asset. Compare exported bytes/digest and filename to the imported result; no screenplay, director, storyboard, graph, chapter or model is required.
5. Change, combine and clear intents/preset. The asset remains accessible and all original module choices remain reachable with unchanged permissions; no network/model job occurs.
6. Check stale CAS, read-only permission, permission revoked during import/download, missing project, branch switch, same-title delete/recreate, corrupt bytes and quota rejection. A late response must not expose or select another scope's asset. Errors preserve the user's recoverable work and explain a safe next action.
7. Soft-delete/restore an owned asset using current version; a dependency blocks unsafe deletion. No action deletes external model files. A backend exception must not be displayed as a successful save/export.
8. Repeat with V2 off, then `V1_ACCEPTANCE_MODE=true`: no new neutral entry/endpoint authority; existing novel shell, selection, edits, conflicts and export continue unchanged.

The route/API details must be taken from the final M1 implementation and stage report, not inferred from these acceptance steps.

## 5. Visual, geometry and accessibility checklist

For **1366×768, 1440×900, 1920×1080 and 2560×1440**, capture blank state, imported-image state, long project name, busy/error state and read-only state. Retain the existing compact/1024-pixel geometry regression as well. Use bundled Chromium, locale `zh-CN`, timezone `Asia/Shanghai`, scale factor 1, light theme, loaded fonts and disabled animation/caret for deterministic browser comparisons.

- Verify 56-pixel header, 44-pixel ContextBar, 32-pixel status band and the applicable 248/340-pixel sidebar/inspector contract. Respect existing compact behavior; no page-level horizontal overflow.
- Check module placement/order, hierarchy, readable density, genuine media aspect ratio and clear primary action. Buttons must not disappear below inaccessible scroll regions.
- Use actual hit-tests after scroll: sticky headers must intercept overpainted underlying controls and controls must work again when visible. Geometry alone is insufficient.
- Use semantic controls with visible labels/focus. Tab order reaches import, selected asset, intent controls, save/export and dialogs; Enter/Space work. Escape and focus restoration preserve the initiating control.
- Check default/hover/active/focus/selected/disabled/loading/error states, empty results, unauthorized/not-found and retry. Persistent conflict must remain visible and preserve the draft.
- Distinguish application save, model queue and upstream cancellation states. A failed or unknown job never produces decorative progress or a false success badge.
- Do not update snapshots to silence a failure. Compare the actual changed image, classify the defect, obtain design-owner review where necessary and change only legitimately affected baselines.

Future canvas acceptance additionally needs port-type errors, drag reconnect, detach/delete without asset loss, undo/redo, keyboard equivalent, minimap/zoom, incremental invalidation and bounded large-graph responsiveness. Freeze performance thresholds only after a reproducible benchmark records hardware, object count, assets and measured latency.

Future Tutor acceptance needs closed/uninstalled normal operation, dock/collapse/float without obscuring canvas or timeline, no focus theft, reduced motion, visible connection/permission states, and verified revocation rather than an optimistic “disconnected” label. Suggestions must remain distinct from internal creative agents and cannot grant edit, payment or memory authority.

## 6. Reproducible verification entry points

The following are planned commands for the engineering owner in an isolated, prepared checkout. They were **not executed by this documentation review**. Use unique evidence labels and preserve failed attempts; do not replace earlier receipts.

```sh
pnpm --dir frontend test -- src/ui/AppShell.projectNoun.test.tsx src/creative/CreativeWorkspace.test.tsx src/ui/LocalAiDiscovery.test.tsx src/interop/LocalTutorIntegration.test.tsx
pnpm --dir frontend build
pnpm --dir frontend lint
pnpm --dir frontend exec playwright test --config playwright.visual.config.ts --update-snapshots=none
pnpm --dir frontend exec playwright test --config playwright.creative.config.ts --update-snapshots=none
CI_RECEIPTS="$PWD/docs/delivery/v2-development/m1-live-$(date -u +%Y%m%dT%H%M%SZ)" pnpm --dir frontend exec playwright test --config playwright.v2-live.config.ts
```

These existing suites are regression inputs, not substitutes for a new M1 live journey. Attach its exact test file/command once authored. Full File/PostgreSQL and original frontend/native/Interop gates remain required according to the stage's change impact.

Every review receipt needs UTC time, commit/tree and dirty-tree digest where applicable, feature flags, backend/browser/runtime, command/exit code/counts, screenshot viewport/route/state, source hashes, reviewer findings, and unresolved checks. Current overall UI/UX status: **PARTIAL; M1 visual acceptance NOT_RUN; native UX LOCAL_REQUIRED**. Historical `39 PARTIAL + F00 INTEGRATED` and independent-review `BLOCKED` are unchanged.
