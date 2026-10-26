# Studio V2 asset usage resource guards

## Verified result and scope

The explicitly paginated File GET chain now shares a fresh request budget from
before the original packaged/collaboration middleware through original admission,
identity, asset/consumer reads, reauthorization and final observation. Actual
payload bytes reconcile exactly to the budget in all 13 measured local,
fresh-process, original schema3 and real File collaboration HTTP observations.
The original typed no-parameter interfaces keep their previous unbudgeted
compatibility behavior. This is not a whole-application or PostgreSQL I/O claim.

Oversize files fail before open/read/JSON decoding. Admitted files are read in
64 KiB unbuffered chunks; JSON depth, encoded string/scalar length and token
counts are admitted before the original allocating JSON decoder. The tests
include giant files, fields, numbers, nesting, tiny objects, hidden consumers,
regular-file replacement and denied concurrent Windows write attempts.

Strict opt-in succeeds on initialized original coordination facilities, on both
API aliases and all three query surfaces. Independent tests observe zero
mutation attempts and zero writes, unchanged complete synthetic file/directory
snapshots, and unchanged original coordination registry. A fresh original app
over a copied data path refuses strict mode without initialization, then the
explicit compatibility queries initialize their original facilities; subsequent
strict traversals return all 540 references in six pages on both aliases with
unchanged snapshots. No facilities are secretly precreated for strict queries.

The original no-page contracts, ordering, replay, cross-page change refusals,
permissions and `other_dependencies=UNKNOWN` are retained. Normal creation still
has its original consumer limits; copied saved synthetic records are explicitly
labeled when they exceed the 25-Graph create limit.

## Source freeze and ownership

Baseline branch: `work/asset-usage-query-20261026`.
Baseline commit: `c6ec9529043dd63e4b96a34de558939bf2efd848`.
Baseline tree: `d3d39ce5dbd602f7fabc7fab4357709af61da8f5`.

Verified and published source freeze:
`18731becb0060d3006dd3f5ab8fe0c6cc00c0266`, tree
`a40cc8e58c304cd77072f31ca98703a439c860cc`.
Delivery branch: `work/asset-usage-resource-guards-20261026` in
`1785235376-blip/AI-Novel-Studio`. Later delivery commits archive evidence/docs
only; the app, tests and scripts remain identical to this tested source.

The user explicitly authorized the precise shared-reader/coordinator proposal
after the initial conflict pause. The optional raw-read hooks and original
coordinator capability were then implemented. Frontend, SDK, TaskCenter,
export_job_service, store.py and Hermia's pending store snapshot/duplicate-key
and lifecycle changes were not modified or merged. The existing budget.read
store integration is preserved. See the [reviewed proposal](ASSET_USAGE_SHARED_OWNER_PROPOSAL_20261026.md).

## Budget coverage matrix

| File boundary / work | Admission and cumulative coverage |
| --- | --- |
| Project metadata, original FileRepository get_novel/read_json | 4 MiB per file; raw bytes admitted before JSON; every authorization reread charged |
| File users/memberships, scope/branches and permission assignments | Same raw read/parse admission; original decisions rerun, no permission cache |
| Original project incarnation marker | Original 256 B maximum plus cumulative reads/bytes; no missing-owner minting |
| Scope JSON, directory/consumer discovery and owner content | 4 MiB per file, same request counter, predecode shape limits; original owner validation retained |
| Asset metadata | 1 MiB per file, same request counter and parse admission |
| Original Graph 3–5 normal asset integrity content reader | 25 MiB per binary, admitted against recorded size, shared counter; original digest check retained; schema3 measured |
| Repeated reads, reauthorization, final observations and retries in the request | Same 8192 file-attempt / 256 MiB actual payload budget; rejected attempts and already-read chunks stay charged |
| Consumer/position projection | Original 16 consumers, 256 visited positions per page; 4096 directory rows/collection and validation positions/consumer |
| Output | At most 200 rows and 256 KiB serialized JSON, unchanged response admission |
| Outside coverage | Legacy typed no-page requests, unrelated routes, metadata syscalls, lock wait, hard CPU/RSS bounds, and PostgreSQL database prefetch |

