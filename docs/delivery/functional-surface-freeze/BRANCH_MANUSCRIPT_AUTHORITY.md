# Branch manuscript authority and functional surface

Date: 2026-10-07. Delivery wave: Feature Completion & Functional Surface Freeze.
This is an engineering surface, not final Opus styling or a freeze declaration.

## Ownership and persistence

- Mainline: existing `ChapterService` and File/PostgreSQL ChapterRepository remain the only mainline manuscript owners. Existing A43 chapter IDs, namespace reservations, rich documents, histories and tombstones are unchanged.
- Collaboration manuscript: `BranchManuscriptRepository` is the only branch prose owner. It stores `branch_manuscripts[branch_id]` in the existing full-scope `ExperimentalStore`. There is no editable manuscript copy in Tasks, Review, Realtime or Sync.
- Scope: exact `{mode: collaboration, novel_id, workspace_id, storyline_id, branch_id}`. Existing CollaborationScopeService validates workspace/project/storyline/branch ancestry. All public routes use the original trusted session and membership/permission resolver.
- File commits are one atomic scope-document replacement under the existing OS/interprocess scope lock. PostgreSQL commits use the real existing `experimental_scope_documents` JSONB row transaction and row lock. No historical migration is modified and no schema migration is necessary.
- Empty branch metadata is not a manuscript. Manifest `initialized=false`, revision 0, empty catalog and unavailable source status persist until explicit chapter creation or confirmed fork.
- Registered production collaboration readers/writers/generation never fall back to mainline. Flag OFF returns disabled; flag ON and uninitialized returns empty or unavailable. Genuinely unscoped local routes retain mainline ownership.
- Source integrations use an explicit `for_scope(scope)` view. Unbound reader adapters are wrapped in a read-only exact project/branch fence; no branch label is invented for a mainline row.

### Stored model

A manuscript contains `owner=BRANCH_MANUSCRIPT_V1`, exact scope, monotonic manuscript revision, next never-reused chapter number, immutable-ID chapter map, operation receipts and audit entries. This manuscript revision is separate from the historical narrative-scope revision; chapter version is the document CAS token.

Each chapter contains:

- ID `novel_id:~b<UUID>`; immutable logical number and independent sort order
- Exact project, branch and full scope; authority owner
- Original rich `document`, derived Markdown `content`, document digest, title, word count
- Integer version; creator/updater and timestamps; archived/deleted state
- Scope-owned immutable history snapshots, actor, source/reason and timestamp
- Optional explicit fork origin `{scope, chapter_id, version, document_digest}` and immutable baseline document

Create allocates a fresh UUID and never reuses a number. Move changes only sort order and manuscript revision. Save/restore/archive/deletion preserve identity. Permanent branch deletion requires prior archive and exact version, retains a tombstone/history, and cannot rebind an old identity to a new chapter. A document restore creates a new current version. Rich nodes/marks are validated and retained as trees, never converted to Markdown and reparsed as the storage authority. Existing AI paragraph-lock preservation remains enforced.

Stored scope, identity, allocation and history corruption fails closed. Scope records/receipts are validated before exposure. No legacy numeric or parent-branch alias resolves a branch chapter.

## Capacity contract

All limits reject before commit with explicit `BRANCH_CAPACITY_*` errors; nothing is silently evicted, compressed, renumbered or replayed. History, tombstones, receipts and review evidence remain readable. To continue at capacity, an operator/author must explicitly export/review data and create a new authorized fork; automatic compaction or deletion is not implemented.

- One document: 2,000,000 UTF-8 JSON bytes
- One branch: 2,000 lifetime chapter identities, including retained tombstones
- Normal chapter history: 500 full snapshots; 20 additional slots reserved solely for explicit restore/archive-restore
- Operation receipts: 5,000; audit entries: 20,000
- Manuscript owner payload, including all histories and receipt chapter snapshots: 64 MiB hard limit, with 4 MiB reserved from ordinary writes for explicit restoration (60 MiB normal-write limit)
- Fork preview: at most 40 unique chapters and 8,000,000 JSON bytes
- Branch-owned review/snapshot collections together: 64 MiB hard limit; 4 MiB is reserved from new records for terminal/recovery journal finalization
- Fork records: 200; merge records: 500; context snapshots: 1,000; individual context snapshot: 1,000,000 bytes

