# A43 shared document and chapter identity repair

Status: diagnosed integration corrections; the last published full hosted checkpoint failed as recorded below. Corrected-source full hosted verification is still required. Draft PR44 is a separate successor to frozen PR43; it is not a release or backport.

## Scope and frozen source

- Repository: 1785235376-blip/AI-Novel-Studio
- Historical audit target: PR43, commit `ad1a90dced36208c63bfd65f5e1d918d4a4f7695`
- Historical tree: `fd32163d45c0cbfb1cf2b54551214b99d282f6e1`
- Repair branch: `fix/a43-document-chapter-identity`
- New Draft: https://github.com/1785235376-blip/AI-Novel-Studio/pull/44
- Actual implementation and integration model: gpt-6-astra

Only A43-01/A43-02/A43-03 are being repaired in the original shared owners. No new feature tranche, UX-01 visual redesign, QingJian change, protocol 1.0 revision, paid provider/model call, real manuscript, user credential, merge, release, deployment or backport is included.

The report identifies defects in shared infrastructure. It does not establish that PR43 introduced them. Repairing this descendant does not automatically patch an installed V1 package or any frozen branch.

## Reproduction before repair

The four portable appendix scripts are preserved under `scripts/a43_baseline/`, with SHA-256 fingerprints in `original_scripts.json`. They run against the exact unchanged historical checkout. Observation exit 0 only means the script completed; it is not a safety PASS.

### A43-01: reproduced in the original File/service owners

Structured JSON survives the original save/reopen, but Markdown/plain text drop nested list and quotation words, and join text on either side of hardBreak. File duplication reconstructs from the lossy projection and introduces another heading. Original NovelService snapshot/export and DOCX output lose the same words.

Formal regression assertions are separate from the observation scripts. Both failure evidence and later corrected-source outcomes will be retained with their exact source/toolchain identities.

### A43-02: reproduced in the original File/service owners

Deleting the last chapter and creating a new one reissues its external ID/version. Old history and archive state then attach to the new chapter. Explicit creation with an occupied number overwrites its Markdown. Formal lifecycle assertions fail before repair.

### A43-03: actual PostgreSQL baseline RED verified

The user's original Session probe remains labelled synthetic. A new dedicated workflow checked out exact ad1a90d, applied its original SQL migrations, and used actual PostgreSQL 16.15 with Python 3.12.9.

Run: https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/37538014264

The original move completed successfully with the real unique constraint. External ID `:1` still reported version 1, but now resolved UUID-B rather than UUID-A. Sending A's original document with its old ID/version then actually wrote to UUID-B and changed B to version 2. This verifies the wrong-target risk on the real database, not merely the synthetic algorithm.

The formal assertion that moving a chapter preserves the document/UUID behind its external ID failed: 1 failure, zero errors/skips. The workflow is green because it required that specific baseline RED; the old application is not safe.

The original ZIP was downloaded through the supported artifact/file flow. Its 7,886 bytes match GitHub's SHA-256 `5dbbd44b2fb81f0784d4aded43838f03188cded1bc63e692f4004c754c2b7af5`; ZIP CRC and every receipt file's recorded hash were verified. Selected JSON/JUnit/source receipts and the verification registry are in `docs/delivery/a43-fixes/baseline/`.

## Required repair contract

- A43-01: structured documents remain authoritative; recursive projection preserves text and line breaks, duplication retains the document, and unsupported content fails explicitly before loss. Text coordinate contracts are documented separately.
- A43-02: durable chapter identity allocation survives chapter deletion and restart; occupied or reserved IDs cannot be overwritten; stale saves/history/tasks cannot attach to a later generation.
- A43-03: PostgreSQL chapter UUID and numeric external identity remain immutable while ordering changes independently. A move does not consume a manuscript version. Legacy contradictions are retained and quarantined rather than guessed.
- Existing historical data and original regression assertions remain. New migration SQL is additive; old migration files are not modified.
- The File/PG API aliases, OFF/ON/V1 modes, original queue/export services, snapshots, references, caches, CAS, history and concurrent move/save paths are regression targets.

See `RICH_DOCUMENT_ROUNDTRIP.md`, `SOURCE_IDENTITY_MIGRATION.md` and the final regression matrix for exact implementation, compatibility uncertainty and evidence.

## Verification still required

Implementation-local Python is actually 3.12.14 and is supplementary evidence. Locked hosted verification uses Python 3.12.9 and actual PostgreSQL 16. Original backend coverage collection, node/source identity, expected-skip maps, finite File/PG shard time limits, postgres_gate and aggregate JUnit/outcome reconciliation remain mandatory. Focused success does not replace full regression.

Final checked SHA/tree, publication changes, both full backend profiles, frontend/build/browser/Interop/Windows receipts and unresolved outcomes will be appended only after they are verified.

## Unchanged product and acceptance boundaries

F00 stays INTEGRATED; the other 39 features stay PARTIAL. Existing remaining product gaps are not erased by this repair. Real model/GPU/TTS/translation quality, native Windows IME/vault/install/upgrade/interaction, target NLE/engine use and actual user acceptance remain NOT_RUN or LOCAL_REQUIRED. Historical independent review remains BLOCKED and is neither restarted nor replaced here.

## First integration checkpoint corrections