The read-attempt ceiling increased from the old subset's 1024 to 8192 because
all authority rereads now count too; it does not reset at internal phases.
The single shared 256 MiB byte allowance includes metadata and binary content.
Each HTTP request, including replay, starts fresh and does not inherit another
request/user budget. A request-local 64-entry shape cache stores only content
digests, limits and token counts. It never retains decoded documents or
permissions; repeated actual bytes, JSON decodes and token counts still charge.

JSON admission limits are depth 64, encoded string 256 KiB, encoded scalar
1024 B, 100000 structural/scalar/string tokens per document and 64000000 tokens
per request. This lexical pass is not a replacement schema or duplicate-key
parser. Original owner JSON/schema validation still runs.

## Read-only compatibility policy

Use `limit=1..200&strict_read_only=true` on `/studio-graph-usages`,
`/studio-timeline-usages` or `/studio-asset-usages`, under both `/api` and
`/api/v1`. Repeat the option on continuation and replay. Cursor bindings include
the mode, so a compatibility cursor cannot be borrowed by a strict request.

Strict mode requires the existing original process lock registration and lock
file/directory. Windows requires an already populated lock byte. The original
RLock, reentrancy depth, lock ordering and OS lock are retained. Strict mode
opens the existing lock without CREATE/TRUNCATE, never calls mkdir or initializes
a lock byte, and maps missing/invalid/failed lock facilities to 409
`STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE` with no-store and no private path.
Original locks need a writable handle for Windows locking; there are no content
writes or filesystem initialization on the verified strict path. This is an
application-operation guarantee, not a claim that the OS never updates access
metadata internally. Native locking failures and cleanup are tested explicitly.

Original permissions remain in force. A request unable to read necessary
authority because facilities/resources are unavailable can refuse before later
Host/query details are evaluated; it never returns data on that path. Tested
initialized missing/revoked Host requests keep original 401 SESSION_REQUIRED.
Budget failures preserve no-store and return no cached rows or fake empty page.

Compatibility mode still uses the original mkdir/a+b coordinator path. Its first
GET can create an operational lock. Initialized compatibility samples can have
zero writes and equal hashes while still requesting writable lock opens; that
alone is not strict-mode proof. Strict mode does not add coordinator registry
keys. Original cursor issue/expiry/pruning changes the bounded in-memory token
registry; lock depths and request budgets are transient memory state. A final
outer authorization refusal can retain an undelivered cursor until original TTL;
no cursor is returned and the original process cap remains 1024.

## Actual measurements

Complete per-file sizes, stages, reads, bytes and decode counts for cold-process,
first, continuation and repeat requests are in the
[read inventory](evidence/asset-usage-resource-guards-20261026/audit/READ_COST_INVENTORY.md)
and [raw final metrics](evidence/asset-usage-resource-guards-20261026/audit/final-metrics/summary.json).
OS caches were not cleared. Instrumentation adds overhead; timings do not claim
a speed improvement. Each row below is one measured request, not a traversal sum.

| Synthetic request | Actual read calls / bytes / JSON decodes | Charged payload |
| --- | --- | --- |
| 1 Graph / 1 Timeline, first page | 389 / 241066 / 389 | All 241066 B |
| Same, continuation/repeated continuation | 420 / 263740 / 420 | All 263740 B each |
| Original schema3 direct pin, including binary integrity | 250 / 124850 / 249 | All 124850 B; binary 19244 B |
| Real File user/membership/scope/permission chain, first page | 1931 / 2444563 / 1931 | All 2444563 B |

The frozen original baseline measured the same actual payload but charged only
the prior scope/asset-metadata subset. The new counters match actual reads;
they do not imply fewer original authorization checks or lower I/O.

