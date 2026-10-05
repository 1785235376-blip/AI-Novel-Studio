import { test, expect, type APIResponse } from '@playwright/test';
import fs from 'node:fs/promises';
import { createPageQuiescer } from './r3-fixture-lifecycle';
import { expectVisibleWorkspaceEditor } from './workspace-editor-geometry';
const API = 'http://127.0.0.1:8019/api';
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}`).toBeTruthy(); return response.json(); }

test('U10 original no-key sample, skip/reopen, write/save/reopen and actual TXT download', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page);
  let ownedId = '';
  const forbiddenWrites: string[] = [];
  page.on('request', req => {
    const path = new URL(req.url()).pathname;
    if (req.method() !== 'GET' && /\/(generate|credentials|providers|runtimes|workflow-runs|agent-jobs)(\/|$)/.test(path)) forbiddenWrites.push(path);
  });
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  info.annotations.push({ type: 'verification', description: 'Original File API, real editor/save/reopen/export/download. No model, credentials, provider calls or response mocking. PostgreSQL is verified separately by mounted contracts.' });
  try {
    expect(await body(await request.get(`${API}/novels`))).toHaveLength(0);
    await page.goto('/');
    await page.getByRole('button', { name: '跳过指引', exact: true }).click();
    await expect(page.getByRole('button', { name: '创建小说', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '重新打开首次使用指引', exact: true }).click();
    for (const text of ['纯写作', '导入长篇', '做剧本与分镜', '有声书', '本地模型']) await expect(page.getByText(text, { exact: true })).toBeVisible();
    const creating = page.waitForResponse(r => r.url().endsWith('/experimental/first-use/sample') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建独立练习（不需要 Key）', exact: true }).click();
    const created = (await body(await creating)).item;
    ownedId = created.project_id; expect(ownedId).toBeTruthy(); expect(created.stage).toBe('READY');
    await page.getByRole('button', { name: '打开独立练习', exact: true }).click();
    await expect(page.locator('.app-shell')).toHaveCount(1);
    await expect(page.locator('.context-bar')).toContainText('灯塔来信 · 独立练习');
    await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toContainText('今晚请留一盏灯');
    await expect(page.getByRole('heading', { name: '独立练习 · 写作到导出', exact: true })).toBeVisible();
    await page.getByRole('button', { name: '收起练习指引', exact: true }).click();
    await page.getByRole('button', { name: '重新打开独立练习指引', exact: true }).click();
    const prose = '原创手工续文：林青把灯举过头顶，海面的远处也亮起了一点光。🌙';
    await page.getByRole('textbox', { name: '章节正文', exact: true }).fill(prose);
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await expect(page.locator('.editorbar')).toContainText('已保存');
    await page.reload();
    await expect(page.locator('.context-bar')).toContainText('灯塔来信 · 独立练习');
    await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toContainText(prose);
    await expect(page.getByText(/当前已保存自己的版本 v/)).toBeVisible();
    for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
      await page.setViewportSize(viewport); await page.evaluate(() => document.fonts.ready);
      await expectVisibleWorkspaceEditor(page, true);
      await page.screenshot({ path: info.outputPath(`u10-guide-${viewport.width}.png`) });
    }
    await page.getByRole('button', { name: '打开练习导出中心', exact: true }).click();
    await page.getByRole('button', { name: 'TXT 小说', exact: true }).click();
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: /^下载 .+\.txt$/ }).click();
    const file = await download, path = await file.path(); expect(path).toBeTruthy();
    expect(await fs.readFile(path!, 'utf8')).toContain(prose);
    const rows = await body(await request.get(`${API}/novels`)); expect(rows.map((r: any) => r.id)).toEqual([ownedId]);
    expect(await body(await request.get(`${API}/novels/${ownedId}/chapters`))).toHaveLength(1);
    expect(forbiddenWrites).toEqual([]);
  } finally {
    if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('u10-failure-before-cleanup.png'), fullPage: true }).catch(() => {});
    await quiet();
    if (ownedId) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(ownedId)}`)).status());
  }
});
