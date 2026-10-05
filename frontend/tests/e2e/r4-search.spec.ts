import { test, expect, type APIResponse, type Response } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function body(response: APIResponse | Response) { expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy(); return response.json(); }

test('U03 real File incremental multi-project search, keyboard navigation, cancel and stale rebuild', async ({ page, request }, info) => {
  const owned: string[] = [], quiet = createPageQuiescer(page);
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  info.annotations.push({ type: 'verification', description: 'Real File repositories and browser. Synthetic manuscripts only. Explicit transport delay tests cancellation; no model/provider calls.' });
  try {
    const first = await body(await request.post(`${API}/novels`, { data: { title: `U03 first ${Date.now()}` } })); owned.push(first.id);
    const second = await body(await request.post(`${API}/novels`, { data: { title: `U03 second ${Date.now()}` } })); owned.push(second.id);
    await body(await request.post(`${API}/novels/${first.id}/chapters`, { data: { title: '起点章节', content: '合成原文，石城。' } }));
    const target = await body(await request.post(`${API}/novels/${second.id}/chapters`, { data: { title: '跨作品灯塔', content: '合成检索目标灯塔。' } }));
    const base = `${API}/novels/${first.id}/experimental/workspace`;
    const cold = await body(await request.get(`${base}/search?scope=authorized&q=灯塔`));
    expect(cold.match_count).toBe(1); expect(cold.items[0].novel_id).toBe(second.id);
    const warm = await body(await request.get(`${base}/search?scope=authorized&q=灯塔`));
    expect(warm.incremental_chapters).toBe(true); expect(warm.source_rows_read).toBe(0);
    const blockedRequests: string[] = [];
    page.on('request', req => { if (req.method() === 'POST' && /\/(generate|accept|execute)(?:[/?]|$)/.test(req.url())) blockedRequests.push(req.url()); });
    await page.goto('/');
    await page.getByRole('button', { name: '切换本机作品', exact: true }).click();
    await page.getByRole('button', { name: first.title, exact: true }).click();
    await page.keyboard.press('Control+k');
    const searchTools = page.getByRole('region', { name: '工作现场工具', exact: true });
    const input = searchTools.getByLabel('搜索中文名称、别名或正文');
    await expect(input).toBeFocused();
    await input.fill('灯塔'); await searchTools.getByLabel('搜索范围', { exact: true }).selectOption('authorized');
    await expect(searchTools.getByRole('heading', { name: '跨作品灯塔', exact: true })).toBeVisible();
    await expect(searchTools.getByText('当前可读匹配：1。', { exact: false })).toBeVisible();
    await input.press('ArrowDown');
    await expect(searchTools.getByRole('button', { name: '打开章节位置', exact: true })).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('.editorbar')).toContainText('跨作品灯塔');
    await expect(page.locator('.ProseMirror')).toContainText('合成检索目标灯塔');
    await page.keyboard.press('Control+k');
    // The editor retains an H1 with this title. It cannot prove that the
    // reopened, debounced search has read the source before we make it stale.
    const currentSearchPath = `/api/novels/${second.id}/experimental/workspace/search`;
    const isCurrentSearch = (response: Response, query: string) => {
      const url = new URL(response.url());
      return response.request().method() === 'GET' && url.pathname === currentSearchPath
        && url.searchParams.get('q') === query && url.searchParams.get('scope') === 'project';
    };
    const reopenedSearch = page.waitForResponse(response => isCurrentSearch(response, '灯塔'));
    await input.fill('灯塔');
    const reopened = await body(await reopenedSearch);
    expect(reopened.match_count).toBe(1);
    expect(reopened.items[0]).toMatchObject({ id: target.id, novel_id: second.id, version: target.version });
    await expect(searchTools.getByRole('heading', { name: '跨作品灯塔', exact: true })).toBeVisible();
    await expect(searchTools.getByRole('button', { name: '打开章节位置', exact: true })).toBeEnabled();
    const current = await body(await request.get(`${API}/chapters/${target.id}`));
    expect(current.version).toBe(reopened.items[0].version);
    const updated = await body(await request.put(`${API}/chapters/${target.id}`, { data: { version: current.version, content: '新版本的星港信号。' } }));
    expect(updated.version).toBe(current.version + 1);
    expect(updated.title).not.toContain('灯塔'); expect(updated.content).not.toContain('灯塔');
    const staleResolve = page.waitForResponse(response => response.url().endsWith(`${currentSearchPath}/resolve`));
    await searchTools.getByRole('button', { name: '打开章节位置', exact: true }).click();
    const rejected = await staleResolve;
    expect(rejected.status()).toBe(409);
    expect(await rejected.json()).toMatchObject({ detail: { code: 'EXPERIMENTAL_SOURCE_STALE' } });
    expect(rejected.request().postDataJSON()).toMatchObject({ id: target.id, novel_id: second.id, revision: reopened.items[0].revision, open_current: false });
    await expect(searchTools.getByRole('button', { name: '核对并打开当前版本', exact: true })).toBeVisible();
    await expect(page.locator('.ProseMirror')).toContainText('合成检索目标灯塔');
    const refreshedSearch = page.waitForResponse(response => isCurrentSearch(response, '灯塔'));
    await searchTools.getByRole('button', { name: '刷新来源', exact: true }).click();
    expect(await body(await refreshedSearch)).toMatchObject({ match_count: 0, items: [] });
    await expect(searchTools.getByRole('heading', { name: '跨作品灯塔', exact: true })).toHaveCount(0);
    const updatedSearch = page.waitForResponse(response => isCurrentSearch(response, '星港'));
    await input.fill('星港');
    expect((await body(await updatedSearch)).items[0]).toMatchObject({ id: target.id, novel_id: second.id, version: updated.version });
    await expect(searchTools.getByRole('button', { name: '打开章节位置', exact: true })).toBeVisible();
    const rebuild = page.waitForResponse(r => r.url().endsWith('/workspace/search/rebuild'));
    await searchTools.getByRole('button', { name: '重建索引', exact: true }).click();
    expect((await body(await rebuild)).updated_documents).toBeGreaterThan(0);
    // Delay an actual read response, cancel it, then release the late response.
    let release: () => void = () => {};
    const delayed = new Promise<void>(resolve => { release = resolve; });
    await page.route('**/workspace/search?**', async route => {
      const response = await route.fetch(); await delayed; await route.fulfill({ response }).catch(() => {});
    });
    const pending = page.waitForRequest(r => r.url().includes('/workspace/search?'));
    await searchTools.getByRole('button', { name: '刷新来源', exact: true }).click(); await pending;
    const cancellation = page.waitForResponse(r => r.url().endsWith('/workspace/search/cancel'));
    await searchTools.getByRole('button', { name: '取消搜索', exact: true }).click();
    expect((await body(await cancellation)).state).toBe('CANCELLED'); release();
    await expect(searchTools.getByText('搜索已取消；不会展示迟到的结果。可重新搜索。')).toBeVisible();
    await expect(searchTools.getByRole('button', { name: '打开章节位置', exact: true })).toHaveCount(0);
    await page.unroute('**/workspace/search?**');
    expect(blockedRequests).toEqual([]);
    for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
      await page.setViewportSize(viewport); await page.screenshot({ path: info.outputPath(`u03-search-${viewport.width}.png`) });
    }
  } finally {
    await quiet();
    for (const id of owned) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${id}`)).status());
  }
});
