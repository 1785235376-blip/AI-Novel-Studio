# Persistent nested display groups — 2026-10-18

## Ownership and compatibility

Display views now optionally carry up to 64 named groups, with unique/disjoint card membership, at most eight parent levels, and persisted collapsed state. They remain schema-1 display records under the existing Creative Graph/Asset/project-incarnation owners. They do not contain executable ports or nested execution engines.

Absent groups are omitted by an explicit model serializer. Legacy definitions, request digests and record integrity retain their original no-groups shape. Explicit null/empty group fields are rejected; removing all groups omits the field. Original 1000-card, 512,000-byte definition, history/record/scope capacity and actor isolation remain unchanged. Duplicate group/member IDs, unknown cards, orphans, cycles and excessive depth fail before persistence.

## Editor

The original display editor adds explicit create/rename/parent/member controls, collapse/expand and dissolve-with-cards-preserved. Removing a card cleans its display memberships. Removing a group promotes its children to that group's parent. Names and hierarchy are validated before changing the local draft; original explicit Save/CAS/reopen remains required.

Group frames show recursive member bounds. Collapsing an ancestor hides descendant cards and child frames but leaves one reopen affordance; no media is deleted and no task starts. The 128-card rendered bound is retained, plus at most 64 bounded group frames. The minimap continues to show all card locations, including collapsed ones. Group operations currently act on the selected card; professional multi-selection/group dragging and reusable executable subgraphs remain separate gaps.

## Evidence

- File service/API/catalog regression: 28 passed.
- Real PostgreSQL service/API regression: 24 passed, database OID 16384, stopped.
- New mounted nested-group create/save/reopen/invalid-cycle tests at both prefixes: File 2, PostgreSQL 2 passed; no model-host admission required for display schema one.
- Public manifest/real PUBLIC wheel/metadata: 3 passed.
- UI/client/geometry regression: 46 passed, TypeScript and production Vite build passed.
- Added collapsed-frame interaction check: 12 passed with existing pointer cases, TypeScript passed. Only tests changed after the production build.
- Catalog remains 2375 operations; source fingerprint 629d579c3d4598b0af0c2faf4f08611be174240eb793d065a30d89275fa5db7a.

Evidence receipts and original logs: `docs/delivery/v2-development/canvas-display-groups-*`.

No live browser rendering/FPS or whole-product acceptance is asserted. File/PostgreSQL persistence and frontend fixture checks are separate layers, not a browser-to-database end-to-end substitute. No Prompt gate, original execution-node limit, public/private isolation, main branch or Release was changed.
