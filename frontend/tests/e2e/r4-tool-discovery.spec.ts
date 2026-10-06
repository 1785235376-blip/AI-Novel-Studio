import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';

const API = 'http://127.0.0.1:8019/api';
const owned = new WeakMap<Page, string[]>();
const quiet = new WeakMap<Page, () => Promise<void>>();

test.beforeEach(({ page }) => {
  owned.set(page, []); quiet.set(page, createPageQuiescer(page));
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  test.info().annotations.push({ type: 'verification', description: 'Real React/File API journey with synthetic data. Local tool filtering must not issue requests, change drafts, or invoke a model.' });
});

test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('tool-discovery-failure.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!();
  for (const id of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(id)}`)).status());
});

test('U03/U10 find enabled tools with the keyboard while preserving the current draft', async ({ page, request }, info) => {
  await page.goto('/');
  await page.getByPlaceholder('小说名称').fill(`Synthetic tool discovery ${test.info().testId}`);
  const creating = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const created = await creating; expect(created.ok()).toBe(true);
  const novel = await created.json(); owned.get(page)!.push(novel.id);
  const chapterResponse = await request.post(`${API}/novels/${encodeURIComponent(novel.id)}/chapters`, { data: { title: '合成工具发现', content: '这段合成正文不因查找工具而改变。' } });
  expect(chapterResponse.ok()).toBe(true); const chapter = await chapterResponse.json();
  const before = await (await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`)).json();
  await page.reload();
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');

  const workbench = page.getByRole('region', { name: 'Experimental 工作台', exact: true });
  const navigation = workbench.getByRole('navigation', { name: '实验功能', exact: true });
  const search = workbench.getByRole('searchbox', { name: '查找已启用工具', exact: true });
  await navigation.getByRole('button', { name: '分层规划', exact: true }).click();
  await expect(workbench.getByRole('button', { name: '刷新实验记录', exact: true })).toBeEnabled();
  const count = await navigation.getByRole('button').count(); expect(count).toBeGreaterThan(30);
  const draft = workbench.getByLabel('规划名称', { exact: true });
  await draft.fill('保留尚未提交的规划草稿');
  const localRequests: string[] = [];
  const trackRequest = (req: import('@playwright/test').Request) => { if (req.url().includes(`/api/novels/${novel.id}/experimental/`)) localRequests.push(`${req.method()} ${req.url()}`); };
  page.on('request', trackRequest);

  await search.fill('  EXPERIMENTAL.OFFLINE_SYNC_V2  ');
  await expect(navigation.getByRole('button')).toHaveCount(1);
  await expect(navigation.getByRole('button', { name: '离线同步', exact: true })).toBeVisible();
  await expect(draft).toHaveValue('保留尚未提交的规划草稿');
  await search.press('Enter');
  await expect(workbench.getByRole('heading', { name: '分层创作规划 V2', exact: true })).toBeVisible();
  await search.fill('没有这样的已启用工具');
  await expect(navigation.getByRole('button')).toHaveCount(0);
  await expect(workbench.getByText('没有匹配的已启用工具。请更换关键词或清除筛选。', { exact: true })).toBeVisible();
  await expect(draft).toHaveValue('保留尚未提交的规划草稿');
  await page.screenshot({ path: info.outputPath('tool-discovery-no-result-keeps-draft.png'), fullPage: true });
  await search.press('Tab');
  await expect(workbench.getByRole('button', { name: '清除筛选', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(search).toBeFocused(); await expect(search).toHaveValue('');
  await expect(navigation.getByRole('button')).toHaveCount(count);
  await expect(navigation.getByRole('button', { name: '分层规划', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(draft).toHaveValue('保留尚未提交的规划草稿');
  expect(localRequests).toEqual([]);
  page.off('request', trackRequest);

  // Native Tab/Enter activates the chosen enabled button, never the search field.
  await search.fill('视觉'); await search.press('Tab'); await page.keyboard.press('Tab');
  await expect(navigation.getByRole('button', { name: '视觉 Embedding', exact: true })).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(workbench.getByText('NOT_CONFIGURED', { exact: true })).toBeVisible();
  await expect(search).toHaveValue(''); await expect(navigation.getByRole('button')).toHaveCount(count);
  await expect(navigation.getByRole('button', { name: '视觉 Embedding', exact: true })).toHaveAttribute('aria-pressed', 'true');
  const after = await (await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`)).json();
  expect(after.version).toBe(before.version); expect(after.document).toEqual(before.document); expect(after.content).toBe(before.content);
});
