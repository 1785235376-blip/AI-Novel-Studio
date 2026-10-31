# Actual read-chain inventory and resource boundaries

Scope: saved Graph/Timeline **direct** asset references in a temporary synthetic
File store, through the original `app.main:app` HTTP assembly. Both `/api` and
`/api/v1` mount the same owner routes. This inventory describes original reader
symbols, the fixed baseline, and the request-budget integration on the resource
guards branch. Final acceptance requires the frozen receipts named by the main
evidence index; exploratory runs are explicitly distinguished below.

## Original call path retained

1. `AssetUsageRequestBudgetMiddleware`, narrowly matched to the three paged
   saved-usage GET routes and their aliases, establishes the fresh budget before
   the original outer middleware. The original `app/main.py` middleware resolves
   an opaque trusted/packaged session where required.
   `resolve_discovery_authority` verifies direct local Host provenance,
   origin, original resolver binding generation and session identity. Its normal
   request resolution is in-memory (`TrustedSessionResolver.resolve`,
   `binding_generation`; packaged `LocalSessionBootstrap.resolve_issued_session`).
   It does not read a project/identity JSON file or issue a session during GET.
2. `app/creative/graph_api.py::asset_usages` and `saved_asset_usages`, or
   `production_execution_api.py::asset_usages`, enter the existing-owner policy
   and reuse the outer request-local budget before their original invokers. Typed
   routes retain their unpaged no-query behavior without opting into this new
   budget. Combined usage always requires valid explicit pagination.
3. `workspace_api.py::invoke/access` calls
   `experimental.api.authorize -> api._workbench_authorize`. Local authority
   calls `NovelService.get -> FileNovelRepository.get -> FileRepository.get_novel
   -> repository.read_json(novel.json)` under the existing project lifecycle
   guard. Collaboration authority calls `_authorize_novel_project ->
   _authorize_project_domain`: original session, project/workspace and branch
   scope, active user/membership, and original permission/role resolution. The
   wrapper captures `CreativeProjectStore.incarnation` and repeats all authority
   and incarnation checks through its `guard`.
4. Graph routes keep `graph_invoke(..., target=('list',), inspection_host=True)`.
   Its `host_required()` reads the current saved scope to preserve protected
   schema classification; it does not use a stale classification cache. Timeline
   routes keep `create_production_invoker`. The combined route composes both
   original invokers for selected sources and checks actor/scope agreement.
   Selecting one source retains only that source's original invocation needs.
5. `asset_usages._source` reauthorizes, takes the original asset -> project
   leases, and calls `workspace._row -> AssetLibraryService.get/_load`. It rejects
   private generation candidates as reference inputs and returns only the
   original bounded asset pin. It repeats this source read during both final
   verification observations.
6. `paged_usages` captures the original incarnation and cursor binding, then
   discovers selected actor-visible saved consumers through
   `CreativeGraphService.usage_directory` and/or
   `ProductionExecutionService.timeline_usage_directory`. Their original
   context/base checks read the novel and incarnation again. File scope reads
   pass through `CreativeProjectStore.read -> ExperimentalStore.read ->
   _file_read`. The physical shared scope document includes other data, but only
   selected, owned and visible consumers enter the returned directory/fingerprint.
7. Each selected owner is fetched through original `usage_get` or
   `timeline_usage_get`, with the existing identity, schema, digest, reference,
   incarnation and redaction validation. Graph schemas 6/7 keep their original
   exclusion. Supported Graph schemas 3/4/5 invoke
   `GraphAssetInputs.states -> read -> _read -> assets.content ->
   AssetLibraryService._verified_content`: this **also reads and hashes binary
   asset contents**. These are real read costs, not merely response bytes.
   Timeline's original saved-owner projection/normalizer is retained.
8. Before cursor issue, after issue and before return, original guards, source
   metadata and selected saved-owner discovery are repeated. An error path also
   reauthorizes before returning a private error. Every physical reread shares
   the same context budget. A cursor replay starts a new request budget and
   repeats observation; it cannot borrow cached private results or permissions.
   Cursor registry operations themselves are bounded, process-local memory.

## File reads and JSON decodes: baseline versus guarded pagination

