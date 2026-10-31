# Core semantic integration and focused checks

Status: implementation and focused Windows File checks passed for the groups
below. These development runs used mutable integration source and are **not**
the later frozen-copy acceptance attestation. Each run used the existing
`scripts/run_studio_backend_tests.py` isolated File/Mock shell, synthetic data,
external-network blocking and loopback allowance. No model was invoked.

## Production changes beyond ordinary B merge

- `UsageReadBudget.read_json_bytes` preserves the actual admitted bytes for the
  original snapshot/CAS owner; existing `read` still returns decoded text and
  maps invalid UTF-8 to the same resource-unavailable error. The lexical shape
  guard runs before any allocating owner JSON decoder.
- `ExperimentalStore._file_bytes` selects that optional reader whenever a
  request budget is active. Initial snapshots, committed captures, no-op lease
  exit CAS and first-creation revalidation therefore share the same cumulative
  attempts/bytes/shape counters. `_file_snapshot` keeps B duplicate detection
  and lifecycle validation; budgeted recursion/Unicode failure is sanitized.
  Missing before initial admission keeps the original missing-file policy;
  disappearance after admission is a resource refusal, never fake empty data.
- Identity combines A admission with B unique keys and lifecycle retention.
  Scope and authorization retain B `_write` decorators and metadata validation;
  their JSON parser now also rejects duplicate object keys.
- Export retains B serialization, same-file private metadata, pure observations
  and legacy public maps. Its one original document reader consults an active
  usage budget and rejects duplicate keys. The original malformed JSON/missing/
  non-object fallback is preserved. Invalid lifecycle metadata and duplicates
  raise rather than masquerading as a reliable empty observation.
- Main retains both middleware additions, with the usage request budget still
  registered last/outermost. TaskCenter remains outside the usage HTTP budget
  enrollment; the Export read hook is opt-in through an already active budget.
- The coordinator itself is unchanged from A, including its original compatible
  lock initialization and strict existing-only RLock/reentrancy/native locking.

## Focused development evidence

| Group / exact selectors | Result | Raw log |
| --- | --- | --- |
| `test_taskcenter_store_lifecycle.py test_identity_binding_rebuild.py test_taskcenter_scope_grant_observation.py test_export_owner_readonly.py test_export_local_window_observation.py test_studio_asset_usage_budget.py test_studio_asset_usage_budget_guards.py -q` | 141 passed, 3 warnings; 13.41 seconds; exit 0 | `core-initial.log` |
| `test_file_backend_safety_integration.py test_studio_asset_usage_strict_coordination.py test_studio_asset_usage_authority_budget.py -q` | 74 passed, 3 warnings; 11.45 seconds; exit 0 | `core-integration.log` |

All selectors above are under `tests/` and were passed to the same existing
runner. Groups are not summed as a unique global total. Warnings are the existing
Starlette TestClient and Pydantic schema-shadowing warnings; no package install
or dependency change was made to hide them.

New core probes verify byte-exact whitespace snapshots; every no-op CAS reread
charged; committed observations while an active buffer differs; budget failure
clears active transactions and later original writes succeed; duplicate-key and
corrupt-lifecycle refusal in all five owners; oversized/deep/long-string/long-
scalar/too-many-token admission before decoding in all five owners; pre-open
growth/replacement/disappearance; short-read accounting and native handle
release; strict zero filesystem/registry change on initialized facilities;
missing strict facility refusal; lifecycle ABA remains invalidated; and Export
legacy malformed fallback plus hidden metadata/read amplification.

Tests do not claim stronger ABA, whole-application budgets, POSIX execution,
PostgreSQL, browser, hosted CI, real model/GPU, RSS bounds, hard lock deadlines,
cross-file crash atomicity or power-loss durability. Root-owned frozen-copy
HTTP/process/independent runs must supply their own source receipts before those
specific supported behaviors can be labeled verified.
