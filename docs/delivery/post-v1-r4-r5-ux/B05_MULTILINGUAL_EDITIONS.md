# B05 · Reviewed multilingual editions

## Scope and reuse

**Classification:** NEW independent language-edition records; EXTEND original chapter/paragraph authorities and the existing ExperimentalStore, author authorization, exact Unicode/ProseMirror helpers, React workbench and design tokens. This is the deterministic manual-authoring slice of B05. Automatic model translation is **BLOCKED / unavailable**, not mocked success.

The user can select up to 20 saved chapters, create a separate language edition, edit aligned source/target paragraphs, configure and approve terminology, submit/preview/accept or reject each segment, recover after source changes, and explicitly download a reviewed UTF-8 edition. These records are not aliases for shared manuscript branches. No operation writes the original manuscript, Canon, chapter history, job store, asset store or legacy export service.

## Entry points and integration

- Backend: `app/experimental/multilingual_editions.py` and `_api.py`
- Frontend: `MultilingualEditionsPanel`, `multilingualEditionsClient`, token-only `multilingualEditions.css`
- Workbench tab: **多语言版本与术语**
- Exact server flag: `multilingual_editions_v2`; no runtime flag dependencies for manual use
- Shared API/flags/capability/navigation/mounted fixture/hosted browser registration are integrated by the lead, not duplicated here
- Routes under `/novels/{nid}/experimental/language-editions`, mounted through the existing `/api` and `/api/v1` composition

Supported actions: GET catalog/list/detail; POST create; PUT segment draft; POST segment preview/review; POST rule draft/review; POST source refresh-preview/refresh; POST export-preview/export. All writes carry edition CAS versions. Review/export actions require current `domain.review`; author-private reads/editing require `domain.write`. Every record additionally belongs to its creating actor. All responses use `Cache-Control: no-store`.

## Data and source boundaries

- Existing scope-atomic `ExperimentalStore`, schema 1, collection `language_editions`; no new database, executor, migration or startup conversion
- Full project/workspace/storyline/branch scope is inherited from the original authorization resolver
- Source chapter version, rich-document digest, source-privacy receipt, exact node path/digest and UTF-16 paragraph positions are bound to each edition
- Source prose is read from the current source authority and not copied into edition storage; target drafts, approved terminology, author notes and revision history remain `LOCAL_ONLY`
- Legacy source branches do not provide independent chapter authority. A collaboration branch without genuinely matching chapter storage gets an empty/unavailable catalog and cannot borrow original manuscript content
- A source version, formatting, privacy or availability change marks the edition stale, withholding target text, source text, title, style, rules, archived candidates and history from ordinary reads. Old source acceptance/export is blocked; no translation or automatic realignment is triggered
- Version-conflict errors contain only safe identity/version/status metadata, never current target prose or history
- Failed final feature/V1/authority/source checks roll back the scope transaction

Source refresh is a separate, preview-bound author action. Only paragraphs at the identical path with the identical node digest retain their target text. Changed/new paragraphs start empty; moved paragraphs are not guessed. All retained translations return to DRAFT. Changed nonempty translations become read-only archived manual candidates after the author explicitly binds the edition to the currently authorized sources. They cannot be accepted or exported directly: the author copies a chosen candidate into a current paragraph and repeats save/check/review. The original complete snapshots remain in protected history. A missing or hidden source must be recovered through its original authority before this refresh can proceed.

## Deterministic terminology and review

Rules have draft/approved/revoked states, rule ID/version, reviewer/time, source aliases, approved target aliases, forbidden translations, term/character/title category, literal substring or Unicode word-boundary matching, and meaning/transliteration/preserve strategies. Matching is literal, case-sensitive and does not normalize saved characters. Preserve rules require the exact source term without alternate spellings. Transliteration rules verify the author's specified spelling; they do not evaluate pronunciation.

Only approved rules are checked. Missing required forms, forbidden forms and incompatible approved rules are real deterministic findings. Empty targets and terminology conflicts block acceptance/export. Rule approval or revocation invalidates prior segment approvals and requires review again. Each segment uses DRAFT → REVIEW → preview digest → explicit ACCEPTED, with reject/reopen paths. Editing an accepted target returns it to DRAFT. Acceptance never overwrites source text.

Bounds: 20 chapters, 500 nonempty source paragraphs, 100 rules, 20 variants per rule list, 20,000 target characters per segment, 250,000 target characters per edition, and 2,000 archived changed-paragraph candidates. Excess is rejected; no silent truncation of prose. The chapter helper's existing 100,000-character bound remains. Lists expose the most recent 50 editions and state truncation.

## Language, export and UI

Language codes use a bounded BCP-47-shaped syntax, not a claim that every language or registry tag is supported. Direction can be selected explicitly or inferred for common RTL languages/scripts. Source and target panes use language/direction attributes; saved target characters, emoji and combining marks are preserved exactly. Font choice uses system generic/token families; glyph availability is not guaranteed.

