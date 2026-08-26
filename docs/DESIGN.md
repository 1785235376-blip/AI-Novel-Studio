# AI Novel Studio Desktop Design System

## Product Read

AI Novel Studio is a desktop creative production workspace for novel writing, story planning, screenplay adaptation, image references, voice, video timelines, and provider tasks. It is a work tool, not a marketing page.

## Direction

- Visual language: Swiss editorial tool, structured and quiet.
- Density: medium-high, optimized for repeated production work.
- Motion: restrained, informative, and disabled for reduced-motion users.
- Accent: one cyan-teal action color on cool graphite neutrals.
- Surfaces: use borders, separators, and background layers before shadows.
- Radius: 6px controls and 6px workspace panels; pills are reserved for statuses.

## Workspace Contract

```text
Header: project identity, module navigation, global search, actor
Context bar: workspace / novel / storyline / branch
Body: navigation rail | primary work area | Inspector
Status dock: save state, provider state, active jobs, errors
```

The Inspector is a reserved integration point for AI context, provider task details, approvals, and future Copilot actions. The bottom status dock is reserved for real task runtime state.

## Interaction Rules

- Every icon-only control has an accessible label and tooltip.
- Every async action exposes loading, success, and failure states.
- Selection and focus are visible without relying on color alone.
- Escape closes transient Inspector and dialog surfaces.
- Panel scrolling is local; the desktop shell does not page-scroll during production work.
- Provider state must be truthful: configured, running, succeeded, failed, or unavailable.

## Component Rules

- Prefer shared workspace primitives over one-off cards.
- Use shadcn primitives for behavior and accessibility, then apply project tokens.
- Keep repeated items as rows or grouped sections; use cards only when framing is meaningful.
- Keep future media preview, timeline tracks, Copilot, and approval rail as explicit slots.

## Visual QA Viewports

- 1440 x 900 desktop baseline
- 1920 x 1080 wide desktop
- 1024 x 768 compact desktop
- keyboard-only navigation and reduced motion
