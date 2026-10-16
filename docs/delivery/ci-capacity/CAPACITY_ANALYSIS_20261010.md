# File / PostgreSQL capacity analysis

## Result

The e6ff File executions are incomplete under the existing 20-minute job cap.
Dependency caching is a small, bounded installation optimization; the remaining
problem is predominantly suite execution. No safe change to the frozen
File-one/PostgreSQL-two assignment or original test command is made here.

The cancelled push PostgreSQL shard also contains an original failed call.
That functional failure remains **FAILED_OBSERVED** alongside cancellation.
Neither successful PR PostgreSQL shards nor later focused runs replace it.
Historical independent review remains **BLOCKED**.

## Source and methodology

- Product source: `e6ff3431cf84b01b77cd1bd73a977fd5e784447b`.
- Tree: `1677c06d6736a07f0d4a507656d9c19e0033494c`.
- Push run: [38070247951, attempt 1](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38070247951).
- PR run: [38070252155, attempt 1](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38070252155).
- PR checkout/event SHA: `6125d9d593ffcb7a1122c0f2c8f5f5005e8335b4`,
  with the same tree. It is recorded separately from the push SHA.

The new `.github/ci/ci_capacity.py` reads already archived metadata, exact event
streams, original job logs and any final JUnit XML. It does not contact GitHub,
execute tests, alter receipts, assign shards, update manifests or call a
coverage verifier. Reports explicitly say `DIAGNOSTIC_ONLY` and
`coverage_verdict: NOT_EVALUATED`.

Input file SHA256 digests, tool digest, run/attempt, source/tree/event identities,
profile and shard remain attached to each report. Push and PR inputs are never
combined. Local file digests identify the analyzed archive bytes; independent
download authentication remains the original archive's responsibility.

The timestamped compact pytest progress output is matched exactly against the
ordered original event statuses. Only the command following the original
full-suite invocation is eligible; whole-second API step times alone cannot
separate the preceding infrastructure suite. A mismatch is rejected instead
of guessing. Windows below are groups of terminal statuses, not inferred
individual test durations. The first window includes collection/startup.
Unprinted tail events have no attributed time.

## Observed File capacity

| Run | Job elapsed | Full-suite step | Dependency install | Nodes with teardown event | Unobserved assigned nodes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Push | 1,223 s | 1,116 s | 19 s | 9,238 | 2,082 |
| PR | 1,229 s | 1,119 s | 17 s | 10,103 | 1,218 |

Both assigned the complete 11,321-node inventory and both lack final backend
JUnit XML. The push additionally observed the setup of the next node without
its teardown. These are event observations, not accepted passing-suite counts.
Elapsed job timestamps include setup and cancellation/cleanup around the
configured 1,200-second budget; the configuration is unchanged.

The push's last observed node is
`test_v2_ai_execution_browser_fixture.py::test_m4_original_mounted_worker_fixture_without_browser`.
The PR's last observed node is
`test_v2_discovery_onboarding_api.py::test_default_off_and_v1_acceptance_reject_new_onboarding_routes[False]`.
The difference demonstrates runtime variability. No completion time is
extrapolated from the proportion of observed nodes.

Largest common File timing windows:

- A 72-status window across the tail of `test_shared_project_route_authority.py`,
  `test_stability_v04.py`, `test_stable_identity_foundation.py` and
  `test_structured_record_cas.py`: **128.35 s push / 109.82 s PR**.
- A 72-status window entirely in `test_r4_story_simulator_model.py`:
  **78.67 s push / 58.50 s PR**.
- The preceding mixed `test_r4_story_simulator.py` / model window:
  **49.94 s push / 37.38 s PR**.

Source inspection identifies an existing 50-iteration cold-start test in the
first window. Each iteration spawns 2 same-key, 2 different-key and 4 mixed-kind
processes, totaling 400 process starts. Its 50 iterations, `spawn`, original
assertions and 20-second per-process joins are preserved. A window does not
establish how much of its total belonged to this one case.

## Observed PostgreSQL costs and failure

- Push shard 0: suite step **3,204 s**, cancelled, 505 assigned nodes never
  observed. Original event stream includes a failed call in
  `test_manual_refresh_completion_boundary_requires_archive_before_review[postgres-settling]`.
  The stream has no traceback; this analysis does not infer its assertion or
  root cause from duration.
