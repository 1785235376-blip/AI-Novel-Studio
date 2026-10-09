# DESIGN SYSTEM CHANGE REQUEST

Requested Change: Add an explicitly opt-in Narrative Production V2 workspace with five workflow modes, a project stage timeline, asset browser, creative canvas, director review inspector and production sequence timeline. The existing AppShell slots are reused without changing protected geometry or the global NOVEL / IMAGE / VIDEO module order.

Reason: Structured creative documents already have a scoped, version-aware API but lack a working UI. Authors need to edit and review screenplay, director, storyboard and production drafts in one coherent workspace.

Current Design System Limitation: DS-v1.0 documents module content but does not describe a cross-stage creative workflow hosted inside NOVEL.

Existing Component Investigated: AppShell, ModuleWorkspaceRoutes, Button, IconButton, Badge, Panel, EmptyState, StatusMessage, existing manuscript editor and experimental request contracts.

Affected Modules: Opt-in NOVEL content only. IMAGE, VIDEO and other existing module routes retain their behavior.

Visual Impact: Existing shell, typography, colors and spacing tokens remain unchanged. New stage navigation and document/asset selection occupy module content slots. Actual sequence duration is used for timeline geometry; no fake media previews or generated status.

Accessibility Impact: Semantic, arrow-key navigable stage tabs; labeled controls; persistent errors and conflict review; visible keyboard focus; keyboard-operable sequence reordering; reduced-motion-compatible and no automatic animation.

Regression Risk: Switching modes must preserve the manuscript owner and unsaved creative drafts. Late responses must not cross identities. Concurrent writes remain expected-version guarded. AI proposals require explicit review before accepting; no generated media is implied.

Migration Required: None. Existing V1 paths and default-off flags remain unchanged. No token, primitive, protected shell or frozen release changes are requested.

Proposed Tests: Default-off/no-call behavior, five stage modes, scoped HTTP calls, create/update and version conflict preservation, duplicate clicks, cancelled navigation, stale response isolation, model-unconfigured status, proposal approval, timeline reorder, shared shell geometry at 1366x768, 1440x900 and 1920x1080, and existing design-system regression checks.

Review: Submitted to the parent/design-system owner. This implementation consumes current DS-v1.0; no protected-system override is required.
