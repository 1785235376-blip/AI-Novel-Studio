# Separately bounded original TCP execution

## Why the execution boundary changed

For branch head `99e3c636bc59f45f5faa4b7af84b80981f1ec2e5`, PR run
`37902141902`, attempt `1`, File job `113726946131` checked out the actual
PR merge SHA `42d8355c00eb545d40ab503c4429315bb7eef74e` (tree
`b0595aaccb9c42437f3d61aaf209a61de94d584d`) and completed its full,
original-order process: 6,190 passed and 3,259 exact skips (9,449 nodes),
1,080.84 seconds reported by pytest. The full workflow step took 1,089 seconds.
After setup, dependencies, font and infrastructure checks, the subsequent TCP
step had only 32 seconds before the original 20-minute job limit cancelled it.
This remains failed/incomplete job evidence. It is not a successful TCP gate.

`backend-tcp` gives the existing two opt-in real-loopback tests a separate
10-minute outer job cap. File remains one original-order process with its
original 20-minute cap. Both PostgreSQL shards retain 55-minute caps and their
existing deterministic assignments. The complete File execution step, original
174 infrastructure checks, all original product tests, original skip/external
gate maps, and `suite_coverage.py`, `coverage_reconcile.py`, `postgres_gate.py`
and `prepare.sh` bytes remain unchanged. The 102 new infrastructure tests run
in the new TCP job, not in File's time budget.

## Producer

The TCP job uses the existing `prepare.sh` tracked-source archive and isolated
profile, Python 3.12.9, the identical constraints and backend extras, `pip check`,
and a real installed-package freeze. The runner executes the original pytest
scope/options once, with `RUN_B10_TCP_SYNC_TEST=1` and `STORAGE_BACKEND=file`.
The tests themselves still start distinct uvicorn processes, bind real loopback
sockets, and use independent data roots. No transport or product assertion is
replaced.

`tcp_evidence.py run`:

- Checks the actual checkout SHA/tree against the preparation environment and
  records event SHA, repository, run ID, attempt, Python/platform and manifest
  and dependency digests.
- Validates every manifest source before execution and again afterward. It
  records both exact source-hash maps and rejects drift.
- Independently compares installed packages with the saved install receipt and
  every exact constraint; it checks installed packages again after execution.
- Writes an incomplete receipt before launching the child process. Cancellation
  or interruption cannot yield a successful completion marker.
- Retains the actual subprocess exit status and original stdout/stderr log.
  The unchanged original JUnit validator requires exactly the original two TCP
  identities, zero skips/errors/failures, and internally consistent counts.
- Refuses to overwrite an existing TCP receipt, log or XML.

A completed receipt alone never authorizes a green aggregate. The enclosing
TCP job must also have actually succeeded according to GitHub Actions `needs`.

## Join and original reconciliation

Both existing required checks, `Backend / file` and `Backend / postgres`, depend
on the full three-shard matrix and the new TCP job. Each independently requires
both `needs` results to be exactly `success`. Failed, cancelled, skipped,
missing, partial or foreign TCP evidence cannot produce conditional success.

Each aggregate downloads the exact current SHA/attempt artifacts into separate
original directories. The joiner rejects duplicate/missing receipts or XML,
symlinks, wrong independent checkout/event/run/attempt/repository identity,
manifest or constraint drift, unequal Python/platform identities, unequal
actual installed dependency bytes, before/after source-hash drift, altered logs,
and invalid raw JUnit. Every full shard must match the TCP identity and actual
installed dependency receipt.

Downloaded originals are never rewritten. The joiner creates a fresh directory,
copies all backend artifact files with exclusive creation, validates every
copied SHA256, and adds a byte-identical copy of the independent `sync-tcp.xml`
beside the copied File receipt. Existing aggregation directories or backend
TCP XML cause refusal rather than replacement. A join report records all input
and copied hashes and explicitly discloses this local layout association.
The joiner then calls the original, unmodified reconciler, which still requires
complete ordered inventories, all original phase/outcome checks, every shard,
and both exact TCP passes. It rechecks original and copied artifact hashes after
validation. The workflow separately invokes the unchanged reconciler CLI too.

This association is only a storage-layout adaptation for the original verifier.
It does not make TCP part of the full File process or inflate complete-suite
unique counts. No old failed/cancelled receipt is repaired or joined to a new
run. Local real TCP execution and synthetic infrastructure fixtures are reported
separately. Actual hosted producer identity and end-to-end current-attempt joins
must still be established by the next exact-source GitHub Actions execution.

Run all standalone infrastructure tests with:

```sh
python -m pytest -p no:cacheprovider -q \
  .github/ci/test_suite_coverage.py .github/ci/test_coverage_reconcile.py \
  .github/ci/test_v2_manifest_extension.py .github/ci/test_v2_check_runner.py \
  .github/ci/test_v2_browser_job.py .github/ci/test_tcp_evidence.py
```
