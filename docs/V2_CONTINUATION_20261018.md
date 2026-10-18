# Studio V2 current continuation checkpoint

Updated 2026-10-18 20:50 UTC. This document inventories bounded additions, not a
replacement for the frozen feature matrix or a V2 percentage/Release declaration.
The source pin below identifies the latest bounded implementation; archive and product heads remain distinct.

## Source and publication

Current checkpoint: 2026-10-18 20:50 UTC. Working branch:
work/dot-recovered-20261018. Latest committed product source is
79fbb1e5d80574e513cd51c09b54118b12c80d90 (guarded IMAGE/ORA UI and font closure).
Latest byte-verified public archive is
b6e00c9d5601140760fc97c98d99569ed7242afa on
archive/verified-studio-v2-20261017-5a6f697. Archive HEAD and product HEAD are
different identities; the archive stores prerequisite-bound incremental bundles.
The restored local source contains the integrated working product, whereas the
archive branch's ordinary source tree is not the current product tree.

Anonymous remote ref inspection at 18:20 UTC confirmed:
- main fed2404c8e30b44061b7139dced45b7f3301601c
- PR #47 head a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3
- PR #48 head 58bbaad11360330d51f49fc2bb78a955a26469f0
- archive 0e5cd80918e8022bee1f94f9295b22c206e0ac77

The new GAP-BACKLOG-2026-10-19-r2 was fully read: 1326 lines, 134744 bytes,
SHA256 0fa7530806476c6a8e4e53e207e468ea6c6ed93b55f3a155796c8fde694b0fd8.
Its appendix B includes SPEC-2026.10.19-r1. DIF-01..12 and
IMAGE-COMIC-01..20 join the same formal V2 gate alongside the original frozen
requirements. Old grouped gap counts and percentages are historical and cannot
measure this expanded release scope. The fixed-ID reconciliation is recorded in
docs/v2/V2_REQUIREMENTS_LEDGER_20261019_R2.json and its companion scope report.
Its 425 linked IDs are an index, not equally weighted features or a percentage denominator.
No new requirement is accepted merely because it has a similarly named owner.

Camera and video benchmark work is committed after targeted File/PostgreSQL,
193 combined UI tests, TypeScript, production build and six PUBLIC artifact checks;
3036 checked source paths match the committed source. It is not expanded into
further P5 work. Next priority is the existing Story/Impact and
Graph/Director owners, followed by standalone model-free Comic editing inside
Image Studio. Actual target-software and final release acceptance remain separate.

These archive uploads do not update the PR source branches. No main merge,
force push, formal Release, paid API, new quota or user Windows/GPU work occurred.
Publishing a new public integration branch remains distinct from local integration
and existing archive uploads; no new branch was pushed in this checkpoint.

## Evidence since the earlier checkpoint

- Research current-incarnation guards: 7de2fb4; actual File and PostgreSQL failure
  reproductions followed by focused passing suites; 74 synthetic persisted snapshots
  were approved, archived and byte-verified. See docs/v2/RESEARCH_CURRENT_INCARNATION.md.
- Director PostgreSQL terminal/pending review: 80b42c8, with e0fc391 structured
  SCREENPLAY HTTP follow-through. Original owners and durable review identity reused.
- Director author work: b7f5e5e local draft backup, 8e4a7a4 note ordering/duplicate,
  3a7b3b3 source-pinned CSV. Backup is not automatic server saving or imported authority.
- GLB reviewed clay preview to original Asset: 7141939 and 2f420b7. Explicit source
  pin, review hash, confirmation and idempotent save; File/PG boundaries and UI checked.
- Reviewed Graph writing brief to personal composer: 6990d74 and 94239d2. Original
  run/graph rereads, text equality and explicit adoption; identity/license and install
  remain separate. No external marketplace or real-model quality claim.
- NLE source bounds and explicit local-draft shortening: 9923494 and 0ceb48a.
  PCM16 diagnostic checks actual source bytes; no automatic rewrite or broad codec claim.
- Public closure repair: 0e8adc2 adds six omitted STANDARD modules to the original
  allowlist. 57 packaging/adversarial checks and actual offline public wheel passed;
  wheel, receipts and scan archived in public-closure-20261018-0e8adc2. Private backend
  exclusions and safety rules were not weakened. Test wheel is not a V2 Release.
- Read-only scene/shot navigation: b67e01c. Navigation/search outside editing lock,
  original write permissions unchanged.
- Optional Tutor floating presentation: 8db2a35, 79 focused checks plus type/build.
  Input/selection avoidance is best effort; existing consent/authority/close owners
  retained. Live2D and detailed native voice work remain outside this slice.
