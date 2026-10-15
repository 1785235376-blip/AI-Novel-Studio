/**
 * R3-U3-D — Prompt 工作台真实浏览器验收配置。
 *
 * 与 `playwright.studio-release.config.ts` 相同的纪律：
 * - **不下载浏览器**：通过 Playwright 的 branded `channel` 启动**已安装的系统浏览器**
 *   （默认 msedge）。若两者都不存在，运行会以 Playwright 自己的“browser is not
 *   installed”失败，那是正确且诚实的结果，不允许用 `playwright install` 让它变绿。
 * - **应用必须已经在运行**：这里刻意没有 `webServer` 块，启动长驻服务是操作者的动作。
 * - 不修改仓库已有的两个配置（`playwright.config.ts` / `playwright.visual.config.ts`）。
 *
 * 三种分辨率各自成为一个 project，跑的是同一份用例。
 */
import {defineConfig} from '@playwright/test';

const channel = process.env.STUDIO_ACCEPTANCE_CHANNEL?.trim() || 'msedge';
const baseURL = process.env.STUDIO_ACCEPTANCE_BASE_URL?.trim() || 'http://127.0.0.1:5173';

const VIEWPORTS = [
  {name: '1366x768', width: 1366, height: 768},
  {name: '1440x900', width: 1440, height: 900},
  {name: '1920x1080', width: 1920, height: 1080},
] as const;

export default defineConfig({
  testDir: './e2e',
  testMatch: /prompt-workspace-acceptance\.spec\.ts/,
  timeout: 90_000,
  expect: {timeout: 20_000},
  // Every case writes real revisions on the operator's running backend, so concurrent
  // writers would make a failure unattributable.
  fullyParallel: false,
  workers: 1,
  reporter: [['list'], ['json', {outputFile: 'prompt-acceptance-results.json'}]],
  forbidOnly: true,
  // No retries: a retry would hide a genuinely flaky surface.
  retries: 0,
  use: {
    baseURL,
    channel,
    locale: 'zh-CN',
    timezoneId: 'Asia/Shanghai',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  projects: VIEWPORTS.map(viewport => ({
    name: `prompt-${viewport.name}`,
    use: {channel, viewport: {width: viewport.width, height: viewport.height}},
  })),
});
