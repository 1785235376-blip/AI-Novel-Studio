# Independent TaskCenter lifecycle re-verification

Baseline 63636958e48ad12f6416194272781c9e3bf8ae71 / tree 31eb13e7d781b68fdeecb8b53e84d1865cde4381.
Frozen candidate 774e65a56fce3464d8b6e884d3da8a0d629aac68 / tree 67fdc75acd411316ea5f136cf2334b1d8c944d30.

## Result
21 independent acceptance cases passed against a fresh detached clone at /tmp/taskcenter-independent-774e. Original production code was neither edited nor replaced by this reviewer. Tests were authored outside the repository and use original mounted File authorization, project deletion/recreation and source readers. No fake epoch, fake permission owner, real model, external service install or upload was used.

Baseline risk reproduction: baseline.log records 5 successful probes (four reproduced risk behaviors plus one positive no-op control). baseline-green-contracts.log records 2 expected acceptance failures and 3 passes. Frozen candidate turns those two acceptance failures green, and all additional original-observation and mounted HTTP cases pass.

## Verified scope
- Cross-instance same-thread/root/scope stale outer write cannot erase committed inner state.
- A cross-instance commit under Creative source_lease is rejected as a conflict rather than silently accepted by the lease.
- Pure no-op, mutate-then-restore, source_lease and exception rollback perform zero experimental atomic_write calls for missing/existing scope; protected capture/no-op preserve bytes/evidence.
- Committed original observation does not expose active transaction values across either store instance; ordinary read-your-write was not required to change.
- Real committed A->B->A changes row nonce, despite restored business bytes.
- Unselected collection updates do not affect semantic source observation.
- Physical legacy document with a current valid project marker remains unsupported and is not migrated by ordinary writes or observation.
- Two mounted prefixes return real first/next/replay/last cursor pages, with no-store; GET leaves scope document bytes unchanged.
- Selected, authorized, query-matching rows inside original 200 scan window but outside current page invalidate continuation on version change, ABA and delete/recreate.
- 201st row outside original observation window, and unselected collection, can change/ABA without invalidating existing cursor or changing replay response. No complete-history coverage or forced expanded scan is claimed.
- Original project delete and same-ID recreate causes old token 409 and new first page 501, on both prefixes, without changing preserved scope bytes.
- Legacy source or missing original marker refuses first page 501/no-store on both prefixes, without creating marker or source metadata.

## Evidence
- frozen-independent.log: full raw stdout, 21 passed.
- frozen-identity.txt: exact commit/tree.
- run_frozen.sh: exact invocation (all commands explicitly cwd=/tmp).
- test_green_contracts.py, test_committed_observation_contract.py, test_http_lifecycle_contract.py: independently authored acceptance probes.
- baseline.log, baseline-green-contracts.log, candidate-store.log: reproducible baseline and staged comparison.
- initial-environment-error.log: initial default identity-path error, before supported isolated XDG_DATA_HOME configuration.
- SHA256SUMS: artifact hashes.

## Limits
This independent batch does not establish PostgreSQL, Windows, power-loss/fsync(parent) durability, restore anti-replay, collaboration/session-grant lifecycle support, all 17 source coverage, broad regression completion or hosted CI status. It does not independently claim multiprocess/SIGKILL success; those are separate worker results. Tests snapshot scope bytes and specific atomic_write calls, not zero OS lockfile operations. Unknown pytest marks are runner-configuration warnings, not skipped tests. Test evidence is local only and unpublished.
