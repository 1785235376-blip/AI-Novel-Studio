import { expect, test, type APIResponse } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
/** Authored real-API/browser contract. Local browser/geometry: NOT_RUN because
 * the execution environment denies Chromium's process-singleton socket.
 * Hosted CI must execute the body; collection/type-check is not a runtime pass. */
const API = process.env.R4_API_URL || 'http://127.0.0.1:8019/api';
async function json(response: APIResponse) {
  expect(response.ok(), `Synthetic fixture request HTTP ${response.status()}`).toBeTruthy();
  return response.json();
}

test('A04/A05 real reviewed graph, chapter knowledge boundary, revocation and shell geometry', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page);
  const owned: string[] = [];
  const secret = '沈墨藏着紫色铜钥，口令为星桥。';
  const modelCalls: string[] = [];
  page.on('request', request => { if (/\/generate\/|\/execute$/.test(new URL(request.url()).pathname) && request.method() === 'POST') modelCalls.push(request.url()); });
  try {
    expect(await json(await request.get(`${API}/novels`)), 'Dedicated File fixture must be empty').toHaveLength(0);
    const novel = await json(await request.post(`${API}/novels`, { data: { title: 'R4 temporal synthetic fixture' } })); owned.push(novel.id);
    const chapter1 = await json(await request.post(`${API}/novels/${novel.id}/chapters`, { data: { title: '第一章·未知', content: '阿澄在月港寻找旧信。' } }));
    const chapter2 = await json(await request.post(`${API}/novels/${novel.id}/chapters`, { data: { title: '第二章·获知', content: '阿澄听到沈墨讲述铜钥。' } }));
    for (const [id, name] of [['alice', '阿澄'], ['bob', '沈墨']]) await json(await request.put(`${API}/novels/${novel.id}/characters/${id}`, { data: { name, privacy_level: 'LOCAL_ONLY' } }));
    await json(await request.put(`${API}/novels/${novel.id}/locations/city`, { data: { name: '月港' } }));
    await page.goto('/');
    await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toBeVisible();
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click();
    await page.keyboard.press('Escape');
    await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '故事图谱', exact: true }).click();
    await page.getByLabel('记录标题', { exact: true }).fill('铜钥关系');
    await page.getByLabel('来源章节', { exact: true }).selectOption(chapter1.id);
    await page.getByLabel('关系起点', { exact: true }).selectOption('CHARACTER:bob');
    await page.getByLabel('关系终点', { exact: true }).selectOption('LOCATION:city');
    await page.getByLabel('关系陈述', { exact: true }).fill(secret);
    await page.getByRole('button', { name: '保存待审记录', exact: true }).click();
    const relation = page.getByRole('article').filter({ has: page.getByRole('heading', { name: '铜钥关系 · 关系', exact: true }) });
    await expect(relation).toContainText('REVIEW');
    await relation.getByRole('button', { name: '批准语义记录', exact: true }).click();
    await expect(relation).toContainText('APPROVED');
    await page.getByRole('button', { name: '人物可知视图', exact: true }).click();
    await page.getByLabel('查询章节 ID', { exact: true }).fill(chapter1.id);
    await page.getByLabel('视角人物 ID', { exact: true }).fill('alice');
    await page.getByRole('button', { name: '查询当前视图', exact: true }).click();
    await expect(page.getByRole('region', { name: '时间化关系图', exact: true })).toContainText('可见关系：0');
    await expect(page.getByText(secret, { exact: true })).toHaveCount(0);
    const base = `${API}/novels/${novel.id}/experimental/story-graph`;
    const hidden = await json(await request.post(base + '/character-context', { data: { character_id: 'alice', chapter_id: chapter2.id } }));
    expect(JSON.stringify(hidden)).not.toContain(secret);
    await page.getByRole('button', { name: '作者全知视图', exact: true }).click();
    await page.getByLabel('记录类型', { exact: true }).selectOption('KNOWLEDGE_EVENT');
    await page.getByLabel('记录标题', { exact: true }).fill('阿澄获知');
    await page.getByLabel('来源章节', { exact: true }).selectOption(chapter2.id);
    await page.getByLabel('观察人物', { exact: true }).selectOption('alice');
    await page.getByLabel('关联已审核关系', { exact: true }).selectOption({ label: '铜钥关系' });
    await page.getByRole('button', { name: '保存待审记录', exact: true }).click();
    const learned = page.getByRole('article').filter({ has: page.getByRole('heading', { name: '阿澄获知 · 知识与心智事件', exact: true }) });
    await learned.getByRole('button', { name: '批准语义记录', exact: true }).click();
    await expect(learned).toContainText('APPROVED');
    await page.getByRole('button', { name: '人物可知视图', exact: true }).click();
    await page.getByLabel('视角人物 ID', { exact: true }).fill('alice');
    await page.getByLabel('查询章节 ID', { exact: true }).fill(chapter1.id);
    await page.getByRole('button', { name: '查询当前视图', exact: true }).click();
    await expect(page.getByRole('region', { name: '时间化关系图', exact: true })).toContainText('可见关系：0');
    await page.getByLabel('查询章节 ID', { exact: true }).fill(chapter2.id);
    await expect(page.getByRole('region', { name: '时间化关系图', exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: '查询当前视图', exact: true }).click();
    await expect(page.getByRole('region', { name: '时间化关系图', exact: true })).toContainText('可见关系：1');
    await expect(page.getByRole('region', { name: '人物上下文预览', exact: true })).toContainText(secret);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(() => document.fonts.ready);
      const geometry = await page.evaluate(() => {
        const rect = (selector: string) => document.querySelector(selector)!.getBoundingClientRect();
        const panel = document.querySelector('.experimental-workbench')!;
        return { header: rect('.global-header').height, context: rect('.context-bar').height,
          sidebar: rect('.workspace-sidebar').width, inspector: rect('.workspace-inspector').width,
          status: rect('.status-bar').height, overflow: panel.scrollWidth - panel.clientWidth,
          pageOverflow: document.documentElement.scrollWidth - innerWidth };
      });
      expect(geometry).toEqual({ header: 56, context: 44, sidebar: 248, inspector: 340, status: 32, overflow: 0, pageOverflow: 0 });
      await page.screenshot({ path: info.outputPath(`story-graph-${width}x${height}.png`), fullPage: true });
    }
    await page.getByRole('button', { name: '作者全知视图', exact: true }).click();
    await learned.getByRole('button', { name: '归档语义记录', exact: true }).click();
    await expect(learned).toContainText('ARCHIVED');
    const revoked = await json(await request.post(base + '/character-context', { data: { character_id: 'alice', chapter_id: chapter2.id } }));
    expect(JSON.stringify(revoked)).not.toContain(secret);
    expect(modelCalls).toEqual([]);
    await info.attach('a04-a05-runtime-boundary.json', { body: JSON.stringify({ backend: 'REAL_FILE', frontend: 'REAL_REACT_CHROMIUM', secret_unknown_excluded: true, explicit_review_required: true, chapter_rollback: true, revocation: true, model_called: false, windows_native: 'NOT_RUN' }), contentType: 'application/json' });
  } finally {
    if (test.info().status !== test.info().expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('story-graph-failure-before-cleanup.png'), fullPage: true });
    await quiesce();
    for (const id of owned) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${id}`)).status());
  }
});
