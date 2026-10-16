# Wave 5: Template Library, SDK and Comic/Webtoon closure

Date: 2026-10-06. Reconstructed continuation on official baseline `4d736c0d14bdcd12d0ad3cc7146553971654620b` (tree `6b8269fb95e695178ce4c587c9fc729275d0e848`). Historical PR #37–#42 evidence is unchanged. This receipt describes the owned sources listed and hashed in the companion JSON, not a final published-head or hosted acceptance result.

## Original features and implemented changes

| Feature | Concrete continuation | Boundary |
| --- | --- | --- |
| B01 Template Library | Novel, Genre, World, Agent and Story Structure starters; strict compatibility and permission manifest; original Agent definition instantiation | IMPLEMENTED / CONTRACT_VERIFIED for declarative imports and File persistence. Overall PARTIAL: generic creative types remain independent editable briefs. No Marketplace or automatic manuscript/Canon creation. |
| B02 Custom Agent / Workflow / Adapter SDK | Persisted finite capability/runtime requirements and visible input/output contracts; trusted local SDK input/output validation | IMPLEMENTED / CONTRACT_VERIFIED. Original Workflow, broker and bound-model coordinator remain authoritative. Real model quality and third-party runtime integration NOT_RUN; executable third-party plugins DENY_ALL. |
| B06 Comic / Webtoon | Panel image brief, approved original-asset character appearance references, scene/shot/reference export lineage | IMPLEMENTED / REAL_VERIFIED for bounded File persistence and synthetic raster output; CONTRACT_VERIFIED for scope/version/privacy rejection. Overall PARTIAL: model artwork quality and external production typography NOT_RUN. |

### Template authority and compatibility

`TemplateLibraryService` remains the catalog/copy/history authority. The original nine-item `items` and seven `types` remain intact. `extended_items` and `extended_types` add five required categories; the existing panel combines both projections. `builtin_packages()` retains its original nine packages.

All imports reuse bounded JSON, strict fields, byte/depth limits, manifest version, CAS installation, preview digests, independent copies, favorites, compare/update/history and restore. Compatibility requires `LOCAL_BOUNDED_JSON_V1`, schema 1 and `READ_ONLY_DECLARATION`. Execute, network, manuscript-write and capability grants must be false. Unsupported protocols, schemas, executable declarations and privilege escalation are rejected.

Agent templates reuse `WorkflowAuthoring` and create `DeclarativeAgentsService.DEFINITIONS` in the same scope transaction. Mandatory review remains; copying creates neither a run nor a dispatch. Novel/Genre/World/Story Structure copies are independent editable briefs. Existing Planning/Workflow authority is unchanged.

### SDK contract

The existing Agent form stores `capability_requirements` (`LOCAL_RULES` / `TEXT`) and `runtime_requirement` (trusted local rules / original bound local model). Contradictions and unsupported capabilities fail before persistence. Catalog/preflight expose effective runtime, finite input/output schemas and no-grant boundaries. A declaration cannot enable a model, register executable code or authorize cloud fallback.

`AdapterCapabilities` adds optional finite scalar schemas and explicit runtime/model capability. The trusted local host checks inputs before dispatch and outputs before a receipt; rejects runtime/model mismatch; preserves cancellation, timeout, bounded retry and authorization fences. This is a trusted in-process seam, not a plugin sandbox or dynamic loader.

### Comic source chain

`ComicPanel` gains bounded `image_brief` and `appearance_references`. Each reference points to a panel character and an approved original asset with an expected version. Duplicates, nonpanel/unknown characters, unapproved/missing/cross-project assets and stale versions fail closed. Original Director character digests, screenplay evidence and asset lineage/privacy bind the layout.

Save/review/restore/restart use the original `comic_layouts_v2` records. PNG rendering is unchanged. Export adds `panel_sources` and bound asset metadata to its existing manifest without regenerating assets. Editing a brief or reference creates a new draft requiring fresh review. The existing panel supplies brief, appearance selection/note and scene reference, preserves undo/redo, and hides an opened saved document after the server marks it stale.

