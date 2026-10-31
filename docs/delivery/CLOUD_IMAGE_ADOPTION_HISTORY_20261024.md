# Browser-node image adoption history and explicit restoration

The original image node now retains local adoption history, compares the current and historical pins, and can explicitly restore a still-valid older adoption. Restoration appends a new local event; the original Job and Asset stay authoritative. No task, provider, server approval or shared canvas is written by restoration.

## Source receipt

- Published starting point: `7eb5e9d21d74bb2f3e75d57c975b7ed80c2c1bf6`.
- Fixed application/tests: `97094d0af8d4f0d74f24d337e38ed93957313dd0`; tree `b2ac32da16bb31b4ea73c223f0222df3926ecae9`.
- Only cloud/GitHub-derived code is used. Main, the prior source histories, backend implementation, asset-query line, dependency locks and external frontend layout remain unchanged.

## Using the history

The original node shows its current task ID, asset ID, observed asset version, content digest and client Job-observation digest. Each pinned historical entry shows the corresponding values and names their differences from current. These are comparisons of **unverified browser records**, not statements that the source remains readable or approved now.

Selecting an entry performs no request and does not switch the current binding. **读取所选历史原任务** explicitly reads the old original-owner job. A valid approved source opens the existing candidate view; it neither previews the image automatically nor adopts it. The user separately previews the exact asset, waits for a successful current-image load and uses **准备历史恢复核对**. A new checkbox and **明确恢复此浏览器原节点** are required for this operation.

Preparation and confirmation revalidate the old job observation, exact project/branch/source task, real asset version and digest, provider/model, bounded bytes/MIME/size and current write authority. Confirmation downloads and hashes the bytes again and checks the original metadata/job again. All four saved pin fields must match the historical entry exactly. A newer metadata version, even with identical bytes, is not silently substituted for the saved version. Deleted, unreadable, changed or revoked sources fail closed. Network-only pending candidates gain no new content or approval path.

On success the existing node/task binding points to the historical task and pin, with a new restore event referring to the selected old event. The preceding current state remains in the previous journal entry; the old source entry remains intact. Server job statuses and assets are unchanged. For example, old A → queue B → adopt B → restore A preserves those previous observations and adds a new current A. It does not rewind server state or recreate a deleted asset.

Reopening displays the saved records and reads current original-owner status. It restores no loaded-image acknowledgement, checked box or pending restore request. A current task/pin identical to the selected target cannot be restored again as a no-op. Duplicate clicks share the existing synchronous guard and full-record comparison.

## Same binding, bounded local journal

The existing owner/node storage key remains in use. New successful writes use schema 2 with local `revision` and ordered `history`. Each entry contains an event ID, local revision, operation, task ID, optional four-field adoption pin and, for restoration, a backward `sourceEventId`. Operations are `queue`, `adopt`, `restore` and first-observation `import`. Entries describe the state **after** each local write; the preceding entry supplies the state before it. No separate before field or historical timestamp is invented. Revision is local observation/write order, not server task order or server canvas version.

Valid old schema-1 records remain readable without a write on open. Their first new successful mutation imports the one current state they actually retain and then appends the new event. A legacy record has no recoverable list of previously overwritten associations; the UI does not manufacture it or claim older history never existed.

The reader validates the complete journal: exact shapes, unique event IDs, contiguous revisions, head equal to the last full task/pin state and valid earlier restore references. The writer compares the entire expected record, checks the current owner/node/source fence, appends and verifies readback. This fences ordinary queue/pin A/B/A changes as well as head changes. No prompts, result URIs, object URLs, tokens or persisted human-confirmation flags are added.

There are at most **32 entries**, including queue and import observations. At capacity, writes are refused and all existing entries remain; nothing is silently pruned. Malformed, unknown, oversized or unreadable existing records are preserved and cannot be overwritten as if absent. The UI distinguishes these from a missing binding. Storage failure means the write was not confirmed, not proof of rollback. Existing queue creation and browser binding are separate: if a server task is created while its browser association cannot be saved, the original queue retains that task and the existing warning provides its actual ID; the client does not automatically create another.

Single-key JSON replacement keeps the recorded head and journal together. Compare-then-write/readback is **not** a cross-tab transaction or tamper-proof audit trail. Preservation applies to this implementation's successful mutations; an older loaded client, manual storage changes, browser-data clearing or storage loss can still remove browser history. Repeated Job/Asset/permission reads do not form a cross-owner server transaction or continuous permission lease. Future use must authorize and re-read through the original owners.

