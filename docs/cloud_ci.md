# Cloud CI scope and evidence

`.github/workflows/cloud-ci.yml` runs on pushes, pull requests, and manual dispatch.
All three jobs are required evidence: full Python File suite, full Python suite
against a disposable PostgreSQL 16 service, and frontend unit tests, TypeScript /
Vite build, design-token lint, and five browser geometry checks. Failures are not converted to optional checks.
Existing backend-only pytest markers determine File/PostgreSQL applicability;
there is no CI test exclusion list. A CI plugin fails the PostgreSQL job if any
`postgres_backend_only` contract skips, including unavailable-database skips.

The runner uses Ubuntu 24.04, Python 3.12.9, Node 22.14.0, and pnpm 10.6.5.
Python installation uses `.github/ci/python-constraints.txt` with the project's
`.[dev]` requirements. Frontend installation uses the checked-in pnpm lockfile
with `--frozen-lockfile`. Update tool versions and constraints deliberately and
rerun all checks when changing them.

## Isolation

The workflow exports the checked-out commit into a fresh runner temporary tree.
Tests execute from that copy. HOME, USERPROFILE, APPDATA, LOCALAPPDATA, XDG
config/cache/data/state, application data and Python temporary directories are
isolated below that tree. No user `.env`, production database, credential vault,
or model cache is copied. Checkout credentials are not persisted, workflow token
permissions are read-only, and repository secrets are not passed to jobs.

MOCK_PROVIDER is true, ENABLE_CLOUD is false, the vault is process-memory only,
and Hugging Face / Transformers offline flags are enabled. Tests may override
settings to exercise mocked failure/security contracts, but CI config supplies
no live provider keys or running model services. PostgreSQL credentials are
fixed throwaway service-container credentials, not user secrets. All SQL
migrations run on the disposable database before tests; failure stops the job.

## Receipts and limits

Every job uploads only its dedicated receipts directory, including exact
checked-out SHA, event SHA, run URL, machine-readable JUnit test counts, logs and
tool/dependency versions. Pull-request checkout may be a GitHub merge SHA; use
`checked_out_sha` from the receipt to identify what was tested. Artifacts are
named `backend-file-<event-sha>`, `backend-postgres-<event-sha>` and
`frontend-<event-sha>`, retained for 14 days and uploaded even after failure.
No home/data trees, database dumps, `.env` files or vault contents are uploaded.
JUnit missing output is labeled NOT RUN, never a pass. The job conclusion is the
authority for success: counts alone do not certify installation, build or lint.

Native Windows host, AppContainer, WebView2, installer execution, Windows screenshot golden comparisons, real local models and paid cloud providers are NOT RUN by this Linux
workflow. Source-level contracts may run, but cannot certify those environments.
A workflow definition or a local smoke test is not proof of a successful hosted
run; use the actual GitHub run and its exact-revision receipts.

Chromium is installed through the locked Playwright CLI. The existing four shell
geometry cases and compact-desktop overflow case run without updating goldens.
The geometry report is included with frontend receipts.
