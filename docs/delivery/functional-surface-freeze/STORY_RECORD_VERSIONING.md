# Original Timeline and Foreshadowing version surfaces

Status: **PARTIAL**. Original-owner File/service/mounted-API behavior and frontend unit contracts are exercised locally. Real PostgreSQL execution and real-browser screenshots/geometry remain **NOT_RUN** here; their opt-in tests are committed for the hosted gates. This document is not a freeze or release approval.

## Authority and storage

These are the existing Story → 时间线 / 伏笔 editors. No new top-level workspace, editable shadow record store, database migration or provider runtime was introduced.

- File: existing `timeline/events.json` and `foreshadowing.json`; project mutation guard and atomic file replacement remain authoritative.
- PostgreSQL: existing `TimelineModel` / `ForeshadowingModel`; metadata stays inside existing JSONB details. The project row is locked for create/update CAS, and captured chapter sources are locked and rechecked in the transaction.
- `_story_record` is private metadata on the original row, containing monotonic version, source versions, provenance, bounded history and feedback. It is omitted from legacy public rows and generation context. CAS hashes the exact public serialization, including privacy normalization.
- Historical rows start at version 0. A versioned mutation appends the prior public row and metadata to a bounded 20-entry history. Old clients remain valid, and legacy saves after opt-in advance version/history so a stale versioned writer cannot overwrite them.
- Existing opaque import extensions survive. Client-supplied unknown fields or private version metadata are rejected. Restore copies only a previously persisted snapshot; it does not accept replacement history from a client.
- Timeline location slugs, status, non-ASCII external identity and pre-existing PostgreSQL UUID identities retain their original public contract. Legacy writers resolve an existing exact identity before applying historical slug creation rules, avoiding duplicate non-ASCII/space-containing records. Sparse legacy snapshots preserve absent optional fields through feedback and restore.

## API and feature boundary

Feature flag: `experimental.story_record_versions_v1`, default OFF, disabled in V1 acceptance mode. Routes are mounted on both `/api` and `/api/v1` under `/novels/{nid}/experimental/story-records`:

| Route | Action | Authority |
| --- | --- | --- |
| GET `/catalog` | PROJECT scope, capabilities, history and recovery limits | Original project `domain.read` |
| GET `/{kind}/{rid}` | Exact public row, digest/version, bounded history, provenance, source state and feedback | Original project `domain.read` |
| PUT `/{kind}/{rid}` | Save known record fields with `expected_digest` and `expected_version` | Original project `domain.write` |
| POST `/{kind}/{rid}/restore` | `confirmed:true`, target retained version and current CAS create a new current version | Original project `domain.write` |
| POST `/{kind}/{rid}/feedback` | Version/source-bound human decision, note and evidence | Original project `domain.review` |

Kinds are `timeline` and `foreshadowing`. Request bodies are bounded to 128,000 bytes. Invalid or unknown inputs return 422; oversized input returns 413. A digest/version/source conflict returns 409 with identifiers only, never current private text or history. Reads use `Cache-Control: no-store`.

Local standalone mode preserves the original no-token authority. Packaged/collaboration mode uses original trusted-session, membership, NOVEL permission and project/workspace mapping. There is no unrelated model-inspection Host gate. A branch-only role does not authorize project-global records; an explicit branch header is rejected instead of being relabeled as a project source. Read/write/review, feature flag and authority identity are checked again at the operation boundary. Revocation before commit prevents the mutation; revocation during read prevents delivery of the materialized history.

## Version, provenance and human review

Chapter sources use the returned immutable chapter identity and document version/digest, not a chapter number as stored identity. Foreshadowing's original numeric planted/target fields are resolved to current stable chapter identities when saved. Planned future chapter numbers remain unlinked rather than inventing chapter IDs. Referenced Timeline events use original public digests.

Responses expose CURRENT, STALE or UNLINKED source state. Missing/archived/changed source chapters are stale. Cross-project source IDs are rejected. Save rechecks source digests before commit; stale sources require explicit `refresh_sources:true` after human review. Restore preserves the selected historical sources and may therefore produce a visibly stale current record. It never restores a removed source chapter.

Feedback decisions are ACKNOWLEDGED, INTENTIONAL, NEEDS_REVIEW or DISMISSED. The decision records note, evidence, actor, timestamp, record digest and source versions. A terminal decision cannot be rewritten for the same record/source snapshot. Changed material makes it stale; it is not silently re-approved. INTENTIONAL/DISMISSED apply to this record/source snapshot, not a global suppression rule for future findings.

