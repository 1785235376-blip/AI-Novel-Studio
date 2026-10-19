# V2 Engineering Runbook — environment, isolation, real test entry points

Version: `ENG-2026.10.19-r1`. Every command below is expected to run from a **clean isolated
checkout/worktree**, never from the user's production checkout, RC1 tree or another agent's
workspace.

## 1. Supported host and minimum dependencies

| Item | Requirement | Verified on this host (2026-10-19) |
| --- | --- | --- |
| OS | Windows 11 / Windows Server 2025 or hosted Ubuntu 24.04 CI | Windows 10.0.26100 (Windows 11 24H2), AMD64 |
| Python | `>=3.11` (repo `pyproject.toml`); CI pins 3.12.9 | 3.11.9 (PATH) with project deps installed |
| Node.js | `>=22.14.0 <25` | 22.14.0 |
| pnpm | `10.6.5` (repo `packageManager`); corepack is authoritative | 10.6.5 via `corepack pnpm` (PATH pnpm 12.4.2 is not authoritative) |
| PostgreSQL | 16.x for real DB integration (CI uses `postgres:16-alpine`) | 16.15 bundled binaries, isolated instance on port 55432 |
| FFmpeg | `ffmpeg` + `ffprobe` on PATH for media tests | 8.1.2 essentials |
| .NET SDK | 8.0.424 for DesktopHost/native build | 8.0.424 installed |
| Browser | System Edge/Chrome for Playwright, or downloaded Chromium | Edge 152.0.4191.53 present; Playwright Chromium not pre-downloaded |
| Git / gh | Git 2.5x, authenticated `gh` for read-only GitHub state | Git 2.55.0, gh 2.98.0 authenticated |

Install (isolated, no admin):

````powershell
python -m pip install -c .github/ci/python-constraints.txt -e '.[dev,fontbuild,otio,comic]'
python -m pip check
cd frontend
corepack pnpm install --frozen-lockfile
````

No global runtime versions are modified by this runbook. Installing the .NET SDK or PostgreSQL
system-wide is **not** required: DesktopHost is optional for this baseline and PostgreSQL 16.15
portable binaries are sufficient.

## 2. Isolation contract (mandatory before any app import)

App imports initialize host identity and settings. Environment isolation must be complete
**before** `app.main` is imported, not after. Use a run directory outside the repository.

````powershell
$run  = 'D:\PoemSeed\Engineering-Runs\20261019-r1'
$repo = 'D:\PoemSeed\Worktrees\v2-eng-baseline-20261019'
$env:PROJECT_ROOT              = $repo
$profile = "$repo\.runtime\engineering-runs\r1"   # MUST stay under PROJECT_ROOT/.runtime
$env:NOVEL_DATA_PATH           = "$profile\data\novels"
$env:BACKUP_PATH               = "$profile\data\backups"
$env:DATABASE_BACKUP_PATH      = "$profile\data\database-backups"
$env:KNOWLEDGE_SOURCE_PATH     = "$profile\data\novels"
$env:STORAGE_BACKEND           = 'file'      # or postgres
$env:MOCK_PROVIDER             = 'true'
$env:MOCK_STREAM_DELAY_MS      = '0'
$env:ENABLE_CLOUD              = 'false'
$env:ENABLE_PROVIDER_FALLBACK  = 'false'
$env:CREDENTIAL_VAULT_BACKEND  = 'memory'
$env:CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK = 'true'
$env:PYTHONDONTWRITEBYTECODE   = '1'
$env:HF_HUB_OFFLINE            = '1'
$env:TRANSFORMERS_OFFLINE      = '1'
$env:TMP = $env:TEMP = $env:TMPDIR = "$profile\tmp"
$env:HOME = $env:USERPROFILE = "$profile\home"
$env:APPDATA  = "$profile\appdata"
$env:LOCALAPPDATA = "$profile\localappdata"
$env:XDG_CONFIG_HOME = "$profile\config"
$env:XDG_CACHE_HOME  = "$profile\cache"
$env:XDG_DATA_HOME   = "$profile\data"
$env:XDG_STATE_HOME  = "$profile\state"
````

Rules:

