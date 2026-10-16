# Studio release acceptance — real browser only

This directory holds the **Phase8 real-browser acceptance entry point** for the six
Studio surfaces: **START / TASKS / ASSETS / MODEL CENTER / PRODUCTION / DELIVERY**.

It is deliberately separate from the repository's other two Playwright suites:

| Config | testDir | Needs |
| --- | --- | --- |
| `playwright.config.ts` | `tests/e2e` | `../.venv`, PostgreSQL, a full app+api `webServer` pair |
| `playwright.visual.config.ts` | `tests/visual` | the `ui-fixture` route, checked-in screenshot baselines |
| **`playwright.studio-release.config.ts`** | **`e2e`** | **an app you started yourself, plus a browser you already have** |

> ## A jsdom pass is NOT browser acceptance
>
> The repository has jsdom component tests that render these same surfaces
> (`src/onboarding/StudioStartPanel.test.tsx`, `src/taskcenter/TaskCenter.test.tsx`,
> `src/creative/IndependentStudioWorkspace.test.tsx`, `src/modelcenter/ModelCenterPanel.test.tsx`,
> `src/production/ProductionDashboard.test.tsx`, `src/production/productionDashboardMount.test.tsx`,
> `src/delivery/DeliveryCenterPanel.test.tsx`). They are real, useful evidence that the
> components render and behave — but they run in **jsdom**, a JavaScript DOM
> emulation with **no layout engine, no CSS, no real focus model and no browser**.
> A green `vitest` run therefore **never** counts as browser acceptance for these
> six surfaces. Only a passing run of *this* suite is browser acceptance.

## What an operator must do

### 1. Provide a browser — this suite does not download one

Phase8 forbids fetching browser binaries. This suite therefore launches a **system
browser** through Playwright's `channel` mechanism, which resolves an already-installed
browser and downloads nothing:

- default: **Microsoft Edge** (`STUDIO_ACCEPTANCE_CHANNEL=msedge`)
- alternative: **Google Chrome** (`STUDIO_ACCEPTANCE_CHANNEL=chrome`)

If neither is installed, the run fails with Playwright's own "browser is not
installed" error. **Do not run `pnpm exec playwright install` to fix that** — that is a
browser artifact download. Install a system browser instead.

On the host this entry point was authored on, Edge is present at
`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`, and there is **no**
Playwright-managed browser (`%LOCALAPPDATA%\ms-playwright` does not exist).

### 2. Start the app yourself

The suite has **no `webServer` block on purpose**: bringing the app up needs a backend
and a storage backend, and the Phase8 brief forbids implicitly starting services.

```powershell
# Terminal A — backend, from the worktree root.
# STORAGE_BACKEND=file avoids requiring PostgreSQL; the surface flag is an explicit
# opt-in (there is no wildcard enable).
$env:STORAGE_BACKEND = 'file'
$env:EXPERIMENTAL_FEATURES = 'narrative_production_v2'
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal B — frontend, from <worktree>\frontend (Vite proxies /api to the backend).
node node_modules/vite/bin/vite.js --host 127.0.0.1 --port 5173
```

The studio only mounts for a project whose server-side `entry_kind` is
`NEUTRAL_STUDIO`, which is why the spec creates a blank project through the app's own
entry instead of deep-linking.

### 3. Run the suite

```powershell
cd <worktree>\frontend
pnpm exec playwright test --config playwright.studio-release.config.ts
```

Useful overrides:

| Variable | Default | Meaning |
| --- | --- | --- |
| `STUDIO_ACCEPTANCE_BASE_URL` | `http://127.0.0.1:5173` | the running app |
| `STUDIO_ACCEPTANCE_CHANNEL` | `msedge` | an already-installed browser channel |

To confirm the suite is discovered without launching anything:

```powershell
pnpm exec playwright test --config playwright.studio-release.config.ts --list
```

## Test runner discovery

`pnpm test` owns the Vitest unit/component suites, including the suites under
`src` and the unit tests directly under `tests`. It excludes the Playwright
directories `e2e`, `tests/e2e`, and `tests/visual`. The two Prompt specs in this
directory belong to `playwright.prompt-acceptance.config.ts`; the eight Studio
release cases remain in `playwright.studio-release.config.ts`.

Run `pnpm test:discovery` for a browser-free regression check. It compares Vitest's
actual file list with an independent source inventory and lists every spec in
this directory through its existing Playwright config. The explicit owner and
per-project case counts are in `../test-runner-manifest.json`. All three Prompt
viewports must remain discoverable. This check never executes browser cases,
and a successful list is not browser acceptance. The pre-existing `tests/e2e`
and `tests/visual` configs and suites are unchanged and are not loaded by this
check (some legacy configs prepare service fixtures at import time).

To list the Prompt suite directly, without executing it:

```powershell
pnpm exec playwright test --config playwright.prompt-acceptance.config.ts --list --reporter=list
```

## What the suite does to your server

Each of the eight cases **creates one real `NEUTRAL_STUDIO` project** through the app's
blank-project entry. Point it at a disposable or local instance. The spec does not
delete those projects: destroying server-owned records is the operator's call.

## What is asserted

One case per surface, each asserting that surface's **own shipped landmark** is
visible (the `aria-label`/heading taken from source, not invented), plus:

- a **zh-CN smoke** case: the shell renders authored Chinese copy, not raw message keys;
- a **keyboard** case: a switcher control is reached with real `Tab` presses,
  reports `toBeFocused()`, shows a computed focus indicator (outline or ring shadow),
  and activates on `Enter`.
