import { test, expect, type Page, type APIResponse } from '@playwright/test';
import fs from 'node:fs/promises';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
const owned = new WeakMap<Page, { id: string; api: string }[]>();
const quiet = new WeakMap<Page, () => Promise<void>>();
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy(); return response.json(); }
async function project(page: Page, text = '合成原文：阿澄在月港，😀 看见灯塔。', api = API, ui = '/') {
  expect(await body(await page.request.get(`${api}/novels`))).toHaveLength(0);
  await page.goto(ui);
  await page.getByPlaceholder('小说名称').fill(`R4 browser synthetic ${Date.now()}-${test.info().testId}`);
  const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await body(await created); owned.get(page)!.push({ id: novel.id, api });
  await page.getByRole('button', { name: '新建章节', exact: true }).click();
  await page.getByLabel('章节标题', { exact: true }).fill('月港与灯塔');
  const added = page.waitForResponse(r => r.url().endsWith(`/novels/${novel.id}/chapters`) && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建章节', exact: true }).click();
  const chapter = await body(await added);
  await page.getByRole('textbox', { name: '章节正文', exact: true }).fill(text);
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('.editorbar')).toContainText('已保存');
  return { novel, chapter: await body(await page.request.get(`${api}/chapters/${chapter.id}`)) };
}
async function tools(page: Page, tab = '工作现场') {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: tab, exact: true }).click();
}
test.beforeEach(({ page }) => {
  owned.set(page, []); quiet.set(page, createPageQuiescer(page));
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  test.info().annotations.push({ type: 'verification', description: 'Real File API and browser, synthetic manual prose, no model or cloud. Deliberate page transport/storage faults are explicitly identified.' });
});
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('failure-before-cleanup.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!();
  for (const row of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${row.api}/novels/${encodeURIComponent(row.id)}`)).status());
});

test('R4 default-off and acceptance override retain no-model Chinese writing', async ({ page, request }, info) => {
  for (const port of [8020, 8021]) {
    const flags = await body(await request.get(`http://127.0.0.1:${port}/api/experimental/features`));
    expect(Object.values(flags.features).every(value => value === false)).toBe(true);
    expect((await request.get(`http://127.0.0.1:${port}/api/novels/unknown/experimental/workspace/search`)).status()).toBe(404);
  }
  const text = '纯手工中文，无模型也能保存。<b>文字不是 HTML</b> 👩🏽‍🚀';
  const { chapter } = await project(page, text, 'http://127.0.0.1:8020/api', 'http://127.0.0.1:5180');
  await page.reload(); await expect(page.locator('.ProseMirror')).toContainText(text);
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  await expect(page.getByRole('button', { name: '实验工作台', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '版本历史', exact: true })).toBeVisible();
  expect((await body(await request.get(`http://127.0.0.1:8020/api/chapters/${chapter.id}`))).content).toContain(text);
  await page.screenshot({ path: info.outputPath('v1-off-manual-writing.png') });
});

test('R4 durable offline draft survives reload and preserves both conflict candidates', async ({ page, request }, info) => {
  const { chapter } = await project(page);
  const endpoint = `**/api/chapters/${chapter.id}`;
  await page.route(endpoint, route => route.request().method() === 'PUT' ? route.abort('failed') : route.continue());
  const candidate = '我的离线候选，中文与 emoji 😀 都必须保留。';
  await page.locator('.ProseMirror').fill(candidate);
  await expect(page.locator('.editorbar')).toContainText('后端未确认保存');
  await page.reload(); await expect(page.locator('.ProseMirror')).toContainText(candidate);
  const current = await body(await request.get(`${API}/chapters/${chapter.id}`));
  await body(await request.put(`${API}/chapters/${chapter.id}`, { data: { version: current.version, content: '另一个客户端的服务器候选。' } }));
  await page.unroute(endpoint);
  await page.getByRole('button', { name: '保存', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '检测到版本冲突' });
  await expect(dialog).toContainText(candidate); await expect(dialog).toContainText('另一个客户端的服务器候选。');
  await dialog.screenshot({ path: info.outputPath('offline-conflict-candidates.png') });
  await dialog.getByRole('button', { name: '保留本地草稿并关闭' }).click();
  const download = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出当前草稿' }).click();
  const file = await download, path = await file.path();
  expect(path).toBeTruthy(); expect(await fs.readFile(path!, 'utf8')).toContain(candidate);
});

test('R4 workspace resume, keyboard search and explicit private diagnostic export', async ({ page }, info) => {
  await project(page);
  await tools(page);
  await page.getByLabel('停止点与下次要做的事').fill('私有停止点：明天检查旧信');
  await page.getByRole('button', { name: '保存工作现场', exact: true }).click();
  await expect(page.getByText('工作现场已保存。正文仍由编辑器保存。')).toBeVisible();
  await page.reload(); await tools(page);
  await expect(page.getByLabel('停止点与下次要做的事')).toHaveValue('私有停止点：明天检查旧信');
  await page.keyboard.press('Control+k');
  const search = page.getByLabel('搜索中文名称、别名或正文');
  await expect(search).toBeFocused(); await search.fill('灯塔'); await search.press('Enter');
  await expect(page.getByRole('button', { name: '打开章节位置', exact: true }).first()).toBeVisible();
  await page.getByRole('button', { name: '打开章节位置', exact: true }).first().click();
  await expect(page.locator('.ProseMirror')).toBeFocused();
  await tools(page);
  await page.getByRole('navigation', { name: '工作现场工具分类' }).getByRole('button', { name: '诊断包', exact: true }).click();
  await page.getByRole('button', { name: '生成诊断预览' }).click();
  await expect(page.getByRole('region', { name: '诊断预览' })).toContainText('上传：否');
  const download = page.waitForEvent('download'); await page.getByRole('button', { name: '导出已选诊断项' }).click();
  const file = await download, path = await file.path(); const data = JSON.parse(await fs.readFile(path!, 'utf8'));
  expect(data.uploaded).toBe(false); expect(data.contains_manuscript).toBe(false); expect(JSON.stringify(data)).not.toContain('私有停止点');
  await page.screenshot({ path: info.outputPath('workspace-diagnostics.png') });
});

test('R4 workflow inspection honestly requires host authority without executing imported data', async ({ page }, info) => {
  await project(page); await tools(page, '工作流检查');
  await expect(page.getByRole('heading', { name: 'Local AI 工作流检查器', exact: true })).toBeVisible();
  await expect(page.getByText(/SESSION_REQUIRED/).first()).toBeVisible();
  await expect(page.getByText(/DENY_ALL/).first()).toBeVisible();
  await page.screenshot({ path: info.outputPath('workflow-host-session-required.png') });
});
