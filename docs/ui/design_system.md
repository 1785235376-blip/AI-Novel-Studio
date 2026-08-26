# AI-Novel-Studio Design System

Version: `DS-v1.0`

## Product Principles

AI-Novel-Studio is a calm, professional, creator-focused desktop workspace for long sessions. Prefer dense but readable information, quiet borders, predictable placement and direct actions. Do not imitate entertainment launchers, decorative AI SaaS, ERP dashboards, ChatGPT, VS Code, or purple-gradient products.

## Visual Language

Use light neutral surfaces, a single blue accent, border-first grouping, restrained shadows and compact typography. The approved direction is represented by `docs/ui/reference/{novel,image,video}_workspace.png`. These images define hierarchy and relationships; they are not pixel-test inputs.

## App Shell

There is one `AppShell`: `GlobalHeader`, `ContextBar`, `WorkspaceBody`, and `StatusBar`. `WorkspaceBody` contains `LeftSidebar`, `MainWorkspace`, and `RightInspector`. NOVEL, IMAGE and VIDEO provide module content through this contract; they may not create parallel shells.

The fixed `ModuleSwitcher` order is 小说 / 图片 / 视频. IMAGE and VIDEO remain capability-gated shell placeholders until their runtimes exist.

## Module Architecture

| Module | Sidebar | Main | Inspector | Status extensions |
| --- | --- | --- | --- | --- |
| NOVEL | chapters, lore, continuity | TipTap editor | AI writing/context | save, version, context, words |
| IMAGE | visual assets | future Infinite Canvas | image properties/generation | assets, consistency, provider |
| VIDEO | scenes, shots, media | future Shot Canvas and Timeline | video properties/generation | timeline, jobs, provider |

Canvas nodes and timeline tracks may have domain geometry, but their toolbars, buttons, menus, dialogs, panels and status language use DS-v1.0.

## Tokens

Source: `frontend/src/ui/tokens.css`.

- Color: app/surface/subtle/elevated backgrounds; primary/secondary/muted/inverse text; default/strong/focus borders; one primary accent; success/warning/error/info statuses; selection background/border.
- Typography: `--font-ui`, `--font-editor`, `--font-mono`. UI uses compact headings, body, label, caption and metadata roles; only novel prose uses editor typography.
- Spacing: 4, 8, 12, 16, 24, 32, 40 and 48 px. New arbitrary spacing requires a Design System Change Request.
- Radius: 3, 6, 8 and round. Cards/panels remain at 8 px or less.
- Border/shadow: panels use borders; only dropdowns, floating tools, overlays and dialogs use shared shadows.
- Layout: header 56, context 44, sidebar 248, inspector 340 and status 32 px; main workspace minimum 480 px; content gap 12 px.
- Icons: Lucide only for general UI, sized 12/16/20/24 px. Domain-specific media can be an exception.
- Z-index: dropdown 40, overlay 80, dialog 100.
- Motion: 120/180 ms and reduced-motion compatible.

Production components must not introduce raw hex, `rgb()` or `hsl()` values. Exceptions are token definitions, real media/canvas colors, third-party compatibility and semantic data visualization.

## Shared Components

The canonical primitives live under `frontend/src/ui/`: `Button`, `IconButton`, `Badge`, `Panel`, `EmptyState`, `AppShell`, `ModuleSwitcher`, and `ContextBar`. Extend this family for Input, Textarea, Select, SearchInput, Tabs, SegmentedControl, Dropdown, ContextMenu, Tooltip, Card, Dialog, ConfirmDialog, Drawer, Toolbar, Breadcrumb, TreeView, ScrollArea, LoadingState, ErrorState and ConflictState when a real consumer needs them. Do not prebuild unused wrappers or modality-specific duplicates.

All interactive states require default, hover, active, focus, selected, disabled, loading and error handling as applicable. Use icons for familiar tool actions, text for commands, segmented controls for modes, tabs for views and tooltips for unfamiliar icons.

## Surfaces

- Sidebar: compact hierarchy/navigation, shared width and selected treatment.
- Inspector: properties, context and generation controls, shared width and sections.
- Panels/cards: border-first, never cards nested inside decorative cards.
- Dialogs/drawers: shared overlay, initial focus, focus containment, Escape and focus restoration.
- Tree views: semantic buttons/items, keyboard access and clear selected state.
- Editor chrome: may frame TipTap but must not restyle prose as panel UI.
- Canvas/timeline chrome: use shared toolbar, menu, inspector and status primitives.

## Status Language

Use the same semantics in every module: Saving, Saved, Unsaved, Conflict, Error, Loading, Queued, Working, Completed, Failed, Cancelled, Checked and Warning. Persistent conflicts use a shared ConflictState/Panel pattern, never a transient-only toast. V0.5.7 local-draft preservation and optimistic concurrency are protected behavior.

Revision restore is explicit, explains that it creates a new current revision, and remains version-aware. Permission display is advisory; backend authorization stays authoritative.

## Loading, Empty And Error

Every data surface provides loading, empty, success, unauthorized/not-found and error states. Disabled placeholders explain unavailable capabilities. IMAGE and VIDEO may never imply generation works before the backend capability exists.

## Focus And Accessibility

Use semantic buttons, tabs, navigation and dialogs; never a clickable `div`. Preserve visible focus rings, keyboard operation, disabled semantics, labels and live regions. Menus and tabs follow expected arrow/Tab behavior. Maintain readable contrast and honor reduced motion.

## Theme And Desktop Rules

DS-v1.0 freezes a light canonical theme while tokens remain theme-ready. Components may not hard-code white/black surfaces. Validate desktop layouts at 1366x768, 1440x900 and 1920x1080. Below 1100 px, inspectors may collapse; editor/canvas content must remain usable. Full mobile design is deferred.

## Visual Regression

Follow `docs/ui/visual_baseline.md`. Canonical references guide design. Approved screenshots generated from the real React fixture become Playwright baselines. Geometry tests separately freeze the shell dimensions.

## Design Change Process

DS-v1.0 is immutable for feature agents. A system-level modification requires:

```text
DESIGN SYSTEM CHANGE REQUEST
Requested Change:
Reason:
Current Design System Limitation:
Existing Component Investigated:
Affected Modules:
Visual Impact:
Accessibility Impact:
Regression Risk:
Migration Required:
Proposed Tests:
```

The Root/Design System Owner approves changes, updates `design_system_changelog.md`, and refreshes affected visual baselines only after review.

