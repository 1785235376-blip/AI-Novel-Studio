import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function openImpact(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '修改影响与更新', exact: true }).click();
}

test('J11 changes affect recorded descendants only; locked outputs survive explicit selected refresh', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '';
  info.annotations.push({ type: 'verification', description: 'Real File API + UI + existing deterministic synthetic PNG executor. No real image/video/audio model, paid provider, manuscript rewriting or output approval.' });
  try {
    await page.goto('/');
    await page.getByPlaceholder('小说名称').fill('U06 synthetic selective change');
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    nid = (await body(await created)).id;
    const chapter = await body(await page.request.post(`${API}/novels/${nid}/chapters`, { data: { title: '改动源章节', content: '阿澄带着旧地图走进月港。' } }));
    const base = `${API}/novels/${nid}/experimental`;
    const create = async (title: string, chapters: string[]) => {
      const brief = await body(await page.request.post(`${base}/media/cover-briefs`, { data: { title, chapter_ids: chapters } }));
      const task = await body(await page.request.post(`${base}/media/tasks`, { data: { brief_id: brief.id, expected_brief_version: 1, adapter_id: 'mock-image-v1', candidate_count: 1 } }));
      return body(await page.request.post(`${base}/media/tasks/${task.id}/execute`, { data: { expected_version: 1 } }));
    };
    const selected = await create('选择更新的结果', [chapter.id]), locked = await create('满意成果', [chapter.id]), unrelated = await create('无关结果', []);
    const before = await body(await page.request.get(`${base}/media/tasks`));
    const changed = await body(await page.request.put(`${API}/chapters/${chapter.id}`, { data: { version: chapter.version, content: '阿澄带着新地图走进月港。' } }));
    await openImpact(page);
    await page.getByLabel('发生修改的来源', { exact: true }).selectOption(`CHAPTER:${chapter.id}`);
    const card = (id: string) => page.locator('article.experimental-record').filter({ has: page.getByRole('checkbox', { name: new RegExp(id) }) });
    await expect(card(selected.id)).toContainText('待更新 / 待核对');
    await expect(page.getByRole('region', { name: '修改影响清单' })).not.toContainText(unrelated.id);
    await card(locked.id).getByRole('button', { name: '锁定满意成果', exact: true }).click();
    await expect(card(locked.id)).toContainText('满意成果已锁定');
    await expect(card(locked.id).getByRole('checkbox')).toBeDisabled();
    await card(selected.id).getByRole('checkbox').check();
    await page.getByRole('button', { name: '预检选中的 1 项', exact: true }).click();
    await expect(page.getByRole('region', { name: '选择性更新预检' })).toContainText('可准备新的选中任务');
    expect((await body(await page.request.get(`${base}/media/tasks`))).items.length).toBe(before.items.length);
    const prepared = page.waitForResponse(r => r.url().includes('/change-impact/preflights/') && r.url().endsWith('/prepare'));
    await page.getByRole('button', { name: '仅准备这些选中更新', exact: true }).click();
    const refresh = (await body(await prepared)).items[0];
    expect(refresh.status).toBe('QUEUED');
    expect((await body(await page.request.get(`${base}/media/tasks`))).items.length).toBe(before.items.length + 1);
    await page.getByRole('button', { name: '执行此选中任务', exact: true }).click();
    await expect(page.getByRole('region', { name: '选择性更新历史' })).toContainText('SUCCEEDED');
    await expect(page.getByRole('region', { name: '选择性更新历史' })).toContainText('PENDING_REVIEW');
    const after = await body(await page.request.get(`${base}/media/tasks`));
    for (const original of [selected, locked, unrelated]) expect(after.items.find((t: any) => t.id === original.id)).toEqual(before.items.find((t: any) => t.id === original.id));
    const newTask = after.items.find((t: any) => t.id === refresh.task_id);
    expect(newTask.sources[chapter.id].version).toBe(changed.version);
    expect((await body(await page.request.get(`${API}/novels/${nid}/assets`))).length).toBe(0);
    const manuscript = await body(await page.request.get(`${API}/chapters/${chapter.id}`));
    expect(manuscript.content).toBe(changed.content); expect(manuscript.version).toBe(changed.version);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`selective-change-${width}.png`) });
    }
    await page.reload(); await openImpact(page);
    await expect(page.getByRole('region', { name: '选择性更新历史' })).toContainText('SUCCEEDED');
    await page.getByLabel('发生修改的来源', { exact: true }).selectOption(`CHAPTER:${chapter.id}`);
    await expect(card(locked.id)).toContainText('满意成果已锁定');
    await card(selected.id).getByRole('checkbox').check();
    await page.getByRole('button', { name: '预检选中的 1 项', exact: true }).click();
    await page.getByRole('button', { name: '仅准备这些选中更新', exact: true }).click();
    await page.getByRole('button', { name: '取消此次更新', exact: true }).click();
    await expect(page.getByRole('region', { name: '选择性更新历史' })).toContainText('CANCELLED');
    await page.getByRole('button', { name: '审核更新产物', exact: true }).click();
    await expect(page.getByRole('heading', { name: /封面与分镜/ }).first()).toBeVisible();
  } finally {
    await quiesce();
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());
  }
});