These are supported capacity ceilings, not a performance benchmark. The original mainline limits and histories are unaffected. Other preexisting experimental collections have their own owner limits; this branch slice does not claim global sharding or production multi-host scale. Capacity limits and used manuscript bytes appear in the manifest.

## API catalog

Both standard `/api` and `/api/v1` mounts use the same router. New surface base:

`/novels/{nid}/experimental/branch-manuscript`

| Method/path | Action / boundary |
|---|---|
| GET `/catalog` | Manuscript owner, initialized state, revision and current write/review advisory permissions |
| GET `/chapters?archived=` | Exact branch catalog |
| POST `/chapters` | Create independent rich document; domain.read + domain.write |
| GET `/chapters/{cid}` | Read exact branch document |
| PUT `/chapters/{cid}` | Rich save with expected_version and immutable operation_id receipt |
| GET `/chapters/{cid}/history` | Exact chapter history |
| POST `/chapters/{cid}/restore` | Historical document to new current version via CAS |
| POST `/chapters/{cid}/archive/{archive\|restore}` | Archive lifecycle via CAS |
| POST `/chapters/{cid}/delete` | Archived-only exact-version tombstone |
| POST `/chapters/{cid}/move` | Stable-ID order change with expected manuscript revision |
| GET `/sources?source_branch_id=` | Authorized branch source catalog; omitted source is explicit project-authorized mainline |
| GET `/records` | Permitted fork/merge metadata; revoked counterpart sources omitted |
| POST `/forks/preview` | Pin up to 40 unique authorized source chapters, at most 8 MB snapshots |
| POST `/forks/{rid}/apply` | Human confirmation, record CAS, preview digest, exact reviewed source versions, target manuscript revision |
| POST `/compare` | Rich-block three-way comparison; explicit per-conflict choices |
| POST `/merges` | Persist a proposal only for the exact comparison digest; no target write |
| GET `/merges/{rid}/review` | Re-authorize counterpart; reopen complete desired document/checkpoint and report staleness |
| POST `/merges/{rid}/apply` | Human-confirmed source and target fences; target write + review authority required |
| POST `/merges/{rid}/recovery` | Inspect current target and exact branch operation receipt; never replay an uncertain write |
| POST `/{fork\|merge}/{rid}/cancel` | CAS cancellation of REVIEW only; executing/terminal operations cannot reopen |

Input JSON is streamed under a bounded body limit, unknown fields rejected. Read responses use no-store. All operations recheck feature flag, host session, identity, read authority and requested mutation authority before persistence. Counterpart reads/writes use their own resolver and must remain the same identity/scope.

Mainline source import requires original PROJECT read authority. Mainline merge additionally requires PROJECT write and review authority. A branch-level role does not grant these rights. Mainline writes use the existing atomic audited chapter port, never a branch route or a bypass repository write.

### Existing Write/editor routes

- Collaboration chapter list/create now select the registered branch owner, while retaining original response schemas.
- Original `/chapters/{cid}` get/save, rename, archive, archive restore, history and historical restore route through the exact branch view.
- Original DELETE lacks an expected-version contract, so a branch request is directed to the versioned deletion surface with HTTP 428; it never falls through to mainline deletion.
- Existing revision and snapshot views use the branch authority. Branch rich saves preserve the existing editor's server/local conflict contract; the new dedicated API exposes content-free 409 metadata.
- Original project `/novels/{nid}/chapters` remains an explicitly project-authorized mainline listing. It is not a branch catalog.

## Generation, context, task and review integration

The original `JobManager` and original generation persistence remain the task owners. Default File composition now reuses the registered ChapterService instead of accidentally constructing an unbound service.

