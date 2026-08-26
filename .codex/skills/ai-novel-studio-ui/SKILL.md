---
name: ai-novel-studio-ui
description: Apply AI-Novel-Studio DS-v1.0 whenever working on visible frontend or UX, including React components, workspaces, navigation, sidebars, inspectors, dialogs, editor UI, collaboration/revision/conflict UI, IMAGE or VIDEO shells, canvas/timeline chrome, settings, styles, icons, accessibility, or visual tests.
---

# AI-Novel-Studio UI

## Required Workflow

1. Read `docs/ui/design_system.md` as the source of truth.
2. Inspect the relevant canonical reference under `docs/ui/reference/`.
3. Read the relevant short reference in this skill.
4. Reuse `frontend/src/ui/tokens.css`, AppShell and shared primitives.
5. Preserve collaboration, optimistic-concurrency and fail-closed behavior.
6. Run relevant unit, geometry and Playwright visual tests.
7. Use the Design System Change Request for any protected-system change.

## Hard Rules

- DO NOT invent a new visual language.
- DO NOT redesign AppShell.
- DO NOT move ModuleSwitcher without an approved design change.
- DO NOT invent new colors or spacing scales.
- DO NOT duplicate primitives or build modality-specific visual systems.
- USE DESIGN TOKENS, SHARED COMPONENTS and APP SHELL.
- COMPARE AGAINST CANONICAL REFERENCES.
- RUN VISUAL REGRESSION.
- Keep IMAGE/VIDEO placeholders honest and capability-gated.

## References

- Read [design_system.md](references/design_system.md) before any UI work.
- Read [layout_rules.md](references/layout_rules.md) for shell/workspace changes.
- Read [component_rules.md](references/component_rules.md) for controls and surfaces.
- Read [visual_review.md](references/visual_review.md) before screenshots or approval.

