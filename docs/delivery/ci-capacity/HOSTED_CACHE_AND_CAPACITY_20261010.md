# Hosted cache initialization and backend capacity: 899d40d

Owner: B read-only analysis, using A's sole original CI archive. No job was
cancelled or rerun for this measurement. The unchanged `ci_capacity.py` accepted
both run archives with exit 0; its output remains `DIAGNOSTIC_ONLY` and
`coverage_verdict: NOT_EVALUATED`.

## Exact source and events

- Head/push checkout: `899d40df5273413d987f9ee98d41a7405ed16d0a`.
- PR merge checkout: `d059cf2cc3aa17e16ec77e7ed1c9edb1f4e45cfe`.
- Source tree in both receipts: `01e338ea26b120f364919a94bc42ad14feb9d448`.
- Push run [38080738263](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38080738263), attempt 1.
- PR run [38080743645](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38080743645), attempt 1.
- Complete collected inventory: 11,417 exact ordered nodes. File assignment:
  11,417; deterministic PG assignments: 5,713 / 5,704. No assignments changed.

## Cache initialization is verified; a hit/speedup is not

All eight backend execution jobs (two TCP, two File, four PG) explicitly reported
a pip-cache **MISS**. Both TCP jobs subsequently saved the dependency-keyed
download cache successfully. The two successful PG shard-1 jobs had successful
post-step conclusions but logged failed cache reservations because another job
might be creating that key. They are recorded as **NOT_SAVED_RESERVATION_CONFLICT**,
not successful uploads. The four cancelled File/PG-0 jobs skipped cache post-steps.

The push TCP setup/install/post steps took 12/22/2 seconds; PR TCP took 10/20/2.
Both actually ran `pip check` successfully and retained installed-package
receipts. Their pip-cache reports show 40.3 MB of HTTP cache, 240 HTTP files and
zero locally built wheels. The cache location remained
`/home/runner/work/_temp/novel-pip-download-cache` after the isolated preparation
changed HOME. This verifies the runner-step initialization correction and the
real save path, without replacing dependency installation or checks.

Saved key:
`setup-python-Linux-x64-24.04-Ubuntu-python-3.12.9-pip-c7fc125ee9ed5386f2028b52a4f51d44bd1601e5466dcdc13df4ca8f420f01d8`.
No hit or timing benefit was observed in these runs. The historical c491d1b
workflow-loader failure remains recorded separately; passing infrastructure
tests had not established GitHub expression-context validity.

## Actual backend outcomes

| Event / profile | Job | Conclusion | Full execution step (s) | Observed nodes / assigned | Unobserved |
| --- | ---: | --- | ---: | ---: | ---: |
| push File | 114296945651 | cancelled, incomplete | 1,112 | 9,330 / 11,417 | 2,087 |
| PR File | 114296961404 | cancelled, incomplete | 1,116 | 9,953 / 11,417 | 1,464 |
| push PG 0 | 114296945710 | cancelled, **failed call observed** | 3,208 | 5,446 / 5,713 | 267 |
| PR PG 0 | 114296961431 | cancelled, incomplete | 3,212 | 5,664 / 5,713 | 49 |
| push PG 1 | 114296945687 | success, receipt complete | 2,985 | 5,704 / 5,704 | 0 |
| PR PG 1 | 114296961374 | success, receipt complete | 3,086 | 5,704 / 5,704 | 0 |

The two File jobs lasted 1,230 / 1,224 wall-clock seconds under the unchanged
20-minute budget. PG-0 lasted 3,318 / 3,317 seconds under the unchanged 55-minute
budget. Logs say the operation was cancelled; no more specific scheduler
annotation was read. These timings are consistent with a capacity boundary,
but they do not erase failed phases or establish a precise host root cause.

Both PG-1 artifacts contain 3,743 passed calls and 1,961 setup skips, with
complete events and JUnit. That is a single-shard observation, not a complete
backend gate pass. File and PG-0 have `complete:false`, null pytest exit status
and no final `backend.xml`. File and PR PG-0 have no observed failed phases;
their unseen tails and incomplete final phases remain unknown.

Both required backend check names fail on each event because their original
requirement that every execution job succeed is not met. Downstream
join/reconciliation did not run. Neither event can supply missing evidence for
the other.

### Repeated real failed call

Push PG-0 again records a failed call for:

`tests/test_v2_graph_text_assets.py::test_manual_refresh_completion_boundary_requires_archive_before_review[postgres-settling]`.

Its exact node-ID SHA256 is
`1961ea0c1517e8aeca029d9bfdee7ca7f37557e546901c9296ad2fd7cdb14b9a`.
The test file is byte-identical at e6ff3431 and 899d40d:
`76dea8012294e130ef9abd00c1b821fb96b21a72d8e17657a2567c54bf687a40`.
The earlier hosted occurrence and this new occurrence both remain
**FAILED_OBSERVED**. No final traceback is present in the incomplete artifact.
Earlier isolated passes or timing diagnostics do not replace either original
failure or prove its cause.

## Bounded attribution and deferred optimization

The largest timestamped File window spans 72 emitted statuses covering the end
of shared-route authority, stability, stable identity and the start of record
CAS: 102.986 seconds push / 122.956 seconds PR. It is not per-case timing.
The next 72-status story-simulator-model window costs 60.952 / 71.285 seconds.
Cancelled runs cannot provide complete JUnit timing, and unseen runtime is not
extrapolated from percentages.

In successful PG-1 JUnit, shared-project route authority totals 420.094 / 436.829
seconds, local interop host 174.746 / 180.536, and surface-adapter projection
134.856 / 141.301. These are observed module totals, not permission to modify
original tests, fixture scopes, authority checks or frozen shard allocation.

The File pip-install steps cost 22 / 21 seconds, while media APT installation
cost 30 / 18 seconds. Perfectly overlapping just these independent preparation
chains would have an optimistic upper bound of 22 / 18 seconds under unchanged
resource costs. Real CPU/network contention could erase that benefit. This
does not explain the 2,087 / 1,464 unobserved-node gap. A chose to leave the
workflow unchanged rather than stack small setup changes onto a frozen full
execution contract. No preparation parallelization, timeout increase, test
sharding, assertion change or new skip was implemented.

## Evidence and next boundary

`hosted-899d40d/` contains both compact diagnostic reports, original-run cache
observations and input/tool hashes. Small original metadata snapshots were
copied byte-for-byte into B's analyzer view; original logs and extracted receipts
were read through links to A's archive, not duplicated or downloaded again.

Caching correctness and opt-in catalog snapshot disk savings are now separately
demonstrated. The hosted backend remains blocked by incomplete File/PG-0
execution and the repeated observed PG failure. No complete-CI or historical
security-review acceptance is claimed. The next naturally authorized run may
show a cache hit; until observed, cache speed benefit remains unmeasured.