- **Enforced profile location**: several repo fixtures assert that `PROJECT_ROOT` equals the repo
  root and that `LOCALAPPDATA`, `NOVEL_DATA_PATH` and the pytest `--basetemp` live under
  `<repo>/.runtime`. A profile outside the repository (even in an isolated run directory) is
  rejected by those fixtures — put the **profile** under `<repo>/.runtime` and keep only
  logs/evidence/media in the external run directory.
- `PROJECT_ROOT` and `NOVEL_DATA_PATH` are independent: changing only the data path leaves host
  identity/credential paths pointed at the real profile.
- `CREDENTIAL_VAULT_BACKEND=memory` keeps tests away from the OS keyring.
- Never run tests against the user's `D:\小说\AI-Novel-Studio-Latest-Product` RC1 checkout,
  `novel_data` of a real project, or another agent's worktree.
- Only the run directory is disposable. The repository worktree itself is not deleted.
- The app-import runner `scripts/run_v2_checks.py` implements the same isolation automatically and
  writes receipts under `docs/delivery/v2-development/`.

## 3. No-model mode (always available)

The product must remain editable without any model: `MOCK_PROVIDER=true`, `ENABLE_CLOUD=false`
and no local runtime is a supported mode, not a degraded test hack. The backend starts, projects
open, text/images already stored can be viewed/edited/exported, and model-dependent actions report
an explicit unavailable state. Tests in this mode never claim model quality.

Real local model smoke tests (Ollama/llama.cpp) are out of this baseline: no authorized model,
no weight download and no paid API are used. Record them `LOCAL_REQUIRED`.

## 4. Exact test entry points

### 4.1 Backend — File backend (default)

````powershell
Set-Location $repo
python -m pytest -p no:cacheprovider --basetemp="$profile\pytest-file" -q -ra --tb=short --junitxml="$run\evidence\backend-file.xml"
````

CI parity adds the fail-closed coverage plugins and a pinned manifest:

````powershell
$env:PYTHONPATH = "$repo\.github\ci;$repo"
python -m pytest -p suite_coverage -p no:cacheprovider --basetemp="$profile\pytest-file" -q -ra --tb=short --ci-coverage-manifest=.github/ci/coverage_manifest_v2.json.gz --ci-scope=backend --ci-shard-index=0 --ci-shard-count=1 --junitxml="$run\evidence\backend-file-ci.xml"
````

### 4.2 Backend — real PostgreSQL

The bundled PostgreSQL 16.15 binaries live under
`Builds/studio-v2-host-*\Base\PostgreSQL\bin` in the host workspace; any PostgreSQL 16 binaries
are acceptable. Initialize a **disposable** cluster on a non-default port:

````powershell
$pgbin = '<postgres-16-bin>'
$pgdata = "$run\pgdata\v2test"
& "$pgbin\initdb.exe" -D $pgdata -U postgres --auth=trust --no-locale -E UTF8
& "$pgbin\pg_ctl.exe" -D $pgdata -o "-p 55432 -c listen_addresses=127.0.0.1" -l "$run\logs\postgres.log" -w start
````

Apply the authoritative migrations once (do not invent tables; migration files are the schema owner):

````python
import psycopg
from pathlib import Path
with psycopg.connect('postgresql://postgres@127.0.0.1:55432/postgres', autocommit=True) as c:
    c.execute('CREATE DATABASE v2_creative_tests')
with psycopg.connect('postgresql://postgres@127.0.0.1:55432/v2_creative_tests') as c:
    for m in sorted(Path('database/migrations').glob('*.sql')):
        c.execute(m.read_text(encoding='utf-8'))
````

Run the PostgreSQL contract suite (the `postgres_gate` plugin fails the run if a
`postgres_backend_only` contract silently skips):

````powershell
$env:STORAGE_BACKEND = 'postgres'
$env:DATABASE_URL = 'postgresql://postgres@127.0.0.1:55432/v2_creative_tests'
$env:TEST_POSTGRES_DATABASE_URL = $env:DATABASE_URL
$env:PYTHONPATH = "$repo\.github\ci;$repo"
python -m pytest -p postgres_gate -p no:cacheprovider --basetemp="$profile\pytest-pg" -q -ra --tb=short --junitxml="$run\evidence\backend-pg.xml"
````

CI splits this suite into two deterministic node-ID shards (`--ci-shard-index`/`--ci-shard-count`
consumed by `.github/ci/suite_coverage.py`). Sharding is a capacity measure, not an exclusion.

