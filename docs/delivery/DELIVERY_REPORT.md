# Delivery report — t150u PoemSeed Studio V2 unified loop [HERMIA-FE-20261025 M10]
Branch work/hermia-unified-loop-20261025, code HEAD f178ff84. Node 22.14.0. Times Asia/Shanghai, 2026-10-25.
See ACCEPTANCE_MATRIX.md (34 rows: 已验证 21 · 已实现 1 · 部分实现 5 · 受阻 3 · 未运行 4), INTERFACE_COVERAGE.md (gaps), INTEGRATION_NOTES.md, GATE_INT.md, evidence/.

## Per stage
| Stage | Commit(s) | Result | Evidence |
|---|---|---|---|
| M0 ledger | a167022b | 294 failing names recorded | /workspace/hr/m10/M0_FAILURE_LEDGER.md (mock) |
| U2/U3/U4 + integration | c50a8d94, 437f7da6, 1f6ab40e, b5241905, 575501b9 | 集成代码 PASS，U1 三项 MUST-FIX，已由 u1fix **d9479872** 修复（93a1e351 是 Vera 的复核段，非修复提交；[HERMIA-FE-20261025 M10-purgeguard] 更正） (full ×3: 292/293/293) | review/INTEGRATION.md, INDEPENDENT_REVIEW.md |
| M5 real browser + stale-label fix | 581c8463 | 30/30 pre-merge | evidence/m5-repro-storagelabel-*, m5-run-premerge |
| Audio merge + wiring | f6e60160, 841effd0 | workspace vitest 357/357 | review/AUDIO.md (mock) |
| U1fix merge | 002ef7fb | no conflicts | review/U1fix.md |
| Duplicate bootstrap removed + scenarios | 69d68a1c | 45/45 browser | evidence/m5-run-69d68a1c.log, m5-repro-bootstrap-* |
| Vera review section (verbatim, author Vera) | 4d0aa402 | cmp identical | INDEPENDENT_REVIEW.md |
| Vera P2 (identity string, landmark-unique, purge doc) + axe scenario | f178ff84 | 48/48 browser; full suite NEW 0 | evidence/m5-run-f178ff84.log, m5-repro-axe-* |

## Browser run (real browser, mock backend) at f178ff84 — 16 scenarios × 3 viewports = 48/48 PASS
loop, param, adopt, restore, coldReopen, audioFilter, audioPreview, identity, worksetPan, sessionSave, axe, aba, corruption, revoked, unknown, projectGone. blocked=[] and pageerrors=0 in all.
Shots: /workspace/hr/m10/shots/<vp>-<scenario>-*.png (files named *-FAIL.png are from earlier script iterations before the fixes listed below; not from the final run). Request logs: /workspace/hr/m10/logs/m5-req-<vp>-<scenario>.log.

## Full suite at f178ff84 (mock) — single final run
tsc -b 0 · vite build 0 · vitest 11593 tests: 11294 passed, 293 failed + 1 failed suite, 6 skipped (exit 1, as at M0).
By name vs M0 (294): persistent 294, NEW 0, gone 1 (`TaskCenter.additive › shows receipt evidence and preserves task info on a later failed read`, fixed by U3).
Note: `src/ui/LocalAiBrowserJourneyContracts.test.tsx` fails at suite level (reads untracked tests/e2e/v2-local-ai-files-live.spec.ts, ENOENT) — also failed at M0 (m0-full.json, 0 assertions); the M0 names file omitted suite-level failures, so it is persistent, not new.

## Passed
Rows 1–13, 16, 17, 23–27 of the matrix (20 已验证). Row 14 fixed after Vera final review, pending her re-check.
## Blocked / not done
受阻: audio history (G-AUD-5), task paging/owner filter (G-AUD-1/G-TC-1), same-id recreation (G-ID-1).
部分实现: cold-start purge (G-PURGE-1), audio adopt beyond trim (G-AUD-4), cost 未知 (G-AUD-7), compare not split, resetAll not in UI.
未运行: real backend API, real provider, PostgreSQL, Windows.