The full 32/540/6 mixed HTTP traversal, with the original instrumented scale
test, read 222626838 B through 7739 file opens / 11000 bounded chunk reads.
First/repeat traversal took 92.269 / 95.657 instrumented seconds respectively;
each separate page stayed within its cooperative allowance. Largest page
Python allocation peaks were 3748438 / 3485948 B; largest response 60234 B.
Both traversals recorded zero actual writes and equal initialized snapshots.
These are measured observations, not a claimed speedup, memory upper bound or
single-request cost for an entire traversal. The raw
[scale metrics](evidence/asset-usage-resource-guards-20261026/coordinator/metrics/summary.json)
retain each page.

The frozen adverse-input run measured a 4194305 B file rejected with **0 read
bytes**, **0 JSON documents** and 2136 B of Python allocation peak. Depth 65 and
100001-token inputs were also rejected before object decoding. An admitted
3932206 B Unicode sample reached **31462998 B** of Python allocation peak;
33333 tiny objects at the admitted token ceiling reached 2512516 B. These are
tracemalloc observations during the stated operation, not worst-case proofs,
process RSS measurements, or hard limits. New-process import/first-use overhead
is reported separately from warm-request allocation peaks.

## Frozen verification and remaining limits

| Group, with overlaps kept separate | Result | Frozen receipt |
| --- | --- | --- |
| Original asset, permission, ownership, production and process-reopen regressions | 192 passed | [regressions](evidence/asset-usage-resource-guards-20261026/coordinator/final-regressions.receipt.json) |
| Preventive reads/parse, native sharing, original authority, strict coordination and mounted refusal cases | 73 passed | [resource guards](evidence/asset-usage-resource-guards-20261026/coordinator/final-resource-guards.receipt.json) |
| Independently authored new counterexamples in separate exact-source worktree | 39 passed | [independent](evidence/asset-usage-resource-guards-20261026/independent/final-independent-resource.receipt.json) |
| Original independent pagination/permissions/lifecycle/mixed-owner cases | 51 passed | [independent legacy](evidence/asset-usage-resource-guards-20261026/independent/final-independent-legacy.receipt.json) |
| Separate frozen File authority and original-main.app cost measurement | 16 passed | [authority/cost](evidence/asset-usage-resource-guards-20261026/audit/audit-final-frozen-authority-costs.receipt.json) |
| Fresh-process real TCP HTTP, both aliases, compatibility and strict 32/540/6 | 1 passed | [loopback](evidence/asset-usage-resource-guards-20261026/coordinator/final-loopback.receipt.json) |
| Original 32/540/6 instrumented mixed HTTP first and repeated traversal | 1 passed | [scale](evidence/asset-usage-resource-guards-20261026/coordinator/final-scale-mixed-measurements.receipt.json) |

Each successful final receipt records the exact source commit/tree, command,
source hashes, raw log hash, clean source state and source_unchanged=true.
The final evidence index also includes the complete mixed-scale measurement.
Overlapping groups are never added as a unique total.

The independent same-size-write counterexample found a real Windows timestamp
hole. Its original failure is retained; assertions were not weakened. The native
reader now denies direct write sharing and rejects reparse/non-disk handles
before reading. A denied competing writer is reported as denied, not as an
executed mutation. Windows can also deny concurrent Path.replace during either
the original Python reader or the new reader; original atomic_write succeeds
after handle release. The incorrect new assumption that replacement must always
succeed during the read is separately preserved as a test issue.

M0's known Windows asset-list cursor failure remains
ASSET_QUERY_CURSOR_UNAVAILABLE. Its failure log/receipt are retained; the
192-case group does not count that owner as fixed or passing. No owner code for
that separate cursor was changed.

Windows File and actual loopback HTTP are verified for the stated groups.
POSIX, real PostgreSQL, browser, real model/GPU and hosted Actions are NOT_RUN.
The POSIX no-follow/nonblocking implementation has not been executed here.
No system/account security setting, package installation, paid quota, real
project, Release, deployment, main update or force push was used.

Overall status remains **PARTIAL** for process RSS hard limits, hard CPU/lock
timeouts, total OS I/O including metadata syscalls, trusted-ancestor races,
strong ABA, durable/cross-worker snapshots and unsupported dependencies. Source
version/digest and finite repeated observations retain their original weaker
meaning. No model call, task dispatch, deletion, repair or relink was added to
the query path.