- Independent Prompt draft reuse: de24555, 53 focused checks plus type/build.
  Original create owner, bindings cleared, no inherited approval/request identity.
- Canvas visual membership editing: ad6b524, 101 focused checks plus type/build.
  Transfer/ungroup through original history, empty-parent promotion, no node/edge loss.
- 2a6f0793: session-only timeline cache speed/loop options, 44 focused checks
  plus type/build. No regeneration or exported clip speed change.

Counts overlap across slices and are not a feature-completion numerator. Individual
reports and original runner receipts retain exact source maps and acceptance limits.

## Recovery and later bounded additions

At 09:39–09:41 UTC the cloud executor disconnected and returned an older filesystem snapshot. The existing public archive base and 49 incremental bundles were verified and imported without resetting unrelated work. Source 4de76c72 was restored exactly; lost uncommitted TXT export work was reimplemented and checked rather than claimed recovered. See the recovery evidence committed with bfe44d71. Tests now use a clean dependency-only interpreter, not the donor editable checkout. A fresh UTF8 disposable PostgreSQL database OID 16384 replaced the lost prior test runtime; the retained first SQL_ASCII bootstrap failed honestly before tests.

- Native PNG/JPEG OCR now has host-pinned program and language files, original job persistence/execution, private broker admission, source-incarnation-aware Research review, explicit UI preview/dispatch/reopen, and reviewed TXT export. Relevant documents begin LOCAL_TESSERACT_OCR, LOCAL_OCR_HOST_SETUP and RESEARCH_NATIVE_OCR. The general synthetic adapter guard was not relaxed.
- 4de76c72 corrected the UI's derived-citation shape after a prior matching synthetic fixture concealed the mismatch. Corrected tests use source/result digests; earlier green evidence was not relabelled.
- 7e35a549 retains original incarnation leases through Research commits. A deterministic failing-before regression and passing File/PG checks are retained; no cross-project exploit is claimed from that ordering test alone.
- 58197ffc adds explicit trusted-host interruption recovery. Operator stop attestation, actor/incarnation/job/ledger checks, no automatic inference replay and idempotent two-owner retry are covered. File 9, PostgreSQL 9, related UI 20 and actual PUBLIC package checks passed. Restart tests inject queued persisted state, not actual process death.
- d9f72589 adds confirmed local Director-note removal through original Save and history. React 23, File 1 and PG 1 checks passed, including unchanged stored state before Save and history restore.
- 4f1b18ec adds bounded local pronunciation-rule text preview with a shared Save parser. One Python shared-contract check, React 27 and strengthened mounted 7-case rerun passed. This does not synthesize or evaluate voice quality.

Each implementation report states its exact acceptance boundary. Updated structural inventory is current-source-inventory-20261018-late.json, pinned before this documentation commit. Its 101 rows remain inventory, not percentage or complete audit. Older inventory remains historical evidence.

## Additions after 10:40 UTC

- fd8ad26d and e32f904f: real failing-before native-provider/runtime readiness checks repaired original packaged-Windows marker handling. Offline checks and PUBLIC wheels passed; this is not live API or clean Windows acceptance.
- 407d7988: original Director-note timing tools, local preview/confirmation/undo, retained source associations and explicit Save.
- 70716295: explicit SCRIPT → SCREENPLAY staging using exact text chunks, original Creative DRAFT/history owner, original downstream Director review chain. No semantic AI scene analysis or direct SCRIPT model admission claimed.
- 49ef1caa: explicit scene ordering preserves scene IDs/text/source and Director note associations. Original Save/CAS/history retained.
- efa890bd: PR47/PR48 source lineage proof. Seven PR48 changes are patch-equivalent and two boundary trees match local ancestors; no PR merge/update is implied. See PR48_SOURCE_LINEAGE.md.
- ab5a2179: original Graph-owned independent display persistence, up to 1000 Asset-reference cards, actual File/PG save and fresh-owner reopen. Execution limits remain 16/24 nodes; no binary read is needed for display metadata.
- f42f78e6: closed display GET/POST/PUT API at both original prefixes. Authority, actual body bound, sanitized errors, no execution routes; File/PG and PUBLIC packaging passed.
- a7000413: original-client media display editor, explicit Save/reopen, bounded viewport rendering, draft/unknown-save ownership integrated with original navigation. Not a browser E2E claim.
- 98e92fe1 and 7614ac87: guarded drag/pan/keyboard/anchor zoom and a single-bitmap full-location minimap. The main view renders at most 128 intersecting cards; raster tests are drawing-call spies, not browser pixels or FPS.
- 1bde91f1: explicit one-asset preview (32 MiB limit) through original AssetInspector after exact metadata, actual byte digest and fresh metadata checks. No bulk preload or automatic in-card thumbnails.
- 8e66c7b9: up to 64 persistent display groups and eight parent levels, explicit membership/parent/collapse controls and preserved cards on dissolve. Legacy absent-group serialization/request identity stays intact. File 28 + mounted 2, PG 24 + mounted 2, PUBLIC wheel 3, UI 46 + frame 12 targeted checks passed. These are display groups, not reusable executable subgraphs.

