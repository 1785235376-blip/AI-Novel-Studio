# B10 · Selected local offline exchange foundation

Status: EXTEND original identity, chapter version/history and B09 rich-document merge authority; NEW bounded opt-in protocol/outbox/inbox/manual UI. Deterministic local engineering loop is implemented and tested. Production cloud operation is not implemented or authorized. Collaboration-branch manuscript writing remains explicitly unsupported.

## What users can actually do

In Experimental → 离线同步, using a current trusted host session:

1. Save prose in the original editor, then select up to 20 chapters of the current local project. Nothing is selected by default. Optionally allow received additions to become new independent chapters after review.
2. Register a public exchange batch label and mutually reversed endpoint labels on two local installations. These labels are routing metadata, not credentials or proof of identity.
3. Queue a current saved chapter snapshot into the durable local outbox, with a stable message/idempotency key, original version, public routing labels, and increasing cursor. Neither an online receiver nor a model is needed to preserve the local save.
4. Inspect the exact versioned JSON envelope and acknowledge the copy boundary before generating a local download. Export rechecks current source version, current feature/session/authority and revocation. There is no network destination field, outbound client, listener created by this feature, timer, automatic retry or cloud fallback.
5. Paste a transferred envelope at the receiving installation, preview it, and explicitly map it to a selected existing chapter or a permitted new chapter. The inbox commits the candidate and a receipt without writing original chapters. The receipt acknowledges inbox storage only, not review acceptance or authenticity.
6. Read the baseline, local current version and incoming candidate. B09's rich-block diff3 identifies conflicts. Choose local/incoming per conflict, re-preview, acknowledge, then apply through the original chapter create/save/archive authority and CAS. No last-writer-wins overwrite exists.
7. Record failed/unknown manual transport, re-export the same message at most eight times, verify the exact receipt, or inspect an uncertain chapter-write result. The same incoming message is idempotent; changed content or changed initial target under that ID is rejected.
8. Reconcile a unique exact existing result explicitly, or close an uncertain record without replay. All candidates, checkpoints and partial new chapters remain. A closed record does not assert that nothing was written.
9. Exchange an explicit tombstone only for a currently archived selected source. Its receiver still reviews delete/modify choices. Tombstones block future updates for that source in that batch. Revoke the whole batch to stop future receive/export/apply.

Already downloaded copies and historical backups cannot be recalled or promised physically erased. Tombstones and revocation govern future application access only.

## Authority and scope

- Exact server flag `offline_sync_v2`, default OFF, depends on `project_forks_v2` and its declared transitive dependencies. `V1_ACCEPTANCE_MODE` forces it OFF. UI hiding is not the security boundary.
- Service/router: `app/experimental/offline_sync.py`, `offline_sync_api.py`. Routes are under both original API prefixes at `/novels/{nid}/experimental/offline-sync`.
- Reuses original host-session resolver, project authorizer, local actor identity and current chapter repository. Actor, project, scope and flag are rechecked at read/dispatch/review/final-write boundaries. Original API adapters independently check `domain.write` immediately before create/save/archive.
- The only supported source scope is the exact local project scope without a branch. Collaboration scopes fail closed and never display base chapters as branch-isolated content.
- B09 `rich_document`, `block_merge`, `advance` are reused. The original chapter store remains the only editable manuscript authority. Incoming snapshots, outbox envelopes and checkpoints are immutable evidence/candidates, not a parallel editable manuscript repository.
- Original rich marks and revision locks are preserved. A lock-breaking incoming choice is blocked. Source drift after preview invalidates apply. Rename is part of the rich-document CAS; no independent metadata overwrite is performed.
- New chapter creation uses the original creation API followed by original rich-document CAS. Durable `CLAIMED` intent precedes this non-atomic two-step operation. An interruption can leave a partial chapter. Such an outcome is `UNKNOWN` and cannot be replayed automatically.

## Protocol and persistence

`AI_NOVEL_SYNC_1` contains only these fields: protocol, stream ID, source/destination endpoint labels, stable message ID, sequence, source chapter ID/version, operation, baseline snapshot, current snapshot or tombstone, and `LOCAL_ONLY` privacy label. Strict extra-field rejection and typed inputs prevent credentials, arbitrary URL/transport options, execution scripts, or other data classes from becoming protocol fields.

Snapshots allow only title and a bounded supported rich document. Asset references are rejected because this protocol does not implement authorized asset mapping. U14's document allowlist plus B09 revision-lock handling reject unsupported rich nodes, links, embedded execution content and undeclared attributes without flattening them. A defensive text guard rejects common absolute local paths and credential-shaped strings. This guard is not an exhaustive secret scanner or DLP guarantee; users inspect the actual envelope before export. Prose is never silently redacted or normalized.

Persistence uses existing `ExperimentalStore` collections:

- `offline_sync_channels_v1`: exact selection, actor ownership, initial baseline, pair labels, source-to-target ID bindings, send/receive high-water cursors, revocation and tombstones
- `offline_sync_outbox_v1`: immutable envelope, digest, idempotency key, PENDING/UNKNOWN/FAILED/ACKNOWLEDGED state, attempts and bounded shallow state history
- `offline_sync_inbox_v1`: immutable received envelope, exact mapping request digest, PENDING_REVIEW/SUPERSEDED/CLAIMED/UNKNOWN/APPLIED/RECONCILED/CLOSED_WITHOUT_REPLAY state, checkpoint/intent and write journal

File transactions use the existing cross-process lock and atomic replacement; PostgreSQL uses the existing isolated experimental metadata transaction/row lock. No new SQL schema/migration is needed. No database directories are copied. Data is not compatible with opening a new experimental data directory in the frozen PR37 build; use isolated copies or supported export/import, not an in-place rollback claim.

