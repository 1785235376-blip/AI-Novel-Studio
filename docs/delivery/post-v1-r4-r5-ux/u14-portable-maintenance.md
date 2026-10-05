# U14 portable maintenance completion

Date: 2026-10-05. Original U14 implementation, with A09 preservation boundaries.

## Exact gaps closed

- Relink preflight previously exposed a digest-match boolean without the hashes or chapter impact. Its public record now contains the original and candidate SHA-256 values, the selected chapter IDs/titles and captured versions, and explicit digest conflicts. Authorized record refresh compares current chapter versions/source privacy and original missing-media state. Changed dependencies block confirmation and require a fresh preflight.
- Restore previously replaced a missing asset reference with a new missing ID but discarded its expected digest. The original import declaration now persists in the new project's existing scoped metadata store, bound to its actor and new missing ID. Its digest and media kind survive service restart and a second portable export; an exact candidate can be relinked without falsely reporting an unknown original digest. This declaration is not an asset library or a permission grant.
- Storage history is measured through the original chapter history authority for authorized, active local chapters. Scoped/custom history without a suitable authority remains unmeasured. Owned preserved import/relink files, non-rebuildable export files and staged assets are reported separately; unreadable inputs are explicitly excluded from measured bytes and retained.
- UI shows a readable relink impact/conflict report, an inspectable missing-media manifest and exact eligible cache list. Failed confirmation reloads the report, clears approval checkboxes and retains the selected local file.

## Boundaries preserved

The existing archive format, bounds and safe decoders are unchanged. Chapter edits still use the original version-aware writer; original assets, old revisions, trash and recovery inputs are never cleanup candidates. Partial writes remain checkpointed `RECOVERY_REQUIRED` records and are not retried automatically. Legacy preflight records without the full review report remain readable but require new preflight before mutation.

Only currently authorized chapter metadata appears in reports. Hidden/inaccessible asset metadata and another actor's imported recovery declaration are not exposed. The original missing reference is checked again before asset creation and at each chapter write boundary. No source text, host paths or binary input is added to public conflict responses.

The storage figures are content/recorded byte projections, not an operating-system disk-usage total. History covers authorized active local chapters, not all archived/scoped versions. Staged asset bytes use the original asset registration; preserved file bytes require their saved digest. None of these measurements expands cleanup authority.

Feature defaults, V1 force-OFF, shared shell/tokens, branch-write restrictions, API composition, workflow/job authorities and frozen PR37/38 remain unchanged. No paid provider, user key/manuscript, runtime configuration, deployment or merge was used.

## Verification

Executed with the isolated `../r2-run.sh` harness, original Python venv and pinned pnpm:

- `python -m pytest -q tests/test_r4_portable_maintenance.py tests/test_r4_portable_batches.py tests/test_r4_portable_batches_mounted.py -m 'not postgres_backend_only'`: **72 passed, 61 deselected**. Includes 14 new File maintenance cases, both mounted API prefixes, exact restore/re-export/relink, original-authority drift, privacy/actor boundaries, partial recovery, history measurement and cache/input preservation.
- `pnpm -C frontend exec vitest run src/experimental/PortableProjectsPanel.test.tsx src/experimental/PortableProjectsPanel.maintenance.test.tsx src/ui/AppShell.test.tsx src/ui/primitives.test.tsx`: **33 passed**. Covers explicit consent, hash/version rendering, conflict blocking/refresh, retained file selection, incomplete measurement display and inspectable missing manifest, plus existing StrictMode/unmount/scope-change and shell/primitive contracts.
- `pnpm -C frontend build`: **PASS**; existing large-bundle warning remains.
- `pnpm -C frontend lint`: **PASS**, UI token guard.
- `git diff --check` on owned files: **PASS**.

Real PostgreSQL: **NOT_RUN locally**; 14 maintenance cases retain the existing marked real-DB fixture matrix for execution with `TEST_POSTGRES_DATABASE_URL`. No in-memory substitute is reported as PostgreSQL evidence.

Browser visual/geometry execution: **NOT_RUN locally**, because Chromium EPERM was already established for this environment. No browser retry, new screenshot acceptance or visual claim was made. The canonical NOVEL reference, design system and component rules were inspected; only existing feature-panel primitives were consumed.