- Push shard 1: suite step **3,077 s**, hosted success.
- PR shard 0: suite step **2,955 s**, hosted success.
- PR shard 1: suite step **3,089 s**, hosted success.

The successful PR JUnit files provide exact testcase timing by original
`ci_nodeid`, separately per shard:

| Module | PR shard 0 | PR shard 1 |
| --- | ---: | ---: |
| shared_project_route_authority | 398.25 s | 432.17 s |
| local_interop_host | 214.88 s | 180.72 s |
| surface_adapter_projection | 154.05 s | 138.33 s |
| r4_story_simulator_model | 141.40 s | 101.08 s |

PR shard 0's existing cold-start stress case reports 102.402 s. This is
PostgreSQL-profile timing evidence, not a substitute for the missing File XML.
The assigned inventories differ by only 13 nodes (5,667 / 5,654), while their
runtime differs materially. Node-count balance is not duration balance.

## What can and cannot change independently

Implemented separately in `5b8a42a`: pip download caching for backend execution
and original TCP, with exact dependency-key inputs and unchanged installation,
package checks and freezes. Hosted net benefit is still **NOT_MEASURED**.

Preserved requirements:

- File remains one original-order process; PostgreSQL remains its original two
  deterministic node-ID shards. No filtering, reorder, xdist or extra shard.
- Original 20/55-minute caps, complete pytest command, source digest validation,
  ordered inventories, exact phase/JUnit reconciliation, skip policy and TCP
  dependency remain unchanged.
- No new workflow/job substitutes for a required check, and no push/PR run is
  skipped to disguise duplicate cost or a failure.
- No original test, fixture assertion, wait, iteration count or product source
  is changed by this work.

Changing File partitioning, replacing hash assignment with duration-based
assignment, moving product cases to a new wrapper, or expanding timeouts would
alter the frozen contract. Those options are **BLOCKED under the current
scope**, rather than implemented through a new green-looking gate.

## Reproduction and remaining work

Run the read-only analyzer once for each archived run directory:

    python .github/ci/ci_capacity.py --run-dir PATH_TO_ONE_ARCHIVED_RUN --output NEW_REPORT.json

The directory must contain the original `run-final.json`, `jobs-final.json`,
`artifacts-final.json`, `artifact-ID/coverage.json`,
`artifact-ID/coverage-events.jsonl`, and available job logs / backend XML. The
tool refuses to overwrite an existing output. Its 40 new infrastructure tests
cover wrong source/run/attempt/profile, missing artifacts, malformed phases,
xfail, progress mismatches, exact JUnit identity, non-finite timing, large node
IDs and preserving original inputs/output.

Read `run-38070247951-capacity.json` and `run-38070252155-capacity.json` beside
this report for the complete bounded timing details and input hashes. They
preserve every observed failed phase; no original raw evidence is replaced.

Remaining steps are measurement of a hosted cache hit on A's final integrated
source, and separately authorized product-performance investigation if needed.
Any supplementary local targeted measurement is reported separately and cannot
close hosted failure, full-suite coverage, or historical review.

## Supplemental unchanged cold-start measurement

One bounded, isolated File-profile execution of the original
`test_real_multiprocess_cold_start_stress_50_iterations` completed on the dot
cloud computer using Python 3.12.14:

- **1 passed**, 90.81 s pytest elapsed; setup **4.80 s**, call **85.64 s**.
- All 50 iterations and 400 process starts, assertions and waits were unchanged.
- Original test SHA256:
  `f998e171c1b498bf5767051bc972984329a36f1bb84db95bffa2f4cf3f8a9ee2`.
- The existing isolation runner records no source changes during execution.
  Source snapshot and original log:
  `../v2-development/b-ci-cold-start-diagnostic.json` and `.log`.
- It ran once, in B's private profile; it was not a rerun of the failed
  PostgreSQL settling test. No model/API calls or original test changes.

This gives a useful standalone cost sample for one known expensive case, not
the missing hosted File duration or its full-suite interaction behavior. It
does not justify reducing stress iterations, replacing spawn, or claiming that
the cold-start test explains every capacity loss.

Final local infrastructure verification: **320 passed** in 9.42 s, including
the 40 new analysis tests and all unchanged gate/hash preservation tests.
Original product tests and V1/gate/helper bytes remain unchanged. A still owns
explicit regeneration of the final V2 source inventory before publication.