| Original symbol / physical input | Baseline admission | Guarded paginated File request |
| --- | --- | --- |
| `repository.read_json`, project `novel.json` | Entire `read_text` then `json.loads`; no usage byte/count admission | Same original decoder/default behavior, now optional `budget.read` before decode; every reread charged |
| `creative.project_store._read_marker`, `creative_project_v2.json` | Separate original <=256-byte marker admission, reads up to257 bytes to detect overflow; not cumulative | `budget.read(path,256)` cumulative before original `json.loads`; original no-budget path preserved |
| `FileIdentityRepository._read`, `identity.json` | Entire shared document decoded for each user/membership resolution | Optional cumulative bounded input/preflight before original decode |
| `FileScopeRepository._read`, `collaboration_scope.json` | Entire shared document decoded repeatedly for original parent/branch checks | Optional cumulative bounded input/preflight before original decode |
| `FileAuthorizationRepository._read`, `authorization.json` | Entire shared grants/roles/audit document decoded | Optional cumulative bounded input/preflight before original decode; class is in **file/scope.py**, not a separate authorization.py |
| `ExperimentalStore._file_read`, hashed `experimental_v1/*.json` | Existing `budget.read` hook for the entire physical scope document | Same hook hardened in budget component; store.py unchanged in this work |
| `AssetLibraryService._load`, `assets/*.json` | Existing usage-budget input, per-file <=1MiB | Same hook, cumulative/preventive shape admission before original decode |
| `AssetLibraryService._verified_content`, `assets/*.bin` | Usage budget absent; separate asset-list budget could apply, then original binary read/hash | Ordinary usage Graph3–5 path uses `read_binary` under the same cumulative usage budget, followed by original size/hash check |
| Optional `AssetLibraryService._verified_bounded_content(max_bytes=...)` native path | Separate native bounded reader contract | Separate; ordinary direct-reference usage validation does not pass `max_bytes` and does not enter it |
| Host/session lookup and cursor registry | In-memory original owners | No file input; no replacement authority or permission cache |
| Operational coordinator lock files | Original mkdir and `a+b`; Windows may initialize one byte | Compatibility preserves original behavior; strict uses owner-reviewed existing facilities, see separate strict acceptance receipts |

All JSON inputs above remain whole-document decodes after preventive encoded
byte and shape admission; no streaming JSON, constant resident memory, process
RSS cap or hard CPU isolation is claimed. Guarded JSON has explicit encoded
bytes, nesting, string, scalar-token, object/token and cumulative token limits.
Physical read bytes/counts and binary reads are charged before/while reading.
The deadline is checked at boundaries/within bounded parsing; it is not an OS
preemption deadline. PostgreSQL prefetch remains unsupported for explicit
pagination; no real PostgreSQL database was exercised by this audit.

The upper bound covers the identified original File request chain **only when
the usage context is active**. Original unpaged requests, unrelated APIs,
application imports/startup, model execution, external processes and optional
native content APIs are separate contracts. Any newly added reader must opt
into the budget; a ContextVar alone cannot intercept arbitrary filesystem I/O.
The read-count/byte meter measures payload reads, not every `stat`, `lstat`,
`fstat`, existence check, path resolution, kernel-cache read or storage-device
operation. Those metadata operations and original lock waits do not become a
hard OS I/O or wall-clock bound. PostgreSQL's original authority can execute
database reads before the later unsupported pagination admission; no File input
bound is extended to those database reads.

## Frozen baseline measurements

The product baseline is `c6ec9529043dd63e4b96a34de558939bf2efd848`, tree
`d3d39ce5dbd602f7fabc7fab4357709af61da8f5`. The detached measurement worktree
contains only the three new instrumentation files above this baseline. Its
`app` diff from the baseline was empty. Exact harness commit/tree and SHA-256
values are in `baseline-harness-provenance.json`; the strict archived run is
`audit-final-baseline-costs.receipt.json` (three distinct cost scenarios; final
harness files byte-identical to the candidate instrumentation).
Earlier single-scenario frozen receipts remain valid, overlapping measurements;
their pass counts are not summed.

