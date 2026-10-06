# Post-Interop R4/R5 UX continuation

## Wave 0: initial checkpoint, not completion

Actual implementation/analysis model: **gpt-6-astra**.
Repository: `1785235376-blip/AI-Novel-Studio`.
New branch: `work/post-interop-r4-r5-ux-continuation`.
Stacked base: `work/local-interop-desktop-prep` (PR42).
Starting SHA: `e58c72b04182cd374af092314386b90f8250a173`.
Starting tree: `af584605316fded96e36947cf96b15c1efd12c07`.

Live GitHub checks on 2026-10-06 at 15:02 UTC confirm all six historical PRs remain open Drafts, unmerged, with the following heads. All 25 branch tips were inspected; no newer directly related continuation was present.

| PR | Head | Base |
|---|---|---|
| 37 | `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0` | main |
| 38 | `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b` | PR37 branch |
| 39 | `c6f2126115b52e17839d48efea091dc21ec08c61` | PR38 branch |
| 40 | `2c5b4e2f43c50318d9c1eeea487f68c2d66f7b42` | PR39 branch |
| 41 | `bcd60afb96cc69bdfd81db619cb0121d8712f074` | PR40 branch |
| 42 | `e58c72b04182cd374af092314386b90f8250a173` | PR41 branch |

## Existing owners first

The inherited product has real bounded services and UI, not just schemas. This continuation checks and deepens those existing workflows. A separate current matrix preserves the historical F00 INTEGRATED +39 PARTIAL classifications. Final delivery must name actual completed journeys and remaining boundaries rather than relabel every capability DONE.

Wave1 prioritizes durable save/recovery, workspace and review recovery, scoped entity search, authoritative tasks, request context, selection CAS and local diagnostics. Wave2 continues creation intelligence; Wave3 model/research/vector boundaries; Wave4 media production; Wave5 extended creation, version-pinned sharing and declarative workflows. Each integrated wave gets its own commit and push.

## Invariants

- Frozen PR37–42 heads, old acceptance packages and historical matrices are not edited.
- PR40 project authority, SSE revocation and generation terminal/rejection semantics remain.
- PoemSeed Local Interop 1.0 is frozen. Original 37 shared files retain SHA-256 manifest `77c1f82f0aec0ef385d95cacf6fe04530b83fb62d2403bc7341cbe6bf19c858c`.
- Original project/manuscript/model/task/asset/permission owners remain unique.
- Experimental flags default OFF; server V1 acceptance mode forces OFF.
- Only additive schema changes, with migration/upgrade/rollback and File/PostgreSQL parity evidence. No real user data profile is used.
- No paid API, credentials, model/software installation, real manuscript, production service, release, merge or deployment.
- Historical independent follow-up audit remains BLOCKED and is not restarted or replaced.

## Verification at this checkpoint

This commit contains baseline/current-delivery documentation only. No new runtime acceptance is claimed. The inherited PR42 baseline reports 6,799 collected backend cases, File one-process and PostgreSQL two deterministic shards; original assertions, skip provenance, bounded caps, separate TCP gate, Interop, frontend, browser and Windows checks must remain. New tests require an explicit reviewed inventory expansion. All applicable tests will run on the final source. Real local models/GPU/native Windows and third-party target acceptance remain NOT_RUN or LOCAL_REQUIRED.
