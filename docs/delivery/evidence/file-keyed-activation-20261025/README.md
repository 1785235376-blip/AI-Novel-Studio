# Local File-keyed generation activation evidence

Historical standalone activation evidence on base e7f2eae / commit 942099b.
These counts do not certify the later M5+M6 merge. See
[merged-source verification](../file-keyed-integration-20261025/README.md) for the
canonical 18c8744 integration and fresh hash-bound results.

Base: `e7f2eaec2a5010a98cad6aa1d48df8e0ffc3b459`, tree
`66ef503f4b3e7c9c4da44dfbf453b09e37ef21a6`.
This is a local implementation and verification record, not a public release.
No GitHub write, upload, deployment, frontend work or real-model invocation
was performed by this slice.

## Evidence layers

- `tests/test_file_keyed_activation.py` mounts original HTTP endpoints and original
  File/JobManager/context/snapshot/Canon/memory composition. Positive continue and
  rewrite start with a NEW key, persist original RESERVED then a bound QUEUED row,
  stream through the actual original Mock adapter, persist COMPLETED and deferred
  snapshot, then use HTTP manual adoption with real manuscript/summary/pending
  Canon and nonempty original bound memory evidence/proposals/relations. It does
  not seed a completed bound row or bypass a mutation gate.
- `tests/test_file_writer_context_ports.py` isolates lower source/context/snapshot
  ports. Its explicitly constructed passive v2 GENERATING rows test expected
  original identities and snapshot state, not execution authorization.
- `tests/test_file_writer_binding_v2.py` covers strict additive source fields,
  cold repository reads, unknown versions and prohibited v1/v2 upgrades or rebase.
- Supplemental actual HTTP tests cover original automatic Mock selection,
  ambiguous/unknown/missing route refusal, and live v2 staged-variant refusal.
- `implementation/local_route_protocol.py` uses the actual LocalDiscoveryService,
  LocalDiscoveryBridge and LocalTextAdapter to check registered verified-local
  external metadata and its locality/fingerprint/management/enablement refusals.
  This is **metadata-protocol only**, not a local server/model inference test.

## Frozen verification

The production freeze manifest is
`implementation/production-freeze-3.sha256`; its SHA256 is
`0f1b7bd071bd39bbe62656b88e231a983c5f269fccdd4c0d81eeb0cf1a633c93`.
It covers every production Python file and remained unchanged through the
final independent review and final verification. Earlier freeze manifests and
their green runs are preserved as historical, superseded evidence. Test-file and runner manifests
are separate so a changed fixture is not silently treated as an unchanged input.

Independent final review: **25 passed**, all input/probe hashes unchanged.
This retains the earlier 22 cases (17 adversarial, 2 original positive E2E and
3 original HTTP malformed/unknown-route probes) and adds three genuine-chain
writer/manual-adoption/memory final-owner-window probes.
See `independent/REVIEW.md` and `independent/freeze3/` for exact commands,
stdout/XML, frozen changed source and source/probe verification.

The authoritative corrected-Mock aggregate is recorded in
`implementation/mock-final-frozen4-regression.log` and `.xml`, with exact command,
all-input before/after manifests and status beside them. **677 passed, 3 live-PG skipped, 0 failed, no deselection** (134.43s);
all app/test/runner/probe hashes were identical before and after. The separate
actual three-way concurrent keyed HTTP admission supplement passed with identical
input hashes. Repeated focused
and aggregate runs are not additive unique coverage.

## Corrections and retained raw failures

Raw failures are deliberately retained, not renamed as successful runs:

1. Early construction inspected unsupported passive PG context sentinels.
   Exact-type-gated pin construction restored the no-downstream-read contract;
   original PG protocol tests were not weakened.
2. A passive direct worker guard temporarily changed exception shape. Original
   HTTP409 refusal was restored, without granting execution.
3. Independent `snapshot-wip/` reproduced a real late deferred-snapshot write
   after cold restore durably FAILED an executing job. Its source hashes did not
   change during that probe. The final original snapshot owner boundary requires
   the exact durable GENERATING row before directory creation/write; the same
   independent probe now passes. Snapshots were not disabled.
