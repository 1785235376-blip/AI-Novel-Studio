import { test, expect, type Page, type APIResponse } from '@playwright/test';
import fs from 'node:fs/promises';
import { createPageQuiescer } from './r3-fixture-lifecycle';
import { expectVisibleWorkspaceEditor } from './workspace-editor-geometry';
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
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport); await expectVisibleWorkspaceEditor(page, false);
    await page.screenshot({ path: info.outputPath(`u01-feature-off-editor-${viewport.width}.png`) });
  }
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

test('U01 two-project reopen restores the exact chapter, filters and original reference layout', async ({ page }, info) => {
  await project(page);
  const second = await body(await page.request.post(`${API}/novels`, { data: { title: `U01 second project ${Date.now()}`, genre: '' } }));
  owned.get(page)!.push({ id: second.id, api: API });
  const inventory = await body(await page.request.get(`${API}/novels`));
  expect(inventory).toHaveLength(2);
  // Choose the actual non-first result rather than assuming repository order.
  const selected = inventory[1];
  const reference = await body(await page.request.post(`${API}/novels/${selected.id}/chapters`, { data: { title: 'U01 fixed reference', content: '只读参考：灯塔与旧信。' } }));
  const destination = await body(await page.request.post(`${API}/novels/${selected.id}/chapters`, { data: { title: 'U01 resume destination', content: '恢复目标章节：明天接着写旧信。' } }));
  const base = `${API}/novels/${selected.id}/experimental`;
  const cards = await body(await page.request.get(`${base}/writing-focus/references`));
  const card = cards.items.find((row: any) => row.kind === 'chapter' && row.id === reference.id);
  expect(card).toBeTruthy();
  await body(await page.request.put(`${base}/writing-focus/preferences`, { data: { expected_version: 0,
    preferences: { font_size: 24 }, pins: [{ kind: card.kind, id: card.id, revision: card.revision }] } }));
  const modelRequests: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /\/(generate|accept|execute)(?:[/?]|$)/.test(request.url())) modelRequests.push(request.url()); });
  await page.getByRole('button', { name: '切换本机作品', exact: true }).click();
  await page.getByRole('button', { name: selected.title, exact: true }).click();
  await tools(page);
  await page.getByRole('button', { name: '搜索与命令', exact: true }).click();
  await page.getByLabel('搜索中文名称、别名或正文').fill('U01 resume destination');
  await page.getByRole('button', { name: '打开章节位置', exact: true }).click();
  await expect(page.locator('.editorbar')).toContainText('U01 resume destination');
  await expect(page.getByRole('complementary', { name: '写作分屏只读参考' })).toContainText('只读参考：灯塔与旧信。');
  await tools(page);
  await page.getByRole('button', { name: '搜索与命令', exact: true }).click();
  await page.getByLabel('搜索中文名称、别名或正文').fill('旧信');
  await page.getByLabel('内容类型', { exact: true }).selectOption('chapter');
  await page.getByLabel('只搜当前章', { exact: true }).check();
  await page.getByRole('button', { name: '任务中心', exact: true }).click();
  await page.getByLabel('按任务 ID、类型或阶段搜索').fill('original-task');
  await page.getByLabel('只看失败或结果未知').check();
  await page.getByRole('button', { name: '继续工作', exact: true }).click();
  const stoppingNote = 'U01 non-first project stopping note ' + '逐章核对灯塔来信与人物伏笔。'.repeat(100);
  await page.getByLabel('停止点与下次要做的事').fill(stoppingNote);
  await page.getByLabel('显示固定参考分屏').uncheck();
  await page.getByRole('button', { name: '保存工作现场', exact: true }).click();
  await expect(page.getByText('工作现场已保存。正文仍由编辑器保存。')).toBeVisible();
  const saved = await body(await page.request.get(`${base}/workspace/resume`));
  expect(saved.item.chapter_id).toBe(destination.id);
  expect(saved.item.layout).toMatchObject({ search_query: '旧信', search_kind: 'chapter', task_query: 'original-task', show_failed_only: true });
  expect(saved.item.view.references_visible).toBe(false);
  const preferencesBefore = await body(await page.request.get(`${base}/writing-focus/preferences`));
  await page.reload();
  await expect(page.getByRole('region', { name: '当前项目上次工作' })).toContainText('U01 non-first project stopping note');
  await page.getByRole('button', { name: '查看上次工作现场', exact: true }).click();
  await expect(page.getByLabel('停止点与下次要做的事')).toHaveValue(stoppingNote);
  await page.getByRole('button', { name: '恢复章节位置', exact: true }).click();
  await expect(page.locator('.editorbar')).toContainText('U01 resume destination');
  await expect(page.getByRole('complementary', { name: '写作分屏只读参考' })).toHaveCount(0);
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport);
    const metrics = await expectVisibleWorkspaceEditor(page, true);
    expect(metrics.noteClipped).toBe(true); expect(metrics.noteHeight).toBeLessThanOrEqual(32);
    await page.screenshot({ path: info.outputPath(`u01-long-note-visible-editor-${viewport.width}.png`) });
  }
  await tools(page);
  await page.getByRole('button', { name: '搜索与命令', exact: true }).click();
  await expect(page.getByLabel('搜索中文名称、别名或正文')).toHaveValue('旧信');
  await expect(page.getByLabel('只搜当前章', { exact: true })).toBeChecked();
  await page.getByRole('button', { name: '任务中心', exact: true }).click();
  await expect(page.getByLabel('按任务 ID、类型或阶段搜索')).toHaveValue('original-task');
  await expect(page.getByLabel('只看失败或结果未知')).toBeChecked();
  expect(await body(await page.request.get(`${base}/writing-focus/preferences`))).toEqual(preferencesBefore);
  expect(modelRequests).toEqual([]);
  await page.screenshot({ path: info.outputPath('u01-two-project-restored-filters.png') });
  // A missing exact project must leave a recovery choice, never select index 0.
  await page.goto('about:blank');
  expect((await page.request.delete(`${API}/novels/${selected.id}`)).status()).toBe(204);
  await page.goto('/');
  await expect(page.getByText(/上次项目当前不存在或不可访问/)).toBeVisible();
  await expect(page.locator('.ProseMirror')).toHaveCount(0);
  await expect(page.getByRole('button', { name: inventory[0].title, exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('u01-missing-project-recovery.png') });
});