## Real bugs fixed (repro first)
1. Stale "布局仅在本次会话有效（无本地存储）" after late storage — m5storageLabel.test before 2 FAIL → after pass; browser coldReopen label count 0.
2. Duplicate bootstrap after U1fix merge (3 GETs) — m5-repro-bootstrap-before/after; int.bootstrap.test 3/3.
3. axe landmark-unique #uw-panel-tasks — m5-repro-axe-before FAIL → after PASS (real browser, local axe-core copy).
4. Legacy TasksPanel fabricated `uw-preview:<id>` identity + empty-token read — u3.repro it.fails → it (same assertions).

## Repro steps
```
export PATH=/tmp/node-v22.14.0-linux-x64/bin:$PATH; cd frontend
V061_API_URL=http://127.0.0.1:5392 npx vite --port 5391 --strictPort --host 127.0.0.1 &
M5_VP=1366x768 [M5_ONLY=axe] M5_HEAD=$(git rev-parse --short HEAD) node tests/m5/run.mjs   # starts mock backend :5392
npx tsc -b && npx vite build && npx vitest run --reporter=json --outputFile=full.json
```
axe scenario needs axe-core at $M5_AXE (default /tmp/vera-vw-axe/node_modules/axe-core/axe.min.js; no network fetch).

## Vera final review of f778eaec — MUST-FIX 1 (fixed at 35377d47, pending Vera re-check)
Bug: UnifiedWorkspacePreview derived `realUser` via resolveWorkspaceIdentity with sentinel projectId '\u0001'; U1fix's scope-mismatch check made it session ⇒ null ⇒ purge never ran (regression vs 575501b9).
Fix: `resolveWorkspaceUser(actorId)` (scopeLease.ts, same actor rules, no project). Repro-first: u1.purge.host.test.tsx FAIL on f778eaec (evidence/purgefix-repro-before.log) → PASS; mutation realUser→null ⇒ test FAILS (killed, purgefix-mutation-realUser-null.log). Browser projectGone was vacuous (filtered '::project::', after a reload = cold start); now seeds real own/other keys, refetches the list in-session and asserts: FAIL on f778eaec code, PASS ×3 at 10f3a1d5. Targeted: src/workspace vitest 42 files 358/358; tsc -b 0. No full suite rerun (per instruction).

## M10-purgeguard (Vera re-review of f6e535a3, MUST-FIX 1) [HERMIA-FE-20261025 M10-purgeguard]
- Bug (Vera): one successful `200 []` project list purged own viewprefs/layout/worksets for every seen project.
- Fix 1681ea85: empty successful list is never evidence (no purge, `seen` kept, pending reset); purge requires **two consecutive non-empty successful lists** missing a project; load failures are never fed in (neither confirm nor reset); one observation per fetch (`dataUpdatedAt` guard). Both of Vera's options applied — the stricter combination.
- Repro-first: u1.purge.guard.host.test.tsx failed 3/3 before the fix (evidence/purgeguard-repro-before.log); browser emptyList FAIL 0/4 kept and projectGone FAIL on f6e535a3 code (evidence/purgeguard-browser-before.json).
- After: src/workspace vitest 44 files 366/366; tsc -b 0; browser projectGone + emptyList PASS at 1366x768/1440x900/1920x1080 (harness 618476cd, evidence/purgeguard-browser-after.json). Targeted only; full suite not rerun.
- Vera section committed verbatim 44eae320.

| # | Mutation | Result | Note |
|---|---|---|---|
| P1 | realUser->null | KILLED | Vera P1 |
| P2 | purge other users | KILLED | Vera P2 |
| P3 | purge canvas drafts | KILLED | Vera P3 |
| P4 | load-failure treated as empty list | KILLED | Vera P4 (was SURVIVED) |
| P5 | first list purges | KILLED | Vera P5 |
| P6 | no identity purges (anon) | KILLED | Vera P6 (was SURVIVED) |
| P7 | placeholder actor accepted | KILLED | Vera P7 (was SURVIVED) |
| G1 | empty list not guarded | KILLED | new guard mutant |
| G2 | empty list does not reset pending | KILLED | new guard mutant |
| G3 | single confirmation | KILLED | new guard mutant |
| G4 | no per-fetch observation guard | KILLED | new guard mutant |
| G5 | dataUpdatedAt dep removed | KILLED | new guard mutant |

Review note: docs/delivery/PURGEGUARD.md
