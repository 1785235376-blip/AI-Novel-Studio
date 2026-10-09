# DESIGN SYSTEM CHANGE REQUEST

## Status and review identity

- Status: **APPROVED for the exact narrow extension; implementation validation pending**.
- Scope: one optional project noun in the existing shared ContextBar.
- Inspection baseline: `4350a61fb9f61acccb845fef96b24b9b1275bbd3`.
- Approval covers only the optional noun plumbing and its focused renderer tests. New feature-entry integration awaits its separate backend contract.
- The implementation changes no tokens, canonical references, or visual baselines.
- Existing historical CI and independent-review outcomes remain unchanged; this request is not verification evidence or a restart of those reviews.

## Repository approval rule

[`design_system.md`, “Design Change Process”](design_system.md#design-change-process) states:

> DS-v1.0 is immutable for feature agents. A system-level modification requires:

It then requires the Design System Change Request fields reproduced below and states:

> The Root/Design System Owner approves changes, updates `design_system_changelog.md`, and refreshes affected visual baselines only after review.

[`protected_ui_surfaces.md`](protected_ui_surfaces.md) states:

> The following DS-v1.0 surfaces are owned by the Root/Design System Owner: GlobalHeader, ModuleSwitcher, ContextBar, AppShell layout, LeftSidebar shell, RightInspector shell, StatusBar, theme tokens and core primitives.

It also states:

> Feature agents are consumers. They may supply module content through existing contracts but may not redesign, relocate, duplicate or introduce parallel styles for protected surfaces.

The repository assigns approval to the Root/Design System Owner; it does not state that every such change additionally requires end-user approval. This request does not confer that role, assume an approval, or override a separate user authorization boundary. The parent must establish its design-owner authority and record a decision before protected code is edited. If that authority is not established, the change remains pending.

## Requested Change

Add a narrowly typed, optional presentation input to the existing `AppShell` → `ContextBar` contract, provisionally named `projectNoun?: '小说' | '项目'`.

- Omission must produce the existing `小说：` text exactly.
- Explicit `projectNoun="项目"` may produce `项目：` only for the newly enabled, neutral-project M1 entry after its server-backed project adapter has resolved the current authorized project.
- Keep the existing `scope.project` value and `未选择` fallback. Do not copy, rename, reinterpret, or create an additional project owner.
- Do not infer a neutral project merely from zero chapters, the selected IMAGE tab, a missing model, or a client-supplied preference.
- Gate the new presentation at the V2 feature consumer. The exact new-project metadata selector must be settled with the backend contract before implementation; do not invent one in the protected shell.
- A changed creative intent or workspace preset remains a preference. It must not remove modules, change permissions, delete assets, create chapters, or execute a task.
- On V2-disabled, V1 acceptance, existing novel, and omitted-prop paths, preserve the complete current DOM output and accessibility strings.

Only this noun is requested. Storyline/branch terminology, project selection, initial navigation, module content, and data adapters belong to their existing feature owners and are not blanket-approved by this request.

## Reason

The supplied V2 roadmap requires independent studios, shared assets, optional connections, and a blank-project → external-image import → save/reopen → independent-export path without forced novel/chapter creation. A neutral project can reuse the existing owner through an adapter, while the ContextBar currently always labels that owner as a novel. An optional noun removes that misleading label for the new entry without redesigning the shell or relabeling existing novel workflows.

## Current Design System Limitation

`frontend/src/ui/AppShell.tsx` currently renders `<span>小说：{scope.project || fallback}</span>` inside the shared ContextBar. `ScopeLabels` supplies values but no project presentation noun. A feature consumer cannot change the noun without a protected-surface extension. CSS replacement, hidden overlays, parallel ContextBars, and post-render DOM mutation are not acceptable alternatives.

## Existing Component Investigated

- `frontend/src/ui/AppShell.tsx`: `ScopeLabels`, `ContextBar`, `AppShell`, and `ModuleSwitcher`.
- `frontend/src/ui/ModuleWorkspaceRoutes.tsx`: existing module-content slots and project requirements.
- `frontend/src/App.tsx`: local home, selected scope labels, and V2 feature gate.
- `frontend/src/novel/EntryExperience.tsx`: existing local/scoped project-selection and creation flows.
- `frontend/src/ui/moduleRegistry.tsx`: authoritative registered module order.
- `frontend/src/ui/DesignSystemFixture.tsx` and `docs/ui/visual_baseline.md`: deterministic shell fixtures and screenshot policy.
- Canonical `docs/ui/reference/novel_workspace.png` and `image_workspace.png`: inspected for shared hierarchy and geometry.

## Affected Modules

The optional input is exposed by the one shared AppShell. Only the new gated neutral-project consumer supplies it. Existing NOVEL, IMAGE, VIDEO, ASSETS, AUDIO, CONTROL, PLUGIN, and WORKFLOW callers retain their current default rendering unless deliberately integrated into that same neutral-project route under the approved contract.

The authoritative module sequence stays `NOVEL, IMAGE, VIDEO, ASSETS, AUDIO, CONTROL, PLUGIN, WORKFLOW`. No tabs are renamed, moved, added, hidden, disabled, or reordered by this change.

## Visual Impact

- In the new neutral-project state, replace only the two-character noun `小说` with `项目`.
- Keep the punctuation `：`, value, fallback, separators, element order, classes, and nesting unchanged.
- No new wrappers, styles, colors, fonts, spacing, borders, tokens, breakpoints, widths, or heights.
- Preserve the 56 px header, 44 px ContextBar, 32 px status band, 248 px desktop sidebar, and 340 px desktop inspector, including existing compact-layout behavior.
- Preserve fixed ModuleSwitcher placement and all unrelated shell/content geometry.
- Existing `/ui-fixture?module=NOVEL|IMAGE|VIDEO` snapshots should remain unchanged. Do not refresh them solely to accommodate an unintended difference.

## Accessibility Impact

- Preserve `<nav className="context-bar" aria-label="当前创作范围">` exactly.
- Preserve default V1 strings `创作空间：`, `小说：`, `故事线：`, `创作分支：`, `未选择`, and all other shell accessibility names.
- The new route changes only the visible/read project noun to `项目：`; no new landmark, focus stop, live region, role, or interaction is introduced.
- Preserve keyboard navigation, focus restoration, module-tab order, reduced motion, and existing screen-reader semantics.

## Regression Risk

- An incorrect default or overbroad caller could relabel legacy projects or change V1 snapshots.
- An intent/preset used as an authorization or module-visibility condition would violate the roadmap and existing scope contracts.
- A frontend-only neutral-project flag could misrepresent a stale, deleted, or unauthorized selection.
- Long project labels could expose existing overflow at compact sizes even when geometry is unchanged.
- The protected edit must remain minimal and separate from unrelated entry, asset, and provenance implementation.

## Migration Required

No data migration, ID change, schema change, permission change, asset copy, local-storage migration, model action, or V1 source rewrite is required by this presentation extension. The optional prop is backward-compatible. Any M1 project metadata or entry routing is a separate backend/frontend contract owned by that feature, and must preserve the current owner and authorization.

## Proposed Tests

1. Focused ContextBar/AppShell unit tests: omitted prop and explicit legacy noun render the exact existing V1 markup/text; empty values retain `未选择`; the neutral prop changes only `小说：` to `项目：`; no new wrappers or accessibility attributes appear.
2. Caller tests: V2 disabled and V1 acceptance mode omit the new input; legacy novel projects keep the old default; the authorized new neutral project supplies the new noun. A zero-chapter legacy novel must not be relabeled merely for being empty.
3. Feature-state tests: creating/reopening the neutral project does not create a chapter; changing/skipping intent preserves assets and every registered module; denied, missing, or stale project resolution fails closed without reusing another project's display or assets.
4. Existing frontend build, token guard, relevant AppShell/module/entry tests, and the existing Design System fixture screenshots remain required. No assertion weakening or automatic snapshot replacement.
5. Run `frontend/tests/visual/design-system.spec.ts` using its existing configuration. Check existing NOVEL/IMAGE/VIDEO baselines and compact geometry, including the existing 1024 px case.
6. Add/review actual neutral-project empty and imported-asset screenshots at 1366×768, 1440×900, and 1920×1080; also check 2560×1440 required by the new roadmap. Use a long project name and verify no page-level horizontal overflow.
7. Verify exact header/context/sidebar/inspector/status dimensions and unchanged ModuleSwitcher order/placement in the new route. Inspect actual screenshots against canonical hierarchy; passing type checks alone does not establish visual approval.
8. Record test commands, current implementation SHA, results, execution level, and any blocked/not-run checks. Existing historical PARTIAL/BLOCKED outcomes remain attached to their original evidence.

## Approval and implementation record

- Root/Design System Owner decision: **APPROVED**, with the exact scope below.
- Decision authority and date: Root design review, relayed by the coordinating parent on **2026-10-09 11:48 UTC**.
- Approved scope: optional `ContextBar` project noun, default-preserving `AppShell` plumbing, and focused renderer tests. Broader protected changes require a new review.
- Implementation SHA: **UNCOMMITTED**; based on inspection baseline above.
- Focused/visual verification: **NOT_RUN**.
- Changelog update: recorded in `design_system_changelog.md`; verification pending.
- Existing-baseline refresh: **NOT REQUESTED**; any actual need must be separately reviewed rather than accepted automatically.

Verbatim approval:

> Root design review approves this exact scoped DS change: optional ContextBar project-noun prop, default 小说 preserves existing V1 rendered text/DOM/accessibility, 项目 only explicitly selected gated neutral V2 project, no geometry/styles/tokens/tab/module ordering changes. Record request approval and design_system_changelog per repo process. Add default-off/V1_ACCEPTANCE_MODE and V2 renderer assertions, correct selected project scope behavior, existing geometry/browser regression. Refresh only demonstrably affected legitimate V2 text baseline after actual visual review; never blanket refresh old failing baselines. If implementation needs broader protected change return for review.

The focused renderer checks are authored in `frontend/src/ui/AppShell.projectNoun.test.tsx`; they are not yet executed. Actual feature-flag/V1-acceptance consumer tests await M1 entry integration rather than simulating an unimplemented gate in the shell. Geometry/browser validation and actual screenshot review remain pending. No existing baseline has been refreshed.
