# A02 / A03: bounded style statistics and evidence review

Experimental, default OFF. These packages do not change the frozen PR37/PR38
branches. They call no model or network by default and cannot apply prose/Canon.

## Composition and runtime boundaries

- `StyleAnalysisService(store, novels, chapters, creation)` and
  `create_style_analysis_router(service, authorize, require_flag)`;
  runtime flag `style_dna_v2`. Existing STYLE `creation_records` remain the only
  profile/rule authority. Derived receipts use `style_analyses` in the existing
  ExperimentalStore, with File/PG transaction parity.
- `NarrativeJudgeService(store, novels, chapters, creation, world, planning=None,
  adapters=())` and `create_narrative_judge_router(...)`;
  runtime flag `narrative_quality_judge_v2`, explicit dependencies
  `advanced_planning_v2`, `world_character_engines_v2`, `unified_review_inbox`.
  A04/A05 are not silently enabled or required for these bounded checks.
- STYLE and review threads retain their inherited **durable-sidecar authority in
  both database profiles**. PostgreSQL receipts do not make these legacy records
  native SQL. No new migration or parallel profile/review system is introduced.
- Original comment list/action routes exclude derived Judge threads. Only the
  gated Judge routes expose/mutate them after source checks. Ordinary comments
  keep their existing behavior.
- All novel-level endpoints require current author (`domain.write`) authority;
  review actions additionally require `domain.review`. Actor, branch and flags
  are rechecked before commit/return. Responses use `Cache-Control: no-store`.
- Unified review inbox binding is a read-only projection via
  `ReviewBinding('narrative_judge', authorized_projection,
  feature='narrative_quality_judge_v2')`. Its wrapper rechecks `domain.write`,
  matching actor/scope and the flag both before and after
  `service.list_review_items(ctx.novel_id, ctx.scope)`. The inbox's own
  `domain.read` is insufficient for these author results. Reason-bearing
  decisions use the original Judge route, not a generic approve button.

Frontend composition: `StyleAnalysisPanel` and `NarrativeJudgePanel` take
`client`, optional `chapter`, optional `onNavigate`. Style additionally accepts
`onUseStyle(id)`; it is called only after explicit preview and a second matching
fresh preview. Existing manuscript/context approval remains independent.

## A02 closed loop

1. Select/edit an existing STYLE record, or create one in the same authority.
   Fields include instruction (existing 120-character limit), author rules,
   declared characters and selected sample chapter IDs. Save remains DRAFT;
   approval is explicit.
2. Select version-bound raw Markdown ranges, declared language (`en` or `zh`),
   applicable preview operations and an optional comparison chapter.
3. Run bounded local statistics, inspect raw counts and paragraph locations.
4. Review context preview. Only existing `instructions` enter the established
   generation request; `rules` remain author reference. Declared task operations
   describe the receipt/preview scope, **not a new generation-policy enforcement
   system**. No automatic style activation or manuscript edit occurs.

Method `unicode-style-statistics-v1`: nonempty lines form paragraphs; sentences
split on `. ! ?` for English and `。！？` for Chinese. Length arrays count nonspace
Unicode code points; Latin words and Han characters use separate lexical units.
Paired quote approximations count dialogue; lexical pronoun cues do not infer
narrative perspective. Raw numerators/denominators accompany mean lengths,
dialogue share and repeated-unit share. No probability or match/quality score.
Abbreviations, nested quotes, bilingual text and morphological word equivalence
are not solved by these deterministic rules. Fewer than five sentences is
`SHORT_SAMPLE`, not a calibrated minimum for literary evaluation.

Comparison reports counts and individual paragraph metrics. Different declared
languages yield `LANGUAGE_METHODS_NOT_COMPARABLE`; no shared thresholds are used.
Removing a sample from STYLE, editing/archiving the profile, deleting/archiving
or changing source text/version/branch/privacy invalidates and redacts old
metrics, sample excerpts and comparison material. Reanalysis is explicit.

Limits: 20 sample ranges; no overlapping ranges; 20 unique source chapters;
100,000 source characters per run; 200 stored analysis receipts per scope;
comparison localization at most 200 paragraphs with explicit truncation.

## A03 closed loop

The versioned `narrative-rules-v1` rubric reports exact repeated paragraphs and
existing approved world-record continuity conflicts only when every referenced
record has a valid quoted phrase in selected source chapters. Quotes use raw
Markdown Unicode offsets, paragraph and exact source version. Invalid quotes,
unselected sources and unsupported adapters reject the complete run before
review-thread writes. World conflict quotes locate recorded statements; they do
not prove that an intentional literary choice is an error.

Pacing, dialogue quality, motivation, foreshadowing, scene purpose and subplot
progress abstain without sufficient evidence. Genre/style differences do not
receive a score or mandatory correction. Unknown/unselected semantic records do
not enter public findings, IDs, counts or explanations.

Authors filter findings, inspect evidence, record REVIEWED / IGNORED with reasons,
reopen decisions, and optionally associate a currently saved source revision.
Association records a reference, not evidence that a suggestion was implemented.
Changed source versions invalidate old findings and require a fresh run; this
slice does not attach a newer changed revision to an old invalidated judgment.
No action has an apply/rewrite/Canon path.

Run receipts use stable source/rubric/actor-bound IDs. Retry reuses the same
threads, including after a sidecar write followed by failed receipt commit;
orphan derived threads remain hidden from legacy APIs. Review status/history
lives only in review_threads. Receipt and legacy sidecar are not a distributed
atomic transaction; failures are recovered idempotently, not called atomic.

Limits: 20 selected chapters, 100,000 characters, 40 deterministic findings,
20 optional model opinions, 2,000-character quotes, 5 quotes per model opinion,
200 run receipts. A single explicitly supplied local adapter can return typed
opinions; no adapter is registered by default. Opinions are MODEL_ASSESSMENT,
with exact model identity, UNVERIFIED independence and NOT_VERIFIED quality.
Adapter implementations own bounded runtime/cancellation and must be separately
validated before registration; this slice does not certify a real model.

## Verification and remaining scope

- Backend tests: `tests/test_r4_style_judge.py` and
  `tests/test_r4_judge_legacy_fence.py`, parameterized File / actual PostgreSQL.
  Actual PostgreSQL requires the existing isolated CI endpoint; it is never
  replaced with an in-memory fake or called verified when skipped.
- Frontend: `StyleReviewPanels.test.tsx`, including captured branch/session,
  stale sparse responses, late callbacks, duplicate writes, reason preservation,
  409 recovery and fresh-preview selection.
- Real AI quality, native Windows IME and native browser visual/geometry results
  are separate evidence. Local Chromium could not launch under current sandbox
  socket restrictions; no new screenshot baseline is claimed.
- Literary model evaluation, enforced task-specific style-policy injection and
  cross-version revision-resolution workflows remain PARTIAL / NOT_VERIFIED.
