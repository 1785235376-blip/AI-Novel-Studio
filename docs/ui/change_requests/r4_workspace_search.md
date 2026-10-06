# Design System Change Request: optional workspace search action

- Requested change: allow the existing global Search control and Ctrl+K to call a supplied workspace-search navigation action when the server explicitly enables workspace_tools_v2.
- Reason: reuse the established global search entry for real project search; avoid a second top-level launcher.
- Current limitation: the existing command overlay searches only module names and fixed utility commands.
- Existing components: AppShell, FeatureLauncher, ExperimentalWorkbench, WorkspaceToolsPanel.
- Affected modules: NOVEL supplies the optional callback; default/off consumers retain the existing command overlay.
- Visual impact: none to AppShell geometry, tokens, dimensions or module ordering.
- Accessibility: preserve existing semantic button and shortcut; ignore IME composition; search panel autofocus and regular keyboard navigation remain domain behavior.
- Regression risk: default overlay must remain reachable when no callback is supplied; captured callback must not become stale.
- Migration required: none. Optional prop only.
- Proposed tests: existing AppShell command and geometry tests; callback/IME/default-off tests; hosted keyboard search journey.
- Integration owner decision: accepted for this narrowly scoped functional extension. No palette, global layout or visual redesign change.

## U04 focus consumer addendum

The existing inspector collapse state may also be temporarily controlled by an optional focusMode prop. This reuses the same collapsed geometry and retains the prior inspector preference. The original editor, chapter tree, status/save failure and active conflict remain mounted. The edge control can exit focus. The integration owner accepts this bounded functional contract; no token, palette, module order or shell redesign is introduced. Component focus/restore tests and existing geometry/browser regressions remain required.
