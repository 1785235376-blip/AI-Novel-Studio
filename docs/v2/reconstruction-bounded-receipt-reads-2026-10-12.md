# Reconstructed bounded Video/Timeline receipt reads

## Source and scope

This is a new, tested reconstruction against published source
`de23bb50b96f07dac3e96dc0f9a1df9940e494b3`, not a recovery of missing implementation
bytes. The recovered historical feature-matrix blob
`cbe4fdcc6977712053165e29eaa81f319377cfe8`, checkpoint 21, describes enforcing the
original receipt byte limit during reading and rejecting unstable snapshots.
That historical entry is a requirement reference, not current test evidence.

The concrete baseline defect was in
`app/services/video_assembly_service.py::_studio_load`: a size check followed by
an unbounded text read. Deterministic races on real temporary receipt files
reproduced oversize acceptance and acceptance of changed snapshots.

Only the original owner's receipt-read helper changes. The original read, list,
video execution, compare-and-swap update, and mutation paths reuse it. Legacy V1
assembly, receipt writing, owner/path checks, feature gates, digest and graph
validation, permissions, queue ownership, callbacks, and locking remain unchanged.
No existing test or fixture was edited.

## Read contract

- Keep the original 384,000-byte receipt limit, including exact-limit UTF-8 JSON.
- Open once in unbuffered binary mode; read at most 384,001 bytes. The extra byte
  is an overflow sentinel and is never admitted as receipt content.
- Compare device, inode, size, nanosecond modification time, and change/creation
  time before opening, on the opened descriptor, after reading, and at the path.
- Reject short reads even if their returned prefix is valid JSON.
- Reject observable replacements and in-place changes before decoding and before
  the original receipt identity, digest, and graph-binding validation.
- Preserve the existing limit/invalid/not-found failure contracts and close the
  read handle on success and failure. There is no automatic retry or new writer
  lock.

This is a bounded same-file read with filesystem-metadata checks, not an
OS-level atomic snapshot or protection against every hostile metadata rewrite.
POSIX change time detects a same-size write even after modification time is
restored. Windows creation time does not provide that guarantee; the dedicated
POSIX test is explicitly marked. Windows may deny replacement/removal while the
handle is open. The tests distinguish that OS-denied mutation from race detection.
Actual Windows execution was not run.

## Verification

The unchanged `scripts/run_v2_checks.py` retained isolated before/after receipts
and source hashes. Final verification used the exact production and test hashes
below, with no source changes during either run.

| Check | Result |
| --- | --- |
| Initial additive reproduction on untouched baseline | 12 failed, 17 passed, 1 canonical PostgreSQL skip |
| Final File/neutral owner and original media/workspace regressions | 170 passed, 117 canonical backend skips |
| Final real PostgreSQL owner/workspace regressions | 117 passed, 151 deselected |
| Independent source review | No blocking defect within the stated scope |
| `git diff --check` | Passed |

The final PostgreSQL run used the original
`scripts/run_v2_postgres_checks.py --fresh-database` owner. It created a distinct
new database from `template0`, verified zero application objects before migration,
applied all 20 original migrations, verified live PostgreSQL 17.11 identity, and
stopped its owned server cleanly. Both databases and diagnostic evidence were
retained privately.

The additive tests cover exact byte limits, post-stat growth, overflow even when
size is subsequently restored, replacement before open, post-read changes,
valid-JSON short reads, malformed bytes, missing receipts, unchanged identity and
digest validation, graph validation, feature-off/V1 overrides, denied guards,
original owner list/video/CAS paths, and real File/PostgreSQL project incarnation
reopen behavior. They do not replace or relax original tests.

### Diagnostic attempts retained

- A manual PostgreSQL startup could not create a Unix-domain socket; TCP-only
  startup succeeded.
- The first manual PostgreSQL test invocation omitted schema initialization and
  produced 117 setup errors before product assertions. After applying the
  original migration sequence, the manual rerun passed 117 tests. The final
  authoritative run used the original harness and a different fresh database.
- An additional File-plus-catalog invocation produced 171 passes, 117 canonical
  skips, and one catalog source-hash failure. The baseline catalog was already
  stale for 27 application files; this owner also requires an updated hash.
  Catalog regeneration belongs to the final integrated source tree. The catalog
  assertion remains unchanged and this task does not claim it passed.

### Reproduction commands

Use an existing trusted Python environment, the official PostgreSQL binaries,
and a disposable cluster owned by this checkout. Variables below are local
operator inputs, not captured environment configuration.

```sh
python scripts/run_v2_checks.py receipt-bounds-file-verified -- python -m pytest \
  tests/test_v2_studio_receipt_bounds.py tests/test_r2_media_lifecycle.py \
  tests/test_v2_independent_workspace.py tests/test_v2_independent_workspace_api.py \
  -q --tb=short --basetemp .runtime/receipt-bounds-file-verified

python scripts/run_v2_postgres_checks.py --pg-bin "$PG_BIN" --data "$PG_DATA" \
  --port "$PG_PORT" --user "$PG_USER" --fresh-database \
  --database "$UNIQUE_V2_DATABASE" receipt-bounds-pg-verified -- python -m pytest \
  tests/test_v2_studio_receipt_bounds.py tests/test_v2_independent_workspace.py \
  tests/test_v2_independent_workspace_api.py -q --tb=short -m postgres_backend_only \
  --basetemp .runtime/receipt-bounds-pg-verified
```

### Verified source hashes

- `app/services/video_assembly_service.py`:
  `a1fcf5983c506ec57636c63d73abcaa4f0f3865b18ca7f139b521edde95f8343`
- `tests/test_v2_studio_receipt_bounds.py`:
  `3b10b28669e3a8e7ba83b8b45cd70c3a9abf6a97a2a98bce51923d033a2b41b2`

Raw logs, databases, runtime profiles, private paths, and captured configuration
are not included in this publication. Browser/frontend, full-suite, hosted CI,
Windows, GPU, and model-quality acceptance were not run for this scoped change.
Historical module classifications remain unchanged.