4. Four existing receipt/legacy-authority fixtures have synthetic dispatch or
   incomplete downstream composition. They now explicitly use HYBRID, outside
   the new narrow LOCAL_ONLY activation. All their original assertions remain;
   the new eligible mode is separately tested with original full composition.
5. The first broad run measured **670 passed, 2 failed, 3 skipped**. One remaining
   receipt fixture needed the same explicit legacy-mode correction. The other
   was a runner configuration error, NOT an adaptation implementation defect or
   stale test: the old runner omitted Mock mode before dependency initialization.
   Its actual predicate was mock=false, adapter=NoneType, remote=true. The source
   has an explicit genuine synthetic seam. With MOCK_PROVIDER=true and packaged
   mode=false before imports, the actual adapter is MockProvider and remote=false;
   the unchanged valid/invalid adaptation test passes both the exact base and
   this worktree. No adaptation source/assertions were changed.
6. A corrected-Mock aggregate first measured **676 passed, 1 failed, 3 skipped**:
   one remaining variants fixture also used a synthetic start/memory owner under
   LOCAL_ONLY. Its explicit HYBRID correction preserved all assertions; separate
   actual eligible concurrent admission was added. The final full run is green.
7. A **675 passed, 3 skipped, 1 deselected** run is retained as intermediate
   runner-mode evidence only. The subsequent corrected-Mock full aggregate has
   no deselection. Do not quote the intermediate run as a full pass.

8. Supplemental original-owner entry probes found late global Job receipt
   writes after genuine same-thread owner replacement: writer GENERATING→COMPLETED,
   v2 manual ACCEPTING→ACCEPTED and bound memory GENERATING→COMPLETED. Replacement
   project bytes were untouched, but late retained receipts were still defects.
   `independent/owner-window/` and `adoption-owner-window/` preserve exact failing
   commands/source/stdout/XML. Final original save now rechecks expected writer
   owner/source/pins and actual memory expected ports immediately before atomic
   write; v2 manual persistence forwards owner-only original expectations. All
   three genuine-chain counterexamples pass on freeze3. V1/legacy modes were not
   activated or reinterpreted. No production change followed freeze3.

The explicit pre-import synthetic environment, sockets blocked, isolated
HOME/XDG/data/tmp, actual worktree PYTHONPATH/PROJECT_ROOT and disabled external
credentials are part of the test contract. Frozen environment predicate logs and
baseline comparison are under `implementation/`. No runtime project data is
included in this evidence package.

## Coverage boundaries

The three aggregate skips are live PostgreSQL tests: atomic chapter CAS/history
and two original generation-snapshot foreign-key/identity tests. They are
**NOT_RUN**, not successful offline PG transactions. Offline original PG protocol
and passive manager regression tests remain separate evidence.

Embedded `test_real_graph_worker_keeps_disjoint_path_and_required_callback_contract`
uses the original Graph prepare/start/worker and Mock seam while forbidding
ordinary author/context paths. Original specialized File persistence tests retain
Graph/adaptation/director/OCR/image disjoint roundtrips. This is not full Graph
owner/UI certification, nor live director/OCR/image execution certification.
Real external/local models, live PostgreSQL, Windows, and frontend: **NOT_RUN**.

This protects cooperating original File ports, not hostile arbitrary filesystem
writes or monkeypatches beneath the final original mutation boundaries. It does
not claim multi-file crash atomicity, exactly-once inference, restored execution,
a general bound retry/cancel facility, or historical unbound repair.

## Reproduction

Historical raw commands retain their original absolute/cwd paths for accuracy.
`run_tests.py` in this directory is the portable equivalent of the corrected
Mock runner, using this checkout and an isolated `.runtime` directory. Run it
with the repository's installed test interpreter and the test paths listed in
`implementation/run_mock_frozen4_regression.sh` (or its recorded exact equivalent).
The supplemental probe file is retained under `implementation/` and can be passed
as an explicit pytest path. Never substitute live model credentials for these
synthetic tests.
