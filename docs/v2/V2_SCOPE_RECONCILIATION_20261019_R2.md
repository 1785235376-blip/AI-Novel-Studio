# V2 r2 scope reconciliation and fixed-ID ledger

Current scope: GAP-BACKLOG-2026-10-19-r2, incorporating SPEC-2026.10.19-r1. This is a documentation-only reconciliation, not a release declaration or a product-test report.

## One current index, preserved historical sources

The [machine-readable requirements ledger](V2_REQUIREMENTS_LEDGER_20261019_R2.json) is the canonical current reconciliation index. It links original requirements and matrices rather than replacing their historical facts. Update each ID there and attach exact-source evidence; do not create another competing completion matrix.

- [Original Master matrix](../../AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md): 312 unique fixed IDs from 352 table occurrences. Repeated rows/addenda are kept as references to the same ID.
- [Original package matrix](../../POST_INTEROP_FEATURE_MATRIX.json): F00 plus A01–A13, B01–B10 and U01–U16.
- [Original functional surface matrix](../../FUNCTIONAL_SURFACE_MATRIX.json): 73 IDs = the same 40 package IDs + 19 FS_ + 14 CORE_ surface IDs, not 73 new independent features.
- [Original detailed FSR register](../delivery/functional-surface-freeze/REQUIREMENTS_REGISTER.json): 406 records are indexed by ID and retained by reference. They include constraints, section context and acceptance gates; their current behavior has not been fully reassessed.
- New entries explicitly enumerate DIF-01–12, IMAGE-COMIC-01–20 and E2E-01–07. Backlog PATH-1–6 is normalized to existing PATH-01–06; no duplicate five-path family is created.

There are 425 linked primary entries. This is an indexing count, never a feature count, workload estimate or progress denominator. Old 13/12 gap groups are old-scope findings only. No current product percentage or completion date is established.

## Historical initial source identity and reading coverage

The committed baseline and remote observation below describe the initial reconciliation, not the latest product or archive. The ledger current_checkpoint and latest_bounded_wave identify the subsequent product checkpoint; dated delivery reports preserve each wave's exact evidence.

Committed baseline: `work/dot-recovered-20261018`, product `e96b749ad7cd6eab29befe0db051c9e1fbf4a060`, documentation HEAD `2c210ebed487052b8ed327f63a7d762d3a0d3e75`, tree `78f4415b896e661f826edb27d93e72e0e21df53e`. Initial read was at 9ccac0be; camera/benchmark are now committed bounded additions. Later in-progress Story/Impact work is excluded from this snapshot.

The uploaded r2 TXT was fully read in contiguous ranges 1–220, 221–440, 441–660, 661–880, 881–1100 and 1101–1326 without truncation: 1326 lines / 134744 bytes, SHA256 `0fa7530806476c6a8e4e53e207e468ea6c6ed93b55f3a155796c8fde694b0fd8`. Appendix B embeds all 351 lines of the SPEC from line 976 through 1326. The ledger records the embedded-byte digest; no comparison to a separate standalone SPEC attachment is claimed. The full input remains the detailed scope source and is not copied into these public-facing documentation summaries.

The original 904-line Master source hash is `c4a8892d1c4a3b1398cc5a5496610294be31bf9c245d59be10f8f570991f7b74`; its [recovery record](MASTER_ROADMAP_SOURCE_RECONCILIATION_20261018.md) preserves full-read evidence. The distinct 167-line frozen continuation hash is `ebabfe5314d9ed4535814baaca295ec6db0f17e5541d4dc35a6ed16805c129f4`. This documentation pass did not reread those two originals in full.

The coordinating root reports a fresh anonymous, read-only `git ls-remote` observation at 2026-10-18 18:20:36 UTC: main `fed2404c8e30b44061b7139dced45b7f3301601c`; PR47 `a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3`; PR48 `58bbaad11360330d51f49fc2bb78a955a26469f0`; archive `0e5cd80918e8022bee1f94f9295b22c206e0ac77`. All were unchanged. Archive HEAD is not product source HEAD. The documentation worker did not rerun that observation or publish anything.

## Scope and evidence precedence

Original mandatory V2 scope plus all 12 DIF and 20 Comic requirements now share one formal Release Gate. The new SPEC overrides suggestions to defer those enhancements to V2.1/V2.2/V3; original Owner, safety, permissions and V1/RC1 freezes remain. Comic is an Image Studio sub-entry. DIF labels are shared capabilities, not twelve new top-level products.

Development remains incremental and tested. Final independent system acceptance must use one candidate SHA, with affected regressions rerun after changes. Code status and formal acceptance are separate ledger fields: `PARTIAL` means bounded reuse, `NOT_REASSESSED` means this pass does not decide the full current implementation, and `NOT_ACCEPTED` does not erase historical focused passes. New full-scope SPEC entries remain `PLANNED` until their complete implementation/integration is established; none is marked ACCEPTED here.

