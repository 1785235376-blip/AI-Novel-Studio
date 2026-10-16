# Design System Changelog

## DS-v1.0 - Initial UI Freeze

- Established the product UI constitution and one shared AppShell.
- Defined color, typography, spacing, radius, border, shadow, layout, icon, z-index and motion tokens.
- Standardized ModuleSwitcher, ContextBar, sidebar, inspector, status and initial primitives.
- Defined NOVEL/IMAGE/VIDEO ModuleWorkspace contracts and honest shell-only placeholders.
- Established canonical-reference, React screenshot, geometry and governance workflows.

## DS-v1.1 - Desktop Craft Pass

- Refined the light neutral palette while retaining the single blue accent and semantic status colors.
- Replaced the generic Inter-first UI stack with the native Segoe UI Variable stack for a more authored Windows desktop character.
- Strengthened product identity, search affordance, user identity and inspector hierarchy without changing AppShell geometry.
- Standardized tactile hover, active, focus, disabled and loading behavior across legacy and shared controls.
- Preserved the 56 / 44 / 32 shell bands, fixed module order, collaboration behavior and capability gating.

## 2026-10-09 - Approved V2 project noun extension (automated checks passed; visual review pending)

- Root design review approved the narrow [V2 project-label request](design_system_change_request_v2_project_label.md).
- Added optional `projectNoun` plumbing from the existing AppShell to ContextBar. The default remains `小说`; only an explicit gated neutral-project consumer may request `项目`.
- Preserved default V1 markup, accessibility strings, scope values/fallbacks, geometry, tokens, and module order. No styles or parallel shell were introduced.
- Source-bound frontend verification, including exact legacy markup/text-node preservation, opt-in noun changes, selected-scope replacement, and M1 content regression coverage: **1773 passed / 8 existing skips**. Corrected TypeScript/Vite/token verification: **PASS**. See the [frontend receipt](../delivery/v2-development/stage-m1-final-frontend-corrected.json) and [build receipt](../delivery/v2-development/stage-m1-final-build-corrected.json); both record unchanged sources during execution. Earlier failure receipts are retained.
- Real Image/Video import, reopen, original-byte export, relationship, default-off/V1-acceptance, and geometry cases are authored. The retained local browser route remains **BLOCKED**; hosted execution of the new M1 states is **NOT_RUN**. Actual screenshot/geometry review remains pending. Test collection and unit/build success are not visual approval.
- No canonical reference or existing visual baseline was refreshed. Broader protected changes require a new review.
