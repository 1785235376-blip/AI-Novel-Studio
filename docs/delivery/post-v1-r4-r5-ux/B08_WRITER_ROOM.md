# B08 · Asynchronous Writer Room / team review

## Delivery status

- Classification: EXTEND, with new scope-bound collaboration metadata; original sessions, membership, roles, manuscript readers, comments, asset authority and review inbox are reused.
- IMPLEMENTED / INTEGRATED: async assignment, responsible reviewer, status/change-request loop, task/comment conflicts, current-authority search and pull notices, local read-only chapter review and original version comments, explicitly selected local review ZIP.
- CONTRACT_VERIFIED: actual mounted File routes at both `/api` and `/api/v1`, trusted-session/role/membership tests, real concurrent clients and persistence reload. React tests verify interaction/lifecycle contracts; their HTTP fixtures are not evidence of browser/runtime success.
- PostgreSQL contracts: authored using the existing real PostgreSQL fixture, requiring the explicit isolated database environment. NOT_RUN locally because no authorized local PostgreSQL service is available; marked cases are skipped rather than emulated.
- Browser/geometry: real File/React `frontend/tests/e2e/r4-writer-room.spec.ts` authored, including screenshots at 1366×768, 1440×900 and 1920×1080. Local browser NOT_RUN because the established Chromium launch EPERM was not retried. Hosted execution must be observed separately before claiming PASS.
- REAL_MODEL_VERIFIED: not applicable to this deterministic async feature. No model, GPU, paid provider, cloud sender, deploy, real-account invitation or permission change is invoked.
- USER_ACCEPTED: NOT_RUN. Independent second-slice review remains platform-BLOCKED; implementation tests do not close it.
- Overall B08 remains PARTIAL for branch manuscript review, detailed below. No realtime-presence claim.

## Reused authorities and entry points

`WriterRoomPanel` is mounted in the existing lazy experimental workbench and uses existing Panel/Button/Badge/StatusMessage components and tokens. `writer_room_v2` is default-off, requires the separately allowlisted `unified_review_inbox`, and is forced off in V1 acceptance mode. No startup scan, timer, socket, background model call or migration is registered.

`app/experimental/writer_room_api.py` mounts `/novels/{nid}/experimental/writer-room`. Every read, index, notice, conflict lookup, package and mutation resolves the existing trusted session, active workspace membership and exact project/storyline/branch permissions afresh. Reads recheck authority before returning and use `Cache-Control: no-store`. Mutations recheck inside the existing scope transaction before commit. UI refresh and window focus fetch current authority; a confirmed authorization denial removes cached rendered content and revokes downloadable Blob URLs. There is no claim that previously delivered bytes can be erased from a client.

The room is the current scope, not a new account or membership system. Eligible assignees must currently have `domain.read` and `domain.write`; reviewers must currently have `domain.read` and `domain.review`. Assigning either creates no role or grant. Original asset access additionally executes `_authorize_asset_project`, preserving its project-plus-branch requirements and asset owner/feature fences.

## Usable asynchronous loop

1. Choose a current member and responsible reviewer, optionally link an exact chapter revision or original-domain review item/version, and create a task. Request IDs make identical creation retries idempotent.
2. The assignee starts work and submits for review. The responsible reviewer can request changes with a mandatory reason, or close the collaboration task. A reviewer with read/review but no manuscript-write permission can perform these review-status actions; they cannot edit task text or comments through a write endpoint.
3. Change requests return to the assignee. Status events retain actor, time and reason. Reopen/cancel are versioned explicit actions.
4. Closing a task never accepts domain content. The UI navigates to the existing unified review inbox; existing domain-specific approval and commit operations remain authoritative. B08 has no approval proxy or Canon/manuscript/media acceptance endpoint.
5. Search and pull notices are rebuilt from the currently authorized scope on request. There is no cached cross-actor search index, push delivery, email or realtime presence.

Tasks and conflict pairs use new collections in the existing File/PostgreSQL `ExperimentalStore` scope document, with its original locks/transactions and schema version. No old migration or source schema is changed. Each scope allows at most 500 tasks and 500 conflict records; capacity errors keep the submitted UI text but do not claim it was persisted.

## Conflict and comment semantics

Two independent trusted clients submitting the same task version produce one successful current revision and one HTTP 409. Before returning that conflict, the scope transaction persists both the server candidate and the submitted candidate, including their original expected versions. A fresh authorized conflict read exposes them. Choosing either candidate is a new CAS write against the current task version and marks that task conflict resolved while retaining both originals. A later conflict creates a further retained pair rather than overwriting it.