Windows note (this host): the disposable PostgreSQL 16 cluster intermittently logs
`could not reserve shared memory region ... error code 487` when a new backend starts
(address-space/ASLR class of Windows failure). Clients then wait in `psycopg.connect`.
This is an environment limitation, not an application defect. Mitigations used for the
engineering baseline: restart the disposable cluster; for test-only runs start it with
`-c fsync=off -c synchronous_commit=off -c full_page_writes=off -c shared_buffers=64MB -c max_connections=64`
(never for user data); and, when full-suite execution is blocked, run a representative
real-PostgreSQL contract subset and report the full suite as BLOCKED_ENVIRONMENT. Never soften a
`postgres_backend_only` contract or convert it to a skip.

### 4.3 Frontend — unit/type/build/design tokens

````powershell
Set-Location $repo\frontend
corepack pnpm test     # vitest run
corepack pnpm build    # tsc -b && vite build
corepack pnpm lint     # node ../scripts/check_ui_design_tokens.mjs
````

### 4.4 Browser — real Playwright

Use the system Edge when no downloaded Chromium exists (do not silently download browsers):

````powershell
cd frontend
corepack pnpm exec playwright test --config playwright.visual.config.ts --project=chromium --reporter=list
````

Configs exist for `visual`, `creative`, `v2-live`, `export`, `surface`,
`branch-surface`, `independent-live`, `interop`, `r2`, `r4`, `experimental`,
`acceptance`, `p0`, `v061`.
`--list` is discovery only and is **never** reported as a browser PASS. Live-backend browser
configs need the isolated backend profile from section 2; launching a browser and a real HTTP
round-trip must be evidenced separately from fixture collection.

### 4.5 Media (real CPU, real files)

Media coverage is provided by pytest modules and the FFmpeg toolchain; always verify produced
files with `ffprobe` and SHA256 rather than trusting the producing module. Query the current tree
for the exact module names instead of guessing:

````powershell
Get-ChildItem tests -Filter '*media*.py','*ffmpeg*.py','*render*.py','*subtitle*.py' | Select-Object Name
python -m pytest -q tests/<selected-media-modules>
````

Burned-in subtitles, MP4 output, audio mixdown and OTIO/SRT/VTT exchange are only PASS when the
artifact exists, `ffprobe` reports the expected streams/duration and the receipt records hashes.

### 4.6 DesktopHost (safe local subset)

Build (does not install anything):

````powershell
dotnet build desktop-host\AI.NovelStudio.DesktopHost\AI.NovelStudio.DesktopHost.csproj -c Release
````

Acceptance matrix: `docs/desktop_host_acceptance_checklist.md`,
`tests/desktop_host_test_harness`, `tests/desktop_host_webview2_t4_harness`.
Clean-machine install/upgrade/uninstall, WebView2 runtime differences and full Windows acceptance
remain `LOCAL_REQUIRED` and cannot be claimed from a developer machine build.

## 4.7 One-command runner and browser fallback used in this round

A single isolated entry point is provided:

````powershell
pwsh -File scripts/run_engineering_checks.ps1 -Checks backend-file,frontend,focused
pwsh -File scripts/run_engineering_checks.ps1 -Checks backend-pg -PostgresUrl 'postgresql://postgres@127.0.0.1:55432/v2_creative_tests'
````

It keeps the profile under `PROJECT_ROOT/.runtime`, writes JUnit/JSON receipts to the run
directory and never touches user profile state. The focused list is maintained in the script.

When no downloaded Playwright Chromium exists, a local (uncommitted) override config may point
the `chromium` project at the installed system Edge with `channel: 'msedge'`. The 2026-10-19
round used exactly that for `playwright.visual.config.ts`: 15/15 checks passed on Edge
152.0.4191.53 (three module visual baselines, four shell geometries, compact overflow, frozen
production shell, conflict/revision visuals, Local AI lifecycle and geometry). A browser
**launch** alone is never reported as a journey pass; the assertions/screenshots are the evidence.

## 5. Diagnostics

- Backend health: `curl http://127.0.0.1:8000/api/health` (dev server) or the app health script
  `scripts/health-check.ps1` / `scripts/health.ps1`; inspect the actual response, do not infer.
- Model environment: `GET /api/model-center/local-ai/environment` (flag-gated) reports what was
  discovered and what remains unverified; it never starts a runtime.
