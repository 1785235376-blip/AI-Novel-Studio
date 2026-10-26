# Compatibility and performance evidence

All data are fresh synthetic File fixtures. No real user directory, model execution, external network, PostgreSQL, hosted Actions, or POSIX execution is exercised.

## M1 baseline

`m1-baseline.receipt.json` binds exact tested commit/tree, source hashes, runner command and log hash. 10 tests passed with source unchanged throughout the run. These include original mounted Graph/Timeline no-query usages, missing Host session 401 before source lookup, all-file read-only snapshots, Graph save/history and stale saved pin observations, single Graph 201-node rejection, single Timeline 30 references, and the tracked identity/history/restore/Host-revocation suite.

The fixed baseline has no tracked original dedicated Graph/Timeline usage test suite: MISSING. The additional tests were authored for this task and are not represented as recovered original tests.

## Exploratory legacy measurements

`m1-measure.log` is exploratory and predates the final source-frozen measurement driver. It is not a final acceptance receipt. Original real mounted HTTP with 14 saved graphs, 16 references each (224 total), returned 200 rows and truncated=true. Instrumentation adds overhead: the first/repeat measurements were 42.677/42.325 seconds, 99,690,903 actual read bytes, 5,566 reads, four distinct files, and 119,972 response bytes. Python tracemalloc peaks were 3,924,195/3,636,470 bytes, not process RSS. OS caches were not dropped. `write_opens` counts writable opens including preexisting locks and is not a count of writes; all source file hashes were identical before/after. The final meter separately records actual write() calls/bytes and original owner reader calls.

## Capacity boundaries

Normal legacy Graph creation permits at most 25 graphs and 16 nodes per graph. The 30-graph fixture explicitly copies valid saved original owner records and exceeds normal create capacity; it tests querying already-saved metadata, not newly authorized graph capacity. A 201-node graph is rejected by original HTTP schema validation. Timeline's normal per-timeline maximum is 30 clips; those fixtures first pass the real save route. Claims remain exact saved direct references only, with other_dependencies UNKNOWN.

Final frozen results are in `final-measurements.log` and its receipt: **10 passed**
on exact `554de521fb2640152408bcede62cbd21d3eaab49`, tree
`9a1ad60c58b42bf7d0b740048e7a34b5f997c642`, with source unchanged throughout.
Raw data are in `metrics/`, including per-page original reader call counts and
actual reads/writes. The source code was not modified to produce the metrics.

The four scenarios are 30 Graphs/480 matches, mixed audio/image Graphs/240
matches, 10 Timelines/300 matches, and 30 Graphs plus 2 Timelines/540 matches.
Each runs through original mounted ASGI HTTP and direct original File service,
first/repeat separately. The final test starts a new interpreter and opens the
same synthetic saved files with original `main.app` assembly; it measures all
540 mixed pins in six pages, then repeats in the same process. This is actual
fresh-process cold state with warm OS cache; interpreter startup/import time is
excluded. It is ASGI mounted HTTP, not a TCP socket measurement. Cleared OS-cache
experiments, real PostgreSQL and real model execution remain NOT_RUN.

New-process first/repeated traversals read 222626838 bytes in 7739 calls;
instrumented times were 97.388/92.691 seconds, with largest per-page Python
allocation peaks 32892223/5796423 bytes. No speed improvement or RSS bound is
claimed. All measured initialized-path traversals recorded zero actual writes;
the separate first-use socket probe documents an operational lock-file creation.
`metrics/summary.json` is a derived summary; sibling per-page JSON and the raw
test output are the primary measurements.
