# Backend package-download cache

## Scope and ownership

- Source baseline: `e6ff3431cf84b01b77cd1bd73a977fd5e784447b`.
- Owner: B, in an independent worktree. A owns final integration, publication,
  API catalogs and explicit V2 inventory regeneration.
- Changes: two backend job cache configurations, four new infrastructure tests,
  this report and their original local test receipts.
- No product source, existing test, manifest, gate, timeout, test assignment or
  assertion is changed. This stage does not establish complete product coverage.

## Change

`backend-execution` and `backend-tcp` use the existing official
`actions/setup-python@v5.6.0` pip cache. Its dependency key inputs include both
`pyproject.toml` and `.github/ci/python-constraints.txt`. Python remains 3.12.9
on hosted CI. No new action or package is installed.

`PIP_CACHE_DIR` is fixed at the runner's temporary package-download directory.
Without an explicit location, `prepare.sh` and the V2 isolation step change
HOME and XDG_CACHE_HOME after setup-python, so pip would use a different cache
from the one restored by the action. The new test exercises this exact
three-HOME transition using real `pip cache dir` subprocesses.

Only pip's download/build cache is restored. Application HOME, runtime state,
databases, installed environments, receipts and secrets are not cache paths.
Every job still installs from its exact checkout, executes `pip check`, and
records the installed dependency freeze, including cache hits. `pip cache info`
adds bounded cache diagnostics to existing receipts. Cache misses follow the
original installation path. The four new self-tests run inside the existing
10-minute TCP infrastructure budget, without consuming the File suite budget.

Official behavior references:
- [setup-python v5.6.0 caching inputs](https://github.com/actions/setup-python/blob/v5.6.0/docs/advanced-usage.md#caching-packages)
- [pip cache behavior and location](https://pip.pypa.io/en/stable/topics/caching/)

## Evidence and honest capacity boundary

Archived e6ff hosted jobs show only 19 seconds (push) and 17 seconds (PR) in
File dependency installation. Their complete-suite steps then ran for 1,116
and 1,119 seconds before cancellation. A package cache can reduce repeated
network work; it cannot credibly be presented as solving this 20-minute limit.
No speedup has yet been measured on a hosted cache hit.

- [Push File job](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38070247951/job/114266005180): cancelled.
- [PR File job](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38070252155/job/114266017679): cancelled.
- [Push PostgreSQL shard 0](https://github.com/1785235376-blip/AI-Novel-Studio/actions/runs/38070247951/job/114266005103): cancelled; its original event evidence also contains a failed call. This failure remains open and is not reduced to a capacity label.

No test count is inferred from elapsed time. PR PostgreSQL success does not
replace push failure, and this cache change does not clear either required
backend join. Historical independent review remains BLOCKED.

## Local verification

- Python 3.12.14, supplemental to hosted Python 3.12.9.
- Focused cache/TCP/browser infrastructure: **109 passed**, 3.15 seconds.
- Entire `.github/ci` infrastructure directory: **280 passed**, 12.34 seconds.
- `pip check`: no broken requirements. `git diff --check`: passed.
- Original full-suite execution step, unrelated frozen jobs and gate/helper
  hashes were checked by the unchanged existing tests.
- Frozen V1 manifest SHA256 remains
  `6457dd4cae85adee42486ef503fdb1cdabcdaf6eb9667eff3e2e97d05d040262`.

Local setup reused a private copy of the existing cloud test environment,
redirecting only that copy's editable source mapping to this worktree. The
default interpreter lacked pytest; an offline editable reinstall also lacked
setuptools and did not execute tests. No files in A's environment were changed.
No claim of a fresh dependency installation or hosted execution is made.

## Integration and risk

The changed workflow and new infrastructure source must be included when A
explicitly regenerates the V2 source inventory before publication. Do not push
this standalone commit with an outdated source manifest and label it a pass.
The existing full-suite command, File=1/PostgreSQL=2 assignment, 20/55-minute
caps, required names and strict reconciliation remain mandatory.

Remaining risks: cache restore/save overhead may offset the small download
saving; first runs are cold; failed/cancelled jobs may not populate a cache;
hosted behavior and exact final-source CI remain to be verified after A's
integration. The next independent task attributes existing runtime evidence
without weakening the frozen monolithic File contract.