The initialized synthetic sample has one original saved Graph with three pins
and one saved Timeline with one pin. The meter wraps original reads/decode
functions transparently; it does not replace authorization decisions. It labels
the query checkpoint, nested original read stage, synthetic relative file,
actual bytes returned by reads, observed physical file sizes, JSON decoder
calls/input bytes, and whether that physical read actually came through the
usage budget reader. A fresh interpreter uses the original assembly; imports
and application startup are outside its per-request meter. OS caches were never
cleared or represented as cold.

| Baseline phase | Actual read calls | Actual bytes | JSON decodes | mkdir attempts / write-capable lock opens | Actual file writes / created directories |
| --- | ---: | ---: | ---: | ---: | ---: |
| First page | 389 | 241066 | 389 | 368 /368 | 0 /0 |
| Continuation page | 420 | 263740 | 420 | 398 /398 | 0 /0 |
| Replayed continuation | 420 | 263740 | 420 | 398 /398 | 0 /0 |
| Repeated first page | 389 | 241066 | 389 | 368 /368 | 0 /0 |

These counts/bytes match in the new-process and initialized-process measurements;
timings/allocations differ and are recorded separately in raw JSON. First-page
breakdown: marker187 reads x84 bytes; project metadata147 x232; scope49 x3802;
asset metadata6 x826. Only the last two categories (55 reads,191254 bytes)
consulted the baseline usage budget. Thus the baseline measured request performs
334 additional physical reads and49812 additional bytes outside that budget.
This is why counting projected results or managed scope reads did not establish
an end-to-end budget.

The additional real File collaboration sample has four saved Graph pins and a
real in-memory packaged Host bootstrap. Every observed request (first,
continuation, repeated continuation and repeated first) performs1931 physical
reads /2444563 bytes /1931 JSON decodes at baseline. Of those,1536 shared
scope/identity/authorization reads consume2227840 bytes outside the original
usage budget; the observed shared file sizes are1052,1455 and2206 bytes. Only57
scope/asset-metadata reads /165983 bytes were in that baseline budget. The
instrumentation is over real File authority decisions; it is not evidence for
PostgreSQL or a launched packaged application.

The separate supported saved Graph schema3 sample reads one19244-byte asset
binary during original reference integrity validation. The baseline first
request performs250 reads /124850 bytes /249 JSON decodes. The binary is read
and hashed but is outside the baseline usage budget; only39 reads /74646 bytes
are charged there. This demonstrates the otherwise easy-to-miss binary input
path using the original HTTP owner, with no model or task dispatch. The first
exploratory schema3 probe omitted two dependencies of the original execution
feature gate and was correctly refused; the corrected probe explicitly enables
all required original flags and retains the success assertion.

Raw per-phase/per-file/per-stage records and the aggregation are in
`baseline-metrics/`. The earlier `audit-baseline-costs*` runs were exploratory
while other units were editing product source: their receipts correctly have
`source_unchanged_during_run=false`. The first failed run also has a meter-test
assumption error (`read_calls > json_decodes` for an all-JSON schema1 sample);
the corrected assertion accepts exact equality and additional bounded chunks.
These runs are not frozen acceptance, and are not added to passing totals.

The original32-consumer/540-reference/six-page baseline evidence remains in the
previous delivery directory. Those fixtures copy structurally valid saved
synthetic owners above the normal creation cap; this does not remove the normal
creation API's consumer limit. The main evidence index carries the new frozen
scale regression and distinguishes it from this small instrumentation sample.

## Final frozen read-cost and authority verification

The final audit ran in a new detached worktree at product source
`18731becb0060d3006dd3f5ab8fe0c6cc00c0266`, tree
`a40cc8e58c304cd77072f31ca98703a439c860cc`. The archived
`audit-final-frozen-authority-costs.receipt.json` records16 passed,3 warnings,
`source_unchanged_during_run=true`, and a clean source worktree. Every source hash
and the output hash was rechecked after completion. `final-metrics-provenance.json`
binds the raw records and owned source files to that freeze.

The same instrumentation and synthetic sample shapes were used at the baseline
and candidate. Read counts/bytes remain the same; **coverage** changes:

