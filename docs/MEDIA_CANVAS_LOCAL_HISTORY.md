# Bounded local media-canvas undo/redo

2026-10-18. The original media display editor now records local definition edits and offers explicit Undo/Redo plus scoped Ctrl/Command Z, Ctrl Y and Shift-Z. Native text-input undo and composing input are not intercepted. Pointer gestures still commit one edit on completion. No backend history or execution state is rewritten by local Undo.

Snapshots are validated detached definitions, bounded to 20 steps and 2,000,000 total serialized bytes across past/future. Large views may retain fewer steps; the interface states this. A new edit retires redo. Explicit successful Save, server-version adoption, new blank view or original owner discard clears this session history. Unknown saves remain blocked until explicit reconciliation; Undo does not infer that the server rejected a write.

Tests: 13 targeted pure-history, actual display-panel and original dirty-owner integration checks passed; TypeScript, production build and shared token guard passed. Evidence: media-canvas-history receipts/logs. Browser keyboard and visual acceptance remain open. The prior source checkpoint documentation commit eb50cb22 is included with this slice's archive prerequisite.
