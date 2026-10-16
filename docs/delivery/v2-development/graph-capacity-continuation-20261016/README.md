# Original graph capacity and independent draft preparation

## Original owner contract

The graph service adds optional read-only capacity metadata to an editable graph view. `history_used` and `history_limit` come from the original stored row and its existing history policy (20 for text/model graphs, 80 for media/image/video graphs). `record_bytes` is the canonical UTF-8 size of that exact stored record, including its history, and `record_limit_bytes` remains 2000000. The decorated public view is not counted or persisted. Unavailable-reference views omit this metadata. No authorization, store, mutation route or capacity limit is changed.

The client validates the optional metadata; absence is shown as unknown rather than zero. The UI reports current usage only. It does not estimate how many notes or saves remain: each save appends a snapshot and the original scope/collection caps also apply. A full known history budget leaves the author draft editable and offers an explicit independent draft action. Existing known atomic quota refusals receive clear messages and keep the draft editable. Unknown/conflicting writes retain the original fail-closed recovery behavior.

## Explicit full-definition preparation

The author confirms the exact current graph ID/version and draft, then chooses “prepare independent new graph.” This is a local no-write action. The original client validates the entire definition, including nodes/edges, notes, groups, comments, view/camera and versioned source references. The controller clears the saved base, selected run/location, selection and undo state; it allocates one fresh original create request ID. The original Save action is the only write. It uses the same create endpoint, validation, capacity check and unknown-create retry/local recovery path as an ordinary new graph.

The original graph and all its history stay unchanged. The new graph has its own ID and starts at version 1 with no old execution or review receipts. Original graph ID/title/version and last-read source states are visible as session context, not a new persisted owner. Source references are not rebound, upgraded or approved; STALE stays explicit, and the original create service can refuse changed sources. There is no automatic save, clone, preflight, run or model call.

Preparation rechecks active editability, current identity, synchronous busy state, pending editor inputs and draft-bound consent at the action. It is unavailable while a write is unknown. The original parent identity retirement and new-draft recovery fences remain authoritative. Denial/discard/adoption clears the new session context. An uncertain text-only new draft retains its exact `base=null`, definition and request ID through the existing local recovery format and a service-owner check; this does not expand local recovery to media/pinned graphs.

## Development evidence

- Initial frontend checks reached 134 passes and one failure caused by using a test matcher unsupported by the installed Vitest version. TypeScript identified the same matcher issue. A second run began against that old test source and is retained. The assertion was split into the existing call-count and exact-arguments matchers, retaining both requirements.
- The corrected mounted capacity, client and existing recovery selection passed **146 tests / 3 files**. The new mounted suite covers exact metadata/unknown fallback, draft-bound consent, no-write preparation, full-definition Save, original navigation, known quota refusals, failed create retention, unknown create remount/retry with one exact request, synchronous identity/busy fences and unchanged STALE pins.
- Initial ordinary File receipt `../graph-capacity-development.json`: **4 passed / 4 PostgreSQL cases deselected**. Real File checks establish exact 20/80 metadata, full 1000-note/pinned definition create/reopen/idempotency, unchanged original row and original source-change refusal. This first selection also reused the existing 20-history atomic refusal regression.
- A dedicated final File case additionally reaches v21/history20, proves the next save leaves the original record byte-for-byte unchanged, then explicitly creates and reopens an independent 1000-note draft containing the otherwise-unsaved edit.

Final independent, stable-source File, type/build and token receipts are recorded below after they complete. Initial logs remain here rather than being replaced.

## Evidence boundaries

All persistence checks are the real original File owner with synthetic authored content; frontend checks are component/transport tests. Browser visual/performance, PostgreSQL, live models and whole-V2 acceptance are not established. The prior own-cloud browser socket restriction was not retried. No blocked lifecycle/security candidate, paid models, dependency installation, hosted CI or publication was run. Production prompt-adoption writes remain disabled.

## Final stable-source verification

- Independent capacity/client/local-draft review: **141 passed / 3 files**, exit 0. Exact selection: `StudioGraphCapacityContinuation.test.tsx`, `studioGraphClient.test.ts`, `studioGraphLocalDraft.test.ts`. No scoped static blocker was found. This is distinct from the development 146-case selection, which used `StudioGraphDraftRecovery.test.tsx` instead of the six-case local-draft unit file.
- Existing mounted workspace/production/image/video/run regressions: **64 passed / 5 files**, exit 0, default timeouts and one worker. The full human-review→pin→reopen case passed in 4011 ms. See `mounted-adjacent.log`; this run was performed after the type/build and File load had cleared.
- Final ordinary File selection: **91 passed / 10 PostgreSQL cases deselected**, exit 0. `../graph-capacity-file-final.json` reports `sources_changed_during_check=false` and exact hashes. It includes the new quota→independent-create/reopen case, 20/80 metadata, complete pinned-definition restart/reopen/idempotency/source-change checks, original presentation contracts and selected original create/CAS/failure/copy/reopen tests. No excluded lifecycle/security tests were selected.
- TypeScript `--noEmit`, Vite production build and UI token guard **PASS (52 files)**. Existing bundle-size advisories remain. Logs are retained here.
- Exact eight changed source/test SHA256 values are in `source-sha256.json`. All match after verification. These sources were also present during the separate PUBLIC worker's final offline wheel capture; packaging's local commit is `1a55491a79a0adf045f2f34712b06caebc3b33eb`, with the capacity changes intentionally committed separately afterward. No wheel publication or installation occurred.
