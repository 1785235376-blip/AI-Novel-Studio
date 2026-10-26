# Saved asset reference query delivery — 2026-10-26

Status: **PARTIAL — scoped pagination and finite consistency verified; full
request IO/CPU/process-memory bounds remain unimplemented.** Scope is saved
Graph and Timeline **direct** asset pins. This is not a complete dependency
system or an authorization to delete assets.

The 32-consumer synthetic saved-state fixture returned all **540 positions in
six pages**, without duplicate or missing positions. Independently authored
mixed-source tests also cover 26 consumers and equal IDs in the two owners.
Changes observed during or between reads refuse continuation. Unobserved
transient changes and strong ABA remain outside the guarantee. Other
dependencies remain **UNKNOWN**. Final receipts are linked below.

The fixed GitHub-aligned product baseline is
`8ea45399816bf74783c4f01247b440ce4a82b5ba`, tree
`3372d4742f0de3f5ec96f2f7c3b505f3d968a107`, branch
`work/studio-backend-integration-20261026`. The delivery branch is
`work/asset-usage-query-20261026`; its separate worktree is
`D:\PoemSeed\Worktrees\asset-usage-query-20261026`.

## Ownership and execution

Three explicitly requested `gpt-6-astra` units own core implementation,
compatibility/performance and independently authored counterexamples. The latter
two use separate worktrees. The coordinator owns assembly wiring, source-bound
receipt recording and this delivery report. The implementation unit is the sole
editor of shared query/read-budget core files. The assembly edit only supplies
the existing Production service to the query router. Frontend/SDK, Production
execution/adoption behavior, TaskCenter collaboration cursors and audio version
history are outside this change.

Windows local process creation, Python 3.11.9 and the existing isolated runner
worked. Initial M0 original asset query regression: 37 passed, 3 warnings. No
`setup refresh had errors` occurred. The runner isolates HOME/USERPROFILE,
APPDATA/LOCALAPPDATA, XDG, PROJECT_ROOT, File data and temporary directories,
removes provider/database credential inputs and blocks external networking.

GraphFlow's connected interface only exposes `gf_read`, `gf_edit`, `gf_exec` and
`gf_macro`. `gf_read` was used before source exploration and for current slices.
The requested legacy context/plan/index tools are unavailable; no index refresh
or planning-tool execution is claimed. Some old index test anchors are absent
from the fixed commit. The specialized old Graph/Timeline usage suites are
MISSING from that commit, rather than treated as passing. New tests use only
this GitHub-aligned source and synthetic temporary File data.

## Interface and compatibility

All paths below use `/api/novels/{nid}/experimental/production/assets/{aid}`;
the original app also mounts the corresponding `/api/v1` aliases.

| Suffix | Query | Behavior |
| --- | --- | --- |
| `/studio-graph-usages` | no parameters | Original response, 25-owner refusal and 200-row truncation retained |
| `/studio-timeline-usages` | no parameters | Original response and limits retained |
| Either original suffix | `limit=1..200`, optional `cursor`, `state=CURRENT\|STALE` | Explicit paged observation for that owner |
| `/studio-asset-usages` | `limit=1..200`, optional `cursor`, `state`, `sources=graph\|timeline\|graph,timeline` | Unified selected-source observation; both sources by default |

Every continuation repeats the same selection and limit. Opaque cursors are
process-local, expire after 300 seconds, and are invalid after process restart or
worker change. Their binding includes actor, project, original project
incarnation, scope/branch, asset, source selection, state filter and page limit.
The saved source fingerprint includes the current asset version/digest.
Duplicate fields, unknown parameters, invalid limits and overlong query/token
values are rejected after original Host/session authorization. Errors are
sanitized; no body, prompt, cursor or private filesystem path is returned.

Graph inspection retains `graph_invoke`, `inspection_host=True`, original
session/scope/incarnation checks and `existing_owner_only`. The mixed route
composes the original Graph and Production invokers, checks their actor/scope
agreement and retains both guards. A single selected source does not acquire
the other source's invocation requirements. Graph schemas 6 and 7 retain the
original list exclusion, explicitly named in the paged coverage report.
The typed routes preserve original 404 for a missing incarnation; the new
combined route uses its sanitized 409. Tested Host revocation is exactly
401 `SESSION_REQUIRED`. Invalid typed pagination uses
`STUDIO_GRAPH_USAGE_UNAVAILABLE` / `STUDIO_TIMELINE_USAGE_UNAVAILABLE` 409;
the combined route uses `STUDIO_ASSET_USAGE_UNAVAILABLE` 409. Permission errors
never become empty results.

## Pagination, costs and consistency

