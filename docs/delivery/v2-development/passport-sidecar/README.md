# Bounded Production Passport unsigned sidecar

Base: `1d6a17f024dca193167b1eff30b73436b7c2ec5d`
Worktree: `/workspace/scratch/20a0022d2b33/studio-passport-sidecar`
Branch: `feat/production-passport-sidecar`
Incremental staged patch: `production-passport-sidecar.patch`
Patch SHA-256: `e0fbc239cea4839659d4c377be0302b2e12b257f1234a48b2d0a774aad13c77c`

## Implemented boundary

One original Media-approved image selected from an existing immutable Production manifest downloads as a deterministic unsigned ZIP: exact original output bytes, redacted JSON, and human-readable TXT with identical evidence fields. Read-only original Media/Asset owners, no persistence, approval changes, replay, model dispatch, or new provenance store. Original public JSON export unchanged.

Checks original manifest payload integrity and membership; task/proposal/asset bindings and approval receipts; bounds/rehashes the exact captured proposal bytes and original Asset bytes; gates current source/privacy; traverses bounded authorized original Asset lineage; revalidates snapshots and terminal current-owner metadata including ancestor chapter pins and root/proposal eligibility. Fresh original route authorization is checked throughout bounded reads and immediately before returning the byte response. No cross-owner lock or write transaction introduced.

Explicit limitations: unsigned, no C2PA/signature/authorship verification, no legal copyright certification, free text represented by digests, only approved original Media images, no completed-film/Comic-chain acceptance, full DIF-12 not accepted. Revalidated multi-read evidence is not an atomic cross-owner transaction; post-response revocation does not retract a previously returned download. Missing and denied evidence is not fabricated or disclosed.

## Verification

File: 47 passed, 47 optional actual-PostgreSQL cases deselected. Includes 25 new Passport cases and 22 existing lineage cases. `backend-file-final.log` and `backend-file-final.xml`.

Command (repository root):

    XDG_DATA_HOME=/tmp/passport-test-data /workspace/scratch/20a0022d2b33/studio-director-transport/.runtime/recovered-python-20261018/bin/python -m pytest tests/test_production_passport_sidecar.py tests/test_r4_production_lineage.py -m file_backend_only -q --disable-warnings --junitxml=/workspace/shared/passport-evidence/backend-file-final.xml

Frontend: 105 targeted tests (37 new), TypeScript and token guard passed. Logs are `frontend-vitest.log`, `frontend-tsc.log`, `frontend-token-guard.log`.

Visual/geometry attempted but Chromium could not launch (local socket EPERM); approved escalation also blocked by environment bwrap read-only runtime path. No visual acceptance claimed; no baselines changed. Details `/tmp/production-passport-visual-results/` and config `/tmp/production-passport-visual.config.cjs`.

Independent code review identified and verified fixes for second-pass stale eligibility, unbounded preview reread, and ancestor-only chapter fencing; bounded code-review clear. Actual PostgreSQL, native Windows, browser geometry and end-to-end full DIF-12 remain pending/not accepted. No model/API calls, installs, PG startup or pushes performed by implementation worker.

Only seven scoped source/test files in patch. Untracked frontend/node_modules symlink is an existing-dependency test aid and is excluded.
