# Explicit node enable/disable impact preview

2026-10-18. The existing Graph inspector's enable checkbox now stages a structural preview before changing the local graph. The user sees the selected node and reachable downstream nodes, newly missing required input ports, and remaining missing ports after the change. Explicit confirmation is required. Neither preview nor confirmation saves, runs, cancels, approves or charges any job.

The operation preserves all node parameters, connections, source snapshots, assets and run history. It goes through the original controller change/history/CAS path; undo and redo remain available. Enabling a node does not imply its input is complete or that execution has been authorized. Disabling an in-flight node does not cancel an existing job. Catalog matching includes definition ID and version.

Source, selected node, owner, catalog and permission changes invalidate candidates. Revoked consent and consumed callbacks cannot apply a retained candidate twice. The same structural required-input and reachability helpers are reused by the earlier connection-disconnect preview. This is advisory structural analysis, not a second workflow validator or model-based semantic analysis.

Evidence: graph-node-state-ui contains 32 passing focused tests across state control, disconnect preview and existing connection editor, plus TypeScript, Vite production build and UI token guard. The controller test demonstrates explicit Save with expected_version=1, undo/redo and no run creation. This frontend-only slice makes no new File/PostgreSQL persistence claim; original backend contracts are unchanged. Browser visual/performance acceptance remains unrun; large build-chunk warnings retained. Node-removal previews remain separate work.