The first complete supplemental File run exposed 26 pre-existing product audio-node contracts rejected by the new overly narrow validator, plus one earlier lifecycle regression already corrected before de92. Original test assertions and skips stayed unchanged. The document projector now preserves the original portable media-node/mark subset, with explicit non-embedded media descriptions in text exports and a separate coordinate-only warning contract.

Actual de92 PostgreSQL initialization stopped before tests: DISTINCT inferred an untyped NULL as text for a UUID target. Migration020 now explicitly casts that value to UUID; all original constraints and historical migration files remain. See docs/delivery/a43-fixes/INTEGRATION_CORRECTIONS.json and MEDIA_CORRECTION_INVENTORY.json. These are diagnosed source corrections, not a retry of an unchanged failure or a PostgreSQL pass claim.

## Completed 1d9 hosted checkpoint and subsequent corrections

Published source `1d9b88ac36b1d75c06544e3aa69c3ab308164120`, tree `7ad139d78404f3f1bf81e67e66dd4b78e16ffc45`, completed all seven push/PR workflows at attempt 1. Both Cloud CI runs failed. This is preserved failure evidence, not final repair acceptance. The PR checkout `88e1cff2b8585f1e2ef492092cfb6164bbef5274` was independently verified to have that same tree.

- File: 7,862 unique nodes; 5,326 passed and 2,536 approved skips, no failures/errors. The original subset remained 5,111 passed/2,381 skipped. Original separate TCP gate: 2 passed.
- Actual PostgreSQL: both deterministic shards completed, yielding 5,290 passed/2,560 approved skips/12 failures, no errors. All 12 failures were the deleted-generation acceptance variants in the additive source-identity matrix. The original 7,492-node subset remained 5,112 passed/2,380 skipped. Both enclosing aggregate gates correctly failed; no aggregate PASS proof was produced.
- Frontend: 1,269 passed/8 original opt-in skips. The separate actual TypeScript client step passed its 2 tests. Build/type/token steps succeeded. All 94 distinct original browser journeys passed. These overlapping trigger/layer results are not summed into backend coverage.
- File and actual PostgreSQL Interop each completed 413 nodes, 345 passed/68 opposite-profile skips; the unchanged strict reconciler passed separately for both events. Windows Host contracts passed 59 tests, reference pipe checks reported 8 plus 33, and fresh native base/UTF-8 PostgreSQL recovery smoke succeeded within its original limited scope.

The PG cause was a preserved safety guard: persistence refused a late result after the original chapter was deleted, leaving an older durable job status. Shared `JobManager.accept` reloaded that status and returned incomplete-draft HTTP400 before resolving the missing source. The correction resolves the original durable chapter before checking draft completion, preserving every content, accounting, authorization and CAS guard. Detached PG completion remains rejected. The unchanged matrix still requires 404/409. A new two-node File-only refusal fixture was RED (1 failed/1 passed); it is explicitly not PostgreSQL emulation. The corrected focused selection passed 325 tests with 294 backend skips. An initial local resource-root mistake produced 91 failures before correction; its complete private originals, exact command change and hashes are retained separately, without changing product assertions.

A separate focused check found that rebuilding a rich leading H1 from title metadata could lose later heading lines, hardBreaks and mixed marks during duplicate. Both original duplicate owners now use a suffix-only deep-copy helper. The new 36-case suite was RED on exact 1d9 (18 failures/18 PG skips); all 18 File cases pass after correction, and the original rich/media neighborhoods pass. Actual PG cases remain for the next changed-source full run. Rename and the existing PG metadata-title rules are unchanged.

The deterministic inventory is now 7,900 nodes: all original 7,492 plus 408 additive cases. Independent complete collections agree. Original test digests, relative ordering, skip maps, finite caps and strict gates remain unchanged. `IMPLEMENTATION_SURFACES.json` identifies 13 shared-owner files and 26 bounded dependent consumer files, plus two new frontend regression files and additive migration 020. No new route or visual restructuring is added.

See `docs/delivery/a43-fixes/hosted-1d9b88ac/CHECKPOINT.json`, its artifact registry, the heading/source-priority inventories and selected safety receipts. These checkpoint results never certify a later SHA. New exact-head completion will be recorded separately after the full original workflows finish.

## Receipt privacy and download boundaries

Raw original receipts are retained privately. Public selected copies redact only executor checkout/temp paths and JUnit executor hostnames; test source, node identities, assertions, outcomes, skip reasons, counts and traceback line numbers are unchanged. `PUBLIC_RECEIPT_PROVENANCE.json` records original and public hashes and replacement counts; `ORIGINAL_RECEIPT_ENCODING.json` distinguishes deterministic encoding from this metadata redaction. Public copies are not claimed to be byte-identical original downloads. Full raw CI logs, private work logs and native executable packages are not published in the repository.

At the 1d9 checkpoint, 25 supported official ZIP downloads matched GitHub SHA-256 and ZIP CRC. Four original monolithic frontend/native-package ZIPs exceeded the supported 32 MiB materialization cap and were not downloaded by another route. Their reported GitHub digests are distinguished from independently verified bytes. Existing bounded compact receipts and source-labelled PNG parts were verified instead; this does not certify uninspected package bytes or native user acceptance.