- Prepare captures the exact branch chapter version/digest before dispatch and stamps the branch feature origin.
- Provider-facing request preparation resolves the branch source each time. Automatic branch context contains branch identity/version only until independently scoped sources are explicitly selected. Mainline lore/manuscript context is never implicitly injected.
- Original generation routes bind the existing transient request-authorization hook for registered branch sources. Provider dispatch re-resolves the original session, branch membership, feature and current source. The token is never serialized, and a missing post-restart hook cannot dispatch.
- Context snapshots live in the same branch scope and preserve chapter version, request-context digest, generation ID, actor/session metadata and model identity. Existing snapshot API shapes are retained.
- PostgreSQL generation rows retain typed branch identity and scope in the original immutable request payload. A branch is never attached to a mainline chapter foreign key or snapshot foreign key. Existing job identity/scope cannot be rebound; tombstones allow terminal recovery of an already recorded job but not admission of a new job.
- Original generation streaming rechecks observer authority at the same live HTTP/SSE and ASGI byte-send boundaries. Branch archive/removal, feature disable and permission/session revoke make the observer unavailable. Observer closure does not cancel another owner's job.
- Read/SSE owner dispatch is based on the configured branch authority for every BRANCH-scoped job, never a substring in its chapter ID. A retained branch-labelled job pointing at an old mainline ID cannot disclose historical output or retry through the branch surface; the retained record is not rewritten. Branch UUID recognition is exact and project-bound, so a branch-like marker within a legacy project slug is not mistaken for a branch chapter.
- Original task-center projection reads the exact branch source/version. Original cancellation and terminal-only review guards remain in force.
- AI acceptance writes only through the branch collaboration application boundary, with original document CAS and AI lock checks. The existing ACCEPTING/ACCEPTANCE_UNCERTAIN journal is retained across restart.
- No branch generation writes mainline summaries, Canon proposals or memory. Response explicitly states `BRANCH_CANON_REVIEW_ADAPTER_REQUIRED`; automatic branch Canon extraction/promotion is not claimed.
- Direct replay of experimental-origin jobs requires fresh author preview. Restart marks interrupted execution FAILED durably and does not dispatch a model automatically.
- Every collaboration `/generation/{id}/retry`, including historical unmarked jobs, validates the current session, membership and source and then requires a fresh author preview. It never invokes the legacy model replay path.
- Branch fork/merge proposals project read-only into the existing Unified Review Inbox. They advertise no generic/batch actions and expose the exact original panel, record ID, version, scope and versioned API navigation contract. Counterpart read permission is rechecked before projection. Cancel and content adoption remain solely in the original branch surface, with its existing read/review permissions and CAS, never a generic approve-all or alternate cancel authority.

Other integrated source owners include Planning/Story Graph/World, Style DNA/Narrative Judge/Revision Intelligence, broker and explicit author context, workbench comments/style/plan references, imports, Change Impact, Writing Focus, Resume/Search and Reader Preflight. Media/audio/visual/research/realtime/sync source integrations consume the same scope adapter through their existing owners.

### Export source authority

The registered `NovelService.export_snapshot` routes branch exports to the exact branch manuscript owner. Captured chapter evidence includes owner, full scope, version and document digest. Project-owned datasets and outline are excluded without reading those owners; adding a branch label to a project record cannot authorize its export. Branch-owned screenplay/resource sources retain their own existing exact branch fences.

Retained pre-authority export artifacts may have a branch permission label while containing mainline prose. They are not rewritten or relabelled. Without verifiable branch snapshot evidence, the original owner must independently have PROJECT authority to read, download, retry or cancel the artifact. History filters these records before pagination and reauthorizes before response, so denied records contribute no visible count or pagination hint. A new branch snapshot remains immutable when the live source later changes. Disabling the branch feature blocks its disclosure.

## Fork, conflict, merge and recovery semantics

Fork captures an explicit, immutable, authorized snapshot. It creates new branch IDs and records lineage; it never changes source ownership or aliases an old source ID. Source freshness is checked before the target transaction. The snapshot represents the reviewed source versions; it is not a globally atomic multi-branch snapshot. Target allocation and the complete fork result commit in one target scope transaction.

Merge reuses the existing deterministic rich-block diff3 algorithm. Overlapping edits and document-attribute differences require explicit choices; paragraph locks cannot be silently removed. A persisted proposal is pinned to source/target versions, exact documents, choices and comparison digest. Target CAS occurs at the authoritative write. No cross-scope lock cycle is introduced: cross-scope inspection happens outside the source claim transaction.

A durable APPLYING intent precedes the external target write. A branch target atomically stores the exact operation receipt with its document; a later recovery can prove that operation committed. Mainline target writes use their original authority in a different transaction. If the response or final journal update is lost, matching text alone is not proof of exactly-once completion: status remains RECOVERY_REQUIRED, current/checkpoint evidence is shown, and automatic replay is forbidden. The original mainline history or branch restore surface remains available for an explicit new-version recovery.

