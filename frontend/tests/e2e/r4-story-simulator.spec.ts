import { expect, test, type APIResponse } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';

const API = 'http://127.0.0.1:8019/api';
async function json(response: APIResponse) {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy();
  return response.json();
}
/** Real File API/React journey. No business-response mocks and no model.
 * Local browser NOT_RUN: the environment denies Chromium launch. CI must run
 * these actual assertions; --list/type-check never counts as browser PASS. */
test('J05 bounded manual comparison, violations, cancellation, pending planning and stale-source recovery', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page), owned: string[] = [], modelRequests: string[] = [];
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  page.on('request', r => { if (r.method() === 'POST' && /\/generate(?:\/|$)|\/execute$/.test(new URL(r.url()).pathname)) modelRequests.push(r.url()); });
  info.annotations.push({ type: 'verification', description: 'Synthetic manual deterministic events against mounted File API. Model calls forbidden. Browser execution pending hosted CI; no local screenshot or runtime claim.' });
  try {
    await page.goto('/');
    await page.getByPlaceholder('小说名称').fill(`R4 simulator synthetic ${info.testId}`);
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    const novel = await json(await created); owned.push(novel.id);
    await page.getByRole('button', { name: '新建章节', exact: true }).click();
    await page.getByLabel('章节标题', { exact: true }).fill('门前的选择');
    const added = page.waitForResponse(r => r.url().endsWith(`/novels/${novel.id}/chapters`) && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建章节', exact: true }).click();
    const chapter = await json(await added);
    await json(await request.put(`${API}/novels/${novel.id}/characters/alice`, { data: { name: '阿澄', privacy_level: 'LOCAL_ONLY' } }));
    const base = `${API}/novels/${novel.id}/experimental`;
    const graph = await json(await request.post(base + '/planning/graphs', { data: { title: '已有城门规划', links: { chapter_ids: [chapter.id] } } }));
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
    await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '剧情推演', exact: true }).click();
    const panel = page.getByRole('region', { name: '有界剧情推演', exact: true });
    await expect(panel.getByText('还没有剧情推演记录', { exact: true })).toBeVisible();
    expect((await json(await request.get(base + '/story-simulator/runs'))).items).toHaveLength(0);
    await panel.getByLabel('推演人物', { exact: true }).selectOption('alice');
    await panel.getByLabel('待审规划的目标节点', { exact: true }).selectOption(graph.root_node_id);
    await panel.getByRole('button', { name: '读取并核对人物已知信息', exact: true }).click();
    await expect(panel.getByText('此视角没有可选的已知事实或秘密', { exact: true })).toBeVisible();
    await panel.getByLabel('人物目标', { exact: true }).fill('进入城门');
    await panel.getByLabel('人物动机假设（不作为已证实事实）', { exact: true }).fill('她可能为保护友人而选择等待。');
    await panel.getByLabel('路线 1 名称', { exact: true }).fill('直接开门');
    await panel.getByLabel('路线 1 事件 1 名称', { exact: true }).fill('使用尚未取得的钥匙');
    await panel.getByText('路线 1 事件 1 前提、变化与未决问题', { exact: true }).click();
    await panel.getByLabel('路线 1 事件 1 前提事实（每行一条）', { exact: true }).fill('取得钥匙');
    await panel.getByLabel('路线 1 事件 1 未决问题', { exact: true }).fill('钥匙在哪里？');
    await panel.getByLabel('路线 2 名称', { exact: true }).fill('等候向导');
    await panel.getByLabel('路线 2 事件 1 名称', { exact: true }).fill('向导抵达');
    await panel.getByText('路线 2 事件 1 前提、变化与未决问题', { exact: true }).click();
    await panel.getByLabel('路线 2 事件 1 新增事实（每行一条）', { exact: true }).fill('向导抵达');
    const started = page.waitForResponse(r => r.url().endsWith('/story-simulator/runs') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '保存输入并创建推演', exact: true }).click();
    const run = await json(await started); expect(run.status).toBe('READY'); expect(run.expansions).toBe(0); expect(run.model_called).toBe(false);
    await panel.getByRole('button', { name: '推进一步', exact: true }).click();
    await expect(panel.getByRole('article', { name: '比较路线 直接开门', exact: true })).toContainText('UNMET_PREREQUISITE');
    await expect(panel.getByRole('article', { name: '比较路线 等候向导', exact: true })).toContainText('状态变化已应用');
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      await panel.getByRole('article', { name: '比较路线 等候向导', exact: true }).scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`story-simulator-${width}.png`) });
    }
    await panel.getByRole('radio', { name: '选择路线 等候向导 另存待审规划', exact: true }).check();
    await panel.getByRole('checkbox', { name: '已核对所选路线的违规、未决问题和动机假设，仅另存为待审规划', exact: true }).check();
    const saved = page.waitForResponse(r => r.url().endsWith(`/story-simulator/runs/${run.id}/save`) && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '将所选路线另存为待审规划', exact: true }).click();
    const receipt = await json(await saved);
    const proposal = await json(await request.get(base + '/planning/proposals/' + receipt.proposal_id));
    expect(proposal.status).toBe('REVIEW'); expect(proposal.simulation_provenance.run_id).toBe(run.id);
    expect((await json(await request.get(base + '/planning/graphs/' + graph.id))).nodes[0].status).toBe('DRAFT');
    expect((await json(await request.get(`${API}/chapters/${chapter.id}`))).version).toBe(chapter.version);
    const restarting = page.waitForResponse(r => r.url().endsWith('/story-simulator/runs') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '保存输入并创建推演', exact: true }).click();
    const second = await json(await restarting);
    await panel.getByRole('button', { name: '取消本次推演', exact: true }).click();
    await expect(panel.getByRole('button', { name: '推进一步', exact: true })).toBeDisabled();
    expect((await json(await request.get(base + '/story-simulator/runs/' + second.id))).expansions).toBe(0);
    await json(await request.put(`${API}/chapters/${chapter.id}`, { data: { version: chapter.version, content: '新版本：阿澄已取得钥匙。' } }));
    await panel.getByRole('button', { name: '刷新推演与来源（保留输入）', exact: true }).click();
    await panel.getByLabel('查看剧情推演记录', { exact: true }).selectOption(run.id);
    await expect(panel.getByText(/旧来源的路线与证据已隐藏/)).toBeVisible();
    await expect(panel.getByRole('article', { name: '比较路线 直接开门', exact: true })).toHaveCount(0);
    expect((await json(await request.get(base + '/planning/proposals'))).items).toHaveLength(0);
    expect(modelRequests).toEqual([]);
  } finally {
    await quiesce();
    for (const id of owned) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${id}`)).status());
  }
});
