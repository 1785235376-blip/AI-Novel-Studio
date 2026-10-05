# U14 portable projects and U16 safe batches

## Status and scope

EXTEND, deterministic implementation and UI integration. File/API/request behavior is exercised below. Actual PostgreSQL, Chromium, native desktop, screen readers, Windows IME and real-model behavior remain NOT_RUN in this environment. This checkpoint does not mark all of U14/U16 complete.

- U14 exports a real bounded ZIP containing selected current manuscript documents and their referenced, decoded media. SHA-256 manifests use relative media references and portable aliases. Import first validates all members and media without extraction, then requires an explicit version/digest-bound confirmation to create a fresh UUID-based project through the original project/chapter/asset services. It never restores into an existing project or copies grants.
- U14 preserves missing-media declarations and readable manuscript. Relinking accepts a user-selected, decoded file, compares its digest to the original when available, and requires an extra explicit replacement confirmation for a different/unknown digest. It creates a new asset, changes only the selected current chapter references with original CAS/history, and keeps the prior record.
- U14 storage previews distinguish manuscript, accepted assets, history, trash, reproducible caches and failed/recovery inputs. Unmeasured categories explicitly say so. Only verified, reproducible portable-export cache files are eligible. Confirmation binds the exact preview; original assets, historical revisions, trash and staged recovery inputs are never cleaned.
- U16 persists an input/configuration/permission/source-privacy/budget snapshot without starting anything. A separate confirmation binds that snapshot and a strict zero-USD budget. Another explicit action dispatches exactly one stage through the original proofreading, frozen-snapshot export, or registered deterministic media executor. Concurrency is one per batch. There is no timer or automatic restart.
- U16 supports selected chapters, an exact single-chapter Unicode proofreading range, TXT/Markdown/DOCX/EPUB/PDF formats supported by the original renderer, and the exact host-owned synthetic image adapter. It reuses the original broker budget configuration when enabled and makes no reservation or paid call for these zero-cost operations. It does not create a second model router or script executor.
- Completed proof/export results with identical current source/configuration fingerprints can be skipped. Only failed stages can return to preflight for a new confirmation. An orphaned RUNNING claim is reported UNKNOWN and cannot be replayed. Unknown paid/model outcomes must be reconciled in their original executor; no paid operation is admitted by this implementation.
- A batch-produced media candidate remains a draft until separately previewed and accepted through the original media review and asset promotion services. Promotion interruption can resume from the original asset checkpoint without duplicate acceptance. Batch-owned tasks/proposals are inaccessible to generic media execute/retry/review/read APIs.

## Boundaries that remain partial

1. The portable format is an explicitly declared current-manuscript/referenced-media subset. Canon, history, trash, screenplay/domain records, workflows and experimental metadata are not copied. The existing offline `app.backup_restore` remains the full backup/recovery authority. No full-project equivalence is claimed.
2. Restore always creates a new application-managed project/directory on the active backend. Arbitrary destination paths, existing-project restore, copying collaboration memberships, and collaboration-branch writes are unsupported. The original branch creation/write adapter must be provided before those operations can be admitted.
3. Portable rich text is a strict safe TipTap subset. Unsupported nodes/attributes/marks fail explicitly. Remote URLs, local `src` paths, raw HTML/XML/SVG, scripts, playlists, model binaries and credential/provider configuration are never portable media. User-authored prose remains literal text. Inline media rendering in the editor is not newly added; accepted media can be verified through the original asset library.
4. Bounds: 100 selected chapters; 100 media records; 101 ZIP members; 40 MiB input ZIP; 32 MiB expanded content; 8 MiB per media member; 4 MiB manifest; compression ratio maximum 100. No extraction, network retrieval or optional-tool installation occurs. Existing decoders fail closed if unavailable.
5. Cross-repository restore/relink is deliberately checkpointed, not a distributed transaction. Interrupted writes retain the partial new project/assets and ID map as RECOVERY_REQUIRED; they are not automatically repeated or cleaned. Recovery uses the original project/chapter/asset interfaces. There is no destructive rollback button.
6. Cleanup currently covers only this feature's reproducible export cache. It is not a full disk scanner, old-asset deleter, history compactor or general cache manager. Cache regeneration requires the same current sources and media. Private recovery assets are excluded from accepted-asset byte totals.
7. U16 allows at most 20 items per batch, at most 200 readable chapters/2,000,000 source characters, 2 MiB per result and 4 MiB total persisted stage results. It does not run cloud/paid models, external workflow programs, real audio redo or real image/video models. Those paths need original workflow and broker admission. There is no GPU telemetry or control claim. B01 reusable template integration remains a dependency, not a parallel preset system.
8. Media-bearing prose exports are refused here and directed to the original resource-package export flow, rather than silently dropping resources. Actual renderer compatibility in Word/EPUB readers/PDF viewers remains unverified.

## Authority and persistence

New server flags: `portable_projects_v2`; `safe_batches_v2` requires `reader_preflight_v2`. Optional synthetic media also requires `cover_storyboard_generation` and `media_adapter_registry`. Broker configuration is consulted only when its own dependencies are enabled. Default OFF, wildcard rejection and V1 acceptance override remain server-authoritative.

