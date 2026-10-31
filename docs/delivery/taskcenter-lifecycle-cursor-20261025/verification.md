# Frozen File/local cursor slice verification

Implementation commit: `774e65a56fce3464d8b6e884d3da8a0d629aac68`.
Implementation tree: `67fdc75acd411316ea5f136cf2334b1d8c944d30`.
Base: `63636958e48ad12f6416194272781c9e3bf8ae71`.
The following delivery commit adds only consumer tests, documentation and evidence;
its application source must compare byte-for-byte equal to the implementation.

All runs used the dot native cloud executor, isolated synthetic File roots,
mock providers and an in-memory credential vault. The existing Python environment
was reused as an interpreter; no dependency was installed or locked, no real
PostgreSQL server/model/paid service was called, and no user computer or Codex
cloud task was used. This report does not attest hosted CI or deployment.

## Final groups (do not add overlapping counts)

- `final-new`: 105 passed. 48 real HTTP cases, 46 original-store lifecycle cases,
  8 exact opt-in cache-boundary cases and 3 POSIX process probes.
- `final-owner-regression`: 86 passed. Exact files:
  `test_cloud_canvas_create_recovery.py`, `test_cloud_formal_canvas_node.py`,
  `test_cloud_saved_canvas_pin.py`, `test_asset_query_index_recovery.py`,
  `test_studio_workspace_identity_history_contract.py`, `test_phase7_novel_import.py`.
- `final-consumers`: 14 passed. Real WorldService ability create/edit,
  PlanningService graph/volume creation and editing, CreativeGraphService schema
  1/2 text-input draft creation/idempotent creation/save, each across legacy,
  protected local and collaboration scope variants. Read/no-op/source-lease,
  stale version/transition, final authorization refusal and rollback checks are
  included. No graph/model execution is invoked.
- Independent fresh detached clone: 21 passed, original probes unchanged.
  Its baseline records four reproduced risk behaviors and a no-op control, not
  five remediations. See `evidence/independent/FINAL_INDEPENDENT_REVIEW.md`.
- Unchanged original verification runner: **accepted=true**, source isolation
  and before/after source integrity both true. Baseline original 65 passed;
  baseline regression 198 passed; 12 baseline-red cases failed as expected,
  with zero setup errors; candidate focused 190 passed; candidate regression
  198 passed. See the final machine-readable summary and raw group logs under
  `evidence/original-runner/`. These are separate overlapping groups, not
  aggregate product coverage. The unchanged runner's historical disclaimer
  does not certify new HTTP success; that evidence is in `final-new` and the
  independent frozen-clone probes.

The selected shared-store consumers above are not a certification of all 54
original transaction consumers. Consumer paths not named by these tests remain
outside this targeted regression claim. Original ordinary read-your-write is
unchanged; only the new capture port promises physical committed observations.

## Commands and provenance

The unchanged original script was run from a separate frozen clone:

```sh
PYTHONDONTWRITEBYTECODE=1 /workspace/scratch/20a0022d2b33/studio-overnight/.venv/bin/python \
  /workspace/shared/taskcenter-lifecycle-frozen-774e/scripts/verify_taskcenter_consistent_query.py \
  --output /workspace/shared/taskcenter-lifecycle-evidence/frozen-original-runner
```

New/consumer groups used the original runner's `run_group` environment and
module-evidence plugin, without changing assertions or application source:

```sh
python evidence/run_isolated_group.py final-new \
  tests/test_taskcenter_lifecycle_http.py tests/test_taskcenter_store_lifecycle.py \
  tests/test_taskcenter_private_cache.py tests/test_taskcenter_store_process.py
python evidence/run_isolated_group.py final-consumers tests/test_taskcenter_store_consumers.py
```

The archived helper records the actual executor paths. Each raw log begins with
its exact cwd and pytest command, including the isolated temporary directory.
The helper strips provider/database environment variables and uses the original
runner's supported HOME/XDG/data-root isolation. The independent invocation and
probe source are archived verbatim with hashes. JUnit, raw stdout and source/hash
summaries accompany the result; no runtime directory or virtualenv is archived.

One earlier full-run attempt overlapped addition of the new consumer test file:
its source-integrity check correctly returned false. It is not counted as a
frozen pass. Application code did not change; the authoritative full run was
repeated in the separate immutable-commit clone above. An initial M0 attempt also
used the default read-only home identity path and failed before the isolated
supported XDG setup was supplied; the successful M0 original 65-test run is not
inferred from that failure.

## Limits preserved

See `stable-slice.md` for the exact observed-row/current-bounded-projection
contract. In particular, transient insertion/removal of a row absent from the
observation is explicitly not full membership-history ABA protection. Hidden
unselected collections and the 201st-and-later unobserved tail are not bound via
a collection epoch. General backup replay, physical power loss, Windows,
PostgreSQL and additional authority/session/grant lifecycles remain unverified
or unsupported. SIGKILL verifies process interruption around replace, not
parent-directory fsync or power-loss durability.
