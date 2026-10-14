/**
 * AI-Novel-Studio V2 — Phase8 (Studio Release Preparation)
 * Real-browser acceptance entry point for the six Studio surfaces:
 * START / TASKS / ASSETS / MODEL CENTER / PRODUCTION / DELIVERY.
 *
 * ─────────────────────────────────────────────────────────────────────────────
 * BROWSER BINARIES MUST BE PROVIDED BY THE OPERATOR. THIS CONFIG NEVER
 * DOWNLOADS A BROWSER, AND THIS SUITE MUST NEVER BE RUN WITH A FETCHED ONE.
 * ─────────────────────────────────────────────────────────────────────────────
 * Playwright's bundled Chromium is deliberately NOT used. Instead this config
 * targets a browser that is ALREADY INSTALLED on the host, through Playwright's
 * branded `channel` mechanism — a channel launch resolves the system browser
 * and performs no download:
 *
 *   STUDIO_ACCEPTANCE_CHANNEL=msedge  (default) → system Microsoft Edge
 *   STUDIO_ACCEPTANCE_CHANNEL=chrome            → system Google Chrome
 *
 * If neither is installed, `pnpm exec playwright test --config
 * playwright.studio-release.config.ts` fails with Playwright's own
 * "browser is not installed" error. That failure is the correct and honest
 * outcome for Phase8: provision a system browser deliberately. Do NOT run
 * `pnpm exec playwright install` to turn this suite green — that is a browser
 * artifact download and is out of scope for this brief.
 *
 * THE APPLICATION UNDER TEST MUST ALREADY BE RUNNING.
 * There is intentionally NO `webServer` block: bringing this app up requires a
 * backend, a storage backend and the `narrative_production_v2` opt-in, and the
 * Phase8 brief forbids implicitly starting long-running services. The operator
 * starts the app; see ./e2e/README.md for the exact commands.
 *
 * PRE-EXISTING CONFIGS ARE LEFT UNTOUCHED ON PURPOSE. This file is deliberately
 * NOT named `playwright.config.ts`, because that path is already owned by the
 * repository's established suite and rewriting it would change existing tests:
 *   - playwright.config.ts        → testDir tests/e2e, needs ../.venv + postgres
 *   - playwright.visual.config.ts → testDir tests/visual, owns the `test:visual`
 *                                   script and the checked-in screenshot
 *                                   baselines
 */
import {defineConfig} from '@playwright/test';

/** An ALREADY-INSTALLED system browser channel. Never a downloaded binary. */
const channel = process.env.STUDIO_ACCEPTANCE_CHANNEL?.trim() || 'msedge';

/**
 * The documented base URL of the running app. The Vite dev server serves the
 * frontend on 5173 and proxies `/api` to the backend; see ./e2e/README.md.
 */
const baseURL = process.env.STUDIO_ACCEPTANCE_BASE_URL?.trim() || 'http://127.0.0.1:5173';

export default defineConfig({
  testDir: './e2e',
  testMatch: /studio-release-acceptance\.spec\.ts/,
  timeout: 60_000,
  expect: {timeout: 15_000},
  // One worker and no parallelism: every case creates a real project on the
  // operator's running backend, so concurrent writers would make failures
  // unattributable.
  fullyParallel: false,
  workers: 1,
  // `list` is the reporting contract for this suite: raw, line-per-test output
  // that can be pasted into a release receipt verbatim.
  reporter: 'list',
  forbidOnly: true,
  // No retries: a retry would hide a genuinely flaky surface. A red run is
  // evidence to report, not something to paper over.
  retries: 0,
  use: {
    baseURL,
    channel,
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    viewport: {width: 1440, height: 900},
    // Evidence on failure only; a passing run writes nothing.
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: [{name: `studio-release-${channel}`, use: {channel}}],
});