Both routers require the original trusted host session and original project/branch permission resolver. Read responses are no-store. Every mutation checks current actor/scope and source/configuration fences immediately before domain effects and before accepting their results. Hidden/deleted/foreign sources conceal dependent IDs, titles, counts and outputs. CAS responses never echo internal frozen rows or binary bodies. Chapter privacy receipts form part of source fingerprints; cloud consent is never inferred or copied.

Metadata uses original `ExperimentalStore` File/PostgreSQL scope transactions. Bounded archive/relink files live in application-managed `portable_cache_v2` sidecars; names derive from scope/actor/record digests, never user paths. These sidecars are separate from canonical manuscript, asset, history and trash storage. Cache symlinks are refused. Explicitly accepted assets retain feature-origin fences through the existing AssetLibraryService. No old migration changes or startup scans are introduced.

MediaService has a narrow server-only context capability plus dispatch/review guards for batch-origin tasks/proposals. Legacy routes cannot supply it. Existing A13 production replay and U06 change-impact guards are preserved. Original media behavior without the marker is covered by regression tests.

## Source map and UI contract

- `app/experimental/portable_projects.py`, `portable_projects_api.py`
- `app/experimental/safe_batches.py`, `safe_batches_api.py`
- Narrow batch-origin fencing in `app/experimental/media.py`
- `frontend/src/experimental/PortableProjectsPanel.tsx`, `portableProjectsClient.ts`
- `frontend/src/experimental/SafeBatchesPanel.tsx`, `safeBatchesClient.ts`
- Composition/flag/capability/Workbench changes are owned by the parent integration checkpoint.

Both panels consume DS-v1.0 `Panel`, `Button`, `Badge`, `StatusMessage`, shared fields/resources/actions and existing experimental classes. There are no custom colors, layout tokens, parallel shells, new global CSS or frontend framework dependencies. Loading, no-data, missing-media, permission error, source conflict, review/confirmation, in-progress, stopped, partial and unknown/recovery states have actual controls. Scope remount clears private prior data and approvals; stale async file reads cannot upload after unmount. Stop has a separate action path and retrieves the current batch version while a dispatch request is in flight.

Opus may restyle presentation within DS-v1.0. It must retain separate preflight/confirmation/execution actions, the exact scope/budget binding, conservative cleanup, unknown-result restrictions, missing-media declarations and distinct candidate acceptance. No screenshot or browser geometry PASS is claimed here.

## Verification commands and observed layers

All local execution uses the existing isolated `r2-run.sh` environment, mock/offline settings and pinned pnpm path. No paid calls, real credentials, model downloads, browser retry, remote push, PR mutation, merge, release or deployment was performed by this worker.

Backend current owned tests:

- `tests/test_r4_portable_batches.py`: File plus opt-in real-PostgreSQL parameterization, actual WAV packaging/decoding/new-project restore, missing-media/relink/old-history preservation, malicious ZIP paths/symlinks/ratio/member/size/digest/HTML/XML/extra-field rejection, source/actor/flag/privacy fences, cache preview/cleanup/regeneration, explicit stage dispatch, selected export, Unicode proof range, failed-only retry, orphan UNKNOWN, concurrent claim, late cancellation, exact synthetic adapter, legacy bypass denial and interrupted original asset-promotion recovery.
- `tests/test_r4_portable_batches_mounted.py`: actual app routes at `/api` and `/api/v1`, real trusted sessions and membership stack, new project restore, actual DOCX ZIP/XML output, OFF/dependency/V1 fences, branch no-fallback, final-dispatch source/flag/V1 revocation, sanitized CAS and legacy child/asset-origin checks. Actual PostgreSQL parameters run only with an authorized disposable endpoint.
- Impacted regressions: `test_r3_media_workflows.py`, `test_r4_production_lineage.py`, `test_r4_change_impact.py`.

Frontend:

- `PortableProjectsPanel.test.tsx`, `SafeBatchesPanel.test.tsx`: 10 actual fetch-bound request/state tests, including StrictMode, exact confirmation payloads, no auto-start, duplicate-click guard, selected files, error retention, scope/unmount suppression and current-version stop.
- With `AppShell.test.tsx` and `ModuleWorkspaceRoutes.test.tsx`: 36 tests passed in the recorded focused run.
- `frontend/tests/e2e/r4-portable-batches.spec.ts` is an authored real File API + React journey using the already configured isolated synthetic host-session profile. It restores a newly downloaded ZIP to new IDs, then preflights/confirms/executes one batch stage and stops the rest. Local Chromium execution is NOT_RUN due the previously established platform EPERM; no launch retry was attempted.

Exact final local test totals and commit SHA are supplied in the worker checkpoint message rather than inheriting historic counts. Real PostgreSQL, real browser rendering/screenshots, actual GPU, paid/real-model quality, Windows and user acceptance remain NOT_RUN/BLOCKED.