Ordering is source owner, consumer ID, then node ID or track/clip ID. Identities
include owner type, so equal Graph and Timeline IDs are distinct. Repeated asset
pins in different positions remain separate items. The algorithm enumerates a
bounded saved-owner directory, then validates and projects a bounded set of
owners and reference positions; it does not collect all usage items before
slicing a response.

The original File format is a whole shared scope JSON document. Discovery and
owner validation still decode that whole document, including nonprojected
metadata, under an explicit encoded byte ceiling. This is not streaming JSON,
O(page-size) I/O, constant resident memory, or an index. Separate limits govern
directory entries, whole-file bytes, aggregate reads/bytes, consumers projected,
reference positions traversed, owner validation, returned rows and serialized
response bytes. Managed reads are scope JSON and asset metadata, **excluding
the authorization chain's other reads**. Whole-request IO, hard CPU timeout and
RSS are not bounded by this change. Physical shared-container resource admission is distinct from
the selected visible-owner fingerprint; unrelated hidden data are never emitted
as usage counts or change diagnostics. PostgreSQL explicit pagination is refused
because the existing JSONB reader has no prefetch byte bound. Legacy requests
retain their old backend behavior.

Only selected, actor-visible saved consumers participate in consistency
fingerprints. The query compares source and selected saved-owner state before
projection, before token issue and after issue before return. Observable
changes require restarting the query. It returns no mixed accepted page after
the tested deterministic changes or revocations. This is finite repeated
observation, **not** a durable snapshot or proof that no intervening change ever
occurred. A saved state changed and exactly restored between observations can
escape detection; strong ABA and full lifecycle history are explicitly false.
No shadow permission counter or lifecycle owner is introduced. The last
comparison does not hold an owner lease through HTTP serialization.
The global process-local registry holds at most 1024 tokens. Continuation does
not renew TTL; very small pages or substantial replay can exhaust capacity and
safely refuse the query. Arbitrarily many pages at `limit=1` are not guaranteed
to complete. A final outer authorization refusal may leave an undelivered token
until TTL, still within the same cap, without returning data.

`observed_count` is the matched count along this continuation; page scan fields
describe this page. `total` is null until the selected visible saved range is
fully scanned under those observations. An empty page may still have
`has_more=true`. Even a final total of zero does not establish absence of other
dependencies. `other_dependencies` remains `UNKNOWN`: unsaved browser drafts,
other modules, running temporary references and external files are unsupported.

The query does not delete assets, collect garbage, relink pins, migrate legacy
data, mint project identities, write query indexes, invoke models or dispatch
tasks. Tests compare complete synthetic file-name/content snapshots and record
actual writes separately from existing lock-file opens.

## Verification and evidence

The final source freeze is `554de521fb2640152408bcede62cbd21d3eaab49`, tree
`9a1ad60c58b42bf7d0b740048e7a34b5f997c642`. Subsequent commits only archive
reports and supplemental executable evidence: the frozen app/test/script
sources remain identical. Receipts and raw output live in
[`evidence/asset-usage-query-20261026`](evidence/asset-usage-query-20261026/README.md).
Each strict receipt contains the exact source commit/tree, command, source
SHA-256 manifest, output SHA-256 and before/after source-state comparison.
Overlapping groups are reported separately, never summed as unique tests.

The original Graph creation owner allows 25 consumers and a schema-bounded
number of nodes; the original Timeline owner allows 30 clips per timeline.
Those write contracts are preserved. Scale tests copy original-owner-saved,
structurally valid synthetic records into the temporary scope JSON, and label
consumer counts exceeding the normal creation cap. Oversize definitions remain
refused. First-query, repeat-query and fresh-process measurements are labeled
separately. OS caches are not cleared. Python allocation peaks are measurements
of Python allocations, not a process RSS bound or an invented performance gain.

Actions are NOT_RUN; known account billing restrictions were not retriggered or
changed. PostgreSQL, browser/UI, real model/GPU, POSIX-only experiments and
cross-worker persistent snapshots are NOT_RUN or unsupported for this delivery.
No packages were installed, system permissions or credentials changed, Release
created, main branch updated, or deployment performed.

## Final frozen receipts

| Group | Actual result | Receipt |
| --- | --- | --- |
| Related original, compatibility, owner, production and process-reopen regressions; separate durable-list-cursor file excluded for the diagnosed platform failure | 192 passed, 0 skipped, 0 xfailed | [receipt](evidence/asset-usage-query-20261026/coordinator/final-regressions-supported.receipt.json) |
| Independently authored pagination, changes, grants, revocation, resources and read-only counterexamples | 51 passed, 0 skipped, 0 xfailed | [receipt](evidence/asset-usage-query-20261026/independent/final-independent.receipt.json) |
| Legacy measurement; four scale scenarios via ASGI HTTP and File service; fresh-process cold/warm | 10 passed, 0 skipped, 0 xfailed | [receipt](evidence/asset-usage-query-20261026/compat/final-measurements.receipt.json) |
| Coordinator saved-consumer deletion/recreation interleavings and budgeted non-File reader admission | 6 passed | [receipt](evidence/asset-usage-query-20261026/coordinator/final-supplemental-corrected.receipt.json) |
| Actual loopback TCP HTTP, original unpatched assembly, both API aliases | 1 passed; each alias 540 pins / 6 pages with no duplicates or omissions | [receipt](evidence/asset-usage-query-20261026/coordinator/final-loopback-observed.receipt.json) |

