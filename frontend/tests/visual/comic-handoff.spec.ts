import { expect, test } from '@playwright/test';
import { readFileSync } from 'node:fs';
import type HttpCapture from '../../src/creative/__fixtures__/comicHandoffHttp.json';
const capture: typeof HttpCapture = JSON.parse(readFileSync(new URL('../../src/creative/__fixtures__/comicHandoffHttp.json', import.meta.url), 'utf8'));

// Actual HTTP bytes are retained fixtures. This verifies browser/React behavior,
// not the live-backend or external-raster integration owned by other suites.
for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
  test(`original Comic handoff native PNG and recovery geometry ${viewport.width}`, async ({ page }, info) => {
    const mode = viewport.width === 1440 ? 'lost' : viewport.width === 1920 ? 'partial' : 'normal';
    await page.setViewportSize(viewport);
    await page.addInitScript(() => Object.defineProperty(crypto, 'randomUUID', { value: () => '00000000-0000-4000-8000-000000000001' }));
    const errors: string[] = [], unexpected: string[] = [], writes: { path: string; body: unknown }[] = [];
    let stored: typeof capture.created | undefined, reads = 0;
    page.on('pageerror', error => errors.push(error.message));
    function result(requestId: string, partial = false) {
      const value = structuredClone(capture.created); value.request_id = requestId; value.timeline.comic_handoff_origin.request_id = requestId;
      if (partial) {
        Object.assign(value, { status: 'PLANNED', version: 2, timeline_snapshot: null });
        delete (value as Partial<typeof value>).timeline; delete (value as Partial<typeof value>).timeline_state;
        Object.assign(value.steps[1], { state: 'PENDING', asset_version: null, observed_state: 'AWAITING_EXPLICIT_RESUME' });
      }
      return value;
    }
    await page.route('**/api/**', async route => {
      const request = route.request(), path = new URL(request.url()).pathname;
      const body = request.method() === 'POST' ? request.postDataJSON() : undefined;
      if (path.endsWith('/comic-layouts/catalog')) {
        const preset = { width: 320, height: 640, safe_area: 24, segment_height: 320 };
        return route.fulfill({ json: { screenplays: [], characters: [], assets: [], presets: { PAGE: preset, WEBTOON: { ...preset, height: 1280 } }, renderer: { available: true }, font: { available: true } } });
      }
      if (path.endsWith('/comic-layouts/records')) return route.fulfill({ json: { items: capture.source_records } });
      if (path.endsWith('/comic-layouts/books')) return route.fulfill({ json: { items: [] } });
      if (path.endsWith('/preflight')) {
        const pin = capture.preview_response.preview.pages.find(p => path.includes(p.source.id))!;
        return route.fulfill({ json: { issues: [], segments: [{ index: 0, width: 320, height: 640, y: 0 }], can_render: true,
          version: pin.source.version, status: 'APPROVED', review_digest: pin.source.review_digest } });
      }
      if (path.endsWith('/comic-handoffs/preview')) return route.fulfill({ json: capture.preview_response });
      if (path.endsWith('/comic-handoffs')) {
        writes.push({ path, body }); stored = result(body.request_id, mode === 'partial');
        if (mode === 'lost') return route.abort('failed');
        return route.fulfill({ json: stored });
      }
      if (path.endsWith('/resume')) {
        writes.push({ path, body }); expect(body).toEqual({ expected_version: 2 }); stored = result(path.split('/').at(-2)!);
        return route.fulfill({ json: stored });
      }
      if (path.includes('/comic-handoffs/') && request.method() === 'GET') { reads++; return route.fulfill({ json: stored }); }
      unexpected.push(path); return route.fulfill({ status: 500, json: { detail: { code: 'UNEXPECTED_FIXTURE_ROUTE' } } });
    });
    await page.goto('/ui-fixture?module=IMAGE');
    await page.evaluate(async projectId => {
      const load = (path: string) => import(/* @vite-ignore */ path);
      const { default: React } = await load('/node_modules/.vite/deps/react.js');
      const { default: ReactDOM } = await load('/node_modules/.vite/deps/react-dom_client.js');
      const { StudioComicPanel } = await load('/src/creative/StudioComicPanel.tsx');
      await load('/src/experimental/experimental.css');
      const slot = document.createElement('div'); document.querySelector('.main-workspace')!.replaceChildren(slot);
      ReactDOM.createRoot(slot).render(React.createElement(StudioComicPanel, { projectId, context: { sessionToken: 'browser-fixture-host-token' },
        isCurrent: () => true, canMutate: true, canReview: true,
        onDirtyChange: (value: boolean) => { slot.dataset.dirty = String(value); },
        onBusyChange: (value: boolean) => { slot.dataset.busy = String(value); } }));
    }, capture.original_timeline.novel_id);
    for (const pin of capture.request.pages) await page.getByLabel(new RegExp(pin.id)).check();
    await page.getByLabel('Timeline 草稿标题', { exact: true }).fill(capture.request.title);
    await page.getByLabel('输出宽度', { exact: true }).fill('640'); await page.getByLabel('输出高度', { exact: true }).fill('360');
    await page.getByLabel('第 1 页停留时长（毫秒）', { exact: true }).fill('10000'); await page.getByLabel('第 2 页停留时长（毫秒）', { exact: true }).fill('10000');
    const prepare = (recovery = false) => page.getByRole('button', { name: recovery ? '重新核对原请求整页预览' : '检查并加载整页预览', exact: true });
    const acknowledge = async () => {
      const version = page.getByLabel('已查看全部整页图片，核对页面版本、顺序和逐页时长', { exact: true });
      await expect(version).toBeEnabled();
      const dimensions = await page.locator('img[alt^="交接整页预览"]').evaluateAll(images => images.map(image => [(image as HTMLImageElement).naturalWidth, (image as HTMLImageElement).naturalHeight]));
      expect(dimensions).toEqual([[320, 640], [320, 640]]);
      await version.check(); await page.getByLabel('确认静态整页合并损失，只创建未批准的 Timeline 草稿', { exact: true }).check();
    };
    await prepare().click(); await acknowledge();
    await page.getByAltText('交接整页预览 2', { exact: true }).scrollIntoViewIfNeeded(); await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: info.outputPath(`comic-handoff-preview-${viewport.width}.png`) });
    await page.getByRole('button', { name: '明确创建原 Timeline 草稿', exact: true }).click();
    if (mode === 'lost') {
      await expect(page.getByText(/提交结果尚未核对/)).toBeVisible(); expect(writes).toHaveLength(1); expect(reads).toBe(0);
      await page.getByRole('button', { name: '按原 ID 读回交接状态', exact: true }).click();
    } else if (mode === 'partial') {
      await expect(page.getByText(/交接等待明确恢复/)).toBeVisible(); expect(writes).toHaveLength(1);
      await prepare(true).click(); await acknowledge(); await page.getByRole('button', { name: '明确恢复剩余交接步骤', exact: true }).click();
    }
    await expect(page.getByText(new RegExp('原 Timeline 草稿 ID：' + capture.created.timeline_snapshot.id))).toBeVisible();
    expect(writes).toHaveLength(mode === 'partial' ? 2 : 1); expect(errors).toEqual([]); expect(unexpected).toEqual([]);
    const markers = await page.evaluate(() => Object.values(sessionStorage));
    expect(markers.join('')).not.toContain('browser-fixture-host-token'); expect(markers.join('')).not.toContain('png_base64');
    await page.getByText(new RegExp('原 Timeline 草稿 ID：' + capture.created.timeline_snapshot.id)).scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath(`comic-handoff-terminal-${viewport.width}.png`) });
    await page.getByRole('button', { name: '关闭交接并保留原记录', exact: true }).click();
    await expect(page.getByRole('button', { name: '新建空白漫画页', exact: true })).toBeEnabled();
    expect(await page.evaluate(() => sessionStorage.length)).toBe(0); expect(page.url()).toContain('module=IMAGE');
    const geometry = await page.evaluate(() => {
      const height = (selector: string) => document.querySelector(selector)!.getBoundingClientRect().height;
      const main = document.querySelector('.main-workspace')!;
      return { header: height('.global-header'), context: height('.context-bar'), status: height('.status-bar'),
        overflow: document.documentElement.scrollWidth > innerWidth, mainOverflow: main.scrollWidth > main.clientWidth };
    });
    expect(geometry).toEqual({ header: 56, context: 44, status: 32, overflow: false, mainOverflow: false });
    await info.attach('handoff-contract.json', { body: JSON.stringify({ mode, viewport, writes, reads, geometry, errors, unexpected }, null, 2), contentType: 'application/json' });
    await page.screenshot({ path: info.outputPath(`comic-handoff-complete-${viewport.width}.png`) });
  });
}