Latest archives are anonymously byte-verified append-only bundles on the existing archive branch. Latest source package includes original reports/logs, actual PUBLIC test wheel and frontend test build. No formal product release is claimed. The original node execution graph and the new media display view share owners/workspace, but a completed unified professional Director workbench is not asserted from this foundation.

## Explicit remaining development gaps

The accessible source audit still identifies production cross-device transport/encryption beyond the synthetic injected sync seam, and complete private Mature runtime implementation not evidenced in the public source. Public-package stripping itself is implemented and tested. Do not infer absence in inaccessible private code, and do not enable a hidden public endpoint.

For the current media canvas, local undo/redo and multi-selection/cohort movement/alignment now exist (5ffafb1b and c02be160). Next bounded work includes richer group batch operations, reusable display/workflow bridging, better source refresh/capacity recovery and final browser interaction/performance. Selected verified preview exists; automatic in-card thumbnails do not. Existing older Graph tools must be checked before duplicating functionality.

No reliable whole-V2 percentage is asserted: the 101-row structural inventory is not a completed-feature numerator, and the original 904-line master roadmap has not been recovered in full. Preserve the accessible frozen product anchor and actual source history as the continuation basis.

## Original P0 security evidence

The original project-retirement/permission inheritance fix was independently checked in ancestor 093c8f66bfd5172d08f6d2d724b9964f15fdf2af. Current restored source c02be160 was freshly rechecked at 12:26–12:29 UTC: File 43, PostgreSQL 38 passed. The first PG invocation omitted the original collaboration-runtime test option and had one setup error; corrected invocation passed without source/test changes. This is not a new fix or pre-fix rerun. Exact scope and preserved evidence are in P0_RESTORED_SOURCE_RECHECK_20261018.md.

## Remaining gates and next-source discipline

The end-to-end Director/Graph implementation has measured File/TCP and PG slices,
but current final-source product browser, installed Windows, real-model/GPU/media
quality and whole-product acceptance remain separate open gates. Earlier Windows
Edge browser evidence exists at older source and must not be relabeled as today's
final-source proof. The latest original-runner browser launch at 11:48 UTC failed because bundled Playwright Chromium was absent. Earlier installed Chromium was also blocked by its process sandbox. Public GitHub reads work. No browser download, sandbox relaxation, tunnel or denied-route workaround was used.

The historical GitHub Actions observation (last checked 03:09 UTC), run 39092404921, had eleven jobs with zero steps
and an account billing lock. No rerun, account change or purchase was made; archive
commits tagged skip ci are not CI test passes.

PROMPT_ADOPTION_WRITE_ENABLED remains False; R3-GATE remains HOLD. The public/internal
backend split is preserved. A/B/U and other historical PARTIAL rows are not promoted
merely because bounded additions exist. Inspect actual current owners before selecting
new gaps; do not redo features based on the old M0 matrix. Keep meaningful focused
checks with changes, reserve full product acceptance for the authorized final stage,
and retain failures. Continue serially while worker quota is unavailable.


## 13:30 continuation

- Fresh original P0 recheck is committed in 04bd8d40: File 43 passes and PostgreSQL 38 passes, original actual persistence tests and fresh-owner positive controls. The first PG setup omitted the required collaboration-runtime flag; its failure log is preserved. This verifies an existing fix, not a new security fix.
- Text graph templates e1e36dab and same-project version-pinned reference templates b9e24316 reuse original graph copy/history/save. Cross-project media rebinding and executable nested subgraphs remain open.
- PDF raster 3a9a0d85, model seam f2c4d516, passive source identity 535c06c3, and integrated original Research PDF loop 225e91ba form one additive chain. Final capabilities and boundaries are in RESEARCH_PDF_NATIVE_OCR_CLOSED_LOOP.md. Native PDF page OCR is now integrated, superseding earlier foundation documents' pending integration notes only.
- Final PDF integration evidence: File 55 passes, real PG 28 passes (server stopped), UI 11 passes plus TypeScript/Vite, actual public wheel/catalog 6 passes. No browser visual acceptance, Windows or general OCR quality claim. API count remains 2375.
- Existing archive d834820d contains through 535c06c3; the newest integration slice is being archived separately. Do not assume an archive HEAD is product source.
- Main and draft PR #47/#48 remain unchanged at the SHA values above. No additional fees or paid cloud/model calls.
- Next development focus returns to the professional Director/Graph workspace gaps. Display-card groups are not executable nested graphs. Preserve original bounded execution owners and current source/approval identity when adding any bridge.

