# One V2 parameter ID migration

The preexisting `object()` illegal-version case used its process-specific `repr` as its pytest ID. Full V2 backend CI compares literal ordered inventories and hashes literal node IDs for sharding; the old pointer-bearing ID could therefore reject a new process's collection before test execution. The original frozen 9151-node inventory does not contain this V2 test module.

The only source edit is the `ids` expression on `test_illegal_version_is_refused` in `tests/test_v2_graph_schema_version_gate.py`:

```python
ids=lambda value: 'opaque-object' if type(value) is object else repr(value)
```

All thirteen illegal inputs, their order, every test body and assertion, and the other twelve literal `repr` IDs remain unchanged. No test is removed, skipped or weakened. No CI gate, normalization rule, skip policy or coverage manifest was edited by this slice.

`graph-schema-stable-id-migration-proof.json` records a raw-byte proof: one exact expression replacement, all other bytes identical. It also verifies the entire module AST is identical after restoring only the old `ids` expression, the input-expression AST and body AST are unchanged, thirteen inputs remain, and the first twelve generated IDs are identical. The original full source bytes are retained in `graph-schema-stable-id-before.py.txt`.

- Old source SHA-256: `f8a8d53a4cf3772238b9eda2b5952ccd339ad7c4ab3e49e31948c2e0eb9c8966`.
- New source SHA-256: `3808d405b39b9256b22147d691a10848734ef1b45d0ace78bd860ed78274e0d4`.
- Old HEAD node: `tests/test_v2_graph_schema_version_gate.py::test_illegal_version_is_refused[<object object at 0x000001B9BFA0FCC0>]`.
- Intermediate collection node: `tests/test_v2_graph_schema_version_gate.py::test_illegal_version_is_refused[<object object at 0x000001A6538420D0>]`.
- Stable node: `tests/test_v2_graph_schema_version_gate.py::test_illegal_version_is_refused[opaque-object]`.

These are an explicit one-case ID migration, not permission for a broad pointer normalization or a claim of literal preservation of the old pointer ID.

Pinned verification `r3-schema-id-module-ci-r1`: **225 passed in 8.36s**, covering the entire affected module and original `.github/ci/test_suite_coverage.py`, `test_coverage_reconcile.py`, and `test_v2_manifest_extension.py`. Exact runner log and source receipts are retained beside this report and at their original `docs/delivery/v2-development` paths. This result is the affected module plus CI selfchecks; it does not claim execution of the full product inventory or a hosted CI run.

The root agent owns the separate additive V2 manifest refresh and two independent full collection comparisons after both test slices freeze. The frozen V1 manifest remains byte-identical with SHA-256 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.