Comments reuse `CreationWorkbenchService.create_comment` and `update_comment`, including their existing source anchors, quote validation, message histories and CAS. A rejected concurrent reply is kept as a conflict candidate in B08 while the accepted reply remains in the original thread. After refresh, an explicit retry uses the current original comment version. Comment and transition conflict entries are retained audit candidates; they are not a second acceptance system and are not automatically marked applied just because a later comment/status operation happened.

The separately committed optional `reauthorize=None` seam on the original comment methods runs inside their existing lock immediately before the original write. Existing callers retain the unchanged default contract. B08 passes current feature/membership/source checks. Failure before write leaves the original comment unchanged. There is no cross-store exactly-once claim for a successful original comment write and any later view refresh.

Unsaved task edits survive refreshes and switching tasks inside the current room, remain in memory, and are not presented as durable storage. The UI disables fields during their save, preserves an unsuccessful candidate, warns before browser unloading with an active dirty edit, and states that work should be saved before leaving the room. Changing session/project/branch discards the old scoped view; no old callback populates the new scope.

## Exact inherited manuscript boundary

The original chapter repositories do not provide a trusted collaboration `branch_id` manuscript source. B08 does not label base chapters as belonging to a branch. In collaboration mode, chapter catalog, plaintext reading, chapter/version comment creation and chapter packaging fail closed with `BRANCH_SOURCE_UNAVAILABLE` unless a genuine authorized branch reader is supplied by the original source authority. Current branch-scoped task metadata and original review-target references work. The inherited original project-scope validation defect was subsequently repaired in separate shared commit `9014cd3`: current project grants now pass the existing level-correct authorization service, while branch-only access still cannot bypass the stronger project gate. The B08 mounted parity test now requires actual successful original asset read and selected review-package export after a valid project grant, and still verifies cross-branch and revoked-membership denial. This does not fix or bypass the separate collaboration manuscript reader limitation.

Local mode uses actual original chapter versions and read-only text projections. Actual chapter comments appear in the original `/review-threads` authority. Source deletion or loss of original target visibility suppresses related task/index/notice/conflict content; stale-but-still-visible versions are marked STALE and cannot be submitted/closed as current. An old linked source is not silently rebound to a newer version; use its original review flow and a newly linked task.

## Restricted local review package

No chapter or asset is selected by default. The author/reviewer explicitly selects up to 30 chapters and 30 assets (20 MiB total source bytes), reviews the source-bound preview, acknowledges the copy boundary, then generates a local ZIP. The ZIP contains only selected chapter text, selected verified asset bytes and a minimal manifest. It excludes unselected chapters, parent assets, comments, histories, prompts, credentials and local filesystem paths. Paths inside the ZIP are generated safe ordinal names. Preview hashes bind actor, scope, selected versions/digests and minimal manifest; current membership, source revisions and original asset authority are checked again for download. No package is sent to another person or external service.

Both preview/manifest and UI explain: 已下载的永久副本无法通过撤销成员权限远程收回。

## Verification commands

- Isolated backend: `../r2-run.sh python -m pytest tests/test_r5_writer_room_mounted.py tests/test_writer_room_comment_authority_seam.py -q`
- React: `pnpm exec vitest run src/experimental/WriterRoomPanel.test.tsx`
- Types/tokens: `pnpm exec tsc -b --pretty false` and `pnpm run lint`
- Hosted browser only: `pnpm exec playwright test --config playwright.r4.config.ts tests/e2e/r4-writer-room.spec.ts`

The shared mounted fixture now rebinds the original captured comment router service as well as its global alias, so HTTP parity tests exercise the actual comment router rather than a test replacement.

## Local focused receipt (2026-10-05)

The final focused backend invocation above plus `tests/test_r2_creation_workbench.py` passed **39 tests**, with **28 explicitly marked real-PostgreSQL cases skipped** in the File environment. This comprises current B08 behavior, its optional original-comment seam, and unchanged original creation-workbench compatibility; it is not a whole-repository or PostgreSQL result.

`WriterRoomPanel.test.tsx` passed **9 React contract tests**; `tests/uiContracts.test.ts` passed **5 shared shell contracts**. TypeScript and the UI token guard passed. The production frontend build passed with its existing large-chunk warning. Playwright `--list` collected the authored B08 hosted test; listing is not browser execution, visual approval or measured geometry evidence.
