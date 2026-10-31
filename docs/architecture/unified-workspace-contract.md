# Unified Workspace Contract (v3) — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

Note: `docs/architecture.md` already exists as a single file; this contract lives in the new directory `docs/architecture/`.

## 1. Panel contract
Builds on the existing `frontend/src/workbench/panels.ts` (PanelRegistry, DockZone left/main/right/bottom, CapabilityStatus); it does not replace it.

`LayoutPanelSpec` (frontend/src/workspace/layout/model.ts):
| field | rule |
|---|---|
| id | stable, unique; persisted. Never reuse a removed id for different content |
| title | user-facing Chinese label; used for aria-label of region/close/dock select |
| defaultDock | one of left/right/bottom/main/float; must be in `docs` |
| docks | allowed docks; a dock action outside this list is a no-op |
| defaultSize / minSize / maxSize? | px; size is clamped to [minSize, min(maxSize, 60% viewport)] for side/bottom docks |
| defaultOpen? / defaultCollapsed? | initial visibility |

Panel content API (`renderPanel(id, api)`): `api.registerDirty({isDirty, save, discard}) → unregister`. A panel that holds unsaved edits MUST register; close goes through the dirty-close guard:
- clean → closes immediately;
- dirty → dialog 取消 / 放弃修改 / 保存并关闭; 保存并关闭 closes only after `save()` resolves; on rejection the panel stays open with the real error text; never reports "saved" on failure;
- late results after cancel/unmount are ignored (sequence counter + mounted ref).
Collapse never unmounts content (state kept). Close unmounts content.

## 2. Action contract
Layout actions are reducer actions (`layoutReducer`): dock, resize, moveFloat, resizeFloat, collapse, close, reopen, focus, split, viewport, reset, replace. Unknown panel ids → no-op (same state object).
Command-level actions keep using the existing `workbench/actions.ts` ActionRegistry semantics (done/stale/duplicate/needs-confirmation/blocked/error, pending dedupe, `shouldHandleShortcut`). `layout.reset` keeps `requiresConfirmation: true`; DockLayout shows a confirm dialog (恢复默认布局). Registering DockLayout actions into ActionRegistry is part of the wiring step (not done in M1).

## 3. Persistence format v3
Key: `poemseed.workspace.layout.v3::<userId>::<projectId>::<projectInstanceId>`; corrupt-data backup: same key + `::backup`.
```json
{"version":3,"split":"single|split-h|split-v","focusId":null,
 "panels":[{"id":"inspector","dock":"right","order":0,"size":340,"collapsed":false,"open":true,"z":0,"floatRect":{"x":0,"y":0,"w":0,"h":0}}],
 "preserved":{"<unknown panel id>":{...raw entry kept verbatim...}},
 "extra":{"<unknown top-level field>":"kept verbatim"}}
```
Panels are serialized sorted by id with canonical key order → byte-identical re-serialization.

## 4. Migration rules
Load order: v3 key → workbench v2 (`poemseed.workbench.layout.v2::…`, written by `workbench/layout.ts`) → workbench v1 (`{schemaVersion:1,panels:[{id,zone}]}`) → AppShell keys `studio-inspector-width` / `studio-inspector-open` (when `inspectorPanelId` given) → defaults.
1. Legacy keys are READ-ONLY. Load never writes, deletes or rewrites them.
2. Load never writes the v3 key either; the first write happens on the first user layout change.
3. Corrupt v3 (bad JSON, non-object, unsupported version) → defaults shown, diagnostic `corrupt-json`/`unsupported-version`, raw copied to `::backup`, original left in place.
4. Migration throwing → defaults, diagnostic `migration-failed`, raw untouched, nothing written.
5. Field-level repair: invalid dock/size replaced by spec defaults with diagnostics; valid fields kept.
6. Unknown panel ids → kept in `preserved` and written back; reset keeps `preserved`.
7. Panels missing from storage → added at defaults (`missing-panel-added`).
8. Duplicate entries for one id → first wins.
9. Idempotent: load→save→load produces identical bytes.
10. Future version > 3 → treated as unsupported (fallback + backup), never downgraded in place.
