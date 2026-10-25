# PURGEGUARD — response to Vera re-review of f6e535a3 [HERMIA-FE-20261025 M10-purgeguard]
Branch work/hermia-unified-loop-20261025. Commits: 1681ea85 (fix+tests), 618476cd (harness), 44eae320 (Vera section verbatim, author Vera), docs commit after.
## Choice
Both options: empty list skipped (no purge, seen kept) AND two consecutive non-empty successful lists required. Safer: a transient empty/partial list can't wipe data; failures carry no information. Trade-off: purge one refetch later.
## Tests (targeted)
- u1.purge.guard.host.test.tsx (StrictMode host, stubbed fetch): Vera repro [n1,n2]→[n1]→[] keeps keys (failed before fix); [n1]→500→[n1] purges own n2 only (kills P4); empty list breaks streak; project switch is not an observation (kills G4).
- u1.purge.user.test.ts: blank/absent/placeholder actors → null (kills P6/P7).
- src/workspace vitest 44 files, 366/366; tsc -b exit 0.
- Browser (mock backend, no model calls): projectGone (pending after 1st, purged after 2nd, other user 2/2 kept) and emptyList (4/4 kept) PASS ×3 viewports; both FAIL on f6e535a3 code.
## Mutations (src/workspace vitest, script /workspace/hr/m10/purgeguard-mut.py, files restored after each)
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

P4 mutant: on load error, feed `[]` to ProjectPresence (failure treated as empty list). Earlier P4 attempt (pending-only gate) was masked by the dataUpdatedAt guard and survived; replaced with this faithful variant, now KILLED. First run also mis-classified G3 (output truncation); rerun with fixed classifier.
## Evidence
evidence/purgeguard-*.log/json. Vera: /workspace/hr/vera-compare/purgefix-f6e535a3/.
## Status
Row 14 remains 待 Vera 复核.