## Readiness and retirement

History controls mount after the initial task read completes, so an enabled choice cannot refer to the pre-read sequence. The initial status read now has the same 15-second abortable deadline as other candidate reads. Preview and history controls initialize and retire their identity/source guards in layout effects before painting, so a committed enabled control does not silently discard its first explicit interaction while awaiting passive initialization. After a failed or timed-out initial read, only the unverified local history becomes available; another source read still needs a click. Late responses cannot mark the failed initial read successful, recreate a candidate or retry automatically.

API/Host epochs, current project/node, source-prompt revisions, full current binding, parent read sequence, selected history entry and a monotonic selection sequence all fence requests and confirmation. Selecting A/B/A, changing scope or refreshing retires the old preview and acknowledgement. Historical display binding and expected-current write binding are separate, so selecting or reading A cannot overwrite current B before confirmation. Existing exact-image `src/currentSrc`, successful load and byte guards remain in force.

## Validation

| Check | Actual result |
| --- | --- |
| Original File/API selection | **36 passed**, 3 existing warnings, 6.90s at `f3db90a032c674d2b042090f2ccd570598fff033` |
| Final bounded frontend regression | **564 passed**, 26 files, one worker, 32.32s at the fixed source |
| Standard `corepack pnpm build` | **PASS**, `tsc -b && vite build`; process 53.634s, Vite 9.41s at the fixed source |
| Independent source, owner, migration and public-content review | **PASS** at the fixed source; no new owner or server write |

File/API coverage comprises queue 4, candidate protocol 3, explicit execution 9, prior asset readback 15 and new cross-history readback 5. The new cases use two synthetic approved original jobs/assets and known bytes. They reopen the real File owners, prove old pins remain readable, distinguish asset identity even for equal digests, observe old metadata/delete/restore invalidation while current remains unchanged, and recheck real revoked membership/read grants on each route. They do not restore a browser binding or perform an approval. No backend/API or Python-test byte changes follow this run; carry-forward is recorded explicitly rather than claiming another run.

The final frontend selection includes the previous 503 cases, 35 added binding/history cases, 25 independent history component cases and one additional original File/API readiness case, for an actual collection of 564. Coverage includes legacy import and explicit restoration, preserved prefixes and backrefs, no-op/capacity/corrupt records, current versus history comparison, exact pin changes, permission withdrawal, owner/project/node/client/Host/prompt/selection A/B/A, late replies, full current-record conflicts, duplicates, storage refusal and reopen. Fixtures use HTTP replay, known bytes and explicit software load events; they do not prove browser decoding, human review or actual provider output. The initial-read deadline case invokes the production 15,000ms callback under test and checks the original AbortSignal, no automatic retry and retirement of a late response; it is not a 15-second wall-clock wait.

Earlier failed verification is retained in the cloud receipts. Initial `f3db90a` had 20 frontend failures: 19 exposed the real history mount/read-sequence readiness issue, and one expected the old empty-state message for a forged record instead of the new preserved-record diagnostic. A targeted `9b6a240` run then passed 48/50, leaving two synchronous message assertions that needed to await the new read-complete mount; those checks were corrected without weakening their behavior assertions. A subsequent run retained a failure in the pre-existing inline-candidate fixture; a separately controlled first-commit interaction reproduced a real guard-initialization window. A committed enabled preview control was clicked while mounted=false and all other identity guards were valid. Moving mount/retirement before paint closed that controlled counterexample; it does not prove the original grouped failure had exactly that trace. The original fixture waits/assertions were retained, and both those cases pass in the final complete selection. A matching history-choice first-commit case also passes and checks zero network and unchanged storage; a separate old-source negative control was not run for that history case. A new-file trailing space was also found by the staged diff check and fixed, rather than reported as a clean initial check.

Exact commands, hashes, pre/post source receipts, raw failure logs and final results remain cloud-only under the round9 records. Raw logs, temporary stores, dependencies and build outputs are excluded from Git. GitHub HEAD and CI are queried after the normal work-branch push; local verification is not CI execution.

Real PostgreSQL, real model/GPU/paid calls, native Windows and browser/geometry/visual acceptance remain **NOT_RUN**. The prior media safety and Chromium sandbox restrictions were not retried or bypassed. The existing asset-query cursor's Windows limitation is unchanged. This is browser history restoration, not shared server canvas restore, pending-to-approved review, deleted-media recovery or recovery of unique local source/history.