## 14:26 continuation and requirements-source recovery

Source through ebaa6d55b7f13a56928f3939508b3c4051d69c80 is committed. Anonymous remote verification confirms archive 8e07964cb07542e1ce25e395b276269b8dbe6be7, parent f460c0d268806aa1e230db11f96b4deb44c65fd1, exact 12 files / 4,607,551 bytes, SHA256 and Git blob identities. This archive contains the incremental source bundle, original logs/reports, PUBLIC test wheel and frontend test build. It is not a release or PR update.

New bounded work since 13:30:
- a6757404: exact current Asset-reference handoff from a saved media view into the original Graph draft, explicit confirmation and no automatic edge/model execution.
- b36a492a: up to three original source-pinned Director consoles for explicit side-by-side comparison, with independent source/owner fences. Not autonomous parallel directors.
- bde00836: whole-definition media-card search and explicit offscreen location; collapsed ancestors open without deleting group membership.
- c4c618c6 and 5f939617: explicit selected-scene Director child drafts through original Creative derive, preserved source references/provenance and no copied approval or execution authority; generated OpenAPI component follow-through included.
- f385bb95: connection-disconnect structural impact preview before confirmed local change. Node removal/disable paths are not covered by this slice.
- 0e779476: explicit local media-view draft recovery, original owner/incarnation checks, exact saved base and current Asset pins, no replay of uncertain writes.
- ebaa6d55: optional persisted grid and bounded world-coordinate drag snapping; legacy absent settings preserve serialization. File 24, actual PG 10, frontend 29 plus TypeScript/Vite, PUBLIC/catalog 6 targeted checks passed. Grid pixels and complete real-browser behavior remain unaccepted.

The newly attached 167-line / 31,398-byte continuation TXT was read in full and compared byte-for-byte with docs/v2/frozen-product-anchor-20261016.txt. SHA256: ebabfe5314d9ed4535814baaca295ec6db0f17e5541d4dc35a6ed16805c129f4. It confirms existing frozen directions; it is not the separately referenced original 904-line Master Roadmap.

The original AI_NOVEL_STUDIO_V2_MASTER_ROADMAP.txt has been located in file metadata (71,777 bytes, originally generated 2026-10-09). Its content read was denied by selected-folder scope. The user has been asked to reattach that specific file. Do not treat metadata, search snippets, an earlier summary, or this continuation TXT as a full reading of the original roadmap. Do not route around the denied file access. Whole-scope reconciliation remains pending that original source.

Current catalog: 2375 operations, fingerprint 0cffb6cd9b7da52c73b4474346ed440763361f215c61f21d95afdfba6e6dacd1. Updated catalog, detail gzip and full OpenAPI gzip are committed. Existing API path set is unchanged by grid options.

Remaining development still includes unified professional Director workflow depth, executable nested subgraphs, cross-project exact-reference rebinding, additional change-impact paths, production cross-device sync, and private Mature implementation not evidenced in accessible public source. These are examples, not an exhaustive replacement for the master roadmap. Whole-product percentage remains unestablished. Browser/Windows/real-model quality and final product acceptance are separate from pure implementation status. Do not turn the 101 structural inventory rows into a completion percentage.

## 15:59 continuation

The original 904-line roadmap has now been read in full from the user's new attachment. Its earlier permission blocker is resolved, with source hash and precedence recorded in docs/v2/MASTER_ROADMAP_SOURCE_RECONCILIATION_20261018.md. Current implementation gaps versus existing code are recorded in docs/v2/CURRENT_DEVELOPMENT_GAPS_20261018.md; historical matrix labels are not completion percentages.

Source 3fe05b171e05f777dba6553c3fad185592b72774 includes independent original-owner audio-only timeline/WAV mixdown and exact Studio image/video task reopening. Final evidence: File 453 passes, real PostgreSQL 27 passes with server stopped, root UI 134 passes plus TypeScript/Vite/token checks, PUBLIC wheel/catalog 6 passes. Legacy schema-1 and schema-2 representative rendered video bytes and normalized digests match the explicit pre-change renderer. Raw failures and corrected evidence remain retained. Browser/Windows/whole-product acceptance remain separate.

