# Project retirement: scope and legacy orphan followup

Status: **PASS for the tested retirement/orphan subset**. The pending followup is ready for review. This does not close the full R3 security/concurrency gate or establish V2 release readiness.

Audit completed on 2026-10-16 after the final combined PostgreSQL run. Git HEAD was `8f50e76af590f76da4714c651d2b9573dde7087f`; the pending source bytes below, rather than HEAD alone, identify the tested candidate. The earlier retirement checkpoint is `cd5e8ed30bf4776078c2df5597df9db97b45344d`.

## Final execution evidence

All paths in this report are relative to the repository root. Receipts and their same-stem `.log` files are retained under `docs/delivery/v2-development/`.

| Receipt | Result | Scope |
| --- | --- | --- |
| `scope-orphan-file-r3.json` | 62 passed, 47 deselected; exit 0 | Followup 19 File cases, retirement 28 File cases, existing scope/authorization/identity/API unit regressions |
| `scope-orphan-pg-r1.json` | 20 passed, 19 deselected; exit 0 | Followup 19 real PostgreSQL cases and original R3-I incarnation reproduction |
| `retirement-scope-pg-final.json` | **48 passed, 47 deselected; exit 0**, 397.74 seconds | Retirement, scope/orphan followup, and original R3-I reproduction together on the final candidate |

The final combined command selected `postgres_backend_only` from `tests/test_v2_project_retirement.py`, `tests/test_v2_scope_lifecycle.py`, and `tests/test_round3i_pg_incarnation.py`, using the original `scripts/run_v2_postgres_checks.py` and isolated `scripts/run_v2_checks.py` harnesses with collaboration runtime enabled. The backend deselections are explicit; no skip is counted as a pass. Each run reports one Starlette/httpx deprecation warning.

All three receipts record `sources_changed_during_check=false`. Independent comparison of all **2,283** recorded source hashes before/after each run found zero drift. A fresh comparison with disk after final PostgreSQL shutdown also found zero changed tested sources.

| Evidence file | SHA256 |
| --- | --- |
| `scope-orphan-file-r3.json` | `b126b324a95bf6bfd1787bcb79bb64517ccb9f9f7d527ad4a2e1b2b8471a6fd3` |
| `scope-orphan-pg-r1.json` | `ef4482154a639d798a8e0faf92a8bab1934505e121feb201d76033ed41a07568` |
| `retirement-scope-pg-final.json` | `80035ce2411598c71abc4a9863dfd0add878387851489f24b50c97df13ffc55c` |
| `retirement-scope-pg-final.log` | `840b865aa1cc28195c22ca4ddab981cf80ce87ac6582e8b89138bb5aacdd20ad` |
| `retirement-scope-pg-final-postgres-runtime.json` | `114f333e3cf530e80840cbd6dd051ededd4caaf52ebde4cdde432918b415e053` |

The final runtime receipt proves PostgreSQL **16.15**, owned loopback port **50678**, fresh database `v2_retirement_scope_final_20261016` (OID **20809**), zero application objects before migration, and all **20 original sorted migrations** applied. Startup ownership was confirmed. It records `status=PASS`, `checks_exit_code=0`, `server_stop=stopped`, and `cleanup_status=completed`; an independent `pg_ctl status` also reported no server running. The disposable database and evidence are retained. No model/provider calls or production database changes were part of this run.

The earlier `retirement-pg-r3.json` remains historical evidence with its recorded source-drift boundary; it is not the final exact-source proof. The combined final receipt above closes that evidence gap.

## Reviewed changes and assertions

The followup continues to use the original Novel, Scope, Authorization, Identity, Session, and Audit owners.

