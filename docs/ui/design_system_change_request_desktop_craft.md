DESIGN SYSTEM CHANGE REQUEST
Requested Change: Refine DS-v1.0 tokens and shared AppShell presentation for the production desktop redesign.
Reason: The existing implementation is functionally complete but visually resembles a generic web administration shell and lacks product identity during long writing sessions.
Current Design System Limitation: Token values and header presentation do not provide enough hierarchy between navigation, document canvas, inspection surfaces and persistent status.
Existing Component Investigated: AppShell, ModuleSwitcher, ContextBar, Button, IconButton, Panel, Badge, FeatureLauncher and the TipTap editor chrome.
Affected Modules: NOVEL, IMAGE and VIDEO shared shell; all feature panels inherit the revised tokens.
Visual Impact: Quieter neutral canvas, more deliberate type hierarchy, refined border contrast, compact product mark and consistent interaction states. Geometry remains unchanged.
Accessibility Impact: Focus visibility and control contrast are strengthened; reduced-motion behavior remains intact.
Regression Risk: Shared styling may expose overflow or specificity issues in older feature panels.
Migration Required: Existing business components continue to use current class names and tokens; no API or state migration is required.
Proposed Tests: TypeScript build, token guard, Vitest UI suite, shell geometry at 1366x768 / 1440x900 / 1920x1080, Playwright visual review and desktop runtime smoke test.