Archive cd80964466c1ed9a5516c1925c7f8bba1f7db836, parent 1123171a3ce8f950b39d46be583ba3a9a4bc27bc, was anonymously read back: exact 12 files, 4,873,558 bytes and SHA256/Git identities. It includes the code/evidence bundle plus actual PUBLIC wheel and frontend test package. No PR update/main merge/Release implied. Current API inventory remains 2375 operations; fingerprint 262a95a653dcacda2d10686ecf7e13969f1781b6d63400dd5f1db6a9e19b3702.

Next active independent slices: A08 authored camera-geometry bridge into the original Creative Director workspace (supplementary evidence, preserving model analysis and rejecting invented model geometry), and basic schema-2 video clip color adjustment. Both are still in development; neither is marked complete. Root coordinates shared builds/catalog and exclusive PostgreSQL use. Other stale roadmap limitations must be checked against current source before coding.

## 16:32 verified continuation

Product source 501ff11b032b3113daea9e8e4dea24920a8f056a is archived in 7b9f70727fb9a21b2e4df4fc9f3da0d914440727, parent cd80964466c1ed9a5516c1925c7f8bba1f7db836. Anonymous Git fetch verified all 12 appended archive files, 5,660,516 bytes, exact parent/paths/SHA256/Git blob identities. Source bundle, original reports/logs, PUBLIC wheel and frontend test build are preserved; no Release or main/PR mutation.

This closes bounded authored-camera geometry, basic VIDEO clip color, implicit narrative progress and workflow dispatch-authority defects, plus offline JSON depth hardening. See delivery/v2-development/director-color-authority-wave-20261018.md for overlapping suite counts and limitations. Actual FFmpeg color and corrected colored/uncolored xfade outputs are preserved. Workflow evidence is File-only; PostgreSQL evidence for other features cannot be substituted. Browser, Windows and model-quality acceptance remain open.

Original roadmap access is resolved. Native workers are available again, superseding the earlier quota-unavailable instruction. Active next slice is layered-planning model generation through existing preview, Broker/JobManager, candidate and human-review owners. Canon provenance and caption styling are being inspected read-only before assigning independent implementation ownership. No implementation-completion percentage is established.

## 16:46 verified continuation

Product b99210e2abfdce3323532cd0b746dff70b1ab991 is preserved in archive 99cf43d81db834a5d4cef98fedea87e2cd884ade, parent 7b9f70727fb9a21b2e4df4fc9f3da0d914440727. Anonymous readback verified 12 files / 5,105,701 bytes and exact parent/path/hash identity. Catalog: 2393 operations, fingerprint 4a806a30586b77a22d0472ba5d128d5a00e4edd1e10466e78466c636632a2e12.

Layered planning now has a bounded original-owner local model bridge (File 64 / PG 64); Canon generation has exact accepted-revision evidence and honest explicit-marker extraction (File 86 / PG 62); schema-2 caption styling has real CPU proof and original timeline lifecycle (File 88 / PG 5). Root stable combined UI 171, TypeScript/Vite/token and PUBLIC/catalog 6 passed. All PG servers stopped and cleanup completed. See delivery/v2-development/planning-canon-caption-wave-20261018.md for precise limits and overlapping counts. Real model quality, browser and Windows remain unaccepted.

Next active work is ordered multi-chapter screenplay adaptation via the existing single-chapter adaptation engine, explicit Author sources, Broker, JobManager, archive and review owners. Preserve V1 single-source receipts. First bounded multi-source path must reject truncation and preserve exact order, per-chapter source/privacy identity and scene-specific attribution. This is under implementation, not completed. General Canon semantic extraction remains a distinct gap; explicit markers are not a substitute claim.

## 17:06 verified continuation

Product eb1a52577bc9aa3e33933f782312fa8b29c5f92e is archived at f7739d58bb68186117887172060ec1b17f75a14d, parent 99cf43d81db834a5d4cef98fedea87e2cd884ade. Anonymous readback verified 12 files / 5,056,721 bytes, exact paths, parent and content identities. Root combined UI 193, TypeScript/Vite/token and PUBLIC/catalog 6 passed. Catalog now has 2397 operations, fingerprint e6e4a14bf5b7c5b799c3ad8bc11926847b3225a4c627e4e8f3033ce171f42273.

