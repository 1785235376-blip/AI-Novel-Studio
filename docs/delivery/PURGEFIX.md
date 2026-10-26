# Purge fix — review note for Vera [HERMIA-FE-20261025 M10-purgefix]
Branch work/hermia-unified-loop-20261025. Fix 35377d47; harness 10f3a1d5; your section 36c18f6b; docs on top.
- UnifiedWorkspacePreview.tsx: realUser = resolveWorkspaceUser(actorId) (new in state/scopeLease.ts: blank/placeholder actor ⇒ null). No projectId involved. Now runs even without a collab scope (purge is per user + project id only).
- Host test src/workspace/state/u1.purge.host.test.tsx (StrictMode, real host, existing bootstrap, stubbed fetch): list [n1,n2] → [n1]; own n2 viewprefs+layout removed; actor-2's n2 keys and own n1 kept. f778eaec: FAIL; now PASS. Mutation realUser→null: FAIL (killed).
- m5 projectGone (real browser, mock backend): seeds own+other real keys, list drops P, in-session refetch (visibilitychange), asserts own 0 / other 2. f778eaec code: FAIL; 10f3a1d5: PASS ×3 viewports.
- Cold-start purge remains the documented gap G-PURGE-1.
Logs: /workspace/hr/m10/logs/purgefix-*.log, m5-repro-purge-before-f778eaec.log, m5-run-10f3a1d5-projectGone.log.