States: REVIEW → APPLIED or CANCELLED for atomic fork; REVIEW → APPLYING → APPLIED / RECOVERY_REQUIRED for merge. Restart preserves REVIEW, CANCELLED and APPLIED; APPLYING is recoverable inspection, never a dispatch instruction. All transitions are versioned. No production distributed transaction is claimed.

## UI surface contract

Existing Experimental tool navigation gains “协作分支正文”; it belongs to Collaboration / Write and creates no top-level product workspace. `BranchManuscriptPanel` reuses existing Panel, Button, Badge, Field, StatusMessage, resource/loading and error primitives, with no shell, token or final visual redesign.

Components/actions:

- Initialization/owner/revision status; authorized branch chapter list and explicit creation
- Exact branch ID/version navigation into the original rich Write editor, its save/conflict/local-draft/history UI and original AI panel
- Explicit source selection, fork preflight, human confirmation and cancellation
- Rich three-way comparison, per-conflict choices, desired document inspection, pinned proposal creation
- Required fresh proposal-content read before final human merge; per-item confirmation
- Persistent uncertain-state recovery evidence, no automatic repeat

States: loading, empty/uninitialized, read-only, unauthorized/session expired, disabled/not-found, input error, CAS/source conflict, review pending, applying, cancelled, applied, recovery required. Missing provider configuration remains in the existing AI preflight/diagnostics. Scope/client changes remount the panel; stale async results cannot change the new branch view. Busy actions cannot double-submit. Confirmation is invalidated by refresh/change/conflict.

Opus may restyle these controls within the existing design system and improve readable diff presentation. Opus must not change identity, explicit source scope, no-fallback behavior, permission gates, CAS/receipt pinning, preview/confirmation requirements, source staleness, cancellation/terminality or uncertain-write no-replay semantics.

## Verification and limits

New tests are additive; no historical test, assertion, skip or migration was edited.

- `tests/test_surface_branch_manuscript.py`: actual File and opted-in real PostgreSQL repositories. Rich history/restore, identity/tombstones, restart, independent clients, same-transaction operation journal, rollback, revocation, flag disable, fork, diff3, human merge, lost-response recovery and sibling isolation.
- `tests/test_surface_branch_manuscript_mounted.py`: actual original sessions/membership/roles, new router and existing Write/generation API, both `/api` prefixes, permission separation, CAS/history/restore, synthetic provider request source, acceptance, durable restart, concurrent HTTP clients and comment precommit revoke.
- `tests/test_surface_branch_generation_stream.py`: original JobManager on real loopback HTTP/SSE; membership/session/feature/archive revocation, cancellation, retry boundary, durable interruption recovery and original task projection.
- Additional restart-recovery coverage verifies tombstoned source denial, original-session provider-dispatch revocation, historical export PROJECT rights and immutable bytes, exact branch provenance, pre-pagination authority filtering, final list reauthorization, tombstone identity capacity, byte/history restoration reserves and hard journal ceilings.
- `BranchManuscriptPanel.test.tsx`: exact editor navigation, default-off/read-only/empty states, explicit content review before merge, 409 preservation, double-submit and late result isolation. Targeted original frontend fork/workbench tests also run.
- New real browser scenario: `playwright.branch-surface.config.ts` and `branch-manuscript-live.spec.ts`, isolated synthetic File server, two browser principals, original editor stale-CAS dialog, explicit fork, unchanged mainline. First local Chromium launch was BLOCKED before the test body: `process_singleton_posix.cc socket() failed: Operation not permitted`. No browser body assertions or screenshots are claimed locally. The denial was not retried or bypassed. Hosted execution remains separate evidence.
- No real model, paid API, GPU, model download, production realtime server, cloud sync service, independent audit or final visual acceptance was run by this slice.

Current implementation limits: branch authority is a scope-atomic JSON/JSONB document (not a production large-document sharding claim); branch Canon/memory proposal generation requires a separate reviewed scope adapter; source assets/references retain their original identity and ordinary scope permissions (fork does not silently clone asset permissions); mainline merge recovery cannot infer exactly-once success from matching text; no automatic merge/replay or production multi-host distributed transaction.