These are synchronous original-record transactions, not background jobs. There is no duplicated task ID or pretend progress queue. Cross-module context/search continue to read the original current row. Exact source navigation opens the original chapter after a fresh authority read; existing manuscript dirty/composition/draft/conflict guards block unsafe navigation.

## Existing frontend surface and state contract

`StoryRecordVersionEditor` wraps the original `TimelineEditor` and `ForeshadowingEditor` only when the server flag is ON. Feature OFF preserves the legacy callback. Discovery/read failures fail closed instead of falling back to an unguarded save. Existing AppShell, layout tokens, primitives and primary workspaces remain unchanged.

- Loading: flag and original-owner capability/current-row reads.
- Empty: new unsaved record; existing historical records appear as version 0; first save/change produces version metadata/history.
- Disabled: flag OFF keeps the historical editor; V1 hides the opt-in endpoint.
- Unauthorized: history/editor material is hidden on 401/403; no automatic legacy write fallback. An authorized retry preserves the unsent draft.
- Error/offline: persistent message and retained local draft. Retrying a read never retries a possibly committed write.
- Conflict: preserves draft and blocks save. An explicit fresh GET must succeed before offering “retain draft and adopt latest baseline.” The latest server title/description is shown for comparison. A second writer after that read still loses CAS.
- Review: bounded version preview, explicit restore confirmation, note/evidence controls, terminal/stale feedback display.
- Cancel: cancel edit removes only the unsent local candidate; cancel restore dismisses a preview; both are unavailable during a dispatched write. Cancel/unmount aborts pending exact-source navigation. It does not claim to roll back a committed save.
- Recovery/resume/restart: actor/project/kind/record-keyed browser candidate is explicitly recoverable after remount. Original GET returns current receipt/history after server restart. Unknown actor sessions use page memory only with a visible warning. Storage-write failure is reported.
- Exact navigation: source buttons carry immutable chapter IDs. Read cancellation, newer source selection, changed project/actor/session/chapter, A→B→A and leaving Story discard stale completions. A dirty current/target manuscript is kept by the existing App draft authority, not a new duplicate guard.
- Missing configuration: no model/provider is required for these deterministic records; model-quality claims and GPU execution are not applicable.

## Verification receipt

Local checks use synthetic project fixtures and an isolated writable HOME/XDG/novel-data root; no private manuscript, paid API, credential, model download or external runtime is needed.

- Focused File and original regression: 59 passed, 57 PostgreSQL cases deselected. Files: `test_surface_story_record_versions.py`, `test_surface_story_record_api.py`, `test_structured_record_cas.py`, `test_r5_structured_forks.py`, `test_r5_structured_forks_mounted.py`, `test_phase4_timeline.py`, `test_phase4_foreshadowing.py`.
- New real-PostgreSQL cases: 22 selected and collected with `STORAGE_BACKEND=postgres -m postgres_backend_only`. **Execution NOT_RUN:** no configured `TEST_POSTGRES_DATABASE_URL` in this executor. There is no SQLite substitution or new skip.
- Frontend: `StoryRecordVersionEditor.test.tsx` covers 14 cases; `AppStorySourceNavigation.test.tsx` covers 9. Existing Story/Search and App draft/history regression tests also passed: 70 cases across 6 files, with a final 23-case rerun after the last UI-only changes.
- TypeScript build/typecheck and token guard passed locally; the final parent gate still owns exact-publication-SHA aggregate verification.
- `surface-freeze-story-records.spec.ts`: 2 real File/React tests collected. Both save through original UI, race another real API writer, recover CAS, cancel/confirm restore, reload/recover/cancel local draft, record terminal feedback and open exact source. Geometry/screenshot checks cover 1366×768, 1440×900, 1920×1080 with frozen 56/44/32 shell heights.
- **Browser/visual execution NOT_RUN:** the previously established local server socket restriction was not retried. Run the existing `playwright.surface.config.ts` in the authorized hosted environment. Collection is not browser verification.
- Existing test assertions, skips, migration files 001–020 and historical audit objects are unchanged by this work.

## Opus handoff

Opus may restyle the inner editor, history display, feedback controls and source metadata with existing DS tokens/primitives. It must preserve original owner/scope, default-OFF/V1 behavior, server authorization, exact CAS inputs, no-content conflict response, current-read-before-rebase, source stale acknowledgment, terminal review binding, explicit restore, bounded history, local draft retention, cancellation/late-response guards and the existing dirty manuscript authority. Production PostgreSQL and browser evidence must remain NOT_RUN until the hosted results exist.
