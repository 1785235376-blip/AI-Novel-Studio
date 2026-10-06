import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';

const API = 'http://127.0.0.1:8019/api';
const owned = new WeakMap<Page, string[]>();
const quiet = new WeakMap<Page, () => Promise<void>>();
async function openResearch(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '创作资料库', exact: true }).click();
}
test.beforeEach(({ page }) => {
  owned.set(page, []); quiet.set(page, createPageQuiescer(page));
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  test.info().annotations.push({ type: 'verification', description: 'Real File API and React UI; synthetic UTF-8 local source; no business mocks, external fetch, models or paid services. Local browser NOT_RUN; CI execution required.' });
});
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('research-failure.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!();
  for (const id of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(id)}`)).status());
});

test('J07 local import, exact citation, original reviewed setting and revocation invalidate all visible derivatives', async ({ page }, info) => {
  const external: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /fetch-webpage|generate|execute/.test(request.url())) external.push(request.url()); });
  await page.goto('/');
  await page.getByPlaceholder('小说名称').fill(`Synthetic research ${test.info().testId}`);
  const creating = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await (await creating).json(); owned.get(page)!.push(novel.id);
  await openResearch(page);
  const panel = page.getByRole('region', { name: '分层研究资料库', exact: true });
  await expect(panel.getByText('还没有可见资料', { exact: true })).toBeVisible();
  await panel.getByLabel('资料标题', { exact: true }).fill('合成潮汐手记');
  await panel.getByLabel('资料作者', { exact: true }).fill('合成测试作者');
  await panel.getByLabel('来源版本或版次', { exact: true }).fill('合成第一版');
  await panel.getByLabel('选择本地资料文件', { exact: true }).setInputFiles({ name: 'synthetic-tide.md', mimeType: 'text/markdown', buffer: Buffer.from('合成潮门每晚关闭。\n\n合成灯塔帮助夜航。', 'utf8') });
  const importing = page.waitForResponse(response => response.url().endsWith('/research-library/sources/import') && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '导入所选本地文件', exact: true }).click();
  const source = await (await importing).json(); expect(source.format).toBe('MD');
  await panel.getByRole('button', { name: '打开来源 合成潮汐手记', exact: true }).click();
  await panel.getByRole('checkbox', { name: '选择引用：第 1 段', exact: true }).check();
  await panel.getByRole('button', { name: '核对原段落 1', exact: true }).click();
  await expect(panel.getByRole('region', { name: '引用原文', exact: true })).toContainText('合成潮门每晚关闭。');
  await panel.getByLabel('研究笔记标题', { exact: true }).fill('港口参考笔记');
  await panel.getByLabel('研究笔记内容', { exact: true }).fill('原创故事改为根据蓝灯决定开关。');
  const noting = page.waitForResponse(response => response.url().endsWith('/research-library/notes') && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '保存带引用的研究笔记', exact: true }).click();
  expect((await (await noting).json()).citations[0]).toMatchObject(source.paragraphs[0].citation);
  await panel.getByLabel('原创设定草稿标题', { exact: true }).fill('原创蓝灯潮门');
  await panel.getByLabel('原创设定内容', { exact: true }).fill('虚构的潮门只有蓝灯照射时才能打开。');
  await panel.getByRole('checkbox', { name: '已写成原创虚构设定，并核对所选参考引用', exact: true }).check();
  const adopting = page.waitForResponse(response => response.url().endsWith('/research-library/setting-drafts') && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '采用为原创设定草稿', exact: true }).click();
  const draft = await (await adopting).json(); expect(draft.canon_promotion_available).toBe(false);
  const reviewing = page.waitForResponse(response => response.url().endsWith(`/setting-drafts/${draft.id}/review`) && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '审核这个设定草稿', exact: true }).click();
  expect((await (await reviewing).json()).status).toBe('RESEARCH_REVIEWED');
  expect((await (await page.request.get(`${API}/novels/${novel.id}/experimental/world/canon`)).json()).items).toEqual([]);
  await panel.getByRole('button', { name: '查看当前来源反向引用', exact: true }).click();
  await expect(panel.getByLabel('来源反向引用')).toContainText('港口参考笔记');
  await expect(panel.getByLabel('来源反向引用')).toContainText('原创蓝灯潮门');
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await panel.scrollIntoViewIfNeeded(); await page.screenshot({ path: info.outputPath(`research-${width}.png`) });
  }
  await panel.getByRole('checkbox', { name: '我知道撤销或删除会使关联检索、笔记、上下文和设定引用失效', exact: true }).check();
  const revoking = page.waitForResponse(response => response.url().endsWith(`/sources/${source.id}/revoke`) && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '撤销来源访问', exact: true }).click();
  expect((await (await revoking).json()).derived_context_invalidated).toBe(true);
  await expect(panel.getByRole('button', { name: '打开来源 合成潮汐手记', exact: true })).toHaveCount(0);
  await expect(panel.getByRole('button', { name: '重新核对设定草稿', exact: true })).toHaveCount(0);
  await panel.getByLabel('资料检索词', { exact: true }).fill('合成潮门');
  await panel.getByRole('button', { name: '检索已保存资料', exact: true }).click();
  await expect(panel.getByText('未找到可见的匹配段落。', { exact: true })).toBeVisible();
  const stale = await page.request.post(`${API}/novels/${novel.id}/experimental/research-library/context-preview`, { data: { citations: [source.paragraphs[0].citation] } });
  expect(stale.status()).toBe(404);
  expect(external).toEqual([]);
  await page.screenshot({ path: info.outputPath('research-revoked-local-only.png') });
});