The independent/performance units launched frozen runs in separate detached
worktrees. Their model turns subsequently reached an account usage limit.
The processes completed; the coordinator recovered their receipts and checked
source/log hashes against the frozen worktree. No extra credits were purchased.
Independently authored tests and pre-run review are distinct from later
coordinator evidence collection. Overlapping groups are not added as a unique
test total. The [source manifest](evidence/asset-usage-query-20261026/source-manifest.json)
lists SHA-256 values for all 19 changed implementation/test/script files.

The first broad regression stopped after 39 passes and **one existing
asset-list durable cursor failure**. The identical case fails at the fixed
baseline: its key loader requires POSIX `dir_fd`, `O_NOFOLLOW` and `O_DIRECTORY`,
unavailable on this Windows host. The resulting
`ASSET_QUERY_CURSOR_UNAVAILABLE` is preserved in the
[candidate log](evidence/asset-usage-query-20261026/coordinator/final-regressions.log)
and [baseline log](evidence/asset-usage-query-20261026/coordinator/baseline-cursor-refusal.log).
Remaining tests in that cursor file were NOT_RUN after the stop. The 192-case
group does not relabel this failure as skipped or passing. Its source was not
changed by this task.

The enforced page limits are 16 projected consumers, 256 visited positions,
200 returned items and 256 KiB serialized response; 4096 directory entries per
collection; 4096 validation positions per consumer; 4 MiB encoded scope JSON,
1 MiB asset metadata and 256 MiB / 1024 managed metadata reads per request.
Query strings have a 2048-byte ceiling. The 30-second deadline is checked at
managed read boundaries, not enforced as a CPU timeout. The source comment's
512 MiB estimate is neither a measured nor proven process-memory bound.
Shared-file resource admission can refuse a request when the physical container
exceeds its cap; it is not a diagnosis of a particular hidden dependency change.

The final instrumented ASGI HTTP measurements below cover a complete traversal.
Actual File read counts/bytes include the original authority chain. The meter
and Python `tracemalloc` add overhead, so these are not bare production latency
or evidence of a speed improvement. Cold-process timing excludes interpreter
import/startup; OS caches remain warm.

| Sample / phase | Returned / pages | Actual read bytes / calls | Instrumented seconds | Largest page Python allocation peak |
| --- | --- | --- | --- | --- |
| 30 saved Graphs, first query | 480 / 5 | 174171698 / 4409 | 63.118 | 5746081 B |
| 10 saved Timelines, first query | 300 / 3 | 5486688 / 378 | 3.213 | 4635709 B |
| 30 Graphs + 2 Timelines, first query | 540 / 6 | 222626838 / 7739 | 90.996 | 5766393 B |
| Same mixed data, new process first query | 540 / 6 | 222626838 / 7739 | 97.388 | 32892223 B |
| Same fresh process, repeat query | 540 / 6 | 222626838 / 7739 | 92.691 | 5796423 B |

All measured traversals on the initialized synthetic paths recorded zero
actual write calls and unchanged file snapshots. The largest mixed page was
59754 response bytes. Freshly copying data to a new absolute path additionally
exposed an original operational coordination-lock creation on its first read;
business files stayed unchanged. This is not a claim of zero physical writes
on all first-use paths. The explicit consumer-delete fixtures inject removal
through the original synthetic File transaction; no product delete API is added.
The non-File admission probe is a unit check, not real PostgreSQL execution.

Raw per-page reader calls, distinct-file counts, response bytes, writes and
memory figures are in [metrics](evidence/asset-usage-query-20261026/compat/metrics/summary.json)
and its sibling JSON files. Reproduction command arrays are in each receipt.
The common entry is:

```text
python scripts/record_asset_usage_validation.py --label REPRO --output-dir EVIDENCE --run-root SYNTHETIC_RUN_ROOT --require-clean-code -- TEST_FILE -q
```

Use `tests/test_studio_asset_usage_measurements.py -q -s` for scale figures;
use both `tests/test_studio_asset_usage_independent.py` and
`tests/test_studio_asset_usage_independent_mixed.py` for the independently
authored checks. Supplemental executable evidence has its own source hashes
named in its receipt. All data are synthetic; no real project or credential
is part of the delivery.