- Test artifacts: JUnit XML under the run directory `evidence/`; logs under `logs/`; never inline
  user data into committed receipts.
- Failure triage rule: classify every failure as PRODUCT / TEST-INFRA / ENVIRONMENT / FIXTURE /
  OPTIONAL-DEPENDENCY / DATABASE-REQUIRED before fixing. Do not convert a failure into a skip.

## 6. Cleanup policy

Delete only the run directory created by the run itself (`$run`), after retaining:

- JUnit XML and command logs;
- environment/toolchain versions and Git SHA;
- SHA256 of any media artifact plus its generation recipe;
- failure screenshots/thumbnails (small) and the defect records.

Never delete: model weights, user projects, RC1 artifacts, another worktree, committed evidence.
Report bytes created and cleaned before deleting anything.

---

## Windows development-host profile matrix (added 2026-10-19, round 2)

The isolated runner remains the only supported way to execute the backend suites on
Windows. Several suites additionally require explicit environment, because they spawn
child processes, assert shell syntax or assert runner-profile paths:

| Suite family | Required environment |
| --- | --- |
| All backend pytest runs | `PROJECT_ROOT=<repo>`, profile under `<repo>/.runtime`, `PYTHONPATH=<repo>` |
| Child-process probes (leases, revocation, authority) | `PYTHONPATH=<repo>` so `sys.executable -c` children import `app` |
| CI shell-syntax assertions (`bash -n`) | Git-for-Windows `bin` on `PATH` |
| R3-I HTTP suites | `NOVEL_DATA_PATH=<repo>/.runtime/v2-checks/<label>/data/novels` and `PROJECT_ROOT` |
| R3-I authorized / revocation | `ENABLE_COLLABORATION_RUNTIME=true`, `EXPERIMENTAL_FEATURES=narrative_production_v2`, exported before app import |
| R3-I adoption | collaboration runtime OFF, `EXPERIMENTAL_FEATURES` set by the suite itself |
| Windows symlink fixtures | Developer Mode / SeCreateSymbolicLinkPrivilege; otherwise the tests skip with an explicit reason and Linux CI covers them |
| Real-text/owned-process runner | POSIX only; Windows fails closed by design (`BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM`) |

Line endings: contracts and source hashes are byte-bound. Keep the checkout LF
(`core.autocrlf=false` or `input`) and regenerate contracts with the LF-safe generator; never
regenerate `contracts/local-interop` from a CRLF checkout.

---

## Unified Windows engineering entry point (round 3)

Do not assemble ad-hoc pytest invocations for release evidence. The single entry point is

    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_windows_engineering_suite.ps1 -Profile targeted
    pwsh -NoProfile -ExecutionPolicy Bypass -File scripts/run_windows_engineering_suite.ps1 -Profile all -Label round3

Profiles are declared in windows_profiles.json (single source):

| Profile | What it runs | Environment |
| --- | --- | --- |
| full | complete File suite, only two documented multi-process/stress deselects | collaboration runtime off |
| targeted | round-1 previously failing file set (dedicated-profile suites excluded) | default |
| collaboration | prompt-process revocation | ENABLE_COLLABORATION_RUNTIME=true + narrative_production_v2 |
| round3i-adoption | R3-I adoption closed loop | collaboration off, .runtime/v2-checks profile path |
| round3i-authorized | R3-I authorized HTTP adoption | collaboration on + experimental flags, .runtime/v2-checks profile path |
| r3-import | R3 import semantics | collaboration off, .runtime/v2-checks profile path |

Each profile writes a raw log, a JUnit receipt and a per-profile JSON under
<workspace>/Engineering-Runs/windows-engineering/<label>/, plus an aggregate JSON with
Git HEAD, branch, Python/OS versions, per-profile counts and overall status. Counts are
parsed from the JUnit receipt; a missing receipt is reported as RECEIPT_MISSING, never PASS.

Round-3 environment notes:
- A hung complete-suite run was observed at 17% in the order-sensitive
  test_post_interop_shared_universe.py area; the file passes standalone (11 passed/11
  skipped). Complete-suite evidence is therefore taken from a run that excludes that file and
  the file is executed separately (D-20).
- Benchmark loopback exception: the R4 worker allows only Windows socketpair loopback
  (recorded as allowed_loopback_attempts); external connects and name resolution stay
  denied (D-18).