Reviewed export requires a fresh version-bound preview and a separate confirmation. TXT is UTF-8 target text; HTML escapes all author text, carries `lang`, `dir` and UTF-8 metadata, and uses fixed generic font CSS; JSON carries language and source-version/path alignment. SHA-256 is returned for the exact UTF-8 bytes. Downloads use local Blob URLs with revocation on changes/unmount. Export never publishes or uploads. Archived/unapproved/missing targets are excluded by blocking whole-edition export until the current segments pass all checks.

UI states include empty, loading, permission/error, missing translator adapter, review, acceptance, source-stale recovery, unsaved input and export preflight. Unsaved segment input is retained on server failure; segment/version navigation is disabled until save or explicit reset, and browser unload warns while dirty. Scope changes discard private screen state and suppress old asynchronous completions. Unsaved inputs are not an additional durable browser store; save before switching the overall workspace or closing the task.

## Model boundary

No translation model, external endpoint, paid call, credential, model download or synthetic translator is invoked. The capability response explicitly returns `AUTHORIZED_TRANSLATION_ADAPTER_UNAVAILABLE` and `model_called: false`. A future translator must be wired through the existing registered authorization, exact-source preview, privacy, budget and original job service; this slice does not create an alternative execution path. Target-language fluency, style quality and actual font rendering remain separate acceptance work.

## Verification receipt

Source checkpoint: `29cf0203f7afffdf9a010c50cd20a847d243690e` (B05-owned paths only). Shared integration belongs to the lead checkpoint. Publication/hosted results are not implied by this local commit.

Executed in the existing isolated no-cloud harness on the owned engineering tree:

- `pytest tests/test_r5_multilingual_editions.py tests/test_r5_multilingual_editions_mounted.py -m 'not postgres_backend_only'`: **37 passed**, **30 PostgreSQL parameter cases deselected**, not counted as passes
- Final combined B05 + original revision regression: **68 passed**, **56 PostgreSQL parameter cases deselected** on the final owned engineering tree before source commit
- React B05 suite: **10 passed**; shared UI contracts: **5 passed**
- `tsc --noEmit`: passed after correcting the typed Blob mock; the final cross-tree retry later reported an unrelated `DeclarativeTemplatePanels.test.tsx:67` unsupported Testing Library `exact` option. No B05 TypeScript errors were reported in that retry. Aggregate build must be rerun after the owning lane fixes it.
- UI token guard, direct owned-CSS color/spacing scan and `git diff --check`: passed
- Browser spec collection: `r4-multilingual-editions.spec.ts`, **1 test discovered**

Tests cover real File storage, restart, two actual mounted prefixes, original manuscript/history nonmutation, private actor/branch/role/session boundaries, OFF/wildcard/V1 denial, last-moment authority rollback, source version/format/privacy/deletion drift, exact duplicate/Unicode anchors, CAS and preview staleness, terminology conflicts/aliases/forbidden forms, read-only archived recovery, RTL/UTF-8 serialization and escaped HTML, React late callbacks/StrictMode/input recovery, and download cleanup. React network responses are mocked contract tests; File and mounted backend tests use real repositories.

**Real PostgreSQL:** same parameterized cases are marked `postgres_backend_only` and use only `TEST_POSTGRES_DATABASE_URL` in the existing hosted `postgres_gate`. No local endpoint exists; execution remains NOT_RUN locally until the lead observes hosted results. No DSN is invented or committed.

**Real browser:** the authored journey uses the actual File backend and mounted React UI without response mocks; it checks manual Arabic authoring, glossary approval, per-segment acceptance, Blob HTML parsing, unchanged original text, source-drift recovery, and screenshots at 1366×768 / 1440×900 / 1920×1080. Local Chromium launch EPERM is established and was not retried. No local screenshots or browser PASS are claimed. Hosted execution must be reported separately.

**Not established:** real translation/model quality, real Windows IME, screen-reader acceptance, exhaustive script/font coverage, zoom acceptance or user aesthetic approval. No frozen PR37/PR38 files, environment, merge or release are changed by this package.

## Opus handoff / remaining work

The panel consumes existing Panel/Button/Badge/StatusMessage/Field primitives, `experimental-grid`, and existing tokens, without changing AppShell or protected dimensions. Preserve explicit source/target distinction, language/direction, dirty-input protection, unavailable-model explanation, preview-bound approval, stale withholding, archived-candidate warning, and export confirmation. Visual polish may not hide these states.

Next evidence steps: hosted real-PG and authored browser execution on the published SHA; then explicit human language/font/IME review. Automatic translation remains unavailable until a real authorized adapter is integrated and separately verified. The lead owns commit/PR receipts and aggregate feature-matrix/Opus updates.
