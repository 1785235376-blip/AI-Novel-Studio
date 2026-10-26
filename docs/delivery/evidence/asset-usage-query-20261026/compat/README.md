# Compatibility and performance evidence

All data are fresh synthetic File fixtures. No real user directory, model execution, external network, PostgreSQL, hosted Actions, or POSIX execution is exercised.

## M1 baseline

`m1-baseline.receipt.json` binds exact tested commit/tree, source hashes, runner command and log hash. 10 tests passed with source unchanged throughout the run. These include original mounted Graph/Timeline no-query usages, missing Host session 401 before source lookup, all-file read-only snapshots, Graph save/history and stale saved pin observations, single Graph 201-node rejection, single Timeline 30 references, and the tracked identity/history/restore/Host-revocation suite.

The fixed baseline has no tracked original dedicated Graph/Timeline usage test suite: MISSING. The additional tests were authored for this task and are not represented as recovered original tests.

## Exploratory legacy measurements

`m1-measure.log` is exploratory and predates the final source-frozen measurement driver. It is not a final acceptance receipt. Original real mounted HTTP with 14 saved graphs, 16 references each (224 total), returned 200 rows and truncated=true. Instrumentation adds overhead: the first/repeat measurements were 42.677/42.325 seconds, 99,690,903 actual read bytes, 5,566 reads, four distinct files, and 119,972 response bytes. Python tracemalloc peaks were 3,924,195/3,636,470 bytes, not process RSS. OS caches were not dropped. `write_opens` counts writable opens including preexisting locks and is not a count of writes; all source file hashes were identical before/after. The final meter separately records actual write() calls/bytes and original owner reader calls.

## Capacity boundaries

Normal legacy Graph creation permits at most 25 graphs and 16 nodes per graph. The 30-graph fixture explicitly copies valid saved original owner records and exceeds normal create capacity; it tests querying already-saved metadata, not newly authorized graph capacity. A 201-node graph is rejected by original HTTP schema validation. Timeline's normal per-timeline maximum is 30 clips; those fixtures first pass the real save route. Claims remain exact saved direct references only, with other_dependencies UNKNOWN.

Final paged metrics await the frozen implementation. Full restart cold-process and cleared OS-cache measurements are NOT_RUN; first-read/repeat-read labels describe observed query state only.