Ordered multi-chapter screenplay adaptation and direct saved Graph/Timeline asset usage queries are implemented with the precise boundaries in delivery/v2-development/ordered-adaptation-usages-wave-20261018.md. Adaptation real PG 190 and usage PG 18 passed; both servers stopped with cleanup. Earlier overlapping File runs and unrelated concurrent edits are documented honestly; no whole-V2 acceptance claim.

Next active slice is CPU sampled video reference preparation: exact formal Video asset, bounded sampling interval, timestamped decoded frames, explicit selected-frame review, first-commit derived Image asset, and existing I2V handoff. This does not yet implement V2V interval cropping, motion/pose/depth or semantic camera analysis. No model execution is needed or authorized for its checks.

## 17:31 sampled reference checkpoint

Product 033a4f6a258473857c5d0ecba56be564563871f2 is archived at 50b4e54afc67694f3e7900efedc36145cc33c1de, parent f7739d58bb68186117887172060ec1b17f75a14d. Anonymous readback verified all 12 files / 5,086,938 bytes. Isolated worktree validation excluded unfinished Model Center changes: File187, UI71 + TypeScript/Vite/token, PUBLIC 6 passed, with real PG45 on identical backend. Compared3001 verified source paths against committed Git blobs with zero mismatches. Original isolated TS failure is retained; subsequent type/test-only fix passed.

See delivery/v2-development/video-reference-isolated-summary-20261018.md for actual-PTS sampled video references and strict limitations. This is a partial closure of remaining group5, not full Video preparation. Catalog2401 fingerprint82b5ec4f5f29bc8fbccd638ef74668dffa23939b691026c3cec81646a1a8abb1.

Model Center single-file transfer mechanism is currently in development with synthetic tests only. Empty reviewed source catalog/destination and POSIX-only safety mean it cannot be described as working downloads for current Windows/catalog models. Windows support, trusted production manifests and actual upstream acceptance remain separate; no real model downloads, fees or credentials were used.

## 17:41 partial transfer checkpoint

Product be9a72314b785da31b3400001a89cf4d64b64402 is archived at 5252f72e1d9ccf6a2e492fb2aa6ed1ac1ca04677, parent 50b4e54afc67694f3e7900efedc36145cc33c1de. Anonymous readback verified 12 files / 5,098,160 bytes and exact content identities. Backend 452 passed (14 PG variants not requested), integrated UI 227 + TypeScript/Vite/token, PUBLIC 6 passed. Initial test-only generic typing failure is retained. Catalog 2417, fingerprint c89b2d50cd9edb15954084a7da62fb6c33bdca274082bf9d2bb83ae3ceab1759.

This is partial Model Center transfer infrastructure. Production manifests/destination are empty, no provisioning UI/loader exists, and Windows fails closed. No current catalog model has become downloadable. Exact trusted metadata, destination provisioning, Windows support and real upstream acceptance remain open. See docs/model_center_controlled_transfers.md and delivery/v2-development/model-transfer-integration-summary-20261018.md. Do not mark remaining group7 or M3 complete.

Next active implementation: bounded opt-in saved-shot image thumbnails and text/image comparison in original CreativeCanvas board, authenticated exact formal Asset pins and bounded image resources. VIDEO_WORKFLOW benchmark is undergoing read-only design review, not implementation yet. No main merge, Release, actual model download or paid service.

## 18:31 UTC archive and overnight continuation

Archive 1d7e2309c94627b9a5b3bc5542aacb1d01c874a6 was independently read back:
13 files / 5,279,074 bytes, exact parent 0e5cd80918e8022bee1f94f9295b22c206e0ac77,
pinned source 1c4bd7b383ffb35ca9e311ee30ffed3372b5c78f. All bytes/SHA256/Git
blob identities matched. Dirty later work was excluded. PUBLIC stage 575 files
and 552 wheel source members matched frozen product e96b749a.

Active lanes are Story/Impact fact-use integration (with independent security
review), model-free independent Comic editing inside Image, and additive Director
intent controls. Each owns separate files; shared composition/build/publication
remains coordinated. None of these in-progress lanes is claimed complete.

## 18:52 UTC bounded development checkpoint

Product e66c53138989de1aff021994110c2083900f0aec integrates exact reviewed
story-fact/shot impact, model-free independent Comic and authored Director
audience/platform/budget constraints. Root UI203/TypeScript/Vite/token, PUBLIC 6
and retirement File33 passed. Actual Story/Comic/Director PostgreSQL evidence and
limits are in docs/delivery/v2-development/story-comic-director-integration-20261018.md.
All 3049 source paths from final PUBLIC receipt match the committed product.
No formal V2 completion or percentage follows from these bounded checks.

