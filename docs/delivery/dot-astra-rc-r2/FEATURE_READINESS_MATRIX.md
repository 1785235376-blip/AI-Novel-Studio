# R2 feature readiness matrix

**Ready for bounded internal desktop acceptance. Final engineering source 98b passes all five hosted lanes, post-layout browser geometry, complete unsigned Windows package and actual native smoke. PARTIAL/NOT_RUN boundaries remain; this is not formal release or all-feature completion.**

- Current documented source: `98b7d53c3193765e792e5a756fff02a87b5948b8`, tree `f6c4a84c5ff0d1b2639b537af1ea287611935fd4`.
- Last verified published branch: `98b7d53c3193765e792e5a756fff02a87b5948b8`. Branch/PR checkout and source-equivalent mappings are recorded in the ledger, not substituted for each other.
- Baseline `f8c141c39a543cc9dbea57647ac91185bc9aecd6`; branch `work/dot-astra-v1-rc-r2`; [Draft PR #37](https://github.com/1785235376-blip/AI-Novel-Studio/pull/37).
- **143 original feature IDs, 19 D00–D18 packages, 28 LAD sections** retained individually. No completion percentage.
- This is the concise per-item view. The [JSON matrix](FEATURE_READINESS_MATRIX.json) preserves every item’s original source/audit mapping, API, persistence, version, dependency, behavioral state and evidence field. [TEST_RESULTS.md](TEST_RESULTS.md) contains full revision-scoped counts and final gate slots.

## How to read every row

- The 143 original codes are preserved exactly. Their historical rows are evidence of the old audit, never proof of current completion.
- The original audit does not contain full canonical feature definitions. Each feature records that limitation rather than inventing requirements.
- Feature D01-D07 and work-package D01-D07 are different namespaces; use features[].code and packages[].package_id.
- IMPLEMENTED describes the bounded stated implementation, not literary quality, every historical requirement, real model verification or final release readiness.
- CONNECTED requires a callable service/API and visible functional entry or documented Host/API entry. DISCONNECTED includes deliberately disabled execution.
- CONTRACT_VERIFIED may use real files, parsers and local codecs but does not prove a real AI model. MOCK_ONLY means model/provider behavior used controlled test doubles.
- No current REAL_VERIFIED model claim is made. Hosted Windows build/native contract results do not replace interactive Windows/WebView2 or user acceptance.
- User-visible states describe shipped capability semantics, not a percentage. AVAILABLE manual CRUD can coexist with NOT_CONFIGURED generation and incomplete higher-level package requirements.
- Results are tied to the revision_evidence_ledger and TEST_RESULTS.md. Earlier focused logs and source inspection stay historical; no pass is inherited by a later source or documentation commit.
- Test paths without a cited execution receipt are inventory only. Counts overlap; skipped tests are not passes. No old completion percentage or historical DONE status is inherited.
- The Local AI supplement is mapped separately as LAD-01–LAD-28; all original 143 A–T feature IDs and D00–D18 packages remain individually present.
- Windows input assembly, hosted compile/native smoke, interactive DesktopHost/IME, installation lifecycle, signing and user acceptance are separate verification layers.
- The inventory is refreshed at the current_checkpoint source. Per-feature source_inspection_revision retains the earlier inventory scope unless a later targeted change is stated; reading this matrix is not a fresh independent source audit.
- Independent d033 review closes the later StrictMode P2 with unchanged original assertions and 23 additional replay checks. b0/871 controls passed the full 93daeb97 hosted suite, including real Windows native smoke. Final 98b post-layout geometry/browser and all hosted gates also passed;93d retains its own historical receipt.

### Shared evidence and platform contract

- **test_revision:** Final engineering source 98b and each historical receipt retain their own exact revision in revision_evidence_ledger / TEST_RESULTS.md. All final hosted gates PASS. Per-feature boundaries still apply; later documentation-only delivery SHA/CI is separate.
- **platform:** Final 98b hosted File/PostgreSQL/frontend/browser/Windows Host/full unsigned package/native layers PASS at exact recorded checkouts. Real model/GPU, interactive Windows/WebView2/vault/IME, clean install/upgrade/uninstall, signing and user acceptance remain NOT_RUN.
- **verification_scope:** Implementation and source inspection do not imply execution. CONTRACT_VERIFIED is bounded contracts; MOCK_ONLY is controlled provider transport; NOT_RUN keeps absent direct acceptance explicit. Existing test paths alone are not passing receipts.
- **local_ai_scope:** Independent e38 closes original Discovery findings; actual model inference remains NOT_RUN. Later d033 review closes a distinct history StrictMode P2. Model-family adapter gaps remain specific per LAD row.
- **next_acceptance:** Follow this item’s specific remaining user/native/provider/product boundary. Final engineering regression gates passed; the later documentation-only delivery-head readback/CI is separate.

## Revision evidence ledger

| Ledger ID | Revision | State / boundary |
|---|---|---|
| HISTORICAL-CI-4E7 | 4e7ca3d3bfcf9908fee7d3a6e80a3d1243b9238a | FAILED; Historical terminal failed snapshot: business history-cache defect. Later repairs and actual native/package/browser success are recorded at 93d and final 98b; this older failure is not relabeled. |
| INDEPENDENT-E38 | e38d1eccff6c1aac02a836817c878f423df0479e | PASS_WITH_SCOPE_LIMITS; All previously reproduced original and Discovery audit defects closed in this scoped review. Synthetic transports and Linux only; exact new-head CI, native acceptance and real inference remain separate. |
| LEAD-E38-FONT | e38d1eccff6c1aac02a836817c878f423df0479e | PASS_WITH_SCOPE_LIMITS; One more pass and one fewer skip than the independent e38 run; counts overlap and must not be added. |
| LEAD-BBB-LOCAL | bbb55d10ac57de123e138a51510efd846ee42aee | PASS_WITH_SCOPE_LIMITS; Python 3.12.14 / Node 24.19.0. A first attempt called nonexistent lint:tokens and did not run lint; the subsequent correct pnpm lint passed. Do not claim the first chained command succeeded. Hosted PG/browser/Windows not run by this local suite. |
| BBB-HISTORY-FOCUSED | bbb55d10ac57de123e138a51510efd846ee42aee | PASS; Mounted version invalidation, full context/ABA fencing, token-free cache keys and clean/dirty App hydration have focused evidence; actual hosted browser reruns subsequently PASS at 93d and final 98b. |
| BBB-AGENT-TIMERS | bbb55d10ac57de123e138a51510efd846ee42aee | PASS; Service owns timeout timers; completion/cancel disposes them; deleted jobs/projects are not recreated, and database failures remain failures. Focused tests overlap full suite. |
| WINDOWS-INPUT-ASSEMBLY | e38d1eccff6c1aac02a836817c878f423df0479e | PASS_INPUT_ASSEMBLY_ONLY; Actual pinned official CPython/PyPI/EDB downloads and Linux materialization are input assembly only. Current collection has29 base-input contract cases; real Windows verification subsequently passed at 93daeb97, separately recorded in HOSTED-93DAEB. |
| INDEPENDENT-BBB | bbb55d10ac57de123e138a51510efd846ee42aee | REQUEST_CHANGES; Historical REQUEST_CHANGES at bbb: initial query discarded by StrictMode replay. The original three independent assertions are preserved and pass at d033. Do not retroactively relabel the failed bbb review as green. |
| FINAL-HOSTED-CI | 98b7d53c3193765e792e5a756fff02a87b5948b8 | PASS_ALL_FIVE_HOSTED_LANES; Final engineering source 98b7d53c is tree-identical to independently reviewed local 1c19d83d. Both push and PR completed all five lanes successfully, including post-CSS three-viewport goal geometry and actual Windows package/native smoke. Branch and PR merge checkout are distinct. Later documentation/evidence-only delivery commit is tracked separately. |
| D033-STRICTMODE-FOCUSED | d03399ee7d4b183173be47e5336b9bc4e0bd30b0 | PASS; Focused passing tests do not transfer bbb complete-suite or 55a hosted results to d033. |
| INTERMEDIATE-HOSTED-55A | 55a9082dbd3655c39a9b23bd4da19fedb3373072 | SUPERSEDED_CANCELLED; Branch/PR readback confirmed by integration lead. This is bbb source, before the new d033 StrictMode repair. It is not final candidate CI. |
| INDEPENDENT-D033 | d03399ee7d4b183173be47e5336b9bc4e0bd30b0 | PASS_WITH_SCOPE_LIMITS; StrictMode P2 closed; no additional concrete unresolved defect in this increment. Real React/QueryClient/App under jsdom, synthetic backend. Full File suite not rerun for the frontend-only fix; backend source/tests/workflow byte-identical to bbb independent 2135/46 run. Counts overlap; final hosted/native/user acceptance remain separate. |
| B0-BROWSER-NAVIGATION | b0cb9723cebaafb1e62d0f2bccd466e2efd6d5ad | PASS_HOSTED_AT_93D_AND_98B; 55a business reached second export after reload. Immediate locator.count() raced React mount; helper now waits for existing accessible navigation to be visible. Product journey/export/snapshot/download assertions are unchanged. This is separate from the closed StrictMode production defect. |
| 871-NATIVE-SMOKE-CONTROLS | 87127a5020c2c8d9463b4b631fe77fd0aacb3115 | PASS_FOCUSED_AND_SUBSEQUENT_NATIVE_EXECUTION; 40 collected focused cases comprise29 base-input cases and 11 verifier cases (10 functions plus parametrization), not12 new cases. Synthetic controls stay separate from the actual 93d Windows smoke now recorded in HOSTED-93DAEB. Browser first-reload history assertion retained. |
| HOSTED-93DAEB | 93daeb977d9fd238ffda7be3d9c566fd3768dc27 | PASS_ALL_FIVE_HOSTED_LANES; Both push 37282974046 and PR 37282980028 completed all five lanes successfully. Push checkout 93daeb97 and PR merge checkoutd4cf7526 are distinct. Native receipt explicitly records93daeb97 and SDK 8.0.424. This full pass does not automatically certify the later CSS/layout source 1c19d83d. |
| LAYOUT-1C19-FOCUSED | 1c19d83d870f325cb6af1d182573b1e8b2a47a29 | PASS_FOCUSED_AND_FINAL_HOSTED_GEOMETRY; Five scoped CSS lines retain existing tokens and behavior. Nine local contracts passed; actual 98b business tests subsequently passed all three-viewport label/input/containment/overlap assertions. Six real screenshots are hash-manifested and visually inspected by integration lead; LocalAI screenshots use synthetic API/runtime/hardware fixtures. |
| INDEPENDENT-871-NATIVE | 87127a5020c2c8d9463b4b631fe77fd0aacb3115 | CLOSED_BY_FINAL_INCREMENT_REVIEW; The native verifier increment was independently reviewed within fixed 1c19;40 input/native contracts and source controls pass, no new concrete finding. Actual Windows execution is separately PASS at 93d and final 98b. |
| INDEPENDENT-FINAL-1C19 | 1c19d83d870f325cb6af1d182573b1e8b2a47a29 | PASS_NO_NEW_CONCRETE_FINDING; Bounded independent increment covers native timeout/owned cleanup, browser synchronization and scoped CSS; original assertions retained. No full backend rerun or local browser is claimed by reviewer. Report was written before final 98b browser CI; its then-pending CSS execution note is now resolved by the separately recorded final hosted PASS, not by editing review history. |
| FINAL-SCREENSHOTS | 98b7d53c3193765e792e5a756fff02a87b5948b8 | PASS_CAPTURE_HASH_AND_VISUAL_REVIEW;  |

## Current verification layers

| Layer | State/evidence |
|---|---|
| engineering_source | 98b7d53c3193765e792e5a756fff02a87b5948b8; treef6c4a84c5ff0d1b2639b537af1ea287611935fd4; source-equivalent independent 1c19d83d. |
| original_and_discovery_review | CLOSED independently at e38;55 preserved/expanded invariants and full UI suite. Later history StrictMode P2 CLOSED at d033; no new concrete finding in final 1c19 incremental review. |
| final_independent_increment | Fixed1c19:35 UI/history/StrictMode/layout and 40 native/input contracts pass; type/token42/build pass;1331 tracked files match exact blobs. This is local independent review, not claimed local PG/Windows/browser execution. |
| final_file_suite | PASS at 98b:2147 passed / 45 skipped. |
| final_real_postgresql | PASS at 98b:2155 passed / 37 skipped; actual PostgreSQL 16.15. Earlier specialized ten-case process/restart/revocation evidence retained. |
| final_frontend_unit_typecheck_build | PASS at 98b:579 unit tests /111 files; typecheck/token lint/build pass; existing large-chunk advisory retained. |
| final_browser | PASS at 98b:geometry/LocalAI9, full business 2 including initial history and goal layout at 1366x768/1440x900/1920x1080, export 1. |
| final_windows_host | PASS at 98b:SDK 8.0.424 selected explicitly; Host build and 59 native contracts. |
| final_windows_package_native | PASS at 98b:complete unsigned internal package and 11 actual native commands all exit0, including Python 3.12.9/27 wheels, PostgreSQL 16.15/pgcrypto/UTF8/custom dump-newDB restore/app import/owned stop. |
| final_runs | Push 37284138175 and PR 37284145310 completed SUCCESS for all five lanes. Actual PR merge checkout 1c10ecc09ce07d445750a3a994931a1bc7f6f0be differs from branch98b. |
| screenshots | Six actual 98b browser PNGs retained with source/run/artifact/hash manifest; all hashes/sizes verified, all opened/reviewed by integration lead. File-business synthetic model data and LocalAI API-fixture boundaries explicit. |
| historical_results | Prior failures, cancellations, local counts and 93d all-green checkpoint retained separately in revision_evidence_ledger; no historical red is rewritten. |
| documentation_delivery | Only later docs/evidence-only commit identity/readback/CI PENDING_LEAD; completed 98b engineering gates are PASS. |
| interactive_windows_webview2_vault_ime | NOT_RUN |
| clean_install_upgrade_uninstall_retention | NOT_RUN |
| signing | NOT_RUN; unsigned internal candidate, no formal Release |
| real_provider_gpu_models | NOT_RUN |
| target_desktop_document_interoperability | NOT_RUN |
| user_acceptance | NOT_RUN |

## Independent review disposition

All five original Discovery findings below are independently **CLOSED at e38d1ecc**. Original R2 privacy/acceptance/scope findings are also closed in the preserved/expanded 55-invariant set. The later StrictMode P2 was found at bbb and independently closed at d033; neither verdict changes historical red evidence or certifies later source.

- **DISCOVERY-REVIEW-01:** Positive local GGUF/model/digest/completion evidence and remote_host/remote_model rejection apply to Discovery and legacy Ollama leaves; current locality is checked before actual prompt dispatch.
- **DISCOVERY-REVIEW-02:** Enabled discovered text routes execute through the real normalized author node using explicitly buffered final deltas, not a real-time token-stream claim.
- **DISCOVERY-REVIEW-03:** Rescan and dispatch identity/capability drift revoke authority for Ollama, A1111, ComfyUI and GGUF; fresh validation and explicit Enable are required.
- **DISCOVERY-REVIEW-04:** Control epochs and final authority callbacks ensure newer Disable/remove/configuration beats older validation/Enable completion and prevents subsequent dispatch.
- **DISCOVERY-REVIEW-05:** External llama sends the actually validated advertised upstream alias; Comfy binds the selected checkpoint to the exact loader field.

See [INDEPENDENT_REVIEW.md](INDEPENDENT_REVIEW.md) and [INDEPENDENT_REVIEW_INCREMENTAL.md](INDEPENDENT_REVIEW_INCREMENTAL.md). Final 98b hosted and native package gates PASS; interactive/model/user acceptance remains separate.

## D00–D18 packages

### D00 · Baseline and traceability

- **Scope:** P0; dependencies none; original IDs A01; A02; A03; A04; A05; A06; A07; A08; A09; A10; B01; B02; B03; B04; B05; B06; B07; B08; B09; B10; B11; B12; B13; C01; C02; C03; C04; C05; C06; C07; C08; C09; C10; D01; D02; D03; D04; D05; D06; D07; E01; E02; E03; E04; E05; E06; F01; F02; F03; F04; F05; F06; F07; F08; F09; F10; G01; G02; G03; G04; G05; G06; G07; H01; H02; H03; H04; H05; H06; H07; I01; I02; I03; I04; I05; I06; I07; I08; I09; J01; J02; J03; J04; K01; K02; K03; K04; K05; K06; K07; K08; L01; L02; L03; L04; L05; L06; L07; L08; L09; L10; M01; M02; M03; M04; M05; M06; M07; N01; N02; N03; N04; N05; N06; O01; O02; O03; O04; P01; P02; P03; P04; P05; Q01; Q02; Q03; Q04; R01; R02; R03; R04; R05; S01; S02; S03; S04; T01; T02; T03; T04; T05; T06; T07
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Verified inherited PR 36/main ancestry, branch and actual model; inventory all 143 original codes.
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Final engineering SHA and all hosted gates are verified at 98b. Later documentation/evidence-only delivery SHA/readback/CI will be supplied by lead outside these self-referential files.

### D01 · Privacy and authorization

- **Scope:** P0; dependencies D00; original IDs G01; G02; G03; G04; G05; G06; G07
- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Original privacy serializer/migration fixes plus consistent raw-manuscript project/outline policies and normalized final-dispatch guards across author, adaptation, Agent, image/audio and motion paths; post-Accept memory is verified-local-only.
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-work.md; docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** No unresolved concrete safety/Discovery finding in the independent scope; final 98b File/PG/hosted gates pass. Real providers and native interactive acceptance remain separate.

### D02 · Export recovery and format fixes

- **Scope:** P0; dependencies D01; original IDs T01; T02; T03; T04; T05; T06; T07
- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Server-scoped history, reauthorization, same-snapshot rediscovery, frozen ZIP resources and Fountain structural fixes connected.
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/fountain-before.json; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 93d export 1 and full business 2 browser tests pass. Target screenplay/Word/EPUB/NLE application typography/interoperability still NOT_RUN.

### D03 · Core authoring and recovery

- **Scope:** P0; dependencies D01; original IDs B01; B02; B03; B04; B05; B06; B07; B08; B09; B10; B11; B12; B13; C01; C02; C03; C04; C05; C06; C07; C08; C09; C10; S01; S02; S03; S04
- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible AVAILABLE
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Core authoring retains Draft/Diff/Accept, source versions and recovery. Local Accept now binds captured generation base; per-job durable ACCEPTING claim serializes side effects across single-host processes, stale/reentrant attempts fail closed; original independent invariants pass. bbb repairs mounted revision history refresh and context-fenced restore through App hydration, preserving dirty drafts.
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/revision-history-work.md; docs/delivery/dot-astra-rc-r2/evidence/revision-history.xml; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** History/StrictMode repairs independently closed and final 98b business 2 browser pass verified. Ambiguous interrupted acceptance remains review-required; native crash/IME and real model acceptance NOT_RUN.

### D04 · Provider execution and vault

- **Scope:** P0; dependencies D01; original IDs A01; A02; A03; A04; A05; A06; A07; A08; A09; A10; H01; H02; H03; H04; H05; H06; H07; R01; R02; R03; R04; R05
- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Guarded compatible/Claude/Gemini adapters and OS vault retained; integrated Local AI Discovery uses existing text/image/model registries with explicit lifecycle steps, bounded read-only probes and managed llama task-only launch design.
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Original Discovery and later final-guard findings closed in independent e38 review. Real provider/model/GPU/Windows acceptance NOT_RUN; named vault profiles and authoritative v2 broker remain incomplete.

### D05 · Advanced authoring and planning

- **Scope:** P1; dependencies D03; D04; original IDs B01; B02; B03; B04; B05; B06; B07; B08; B09; B10; B11; B12; B13; F01; F02; F03; F04; F05; F06; F07; F08; F09; F10
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Multi-variant review plus reusable STYLE/PLOT, compare/history/approval/restore and actual generation inputs; bounded selected-model exact-evidence structured suggestions and explicit-marker rule/plot drafts added.
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Full outline/volume/chapter/scene hierarchy and semantic planning quality remain incomplete; model proposals are MOCK_ONLY. Final engineering API/UI/hosted regression passes.

### D06 · Import extraction and review

- **Scope:** P1; dependencies D03; D04; original IDs C01; C02; C03; C04; C05; C06; C07; C08; C09; C10; D01; D02; D03; D04; D05; D06; D07
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Evidence-located four-group extraction/review/journal plus separate explicit-marker rule/plot proposals and bounded selected-model planning drafts.
- **Evidence:** docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Historical missing-authority fixture mismatch is superseded by complete passing regression. Semantic long-book extraction and global multi-entity atomicity remain incomplete.

### D07 · World characters continuity

- **Scope:** P1; dependencies D05; D06; original IDs D01; D02; D03; D04; D05; D06; D07; E01; E02; E03; E04; E05; E06; F01; F02; F03; F04; F05; F06; F07; F08; F09; F10; G01; G02; G03; G04; G05; G06; G07
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Typed HISTORY/GEOGRAPHY/CIVILIZATION/ABILITY/PSYCHOLOGY records plus exact-evidence optional selected-model suggestions/local explicit rule extraction; existing rule/findings/graph retained.
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** New reviewed drafts do not constitute semantic engines or automatically join Canon/checker rules; real model quality unverified.

### D08 · Screenplay storyboard transitions

- **Scope:** P1; dependencies D03; D04; original IDs I01; I02; I03; I04; I05; I06; I07; I08; I09; J01; J02; J03; J04; K01; K02; K03; K04; K05; K06; K07; K08
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Branch-aware screenplay operations, approved revision fork preserving assets, shot/card/prompt fields and source-linked exports.
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Specialized model-assisted shot/composition/camera/transition quality and complete independent scene/shot revision UX remain limited.

### D09 · Resource packages and documents

- **Scope:** P1; dependencies D02; D08; original IDs I01; I02; I03; I04; I05; I06; I07; I08; I09; M01; M02; M03; M04; M05; M06; M07; T01; T02; T03; T04; T05; T06; T07
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Three frozen resource ZIP formats connected to queue/API/UI; bounded owned bytes; licensed pinned CJK font and PDF embedding/render evidence.
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Target Word/Final Draft/EPUB/NLE interoperability, typography and archive reimport remain independent gaps.

### D10 · Images references assets

- **Scope:** P2; dependencies D04; D07; original IDs J01; J02; J03; J04; L01; L02; L03; L04; L05; L06; L07; L08; L09; L10; M01; M02; M03; M04; M05; M06; M07
- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Persistent image queue/review, real decoder checks, approved lexical reference index, digest-safe assets/lineage/trash/restore.
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real image/vision models, embeddings/semantic identity, cover/storyboard-specific generation and bulk governance/reimport remain gaps. Existing canvas zoom/pan/select/drag/align/group/layer/lock/undo is retained.

### D11 · Video tasks and timeline

- **Scope:** P2; dependencies D08; D10; original IDs K01; K02; K03; K04; K05; K06; K07; K08; M01; M02; M03; M04; M05; M06; M07; N01; N02; N03; N04; N05; N06
- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Frame/prompt consent, fenced submit/cancel/callback, SSRF-safe actual download/decode, ordered trimmed silent review-cut output. Motion cloud review is now complete-request-bound and final dispatch reauthorizes all inputs; legacy remote asset workers are fail-closed rather than implicitly consented.
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No real video model, bundled Windows codec distribution, soundtrack/final master/NLE conformance or vendor-specific asymmetric callbacks.

### D12 · Voices and audiobook

- **Scope:** P2; dependencies D04; D07; original IDs M01; M02; M03; M04; M05; M06; M07; O01; O02; O03; O04
- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Durable voice/dictionary/provenance, immutable consent-checked sentence queues, verified audio, order-preserving PCM concatenate/export.
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real TTS/voices, expressive emotion, auto multi-character attribution, mixed-format mastering and phoneme-aligned subtitles absent/unrun.

### D13 · Agent and workflow execution

- **Scope:** P2; dependencies D04; D05; D06; D08; original IDs H01; H02; H03; H04; H05; H06; H07; Q01; Q02; Q03; Q04
- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Bounded persistent authorized DAG with genuine Agent-job dispatch/completion and review; three tested local rule artifact recipes. Full-scope epoch/remount guards close original stale cross-project UI leak; automatic memory extraction is guarded-local-only and safe when no route is configured. bbb owns/cancels Agent timers and prevents deleted jobs from being recreated by late callbacks.
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/browser-ci-repair.md; docs/delivery/dot-astra-rc-r2/evidence/agent-timer-cleanup.txt; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md
- **Remaining acceptance:** Recipes are not autonomous domain-apply loops; real-model role quality and transactional multi-worker/crash-gap scheduling incomplete.

### D14 · Comments and unified review

- **Scope:** P1/P2; dependencies D03; D06; original IDs S01; S02; S03; S04
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Version/hash/quote-anchored persistent comments, trusted actor, stale markers, resolve/reopen/reply and history/UI.
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Separate import/Canon/Agent/media queues are not a unified approval inbox. Final bounded browser/permission regression passes; full target-desktop multiuser acceptance is NOT_RUN.

### D15 · Plugin management and isolation

- **Scope:** P2; dependencies D00; D01; D04; original IDs P01; P02; P03; P04; P05
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Integrity-checked local declarative install/update/rollback/recoverable remove and grant reset; PR 26 independently inspected.
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Executable runtime DISCONNECTED/DENY_ALL; real Windows isolation/broker absent; packaged/collaboration lifecycle writes blocked without Host-admin authority.

### D16 · Migration backup and restore

- **Scope:** P0/P1; dependencies D01; original IDs A01; A02; A03; A04; A05; A06; A07; A08; A09; A10
- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Stricter File/PG migration and non-destructive exclusive backup/new-target restore; exact inventory/digests and whole runtime sidecars included.
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-work.md; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/evidence/ci-93d.json; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-native-smoke.json; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-provenance-check.json; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Actual 93d PG 2155/37 and native Windows new-database dump restore pass; process/restart/revocation cases are exercised. Native ACL/power-loss/interactive install lifecycle remain NOT_RUN; sidecars are not all migrated to SQL.

### D17 · Usability and Opus handoff

- **Scope:** P0/P1; dependencies D00; original IDs A01; A02; A03; A04; A05; A06; A07; A08; A09; A10; B01; B02; B03; B04; B05; B06; B07; B08; B09; B10; B11; B12; B13; C01; C02; C03; C04; C05; C06; C07; C08; C09; C10; D01; D02; D03; D04; D05; D06; D07; E01; E02; E03; E04; E05; E06; F01; F02; F03; F04; F05; F06; F07; F08; F09; F10; G01; G02; G03; G04; G05; G06; G07; H01; H02; H03; H04; H05; H06; H07; I01; I02; I03; I04; I05; I06; I07; I08; I09; J01; J02; J03; J04; K01; K02; K03; K04; K05; K06; K07; K08; L01; L02; L03; L04; L05; L06; L07; L08; L09; L10; M01; M02; M03; M04; M05; M06; M07; N01; N02; N03; N04; N05; N06; O01; O02; O03; O04; P01; P02; P03; P04; P05; Q01; Q02; Q03; Q04; R01; R02; R03; R04; R05; S01; S02; S03; S04; T01; T02; T03; T04; T05; T06; T07
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Existing shell/tokens retained; real forms/history/errors/review/recovery and LocalAI entry connected. Scoped goal-field layout preserves global design rules and passes final actual three-viewport geometry and reviewed screenshots.
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/revision-history-work.md; docs/delivery/dot-astra-rc-r2/evidence/revision-history.xml; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md; docs/delivery/dot-astra-rc-r2/writing-goal-layout-work.md; docs/delivery/dot-astra-rc-r2/evidence/writing-goal-layout.xml; docs/delivery/dot-astra-rc-r2/evidence/screenshots/manifest.json; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_FINAL_INCREMENT.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Final 98b UI 579/111, geometry 9, business 2 with all three goal-layout viewports and export 1 pass; six screenshots verified/reviewed. Broader visual polish, native IME/accessibility and user acceptance remain separate.

### D18 · Build Windows delivery

- **Scope:** P0/P1; dependencies D02; D03; D04; D09; D16; D17; original IDs A01; A02; A03; A04; A05; A06; A07; A08; A09; A10; B01; B02; B03; B04; B05; B06; B07; B08; B09; B10; B11; B12; B13; C01; C02; C03; C04; C05; C06; C07; C08; C09; C10; D01; D02; D03; D04; D05; D06; D07; E01; E02; E03; E04; E05; E06; F01; F02; F03; F04; F05; F06; F07; F08; F09; F10; G01; G02; G03; G04; G05; G06; G07; H01; H02; H03; H04; H05; H06; H07; I01; I02; I03; I04; I05; I06; I07; I08; I09; J01; J02; J03; J04; K01; K02; K03; K04; K05; K06; K07; K08; L01; L02; L03; L04; L05; L06; L07; L08; L09; L10; M01; M02; M03; M04; M05; M06; M07; N01; N02; N03; N04; N05; N06; O01; O02; O03; O04; P01; P02; P03; P04; P05; Q01; Q02; Q03; Q04; R01; R02; R03; R04; R05; S01; S02; S03; S04; T01; T02; T03; T04; T05; T06; T07
- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL
- **Before:** Inherited f8c141c baseline; see mapped feature before values and historical audit excerpts. Historical DONE and percentages are not accepted as current verification.
- **After:** Fresh official input lock/materializer prepared 4876 files without user data; new native base verifier and full unsigned internal Windows package CI are implemented. global.json pins .NET SDK 8.0.424; self-contained Host restores/publishes the .NET 8 runtime with full recorded license notices. Native verifier now uses bounded file-backed command output capture and owned-PID cleanup; focused failure controls pass.
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/R2_WINDOWS_BASE_INPUTS.md; packaging/windows-runtime-inputs.json; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; tests/test_r2_windows_native_verifier.py; scripts/verify_windows_base.py; docs/delivery/dot-astra-rc-r2/evidence/ci-93d.json; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-native-smoke.json; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-provenance-check.json; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_FINAL_INCREMENT.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Final 98b Windows SDK 8.0.424 Host 59, complete unsigned package and real native base PASS with exact artifact digests. External Evergreen/VC++ x64 prerequisites, clean interactive install/upgrade/uninstall/IME/signing/user acceptance remain separate.

## Original A–T inventory

States are implementation / integration / verification, followed by user-visible availability. Original D01–D07 feature codes are distinct from D01–D07 work-package IDs. Per-row requirement/API/storage/dependency/version details remain in JSON; shared verification and final acceptance rules above apply to each row.

### A. Desktop runtime

#### A01 · Embedded desktop frontend

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P0; packages D04; D16; D18
- **Before:** WebView2 Host/static frontend already existed.
- **After:** Retained packaged Host/React bridge; UI extensions use the same shell.
- **Entry:** frontend/src/packagedHost.ts
- **Source:** app/packaging/packaged_desktop_host.py; app/packaging/static_frontend.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Interactive Windows/WebView2 lifecycle and screenshots still NOT_RUN.

#### A02 · Desktop launch and child lifecycle

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P0; packages D04; D16; D18
- **Before:** Packaged launcher and owned-process controls existed.
- **After:** Existing launcher retained; Windows build/provenance work is separate from an installable full runtime.
- **Entry:** frontend/src/packagedHost.ts
- **Source:** app/packaging/packaged_desktop_launcher.py; app/packaging/packaged_launcher.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Clean install, upgrades, uninstall data retention and actual window launch remain pending.

#### A03 · FastAPI application

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0; packages D04; D16; D18
- **Before:** Versioned API and service composition existed.
- **After:** New authoring/media/workflow/plugin routers registered through existing app composition.
- **Entry:** frontend/src/packagedHost.ts; frontend/src/ui/ModelCenter.tsx
- **Source:** app/main.py; app/packaging/packaged_desktop_host.py; app/packaging/packaged_processes.py; app/packaging/runtime_lifecycle.py; app/model_runtime.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Final File/PostgreSQL/application/browser regression passes. Interactive desktop and real-provider acceptance remain separate.

#### A04 · Bundled PostgreSQL runtime

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P0; packages D04; D16; D18
- **Before:** Packaged PostgreSQL bootstrap existed.
- **After:** Privacy migration and original packaged bootstrap retained. Fresh origin-pinned CPython/PyPI/EDB PostgreSQL input assembly replaces reliance on a historical user BaseApplication; actual 4876-file Linux preparation completed.
- **Entry:** frontend/src/packagedHost.ts
- **Source:** app/packaging/packaged_processes.py; app/packaging/database_bootstrap.py; scripts/prepare_windows_base.py; scripts/verify_windows_base.py; packaging/windows-runtime-inputs.json
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/R2_WINDOWS_BASE_INPUTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-native-smoke.json; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-provenance-check.json; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Actual 98b packaged Windows Python/PostgreSQL smoke and unsigned internal package pass. Clean Windows prerequisite setup, interactive startup and install/upgrade/uninstall acceptance remain NOT_RUN.

#### A05 · Database migration

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0; packages D04; D16; D18
- **Before:** Migration ledger through inherited schema existed.
- **After:** Migration 018 persists/validates foreshadowing policy and preserves stricter imported policies.
- **Entry:** frontend/src/packagedHost.ts
- **Source:** app/packaging/postgres_migrations.py; database/migrations/018_context_privacy.sql
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-native-smoke.json; docs/delivery/dot-astra-rc-r2/evidence/ci-93d-provenance-check.json; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Actual 98b PostgreSQL suite2155/37 and native pgcrypto/UTF8/new-database restore pass. Interactive Windows upgrade, ACL/power-loss and user acceptance remain separate NOT_RUN checks.

#### A06 · Restart, shutdown and recovery

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P0; packages D04; D16; D18
- **Before:** Owned-process lifecycle and generation recovery existed.
- **After:** Non-destructive verified backup/restore added; interrupted Agent jobs fail for explicit retry.
- **Entry:** frontend/src/packagedHost.ts
- **Source:** app/packaging/runtime_lifecycle.py; app/backup_restore.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Windows process/ACL/power-loss checks remain unrun.

#### A07 · Desktop bridge

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P0; packages D04; D16; D18
- **Before:** Trusted Host bridge existed.
- **After:** Bridge preserved; new UI does not put provider secrets in browser storage.
- **Entry:** frontend/src/packagedHost.ts
- **Source:** app/packaging/desktop_bridge.py; app/packaging/host_uplink.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real WebView2 interaction and Host authorization handoff pending.

#### A08 · Trusted session and credential boundary

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P0; packages D04; D16; D18
- **Before:** Opaque session and OS vault architecture already existed.
- **After:** Legacy supported provider dispatch resolves vault entries; packaged env-only key is insufficient.
- **Entry:** frontend/src/novel/DeepSeekCredentialControl.tsx
- **Source:** app/credential_vault.py; app/trusted_sessions.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Native Windows vault/Host end-to-end remains unrun.

#### A09 · Text provider execution

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P0; packages D04; D16; D18
- **Before:** Compatible adapter and old real-provider history existed; current source egress guard was incomplete.
- **After:** Last-send source/version/privacy checks, native Claude/Gemini protocols, cancellation/usage and explicit Mock disclosure.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/providers.py; app/openai_compatible.py; app/native_text_providers.py; app/jobs.py; app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** No current real provider, credential, billing or quality verification; full v2 authoritative broker incomplete.
- **Subcapability Optional Local AI Discovery registration/route bridge:** implementation_state=PARTIAL; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; verification_scope=See row_evidence_contract.local_ai_scope and LAD runtime-specific evidence.; user_visible_state=EXPERIMENTAL; evidence=docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md

#### A10 · Multi-provider/model routing

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P0; packages D04; D16; D18
- **Before:** Catalog and explicit text/media adapters existed.
- **After:** Explicit compatible/native routes and the mounted two-alias Local AI state machine reuse existing registries. Positive locality, current identity/authority, buffered Writer dispatch and validated external aliases passed independent e38 invariants.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_runtime.py; app/provider_runtime_v2_routing_service.py; app/providers.py; app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_packaged_desktop_composition_v070.py; tests/test_runtime_ownership_foundation_v070.py; tests/test_packaged_postgres_migrations_v070.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/BASELINE_RECEIPT.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Real Windows/GPU/model routing acceptance NOT_RUN. Multiple named vault profiles and full authoritative v2 compatibility/budget broker remain incomplete.
- **Subcapability Optional Local AI Discovery registration/route bridge:** implementation_state=PARTIAL; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; verification_scope=See row_evidence_contract.local_ai_scope and LAD runtime-specific evidence.; user_visible_state=EXPERIMENTAL; evidence=docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md

### B. Novel authoring

#### B01 · Novel/project creation

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** Novel creation and basic overview already existed.
- **After:** Core creation retained; persisted plans/comments/goal entries extend project workflow.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 98b browser save/reopen journey passes. No claim of all unseen historical overview requirements; final 98b hosted gates also passed; remaining acceptance is item-specific.

#### B02 · Workspace organization

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** Workspace/storyline/branch identity and basic navigation existed.
- **After:** Existing identity model reused by new routes; no parallel accounts.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Interactive multi-user desktop acceptance pending.

#### B03 · Chapter lifecycle

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** Create/archive/duplicate/move chapter operations existed.
- **After:** Existing atomic lifecycle reused by creation/import/audio references.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 98b backend and browser lifecycle gates pass; native crash/power-loss acceptance remains separate.

#### B04 · Editor and saving

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** TipTap editor, versioned writes and unsaved conflict handling existed.
- **After:** Retained editor/save contract and generation acceptance boundary.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 98b browser authoring/recovery journey passes. Native crash/Chinese IME/undo/keyboard desktop acceptance remains NOT_RUN.

#### B05 · Chapter version history

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** Persistent chapter revisions existed.
- **After:** History remains authoritative and is now keyed by chapter server version plus opaque scoped observer identity, so AI Accept/manual save/restore refresh the mounted timeline. Late list/detail/restore results are fenced across full context changes, including A→B→A; tokens do not enter cache keys.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py; frontend/src/AppRevisionHistory.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/revision-history-work.md; docs/delivery/dot-astra-rc-r2/evidence/revision-history.xml; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Independent StrictMode/history controls and actual 98b browser first-reload, AI Accept and revision restore journey pass. Broader native unexpected-exit acceptance remains NOT_RUN.

#### B06 · Version restore

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** Optimistic version restore existed.
- **After:** Restore captures API context and revisions, validates chapter identity and updates existing App hydration without reloading. Newer cached versions do not regress; newer local dirty buffers are preserved in the existing persistent version-conflict flow. Plan restore remains a new reviewable draft.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py; frontend/src/AppRevisionHistory.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/revision-history-work.md; docs/delivery/dot-astra-rc-r2/evidence/revision-history.xml; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Real App clean/dirty context-fencing controls and actual 98b browser restore/conflict flow pass. Native unexpected-exit/IME combinations remain NOT_RUN.

#### B07 · AI continuation

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P0/P1; packages D03; D05
- **Before:** Continue operation existed but old baseline could send raw restricted source.
- **After:** Version/hash/privacy-bound actual dispatch; returned content remains Draft until Accept.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 98b Draft/Diff/Accept/recovery browser flow passes with synthetic provider. Real model inference/output quality remains NOT_RUN.

#### B08 · AI rewrite

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P0/P1; packages D03; D05
- **Before:** Rewrite/selection and review path existed.
- **After:** Actual egress rechecks, selected-text membership, owner-scoped job access and repeat-safe accept enforced.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real-provider output quality and interrupted live stream NOT_RUN.

#### B09 · AI polishing (inferred label)

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P0/P1; packages D03; D05
- **Before:** Generic operation dispatch existed; audit omitted precise historical name.
- **After:** Current polish operation shares guarded generation, Draft/Diff/Accept and failure handling.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Precise original definition unavailable; real model NOT_RUN.

#### B10 · AI brainstorming (inferred label)

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P0/P1; packages D03; D05
- **Before:** Generic operation dispatch existed; audit omitted precise historical name.
- **After:** Current brainstorm operation shares guarded generation and review.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Precise original definition unavailable; real model NOT_RUN.

#### B11 · Multiple writing candidates

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P0/P1; packages D03; D05
- **Before:** Variant endpoint and comparison UI existed despite historical TODO.
- **After:** Multiple persisted candidates and Diff/explicit selection remain. Accept now uses the captured generation base and a durable serialized single-host acceptance claim; stale/current-version injection and concurrent duplicate side effects are rejected.
- **Entry:** frontend/src/App.tsx; frontend/src/novel/AiWritingPanel.tsx; frontend/src/RevisionPanel.tsx
- **Source:** app/services/novel_service.py; app/services/chapter_service.py; app/services/generation_service.py; app/jobs.py; app/source_privacy.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_acceptance_integrity.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 98b PG suite and browser acceptance pass, including explicit process/restart/authority coverage inherited from55a. Candidate synthesis remains missing; ambiguous interrupted Accept requires review; real model quality remains NOT_RUN.

#### B12 · Reusable writing style

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** Only one-off style strings/presets existed.
- **After:** Typed versioned STYLE drafts, approval, history/restore and actual generation input with last-hop review recheck. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/App.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/creation_workbench_service.py; app/creation_workbench_api.py; app/api.py; app/jobs.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Manual style authoring works; no learned style model; generation requires separately configured provider.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### B13 · Writing goals and progress

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D03; D05
- **Before:** Goal APIs and App goal display/editor already existed.
- **After:** Existing targets/deadline/current counts retained and chapter operations refresh progress. Scoped writing-goal fields now use token-based single-column stacking with contained full-width inputs; post-fix actual browser geometry passes all three documented viewports.
- **Entry:** frontend/src/App.tsx
- **Source:** app/services/novel_service.py; app/api.py
- **Tests:** tests/test_core.py; tests/test_chapter_concurrency.py; tests/test_generation_idempotency_contracts.py; tests/test_generation_variants_phase3.py; tests/test_r2_generation_egress.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; frontend/tests/writingGoalLayout.test.ts
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/writing-goal-layout-work.md; docs/delivery/dot-astra-rc-r2/evidence/writing-goal-layout.xml; docs/delivery/dot-astra-rc-r2/evidence/screenshots/manifest.json; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_FINAL_INCREMENT.md; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Scoped writing-goal layout passes actual final 98b three-viewport geometry and reviewed screenshots. Goals/progress remain bounded manual features; no new analytics or interactive native-user acceptance claim.

### C. Import and knowledge review

#### C01 · TXT import

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D03; D06
- **Before:** TXT parsing and chapter import existed.
- **After:** Existing parser reused with durable versioned knowledge review and safe application journal.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Measured 200-chapter/1,002,092-character synthetic File fixture exists (evidence/synthetic-scale.json); native picker and target-hardware performance acceptance pending.

#### C02 · Markdown import

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D03; D06
- **Before:** Markdown parsing/import existed.
- **After:** Existing parser and source content retained; review can reopen.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** A measured million-character synthetic File fixture exists; malformed mixed-layout document coverage remains limited.

#### C03 · DOCX import

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D03; D06
- **Before:** DOCX parsing/import existed.
- **After:** Parser remains actual file reader; review journal prevents silent all-or-nothing false success.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Target Word layouts and edge-case embedded content require independent acceptance.

#### C04 · PDF import

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D03; D06
- **Before:** PDF text extraction/fallback existed.
- **After:** Existing text extraction retained; no OCR pipeline added.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Scanned/image-only PDFs and layout reconstruction not implemented as reliable import.

#### C05 · Import structure analysis

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D03; D06
- **Before:** Adaptation/review could hold structure proposals.
- **After:** Bounded local heuristics emit exact version/hash/offset evidence; optional AI review remains review-only. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Explicit-marker rule/plot proposals now exist separately from four-group import review. Natural-language rule/structure quality, cross-chapter identity, interrupted large-book analysis and hierarchy generation remain incomplete.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=EXPERIMENTAL
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### C06 · Character extraction/review

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D03; D06
- **Before:** Review surface existed without deterministic extraction closure.
- **After:** Heuristic English/Chinese names, within-chapter dedupe, editable versioned review and journaled accepted upserts.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No cross-chapter identity resolution guarantee; homonym quality needs real corpus evaluation.

#### C07 · Location extraction/review

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D03; D06
- **Before:** Review model could store location candidates.
- **After:** Bounded place-name heuristics with source evidence and explicit accepted application.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Heuristic false positives remain; geographic semantics and long-form quality unverified.

#### C08 · Import timeline candidates

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D03; D06
- **Before:** Timeline CRUD existed; import linkage incomplete.
- **After:** Chapter-derived timeline candidates carry source locations and manual review/application.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** A chapter summary is not temporal reasoning; precise event chronology extraction remains incomplete.

#### C09 · Import foreshadowing candidates

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D03; D06
- **Before:** Foreshadowing/canon review existed.
- **After:** Cue-based candidate extraction, privacy, selection and checkpointed application connected.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Semantic setup/payoff matching and rule extraction remain incomplete.

#### C10 · Adapt unfinished novel

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible NOT_CONFIGURED; P1; packages D03; D06
- **Before:** Adaptation service and reviewable generation workflow existed.
- **After:** Independent R2 audit found unreviewed adaptation-source cloud dispatch in eb165609. Current repair adds source/hash/version/project-policy/branch reauthorization immediately before normalized dispatch; historical snapshots without current consent remain local-only. Output stays reviewable Draft.
- **Entry:** frontend/src/novel/NovelImportPanel.tsx
- **Source:** app/import_parsers.py; app/knowledge_extraction.py; app/services/import_review_service.py; app/services/import_apply_service.py; app/services/adaptation_service.py; app/source_privacy.py
- **Tests:** tests/test_import_parsers.py; tests/test_import_ai_review.py; tests/test_r2_import_boundaries.py; tests/test_r2_import_apply_journal.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx; tests/test_r2_dispatch_revalidation.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/import-apply-checkpoints.md; docs/delivery/dot-astra-rc-r2/evidence/synthetic-scale.json; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Recording-transport invariant and complete 98b hosted suites pass. Real model adaptation quality and long-book semantic acceptance remain NOT_RUN.

### D. World knowledge

#### D01 · Lore/world knowledge base

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D06; D07
- **Before:** Lore evidence/proposals/memory existed.
- **After:** Stricter privacy filtering and reviewed manual typed structures reuse existing project identity. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/lore_service.py; app/lore/continuity_engine.py; app/services/creation_workbench_service.py; app/services/novel_service.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Full semantic world model and evidence-quality acceptance incomplete.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D02 · World rules

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D06; D07
- **Before:** Approved rule registry and forbidden-term checks existed.
- **After:** Conservative privacy persistence and manual structure references retained. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/lore_service.py; app/lore/continuity_engine.py; app/services/creation_workbench_service.py; app/services/novel_service.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Model/local explicit proposals become ABILITY drafts and require separate review; they do not automatically enter the approved world-rule registry or semantic checker.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D03 · Historical event records

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D06; D07
- **Before:** No dedicated historical-event structure found in baseline audit.
- **After:** HISTORY record kind has schema, versions, API, approval/restore and UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/lore_service.py; app/lore/continuity_engine.py; app/services/creation_workbench_service.py; app/services/novel_service.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Manual and model-proposed source-evidenced records now exist; historical chronology inference and automatic Canon/checker integration remain absent.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=EXPERIMENTAL
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D04 · Geography structures

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D06; D07
- **Before:** Location CRUD was not a geography system.
- **After:** GEOGRAPHY records support referenced locations, rules and versioned review. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/lore_service.py; app/lore/continuity_engine.py; app/services/creation_workbench_service.py; app/services/novel_service.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Geography drafts can be model-proposed with evidence; no map/topology/path or geographic consistency engine.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=EXPERIMENTAL
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D05 · Civilization/organization structures

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D06; D07
- **Before:** No dedicated civilization product found.
- **After:** CIVILIZATION record kind persisted with constraints, references, version/review UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/lore_service.py; app/lore/continuity_engine.py; app/services/creation_workbench_service.py; app/services/novel_service.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Civilization drafts can be model-proposed with evidence; simulation/hierarchy reasoning and automatic Canon integration absent.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=EXPERIMENTAL
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D06 · Ability/power structures

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D06; D07
- **Before:** No dedicated ability product found.
- **After:** ABILITY records retain rules, references, history and explicit approval. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/lore_service.py; app/lore/continuity_engine.py; app/services/creation_workbench_service.py; app/services/novel_service.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Explicit-marked or model-proposed rules can become reviewed drafts; no power-system solver or automatic formal rule installation.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=EXPERIMENTAL
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### D07 · World consistency checks

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D06; D07
- **Before:** Deterministic continuity/rule service existed.
- **After:** Existing findings retained with stricter policy/source boundaries.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/lore_service.py; app/lore/continuity_engine.py; app/services/creation_workbench_service.py; app/services/novel_service.py; app/creation_workbench_api.py
- **Tests:** tests/test_lore_contract.py; tests/test_world_rule_payload.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Full semantic aggregate consistency and new manual-record-to-rule engine integration incomplete.

### E. Characters

#### E01 · Character records

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D07
- **Before:** Character CRUD and editor existed.
- **After:** Existing persistent character records retained and usable by reference validation.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/WorldRelationshipGraph.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/v1_capability_service.py; app/services/creation_workbench_service.py; app/review.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Exhaustive interactive cross-branch character acceptance remains NOT_RUN.

#### E02 · Character attributes

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D07
- **Before:** Flexible character metadata existed.
- **After:** Existing attributes plus referenced versioned manual psychology records available.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/WorldRelationshipGraph.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/v1_capability_service.py; app/services/creation_workbench_service.py; app/review.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No comprehensive typed/versioned character attribute schema migration delivered.

#### E03 · Character relationships/graph

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D07
- **Before:** Relationship CRUD and graph/filter view already existed.
- **After:** Actual relationship graph retained; new plans can reference entities.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/WorldRelationshipGraph.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/v1_capability_service.py; app/services/creation_workbench_service.py; app/review.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No automatic inferred relationship acceptance or causal reasoning claim.

#### E04 · Character growth records

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D07
- **Before:** Evolution records/editor already existed.
- **After:** Existing evidence/version-linked evolution records retained.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/WorldRelationshipGraph.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/v1_capability_service.py; app/services/creation_workbench_service.py; app/review.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Dedicated growth planner/route visualization and integration with all new records incomplete.

#### E05 · Psychological records/engine

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P1; packages D07
- **Before:** No psychological-state engine found.
- **After:** PSYCHOLOGY record kind adds manual schema, references, approval/version/restore/UI. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/WorldRelationshipGraph.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/novel_service.py; app/services/v1_capability_service.py; app/services/creation_workbench_service.py; app/review.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Evidence-bound psychology suggestions can become reviewed drafts; no psychological-state inference/simulation engine or validated character-quality benchmark.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=EXPERIMENTAL
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### E06 · Character consistency

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1; packages D07
- **Before:** Deterministic check endpoint/editor action existed.
- **After:** Current rule checks and evidence findings retained.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/WorldRelationshipGraph.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/v1_capability_service.py; app/services/creation_workbench_service.py; app/review.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase4_characters.py; tests/test_phase4_relationships.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Complete persistent semantic consistency workflow/quality catalog incomplete.

### F. Plot planning

#### F01 · AI outline generation

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1; packages D05; D07
- **Before:** Manual outline editor existed, no dedicated outline generator.
- **After:** Approved PLOT instructions feed existing text generation; selected-model Agent can propose text. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Structured PLOT candidates feed approved generation input, but full outline→volume→chapter→scene decomposition/review/apply hierarchy remains incomplete.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=NOT_RUN; user_visible_state=EXPERIMENTAL
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F02 · Three-act planning

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** No typed three-act domain record found.
- **After:** PLOT requires three acts/conflict/climax/ending; versions, compare, approval and generation input connected. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Manual three-act record closure and bounded structured proposals exist; real-provider/plot-quality acceptance NOT_RUN.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F03 · Volume planning

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** Volume APIs and editor existed.
- **After:** Existing persisted manual volume planning retained.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No automatic AI decomposition/acceptance claim; final bounded API/UI regression passes; full semantic/user acceptance remains NOT_RUN.

#### F04 · Chapter outline planning

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** Outline APIs and editor existed.
- **After:** Existing persisted outline retained and privacy-filtered in outbound contexts.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Dedicated AI outline generation is separate F01 gap.

#### F05 · Scene planning

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** Scene APIs/editor existed.
- **After:** Existing scene planning reused by screenplay/media references.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No automatic semantic scene design guarantee.

#### F06 · Main story routes

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** Story route/thread CRUD existed.
- **After:** Existing routes remain referencable from versioned PLOT records.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Full graphical route-to-manuscript planning remains a limited manual workflow.

#### F07 · Subplot routes

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** Route type/branch metadata and editor existed.
- **After:** Existing subplot records retained without inventing analytics.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Dedicated subplot balance/causal analytics absent.

#### F08 · Conflict design

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** Continuity finding proposals existed without design assistant.
- **After:** Typed required PLOT conflict, comparison and approved generation input added. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Structured conflict proposals require exact source evidence and explicit review; no broader semantic conflict-quality engine.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F09 · Climax planning

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** No dedicated climax planning model found.
- **After:** Required PLOT climax, versions, source linkage and generation input added. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Structured climax proposals require exact source evidence and explicit review; no automated tension/pacing measurement.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

#### F10 · Multiple ending planning

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D05; D07
- **Before:** Collaboration branches were not ending plans.
- **After:** Multiple separately versioned PLOT endings can compare and be selected for generation. Structured planning now supports exact-evidence selected-model proposals and explicit-marker local ABILITY/PLOT extraction, then idempotent save as DRAFT and separate existing edit/compare/approve/history.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx; frontend/src/novel/AIPlanningPanel.tsx
- **Source:** app/services/novel_service.py; app/services/creation_workbench_service.py; app/narrative.py; app/creation_workbench_api.py; app/services/ai_planning_service.py; app/ai_planning_api.py; app/planning_extraction.py
- **Tests:** tests/test_phase5_outline.py; tests/test_phase5_volumes.py; tests/test_phase5_scenes.py; tests/test_phase5_story_routes.py; tests/test_r2_creation_workbench.py; tests/test_r2_ai_planning.py; frontend/src/novel/AIPlanningPanel.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Multiple source-bound structured endings can be proposed/compared; no graph of consequence propagation or automatic branch-to-manuscript synthesis.
- **Subcapability Existing manual/domain operations:** integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE
- **Subcapability Selected-model structured planning suggestions:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=MOCK_ONLY; user_visible_state=NOT_CONFIGURED; limit=At most 3 chapters (model excerpts first 16000 characters each), 1–3 strict JSON suggestions with exact quote/offset/hash/version evidence; no real model calls, semantic-quality certification, full outline hierarchy or automatic Canon/manuscript writes.
- **Subcapability Explicit marker rule/plot extraction:** implementation_state=IMPLEMENTED; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; user_visible_state=AVAILABLE; limit=Only explicit bilingual rule lines or complete six-field three-act markers; incomplete/duplicate plot markers yield findings. Saves ABILITY/PLOT DRAFT only; not automatic extraction of unstated facts.

### G. Foreshadowing and continuity

#### G01 · Foreshadowing records

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D01; D07
- **Before:** Foreshadowing CRUD and PendingCanon existed.
- **After:** Persisted strict privacy fixes plus reviewable extracted candidates integrated.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/ContinuityCheckPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/narrative_finding_service.py; app/services/continuity_finding_service.py; app/lore/continuity_engine.py; app/review.py
- **Tests:** tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Complete 98b actual PostgreSQL regression passes; target native crash/power-loss and user acceptance remain separate.

#### G02 · Foreshadowing payoff tracking

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D01; D07
- **Before:** Tracker/lifecycle metadata existed.
- **After:** Existing status/reminder display retained with durable privacy.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/ContinuityCheckPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/narrative_finding_service.py; app/services/continuity_finding_service.py; app/lore/continuity_engine.py; app/review.py
- **Tests:** tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Comprehensive payoff linkage and semantic lifecycle audit incomplete.

#### G03 · Overdue reminders

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D01; D07
- **Before:** Chapter-aware reminder query/UI existed.
- **After:** Existing deterministic reminders retained.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/ContinuityCheckPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/narrative_finding_service.py; app/services/continuity_finding_service.py; app/lore/continuity_engine.py; app/review.py
- **Tests:** tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No scheduled/background notification delivery; query is not a notification service.

#### G04 · Timeline conflict checks

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D01; D07
- **Before:** Deterministic continuity timeline conflict rules existed.
- **After:** Rules retained; stricter timeline serialization prevents cloud leakage.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/ContinuityCheckPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/narrative_finding_service.py; app/services/continuity_finding_service.py; app/lore/continuity_engine.py; app/review.py
- **Tests:** tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Coverage limited to implemented rules; full story temporal reasoning not claimed.

#### G05 · Behavior consistency

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1; packages D01; D07
- **Before:** Deterministic character behavior rules existed.
- **After:** Existing checks retained with source-aware runtime filtering.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/ContinuityCheckPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/narrative_finding_service.py; app/services/continuity_finding_service.py; app/lore/continuity_engine.py; app/review.py
- **Tests:** tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Semantic behavior model and broad evidence-based rule catalog incomplete.

#### G06 · World-rule violation checks

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1; packages D01; D07
- **Before:** Approved rules/forbidden-term check existed.
- **After:** Conservative policy preserves approved source restrictions.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/ContinuityCheckPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/narrative_finding_service.py; app/services/continuity_finding_service.py; app/lore/continuity_engine.py; app/review.py
- **Tests:** tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Semantic interpretation of arbitrary world/ability rules incomplete.

#### G07 · Plot findings and resolution

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D01; D07
- **Before:** Findings/check/resolve APIs and UI existed.
- **After:** Existing workflow retained; human resolution remains explicit. Automatic post-Accept memory extraction only uses explicitly enabled guarded local TextModelNode registrations or labeled non-packaged test Mock; no safe local route records NOT_CONFIGURED without undoing accepted text. It never falls back to cloud.
- **Entry:** frontend/src/novel/StoryDatabase.tsx; frontend/src/novel/ContinuityCheckPanel.tsx; frontend/src/novel/WorldBuildingDashboard.tsx
- **Source:** app/services/narrative_finding_service.py; app/services/continuity_finding_service.py; app/lore/continuity_engine.py; app/review.py
- **Tests:** tests/test_phase4_foreshadowing.py; tests/test_narrative_detection.py; tests/test_continuity_lifecycle.py; tests/test_r2_privacy_persistence.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/privacy-recovery-focused.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No assertion all narrative plot holes can be detected.

### H. Agent team

#### H01 · Planning Agent

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D04; D13
- **Before:** Agent catalog/job primitives existed.
- **After:** Guarded selected-model executor connected; local planning recipe explicitly uses user-supplied input. Owned Agent timeout timers are cancelled on completion/cancel; deleted jobs/projects are not recreated by late timers.
- **Entry:** frontend/src/novel/AgentTeamPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx; frontend/src/novel/AgentResultReview.tsx
- **Source:** app/agent_catalog.py; app/services/agent_job_service.py; app/services/agent_context_service.py; app/workflow_api.py; app/model_runtime.py
- **Tests:** tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/browser-ci-repair.md; docs/delivery/dot-astra-rc-r2/evidence/agent-timer-cleanup.txt; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md
- **Remaining acceptance:** Specialized structured planning outputs/domain application and real model quality incomplete.

#### H02 · Writing Agent

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D04; D13
- **Before:** Generation/Agent review/apply existed.
- **After:** Actual selected-model job execution, source/usage provenance and restart failure recovery connected.
- **Entry:** frontend/src/novel/AgentTeamPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx; frontend/src/novel/AgentResultReview.tsx
- **Source:** app/agent_catalog.py; app/services/agent_job_service.py; app/services/agent_context_service.py; app/workflow_api.py; app/model_runtime.py
- **Tests:** tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real provider NOT_RUN; generated work still needs explicit review/apply.

#### H03 · Editing Agent

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D04; D13
- **Before:** Generic review/apply roles existed.
- **After:** Guarded executor shared; result approval remains explicit.
- **Entry:** frontend/src/novel/AgentTeamPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx; frontend/src/novel/AgentResultReview.tsx
- **Source:** app/agent_catalog.py; app/services/agent_job_service.py; app/services/agent_context_service.py; app/workflow_api.py; app/model_runtime.py
- **Tests:** tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Dedicated editorial policy/quality engine not delivered.

#### H04 · Continuity Agent

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D04; D13
- **Before:** Continuity service existed, orchestration incomplete.
- **After:** Agent nodes wait for real jobs; deterministic continuity remains separate. Automatic post-Accept memory extraction only uses explicitly enabled guarded local TextModelNode registrations or labeled non-packaged test Mock; no safe local route records NOT_CONFIGURED without undoing accepted text. It never falls back to cloud.
- **Entry:** frontend/src/novel/AgentTeamPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx; frontend/src/novel/AgentResultReview.tsx
- **Source:** app/agent_catalog.py; app/services/agent_job_service.py; app/services/agent_context_service.py; app/workflow_api.py; app/model_runtime.py
- **Tests:** tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Specialized automated continuity-to-finding-to-review recipe not complete.

#### H05 · Director Agent

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D04; D13
- **Before:** Adaptation/screenplay services existed.
- **After:** Generic selected-model execution and local shot-proposal review recipe available.
- **Entry:** frontend/src/novel/AgentTeamPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx; frontend/src/novel/AgentResultReview.tsx
- **Source:** app/agent_catalog.py; app/services/agent_job_service.py; app/services/agent_context_service.py; app/workflow_api.py; app/model_runtime.py
- **Tests:** tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Dedicated model-backed director scene/shot contract and apply closure incomplete.

#### H06 · Art Agent

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D04; D13
- **Before:** Generic asset tasks existed; no autonomous art agent.
- **After:** Image review queue and Agent executor exist as distinct controlled paths.
- **Entry:** frontend/src/novel/AgentTeamPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx; frontend/src/novel/AgentResultReview.tsx
- **Source:** app/agent_catalog.py; app/services/agent_job_service.py; app/services/agent_context_service.py; app/workflow_api.py; app/model_runtime.py
- **Tests:** tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No dedicated art-agent executor-to-image review workflow; generic components not full art agent.

#### H07 · Multi-Agent coordination

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible EXPERIMENTAL; P2; packages D04; D13
- **Before:** Generic workflow lacked actual Agent completion gating.
- **After:** Bounded DAG dispatches selected-model Agent jobs, waits for real state and retains approval/failure/cancel.
- **Entry:** frontend/src/novel/AgentTeamPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx; frontend/src/novel/AgentResultReview.tsx
- **Source:** app/agent_catalog.py; app/services/agent_job_service.py; app/services/agent_context_service.py; app/workflow_api.py; app/model_runtime.py
- **Tests:** tests/test_phase6_agent_jobs.py; tests/test_r2_provider_execution.py; tests/test_r2_workflow_execution.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No fully autonomous three-recipe domain closure; cross-process transactional scheduler not claimed.

### I. Screenplay

#### I01 · Novel-to-screenplay conversion

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Screenplay service/create/export existed.
- **After:** Source-traceable branch-safe screenplay and approved revision fork strengthened; current per-edit CAS/history changes require their final test receipt.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Deterministic structural conversion is not model-quality certification.

#### I02 · Industry screenplay formats

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Fountain/Markdown/DOCX exporters existed with semantic Fountain defects.
- **After:** Forced character/action handling, frozen resource packages and font/build improvements added.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Target Final Draft/Word pagination/industry-layout acceptance still NOT_RUN.

#### I03 · Screenplay scenes

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Scene model/update existed.
- **After:** Branch-aware authorization and version-safe approved screenplay fork added.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Full interactive reorder/edit acceptance pending.

#### I04 · Shot records

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Shot model/routes existed.
- **After:** Structured shot data preserved across guarded screenplay revision/export.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Scenario-specific target-desktop source/order acceptance remains NOT_RUN.

#### I05 · Shot numbering

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Deterministic numbering existed.
- **After:** Numbering remains the source for storyboard/export/task provenance.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Complex interactive reorder acceptance pending.

#### I06 · Framing/shot design

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Shot metadata carried framing.
- **After:** Existing editable shot fields retained; manual design flows into assets/export.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No complete model-assisted shot-design engine.

#### I07 · Camera movement

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Camera metadata fields existed.
- **After:** Existing manual motion fields feed prompt/task records.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No camera-planning/physical feasibility engine.

#### I08 · Screenplay dialogue conversion

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Dialogue conversion/export existed.
- **After:** Fountain character and multiline dialogue semantics corrected.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Target screenplay application import still NOT_RUN.

#### I09 · Action descriptions

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D08; D09
- **Before:** Scene/shot/storyboard action text existed.
- **After:** Forced Fountain actions preserve text that resembles syntax/character lines.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_screenplay.py; tests/test_phase8_shots.py; tests/test_screenplay_branch_revision.py; tests/test_industry_export_queue.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Industry rendered layout acceptance remains separate.

### J. Storyboard

#### J01 · Storyboard cards/review

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D08; D10
- **Before:** Create/edit/approve storyboard existed.
- **After:** Branch-safe screenplay revision leaves approved asset references unchanged.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No generated storyboard image implication.

#### J02 · Composition planning

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D08; D10
- **Before:** Composition fields existed.
- **After:** Manual composition records remain connected to storyboard/export.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No automatic composition engine or generated image quality verification.

#### J03 · Visual descriptions

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D08; D10
- **Before:** Descriptions and HTML/storyboard exports existed.
- **After:** Descriptions retained with immutable resource snapshot export path.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Description text is not a rendered/generated visual.

#### J04 · Visual continuity

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1; packages D08; D10
- **Before:** Continuity fields/transition metadata existed.
- **After:** Approved references can be looked up lexically with provenance.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx
- **Source:** app/services/screenplay_service.py; app/industry_export_formats.py
- **Tests:** tests/test_phase8_storyboard.py; tests/test_screenplay_branch_revision.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No trained visual-consistency validator; embedding/semantic inference absent.

### K. Transitions

#### K01 · Transition suggestions

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1/P2; packages D08; D11
- **Before:** Deterministic suggestion/prompt service existed.
- **After:** Existing rule-based suggestion retained with durable screenplay state.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No integrated real-model transition reasoning acceptance.

#### K02 · Scene transitions

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1/P2; packages D08; D11
- **Before:** Scene transition records existed.
- **After:** Existing editable transitions flow into source-linked exports/tasks.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Manual transition records only; no cinematic quality guarantee.

#### K03 · Shot transitions

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1/P2; packages D08; D11
- **Before:** Shot transition records existed.
- **After:** Existing transition/task linkage retained.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Final interactive shot-transition acceptance pending.

#### K04 · Temporal transitions

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1/P2; packages D08; D11
- **Before:** Temporal transition type existed.
- **After:** Current manual temporal type/prompt remains available.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No temporal reasoning engine.

#### K05 · Spatial transitions

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1/P2; packages D08; D11
- **Before:** Spatial transition type existed.
- **After:** Current manual spatial type/prompt remains available.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No spatial planner or geometry-aware validation.

#### K06 · Emotional transitions

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1/P2; packages D08; D11
- **Before:** Emotional type/reason fields existed.
- **After:** Current manual rationale and prompt remain available.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No emotion model or quality-certified cinematic transition engine.

#### K07 · Action match cuts

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1/P2; packages D08; D11
- **Before:** Keyword action matching/suggestion existed.
- **After:** Current deterministic matcher retained.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Model-assisted motion/action alignment unimplemented.

#### K08 · Transition prompt workflow

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1/P2; packages D08; D11
- **Before:** Prompt history/freeze existed.
- **After:** Durable prompts remain linked to scene/shot state and guarded motion submission.
- **Entry:** frontend/src/novel/ScreenplayPanel.tsx; frontend/src/novel/ScreenplayPipelinePanel.tsx
- **Source:** app/services/screenplay_service.py
- **Tests:** tests/test_phase8_transitions.py; tests/test_phase1_video_runtime.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real transition model adapter/quality not verified; template generation is not model execution.

### L. Images and visual memory

#### L01 · Vision adapter

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D10
- **Before:** Compatible Vision adapter existed.
- **After:** Current adapter and analysis entry retained; no real model run.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Authorized configured vision model and output-quality/security acceptance required.

#### L02 · Image understanding

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D10
- **Before:** Image-URL analysis panel existed.
- **After:** Existing actual request path retained; results can inform reviewed references.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real image-understanding quality and supported URL/vendor formats NOT_RUN.

#### L03 · Character visual understanding

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D10
- **Before:** Character-linked analysis/memory existed.
- **After:** Reviewed CHARACTER reference metadata has exact asset provenance and lexical lookup.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No trained identity-consistency/embedding engine; real vision quality NOT_RUN.

#### L04 · Scene visual understanding

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D10
- **Before:** Scene-linked analysis/memory existed.
- **After:** SCENE/LOCATION references can be approved and retrieved lexically.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No scene-semantic similarity or geometry reasoning engine.

#### L05 · Image generation/review

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D10
- **Before:** Direct request/history could lose inline image bytes and status.
- **After:** Persistent image queue, real parameter mapping, decoder validation and explicit accept-to-library remain. Image execution now rechecks the durable attempt, cancellation, ownership and current authorization after provider resolution and before dispatch; late results cannot revive cancelled attempts.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx; frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py; app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Real model execution is NOT_RUN. Discovery route invariants are independently repaired at e38, but supported metadata/adapter contracts do not prove image quality or all model families. Local cancellation cannot recall a request already sent.
- **Subcapability Optional Local AI Discovery registration/route bridge:** implementation_state=PARTIAL; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; verification_scope=See row_evidence_contract.local_ai_scope and LAD runtime-specific evidence.; user_visible_state=EXPERIMENTAL; evidence=docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md

#### L06 · Character image generation

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D10
- **Before:** Generic character-linked generation existed.
- **After:** Generic image queue and reviewed character reference assets available.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Dedicated character templates/consistency control and real-model validation incomplete.

#### L07 · Scene image generation

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D10
- **Before:** Generic scene-linked generation existed.
- **After:** Generic parameterized queue and approved scene references available.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Dedicated scene-generation/continuity workflow incomplete.

#### L08 · Cover creation workflow

- **States:** MISSING / DISCONNECTED / NOT_RUN; user-visible UNAVAILABLE; P2; packages D10
- **Before:** No dedicated cover workflow found.
- **After:** Generic image prompts can request a cover but no dedicated cover product was added.
- **Entry:** No dedicated implemented workflow
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** None
- **Evidence:** docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Need composition/title-safe-area/typography/review/export workflow; generic prompt is not completion.

#### L09 · Storyboard image generation

- **States:** MISSING / DISCONNECTED / NOT_RUN; user-visible UNAVAILABLE; P2; packages D10
- **Before:** Storyboard visual cards lacked image generation.
- **After:** Image queue exists independently; storyboard assets may be manually linked.
- **Entry:** No dedicated implemented workflow
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** None
- **Evidence:** docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Need storyboard-specific image generation and versioned card acceptance/association.

#### L10 · Visual memory retrieval

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P2; packages D10
- **Before:** Visual memory records lacked a real index.
- **After:** Approved version/digest-bound Unicode lexical/metadata index rebuilds safely and returns provenance.
- **Entry:** frontend/src/novel/ImageGenerationPanel.tsx; frontend/src/novel/ImageQueuePanel.tsx; frontend/src/novel/VisionAnalysisPanel.tsx; frontend/src/novel/VisualReferencePanel.tsx
- **Source:** app/asset_providers.py; app/services/image_job_service.py; app/services/visual_memory_index.py; app/asset_lifecycle_api.py
- **Tests:** tests/test_asset_provider_adapter.py; tests/test_r2_media_api.py; tests/test_r2_media_lifecycle.py; tests/test_asset_lifecycle_r2.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No embeddings, visual semantic search or inference; full-scale performance not benchmarked.

### M. Asset library

#### M01 · Asset library

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1/P2; packages D09; D10; D11; D12
- **Before:** Asset service/API/UI existed.
- **After:** Digest/size/id/path checks, atomic publication, restore/recycle bin and permission-aware reads strengthened.
- **Entry:** frontend/src/novel/AssetLibraryPanel.tsx; frontend/src/novel/AssetInspector.tsx
- **Source:** app/services/asset_library_service.py; app/asset_lifecycle_api.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Whole-product reference scanning and archive reimport incomplete.

#### M02 · Image asset storage

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1/P2; packages D09; D10; D11; D12
- **Before:** Generic storage accepted image MIME.
- **After:** Accepted generated images must decode; generic upload preserves opaque-byte contract and honest preview errors.
- **Entry:** frontend/src/novel/AssetLibraryPanel.tsx; frontend/src/novel/AssetInspector.tsx
- **Source:** app/services/asset_library_service.py; app/asset_lifecycle_api.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Declared MIME on generic upload alone does not prove decoding. Existing ImageInfiniteCanvas retains zoom/pan/select/drag/align/group/layer/lock/undo; no raster editing or semantic inference claim.

#### M03 · Audio asset storage

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1/P2; packages D09; D10; D11; D12
- **Before:** Generic audio MIME storage existed.
- **After:** TTS ingress now validates real audio bytes/duration before creating owned asset.
- **Entry:** frontend/src/novel/AssetLibraryPanel.tsx; frontend/src/novel/AssetInspector.tsx
- **Source:** app/services/asset_library_service.py; app/asset_lifecycle_api.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Opaque manual-upload semantics differ; provider playback on target Windows still unrun.

#### M04 · Video asset storage

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1/P2; packages D09; D10; D11; D12
- **Before:** Generic video MIME storage existed.
- **After:** Generated download ingress uses pinned-network policy plus ffprobe/ffmpeg decode.
- **Entry:** frontend/src/novel/AssetLibraryPanel.tsx; frontend/src/novel/AssetInspector.tsx
- **Source:** app/services/asset_library_service.py; app/asset_lifecycle_api.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** ffmpeg licensing/bundling and native playback pending; generic uploads retain opaque contract.

#### M05 · Project ownership

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1/P2; packages D09; D10; D11; D12
- **Before:** Novel ownership existed.
- **After:** Project/branch provenance, ID validation and current membership checks guard new asset paths.
- **Entry:** frontend/src/novel/AssetLibraryPanel.tsx; frontend/src/novel/AssetInspector.tsx
- **Source:** app/services/asset_library_service.py; app/asset_lifecycle_api.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Legacy unbound records are not auto-adopted into a branch; final cross-user UI acceptance pending.

#### M06 · Character associations

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1/P2; packages D09; D10; D11; D12
- **Before:** Association metadata could reference characters.
- **After:** Reviewed CHARACTER references and guarded lineage metadata are persisted and searchable.
- **Entry:** frontend/src/novel/AssetLibraryPanel.tsx; frontend/src/novel/AssetInspector.tsx
- **Source:** app/services/asset_library_service.py; app/asset_lifecycle_api.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Manual entity-ID entry; universal typed foreign keys/bulk relation UI incomplete.

#### M07 · Scene associations

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1/P2; packages D09; D10; D11; D12
- **Before:** Scene/screenplay asset tasks existed.
- **After:** Source tasks, scene/shot references, digest/version lineage and video assembly provenance retained.
- **Entry:** frontend/src/novel/AssetLibraryPanel.tsx; frontend/src/novel/AssetInspector.tsx
- **Source:** app/services/asset_library_service.py; app/asset_lifecycle_api.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_asset_lifecycle_r2.py; tests/test_asset_safety.py; tests/test_export_resource_packages.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/assets-tests.xml; docs/delivery/dot-astra-rc-r2/assets-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Universal scene relation constraints and full dependency/reimport handling incomplete.

### N. Video production

#### N01 · Shot-to-asset task pipeline

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P2; packages D11
- **Before:** Screenplay shot/asset tasks existed.
- **After:** Owned shot/asset tasks retain file validation and result fencing. Legacy asset-task cloud dispatch now fails closed because no complete exact-prompt review exists; individual authorized local dispatch remains supported. Bulk workers require per-task authority callbacks.
- **Entry:** frontend/src/novel/VideoTaskInspector.tsx; frontend/src/novel/MotionPrivacyPanel.tsx; frontend/src/novel/VideoAssemblyPanel.tsx
- **Source:** app/services/screenplay_service.py; app/services/video_assembly_service.py; app/media_files.py; app/media_frames.py; app/video_assembly_api.py
- **Tests:** tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Remote legacy asset execution is UNAVAILABLE pending a proper consent workflow; this safe restriction is not feature completion. Real video generation and multi-host workers remain unverified.

#### N02 · Storyboard-to-video assembly

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P2; packages D11
- **Before:** Storyboard approval could produce tasks but no finished cut.
- **After:** Author orders/trims owned clips; real bounded silent 640x360/24fps MP4 review rendition plus manifest.
- **Entry:** frontend/src/novel/VideoTaskInspector.tsx; frontend/src/novel/MotionPrivacyPanel.tsx; frontend/src/novel/VideoAssemblyPanel.tsx
- **Source:** app/services/screenplay_service.py; app/services/video_assembly_service.py; app/media_files.py; app/media_frames.py; app/video_assembly_api.py
- **Tests:** tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Not final-master production; no soundtrack/compositor/automatic storyboard rendering.

#### N03 · Motion prompt/task handoff

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D11
- **Before:** Motion prompt and task endpoints existed.
- **After:** Motion submit/poll/cancel/retry retains actual file validation. Cloud review now binds complete request_sha256: prompt, both frame references, constraints, provider/model/endpoint and owner scope. Final current authorization/state/attempt/source-policy/frame checks run after preparation; stale prompt-only consent cannot authorize dispatch.
- **Entry:** frontend/src/novel/VideoTaskInspector.tsx; frontend/src/novel/MotionPrivacyPanel.tsx; frontend/src/novel/VideoAssemblyPanel.tsx
- **Source:** app/services/screenplay_service.py; app/services/video_assembly_service.py; app/media_files.py; app/media_frames.py; app/video_assembly_api.py
- **Tests:** tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_legacy_egress_guards.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Remote provider NOT_RUN; review must be repeated for legacy prompt-only approvals. Callback is shared-secret rather than all-vendor asymmetric verification. Windows codec distribution remains pending.

#### N04 · Start-frame handling

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P2; packages D11
- **Before:** Start-frame storage/history existed.
- **After:** Local frame resolves owned current asset/shot/storyboard bytes with image decode and digest/version.
- **Entry:** frontend/src/novel/VideoTaskInspector.tsx; frontend/src/novel/MotionPrivacyPanel.tsx; frontend/src/novel/VideoAssemblyPanel.tsx
- **Source:** app/services/screenplay_service.py; app/services/video_assembly_service.py; app/media_files.py; app/media_frames.py; app/video_assembly_api.py
- **Tests:** tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Opaque external frame URLs have content_verified=false; real provider use NOT_RUN.

#### N05 · End-frame handling

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P2; packages D11
- **Before:** End-frame storage/history existed.
- **After:** Same actual frame validation/privacy and active-task freeze as start frame.
- **Entry:** frontend/src/novel/VideoTaskInspector.tsx; frontend/src/novel/MotionPrivacyPanel.tsx; frontend/src/novel/VideoAssemblyPanel.tsx
- **Source:** app/services/screenplay_service.py; app/services/video_assembly_service.py; app/media_files.py; app/media_frames.py; app/video_assembly_api.py
- **Tests:** tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** External URL/frame interpretation and target model support unverified.

#### N06 · Video provider execution

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D11
- **Before:** HTTP submit/poll/callback path existed.
- **After:** Motion submit/poll/cancel/retry retains actual file validation. Cloud review now binds complete request_sha256: prompt, both frame references, constraints, provider/model/endpoint and owner scope. Final current authorization/state/attempt/source-policy/frame checks run after preparation; stale prompt-only consent cannot authorize dispatch.
- **Entry:** frontend/src/novel/VideoTaskInspector.tsx; frontend/src/novel/MotionPrivacyPanel.tsx; frontend/src/novel/VideoAssemblyPanel.tsx; frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/services/screenplay_service.py; app/services/video_assembly_service.py; app/media_files.py; app/media_frames.py; app/video_assembly_api.py; app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_phase1_video_runtime.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_legacy_egress_guards.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Remote provider NOT_RUN; review must be repeated for legacy prompt-only approvals. Callback is shared-secret rather than all-vendor asymmetric verification. Windows codec distribution remains pending.
- **Subcapability Optional Local AI Discovery registration/route bridge:** implementation_state=PARTIAL; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; verification_scope=See row_evidence_contract.local_ai_scope and LAD runtime-specific evidence.; user_visible_state=EXPERIMENTAL; evidence=docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md

### O. Speech and audiobook

#### O01 · TTS execution

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D12
- **Before:** Compatible speech API existed but success could depend on URL-only response.
- **After:** Real binary/URL audio validation, usage/error/cancel fencing, verified owned audio asset and preview. Current attempt/cancellation/source privacy/project authority are rechecked after provider resolution and immediately before synthesis; original cancellation/revocation recording-provider regressions now pass.
- **Entry:** frontend/src/novel/AudioGenerationPanel.tsx; frontend/src/novel/AudioTaskInspector.tsx; frontend/src/novel/AudiobookManifestPanel.tsx
- **Source:** app/audio_providers.py; app/audio_production_store.py; app/services/audiobook_service.py; app/media_files.py
- **Tests:** tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No real TTS/model quality; async-only providers without poll adapter unavailable.

#### O02 · Character voice profiles

- **States:** IMPLEMENTED / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D12
- **Before:** Voice bindings/history already existed.
- **After:** Durable bindings, pronunciation and authorization notes captured into jobs/manifests.
- **Entry:** frontend/src/novel/AudioGenerationPanel.tsx; frontend/src/novel/AudioTaskInspector.tsx; frontend/src/novel/AudiobookManifestPanel.tsx
- **Source:** app/audio_providers.py; app/audio_production_store.py; app/services/audiobook_service.py; app/media_files.py
- **Tests:** tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No multi-speaker automatic dialogue detection; actual authorized voice verification required.

#### O03 · Audiobook chapters

- **States:** PARTIAL / CONNECTED / MOCK_ONLY; user-visible NOT_CONFIGURED; P2; packages D12
- **Before:** Chapter manifests/queues existed in later baseline, despite historical TODO.
- **After:** Immutable reviewed text, ordered sentence queues, retry/recovery, verified audio and PCM WAV concatenate/export. Current attempt/cancellation/source privacy/project authority are rechecked after provider resolution and immediately before synthesis; original cancellation/revocation recording-provider regressions now pass.
- **Entry:** frontend/src/novel/AudioGenerationPanel.tsx; frontend/src/novel/AudioTaskInspector.tsx; frontend/src/novel/AudiobookManifestPanel.tsx
- **Source:** app/audio_providers.py; app/audio_production_store.py; app/services/audiobook_service.py; app/media_files.py
- **Tests:** tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py; tests/test_r2_outbound_dispatch_authority.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/dispatch-repair.xml; docs/R2_LEGACY_EGRESS_CLOSURE.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Mixed codec/sample-rate mastering, automatic multi-character detection and aligned subtitles incomplete.

#### O04 · Emotion narration

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible UNAVAILABLE; P2; packages D12
- **Before:** No complete emotion narration engine found.
- **After:** Neutral supported contract and explicit rejection of unsupported emotions replace fake spoken emotion tags.
- **Entry:** frontend/src/novel/AudioGenerationPanel.tsx; frontend/src/novel/AudioTaskInspector.tsx; frontend/src/novel/AudiobookManifestPanel.tsx
- **Source:** app/audio_providers.py; app/audio_production_store.py; app/services/audiobook_service.py; app/media_files.py
- **Tests:** tests/test_audio_providers.py; tests/test_r2_media_lifecycle.py; tests/test_r2_media_api.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/media-work.md; docs/delivery/dot-astra-rc-r2/evidence/media-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No supported expressive/emotion provider mapping verified; rejecting unsupported input is not emotion synthesis.

### P. Plugins

#### P01 · Plugin execution/runtime

- **States:** PARTIAL / DISCONNECTED / NOT_RUN; user-visible UNAVAILABLE; P2; packages D15
- **Before:** Manifest surface existed; PR 26 was an unverified sandbox prototype.
- **After:** Declarative packages manageable; executable runtime remains execution_supported=false, DENY_ALL.
- **Entry:** frontend/src/novel/PluginManagerPanel.tsx; frontend/src/novel/PluginInspector.tsx
- **Source:** app/plugin_contracts.py; app/plugin_package_manager.py; app/plugin_management_api.py; app/plugin_runtime_contracts.py
- **Tests:** tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Trusted broker/OS vault mediation/native AppContainer denial and cleanup not implemented/verified as full execution.

#### P02 · Plugin manifest

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P2; packages D15
- **Before:** Manifest validation already existed.
- **After:** Bundle integrity, strict manifest/resource allowlists and size/path/symlink checks added.
- **Entry:** frontend/src/novel/PluginManagerPanel.tsx; frontend/src/novel/PluginInspector.tsx
- **Source:** app/plugin_contracts.py; app/plugin_package_manager.py; app/plugin_management_api.py; app/plugin_runtime_contracts.py
- **Tests:** tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Manifest validity does not authorize code execution or package trust.

#### P03 · Plugin API surface

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P2; packages D15
- **Before:** Catalog/permission endpoints existed.
- **After:** Declarative resource lifecycle is exposed with local authority checks.
- **Entry:** frontend/src/novel/PluginManagerPanel.tsx; frontend/src/novel/PluginInspector.tsx
- **Source:** app/plugin_contracts.py; app/plugin_package_manager.py; app/plugin_management_api.py; app/plugin_runtime_contracts.py
- **Tests:** tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No broad executable extension SDK/broker; packaged/collaboration package writes blocked without Host-admin authority.

#### P04 · Plugin permissions

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P2; packages D15
- **Before:** Permission/authorization service existed.
- **After:** Package changes reset grants; rollback cannot restore implicit trust; current actor checks retained.
- **Entry:** frontend/src/novel/PluginManagerPanel.tsx; frontend/src/novel/PluginInspector.tsx
- **Source:** app/plugin_contracts.py; app/plugin_package_manager.py; app/plugin_management_api.py; app/plugin_runtime_contracts.py
- **Tests:** tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Executable permission enforcement cannot be claimed while runtime disabled.

#### P05 · Plugin lifecycle management

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P2; packages D15
- **Before:** Enable/disable/list existed without full lifecycle UI.
- **After:** Host-local declarative install/update/rollback/recoverable remove with integrity checks and UI.
- **Entry:** frontend/src/novel/PluginManagerPanel.tsx; frontend/src/novel/PluginInspector.tsx
- **Source:** app/plugin_contracts.py; app/plugin_package_manager.py; app/plugin_management_api.py; app/plugin_runtime_contracts.py
- **Tests:** tests/test_r2_plugin_packages.py; tests/test_plugin_contract_v1.py; tests/test_plugin_discovery_security.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No marketplace, signed executable distribution or packaged Host-admin write authority.

### Q. Workflow

#### Q01 · Workflow engine

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P2; packages D13
- **Before:** Workflow/DAG definitions and runs existed.
- **After:** Bounded durable snapshots, cycle rejection, actual Agent completion gating, cancellation/rejection and scope guards. Workflow/queue observers now remount and epoch-fence full actor/session/workspace/project/storyline/branch changes; old-scope callbacks cannot repopulate the next scope.
- **Entry:** frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/WorkflowInspector.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Source:** app/workflow.py; app/workflow_api.py; app/workflow_recipes.py; app/services/v1_capability_service.py; frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Tests:** tests/test_workflow.py; tests/test_r2_workflow_execution.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Single Host process; distributed leases/multi-process transactional scheduling not claimed.

#### Q02 · Novel-to-film recipe

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; P2; packages D13
- **Before:** Release-gate/workflow primitives existed.
- **After:** Three bounded local transformations save reviewed candidates, supplied draft and shot/task proposals.
- **Entry:** frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/WorkflowInspector.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Source:** app/workflow.py; app/workflow_api.py; app/workflow_recipes.py; app/services/v1_capability_service.py
- **Tests:** tests/test_workflow.py; tests/test_r2_workflow_execution.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No end-to-end novel-to-film production/apply pipeline; proposals do not start media generation.

#### Q03 · Custom workflows

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P2; packages D13
- **Before:** Definition/create/run APIs and UI existed.
- **After:** Persisted input/results, human approval/reject, pause/resume/cancel/retry available. Workflow/queue observers now remount and epoch-fence full actor/session/workspace/project/storyline/branch changes; old-scope callbacks cannot repopulate the next scope.
- **Entry:** frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/WorkflowInspector.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Source:** app/workflow.py; app/workflow_api.py; app/workflow_recipes.py; app/services/v1_capability_service.py; frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Tests:** tests/test_workflow.py; tests/test_r2_workflow_execution.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Core local DAG contracts verified; full desktop long-running recovery pending.

#### Q04 · Agent workflow nodes

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible NOT_CONFIGURED; P2; packages D13
- **Before:** Agent nodes could be marked successful before actual work.
- **After:** Selected-model dispatch persists real Agent jobs and synchronizes actual completion with approval. Workflow/queue observers now remount and epoch-fence full actor/session/workspace/project/storyline/branch changes; old-scope callbacks cannot repopulate the next scope. Owned Agent timeout timers are cancelled on completion/cancel; deleted jobs/projects are not recreated by late timers.
- **Entry:** frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/WorkflowInspector.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Source:** app/workflow.py; app/workflow_api.py; app/workflow_recipes.py; app/services/v1_capability_service.py; frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Tests:** tests/test_workflow.py; tests/test_r2_workflow_execution.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/browser-ci-repair.md; docs/delivery/dot-astra-rc-r2/evidence/agent-timer-cleanup.txt; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_INCREMENTAL.md
- **Remaining acceptance:** Model calls MOCK_ONLY; domain-specific multi-agent recipes and atomic crash-gap recovery incomplete.

### R. Credentials and provider selection

#### R01 · Session credentials

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0; packages D04
- **Before:** Trusted sessions/vault already existed.
- **After:** Existing Host boundary retained; no persistent browser secret storage added.
- **Entry:** frontend/src/novel/DeepSeekCredentialControl.tsx; frontend/src/ui/ModelCenter.tsx
- **Source:** app/credential_vault.py; app/trusted_sessions.py; app/providers.py; app/native_text_providers.py
- **Tests:** tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Real Host handoff/native session lifecycle still NOT_RUN.

#### R02 · Persistent provider secrets

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P0; packages D04
- **Before:** Historical audit said TODO, but inspected baseline already has WindowsBackend/keyring persistence.
- **After:** Existing durable OS vault reused; production avoids environment-only configured claims.
- **Entry:** frontend/src/novel/DeepSeekCredentialControl.tsx; frontend/src/ui/ModelCenter.tsx
- **Source:** app/credential_vault.py; app/trusted_sessions.py; app/providers.py; app/native_text_providers.py
- **Tests:** tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No current OS-store integration run; memory test backend is not durable proof.

#### R03 · Windows Credential Manager

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P0; packages D04
- **Before:** Actual CredWriteW/CredReadW/CredDeleteW implementation already present.
- **After:** Reuse actual OS integration instead of replacing with a new secret store.
- **Entry:** frontend/src/novel/DeepSeekCredentialControl.tsx; frontend/src/ui/ModelCenter.tsx
- **Source:** app/credential_vault.py; app/trusted_sessions.py; app/providers.py; app/native_text_providers.py
- **Tests:** tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Native Windows credential persistence/revocation and desktop UI end-to-end NOT_RUN.

#### R04 · Multiple key/profile management

- **States:** MISSING / DISCONNECTED / NOT_RUN; user-visible UNAVAILABLE; P0; packages D04
- **Before:** One vault slot per provider; no multi-profile model found.
- **After:** Still one provider-key identity; no named profile CRUD/selection implemented.
- **Entry:** No dedicated implemented workflow
- **Source:** app/credential_vault.py; app/trusted_sessions.py; app/providers.py; app/native_text_providers.py
- **Tests:** None
- **Evidence:** docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Need bounded profile identity/scope/revocation/masked UI and authoritative runtime selection.

#### R05 · Provider/model switching

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible NOT_CONFIGURED; P0; packages D04
- **Before:** Provider catalog and credential routes existed.
- **After:** Explicit compatible/Claude/Gemini selection feeds current adapters; no guessed model IDs. Discovered local routes require fresh positive locality/capability/identity evidence and explicit Enable; actual author dispatch is tested with buffered output.
- **Entry:** frontend/src/novel/DeepSeekCredentialControl.tsx; frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/credential_vault.py; app/trusted_sessions.py; app/providers.py; app/native_text_providers.py; app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_credential_vault.py; tests/test_credential_provider_lifecycle.py; tests/test_r2_native_text_providers.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/runtime-work.md; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Discovery protocol/authority invariants pass independent e38 review. Actual model switching, multi-key profiles and full v2 execution broker remain unverified/incomplete.
- **Subcapability Optional Local AI Discovery registration/route bridge:** implementation_state=PARTIAL; integration_state=CONNECTED; verification_state=CONTRACT_VERIFIED; verification_scope=See row_evidence_contract.local_ai_scope and LAD runtime-specific evidence.; user_visible_state=EXPERIMENTAL; evidence=docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md

### S. Collaboration and review

#### S01 · Workspaces/storylines/branches

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D03; D14
- **Before:** Collaboration scope already existed.
- **After:** New records/tasks reuse existing identity/scope with reauthorization and remount protection.
- **Entry:** frontend/src/WorkspaceManagement.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/collaboration_api.py; app/services/membership_authorization_service.py; app/creation_workbench_api.py; app/services/creation_workbench_service.py; frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Tests:** tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Different domain-sharing semantics are documented; exhaustive multiuser target-desktop acceptance remains NOT_RUN.

#### S02 · Membership and permissions

- **States:** IMPLEMENTED / CONNECTED / NOT_RUN; user-visible AVAILABLE; P1; packages D03; D14
- **Before:** Server-side identity/membership authorization existed.
- **After:** New workflow, plans, comments, media and export paths use trusted actor/current membership.
- **Entry:** frontend/src/WorkspaceManagement.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/collaboration_api.py; app/services/membership_authorization_service.py; app/creation_workbench_api.py; app/services/creation_workbench_service.py; frontend/src/novel/WorkflowPanel.tsx; frontend/src/novel/AgentQueuePanel.tsx
- **Tests:** tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py; frontend/src/novel/WorkflowScopeGuards.test.tsx; frontend/src/novel/WorkflowPanel.independent-audit.test.tsx
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/acceptance-scope-work.md; docs/delivery/dot-astra-rc-r2/evidence/acceptance-integrity.xml; docs/delivery/dot-astra-rc-r2/evidence/workflow-scope.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Recorded backend/collaboration revocation controls pass in 98b regression. Complete target-Windows multiuser interaction remains NOT_RUN.

#### S03 · Comment/review threads

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P1; packages D03; D14
- **Before:** No comments/review threads found in audit.
- **After:** Persistent chapter-version/quote/hash anchor; trusted actor, reply/resolve/reopen/history and stale-anchor UI.
- **Entry:** frontend/src/WorkspaceManagement.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/collaboration_api.py; app/services/membership_authorization_service.py; app/creation_workbench_api.py; app/services/creation_workbench_service.py
- **Tests:** tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.txt; docs/delivery/dot-astra-rc-r2/creation-work.md; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.xml; docs/delivery/dot-astra-rc-r2/evidence/readiness-planning-focused.txt; docs/delivery/dot-astra-rc-r2/planning-work.md; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual final anchored-comment browser flow passes. Changed/missing source is flagged rather than automatically remapped.

#### S04 · Unified approvals

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; P1; packages D03; D14
- **Before:** Import/Agent/release approvals were separate.
- **After:** Comments/review panel adds durable audit; creation approval and import journals preserve explicit review.
- **Entry:** frontend/src/WorkspaceManagement.tsx; frontend/src/novel/CreationWorkbenchPanel.tsx
- **Source:** app/collaboration_api.py; app/services/membership_authorization_service.py; app/creation_workbench_api.py; app/services/creation_workbench_service.py
- **Tests:** tests/test_r2_creation_workbench.py; tests/test_collaboration_scope.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/readiness-focused.xml; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** No unified inbox aggregating import/Agent/Canon/media approvals; separate domain queues remain.

### T. Exports

#### T01 · TXT export

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D02; D09
- **Before:** TXT exporter/queue existed; history UI could not rediscover jobs.
- **After:** Scope-bound server history/filter/reopen plus immutable snapshot/download/retry.
- **Entry:** frontend/src/novel/ExportPanel.tsx
- **Source:** app/export_formats.py; app/pdf_export.py; app/industry_export_formats.py; app/services/export_job_service.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 98b business/export recovery browser checks pass; interactive target Windows download/user acceptance remains NOT_RUN.

#### T02 · Markdown export

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D02; D09
- **Before:** Markdown exporter existed.
- **After:** Same durable scoped history/snapshot/reauthorization as TXT.
- **Entry:** frontend/src/novel/ExportPanel.tsx
- **Source:** app/export_formats.py; app/pdf_export.py; app/industry_export_formats.py; app/services/export_job_service.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual 98b format and browser regression pass; target desktop/user acceptance remains separate.

#### T03 · DOCX export

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D02; D09
- **Before:** DOCX output and structure tests existed.
- **After:** Retained DOCX and added frozen screenplay-resource packaging.
- **Entry:** frontend/src/novel/ExportPanel.tsx
- **Source:** app/export_formats.py; app/pdf_export.py; app/industry_export_formats.py; app/services/export_job_service.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Word/LibreOffice rendered pagination and target font behavior remain unrun.

#### T04 · PDF export

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D02; D09
- **Before:** PDF export existed; strict CJK embedding gate incomplete.
- **After:** Pinned OFL Noto CJK preparation, licensed manifest and actual embedded PDF validation/render evidence.
- **Entry:** frontend/src/novel/ExportPanel.tsx
- **Source:** app/export_formats.py; app/pdf_export.py; app/industry_export_formats.py; app/services/export_job_service.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Actual pinned-font runtime check passes in lead-local e38 and bbb suites. Final Windows font/runtime, target application typography and broad layout acceptance remain NOT_RUN.

#### T05 · EPUB export

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D02; D09
- **Before:** EPUB exporter existed.
- **After:** Retained immutable export snapshots and discoverable job history.
- **Entry:** frontend/src/novel/ExportPanel.tsx
- **Source:** app/export_formats.py; app/pdf_export.py; app/industry_export_formats.py; app/services/export_job_service.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** External EPUB validator/reader compatibility and accessibility audit not newly claimed.

#### T06 · Screenplay export

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D02; D09
- **Before:** Fountain/Markdown/DOCX existed with mixed-name/action/multiline defects.
- **After:** Structural Fountain fixes; screenplay ZIP with immutable resource bytes enters queue/API/UI.
- **Entry:** frontend/src/novel/ExportPanel.tsx
- **Source:** app/export_formats.py; app/pdf_export.py; app/industry_export_formats.py; app/services/export_job_service.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Complete fountain-js 1.2.4 parser tests passed at the focused checkpoint; target Final Draft/industry layout and final exact-SHA rerun remain separate.

#### T07 · Shot/storyboard exports

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; P0/P1; packages D02; D09
- **Before:** CSV/storyboard/HTML output existed.
- **After:** Shot/storyboard resource ZIPs, source versions, exact byte digests and history/recovery connected.
- **Entry:** frontend/src/novel/ExportPanel.tsx
- **Source:** app/export_formats.py; app/pdf_export.py; app/industry_export_formats.py; app/services/export_job_service.py; app/services/export_resource_snapshot.py
- **Tests:** tests/test_export_jobs.py; tests/test_export_history_recovery.py; tests/test_export_resource_packages.py; tests/test_docx_export.py; tests/test_pdf_export.py; tests/test_r2_pdf_font.py
- **Evidence:** docs/delivery/dot-astra-rc-r2/evidence/pdf-fonts.txt; docs/delivery/dot-astra-rc-r2/evidence/font-manifest.json; docs/delivery/dot-astra-rc-r2/evidence/export-backend.txt; docs/delivery/dot-astra-rc-r2/evidence/export-frontend.txt; docs/delivery/dot-astra-rc-r2/evidence/fountain-after.json; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md
- **Remaining acceptance:** Archive reimport not added; target NLE/industry interoperability NOT_RUN.

## Local AI supplement: LAD-01–LAD-28

Detection/metadata/registration evidence is not actual inference. Every row keeps its distinct implementation, runtime/adapter limits, sources, tests and next acceptance boundary. Full API/storage mappings are retained in JSON.

### LAD-01 · Goal and Model Center integration

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Settings→Model Center→Local AI is a real mounted surface reusing existing registries.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Mounted integration and normalized author contract pass independent review and final hosted checks. Actual model inference and interactive Windows usability remain NOT_RUN.
- **Historical finding IDs:** DISCOVERY-REVIEW-02; independently closed at e38, retained for provenance.

### LAD-02 · Detect→Validate→Register→Enable→Launch

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Distinct backend operations; registration disabled, Enable explicitly confirmed, task-only managed launch.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Digest/control authority findings closed independently at e38. Actual managed process/GPU lifecycle and final candidate hosted gates remain unverified.
- **Historical finding IDs:** DISCOVERY-REVIEW-01; DISCOVERY-REVIEW-03; DISCOVERY-REVIEW-04; independently closed at e38, retained for provenance.

### LAD-03 · Windows hardware inventory

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Host inventory reused for architecture, CPU/RAM and GPU vendor/name/VRAM display; missing facts remain unknown.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py; app/provider_runtime_v2_host_hardware_inventory.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Real Windows hardware collection and matched compatibility NOT_RUN; Linux/mock metadata does not certify hardware.

### LAD-04 · Ollama text discovery

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Existing OllamaProvider.list_models used for tags/details; metadata show/version and explicit completion capability; registry bridge exists.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py; app/providers.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Locality, buffered Writer eligibility, malformed/incomplete-response handling and identity revocation pass independent e38 review. No real Ollama inference or version-wide compatibility certification.
- **Historical finding IDs:** DISCOVERY-REVIEW-01; DISCOVERY-REVIEW-02; DISCOVERY-REVIEW-03; independently closed at e38, retained for provenance.

### LAD-05 · llama.cpp/GGUF

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Configured bounded GGUF roots/header/metadata, executable hints, context/GPU-layer/thread/batch settings, managed task-only lifecycle and external association.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py; app/model_center/runtime_profiles.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Validated external alias and passive validation defects are independently closed. No actual executable/GGUF generation/CUDA validation; passive version data is not runtime execution.
- **Historical finding IDs:** DISCOVERY-REVIEW-03; DISCOVERY-REVIEW-05; independently closed at e38, retained for provenance.

### LAD-06 · Flexible Qwen text families

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Version-flexible family recognition and user-installed Ollama/GGUF identity; fixed old profile is not the only catalog entry.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Names remain declarations only; current locality/alias contracts pass independent e38 review, but real family compatibility and inference are NOT_RUN.
- **Historical finding IDs:** DISCOVERY-REVIEW-01; DISCOVERY-REVIEW-02; DISCOVERY-REVIEW-05; independently closed at e38, retained for provenance.

### LAD-07 · ComfyUI runtime discovery

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; L01; L05; L10; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Default/saved loopback probes read system_stats and object_info, retain partial outcomes and separate runtime/node/model evidence.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Actual ComfyUI node/workflow execution NOT_RUN; metadata alone is not generation proof.

### LAD-08 · ComfyUI model families

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; L01; L05; L10; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** IMAGE Qwen-Image/FLUX/Z-Image, VIDEO H3/Wan/LTX, RESTORATION SeedVR2 and INTERPOLATION RIFE are classified with UNKNOWN fallback.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Family/loader declarations do not supply missing reviewed workflow adapters; arbitrary custom nodes remain unsupported.

### LAD-09 · Qwen-Image

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; L01; L05; L10; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Discovered candidates and disabled registration retain distinct model/file/node/workflow/inference evidence.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** No verified Qwen-Image workflow adapter or real generation; file/loader presence cannot be READY.

### LAD-10 · MiniMax H3 identity correction

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; N06; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** minimax-h3-video is a distinct ComfyUI VIDEO identity; legacy minimax-h3 AUDIO identity remains disabled solely for old history.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Does not validate user's actual model/license/workflow; no UUID/history reinterpretation or executable-video completion.

### LAD-11 · Local video model/adapters

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; N06; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** H3/Wan/LTX family discovery separates runtime identity, model registration and workflow_adapter_id.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** T2V/I2V/start-end/continuation adapters are extension contracts, not implemented runnable workflows for every family.

### LAD-12 · SeedVR2/RIFE utility modalities

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; N06; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** RESTORATION/INTERPOLATION labels stay separate and LOCAL_VIDEO_PIPELINE_V1 architecture is retained.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Actual restoration/interpolation adapters, model output and complete video pipeline NOT_RUN/unavailable where adapter missing.

### LAD-13 · Automatic1111

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; L01; L05; L10; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Default/saved loopback discovery enumerates sd-models; missing service is NOT_FOUND; explicit IMAGE route uses existing adapter without credentials.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Real checkpoint inference not run; existing supported request contract is not universal A1111 version certification.

### LAD-14 · Custom local runtime editor

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Name/type/endpoint/model/modality/health/credential requirement/lifecycle settings persist; loopback-only validation; managed lifecycle limited to llama.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Unknown generic HTTP/OpenAI-compatible models lists do not authorize inference; secure credential binding remains unsupported. External llama alias is fixed, actual runtime acceptance NOT_RUN.
- **Historical finding IDs:** DISCOVERY-REVIEW-05; independently closed at e38, retained for provenance.

### LAD-15 · Declared versus verified capability

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Separate declared_capabilities, metadata/workflow verified_capabilities and actual inference verified=false; standard modalities preserved.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Locality must be positive and current at final dispatch and now passes independent e38 invariants. Metadata/workflow capability is not actual inference verification.
- **Historical finding IDs:** DISCOVERY-REVIEW-01; independently closed at e38, retained for provenance.

### LAD-16 · Hardware compatibility display

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Unknown/possibly compatible/unsupported statuses and offload/context warnings do not delete small-VRAM models.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** No actual matched-GPU benchmark; COMPATIBLE cannot be asserted from filename or static recommendation.

### LAD-17 · Validation states

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** DISCOVERED/NOT_FOUND/NOT_INSTALLED/VALIDATION_REQUIRED/LICENSE_REQUIRED/DISABLED/DEGRADED and conservative compatibility shown.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Identity-change/late-callback findings independently closed and final hosted gates pass. READY and matched-hardware COMPATIBLE still require actual model/hardware evidence.
- **Historical finding IDs:** DISCOVERY-REVIEW-03; DISCOVERY-REVIEW-04; independently closed at e38, retained for provenance.

### LAD-18 · License and usage policy

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** License acknowledgment is separate from validation and explicit Enable; unknown/restricted model use is not assumed commercially permitted.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Application acknowledgment is not a granted license; actual user license and purpose need user review.

### LAD-19 · Model lifecycle

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** No startup inference; managed llama launches only for task and releases afterward; other runtimes remain EXTERNAL_RUNTIME; restart disables registrations.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Disable/rescan/alias/Writer and passive validation invariants are independently closed. Real process/GPU cleanup NOT_RUN; external runtimes stay under user control.
- **Historical finding IDs:** DISCOVERY-REVIEW-02; DISCOVERY-REVIEW-03; DISCOVERY-REVIEW-04; DISCOVERY-REVIEW-05; independently closed at e38, retained for provenance.

### LAD-20 · Functional Local AI UI

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Scan/rescan/cancel, categories/evidence, Validate/Register/Configure/explicit Enable/Disable/Remove-registration are wired to actual API.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_FINAL_INCREMENT.md; docs/delivery/dot-astra-rc-r2/evidence/screenshots/manifest.json; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Final 98b UI 579/111, actual geometry/LocalAI9 and business 2 pass; six final screenshots verified/reviewed. LocalAI browser uses synthetic metadata fixtures; actual Windows hardware/model usability NOT_RUN.
- **Historical finding IDs:** DISCOVERY-REVIEW-02; DISCOVERY-REVIEW-04; independently closed at e38, retained for provenance.

### LAD-21 · Skippable first-use experience

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Panel supports Skip, no scan on startup; explicit Scan and explicit registration/Enable are separate.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Actual first clean Windows install NOT_RUN; no startup scan/launch should be inferred from opening Model Center.

### LAD-22 · Privacy and safety

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Every discovery read/write requires trusted Host session; bounded configured paths, loopback transports, no proxy/redirect/cloud classification or manuscript scan.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Original locality/stale-authority defects are independently closed; positive local model evidence and final-send fences remain mandatory. Synthetic captures do not certify real provider/GPU or native OS isolation.
- **Historical finding IDs:** DISCOVERY-REVIEW-01; DISCOVERY-REVIEW-03; DISCOVERY-REVIEW-04; independently closed at e38, retained for provenance.

### LAD-23 · Performance and partial results

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Background bounded scan, per-probe timeout/size/read budget, partial outcomes and cancellation between probes/directory entries.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Cancellation cannot preempt an in-progress blocking call; real desktop startup/large directory latency not benchmarked. Existing synthetic novel benchmark is not discovery performance.

### LAD-24 · Test requirements

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Original repros and expanded55 invariants are preserved; independent final review and exact 98b File/PG/UI/browser/Host/package/native receipts establish bounded engineering verification.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py; tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts; frontend/tests/visual/local-ai-discovery.spec.ts
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_FINAL_INCREMENT.md; docs/delivery/dot-astra-rc-r2/evidence/screenshots/manifest.json; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Final 98b complete File/PG/UI/browser/Host/package/native gates PASS, with independent 1c19 latest review. Real model/GPU/interactive user acceptance remains NOT_RUN.

### LAD-25 · Documentation and Opus handoff

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Root LOCAL_AI_DISCOVERY.md, LOCAL_AI_WINDOWS_ACCEPTANCE.md and OPUS_UI_HANDOFF.md sections exist; source/status/limits documented.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py; LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; OPUS_UI_HANDOFF.md
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_FINAL_INCREMENT.md; docs/delivery/dot-astra-rc-r2/evidence/screenshots/manifest.json; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** Final engineering source and receipts reconciled. Later docs-only delivery SHA/readback/CI is separately reported by lead; do not confuse it with tested98b source.

### LAD-26 · No fake completion

- **States:** PARTIAL / CONNECTED / CONTRACT_VERIFIED; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Real state machine and runtime probes replace static-only dropdowns; no actual inference verified flag from filename/metadata.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Previously reproduced locality/Writer/revocation and later final-guard defects are independently closed. Unknown/missing model-family adapters and real inference remain honestly PARTIAL/NOT_RUN.
- **Historical finding IDs:** DISCOVERY-REVIEW-01; DISCOVERY-REVIEW-02; DISCOVERY-REVIEW-03; DISCOVERY-REVIEW-04; DISCOVERY-REVIEW-05; independently closed at e38, retained for provenance.

### LAD-27 · Priority within R2

- **States:** IMPLEMENTED / CONNECTED / CONTRACT_VERIFIED; user-visible AVAILABLE; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Original privacy/data/Accept/export/recovery work retained; supplement reuses same project rather than replacing P0 fixes.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md
- **Remaining acceptance:** Do not bypass original final File/PG/browser/Windows gates with supplement counts; later exact-head execution and interactive acceptance remain separate.

### LAD-28 · GitHub direct delivery

- **States:** PARTIAL / CONNECTED / NOT_RUN; user-visible EXPERIMENTAL; original IDs A09; A10; R05; packages D04; D10; D11; D17; D18
- **Before:** Static Model Center/runtime/provider/hardware components existed; discovery state machine was not an integrated product flow.
- **After:** Same working branch and Draft PR retained; local fixed snapshot includes integrated supplement and documentation.
- **Entry:** frontend/src/ui/ModelCenter.tsx; frontend/src/ui/LocalAiDiscovery.tsx; frontend/src/localAiDiscoveryApi.ts
- **Source:** app/model_center/discovery_types.py; app/model_center/discovery_probes.py; app/model_center/discovery.py; app/model_center/discovery_api.py; app/model_center/discovery_bridge.py; app/model_center/domain.py; app/model_center/service.py; app/dependencies.py; app/main.py; .github/workflows/cloud-ci.yml
- **Tests:** tests/test_local_ai_discovery.py; frontend/src/ui/LocalAiDiscovery.test.tsx; frontend/src/localAiDiscoveryApi.test.ts
- **Evidence:** LOCAL_AI_DISCOVERY.md; LOCAL_AI_WINDOWS_ACCEPTANCE.md; docs/delivery/dot-astra-rc-r2/local-ai-work.md; docs/delivery/dot-astra-rc-r2/evidence/local-ai-provider-hardware.xml; docs/delivery/dot-astra-rc-r2/evidence/local-ai-frontend.txt; docs/delivery/dot-astra-rc-r2/TEST_RESULTS.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW.md; docs/delivery/dot-astra-rc-r2/INDEPENDENT_REVIEW_FINAL_INCREMENT.md; docs/delivery/dot-astra-rc-r2/evidence/screenshots/manifest.json; docs/delivery/dot-astra-rc-r2/evidence/ci-98b.json
- **Remaining acceptance:** 98b final engineering branch and all five push/PR lanes verified PASS. Only the subsequent documentation/evidence-only delivery commit SHA/readback/CI remains for lead reporting.

## Concrete remaining product gaps

- **GAP-01 (D04)** One key slot per provider; multiple profile selection/rotation and authoritative v2 execution broker remain absent. Source: app/credential_vault.py CredentialVault/provider key identity. Next: Define profile scope and masked UI/host policy; test revocation and route selection without broadening cloud authority.
- **GAP-02 (D05; D07)** Manual and bounded selected-model proposals are useful; approved STYLE/PLOT feed author generation. Reviewed other kinds still do not become semantic Canon/checker engines. Source: app/services/creation_workbench_service.py WorkbenchRecordIn/generation_inputs. Next: Add narrow reviewed adapters to existing domain registries and structured AI outline acceptance before claiming intelligence.
- **GAP-03 (D06)** Four-group heuristics plus separate explicit-marker rule/plot drafts now exist. No proven natural-language fact extraction/long-book identity resolution; complete six markers are required for local plot extraction. Source: app/knowledge_extraction.py extract_knowledge_candidates. Next: Evaluate bounded model proposals on controlled quality fixtures; decide explicit reviewed adapters to existing world-rule/Canon registries without broadening permissions.
- **GAP-04 (D10)** Lexical metadata index only; dedicated cover/storyboard generation and semantic consistency incomplete. Existing canvas manipulation is retained, not missing. Source: app/services/visual_memory_index.py; app/services/image_job_service.py. Next: Implement per-card/cover source-version review workflows first; add optional embeddings only with a real installed/authorized model.
- **GAP-05 (D10; D09)** References scan is not universal; no archive reimport/full bulk association manager. Source: app/services/asset_library_service.py references; app/services/export_resource_snapshot.py. Next: Define safe reviewed reimport IDs/ownership and extend per-module reference adapters; never silently cascade-delete.
- **GAP-06 (D11; D18)** Output is silent low-resolution review cut; codec binaries/license distribution and final master/audio mixing unavailable. Source: app/services/video_assembly_service.py; scripts/build_windows_application.ps1. Next: Make supported Windows codec installation/package provenance explicit; separately build bounded audio mux/master profiles if authorized scope requires.
- **GAP-07 (D12)** No expressive emotion mapping, automated speaker attribution, cross-codec mix or phoneme-aligned timing. Source: app/services/audiobook_service.py; app/audio_providers.py. Next: Expose each supported provider capability accurately and add actual model/codec fixtures; keep estimated subtitle labels.
- **GAP-08 (D13)** Real Agent dispatch exists, but local recipes stop at reviewed artifacts; no autonomous domain apply or transactional distributed scheduler. Source: app/workflow_recipes.py execute_local_recipe_node; app/workflow_api.py. Next: Connect one bounded reviewed artifact to existing Draft/Canon/media approval APIs with explicit approval and restart-safe idempotency.
- **GAP-09 (D14)** Comments are complete bounded feature; approvals remain split across domains. Source: frontend/src/novel/CreationWorkbenchPanel.tsx; app/creation_workbench_api.py. Next: Add read-only aggregation of existing authorized pending queues before adding cross-domain action controls.
- **GAP-10 (D15)** Executable plugins deliberately unavailable; local declarative lifecycle does not close sandbox/broker/Host-admin authority. Source: app/plugin_runtime_contracts.py; app/plugin_management_api.py. Next: Keep DENY_ALL until real Windows identity, filesystem/network/process denial, cleanup, trust and credential-broker evidence exists.

Resolved GAP-11 and GAP-12 are preserved in JSON with independent repair and final hosted closure evidence. No original feature is removed to improve a completion metric.
