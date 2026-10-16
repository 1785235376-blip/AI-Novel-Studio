import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api';
const UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function tools(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '作品审稿', exact: true }).click();
}

test('A03 registered synthetic Judge previews exact evidence, separately sends one original job and persists advisory opinions', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '', jobId = '';
  info.annotations.push({ type: 'verification', description: 'Actual React + File + original AuthorPreparer/Broker/JobManager/review_threads production composition. Shipped labeled synthetic provider, no response mocks or paid/real-model inference. Real-model quality NOT_RUN. Local Chromium is known EPERM and not retried; hosted CI must establish browser execution.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('A03 synthetic registered Judge');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await body(await creating)).id;
    const base = `${API}/novels/${nid}/experimental`;
    const created = await body(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: '合成灯塔', content: '她把灯留在门边，等待夜航的船只返回。\n\n她把灯留在门边，等待夜航的船只返回。' } }));
    const chapter = await body(await request.get(`${API}/chapters/${created.id}`, { headers }));
    await tools(page);
    const panel = page.getByRole('region', { name: '叙事证据审阅', exact: true });
    await panel.getByRole('checkbox', { name: `审阅章节：${chapter.title} · v${chapter.version}`, exact: true }).check();
    const started = page.waitForResponse(r => r.url().endsWith('/narrative-judge/runs') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '检查所选已保存章节', exact: true }).click();
    const ruleRun = await body(await started); expect(ruleRun.model_called).toBe(false);
    expect(ruleRun.findings.some((f: any) => f.origin === 'DETERMINISTIC')).toBe(true);
    const model = panel.getByRole('region', { name: '已注册模型审稿', exact: true });
    await model.getByRole('button', { name: '查看已注册本地审稿路线', exact: true }).click();
    const catalog = await body(await request.get(`${base}/narrative-judge/model/catalog`, { headers }));
    const route = catalog.routes.find((r: any) => r.provider_id === 'mock'); expect(route.synthetic).toBe(true);
    await model.getByLabel('已注册本地审稿模型', { exact: true }).selectOption(route.route_id);
    const previewing = page.waitForResponse(r => r.url().endsWith(`/runs/${ruleRun.id}/model/preview`) && r.request().method() === 'POST');
    await model.getByRole('button', { name: '准备准确模型审稿预览', exact: true }).click();
    const prepared = await body(await previewing); const preview = prepared.model_preview;
    expect(preview.request.context).toEqual({}); expect(preview.broker.chosen.price.reserve_microusd).toBe(0);
    expect(preview.sources[chapter.id].version).toBe(chapter.version); expect(preview.independence).toBe('UNVERIFIED');
    expect(JSON.parse(preview.author.instruction.split('NARRATIVE_JUDGE_REQUEST_V1\n')[1]).chapters[0].content).toBe(chapter.content);
    expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(0);
    await expect(model.getByRole('button', { name: '明确发送此次本地模型审稿', exact: true })).toBeDisabled();
    await expect(model.getByLabel('准确模型请求（含完整选中证据）', { exact: true })).toHaveValue(JSON.stringify(preview.request, null, 2));
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready); await model.scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`judge-model-preview-${width}.png`) });
    }
    await model.getByLabel('已核对完整证据、版本、模型身份与零费用预占', { exact: true }).check();
    const sending = page.waitForResponse(r => r.url().endsWith(`/runs/${ruleRun.id}/model/dispatch`) && r.request().method() === 'POST');
    await model.getByRole('button', { name: '明确发送此次本地模型审稿', exact: true }).click();
    const running = await body(await sending); jobId = running.model_execution.job_id;
    await expect(model.getByRole('button', { name: '明确发送此次本地模型审稿', exact: true })).toHaveCount(0);
    await expect.poll(async () => (await body(await request.get(`${base}/model-broker/jobs/${running.model_execution.reservation_id}`, { headers }))).ledger.status, { timeout: 90000 }).toBe('SETTLED');
    const reconciling = page.waitForResponse(r => r.url().endsWith(`/runs/${ruleRun.id}/model/refresh`) && r.request().method() === 'POST');
    await model.getByRole('button', { name: '查询原任务并核对模型证据', exact: true }).click();
    const result = await body(await reconciling); expect(result.model_execution.status).toBe('COMPLETED');
    const opinion = result.findings.find((f: any) => f.origin === 'MODEL_ASSESSMENT'); expect(opinion).toBeTruthy();
    expect(opinion.model.synthetic).toBe(true); expect(opinion.quality_verification).toBe('SYNTHETIC_PROTOCOL_ONLY');
    const finding = panel.getByRole('article', { name: `检查线索 ${opinion.id}`, exact: true });
    await expect(finding).toContainText('合成协议测试，未调用真实模型');
    await finding.getByLabel(`审核理由 ${opinion.id}`, { exact: true }).fill('这是合成协议测试意见，保留原文，由作者另行判断。');
    await finding.getByRole('button', { name: '记录忽略理由', exact: true }).click();
    await expect(finding).toContainText('已忽略');
    expect((await request.post(`${API}/generation/${jobId}/accept`, { headers, data: {} })).status()).toBe(409);
    expect((await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }))).content).toBe(chapter.content);
    await page.screenshot({ path: info.outputPath('judge-model-advisory-opinion.png'), fullPage: true });
    await quiesce.drain(); await page.reload(); await tools(page);
    await panel.getByLabel('查看审阅记录', { exact: true }).selectOption(ruleRun.id);
    await expect(panel).toContainText(jobId);
    expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(1);
    await body(await request.put(`${API}/chapters/${chapter.id}`, { headers, data: { version: chapter.version, content: '新的合成版本，旧证据必须隐藏。' } }));
    await panel.getByRole('button', { name: '刷新审阅与来源（保留输入）', exact: true }).click();
    await expect(panel.getByText('历史结果已隐藏', { exact: false })).toBeVisible();
    await expect(panel.getByRole('region', { name: '准确模型审稿预览', exact: true })).toHaveCount(0);
    await expect(panel.getByRole('article', { name: `检查线索 ${opinion.id}`, exact: true })).toHaveCount(0);
    await page.screenshot({ path: info.outputPath('judge-model-stale-redaction.png'), fullPage: true });
  } finally {
    if (!page.isClosed() && info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('judge-model-failure.png'), fullPage: true }).catch(() => {});
    if (jobId) await request.post(`${API}/generation/${jobId}/cancel`, { headers }).catch(() => {});
    await quiesce();
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status());
  }
});
