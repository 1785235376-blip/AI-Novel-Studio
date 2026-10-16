# A02 saved comparison review — 2026-10-16

## Pre-edit source audit
Baseline: `9e52e08fe5e66b0f23fd5159d9c3f4376811f0fb`.
Original owners already implement saved sample ranges/version capture, deterministic metrics, target paragraph measurements, model opinion feedback/history, and versioned STYLE draft/edit/review/preview. Sources: `app/experimental/style_analysis.py`, `style_analysis_model.py`, `frontend/src/experimental/StyleAnalysisPanel.tsx`, `StyleAnalysisModelPanel.tsx`, `styleReviewClient.ts`. No missing model or feedback store is inferred.

Concrete gap: `AnalysisReport` exposes `comparison` only inside raw JSON. The author cannot read target-versus-exemplar measurements and target paragraph evidence in the normal report, or open the exact saved comparison target through existing navigation. Samples already have source navigation and paragraphs. This slice mounts that existing comparison evidence, labels language and short-sample limitations, and retains independent human feedback/profile edit paths. Counts are not normalized drift or literary judgments. No automatic profile change, novel rewrite, new backend/store/provider, authority or lifecycle edit.

## Verification
Pending implementation and scoped checks. Browser/visual/native/HTTP, PG/P0, GPU/provider/Windows/full RC NOT_RUN. No push/CI; cost unknown. P0 BLOCKED, R3-GATE HOLD, Prompt Adoption writes disabled.

## Delivered behavior
- Existing mounted `AnalysisReport` now displays paired exact rational mean-length/dialogue/repetition measurements, preserving original report/profile/language identity. No new threshold, score, semantic classification or provider call.
- Existing target evidence gets Unicode-correct paragraph/range/text review, 20-paragraph pages and original report's 200-paragraph truncation disclosure. Short-sample and unlike-language boundaries are visible. Empty denominator and malformed evidence are explicit, never NaN/Infinity or guessed source navigation.
- Target navigation passes the recorded chapter ID/version into the existing host. This opens the original chapter editor/history context, not a fabricated historical snapshot. Existing host pending-anchor version/dirty logic remains authoritative; no RAW_MARKDOWN offsets are passed as editor-text coordinates.
- Original manual profile editor, version/CAS save, approval, explicit preview/use, and model-opinion feedback/history are reused unchanged. The new review does not create feedback or edit state. Target navigation first requires a distinct leave confirmation disclosing loss of unsaved profile and feedback-reason inputs. Cancel preserves the mounted panel; confirmed leave opens the existing host. Confirmation resets on report identity/version/comparison or unmount. A real App + real Style panel test verifies both draft types survive cancel and only confirmed leave unmounts; no writes or style application occur.
- Files: `StyleComparisonReview.tsx`, pure `styleComparison.ts`, their tests, two-line mount in `StyleAnalysisPanel.tsx`, mounted workflow test, and a nonsecurity original File-owner persistence test. No backend production/API/schema/auth/lifecycle or protected shell/token edit.

## Evidence and limits
Final receipts indexed in adjacent `style-comparison-review-20261016.json`. Selected UI/pure/mock checks: 34 (including one real App host-lifecycle mount with mocked transports/chrome). Original File-owner cases: 3; deterministic language metric case: 1; PUBLIC checks: 30. Forced TypeScript/Vite, discovery, global/scoped tokens, diff check and 487-file PUBLIC source closure are separately recorded. Discovery is not execution of all suites. Existing large-chunk Vite warning is retained; no new runtime packaging claim.

Earlier successful checks are retained; initial build overlapped a strict malformed-response validation refinement and is superseded by unchanged-source final build. The first real App fixture returned an invalid novels object; its failing receipt is retained, and the fixture now supplies the existing novels-list contract. No failure was removed or skipped. Browser/visual/native/HTTP and real quality measurements remain NOT_RUN, consistent with the inherited browser boundary. Canonical NOVEL reference inspected; no screenshot or geometry acceptance claimed. PG/P0/security, GPU/provider/Windows/full RC NOT_RUN. No push/CI.

A02 remains PARTIAL. Calibrated drift, additional-language/real literary quality, historical full-source replay and durable unsaved recovery remain open. Next work requires parent review of this bounded local commit; preserve all prior receipts and restrictions.

Independent review found that a stub-only navigation assertion missed actual host unmount and draft loss. The correction adds explicit cancel/leave acknowledgement and real App mounted lifecycle coverage, without changing the protected host. Chinese repeated-unit labels now explicitly say Han characters, not words. Initial implementation commit: `bae0e34d7956f87116df3873fa7cbf0f581be5a2`; containing follow-up commit identifies reviewed corrections.
