import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
const owned = new WeakMap<Page, string[]>();
const quiet = new WeakMap<Page, () => Promise<void>>();
async function tools(page: Page, label: string) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: label, exact: true }).click();
}
test.beforeEach(({ page }) => {
  owned.set(page, []); quiet.set(page, createPageQuiescer(page));
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  test.info().annotations.push({ type: 'verification', description: 'Authored real File API/React journey; Chromium execution NOT_RUN because platform EPERM, no launch retry. Synthetic manuscript only, no model/network/push calls.' });
});
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('reader-session-failure.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!();
  for (const id of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(id)}`)).status());
});

test('J08 read actual chapters, annotate exact quote, preflight without write, and finish a persisted session', async ({ page, request }, info) => {
  const forbidden: string[] = [];
  page.on('request', req => { if (req.method() === 'POST' && /\/generate|\/execute|\/dispatch|\/exports\b/.test(req.url())) forbidden.push(req.url()); });
  await page.goto('/');
  await page.getByPlaceholder('小说名称').fill(`Synthetic reader ${test.info().testId}`);
  const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await (await creating).json(); owned.get(page)!.push(novel.id);
  const created = await request.post(`${API}/novels/${encodeURIComponent(novel.id)}/chapters`, { data: { title: '合成潮汐', content: '甲🙂。\n\n阿青！！ the the 海港。' } });
  expect(created.ok()).toBeTruthy(); const chapter = await created.json();
  await page.reload();
  await tools(page, '阅读与发布预检');
  const reader = page.getByRole('region', { name: '阅读校对与发布预检', exact: true });
  await expect(reader).toContainText('甲🙂。');
  await reader.getByLabel('模拟阅读宽度').selectOption('390');
  await reader.getByRole('button', { name: '合成潮汐', exact: true }).focus();
  await page.keyboard.press('Enter');
  await expect(reader.locator('.reader-chapter')).toBeFocused();
  await reader.getByRole('button', { name: '注释第 2 段', exact: true }).click();
  await reader.getByLabel('段落注释').fill('合成阅读批注，保留原文。');
  const annotation = page.waitForResponse(r => r.url().endsWith('/reader-preflight/annotations') && r.request().method() === 'POST');
  await reader.getByRole('button', { name: '保存注释', exact: true }).click();
  expect((await annotation).ok()).toBeTruthy();
  await reader.getByLabel('忽略建议的理由').fill('人物在有意强调');
  await reader.getByRole('button', { name: /忽略建议/ }).first().click();
  const before = await (await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`)).json();
  const checking = page.waitForResponse(r => r.url().endsWith('/reader-preflight/check') && r.request().method() === 'POST');
  await reader.getByRole('button', { name: '运行发布预检', exact: true }).click();
  const report = await (await checking).json(); expect(report.read_only).toBe(true); expect(report.model_calls).toBe(0);
  expect(report.target_renderer_verified).toBe(false); expect(report.export_snapshot_created).toBe(false);
  const after = await (await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`)).json(); expect(after.version).toBe(before.version); expect(after.document).toEqual(before.document);
  await page.screenshot({ path: info.outputPath('reader-390-preflight.png'), fullPage: true });
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '本次写作目标', exact: true }).click();
  const session = page.getByRole('region', { name: '写作目标与本次回顾', exact: true });
  await session.getByLabel('本次写作目标（可选）').fill('补上真实保存的结尾');
  await session.getByRole('button', { name: '开始本次写作', exact: true }).click();
  await expect(session.getByLabel('本次停止点笔记')).toBeVisible();
  // A real persisted save through the original chapter authority provides evidence.
  const write = await request.put(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { data: { version: after.version, content: after.content + '\n\n合成结尾。', source: 'USER' } });
  expect(write.ok()).toBeTruthy();
  await session.getByLabel('本次停止点笔记').fill('下次核对合成潮汐时间。');
  await session.getByRole('button', { name: '结束本次写作并回顾', exact: true }).click();
  await expect(session).toContainText('实际保存历史事件 1 次');
  await expect(session).toContainText('下次核对合成潮汐时间。');
  await expect(session.getByLabel('启用自定应用内提醒')).not.toBeChecked();
  await page.screenshot({ path: info.outputPath('session-persisted-recap.png'), fullPage: true });
  expect(forbidden).toEqual([]);
});