- `CollaborationScopeService` holds the original project lease across owner/parent validation and link/storyline/branch save. Existing shared PostgreSQL creation transactions keep their original session boundary.
- `AuthorizationService` verifies that the original novel exists while its existing assignment lease is held; an old binding alone cannot authorize new grants.
- `AtomicPathMutationPort` retires same-workspace pre-upgrade orphan role/permission assignments and scope rows inside the creation transaction or File snapshot. Foreign-workspace residue retains the exact 400 detail `project already belongs to another workspace`. A failed new link restores the exact old state and leaves no public orphan novel.
- Audited scope writes hold the owner lease through scope and audit commit. Original admin routes opt into pre/post mutation reauthorization; actual inactive membership at the final guard produces exact 403 `INACTIVE_MEMBERSHIP` and rolls back scope plus audit.
- Retirement removes project-specific grants, binding, storyline and branch metadata while retaining audits, workspace roles, memberships, and unrelated projects. Same public ID recreation has a new incarnation. Old actor + old session + old branch returns exact 403 `PROJECT_SCOPE_FORBIDDEN`; fresh explicitly authorized actors create/read CreativeDocuments successfully. Data, asset, idempotency, authorization, and cross-workspace controls remain in the combined suite.
- The followup adds deterministic delayed link/storyline/branch and audited-write races, legacy orphan recreation/rollback, missing-owner grant denial, and real admin membership revocation checks. Positive blank-project overview is 200 with zero chapters, `NEEDS_CONTENT`, and `placeholder=false`.

The legacy orphan fixture uses actual API deletion with only the two retirement callbacks temporarily disabled to reproduce the historical defect, and asserts the orphan preconditions. Identity, authorization, repository, and PostgreSQL operations remain real; no handwritten SQL repairs product state. The preserved baseline failure is `scope-legacy-orphan-before.json` / `.log`, HEAD `5666d53269d7029dced08129ae21a2ef47d9c59c`, exit 1 at the retained project-role assertion. Earlier fixture failures also remain retained; final exact negative assertions were not weakened.

## Exact audited source bytes

These hashes match the final combined PostgreSQL receipt, the File receipt, and current disk after execution.

| Source | SHA256 |
| --- | --- |
| `app/services/collaboration_scope_service.py` | `605fe6b9de231240f4b76fe54595db3f24ca02dbc3e060c8db637e6bcd6c1dfd` |
| `app/services/authorization_service.py` | `ad1862ae3aa21eb9547e4d9ddadf30c08a4aeff8e9a2c4a9d345548d689bd374` |
| `app/application/persistence.py` | `f34f58c6866cade1f85f1c81b9432a4cf39f3d30c07bab175c7bc3f19c4eca9d` |
| `app/collaboration_admin.py` | `47cd13de0023a40769ceedc5f3ffd32f6781e5f6013431a263da30f5e01be33c` |
| `tests/test_v2_scope_lifecycle.py` | `bb79fa723be169b98294ab156d5b0dfbec2b7f20e66eadc3073d47c35ddb2699` |
| `tests/test_v2_project_retirement.py` | `132e7332963a9972825c223ecd403fbaebffa69feb4d925a1d17f7a442b4ce85` |
| `tests/test_round3i_pg_incarnation.py` | `adf4c024d2d079618fa74dca1e8f0097695705bea762f30269eb9ed3ba2c4317` |

## Frozen-source policy and remaining boundary

The followup changes four application files and adds `tests/test_v2_scope_lifecycle.py`; it makes no new frozen test/gate edits. `protected-v1-source-audit-summary-r2.json` records all 750 protected test/gate sources unchanged from selected baseline `045b865e5a003cac3333462d055f22099f6368d6`. Its single portable-entry `-B` migration relative to the older manifest was already present at that baseline and remains explicitly documented.

The frozen `.github/ci/coverage_manifest.json.gz` remains SHA256 `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`. Only the additive V2 manifest was refreshed, SHA256 `5dfb54185bf3f74d3c1457624ebd17f5d51fcf6b6166be009d5dd7116a8cf16f`. `additive-ci-collection-pytest8-pinned-verification.json` records pinned pytest 8.4.2 collection of 14,910 nodes, all 9,151 frozen nodes retained in order, unchanged historical skips/external gates, and current source hashes. This is inventory evidence, not a full-suite execution claim.

Remaining R3 work includes broader Prompt authoring/adoption, tombstone/deletion, write-time binding, all-route authorization and concurrency acceptance. The admin tests here prove revocation before the final checkpoint; they do not establish a general session/membership lease through commit or exhaustive ABA interleavings. Raw writes outside participating product lifecycle methods are outside this acceptance scope. File storage uses compensating snapshots and quarantine/reclaim behavior; these receipts do not prove power-loss atomicity. Browser workflows, real model execution, GPU behavior, paid providers, packaging, and full V1 runtime acceptance require their own evidence.

No application/test source was changed by this final audit, and the auditor did not commit or push.
