# A43 shared document and chapter identity repair

Status: implementation and exact-source full regression in progress. Draft PR44 is a separate successor to frozen PR43; it is not a release or backport.

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

The original ZIP was downloaded through the supported artifact/file flow. Its 7,886 bytes match GitHub's SHA-256 `5dbbd44b2fb81f0784d4aded43838f03188cded1bc63e692f4004c754c2b7af5`; ZIP CRC and every receipt file's recorded hash were verified. Selected original JSON/JUnit/source receipts and the verification registry are in `docs/delivery/a43-fixes/baseline/`.

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
