# A05: character event evidence → original author review

Date: 2026-10-16. Base: `ece0ac7c5206904e4ba97aaa73d7e10403a3ac3e`.
Status: bounded frontend workflow IMPLEMENTED; A05 overall PARTIAL.

## Audit and scope

Read repository AGENTS, full supplied frozen 2026-10-16 project requirements, current frozen-capability ledger, DS-v1.0 and the novel reference. Actual owners already implement temporal knowledge events, beliefs/secrets/goals/motives, review/edit/history, scene-aware projection, and local-only character writing context. This slice does not rebuild any of these.

The concrete gap was that projected mind evidence could only jump to a chapter. The author could not reconcile that exact projected event with the current original record and load it into the original editor.

## User flow

1. In the existing StoryGraphPanel, query a character/chapter/optional scene. Only original character graph/context endpoints are called in this mode.
2. Select “退出人物视图并核对原事件”. This explicitly leaves the character-only display and enters the existing author workspace, requiring original author access. No author evidence is read or rendered while staying in character mode.
3. Read the exact original event ID. Check current ID/version, source map with exact versions/digests and no extra or missing entries, character, epistemic category, evidence status, approved/current status and record shape. Compare belief/motive text directly. For facts/secrets, the projection text originates from the relation; this panel does not fetch that relation or claim independently to prove its text.
4. Inspect the original event time/scene/order/state key, evidence classification, source pins and quotes. Copy its approved content into the existing pending-record form. Editing and explicit save use the original POST owner; no automatic review, Canon change, model call, new storage or permission change occurs.
5. Dirty inputs block replacing the editor and leaving it. Refresh rechecks the original event. Identity replacement and returning to character view discard the inspection. Existing save failures preserve the original form draft.

Malformed/missing/denied/stale/wrong-character/wrong-category/source-mismatched events cannot be loaded. The original service remains authoritative. Matching evidence means matching the current returned snapshot, not replaying historical chapter text or recomputing its digest. A later owner change remains subject to the existing save/review validation; this is not a new transaction or restore API.

## Evidence

- Focused mock HTTP/jsdom tests: CharacterMindEvidenceReview, StoryGraphPanel, StoryGraphEvidenceReview, CharacterAuthorPanel. Includes copy/save with no PUT/approve; author-only fetch boundary; stale/denied/missing reads; dirty and consumed actions; owner A→B→A late read suppression; refresh revalidation; Unicode code-point limits.
- Full frontend `tsc --noEmit --pretty false`: exit 0.
- `node scripts/check_ui_design_tokens.mjs`: exit 0, existing 52-file token guard.
- `git diff --check`: exit 0.
- Dependencies reused from the existing installation; no installs. Focused final tests run with cache disabled; build/test outputs kept in this worktree.

## Not claimed

No browser screenshots/visual regression or geometry run, no new File/PG service execution, no GPU/model/literary quality validation, no hosted CI/push. Existing owner backend was inspected, not modified. P0 and publication gates remain unchanged. Full A05 timeline comparison/recovery and real writing quality remain PARTIAL/NOT_RUN; this slice adds exact event inspection and manual candidate editing only.
