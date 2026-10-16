# A10 original-source citation location — 2026-10-16

Baseline: local `fd2a75e5e34fd630c354f80c14be40ef518e6f41` on `work/dot-usability-handoff11-20261015`. The containing commit identifies this bounded delivery. **A10 remains PARTIAL.** No push or hosted CI was triggered because its cost remains unknown.

## Audit and actual gap

Read the frozen product anchor, repository/UI rules, continuation checkpoint and current capability ledger. The original referenced 904-line roadmap remains unavailable; no new full-roadmap reconciliation is claimed. Current code, not old matrix labels, established:

- `ResearchPanel` retains the original legacy sidecar metadata/excerpt editor. `ResearchLibraryService` projects live legacy references without copying their ownership or fetching URLs.
- `ResearchLibraryPanel` is mounted under `ExperimentalWorkbench` and already imports selected local files, searches local literal text, resolves exact citations, previews context, saves original notes and creates/reviews original fictional setting drafts. There was no need for another research store, crawler, search engine or draft owner.
- Citation identity is original source ID/version/paragraph/quote SHA256; extracted paragraphs carry PDF page numbers. Page-only references use paragraph zero, page number and original-content digest. There are no character offsets in this contract. Duplicate text must not be located with substring search or Unicode-normalized offsets.
- Source history deliberately returns metadata without original paragraphs. Original-file historical downloads and explicit restore already exist under their original owner; a current readable source does not prove historical content. Existing resolve rejects outdated source versions.
- `research_vision.py` contains bounded optional OCR/image/chart/table adapter contracts and synthetic fixtures. `analysis_status` declares runtime admission NOT_CONFIGURED, no durable worker and model quality NOT_RUN. No research-analysis frontend entry was found. `EmbeddingPanel` separately mounts original Embedding/Hybrid query owners, including registered local provider contracts. This research search remains LOCAL_LITERAL; configuration/declaration is not real model verification. The old broad “all vector/OCR unconfigured” panel copy was narrowed accordingly.

**Missing seam:** a resolved search/note citation could display a detached passage, but could not take the author to that exact paragraph/page in the original source’s paginated view. Existing save/review workflows were already available.

## Bounded implementation

1. Explicit “在原来源中定位此引用” reads the exact source through the existing GET, checks ID/version/citation/text/page, then opens the existing source view at the correct twenty-paragraph page and focuses the exact whole paragraph. Repeated quote text is distinguished by owner paragraph ID. No guessed byte, Unicode or editor offsets.
2. Page-only citations locate an original unread-page reference, expressly without claiming extracted text or visual understanding. No image/iframe/browser fetch is introduced.
3. Source view performs its original reread; mismatched, malformed, failed or unavailable results cannot display the located source body or old evidence as confirmed. Stale pins retain only metadata and do not silently upgrade, restore, fetch historical bytes or create proof for unknown historical content.
4. Current saved version and citation ID/digest remain visible. The author still explicitly chooses citations and uses the existing note or original-setting draft save/review controls. Location never selects a citation, changes author input, writes a source, saves a draft or promotes Canon.
5. Original action lock and scope/epoch checks fence delayed reads. Explicit cancellation aborts the source GET and discards ignored-abort responses; query changes and scope replacement invalidate work. Active composition prevents focus transfer. Original read/unavailable behavior and write owners are unchanged.
6. New pure matching guards reject malformed objects/collections/citations, duplicate paragraph identities, invalid pages, unknown versions, changed quotes and normalized-text differences. On a second malformed original read, the original view is withheld rather than rendering invalid collections.

No backend/API/schema, permission, lifecycle, P0, queue, model dispatch, source authority, production Prompt Adoption or gate was changed. Existing AppShell/primitives/classes are reused; no CSS/token change.

## Verification and evidence

Exact commands, exit codes, source hashes, timestamps and log hashes are indexed in `research-evidence-location-20261016.json`. The original runner receipts remain under `docs/delivery/v2-development/research-location-*`.

- **49 passed:** selected mocked UI/pure tests, including original ResearchLibrary tests, continuation tests, original-view location, duplicate Unicode text, page-only identity, metadata fallback, stale/malformed second read, preserved note input, explicit original note save, composition, cancellation, scope/query invalidation and PUBLIC placeholder.
- **5 passed:** selected nonsecurity original File-owner cases: import/reopen/original citation, notes/reviewed setting separation, version conflict, page-only manual note, and new duplicate-Unicode paragraph 22 → exact citation → original note → reopen → stale version rejection / metadata-only history case.
- **2 passed:** original UTF-8 TXT/MD extraction cases. These are pure synthetic inputs, not real OCR evidence.
- **30 passed:** PUBLIC profile contracts.
- Forced TypeScript build, Vite build, test discovery, global/scoped token guards, diff whitespace and **487-file PUBLIC source closure** pass. Discovery is not execution of the full test inventory. Existing large-chunk and Starlette deprecation warnings remain nonfatal.
- Initial builds caught new test fixtures missing required synthetic sessionToken and Source access metadata. Corrected and rerun; all failed receipts are preserved. Earlier successful receipts are superseded by final unchanged-source receipts, not deleted.
- Independent source review identified malformed-proof handling and subsequent query-edit exposure; unconditional source-shape guards and mounted reread/query regressions were added. Independent revised-source UI/pure run passed 48 checks; final SHA verification remains with parent review.

## Limits and continuation

Browser/native IME/visual/assistive-technology/HTTP integration, PostgreSQL/security lifecycle, Windows/GPU/provider/model quality and full RC were **NOT_RUN**. No browser workaround, paid call, web-content fetch, user-computer/saved-environment access or hosted CI was attempted. This is current-source passage location, not historical passage retrieval or verified scholarly/literary truth. Source history body replay, durable unsaved notes/recovery, wider research-analysis UI and actual OCR/embedding quality remain open.

P0 stays BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled; all previous PUBLIC/cost/environment boundaries remain unchanged. Preserve all historical receipts. Parent independent review/final SHA verification precedes another tracked feature slice.
