# Narrative continuity review: implicit progress projection

## Finding and scope

The mounted blank-facts path (`App → ContinuityCheckPanel → FindingReviewPanel → findingReviewClient → POST /projects/{id}/narrative/review-checks`) loaded stored expectations and events, but omitted both deadline-rule progress maps. Consequently, genuine reviewed thread advancement at chapter 5 and seed payoff at chapter 4 still produced `THREAD_STALE` and `FORESHADOWING_OVERDUE` while checking chapter 6 against deadline 5.

The failing-before fixture uses the original `NarrativeStateService.record_chapter_narrative_progress` owner and its canonical default-scope adapter, real File persistence, and the mounted production app at both `/api` and `/api/v1`. It preserves one legitimately unpaid seed. The original source incorrectly returned three findings instead of that one.

Red evidence: `narrative-progress-file-red-20261018.json` and `.log` (2 failed, 2 PostgreSQL cases skipped). This receipt is diagnostic rather than a final whole-tree freeze receipt.

## Implementation

- Added the read-only `narrative_progress_projection` helper. It requires the original typed chapter link, matching typed event, entity identity and association, and exact current chapter identity/version. The original chapter owner's number is used, never parsed IDs or display order.
- A thread counts only `PLOT_THREAD:ADVANCED` progress associated with the stored thread. A payoff counts only an original `FORESHADOWING:PAYOFF` link/event associated with a stored `PAYOFF` seed and its `payoff_event_id`.
- Mainline legacy records and the complete canonical default-scope tuple are accepted. Foreign projects, partial/unsupported collaboration scopes, stale/deleted/archived chapter revisions, and future chapters do not satisfy the maps. A late seed payoff remains overdue. Free-form event prose or state transitions without the reviewed chapter link do not supply progress.
- The context digest binds stored links, subject associations, events, and supporting chapter identity/version/number/content/scope snapshots. Changes invalidate prior intentional suppression even if derived chapter numbers remain unchanged.
- Revalidation runs before finding writes, within the existing atomic finding mutation, and before completion, including when evaluation returns no findings.
- Explicit facts retain their own maps and provenance. Collaboration blank facts still fail with `BRANCH_FACTS_REQUIRED`. Existing authorization, human review, CAS, source evidence, and original progress storage remain in place. No migration or rule-threshold changes.

## Limits and review behavior

Absent verified progress is not proof that no progress ever occurred. Stale, archived, deleted, unsupported-scope or mismatched records are intentionally excluded rather than guessed into a satisfied deadline. The resulting findings are advisory and may require source repair or renewed human review. This fixes omission of valid current original-owner progress; it does not claim to eliminate every possible stale-history false positive. Existing findings are not automatically resolved or deleted.

The complete stored event set remains in `context['facts']['narrative_events']`, so event changes are included in freshness checks alongside the returned link, subject and supporting chapter snapshots.

## Verification

Provisional focused File debug: `narrative-progress-file-debug2-20261018.json` and `.log`: 83 passed, 78 backend skips. This includes the new projection regressions plus existing finding-review, narrative progress and detection tests. The first debug receipt is retained; its only failures were a new branch test fixture attempting to move an already-default-scoped project into a different workspace. The fixture now uses the original unscoped local owner before creating its real collaboration scope.

Covered cases include exact mounted blank-facts behavior; real unresolved work; early thread/late seed/future progress; edited, archived and deleted supporting chapters; reorder stability; corrupted event/link/subject associations; cross-project/cross-scope records; arbitrary prose/state transitions; unchanged-map snapshot changes; source changes during both nonempty and empty evaluation; explicit fact precedence; and branch rejection.

Final verification:

- `narrative-progress-file-final-20261018.json`: 83 passed, 78 backend skips; `sources_changed_during_check=false`.
- `narrative-progress-pg-final-20261018.json`: original combined PostgreSQL run retained with 77 passed and one existing fixture collision. The `/api/v1` instance of the stored-expectation test reused global `seed-expectation` after `/api`; the failure occurred when creating the fixture, before invoking review. All 44 new PostgreSQL projection cases passed in that run.
- The parent authorized a test-only repair: prefix both expectation IDs in that existing test with `e.nid`. All assertions and both route prefixes are unchanged. Production source remained frozen.
- `narrative-progress-file-fixture-final-20261018.json`: both affected File cases passed; 2 PostgreSQL cases skipped and 64 unrelated cases deselected; source snapshots unchanged during the run.
- `narrative-progress-pg-fixture-final-20261018.json`: the full intended real PostgreSQL suite passed, 78 passed and 78 non-PostgreSQL cases deselected; source snapshots unchanged during the run.
- The PostgreSQL runtime receipt verifies PostgreSQL 17.11 on `127.0.0.1:55439/v2_recovered_ocr_export_20261018`, reuse mode, no migrations requested, `server_stop=stopped`, and `cleanup_status=completed`.

Earlier File/full-tree receipts precede the narrowly scoped fixture-ID amendment; they are not represented as snapshots of that later test change. The amended affected File cases and complete PostgreSQL suite were rerun. Existing warning output and both earlier failure receipts are retained. No models, paid providers, installations, user Windows access, commits, pushes or migrations were introduced.
