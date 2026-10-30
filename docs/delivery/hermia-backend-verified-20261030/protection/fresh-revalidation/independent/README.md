# Fresh independent recovery review (2026-10-30)

This is new evidence, not the missing historical 25-case review or historical joint-suite logs.

## Provenance and results
- Fixed source: `342ad72626667d622040d8eca4d6c9ab8d1e2309`, tree `3b6b7984d3c782b051e8754b94205cc14b6c9bb9`.
- Counterfactual: `bd19e6a2923c6e9c515045264990f386e9c4c64b`, tree `71df909242415543d380c5d229838e85d40389a7`.
- Each source was independently extracted with `git archive`, outside the recovered working tree. Identical new test file was placed under each archive's tests directory. Existing frozen fixtures were imported; no production edits.
- Fixed: **14 passed, 3 warnings in 7.56s; exit 0**.
- Counterfactual: **4 failed, 10 passed, 3 warnings in 7.35s; exit 1**.
- All 611 app files have equal before/after SHA256 and match the fixed Git source blob content. Loaded module paths and hashes are in provenance.json.

## Scope of the 14 fresh cases
- Four cooperative cancellation scenarios: other-owner callback, return without callback, late provider exception, same-owner callback. Verify no replay, stable cancelled record, no result/artifact, released local bookkeeping and execution claim.
- Two normal success/failure cases: actual synthetic download bytes and retained provider timeout error; claim/bookkeeping release.
- Two mounted-API inherited-expired-scope cases (/api and /api/v1): TaskCenter read does not write or inherit stale scope, caller context restored, actual export POST and download with independent running-owner observation.
- Four final TTL cases: empty and continuation pages on both API prefixes reject expiry after last capture, no-store and no read-path writes.
- Two actual aggregate-reader denial cases: empty export source returning 403 only inside WorkspaceToolsService.tasks yields sanitized 501, not a successful empty page; no-store and no writes.

## Counterfactual interpretation
The predecessor already has integrated request/TaskCenter/export-ownership protections. The diff to fixed is exactly export_job_service.py plus its original regression-test file (patch included). Four failures do not mean fourteen distinct defects: callback continues past cancellation; return writes an orphan artifact; exception and same-owner cancellation retain Future bookkeeping. The other ten cases pass on both revisions. This establishes sensitivity of the new cancellation tests, not an independent causal claim for earlier protections.

## Commands and isolation
Interpreter: <CLOUD_WORKSPACE>/studio-overnight/.venv/bin/python. No installs.
Fixed cwd: <TEMP_PATH> Command:
```
XDG_DATA_HOME=<TEMP_PATH> NOVEL_DATA_PATH=<TEMP_PATH> PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=<TEMP_PATH> <CLOUD_WORKSPACE>/studio-overnight/.venv/bin/python -m pytest -q tests/test_recovery_independent_20261030.py --junitxml=<TEMP_PATH> > <TEMP_PATH> 2>&1
```
Counterfactual uses cwd/PYTHONPATH baseline, base-xdg, base-runtime, baseline.xml and baseline.log under the same parent. Exit files preserve actual process status. Pytest tmp_path supplies synthetic job data; no user runtime data or external provider calls.

## Limits
Mounted FastAPI TestClient, not a live TCP server. POSIX/File synthetic workloads; no Windows, PostgreSQL, real provider or whole-Studio validation claim. Cancellation is cooperative at callbacks and return boundaries, not immediate termination of a blocked provider. Existing FastAPI and Pydantic warnings are retained in raw logs. Broader joint-suite evidence is separate.