## API, persistence, flags and rollback

No new routes, feature flags, authoritative registries or SQL migrations. Additive fields travel through the existing template-library catalog/preview/instances endpoints, declarative-agents catalog/preflight/definitions endpoints, and comic-layouts catalog/records/review/restore/export endpoints. Existing default-off, V1 acceptance override, current-actor, project, branch, dependency and permission checks remain.

The original atomic File/PostgreSQL scope store persists the additional metadata. Reads do not rewrite legacy declarations. Normalized semantic comparison permits unchanged old manifests without a false version-bump requirement. Old comic records without the new fields read/export normally; explicit restore writes a new draft with defaults and preserves history. Backend-parameterized tests cover these upgrades.

Rollback: disable experimental flags and retain the data. Older strict writers must not rewrite new template kinds or Agent fields. No destructive conversion, container deletion or replacement of V1 user data is supplied.

## Current reconstructed validation

- Fresh seven-suite backend aggregate: **160 passed, 142 skipped, zero failures/errors**, 35.69 seconds. Includes restored Wave 5 tests plus original template, bound-model, mounted Agent, job-bound, comic and mounted comic suites.
- The 142 skips are PostgreSQL parameters without an authorized disposable local endpoint. The original pinned CJK font/OFL rendering and export case ran and passed. No assertions or skips were weakened.
- Python syntax and `git diff --check`: PASS.
- Four UI contract tests and two real React/File API browser journeys are fully restored. Fresh frontend focused aggregate: **44 passed**. Full current TypeScript check and 42-file token guard: **PASS**. Both browser journeys were collected with `--list`; browser execution and fresh screenshots remain **NOT_RUN locally**. Verified restored locked dependencies were invoked directly; no local Chromium was launched.
- Browser journeys cover additive catalog and original Agent/SDK persistence, comic brief/reference reload and stale-source rejection, no model dispatch, and screenshots/overflow at 1366×768, 1440×900 and 1920×1080.
- Real PostgreSQL, model/GPU, third-party software and artwork-quality acceptance: **NOT_RUN locally**.
- Official exact-source hosted CI: **pending exact-source publication and hosted verification**. The companion receipt contains `official_ci: null`; no hosted success is inferred. Initial fresh checks before the font became available recorded 159 passes/143 skips; the explicit font-enabled result above is a separate fresh run. An initial package-manager version mismatch stopped before UI tests; the successful check used already-restored executables without installing dependencies.

Historical pre-reconstruction results were 160 backend passes/142 PostgreSQL skips with the pinned CJK font, 44 frontend passes, token guard PASS and two browser cases collected. Those results belong to the earlier execution environment and are **historical only**, not current reconstructed validation. Raw infrastructure logs are excluded from public delivery; the companion JSON contains compact measured results and owned-source hashes.

## UI handoff and public references

The existing TemplateLibraryPanel, DeclarativeAgentsPanel and ComicLayoutsPanel remain inside the shared workbench. New controls consume existing Panel/Field/Button/StatusMessage/Details and `.experimental-*` layouts. No protected shell, tokens, primitives or CSS changed. Preserve read-only mounting, explicit copy/review, no automatic runs, source/version/privacy fences, hidden stale material and local-draft conflict behavior. Final visual approval remains separate.

Public references: `POST_INTEROP_FEATURE_MATRIX.md`, `POST_INTEROP_R4_R5_CONTINUATION_REPORT.md`; frozen `docs/delivery/post-v1-r4-r5-ux/{FEATURE_MATRIX.md,FEATURE_MATRIX.json,FINAL_DELIVERY.md,SCOPE_RECONCILIATION.md,ACCEPTANCE_RESULTS.md,B01_B02_LOCAL_DECLARATIVE.md,B02_BOUND_MODEL_RECEIPT.md,U16_DOMAIN_ADMISSION.md}`; `docs/ui/{design_system.md,protected_ui_surfaces.md,visual_baseline.md,reference/novel_workspace.png}`; source/tests in the companion inventory.
