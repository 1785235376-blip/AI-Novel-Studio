# Repository Agent Rules

Preserve user changes and existing runtime contracts. Keep work scoped, reuse established architecture, and run verification proportional to risk.

## UI Design System Rules

All frontend work MUST follow `docs/ui/design_system.md`.

Before modifying visible UI:

1. Load `$ai-novel-studio-ui`.
2. Read the relevant Design System section.
3. Reuse existing Design Tokens and UI primitives.
4. Reuse AppShell and the ModuleWorkspace contract.
5. Do not invent colors or arbitrary spacing.
6. Do not duplicate components.
7. Preserve the shared NOVEL / IMAGE / VIDEO shell.
8. Preserve V0.5.7 collaboration, conflict, revision and fail-closed behavior.
9. Run relevant visual regression and geometry tests.
10. Submit a `DESIGN SYSTEM CHANGE REQUEST` for any system-level modification.

Protected surfaces are listed in `docs/ui/protected_ui_surfaces.md`. Feature agents are consumers by default.