Next independent work: original-owner Style DNA hierarchy in an isolated worktree,
Comic book/chapter/page collections, and a separate additive Director IMAGE/vision
contract seam in an isolated worktree. No actual model calls are authorized by
test fixtures; unsupported vision must remain explicitly unavailable.

## 18:56 UTC archive delivery

Archive c8a93e10c4444e6fd7a1fbfea9b4f16dcbc817b0 was anonymously read back
against parent 1d7e2309c94627b9a5b3bc5542aacb1d01c874a6: all 13 files /
5,516,265 bytes matched their exact SHA256 and Git identities. Source checkpoint
18ce2ce945574d9842df5e99b4ecf215d4111fc6 includes product e66c5313; later
dirty Comic collection work is excluded. PUBLIC stage 577 source identities and
554 wheel source members match that product. Normal PR source branches remain
unchanged; no new public integration source branch has been pushed.

## 19:20 UTC bounded product checkpoint

Product eb8b8b8ed617c34e1e01415fa5eef9d4c074c348 adds Comic collections and
Style DNA backend hierarchy, plus an unmounted Director image source/codec
foundation. See docs/delivery/v2-development/comic-style-vision-integration-20261018.md
for exact passed/failed/corrected-run distinctions. Integration File 144, UI 97,
TypeScript/Vite/token and PUBLIC 6 passed; real PG evidence covers the applicable
owner lifecycles with explicit test-only corrections. Final owner-test receipt
3061 source paths match this committed product exactly. No full V2 acceptance.

Style DNA UI, guarded local vision runtime and native Comic layers/ORA export are
being developed in separate isolated worktrees. They are not included in this
checkpoint; unsupported runtime/adoption/format capabilities remain unavailable.

## 19:33 UTC Style authoring/runtime checkpoint

Product 9d5ac505b4ef67e556af16162129f0830b83310d adds original Style authoring
and guarded local VISION runtime. See style-ui-local-vision-integration-20261018.md
in the delivery evidence directory: File 99, real PG 5, UI 42, TypeScript/Vite/token
and PUBLIC 6 passed with stable sources; all 3067 source paths match this commit.
No live model inference occurred. Durable Director IMAGE jobs, terminal review and
adoption remain unavailable. Host in-app dirty-navigation protection remains open.

Previous checkpoint cab201e was publicly archived as
bab2926453fdb2ea9980e507c61bc2c33d062bcf: 13 files / 5,871,246 bytes, anonymous
exact-parent/path/byte/hash verification passed. Fresh remote observation at
19:20 UTC left main and PR47/48 heads unchanged. New source publication remains
archive-only; no main merge, release, tag or new public source branch.

## 19:47 UTC Comic layers and ORA export checkpoint

Product 69943270e38df8d6d9869808c75760ca0a1c883a adds optional native reference
layers and real bounded ORA export. File 84, PG 52, UI 148, TypeScript/Vite/token
and final PUBLIC 6 passed; exact skip/failure distinctions are preserved in
comic-layer-ora-integration-20261018.md. Pixel preview requires save and server
preview. ORA import and target-application roundtrip remain open.

Previous source faff5940 was anonymously verified in public archive
9c406ba770e58b037918ddb2ecbed121f24284fb, parent bab2926453fdb2ea9980e507c61bc2c33d062bcf:
13 paths / 4,760,204 bytes. Normal source branches remain unchanged.
Style host navigation fixes and durable IMAGE V3 Job preparation remain isolated,
not included in this product. Full V2 acceptance remains open.

## 19:55 UTC navigation and parser checkpoint

Product b02ef383287ea3f01ead4e50887caa1cfb172c48 closes bounded Style host
navigation loss paths and adds pure no-write ORA inspection. Integrated UI71 plus
separate original UI96, parser78, TS/Vite/token and PUBLIC6 passed. No ORA staging/
review/page attachment yet. Detailed boundaries and review fixes are recorded in
navigation-ora-preview-integration-20261018.md.

Prior source1d6a17f0 was archived as40bd889737fc9b891bfc5c0c95c835f97e2174e4,
parent9c406ba7:13 paths/4,923,586 bytes independently verified. Director IMAGE
Job and Production Passport slices remain isolated under review.

## 20:02 UTC internal IMAGE jobs and Passport checkpoint

Product 0d72d692dfa56f6a47d8050d12eaf98e364c9e05 integrates guarded internal
IMAGE V3 terminal/pending persistence and original approved Media image unsigned
Passport download. File69, real PG69 with exact five-table row hashes, UI48,
TypeScript/Vite/token and PUBLIC6 pass. All3090 final source paths match product.
IMAGE accounting remains UNKNOWN_UPSTREAM and adoption unavailable. Passport
does not authenticate a signer or certify copyright. See the full bounded report.

