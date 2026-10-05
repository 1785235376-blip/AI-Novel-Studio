import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api', UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function openSimulator(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '剧情推演', exact: true }).click();
}
test('A01 explicit synthetic local candidates use original character author broker job then manual planning review', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '', jobId = '';
  const sends: string[] = [];
  page.on('request', r => { if (r.method() === 'POST' && r.url().endsWith('/model/dispatch')) sends.push(r.url()); });
  info.annotations.push({ type: 'verification', description: 'Actual React + File + A05 author projection + original broker/JobManager. Shipped labeled synthetic route only; no HTTP response mocks, downloads, paid inference or model-quality claim. Quality NOT_RUN. Local Chromium launch NOT_RUN; hosted CI must execute.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('A01 synthetic bounded model candidates');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await body(await creating)).id;
    const base = `${API}/novels/${nid}/experimental`;
    const made = await body(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: '合成城门章节', content: 'SYNTHETIC_OMNISCIENT_MANUSCRIPT_NOT_SENT' } }));
    const chapter = await body(await request.get(`${API}/chapters/${made.id}`, { headers }));
    await body(await request.put(`${API}/novels/${nid}/characters/alice`, { headers, data: { name: '阿澄', privacy_level: 'LOCAL_ONLY' } }));
    const graph = await body(await request.post(`${base}/planning/graphs`, { headers, data: { title: '现有待审规划', links: { chapter_ids: [chapter.id] } } }));
    const context = await body(await request.post(`${base}/story-simulator/context`, { headers, data: { chapter_id: chapter.id, expected_version: chapter.version, character_id: 'alice' } }));
    let run = await body(await request.post(`${base}/story-simulator/runs`, { headers, data: { chapter_ids: [chapter.id], expected_versions: { [chapter.id]: chapter.version }, chapter_id: chapter.id, character_id: 'alice', node_id: graph.root_node_id, expected_node_version: 1, context_digest: context.context_digest, max_steps: 2, max_branches: 2, character_goal: '进入城门', routes: [{ id: 'manual', title: '作者手工路线', events: [{ id: 'wait', title: '等待同伴', at: 1, adds: ['companion-arrived'] }] }] } }));
    run = await body(await request.post(`${base}/story-simulator/runs/${run.id}/step`, { headers, data: { expected_version: run.version } }));
    const catalog = await body(await request.get(`${base}/story-simulator/catalog`, { headers }));
    const route = catalog.model_routes.find((r: any) => r.provider_id === 'mock'); expect(route.available).toBe(true); expect(route.synthetic).toBe(true);
    await openSimulator(page);
    const panel = page.getByRole('region', { name: '有界剧情推演', exact: true });
    await panel.getByLabel('查看剧情推演记录', { exact: true }).selectOption(run.id);
    await panel.getByLabel('推演候选本地模型', { exact: true }).selectOption(route.route_id);
    const previewResponse = page.waitForResponse(r => r.url().endsWith(`/runs/${run.id}/model/preview`) && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '预览模型候选请求（不发送）', exact: true }).click();
    const previewed = await body(await previewResponse);
    expect(previewed.model_preview.author.character_id).toBe('alice');
    expect(previewed.model_preview.source_strategy).toBe('A05_CHARACTER_ONLY_NO_MANUSCRIPT');
    expect(JSON.stringify(previewed.model_preview.request)).not.toContain(chapter.content);
    expect(previewed.model_preview.request.context.character_viewpoint.character_id).toBe('alice');
    expect(sends).toHaveLength(0);
    await expect(panel.getByRole('button', { name: '发送这一次模型候选请求', exact: true })).toBeDisabled();
    await panel.getByText('核对完整发送指令与角色上下文', { exact: true }).click();
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height });
      await panel.getByRole('region', { name: '模型候选发送预览', exact: true }).scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`simulator-model-preview-${width}.png`) });
    }
    await panel.getByLabel('我已核对这份发送内容、当前本地路线与零费用上限，允许发送一次模型候选请求', { exact: true }).check();
    const dispatchResponse = page.waitForResponse(r => r.url().endsWith(`/runs/${run.id}/model/dispatch`) && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '发送这一次模型候选请求', exact: true }).click();
    const running = await body(await dispatchResponse); jobId = running.model_execution.job_id;
    await expect.poll(async () => (await body(await request.get(`${base}/model-broker/jobs/${running.model_execution.reservation_id}`, { headers }))).ledger.status, { timeout: 90000 }).toBe('SETTLED');
    expect(sends).toHaveLength(1);
    await panel.getByRole('button', { name: '检查原模型请求结果', exact: true }).click();
    const candidateTitle = '合成候选：等待并核对现有线索';
    await expect(panel.getByRole('article', { name: `比较路线 ${candidateTitle}`, exact: true })).toContainText('SYNTHETIC_PROTOCOL_ONLY');
    await expect(panel.getByRole('button', { name: '将选中模型候选创建为独立推演', exact: true })).toBeDisabled();
    await panel.getByLabel(`选用模型候选 ${candidateTitle} 创建独立推演`, { exact: true }).check();
    await panel.getByLabel('已核对所选模型假设、证据与违规，只创建待手动推进的独立推演', { exact: true }).check();
    const selectedResponse = page.waitForResponse(r => r.url().endsWith(`/runs/${run.id}/model/select`) && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '将选中模型候选创建为独立推演', exact: true }).click();
    const selected = await body(await selectedResponse); expect(selected.id).not.toBe(run.id); expect(selected.status).toBe('READY'); expect(selected.expansions).toBe(0);
    expect((await body(await request.get(`${base}/planning/proposals`, { headers }))).items).toHaveLength(0);
    await expect(panel).toContainText('此记录由人工选用模型候选创建');
    await panel.getByRole('button', { name: '推进一步', exact: true }).click();
    await panel.getByLabel(`选择路线 ${candidateTitle} 另存待审规划`, { exact: true }).check();
    await panel.getByLabel('已核对所选路线的违规、未决问题和动机假设，仅另存为待审规划', { exact: true }).check();
    const savedResponse = page.waitForResponse(r => r.url().endsWith(`/runs/${selected.id}/save`) && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '将所选路线另存为待审规划', exact: true }).click();
    const saved = await body(await savedResponse);
    expect((await body(await request.get(`${base}/planning/proposals/${saved.proposal_id}`, { headers }))).status).toBe('REVIEW');
    expect((await request.post(`${API}/generation/${jobId}/accept`, { headers, data: {} })).status()).toBe(409);
    expect((await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }))).content).toBe(chapter.content);
    expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(1);
    await page.screenshot({ path: info.outputPath('simulator-model-manually-selected-review.png'), fullPage: true });
    await quiesce.drain(); await page.reload(); await openSimulator(page);
    await panel.getByLabel('查看剧情推演记录', { exact: true }).selectOption(selected.id);
    await expect(panel).toContainText('已另存待审规划'); expect(sends).toHaveLength(1);
    await body(await request.put(`${API}/chapters/${chapter.id}`, { headers, data: { version: chapter.version, content: 'SYNTHETIC_SOURCE_CHANGED' } }));
    await panel.getByRole('button', { name: '刷新推演与来源（保留输入）', exact: true }).click();
    await expect(panel).toContainText('旧来源的路线与证据已隐藏');
    expect((await request.post(`${base}/planning/proposals/${saved.proposal_id}/approve`, { headers, data: { expected_version: 1 } })).status()).toBe(409);
  } finally {
    if (!page.isClosed() && info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('simulator-model-failure.png'), fullPage: true }).catch(() => {});
    if (jobId) await request.post(`${API}/generation/${jobId}/cancel`, { headers }).catch(() => {});
    await quiesce(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status());
  }
});
