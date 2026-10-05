# Revision-history refresh and restore isolation

Date: 2026-10-05 UTC. Synthetic local test data only. No publication, real provider call, user manuscript or credential was used.

## Hosted finding

The real File/browser flow accepted an AI draft and advanced the chapter from v2 to v3, but the still-mounted revision observer reused a cache key without the current chapter version. Its timeline stayed at historical v1, so the expected pre-AI v2 could not be selected. The hosted timeout occurred before revision restore.

## Repair

- The live `RevisionHistory` list key includes the current server chapter version, so AI Accept/manual save/restoration chapter-cache updates obtain the new history.
- An opaque random per-observer ID separates actor, session, novel, chapter, workspace, project, storyline and branch identities. Raw session tokens are used only in captured in-memory request context/identity comparisons; they never enter revision query keys or dehydrated caches.
- The observer remounts on identity changes, with epoch checks for list/detail successes, failures and restore completion. Direct store subscriptions also fence an A→B→A navigation batched into one React render. Inactive revision queries have zero cache retention.
- The live restore handler captures API context and both revision versions, validates the returned chapter identity, and never reloads the page. After a same-context check, the root callback puts the returned chapter into the existing chapter query without regressing a newer cached version.
- Existing App hydration remains authoritative. It preserves a newer local dirty draft and opens the persistent version-conflict dialog with both local and restored server content. The repair does not directly call `setText` or clear draft/conflict persistence.
- The old unused `History` function below the live component remains outside this edit's ownership. `Panel` routes exclusively to the repaired `RevisionHistory`.

The integration lead added captured-context parameters to the four revision API helpers. This worker changed only the App imports, RevisionHistory block and minimal Panel/main callback plumbing, plus a dedicated test file.

## Verification

**49 tests passed in 6 files**, including **19 new real-QueryClient RTL tests**:

- Mounted server-version change v2→v3 exposes historical v2, both directly and through the actual App chapter cache
- Late history responses across actor/session/project/workspace/storyline/branch changes
- Late historical detail from project A cannot appear in project B
- Late restores across project/branch/session/actor changes and batched A→B→A do not apply or reload
- Actual App hydration updates a clean buffer from the returned chapter
- Actual App hydration preserves a newer dirty buffer and persists the version conflict
- Actual App preserves a new project's/branch's/session's dirty buffer when an old restore completes
- Query keys and dehydrated revision cache do not contain the synthetic session token

Additional passing files cover the existing App, RevisionPanel, collaboration guards, generation recovery and design-system contracts. TypeScript, design-token lint and scoped diff checks pass.

Evidence:
- `evidence/revision-history.txt`
- `evidence/revision-history.xml`
- `evidence/revision-history-typecheck.txt`
- `evidence/revision-history-token-lint.txt`

Actual browser retest remains **NOT_RUN locally** because the executor's established Chromium Unix-socket restriction is unchanged. No screenshot baseline or global UI styling was modified. The integration lead must rerun the hosted real File/browser scenario against the published candidate before claiming the original business flow passes.

## Files

- `frontend/src/App.tsx`
- `frontend/src/AppRevisionHistory.test.tsx`
- This report and its four evidence files
