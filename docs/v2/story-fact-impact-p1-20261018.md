# P1 Story fact usage and bounded Creative impact

## Status and exact claim

This is an additive implementation of one DIF-01/DIF-02 vertical slice, not full
acceptance of either requirement or of the V2 release. It connects an explicitly
approved World fact relation to an author-confirmed saved Creative storyboard
shot and projects that shot's current, verified original image/video bindings.
It performs no model calls, regeneration, asset approval, automatic rewriting,
new execution, timeline mutation, or preservation decision.

The existing Story Graph, World review, Creative document store, shot history,
Storyboard/Asset production owner, and Host/session/scope invocation remain the
authorities. No canonical fact database, queue, executor, top-level module, or
parallel asset/shot identity was added.

## Interface

All routes are beneath the existing Creative route, available through the
original `/api` and `/api/v1` mounts:

- `GET /novels/{nid}/experimental/creative/story-facts`
- `POST /novels/{nid}/experimental/creative/documents/{rid}/shots/{shot_id}/fact-uses`
- `GET /novels/{nid}/experimental/creative/documents/{rid}/fact-uses`
- `GET /novels/{nid}/experimental/creative/story-facts/{fact_id}/impact`

Catalog items are exact ID/version/digest pins for eligible approved `WORLD_FACT`
relations. Confirmation requires the original document version/digest, original
shot version/digest, exact fact pin, a bounded purpose and rationale, and literal
boolean `confirmed: true`. It checks original `domain.review` plus `domain.write`,
current trusted Host/session, required flags, scope, project incarnation, and
source pins. Identical confirmations by the same actor are idempotent. Only a
bounded pointer record is stored; the document and asset versions/digests remain
unchanged.

Impact returns original confirmed pins, current fact pins, current/stale state,
explicit blockers, a stable fact-to-Creative-shot evidence path, and verified
original shot asset references. A changed/deleted/recreated shot is not silently
rebound to a new asset. Readback is required before UI reports successful saving.

## Ownership and security

- `app/creative/story_fact_bindings.py`: strict pointer contract, bounded original
  owner observations and manual confirmation. Pointer collection
  `creative_story_fact_uses_v1` is registered with the original Creative project
  incarnation view. It is not a fact authority.
- `app/creative/story_fact_api.py`: invokes the original Creative/Storyboard
  trusted Host route; requires Story Graph, change-impact, asset-lineage and
  Creative feature admission. Stored-data validation errors are sanitized.
- `app/experimental/world.py`: default-empty creation transaction provenance hook
  and the shared original freshness-field contract. Unconfigured legacy owner
  record serialization is unchanged.
- `app/experimental/story_graph.py`: server-configured creation-only epoch pin.
  Original raw scope transaction and original project lease are held through
  atomic commit. DTOs cannot supply the epoch. Reads, edits and reviews never
  retroactively bind old records.
- `app/creative/service.py`, `project_store.py`, `api.py` and
  `app/experimental/api.py`: narrow owner construction, incarnation registration
  and router/configuration wiring.
- `frontend/src/storyboard/StoryFactUsagePanel.tsx`, `storyFactClient.ts`,
  `storyFactUsage.css`, and existing `StoryboardWorkspacePanel.tsx`: explicit
  user-triggered inspection and confirmation at the saved-shot entry. Context
  changes invalidate pending responses. Existing shell and UI primitives remain.

Ordinary Creative `get`/`list` freshness behavior is unchanged. The narrow owner
metadata observer can expose an accessible stale derived target's safe pins,
but independently revalidates every ancestor's access before classifying source
drift as stale. Hidden, foreign, missing or archived inaccessible dependencies
withhold the whole usage, including its saved rationale, identities and counts.

Fact observations use one bounded original graph snapshot per pass, shared
ancestor memoization and a total traversal budget, then independently rebuild
at the response boundary. Current World capture/freshness fields come from the
original owner's shared helper. Cycle/depth/capacity failures are explicit
bounded-evidence errors without private IDs or counts.

Asset observations use original `GraphAssetInputs.phase`, retaining the original
scope → Asset → project order. No asset read is opened while holding a separately
acquired Creative project transaction. Without the configured production owner,
asset-backed observations fail closed.

