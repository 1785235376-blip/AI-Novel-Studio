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

## 2026-10-09 - Approved V2 project noun extension (verification pending)

- Root design review approved the narrow [V2 project-label request](design_system_change_request_v2_project_label.md).
- Added optional `projectNoun` plumbing from the existing AppShell to ContextBar. The default remains `小说`; only an explicit gated neutral-project consumer may request `项目`.
- Preserved default V1 markup, accessibility strings, scope values/fallbacks, geometry, tokens, and module order. No styles or parallel shell were introduced.
- Authored focused renderer assertions for exact legacy markup/text-node preservation, opt-in noun changes, and selected-scope replacement. Test execution, M1 caller feature-gate/V1-acceptance checks, and browser/visual validation remain **NOT_RUN**.
- No canonical reference or existing visual baseline was refreshed. Broader protected changes require a new review.