Bounds: 20 channels/project, 20 selected chapters/channel including received additions, 100 outgoing plus 100 incoming messages/channel, 8 MiB total channel record budget, 512 KiB envelope/input payload limit (8 KiB HTTP wrapper allowance), approximately 256 KiB individual snapshot limit, eight manual exports/message, 100 shallow historical state entries/record. Saturation fails closed without discarding original prose or older candidates. Finish/review/export the batch and establish a fresh explicitly selected batch rather than deleting evidence invisibly.

The receive cursor is a monotonic high-water mark. Gaps are accepted for full snapshots; old/out-of-order messages are rejected. Requeue the current saved chapter as a new message if an older chapter's envelope was skipped. A newer received full snapshot supersedes pending earlier candidates for that same remote source while retaining their evidence. Pending uncertain writes block newer candidates for that source until explicit reconciliation/closure.

The batch baseline is intentionally fixed. Repeated sequential changes can therefore require another explicit conflict choice even if an earlier candidate was applied. This conservative behavior avoids inventing an unauthenticated applied-version acknowledgement protocol. Establish a fresh selected batch when a new common baseline is wanted. A tombstoned or revoked batch cannot be silently reopened.

## Recovery and privacy boundaries

- Outbox export state is UNKNOWN until a matching manually supplied receipt is checked. Exporting or clicking a download cannot prove that another installation received anything.
- Claimed/unknown manuscript writes are never automatically retried. Recovery compares original authority against the captured checkpoint and intended document and reports exact match, unchanged checkpoint or divergence/partial result.
- Exact-match adoption is explicitly labeled manually reconciled, not proof of exactly-once execution. A changed recovery observation invalidates adoption.
- Closing an uncertain record retains its checkpoint and candidates and does not mutate original chapters. Partial additions can require inspection and a fresh batch mapped to the existing chapter; the old create is never replayed.
- No credentials, binaries, model/cache directories, assets, character/Canon/workflow stores or local path metadata are collected. No arbitrary external scripts/templates execute.
- Standard HTTP over loopback is used only by the explicitly run synthetic two-process test. Production external network synchronization is absent/OFF. No custom encryption, E2EE, hosted cloud storage, TLS deployment or production key lifecycle is claimed.

## Verification at this implementation checkpoint

All data is original synthetic test content; no paid model, real credential, cloud account or production deployment was used.

- Actual File service plus mounted production API: 33 PASS; 33 real-PG cases selected out in the File run. Includes restart persistence, selected-only boundaries, original writers, CAS conflict/history, unknown create recovery, duplicate replay, wrong routing/base/binding, source drift, lock protection, current session/flag/V1 revocation, strict input/limits, concurrent single-writer claim, tombstones and bounded retries. Command: `../r2-run.sh pytest -q tests/test_r5_offline_sync.py tests/test_r5_offline_sync_mounted.py -m file_backend_only`.
- Real two-endpoint TCP runtime: 1 PASS locally. Command: `RUN_B10_TCP_SYNC_TEST=1 ../r2-run.sh pytest -q -s tests/test_r5_offline_sync_tcp.py`. Two different uvicorn PIDs, loopback ports and isolated File data roots, real `httpx` socket transfer. Add, edit, conflict, stopped receiver, durable sender save, restarted receiver, replay, tombstone and revoked receiver all ran. This is independent of the in-process mounted API evidence.
- React/jsdom behavior: 8 PASS, including explicit selections/acknowledgements, copy cleanup, retained Unicode input on receive failure, per-conflict re-preview, stale-choice reset, unknown-write actions, refresh revocation, captured host context and delayed result suppression under StrictMode/project switch.
- TypeScript build/typecheck and UI token guard PASS on the implementation worktree. No new design token, shell or protected system surface is changed.
- Authored real browser journey: `frontend/tests/e2e/r4-offline-sync.spec.ts`, existing trusted synthetic host at UI port 5182/API 8022, actual File/API/React without response mocks. Includes manual download, exact receipt, same-block conflict choice, original CAS apply, untouched unselected chapter, revocation and 1366×768/1440×900/1920×1080 screenshots. Local Chromium previously fails with EPERM; it was not retried. Hosted result and actual screenshot evidence must be observed separately before PASS is reported.
- PostgreSQL tests are real marked service/mounted tests requiring `TEST_POSTGRES_DATABASE_URL` under the existing isolated hosted gate. Local PostgreSQL is absent. No local PostgreSQL PASS or parity result is claimed.
- Windows IME/native desktop, production networking/authentication/key lifecycle/cloud operations, real recipient identity authentication and physical deletion of existing copies remain NOT_RUN / outside this implementation.

Counts above describe explicit runs, not a release acceptance or final commit-SHA receipt. The lead records published source SHA and hosted run receipts after integration. The separate model-review slice is platform-blocked and is not represented as independently reviewed.

## Frontend / Opus handoff

`OfflineSyncPanel.tsx` and `offlineSyncClient.ts` are consumers of existing `Panel`, `Button`, `Badge`, `StatusMessage`, `Field`, resource/action hooks, experimental layout classes and captured `ExperimentalClient`. No new AppShell, colors or spacing are introduced. Forms use native labels/checkboxes/selects and standard keyboard focus. No polling or background listener beyond an existing-style window-focus refresh is installed.

Presentation can improve, but retain: explicit empty selection, fixed target mapping, source-version readouts, complete envelope/diff evidence, renewed review after conflict choices, final apply/copy acknowledgement, pending/failed/unknown states, no automatic retry of uncertain writes, visible limitations, source/authority errors, and the irretrievable-copy warning. A cosmetic change must not turn manual file preparation into a misleading working-network Sync button.
