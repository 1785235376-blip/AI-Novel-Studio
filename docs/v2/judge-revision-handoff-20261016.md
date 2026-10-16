# Narrative evidence to original paragraph revision

Baseline: `ef98a47348ae75d7f5f935ac1ac409ed73f680cc`. The containing local commit identifies this delivery. A03/A11 remain PARTIAL. No push or hosted CI was triggered because cost is unknown.

## Audited gap and original owners

`frontend/src/experimental/NarrativeJudgePanel.tsx` already displays exact source quotations, opens source chapters, records author decisions, and creates explicit Writer Room tasks. `NarrativeJudgeRevisionTaskPanel.tsx` and `app/experimental/narrative_judge.py` already own that task association; those services were not duplicated. Before this slice, there was no mounted transfer of the selected finding/evidence into existing original-manuscript revision preparation.

`RevisionIntelligencePanel.tsx`, `revisionIntelligenceClient.ts`, and `app/experimental/revision_intelligence.py` already own selection validation, manually authored candidates, original-segment diffs, partial acceptance/rejection, original chapter CAS/history, and durable ACCEPTING/ACCEPTANCE_UNCERTAIN behavior. `revision_intelligence_api.py` retains all original feature, read/write/review and scope checks. No backend or API change was necessary. Judge model and revision-comparison model coordinators already separate model opinions from manuscript changes and retain explicit dispatch/UNKNOWN boundaries; neither was changed or invoked.

The coordinate mismatch is substantive: Judge evidence indexes raw Markdown by Unicode codepoints and nonempty lines (`style_analysis.py::paragraphs`); A11 indexes the structured original document by ProseMirror UTF-16 node positions (`revision_intelligence.py::text_blocks`). They are not interchangeable. This slice deliberately does not infer a coordinate transform or use a first matching quotation to select a duplicate paragraph.

## Delivered bounded flow

1. In an already enabled Judge panel, open a current finding. Its new evidence-specific action is available only when both existing features are enabled and the current chapter is saved. Only exact current-chapter/version/quote/line evidence can transfer. Other chapters continue to use original chapter navigation first.
2. The original Workbench switches to its existing A11 panel with a session-only, client/chapter/content/feature-bound source intent. The receiving panel rereads the exact run and finding, checks their versions, rejects ambiguous IDs/stale or intentional findings, and validates the selected evidence against the saved chapter without normalization. Raw Markdown and Unicode positions remain explicit. Matching a quotation proves its location, not a semantic or literary diagnosis.
3. The author explicitly selects an original paragraph or editor selection. Duplicate text is not auto-selected. A fresh Judge read must still validate before the existing A11 selection endpoint receives the original catalog/editor positions. The candidate initially contains unchanged original text, not the Judge suggestion.
4. An editable reference to the run/finding/version/evidence/source chapter is placed in the existing candidate goal. This is a human-readable review note, not a new structured lineage authority or proof of applying the suggestion. The author writes a candidate; another Judge reread precedes candidate creation. The existing block diff, accept/reject choices, preview digest, human confirmation, original apply, and original history remain unchanged.
5. Client, chapter, content, saved-state and feature transitions invalidate the session handoff. Monotonic epochs prevent ABA/late completion revival; repeated clicks use existing in-flight suppression. Failed rereads hide old evidence and preserve a typed candidate while blocking further preparation. No automatic retry, model call, finding acceptance, Canon approval, whole-chapter overwrite, or replacement owner was added.

The selected target is the author's explicit choice. This slice does not claim automatic semantic mapping between the evidence and selected text, automatic issue resolution, durable cross-panel draft recovery, or a machine-enforced persistent Judge-to-proposal relationship.

## Verification

Final receipts and source/log hashes: `judge-revision-handoff-20261016.json`.

- 105 mocked UI/pure frontend checks passed across 11 files, including 14 new mounted handoff tests and 20 pure evidence checks. The duplicate-emoji scenario transfers the second quotation but explicitly sends original PM positions 7–11, never raw Markdown positions 5–8, then reaches the original candidate/diff/preview/human-apply callback. Further tests cover entry and later read failures, stale versions, preserved candidates, scope/chapter/dirty/feature ABA, repeat clicks, UNKNOWN records, invalid raw offsets, whitespace and Markdown-versus-rendered text.
- Six original nonsecurity File owner cases passed: partial write with original history/reopen, rejection, duplicate Unicode selection, interrupted acceptance without replay, changed version and changed structured content. Five pure Unicode boundary cases and 30 PUBLIC checks also passed. These are existing owner tests, not newly fabricated persistence.
- Forced TypeScript build, Vite build, discovery, token guard, scoped raw-color check, diff check and 487-file PUBLIC source closure passed. No shared shell/token/schema/authority/lifecycle changes.
- Earlier test-fixture TypeScript typing failure and superseded receipts are retained. An exploratory selection included six optional HTTP-service tests that their existing harness skipped; these are NOT_RUN, not passes. The final mock-only command has no skips. Existing Vite chunk-size and Starlette deprecation warnings remain.

Actual browser/visual/native selection/IME/accessibility/performance, HTTP integration service, PostgreSQL/P0/security lifecycle, Windows/GPU/user machine, paid providers, real model/literary quality, hosted CI and full RC: NOT_RUN. P0 remains BLOCKED; R3-GATE remains HOLD; production Prompt Adoption writes remain disabled. PUBLIC exclusion contracts remain intact.

Independent review identified feature-toggle ABA and later-read failure presentation gaps; both were fixed and tested before final receipts. Parent independent review is required before the next tracked feature slice. Cross-chapter handoff, durable linked review recovery and actual model quality remain open; no automatic migration, source relocation or new approval authority was invented.
