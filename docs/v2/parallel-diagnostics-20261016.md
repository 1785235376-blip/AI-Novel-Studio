# Bounded diagnostic preview and error guidance

Status: IMPLEMENTED bounded frontend slice; U12 overall remains PARTIAL.

## Requirement mapping and original owners

The frozen prose describes error explanations/redacted diagnostics under the user-facing U11 reference. The current capability ledger assigns this capability to **U12**; its U11 is reading/proofreading/publishing. This receipt uses U12 without rewriting the shared ledger.

Existing owner: `app/experimental/ux.py` (`diagnostics`, `export_diagnostics`, `SAFE_CODES`), `ux_api.py`, and `frontend/src/experimental/uxClient.ts`. The backend already projects allowed metadata and validates preview digests on export. The mounted WorkspaceToolsPanel already exposed explicit preview/download. This slice extracts only that panel into `WorkspaceDiagnostics.tsx`; it does not add a logger, another export authority, or a second task store.

## User workflow and actual change

1. Open Worksite tools → diagnostic package; nothing is collected until the user requests a preview.
2. Select original owner metadata categories and generate a preview.
3. Review original error codes alongside deterministic next-step guidance, including truthful unclassified fallback. TIMEOUT/NETWORK_ERROR advice warns against blindly replaying an unknown result; permission/version/source errors point to original authority and preserve drafts.
4. See the original coverage truncation flag and the warning that absence of errors is not proof that every task or model is healthy.
5. Explicitly recheck: old preview is cleared before requesting current data. A failed recheck cannot leave that older preview exportable.
6. Explicitly download using the existing owner and exact preview digest. A refused export invalidates preview; 409 explains that another preview is needed. Guidance is never added to the exported owner payload. Object URL is released even if click throws.

Original client-keyed scope reset and unmount guards remain. Shared shell, CSS, tokens, runtime diagnostics, provider/model controls, backend security and task mutations are unchanged.

## Verification

- `frontend/node_modules/.bin/vitest run src/experimental/WorkspaceDiagnostics.test.tsx src/experimental/WorkspaceToolsPanel.test.tsx --maxWorkers=1 --minWorkers=1 --no-cache` (from frontend): 36 tests, exit 0.
- `frontend/node_modules/.bin/tsc --noEmit` (from frontend): exit 0.
- `frontend/node_modules/.bin/vite build` (from frontend): exit 0; existing large-chunk warning remains.
- `node scripts/check_ui_design_tokens.mjs`: exit 0, 52 files checked.
- `git diff --check`: exit 0.

New tests cover bounded coverage/guidance, failed refresh invalidation and recovery, digest/409 invalidation, A→B→A late preview, prototype/unknown-code fallback, and explicit successful download of original payload with URL cleanup. Existing 30 panel tests include field-change invalidation, keyed identity changes, and suppressed late export after unmount.

Existing dependencies were used without install. Initial Vitest runs used a symlink to existing dependencies, so their default Vitest cache may have touched shared `node_modules/.vite/vitest/results.json`; final runs disabled caching. The symlink is not committed. Source and build output stayed in the assigned worktree.

## Limits / NOT_RUN

UI tests are synthetic jsdom tests, not browser or backend acceptance. Browser screenshots, visual/geometry regression, actual download UX, real File/PG endpoints, Windows/GPU/model execution, CI and remote push were NOT_RUN. There is no new network probe, upload, support contact, provider call, or install.

Diagnostics still depend on the original service's typed allowlist response. This slice does not prove malformed-response fail-closed behavior or comprehensive privacy cleaning. Unknown codes use a truthful explanation fallback; no regex is claimed to certify privacy. Existing export serialization and backend redaction contract are unchanged. Coverage can be incomplete even when the truncation flag is false (for example an unavailable original source); this slice makes no complete telemetry claim.
