# B09 reviewed project forks and merge

Status: IMPLEMENTED / INTEGRATED / CONTRACT_VERIFIED for the bounded local workflow. Real File tests use original repositories and the mounted production router. Real PostgreSQL and hosted-browser tests are authored; the release lead must attach results for the exact published commit. No local PostgreSQL endpoint is configured. Known local Chromium launch EPERM is not retried. This is not a model-quality, collaboration-branch, global transaction, release, or user-acceptance claim.

## Reuse and scope

- Extends original NovelService / ChapterService / rich document history and CAS. No editable manuscript lives in ExperimentalStore.
- ExperimentalStore contains immutable selected baselines, mappings, pre-merge checkpoints, bounded metadata histories, and durable operation journals. The same store implementation runs on File and PostgreSQL.
- `project_forks_v2` is off by default, requires `revision_intelligence_v2` and `asset_lineage_v2`, and is suppressed by V1 acceptance mode. Requests use the existing trusted host session and project authority; both projects are reauthorized before each merge write. Checkpoint recovery reads only the original project’s own stored evidence and reauthorizes that original authority; a lost or inaccessible fork cannot trap the original checkpoint.
- Real entry: Experimental workbench → 项目分叉与合并. Selected saved chapters first enter preflight, then an explicit confirmation creates an independent local project through original services. It is not a collaboration branch, Git branch, or story route.
- Supported structures: original rich chapter documents, first-heading chapter names, recoverable archive state, and supported image/audio/video references. The asset library remains the only asset authority.
- Unsupported: characters, Canon, graph records and cross-graph links, workflows, grants, secrets, old history/trash, custom embedded nodes/links and unmapped new fork assets. These domains are listed and unsupported rich shapes fail closed; no unknown IDs or fields are copied blindly.

## Three-way behavior

The baseline is the originally selected saved content. The two live sides are the current original project and current new-project fork. Rich top-level blocks are diffed deterministically without flattening nested nodes, marks, or AI lock attributes. Unilateral/disjoint rich-block changes combine; overlapping edits require explicit ORIGINAL/FORK choices. Inserts at edited boundaries are conservatively treated as overlapping. Same-title-heading changes are ordinary rename conflicts. Deleted or archived chapters always require explicit resolution; choosing a removed fork archives the original chapter, never permanently deletes it. A permanently deleted original chapter cannot be recreated under its former ID by this feature.

The preview digest binds current original/fork versions, full rich snapshots, the fork record revision, mappings, and choices. Apply recomputes and revalidates it; a changed choice or either-side drift requires another review. Every original write has expected version + current actor/source/target authority. Original A11 locks are checked before any merge or recovery: lock-changing merges require explicit unlock in the original editor first. Marks and locks are preserved exactly; a locked node containing a remapped media ID is rejected rather than silently weakening its lock digest.

## Media and provenance

Every selected asset requires an explicit per-asset author license declaration with original version and SHA-256 and permission for the local copy. Unknown/unspecified licenses do not pass. These are author declarations, not legal verification. Bytes are checked by the original asset integrity reader and bounded media decoder. New IDs are mapped explicitly. Original asset version/digest/license evidence is retained in the fork baseline and original-library provenance. Cross-project ancestry is recorded as provenance rather than inventing an invalid cross-project A09 DAG edge. Both original and cloned asset versions are checked on compare. New/unmapped or modified fork media cannot merge implicitly.

Bounds: 40 selected chapters, 1000 top-level rich blocks per document, 4 MiB selected snapshots per side, 100 assets, 8 MiB per asset and 32 MiB total media; streamed mutation inputs are capped at 128 KiB. No providers, models, external URLs, or background jobs are invoked.

## Checkpoint and interruption semantics

Apply durably records CLAIMED with the complete pre-write original checkpoint, intended result, original/fork source fences and fork's active merge ID. Before each original create/save/archive/restore step, a CLAIMED journal entry is committed. While issuing one original CAS, the existing metadata owner lock prevents a concurrent recovery from overtaking the active writer. Original data and metadata still have independent commit boundaries: process termination or a lost acknowledgement can leave APPLYING / CLAIMED even if a write happened. The service never automatically retries it.

An original callback response first records ACKNOWLEDGED; only a verified current document/state/version becomes DONE. A normal exception preserves RECOVERY_REQUIRED and all prior receipts; the old snapshot cannot be used to invoke apply again. The UI exposes receipts and current original versions. Recovery classifies unchanged checkpoint, confirmed receipt, matches-intent-but-unconfirmed, or unknown/newer. It never declares matches-intent proof of exactly-once completion.

Recovery is a new, separately confirmed operation. It shows current rich content beside the pre-merge checkpoint and warns that restoring can replace later manual edits. The fresh digest and all original expected versions are checked again. A new journal saves checkpoint content through original services as new revisions and restores archive state when needed. Original history and both projects remain. Permanent deletion or active paragraph locks may require the original editor's recovery tools.

New-project creation interrupted before all content is copied leaves the partial project, planned chapter IDs, copied-asset mappings and journal visible. It does not retry creation or overwrite existing target chapters; the author can inspect the preserved target and choose a separately preflighted new fork. New target chapter creation uses the original File project lifecycle lock with an absence check; PostgreSQL uses the original unique chapter identity.

File archive currently keeps the original document version unchanged, while PostgreSQL archive increments it. B09 verifies the exact backend's existing version behavior and archived state/document receipt; it does not change old archive semantics or pretend File archive generated an original rich-history revision.

## Verification inventory

- `tests/test_r5_project_forks.py`: original File/marked PostgreSQL selected fork, rich marks/locks, stable IDs, three-way unilateral/bilateral edits, rename and delete/modify, explicit checkpoint restore, source and target drift, authority revocation, multi-write interruption, lost receipt, process-exit claim, concurrent acceptance, media license/provenance/mapping and stale media, no branch fallback, bounds, pure legacy preflight.
- `tests/test_r5_project_forks_mounted.py`: both production API prefixes, original save callbacks and current host token, flag/dependency/V1 off, revoked session, changed fork, original CAS conflict sanitization, bounded inputs and unavailable collaboration scope.
- `frontend/src/experimental/ProjectForksPanel.test.tsx`: StrictMode read-only mount, separate fork confirmation, exact conflict choices and refreshed preview, explicit apply, media permission, stale reply suppression, interrupted recovery and scope replacement.
- `frontend/tests/e2e/r4-project-forks.spec.ts`: authored real File/API/React host-session journey, selected clone → bilateral conflict and unilateral edit → rich reviewed merge → explicit checkpoint restore; screenshots and viewport containment at 1366×768, 1440×900, 1920×1080. No response mocks.

Local focused verification before handoff: 42 Python File/mounted contracts passed (39 PostgreSQL instances deselected because no authorized local endpoint); 6 B09 React tests passed, plus 11 workbench/design-system contract tests; design-token lint passed. The final full TypeScript build passed after the concurrent author-preview test typing fixes. The hosted B09 browser spec collects as one test without launching Chromium. These are fresh focused counts, not accumulated release-wide results. Hosted PostgreSQL runs must run the marked cases without skips using the existing postgres gate.
