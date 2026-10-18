# Explicit graph connection removal preview

2026-10-18. The original Graph connection list now stages an impact preview before removing one connection. It shows the target and structurally reachable downstream nodes, newly missing required enabled-input ports, and nodes outside that downstream path. The user explicitly confirms before the original controller changes the local draft. Original undo/redo and CAS saving remain the only write path; no run is created, no node/asset/document/history is deleted, and saved source pins are unchanged.

The preview is tied to exact draft, catalog, owner and editability lifetimes. Draft/authority/permission ABA or revoked consent invalidates retained callbacks; application is synchronously consumed once. This is structural reachability and port analysis, not a model judgment, cost estimate or assertion that every downstream node will fail. Runtime validation still belongs to the original Graph service.

Evidence: graph-disconnect-final, 35 focused tests passed plus TypeScript, Vite production build and shared-token guard. Includes actual original controller preview→apply→undo→redo→CAS save without run creation and existing canvas/Director/starter regressions. The first run had a new test selector ambiguously matching both the old connection list and the new missing-port explanation. The selector now targets the exact explanation; assertions remain, and the failed log is preserved.

No backend contract or execution budget changed. This closes connection-list removal preview, not all node-deletion/disable consequence flows or protected saved-reference removal. Browser visual/end-to-end and full professional workspace acceptance remain pending.
