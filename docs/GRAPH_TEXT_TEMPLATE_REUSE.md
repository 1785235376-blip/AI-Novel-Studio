# Bounded text-graph template reuse

2026-10-18. Adds explicit local JSON export/import for text graphs v1/v2 without Asset references. The original local-graph validator, Graph selection-copy planner, typed connection checks, node/edge/byte limits, draft history and Save owner are reused. No external plugin registry, workflow engine, executable code, run or provider call is introduced.

The file contract is `poemseed-text-graph-template/1`, bounded to 110,000 actual UTF8 bytes. It contains only a normalized definition's text nodes, internal edges, title and viewport. It never includes project/actor scope, saved graph IDs, approvals, request identity, run/cache receipts, presentation groups or notes. Imported source nodes/edges receive fresh IDs and are appended to a same-format target; existing target content is preserved. No implicit schema upgrade or capacity expansion.

Export requires an explicit acknowledgment that node prose goes into a local file. Import first produces a node/edge-count preview and requires a separate, target-bound confirmation. Confirmation is single-use and retires on owner/target/disabled changes; late file reads cannot publish into another target. Text can contain user-authored instructions as data, but JSON does not execute code or authorize runtime actions. The original Save, preflight and model/host approval flows still apply.

## Evidence

- Final focused parser/component/original-controller/original workspace checks: 48 passed.
- TypeScript and production Vite build passed; shared token guard passed.
- The original-controller integration proves local append → original Undo/Redo → explicit original create, without automatic Save or run creation. Its transport is a test fixture, not browser-to-server acceptance.
- First parser run exposed that the existing normalizer silently ignored an extra `reviewed` field. The new file boundary now recursively rejects fields absent from the normalized allowed shape; it does not merely discard an apparent receipt. The initial failure is retained and is not a demonstrated privilege escalation.
- A subsequent new-test TypeScript error assigned 3 to the literal catalog limit 16. The negative fixture now uses the genuine 16-node catalog and a 15-node target that cannot accept two more nodes; no product limit or assertion was relaxed.

Receipts/logs: `docs/delivery/v2-development/graph-text-templates*`.

This is the first text-only file-template slice. General media templates, rebinding external project sources, reusable executable subgraphs, real browser file-dialog/visual acceptance and whole V2 acceptance remain separate. No production gate, original backend API or public/private packaging rule was changed.
