# CONTRACT_CHANGELOG — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

## v3 (new, M1)
- Added docs/architecture/unified-workspace-contract.md.
- New storage key poemseed.workspace.layout.v3::scope (+ ::backup). Format version 3 (workbench layout was schemaVersion 2).
- Added float dock and split modes (single/split-h/split-v).
- Unknown panels now preserved (workbench v2 sanitize dropped them).
- Legacy keys read-only migration sources; nothing deleted.
- Panel API: registerDirty for dirty-close guard.
No change to workbench/layout.ts, panels.ts, actions.ts contracts.

## M1-s2 [HERMIA-FE-20261023 M1-s2] — 6930d5c9
- §2 actions: layout actions are now registered in workbench ActionRegistry (ids layout.reset, layout.reopenPanel, layout.toggleCollapse, layout.switchSplit; default Mod+Alt+0/O/C/S). actions.ts unchanged.
- New in workspace/actions: ShortcutTable (claim/release/lookup, conflict → shortcut dropped, action still registered), RESERVED_SHORTCUTS (Mod+K), registerLayoutActions, actionIdForKey.
- DockLayout: new optional props actionRegistry, shortcutTable.
- layout/model: Viewport.reserveTop? (optional); dock action index = precise insertion index; exported dropIndexFromPoint, dropAxis, mainArea.
