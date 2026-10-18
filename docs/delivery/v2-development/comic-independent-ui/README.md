# Independent Comic editing slice

Status: partial implementation of IMAGE-COMIC-01/02/09, not full product acceptance or a release gate pass.

## Implemented ownership

- Original `ComicLayoutsService`, `comic_layouts_v2` collection and private Comic router remain authoritative.
- Explicit `INDEPENDENT` source mode permits no screenplay/shot binding and an empty page. Absent mode retains legacy screenplay semantics.
- Explicit `BLANK` artwork permits intentional empty/text-only panels; absent artwork mode still requires approved imagery. Blank panels reject asset/version bindings.
- Existing bubble text/geometry/type/font controls, local undo/redo, versioned save, history restore and CAS are reused. No model, task, image-generation or cost path is added.
- A nested Comic surface lives inside independent Image's asset workspace. It uses the original captured Studio transport, original Comic API gates and parent authority/dirty-navigation guards. No top-level module.
- New optional fields preserve absence during legacy serialization. Existing adapted review binding remains unchanged.

## Security boundary

Independent Comic rows bind the original Creative project's creation epoch. The shared composition hook supplies `comic_layouts_service.independent_store = creative_service.store`; no parallel store or widened Creative collection registry is created.

Original raw scope transaction → original asset Python lock → original asset-library coordinator → original project lease. Asset and project leases outlive the raw Comic commit. Independent reads/updates use existing-owner-only lookup; only legitimate new creates initialize an original project marker. Asset/character validation precedes provisioning. Unknown/unbound/previous-incarnation independent records are hidden and cannot be edited, restored, approved or exported. Existing-row source-mode conversion is rejected instead of discarding lifetime protection.

Independent static review found and verified correction of project/asset lock inversion. Tests instrument original lock ownership through create/update/approve commit and exercise threaded project deletion during File commit.

## Verification

- `comic-independent-epoch.json`: broader File regressions, 112 passed, 2 skips (real pinned CJK font unavailable), 70 PostgreSQL deselected.
- `comic-independent-final-locks.json`: newest blank/epoch/private/CAS/original-lock File contracts, 32 passed, 26 PostgreSQL deselected.
- `comic-independent-epoch-postgres.json`: real PostgreSQL epoch + original Comic suites, 57 passed, 7 skips (6 File-specific contracts and 1 pinned-font test), 70 deselected.
- `comic-independent-cleanup.json`: final test-fixture teardown correction, real PostgreSQL new contracts, 20 passed, 6 File-specific skips, 32 deselected.
- `unit-final.log`: 94 tests across 7 files, mounted Image/Comic components and original independent navigation/Comic editing/duplication/arrangement.
- `typescript.log`: TypeScript noEmit exit 0, no diagnostics.
- `visual-unavailable.log`: attempted Image baseline + four protected shell geometry checks; all five could not launch missing Chromium headless shell. No visual assertions ran, no browser installed, no baseline updated. Not browser E2E acceptance.
- `source-sha256.json`: final owned product/test source hashes. Shared composition injection belongs to the Story owner. Git remains uncommitted by this worker.

Earlier failure logs are retained: worker-count conflict before any UI tests, then missing jsdom URL API mock in new fixture. The fixture mock was corrected; no runtime workaround was introduced.

## Disposable PostgreSQL cleanup

Only existing PostgreSQL 17.11 / UTF8 test database `v2_recovered_ocr_export_20261018`, OID 16384, was reused. No database creation or migrations. Runner shutdown and separate pg_ctl status confirm stopped; see `postgres-stopped-final.log`.

The first epoch fixture version left two synthetic orphan scope documents because that table has no FK cascade. Exact identities, expected Comic-only synthetic content checks, absent live project checks and exact-ID deletes are recorded by `verify_fixture_cleanup.py` / `fixture-cleanup.json`. Final corrected fixture uses a finally block over exact project IDs it created. Post-rerun counts for its scope rows and projects are both zero. Full pre-delete document bodies/hashes were not captured before the additional evidence request arrived; no reconstruction is claimed.

## Remaining gaps

- Existing authorization resolves NOVEL-domain project grants. An IMAGE-only actor is explicitly denied; opening the Image module grants no permission. This is a remaining role-compatibility product gap.
- All original `comic_layouts_v2`, `asset_lineage_v2`, `ai_director_v2` gates remain. The independent Image entry itself retains its original `narrative_production_v2` gate. No silent feature enabling.
- Full book/chapter/page/layer hierarchy, advanced recovery/duplication at all levels, bubble tails/vertical typesetting/spacing/alignment, full external-image continuation and remaining IMAGE-COMIC requirements are not claimed complete.
- Save/reopen works without renderer or font. Raster preview/export still reports genuine renderer/font blockers and still requires explicit current approval for export.
- Source tests and controlled HTTP component tests are not a substitute for real interactive product acceptance, visual verification, a packaged runtime build, or all twenty Comic requirements.
