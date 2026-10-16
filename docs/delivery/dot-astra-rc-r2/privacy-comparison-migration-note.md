# PostgreSQL comparison correction after R2 privacy migration

The safety-batch GitHub PostgreSQL 16 run at `78920f2` reported one failed parity
check (1 failed, 1,660 passed, 37 skipped). The comparator called its PostgreSQL
semantic serializer output “raw” but compared it with unmodified legacy File JSON.
The fixture omits character/location privacy, whereas migration correctly produces
`LOCAL_ONLY` / `UNKNOWN`. This was an inconsistent comparison contract, not a
reason to restore permissive defaults or strip PostgreSQL privacy fields.

`compare_context_backends` now projects legacy File policy using the same
fail-closed interpretation before the raw comparison. All original nonprivacy
fields and array order remain compared. Original File bytes are never rewritten.
The PostgreSQL side is deliberately not normalized. Reports identify
`FAIL_CLOSED_PRIVACY_PROJECTION_V1` and list each original versus effective File
policy. Missing, invalid, loosened or otherwise different PostgreSQL output still
fails; exact semantic/context-pack comparisons remain unchanged.

Four independent tests in `test_r2_context_privacy_compare.py` verify byte
preservation, explicit policy retention, detection of a LOCAL_ONLY→CLOUD_ALLOWED
regression, detection of missing PG policy, nested nonprivacy content changes and
array-order changes. Local focused result: 5 passed, 1 PostgreSQL-only skip
(including the existing comparator unit). Real PG re-verification belongs to the
next exact-commit CI receipt; it is not claimed from this local check.