Deferred production cloud synchronization, realtime same-manuscript collaboration and full DCC remain deferred. This does not excuse bounded B08/B10 or the newly mandatory minimum Blender/UE exchange, Ren'Py/Ink adaptation, ORA/CBZ/fixed-layout EPUB and Passport credential/sidecar requirements.

## Current-source corrections

- Restored local source already contains later canvas, Director, native OCR/PDF, static GLB, media and Timeline increments. The attachment's old PR47/ordinary archive-tree audit is historical, not proof these are absent locally.
- `GraphDirectorProposalReview` and `GraphDirectorStoryboardHandoff`, mounted by `GraphDirectorConsole`, already reuse original suggestion/review/draft/UNKNOWN owners. The separate read-only `StudioGraphDirectorConsole` does not establish that the entire current Director chain is read-only.
- `story_graph.py` already has World-owned time intervals, knowledge events and fact/belief/speculation layers. `change_impact.py` already provides bounded dependency/selective-refresh behavior. Full new cross-media semantic coverage still needs integration; no second Canon or execution queue is justified.
- Comic now has an Image Studio sub-entry and independent blank-page/panel/editable-text save/reopen through original Comic owners, plus book/chapter/page ordering and native reference layers. Legacy adapted layouts still require their screenplay/Shot sources; original NOVEL grants remain required, so IMAGE-only role compatibility is open. The supported flat-raster ORA import/recovery/review/attachment/edit/export workflow and bounded CBZ, raster PDF, JPEG/WebP ZIP and fixed-layout raster EPUB reading copies are integrated. Live layered pixel editing, broader ORA semantics, external-editor/reader/platform acceptance and full native portable restoration remain open. The bounded assetless independent PAGE author archive now preserves editable native text/geometry/layers in fresh draft books; media/assets/sources and WEBTOON remain unsupported. See story-comic-director-integration-20261018.md, image-ora-workflow-integration-20261018.md and comic-epub-integration-20261018.md plus comic-author-integration-20261018.md under docs/delivery/v2-development.
- The committed static-camera and video-benchmark slices map to parts of DIF-05/DIF-08. Root reports integrated UI193 plus TypeScript/Vite/token, PUBLIC6, real camera PG107 and benchmark API40 File/40 PG; these are bounded, non-additive evidence and were not rerun by this documentation worker. Canonical camera data is not verified native DCC acceptance; benchmark orchestration observations are not measured VRAM, model quality or real billing.
- The latest bounded Shot Board image comparison is already recorded in source 9cc. Video sampling and controlled-transfer infrastructure remain partial within their stated limits. No old gap is blindly reopened or promoted.

## Next engineering order

1. Preserve the committed camera/benchmark wave, ongoing work and source/bundle ancestry; compare actual PR47/48 changes without reset, force-push or blanket replacement. Reuse the existing same-purpose recovery branch after verification.
2. In parallel where paths permit: deepen Graph/Director editable approval and complete the first Story/Impact source-to-downstream chain. Preserve typed-port, source, permission and exact-impact contracts.
3. Continue Identity/Style/Image and Comic depth from the integrated independent page/panel/text save/reopen, hierarchy, layer/ORA and bounded publication slices. Complete IMAGE-only permissions, live pixel editing, deeper authoring and native portability through original owners; preserve the distinction between model-free authoring and still-required project/domain authority.
4. Semantic Rebuild and Comic local reflow/motion handoff; then Scene Twin, Performance, Model Lab, Storyverse and professional media/NLE.
5. QA/Audience/Passport, actual output formats, original A/B/U/FS/CORE gaps, storage/model/project delivery and PUBLIC/PRIVATE closure.
6. Same-SHA independent final acceptance and separately authorized publication. Preserve raw failures, exact File/PG/frontend/build/media evidence and unrun target gates throughout.

The seven formal E2Es are long novel→film, novel→six-page color comic, blank/model-free→eight-page monochrome comic, thirty-panel vertical comic, story change→selective rebuild, comic→twenty-second motion comic and branching story→runnable interactive work. Old development PATH cases cannot substitute for them.

## Permission and publication limits

No product source, commit, push, merge, release, model invocation or test execution was performed by this documentation task. Existing publication authority must be checked before publishing restored runtime source on a new named branch; permission for append-only bundles on an existing archive does not automatically authorize a new public destination. No private exclusive implementation belongs in any publicly readable branch. Keep production Prompt Adoption closed and bounded execution limits intact. User-machine, paid API, credential/billing and other protected actions remain separately gated.
