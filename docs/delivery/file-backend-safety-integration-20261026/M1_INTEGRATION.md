# M1: fixed published File backend integration

This is an implementation audit, not a final acceptance receipt. Synthetic File
and focused Windows tests are recorded separately from frozen HTTP/process runs.

## Fixed inputs and actual conflict matrix

- A: `856d1ed3341fe0c24df1daff9a8bc1242c260e6c`, tree
  `d6c8057a0595d93eab6d3799787226faf660e834`.
- B: `31b6cb56ba3d2fa08719cf917c2c75ee8f168c8f`, tree
  `fc6f7e5510313e0e334b07efaae99127a895d568`.
- Merge base: `ffe1937911cff32d4ebd4770b350674627501d3a`.
- The integration worktree started at A and uses an ordinary two-parent merge of
  B. Neither `692c2c6` nor `3e027e8` is reapplied: both are already ancestors of B.

Actual `git merge --no-commit --no-ff B` reports three conflicted files, four
textual conflict blocks; main.py merges textually without conflict. The following
matrix is based on the two base-to-tip diffs and actual conflict hunks.

| File / symbols | A responsibility | B responsibility | Integration decision |
| --- | --- | --- | --- |
| experimental/store.py: `_file_read`, new `_file_bytes` / `_file_snapshot`, `transaction`, `capture_committed_collection` | Request byte/shape admission; bounded File-only read path | Unique keys; committed raw snapshot; physical CAS including no-op lease; project identity and row/document lifecycle | Put optional admission at `_file_bytes`; preserve exact bytes and B snapshot pipeline, metadata and scope-to-project lock order |
| repositories/file/identity.py: `_read`, `_write`, `binding_observation` | Budget before JSON decoding | Unique keys; same-file incarnation/user/member nonces; original audit lock | Combine budget and unique-key decoder; retain owner validation/writers/compensation |
| repositories/file/scope.py: scope `_read` / `_write`, authorization `_read` / `_write`, binding methods | Optional authority-read budget | Scope topology and selected grant nonces under original locks | Retain B metadata and writers, admit all rereads, reject duplicate object keys before lifecycle validation |
| main.py: TaskCenter cache middleware and final AssetUsageRequestBudgetMiddleware registration | Fresh outer request budget before original authorization | Exact TaskCenter opt-in no-store wrapper | Preserve both; usage budget remains outermost and narrowly route-scoped |
| repositories/file/mutation_coordinator.py (A only; semantic overlap) | Existing-only strict capability, registered RLock, populated Windows byte, no CREATE/init; normal compatibility creation | B owners reuse workspace_mutation | Keep original A coordinator intact; test B owners against same locks, depth, failure cleanup and strict refusal |
| services/export_job_service.py (B only; semantic overlap) | No prior modification | Original queue serializes cross-instance/process writes; same-file hidden metadata; pure selected-row observation | Preserve B queue and `_mutation`; add optional active budget at `_read_document` and unique-key rejection; do not enroll TaskCenter HTTP in the usage-only budget |

Scope/grant/Export in B used plain `json.loads`. Rejecting duplicate JSON object
keys in these owners is an explicit integration hardening, including unbudgeted
reads; valid documents and public envelopes are unchanged. Export's prior missing,
syntactically malformed JSON, and non-object fallback remains `{}`. Duplicate
keys and invalid reserved lifecycle metadata are refused as `ValueError`, not
silently converted into an empty successful lifecycle observation. Existing
unbound legacy documents remain unbound after ordinary writes.

## Actual owner call chains and read amplification

1. Paged usage GET enters `AssetUsageRequestBudgetMiddleware`, creating a fresh
   ContextVar budget and optional existing-only coordination capability before
   packaged/collaboration middleware. Existing identity/scope/grant/project
   reads, query owner reads, reauthorization and final observations all share it.
   Original no-parameter typed Graph/Timeline behavior remains unchanged.
2. `ExperimentalStore.read` takes the original experimental workspace lock and
   invokes `_file_read -> _file_snapshot -> _file_bytes`. Committed collection
   capture also invokes `_file_snapshot`, then the original project owner lease.
   A transaction reads its initial snapshot and rereads physical bytes at exit,
   even for no-op leases; first creation revalidates project identity and physical
   bytes again. All actual payload attempts now enter the same active budget.
3. Identity uses the existing authorization/audit mutation lease. Scope uses
   `collaboration-scope`; authorization uses its original RLock plus
   `authorization-store`. Original `_write` rereads stay within those locks;
   lifecycle updates never replace the authorization decision.
4. Export writers take `workspace_mutation(root, 'export-jobs')` then the service
   RLock. Reads/get/list/observations keep the B read-only atomic-file behavior;
   observation does not construct a service or recover/submit work. Real startup
   recovery is still an original mutation. Same-file metadata is removed from
   public id-to-job views.
5. TaskCenter keeps its original authorize/capture/real-reader/reauthorize/final
   revalidation chain and bounded safe projection. Supported cursors remain
   File/local semantic_import, File/local exports, and File/collaboration single
   agent_team with the previously validated no-source window. Mixed sources,
   collaboration exports and unsupported authorities remain explicit refusals.

## Plan and evidence discipline

M2 compatible readers and preventive byte/shape admission; M3 original writers,
lock ordering/reentrancy and lifecycle metadata; M4 query assembly and original
authorization; M5 integration regressions; subsequent root-owned frozen-copy
HTTP/process/independent verification and publication. The merge is committed
only after the semantic core and focused tests agree. Later corrections are
separate reviewable commits with `[skip ci]`.

Repository AGENTS.md and A resource-guard/shared-owner/evidence documents plus B
local lifecycle, collaboration rebuild, Export owner and local Export cursor
stable-slice documents were read before edits. GraphFlow was attempted first in
this exact worktree. Available MCP tools are only gf_read/gf_macro/gf_exec/gf_edit;
the requested legacy context/plan/index tools are unavailable. gf_read returned
mostly irrelevant frontend anchors; these were not used for implementation.
gf_macro brief did not complete promptly and was stopped. Explicit file/symbol
diffs above replace that unavailable planning output; no token-saving metric or
successful index refresh is fabricated.

No stronger guarantee is implied for complete ABA, invisible insert/remove
events, cross-owner atomic snapshots, persistent/cross-worker cursors, hard
CPU/RSS/lock deadlines, backup replay or power-loss durability. No frontend, SDK,
main/BOT/A/B branch, package installation, security setting, provider, paid API or
hosted Actions change is part of this work.
