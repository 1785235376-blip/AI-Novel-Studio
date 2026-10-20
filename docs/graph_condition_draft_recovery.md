# GRAPH-08: bounded schema7 authoring-draft recovery

The current requirement is `AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md`, GRAPH-08 §7.2:
graph versions, visible locally preserved drafts and reload/disconnect recovery.
The historical row remains PARTIAL. The original recovery owner previously accepted
only schemas1–2 (`studioGraphLocalDraft.ts`); the newly available pure local condition
canvas was therefore unable to preserve any unsaved source text or predicate on reload.
This slice closes that specific chain, without creating another store or workflow owner.

## Original owner and boundary

- Reuse the existing localStorage envelope/version, actor + scope + original project
  incarnation namespace, original request ID, definition decoder and size limits.
- Admit schema7 only through its existing strict finite topology/parameter decoder.
  Schemas3–6, external bindings, unsupported nodes, scripts and runtime/review receipts
  remain outside this recovery slice. Schemas1–2 retain their prior flow.
- Restoring schema7 explicitly rereads the original conditional catalog, with the server
  gate still default OFF. Owner/incarnation/edit permission are checked before and after
  those reads. Saved drafts also require the exact original schema7 graph ID/version,
  definition digest, execution digest and edit permission; no legacy graph is upgraded.
- A separate captured recovery lifetime rejects late responses/old callbacks after
  owner, source, permission, selection or busy changes. One pending recovery consumes
  one read; another tab's changed cache is never overwritten.
- Apply the recovered draft and catalog only after all checks. Preserve original request
  identity, UNKNOWN status, source baseline/CAS, capacity and history behavior. No Save,
  run, approval, model call, automatic retry or cache enablement follows recovery.
- Cache inspection displays the saved finite predicate read-only, using the existing
  condition form. It carries author input only, not execution or review authority.

Execution-result caches, task-engine recovery, models, NLE, Timeline and DSH components
are unchanged. The `creative-graph-local-conditions/1` runtime cache remains disabled.
The full GRAPH-08 requirement is not promoted to DONE by this bounded authoring slice.

## Targeted evidence

`StudioGraphDraftRecovery.conditions.test.tsx` first reproduced the decoder rejection
and absent autosave as two failing tests. The corrected recovery passes 17 focused cases,
including unsaved/saved/UNKNOWN recovery, gate denial, changed version/both digests,
incarnation/permission changes, ABA, duplicate reads and other-tab edits. Together with
legacy draft/recovery/notes and condition-entry regressions, 45 tests pass.

The task-local handoff retains raw RED/GREEN logs, exact type/build results and controlled
three-width component screenshots. Real Host browser and PostgreSQL acceptance are not
established; no credentials are created and no models are executed.
