# UI Debt Map

## High

- The production NOVEL workspace is still concentrated in `App.tsx`; fully extracting business orchestration from shell composition carries autosave/conflict risk and is deferred.
- Connection UX exposes raw scope IDs instead of hierarchical selectors.

## Medium

- Legacy global CSS contains hard-coded dark colors and layout values. DS-v1.0 tokens govern new shared surfaces; broad migration is deferred to avoid behavioral regression.
- Collaboration panels expose some backend-shaped metadata/JSON rather than fully structured semantic rows.
- File and collaboration composition remain interleaved in one component.
- Responsive behavior is desktop-first and has no complete mobile design.

## Low

- Mixed Chinese/English labels need copy normalization.
- Obsolete selectors in legacy CSS should be removed when their owning views are touched.
- Runtime Health remains visually separate from the primary studio shell.
- Package version still reports the historical frontend version.
- Main bundle is approximately 515 kB; optimization is known non-blocking technical debt.

## Raw Color Debt

`style.css`, `ux.css`, and `collaboration.css` predate DS-v1.0 and contain raw colors. They are grandfathered legacy debt, not precedent. New files must use `tokens.css`; migrate legacy rules incrementally alongside owned component work.