Previous source a30d8267 was publicly archived as
114f61aaa8366a2477ded75a3d394d1d41ba778e, exact parent40bd8897:
13 paths/5,073,297 bytes independently verified. No normal source branch update.

## 20:09 UTC private ORA staging checkpoint

Product 2a9287733aea93bdda4dd2de27c3021b46dc6ded implements private original
Asset staging, exact planned-ID recovery and retained-orphan quota accounting.
Final File68, real PG18, PUBLIC6 passed. Initial File fixture timestamp failure is
preserved and explained; production digest checks unchanged. Frontend source
unchanged. Review/page attachment and upload UI remain unimplemented.

Prior source64083447 was archived as8996f8a2d0c53a591e4f887fb30f314e1177f53e,
exact parent114f61a:13 paths/4,946,353 bytes anonymously verified. No main or normal
source branch changed. Next isolated work: explicit human-cost IMAGE adoption,
ORA review/attachment and chapter-only author-entered Audience comparison.

## 20:15 UTC IMAGE declaration/adoption checkpoint

Product b5062095926fb449429482467a014b66688744a1 adds explicit human-declared
local cost and original scene-note adoption. File46/realPG46/PUBLIC6 pass;
all3096 source paths match. No public mounted workflow or live-model acceptance.
Prior source c7bffde8 is archive e57446be2776d4066e3a9892c2bd1f142222a7eb,
parent8996f8a2:13 paths/5,096,930 bytes independently verified. New mounted
workflow, ORA review/attachment and Audience comparison remain isolated.

## 20:19 UTC local audience checkpoint

Product 560bdcc5f1f626351150c4586e17957422680873 adds source/incarnation-pinned
hypothetical profiles, author-entered feedback and original review decisions.
File53 plus mountedFile2, realPG31 with one File-only skip, UI42, TS/build/token
and PUBLIC6 pass. Actual simulated reader feedback is not implemented.
Previous source994d0d6b archived as cfe6ef459f7cc1bb49a611a8b1bed0b36dc2201e:
13 paths/4,788,862 bytes verified against exact parent e57446be.

## 20:25 UTC mounted IMAGE backend and ORA attachment

Product 7fad622f9cec1c4a8455f4f97412fcfa22dc9641 mounts authorized IMAGE API
and adds server-only reviewed ORA raster attachment. Fourteen unique Director
mounted scenarios and14 ORA cases have actualPG evidence; overlapping runs
explicitly distinguished. PUBLIC6 passes;3106source hashes match. Both frontend
closures and real inference/external-app acceptance remain open.

Prior source899a2566 archived as321f498d6023508e972da86d2330484c9d34f1d3:
13 paths/5,262,941 bytes anonymously verified against parentcfe6ef4.

## 20:50 UTC bounded authoring workflow closure

Product79fbb1e5d80574e513cd51c09b54118b12c80d90 adds guarded Director IMAGE
authoring and ORA upload/recovery/raster UI. Combined UI120+TS/build/token,
ORA File26/realPG57 with14-table exact cleanup, passive recovery File2/PG2,
pinned CJK File5/PG1 (one File-only skip), Windows-source41 and PUBLIC6 pass.
All3121 source paths match. Windows fonttools omission fixed; actual Windows,
browser, external-editor and real-model acceptance remain open.

Prior source7a9e745 archived asb6e00c9d5601140760fc97c98d99569ed7242afa:
14 artifacts/4,981,463 bytes verified, extra exact standalone report and explicit
README caveats. Parent321f498. No main/Release/new public source branch.

## 21:17 UTC bounded publication, exchange and author recovery

Product 195ebd9b0cb80431cc987de5a103867ef58cb285 adds actual ordered full-page CBZ, pinned Ink exchange, guarded local Director author recovery and Audio admission catalog compatibility. File 289, final real PG 113 with exact 14-table cleanup, UI 632 in 55 suites, TS/build/token and PUBLIC 6 pass. Initial PG fixture cleanup failure and exact-owned correction are retained. All 3137 source paths match final product. See docs/delivery/v2-development/exchange-recovery-integration-20261018.md. Browser, independent CBZ readers, native target/platform and whole V2 acceptance remain open. Director storage/locking and 1024-marker ceiling are explicit limits.

Prior source 311adda1 archived as ce99a289b1f3ed369433400443aac7fa817b08a9, parent b6e00c9d: 14 files / 5,352,949 bytes anonymously verified. No main/Release/normal source branch update.