| Actual request | Actual read calls /bytes | Baseline charged calls /bytes | Frozen candidate charged calls /bytes |
| --- | ---: | ---: | ---: |
| Local first page, initialized or new process | 389 /241066 | 55 /191254 | 389 /241066 |
| Local continuation, including replay | 420 /263740 | 60 /210264 | 420 /263740 |
| Real File collaboration authority, each observed page/replay | 1931 /2444563 | 57 /165983 | 1931 /2444563 |
| Original saved schema3 binary input, first page | 250 /124850 | 39 /74646 | 250 /124850 |

All13 measured HTTP requests have exactly one fresh request budget; every
observed payload read travels through the guarded reader, and actual bytes
equal that budget's charged bytes exactly. This includes the new interpreter,
native Windows reader, actual File scope/user/membership/grant owners and the
19244-byte binary integrity read. JSON decoder counts remain389/420/1931 and249
respectively. These small files each fit one physical read; the file-admission
attempt counter is separate from chunk read-call counts on larger inputs.

The largest instrumented Python allocation peak in the initialized local sample
is615809 bytes; the new-process first page reports27979751 bytes, and subsequent
pages are579273 bytes or less. The real File authority sample peaks at606962
bytes and the schema3 sample at413316 bytes. These are measured `tracemalloc`
allocations during instrumented requests, including any lazy request-time work;
they are not process RSS, an RSS upper bound, or proof of a latency improvement.
Raw timings, peaks, physical file sizes and read/decode stages are retained per
request in `final-metrics/`, rather than added across overlapping scenarios.

All measured compatibility-mode requests performed zero actual file-write calls
and created zero directories, with identical complete synthetic file snapshots.
They still used original write-capable coordinator opens/mkdir attempts. This
cost group does not claim compatibility mode is strict; successful strict-mode
filesystem-operation evidence is a separate frozen owner/loopback group.

The13 additional authority-hook tests preserve each of the five original reader
defaults, reject encoded input before `json.loads`, accumulate repeated reads
within one request, reset the next budget, refuse deterministic project-metadata
growth after initial admission with409/no-store, and retain missing Host401
precedence on both aliases. These13 tests and the three cost tests form this
16-pass group; overlapping broader regression groups must not be summed into a
purported unique test count.

## Strict-read ownership assessment

At the baseline `mutation_coordinator.workspace_mutation` unconditionally called
`mkdir(exist_ok=True)` and opened `a+b`; `_lock_file` wrote `b'0'` for empty
Windows locks. `existing_owner_only` prevented creation of the project marker,
but did not make the coordinator read-only. A file-hash equality check on a warm
fixture did not prove no write-capable calls. A preflight existence check alone
also cannot prevent a later create race. Replacing or skipping original locks,
or precreating them from GET, would weaken the lifecycle/concurrency contract.

The exact reviewed shared-owner change is in
`../../../ASSET_USAGE_SHARED_OWNER_PROPOSAL_20261026.md`. The user subsequently
authorized that precise integration. The coordinator owner, rather than this
audit unit, supplies strict existing-only handles and the same original locks,
reentrancy and ordering. The acceptance record must show a real successful page
with existing original facilities and no filesystem write calls, and a stable
private refusal when facilities are absent. Refusing every strict request is
not acceptance. No new initialization route, hidden precreate, system policy or
security-setting change is part of the proposal.

Registry snapshots distinguish the allowed process-local cursor registry from
the coordinator's existing lock registry. Compatibility can initialize an
original operational lock; strict must not. Scope/asset/project business files,
directories, lock contents and temporary files require separate comparisons.

## Privacy and remaining guarantees

The meter is synthetic evidence only. It never emits paths, read counts, file
sizes, private owner IDs, hidden consumers, permission activity or per-phase
diagnostics to ordinary callers. Physical-container admission can refuse because
shared input is too large, using one fixed sanitized resource failure; it does
not identify a hidden consumer. Original no-store behavior remains in force.

Version/digest equality is finite repeated observation, not strong ABA
protection. Tokens remain process-local, not a durable/cross-worker snapshot.
Other dependencies stay UNKNOWN. Process RSS hard isolation, hard CPU
preemption, POSIX execution, real PostgreSQL, browser, GPU/model execution and
hosted Actions are separate evidence boundaries; this audit does not claim they
ran or passed.
