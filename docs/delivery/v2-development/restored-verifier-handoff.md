# Restored-file verification handoff

## Scope and frozen source

Isolated branch: `work/dot-restored-verification-20261017`.
Baseline: `d10b72c1bc2db33dc2dff85af4f31ede478cf1fc`.
This is an additive offline File-byte verification command in the original recovery
module, plus new tests and a new guide. Existing tests, indexed guides, default
backup/restore behavior, application startup, and live data-root selection are not
changed. Runtime/dependencies are excluded from delivery.

| File | SHA-256 |
| --- | --- |
| `app/backup_restore.py` | `a0bfd17bd268581d41b7a0347e376f6c0895338b9cea16a7a86c2c8981cc6a62` |
| `tests/test_restored_file_verification.py` | `2f66a923a30ad21560b35a626de34eb90f6e12510d079df930f62cbc6bc78b22` |
| `docs/RESTORED_FILE_VERIFICATION.md` | `5cc6204762f57db89347e381029bea71a376842b4d0e2d9534cd3b3464130a62` |
| unchanged `scripts/run_v2_checks.py` | `64cf16c26412c5a1e36a1d4fb799519111ad409f7594ae15aa0b158e53396cd5` |

## Primary verification

Original runner label `restored-verifier-primary-r1`, 2026-10-17
10:02:49–10:03:00 UTC: **69 passed, 2 warnings**; pytest elapsed 7.45 seconds.
Normal original `tests/conftest.py` was enabled. Selected tests:

- `tests/test_restored_file_verification.py`
- `tests/test_r2_backup_restore.py`
- `tests/test_asset_lifecycle_r2.py::test_delete_recover_and_restart_preserve_original`

The command was the unchanged `scripts/run_v2_checks.py LABEL -- python -m
pytest -q -x ... --basetemp OWNED_PATH`, not a direct-pytest substitute. The runner
used a dedicated label/profile and basetemp under this worktree. The parent
process was launched with a clean `env -i` environment, owned HOME/USERPROFILE,
APPDATA/LOCALAPPDATA/XDG/data/temp paths, File storage, memory credential vault,
mock providers, cloud disabled and model downloads offline before runner import.

| Evidence | SHA-256 |
| --- | --- |
| [Primary receipt](restored-verifier-primary-r1.json) | `22e8501145d417a327ed2c1c6c694861a029ecabe40e28ca6781922df32e839b` |
| [Primary log](restored-verifier-primary-r1.log) | `fa45cc9f2b847e27173f65f76728fcd14ad5f13fcda9e963177050efb02ae6ae` |
| [Runner-child origin receipt](restored-verifier-runtime-proof-r1.json) | `89b334751ca9bc0602904fc01a127047ac2140b33cd20b9f9eee918ffba4d3c4` |
| [Runner-child origin log](restored-verifier-runtime-proof-r1.log) | `57790b5d85dfcab8fb817a8747dfb51cf5320e09bbf9b9a683f6d352726a8fcc` |

Both retained receipts were audited after the gate: exit 0/PASS, unchanged
before/after/current hashes for all 2601 bound source files, and matching log
SHA-256. The guide is separately bound above because runner snapshots omit docs.
Two warnings were existing Starlette/httpx deprecation and a Pydantic `schema`
field-name warning; neither was suppressed.

## Interpreter origin and fresh CLI evidence

Before the runner, a natural Python process asserted its prefix and pytest module
origin. This passed at 10:02:32 UTC; its output was captured in orchestration tool
output, not a separately retained log. The subsequent actual original-runner child
proof independently asserted the same origin and retained the receipt/log above:

- Executable: `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1/bin/python`
- Prefix: `/workspace/scratch/20a0022d2b33/studio-ci-reconciliation/.runtime/ci-reconciliation-python-r1`
- Base prefix: `/opt/codex/runtimes/codex-primary-runtime/dependencies/python`
- pytest 8.4.2 loaded from that environment's `lib/python3.12/site-packages/pytest/__init__.py`
- No injected origin substitutes, package installation, or alternate Python.

The new test runs actual `python -m app.backup_restore verify-restored` child
processes for success and failure, with a synthetic `sitecustomize` exit observer
asserting no `app.main`, `app.api`, `app.runtime`, or `psycopg` module imports.
The successful sentinel is required in stderr. This no-startup claim applies to
the standalone CLI child, not the normal pytest process whose original fixtures
import app.main. Asset reopening separately uses the original AssetLibraryService.

## Independent review and verification

Serialized independent original-runner verification passed the same 69 tests,
with the same two warnings, in 7.49 seconds. It used the original conftest and
fresh owned profile/basetemp, without product/test changes. The independent
natural-process proof additionally confirmed the imported recovery module came
from this worktree; actual runner-child origin proof confirmed the clean runtime.

| Evidence | SHA-256 |
| --- | --- |
| [Independent natural origin log](restored-verifier-independent-natural-r1.log) | `961cf79bebf3234ec5c2bd963cea95f3d3820b097c75ed452320f4ee113ce80d` |
| [Independent runner-child origin receipt](restored-verifier-independent-origin-r1.json) | `a508b5caf66ddcbcbce738c91bb029bbeee9d0af6cb7597f1f6141169bf757d4` |
| [Independent runner-child origin log](restored-verifier-independent-origin-r1.log) | `548e9d07003ef119da146b459a03ffe9b9bacd7aa2312d8c8393e29b55d8da04` |
| [Independent test receipt](restored-verifier-independent-r1.json) | `0780c0f36c47c58ef14a2b10604fb8c179fe8505c43ac608d956320659263a22` |
| [Independent test log](restored-verifier-independent-r1.log) | `1b722375b84dc8ade322e740a77e144cbcaa92fac36b018a2b4e7acf100bc778` |
| [Independent audit](restored-verifier-independent-audit-r1.json) | `d846ea4e5c666b5ecd1826bc7d45f38b4a6cc1715c515fb031fda438e219fdb1` |

Independent audit confirms matching primary/independent before/after/current
source maps (2601 files), matching log hashes, and unchanged original runner,
conftest and old tests. The original indexed backup guide is also unchanged.

## Limits and acceptance boundaries

Success means matching restored File bytes only. It explicitly reports
`application_compatibility=not_verified`, `switch_performed=false`, and for
PG-containing backup sidecars `database_validation=unsupported`. The synthetic PG
dump test is not a real PostgreSQL backup/restore validation.

Trusted, stopped-writer directories are mandatory. There is no atomic snapshot,
lock, adversarial filesystem guarantee, or backup authenticity guarantee. Root
and ancestor symlinks (even legitimate ones), member symlinks, hardlinks, special
files, incomplete markers, unexpected files/empty directories, incompatible
receipts and malformed manifests fail closed with bounded redacted error codes.

Limits: 100,000 combined unique root/file/directory entries per tree or expected
membership; depth 64; manifest path 4096 characters; manifest and expected JSON
credential checks 16 MiB each; receipt 64 KiB. Actual JSON reads are capped before
parsing in the new command; original command defaults remain unchanged. Streaming
hashes have no total-byte or elapsed-time cap. Parsed JSON can occupy more memory
than its encoded bytes. Metadata rechecks detect ordinary changes, not malicious
replacement races.

No live user files, live root switch, service startup, repair/deletion, real PG,
provider/browser, Windows PowerShell/ACL/desktop execution, push, or main-branch
integration was performed. These remain separate acceptance gates.