## Legacy and lifecycle compatibility

Existing unbound facts remain readable/reviewable in their original World/Story
Graph UI. They are ineligible for this bridge. An author must create/copy a new
candidate and approve it through the original review flow; no read-side migration
or silent adoption occurs. Semantic fact ancestors must also carry the current
creation epoch. The UI discloses this limitation.

An explicitly authorized original graph creation can initialize the existing
Creative project marker if none exists. Initial invalid DTOs, missing projects
and initial authorization denial do not provision it. A later denial rolls back
all staged fact/index/use writes. The original owner's separately initialized
inert marker can remain after a later failure; no unsafe marker deletion is
attempted and no old fact is rebound to it.

The recreation regression deliberately recreates the same public project ID and
chapter IDs/version/content/order. Original source freshness alone still passes;
the new epoch fence denies the old fact, and a newly created/reviewed fact works.

## Coverage limits and remaining work

The response explicitly says temporal reasoning and transitive Graph, Timeline
and Export impact are `NOT_EVALUATED`; unrecorded/unavailable dependencies are
`UNKNOWN`, and resource cost is `UNKNOWN`. The purpose field records an author's
intended usage, not machine-proven semantic correctness. Neither an empty list
nor an unchanged fingerprint establishes semantic non-impact.

Not implemented in this slice: comprehensive facts across all media, alias and
state conflict workflows, before/after event contradiction reasoning, exact
Comic consumers, transitive graph/timeline/export coverage, selective rebuild
planning/execution, resource estimation, persisted preservation decisions or full
DIF acceptance. Existing Director proposal review and storyboard handoff remain
in place rather than being rebuilt.

## Verification

Focused tests cover manual confirmation/save/reopen, exact original image pins,
unchanged document/asset fingerprints, unchanged sibling shot/bindings after an
original-owner edit, immutable approved fact lifecycle, strict request fields,
source CAS, revocation rollback, stale accessible derived documents, hidden and
foreign entities, archived planning scenes, same-ID project recreation,
legacy-unbound denial, shared DAG/budget behavior, original freshness parity,
late authority/entity changes, private errors, original Host/feature admission,
and review-permission denial.

Final verification:

- File: 99 passed, 99 deselected across the two new suites and original Story
  Graph, Change Impact, mounted Graph and Storyboard suites. Receipt:
  `docs/delivery/v2-development/story-fact-p1-file-final.json`.
- PostgreSQL: changed response-boundary test first passed 1/1, then the same
  six suites passed 99 tests. Receipt:
  `docs/delivery/v2-development/story-fact-p1-postgres-rerun.json`.
  The included Director intent file contributed no PG cases because its current
  lifecycle cases are explicitly File-only; its 19 cases were deselected.
- The one changed File response-boundary test passed again after the PG-specific
  concurrency correction (`story-fact-p1-file-response-final.json`).
- UI: 52 passed (9 fact panel, 24 Storyboard, 19 AppShell); full TypeScript noEmit
  and design-token guard passed. Product sources stayed frozen for these checks.

The first PG run was interrupted (exit 130), not a PASS: its synchronous test
callback attempted a repository write while that very read correctly held the
original project lease. The corrected PG case uses a real concurrent repository
writer, proves it blocks while the read lease is held, then verifies that the
subsequent read suppresses the newly inaccessible relationship. The File case
still verifies reentrant revocation at the final response boundary. No product
change was needed for this test scheduling correction.

The interrupted synthetic fixture was removed by exact scope key and project
ID, guarded by its synthetic fact title, actor and project title. Its exact
identity is recorded in `story-fact-p1-postgres-interruption.json`; a pre-delete
full-body hash was not captured. Rerun cleanup evidence proves exact before/after
scope and project keys match, with zero additions or removals. The original PG
runner reused the existing UTF-8 database OID 16384, without creation or migrations,
stopped cleanly, and independent `pg_ctl status` returned 3 (not running).

These are synthetic authored fixtures and original storage/HTTP integration
tests, not production model, Windows/GPU, visual/browser, or full product
acceptance. No production build, model runtime, install, commit or publishing
was performed by this implementation lane.
