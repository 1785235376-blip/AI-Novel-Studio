# B10 existing recovery status presentation

Scope: four frontend paths only, following local media commit `9b027fde2716ff34b37acdf1bd83eb803841ad3c`. The adjacent B02 implementation is independently owned. This slice changes no backend response, reader, permission, stored snapshot, preview digest, original adoption/close rule or retry behavior.

## Privacy and authority audit

The original recovery owner is local-mainline and actor-owned (`offline_sync.py:146–155,188–194`). Its public summary deliberately omits checkpoint, intent, envelope, history and scope (`172–174`); uncertainty stores full checkpoint/intent snapshots only internally (`479–480`). Recovery reads actual chapters through the current authorized reader and omits unavailable results (`530–541`). The API also scrubs raw conflict rows and repeats original host/session/scope checks (`offline_sync_api.py:21–47,125–128`). These omissions must not be reversed in a general record projection.

Current chapter access is not an unrestricted historical-body capability. The original File history owner separately requires verified historical identity, even when a live chapter can be read (`chapter_repository.py:70–75`, `chapter_identity.py:187–193`). Existing chapter identity allocation/reservations fence deleted/reused identities in the original owners; this slice neither changes those modules nor infers a new historical disclosure permission from a current ID. All audit work was read-only; no lifecycle/security test was run.

## What the UI actually says

Only the existing `observations[].state`, chapter ID/version, and already-returned optional withdrawal/selection flags are presented. Raw recovery JSON is replaced by an allowlisted status component; no historical/current body, title, content hash or content length is rendered by it.

- `CHECKPOINT_UNCHANGED`: the complete current read snapshot equals the saved checkpoint: ID, version, archive status, title and document. It is not a write-completion receipt.
- `MATCHES_INTENT_UNCONFIRMED`: “当前内容符合预期，但不能证明本次写入已经执行（也可能原本相同）”. The original predicate compares document content while unarchived, or only archived status for an archive intent. It does not compare title/version. Its existing priority can also cover content that already matched before the request. No invented both-match flag is added.
- `DIVERGED_OR_PARTIAL`: the original predicates found neither a matching intent nor an unchanged checkpoint. The author is directed to the original editor rather than replaying a request.
- Missing/mismatched target observations, unknown response states or withdrawn targets are generic unavailable states. Unbound creates remain explicitly unknown; already-authorized readable candidate IDs/versions may be listed without presenting them as proof of this write.

The comparison is explicitly labeled as the last requested observation. Detailed before/intended manuscript comparison remains intentionally unavailable here. Original `can_adopt`, `retry_allowed` and `preview_digest` remain authoritative and unchanged.

## Retained failure and narrow cache repair

Independent static review found that the original UI retained successful recovery observations and adopt/close controls during a new check and after a denied recheck. It could also install a late reply after the selected record changed. `ui-cache-red.log` preserves **3 failed / 19 filtered** cases: 401 recheck, 403 recheck, and a late reply after withdrawal. Filtered tests are not passes.

The repair clears only recovery state at explicit recheck start. A synchronous record/selection/refresh epoch retires pending results and prevents an old result from returning after a context change. Results install only for the same current request, record ID and version in the same mounted identity. Other unsaved review/selection inputs are untouched. No new recovery transport or writer exists.

Owner verification: **36/36** across `OfflineSyncRecoveryStatus.test.tsx` (25) and unchanged `OfflineSyncPanel.test.tsx` (11), using installed Vitest with `--no-cache --maxWorkers=1 --minWorkers=1`. `ui-owner.log` preserves the initial 33-case green run; `ui-owner-final.log` is the final 36-case selection. Mounted tests retain the exact original adopt/close payload and digest, server-controlled eligibility, no automatic retry/apply, possible no-op, missing/withdrawn/divergent/unchanged/matching and unbound-create states, denied rereads, and late project/record replies. Getter-based fixtures prove the new presenter does not inspect bodies or private fields.

Independent verification also passed **36/36** in 3.08 seconds with the unchanged default test timeouts, `--no-cache`, and one worker; `ui-independent.log` retains the output. The reviewer confirmed all four frozen Git blobs and found no scoped blocker. The exact four reviewed blobs are in `reviewed-source-hashes.json`. Shared type/build/token results will be bound by the adjacent B02 final receipt; they are not claimed complete in this commit. This is mounted component evidence, not new File/PG persistence, browser, lifecycle/security or whole-B10 acceptance. The previous browser socket restriction was not retried. No model, network provider, paid action, installation, push or release occurred.
