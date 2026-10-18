# Current mounted API catalog reconciliation

2026-10-18. Exact product source: 2c0e0fdc9608b6a706a083fd5b68d089d99c18f1.
Staged tree: 37ecd56e5ebabd3c5733e1a1286577b9073954b0.
Application source fingerprint: 6c6d8296a0762bd40b2b4efaac606d6923a38508b930f64d97d2d0c671db94a6.

The original refresh_v2_staged_catalog.py --compact generator updated the four
current catalog artifacts from a hash-verified immutable staged snapshot, not a
mutable working-tree import. The snapshot retained 3,614 regular source files
(46,093,728 bytes), excluding exactly historical docs/delivery evidence. An audit
hook refused reads from that excluded directory and checked that project-module
imports remained inside the snapshot. Captured import origins and generator log
are retained beside the generator's original receipt.

Results: 2,315 → 2,359 method/path entries, 44 newly catalogued, zero removed.
The 44 include both /api and /api/v1 aliases; they are not 44 new features. They
cover previously implemented Director model-v2 review routes, GLB/reference/clay
operations, the Bailian text preset, source-bound timeline inspection, Director CSV
and the new Storyboard CSV. Cataloguing never enables a gate or dispatches them.

Six unchanged catalog/discovery-annotation checks passed in an isolated owned
profile: current application-source hashes, complete OpenAPI/schema/owner binding,
retained real owner references and current discovery-host provenance. No baseline
assertion was weakened. This is source metadata reconciliation, not a runtime
permission audit, PostgreSQL/browser/model execution or full product acceptance.
No app/frontend implementation, historical freeze report, private backend exclusion,
Prompt adoption switch, main branch or formal release was changed by this slice.

Original evidence:
- catalog-37ecd56e5eba-compact-0ba7646c43004cc58470940d15a56ae3.json
- current-api-catalog-generator-20261018.log
- current-api-catalog-import-origins-20261018.json
- current-api-catalog-20261018-green1.json and .log

The containing commit publishes the reconciled metadata. The original temporary
snapshot remains local until any recoverable compaction is independently verified.
