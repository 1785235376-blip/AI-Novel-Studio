# Independent adaptation fixture review

Verdict: PASS within the test-only repair scope. No blocking findings.

Reviewed frozen worktree `${WORKSPACE}/studio-adaptation-fixture-repair`, canonical base `5eb983fd620ef905aa4dc1afae80b756ee7e7078`. Authorization test SHA256: `ec890d7caccc020780ba81a007d0de9e96dffedd80b18cca1fb49f628de1dd96`.

## Findings

- All tracked files were compared byte-for-byte with `git show <base>:<path>`. Only `tests/test_phase7_adaptation_authorization.py` differs. All 595 tracked app/src files match canonical base. Full production/source hashes are in `source-hashes.json`; changed-file result in `tracked-difference.json`. No production or other manual-review code was edited by this review.
- Module-local autouse fixture explicitly enables only `branch_manuscript_v1`, clearing acceptance-mode override using pytest monkeypatch. No owner, permission function, route, or authorization service is replaced.
- Branch fixture creates its chapter through the original authenticated collaboration chapter POST route. The resolved registered admin session is then passed to original `collaboration_application_service.update_chapter` with actual version. Production implementation checks domain.write, feature gate and branch owner on create/update. Mainline remains a distinct title/content/id decoy.
- Existing member read/write 403, invalid session 401, lead create/read/approve, content-free audit, materialized chapter, and same-project idempotence assertions remain. Additional valid foreign-workspace actor and mismatched branch assertions strengthen 403 coverage. No role grants were broadened by the repair.
- Snapshot/source document equality and target chapter document equality, distinct chapter IDs and nonempty body assertions establish real original branch-owned snapshot/materialization, rather than a substituted fake or mainline fallback.
- Disabled flag GET and POST both return exact 404 EXPERIMENTAL_FEATURE_DISABLED / branch_manuscript_v1 responses.

## Independent executions

Exact invocations are printed in corresponding stdout and `run.sh`; independent wrapper `run.py` checks actual worktree import locations, denies external socket connect/create_connection, and verifies EXPERIMENTAL_FEATURES / V1_ACCEPTANCE_MODE restoration after every test. Uses shared existing .venv, separate fresh HOME/XDG/config/data/tmp/cache, file backend, memory credential vault, mock provider, no real API keys/database URLs.

1. Authorization file first, original compatibility file second: **10 passed**, 4 warnings, 9.94s. See `reverse.stdout` and `reverse.xml`. Both variables were absent before and after every test, including crossing the module boundary.
2. Authorization file with initial EXPERIMENTAL_FEATURES=adaptation_lifecycle_v1 and V1_ACCEPTANCE_MODE=true: **5 passed**, 4 warnings, 9.60s. See `sentinel.stdout` and `sentinel.xml`. Both original nonempty values restored after every test, including flag-disabled test.
3. `git diff --check`: passed.

Warnings concern existing Pydantic `schema` fields shadowing base attributes; no new warning mechanism was introduced.

This is bounded file-backend adaptation fixture review, not a full-project green claim. No PostgreSQL, live provider/model, frontend, deployment, or other manual-review validation is asserted. The original 5P3F baseline and flag-only 2P1F experiments are implementer evidence, not independently rerun here.
