# Native Research current-incarnation fence

## Reproduction and repair

The mounted V2 Research owner already stamped new imports with the original
CreativeProjectStore incarnation, but only exact historical inspection enforced
it. Deleting/recreating a public project ID left scoped source records present;
current metadata, original bytes, source history, citations and lists disclosed
retired records to the same actor. File and real PostgreSQL both reproduced five
failures before production changes. No original tests were edited.

Strict native Research now requires current project identity for native source
reads, archive/history bytes, restore, and downstream citation consumers. Old
notes cannot be rebound to fresh references, deleted, or inspected as new-owner
notes. Analysis receipts/actions must still belong to a current-incarnation
source; citation freshness and source visibility remain separate checks. Reads
do not provision identity. Unbound source/revision/legacy projections fail closed
in this mounted strict service, without automatic migration or rewriting old data.
The original legacy service default and its routes remain unchanged.

All mounted strict native operations except imports capture/recheck incarnation
at the original authority guard, including after projection; imports retain their
existing provision-before-extraction and before/after-commit identity checks.
The original scoped transaction and owner lock order are retained. No second
identity registry, owner, workflow, permission bypass, source purge or migration.

## Evidence

- baseline-file-r1/r2 and baseline-pg-r1/r2: each 5 FAIL, 5 deselected.
- research-current-incarnation-file-r1: 92 PASS, 92 deselected.
- research-current-incarnation-file-r2: 104 PASS, 104 deselected.
- research-current-incarnation-pg-r1: 104 PASS, 104 deselected.
- Fresh GREEN PostgreSQL 17.11 database v2_research_incarnation_green_20261018,
  OID 29071, empty-before-migrations probe, all 20 original migrations, confirmed
  owned startup and terminal server stop. RED database OID 28200 is distinct.
- Original source/history/mounted-route regressions plus additive source/list,
  legitimate fresh owner, note rebind, stale-note repair, unbound revision,
  non-provisioning, analysis receipt and post-projection recreation cases.
- Persisted snapshot archive and SHA manifest beside delivery receipts includes
  actual RED and GREEN scope JSON, retained old records, and fresh-owner proof.
  Synthetic fixtures clean PostgreSQL rows only after assertions/capture.

## Limits

This is the mounted native Research boundary, not an audit or migration of all
legacy V1 sidecars or all experimental modules. Retained records still count
against existing storage quotas; no storage-erasure decision is implied. No
actual OCR/model call, product browser acceptance, Windows acceptance or full V2
release claim. Backend-only change: no frontend or production bundle changes;
focused Python checks replace redundant frontend rebuilds for this slice.
