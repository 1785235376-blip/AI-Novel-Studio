# Audience comparison: local chapter-only slice

## Scope and truthfulness

Partial DIF-11 only. Two explicit hypothetical reader profiles are saved with one exact chapter version, full source identity digest, original project incarnation and author-entered observations. Genre experience, target content age group and language habits are parameters, not inferred reader abilities. There are no real-person/minor records, simulated opinions, market data, success predictions or quality scores.

Reading time is exactly non-whitespace Unicode codepoints × 60 / declared codepoints per minute. It is an estimate, not a measured reading test. Observations and agreement/disagreement are labeled AUTHOR_ENTERED. No model, network request, broker reservation, new job/queue or manuscript/Canon mutation is introduced.

## Original authorities

- NarrativeJudgeService narrative_judge_runs receipts, original ExperimentalStore scope transaction.
- CreationWorkbenchService review_threads for findings, human decisions, reasons and history.
- CreativeProjectStore original incarnation/lease, including original PostgreSQL novel UUID.
- Existing narrative review access checks and review endpoint. Additive routes live only beneath the existing narrative-judge router.

GET source never creates a project identity. Explicit POST source/{chapter_id}/prepare may initialize the original project marker. The returned source_digest binds the complete source capture and original incarnation. Comparison creation must present expected_source_digest; same-version unquoted edits, privacy changes and project recreation invalidate it. Dispositions and creation hold the original project lease. Finding identity includes the original incarnation, full source and profile snapshot, preventing cross-reader/version/owner intentional-decision propagation.

Old/stale evidence, profiles, measurements and comments stay redacted; old receipts remain historical and cannot be reviewed. This does not claim full prior-version evidence browsing. Comic/page/shot anchors, real simulated reading and full DIF-11 acceptance remain open.

## UI

Optional expansion within NarrativeJudgePanel; shared design primitives and existing layout only. Expansion retains the child on collapse. Drafts are separated by exact source digest, review reasons by comparison/finding. Source/client changes hide old results and invalidate pending action notices/errors; no automatic retry. Existing regular judge lists and model review inbox exclude audience receipts. Model routes and result publication reject audience receipts.

## Validation

File tests: tests/test_audience_review.py has 30 passing cases at the backend freeze, including exact Unicode anchors, arithmetic, original-owner persistence, retry/CAS, stale/hidden/deleted/private evidence, source preview drift, incarnation replacement, cross-owner propagation, permission gates, model-route denial, history limits, explicit preparation and non-provisioning GET.

Final combined backend regression: 122 passed / 114 deselected across audience, original style/judge, post-interop judge, legacy fence, original model-protocol and mounted tests. Model-protocol tests use synthetic fixtures, not actual model calls. No real model or service was started.

Actual PostgreSQL variants are parametrized and create real original novel owners, then clean up those owners. They were NOT RUN in this task. Use an externally authorized, disposable already-provisioned database with the existing test-isolation workflow and select postgres_backend_only for tests/test_audience_review.py. Do not mistake File results or skips for PostgreSQL acceptance.

Browser visual/geometry screenshots were NOT RUN because starting a Vite/browser service was outside this task's constraints. Final UI validation: 20 AudienceReviewPanel tests plus 17 narrative/UI contract regressions passed (37 total); tsc --noEmit, static token guard and git diff --check passed. Independent read-only review found no remaining blocker within this bounded slice; it did not independently run tests, PostgreSQL or browser verification.

## Additive original-repository integration coverage

`tests/test_audience_review_mounted.py` uses the existing production app composition and actual ChapterService repositories through both `/api` and `/api/v1`. It saves and rereads a chapter through a newly constructed repository bundle; obtains server preview evidence/digest; creates author comparisons; accepts and reopens an original review-thread finding; verifies no chapter mutation; then saves a real changed chapter and verifies stale result redaction and refusal of old evidence. No canonical source digest is mocked.

File run: **2 passed, 2 PostgreSQL variants deselected**. Genuine PostgreSQL variants use the existing mounted fixture's actual novel/chapter repositories, scope persistence and original owner UUID, with bounded fixture cleanup. They remain **NOT RUN** here; the root integration task may run them against its authorized already-provisioned database. The earlier 30-case unit/service suite uses synthetic chapter inputs with real scope/owner storage and must not itself be described as real chapter repository coverage.
