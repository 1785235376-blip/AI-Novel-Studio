import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
const wire = JSON.parse(readFileSync(new URL('../../src/modelcenter/bailianPresetWire.testFixture.json', import.meta.url), 'utf8'));
for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
  test(`cloud preset preflight and safe failure ${viewport.width}`, async ({ page }, info) => {
    await page.setViewportSize(viewport);
    let fail = false; const requests: { url: string; method: string }[] = [];
    await page.route('**/api/**', route => {
      const request = route.request(); requests.push({ url: request.url(), method: request.method() });
      if (!request.url().endsWith('/api/model-center/provider-presets/bailian-text') || request.method() !== 'GET') return route.abort();
      return fail ? route.fulfill({ status: 503, json: { code: 'SYNTHETIC_UNKNOWN', message: 'SYNTHETIC_PRIVATE_BODY' } }) : route.fulfill({ json: wire });
    });
    await page.goto('/ui-fixture?module=IMAGE'); await expect(page.locator('.app-shell')).toBeVisible();
    await page.evaluate(async () => {
      const load = (url: string) => import(/* @vite-ignore */ url);
      const { default: React } = await load('/node_modules/.vite/deps/react.js');
      const { default: ReactDOM } = await load('/node_modules/.vite/deps/react-dom_client.js');
      const { BailianPresetPanel } = await load('/src/modelcenter/BailianPresetPanel.tsx');
      const { ApiError } = await load('/src/api.ts');
      await load('/src/modelcenter/modelCenter.css');
      const slot = document.createElement('div'); slot.className = 'model-center-panel';
      document.querySelector('.main-workspace')!.replaceChildren(slot);
      const transport = { json: async (url: string, method: string, _body: unknown, signal: AbortSignal) => {
        const response = await fetch(url, { method, signal });
        if (!response.ok) throw new ApiError({ status: response.status, code: 'SYNTHETIC_UNKNOWN', message: 'SYNTHETIC_PRIVATE_BODY' });
        return response.json();
      } };
      ReactDOM.createRoot(slot).render(React.createElement(BailianPresetPanel, { projectId: 'fixture', transport,
        identity: 'fixture', active: true, denied: false, busy: false, isCurrent: () => true,
        read: (work: () => Promise<unknown>) => work() }));
    });
    const read = page.getByRole('button', { name: '明确读取百炼文本预设' }); await expect(read).toBeVisible();
    expect(requests).toEqual([]); await read.click();
    await page.getByLabel('百炼 API 地区').selectOption('cn-hongkong');
    await page.getByLabel('百炼文本模型 ID').fill('synthetic-model');
    await page.getByRole('button', { name: '本地预检端点与模型 ID（不连接）' }).click();
    await expect(page.getByText('本地格式预检通过（未连接）', { exact: true })).toBeVisible();
    await expect(page.getByText(/未验证模型存在、账户权限、额度或实际推理/)).toBeVisible();
    expect(requests).toHaveLength(1); await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: info.outputPath(`cloud-preflight-${viewport.width}.png`) });
    fail = true; await read.click();
    await expect(page.getByText('宿主预设服务暂不可用', { exact: true })).toBeVisible();
    await expect(page.getByText(/不是百炼云端连接测试/)).toBeVisible();
    await expect(page.getByText('SYNTHETIC_PRIVATE_BODY')).toHaveCount(0);
    const geometry = await page.evaluate(() => {
      const rect = (selector: string) => document.querySelector(selector)!.getBoundingClientRect();
      const main = document.querySelector('.main-workspace')!;
      return { header: rect('.global-header').height, context: rect('.context-bar').height, status: rect('.status-bar').height,
        sidebar: rect('.workspace-sidebar').width, inspector: rect('.workspace-inspector').width,
        overflow: document.documentElement.scrollWidth > innerWidth, mainOverflow: main.scrollWidth > main.clientWidth };
    });
    expect(geometry).toEqual({ header: 56, context: 44, status: 32, sidebar: 248, inspector: 340, overflow: false, mainOverflow: false });
    expect(requests).toHaveLength(2); expect(requests.every(request => request.method === 'GET')).toBe(true);
    await page.screenshot({ path: info.outputPath(`cloud-safe-error-${viewport.width}.png`) });
  });
}
