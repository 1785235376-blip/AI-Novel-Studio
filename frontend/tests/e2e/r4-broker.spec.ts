import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';

// Dedicated isolated development profile, not a bypass of production auth.
const API = 'http://127.0.0.1:8022/api';
const UI = 'http://127.0.0.1:5182';
const TOKEN = 'r4-broker-test-session';
const headers = { 'X-Session-Token': TOKEN };
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function tools(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '模型路由与评测', exact: true }).click();
}
async function createProject(page: Page) {
  // Emulate the trusted local host header, not an unselected collaboration session.
  await page.setExtraHTTPHeaders(headers);
  await page.goto(UI);
  await page.getByPlaceholder('小说名称').fill('R4 synthetic broker browser');
  const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await body(await created);
  await page.getByRole('button', { name: '新建章节', exact: true }).click();
  await page.getByLabel('章节标题', { exact: true }).fill('合成港口');
  const added = page.waitForResponse(r => r.url().endsWith(`/novels/${novel.id}/chapters`) && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建章节', exact: true }).click();
  const chapter = await body(await added);
  await page.getByRole('textbox', { name: '章节正文', exact: true }).fill('这是用于软件协议验证的合成章节。门后传来钟声。');
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('.editorbar')).toContainText('已保存');
  return { novel, chapter: await body(await page.request.get(`${API}/chapters/${chapter.id}`, { headers })) };
}
async function preview(page: Page, routeId: string) {
  await page.getByLabel('调度策略', { exact: true }).selectOption('CUSTOM');
  await page.getByLabel('偏好模型路线', { exact: true }).selectOption(routeId);
  await page.getByLabel('明确允许内置合成协议测试（不代表真实模型质量）', { exact: true }).check();
  await page.getByRole('button', { name: '预览合法模型路线', exact: true }).click();
  await expect(page.getByRole('region', { name: '模型路线预览' })).toContainText('KNOWN_SYNTHETIC_ZERO');
}
async function approveAuthor(page: Page) {
  await page.getByLabel('本次创作要求', { exact: true }).fill('只使用合成资料，返回中文短稿。');
  await page.getByRole('button', { name: '检查真实生成请求', exact: true }).click();
  await expect(page.getByText('请求已预检', { exact: true })).toBeVisible();
  await page.getByLabel('已核对准确请求、来源与模型，并授权生成这一次草稿', { exact: true }).check();
}

test('R4 broker real API, author executor, cancellation, bounded evidence and draft review navigation', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '', lastReservation = '', lastJob = '';
  info.annotations.push({ type: 'verification', description: 'Real File API + React + shipped deterministic MockProvider only, explicit synthetic opt-in and trusted development session. No real model, paid API or real credential. No mocked route responses.' });
  try {
    const created = await createProject(page); nid = created.novel.id;
    const chapter = created.chapter, base = `${API}/novels/${nid}/experimental`;
    // The same real endpoint refuses missing trusted host authority.
    expect((await request.get(`${base}/model-broker/status`)).status()).toBe(401);
    const status = await body(await request.get(`${base}/model-broker/status`, { headers }));
    expect(status.author_execution_available).toBe(true);
    const route = status.candidates.find((row: any) => row.provider_id === 'mock');
    expect(route.available).toBe(true); expect(route.synthetic).toBe(true);
    await tools(page);
    await page.getByLabel('累计预占上限（µUSD；留空不设金额上限）', { exact: true }).fill('0');
    await page.getByRole('button', { name: '保存版本化项目预算', exact: true }).click();
    await expect(page.getByText('项目预算已保存，旧路线预览失效。', { exact: true })).toBeVisible();
    await page.getByLabel('调度策略', { exact: true }).selectOption('CUSTOM');
    await page.getByLabel('偏好模型路线', { exact: true }).selectOption(route.route_id);
    await page.getByRole('button', { name: '预览合法模型路线', exact: true }).click();
    await expect(page.getByRole('region', { name: '模型路线预览' })).toContainText('没有合法候选');
    expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(0);
    await preview(page, route.route_id); await approveAuthor(page);
    const generated = page.waitForResponse(r => r.url().endsWith('/model-broker/generate') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '按预览路线预占并生成', exact: true }).click();
    const job = await body(await generated); lastReservation = job.reservation_id; lastJob = job.job_id;
    await expect.poll(async () => (await body(await request.get(`${base}/model-broker/jobs/${job.reservation_id}`, { headers }))).ledger.status).toBe('SETTLED');
    await expect(page.getByLabel('生成草稿（只读）', { exact: true })).not.toHaveValue('');
    const current = await body(await request.get(`${base}/model-broker/jobs/${job.reservation_id}`, { headers }));
    expect(current.job.status).toBe('COMPLETED'); expect(current.ledger.actual_microusd).toBe(0);
    expect(current.job.dispatch_hooks_required).toBe(true);
    expect((await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }))).content).toBe(chapter.content);
    await page.screenshot({ path: info.outputPath('broker-existing-job-ledger.png') });
    await page.getByRole('button', { name: '在原有草稿审核中打开', exact: true }).click();
    await expect(page.getByRole('button', { name: '采用草稿', exact: true })).toBeVisible();
    // Opening the review is not adopting the output.
    expect((await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }))).content).toBe(chapter.content);

    await tools(page); await preview(page, route.route_id); await approveAuthor(page);
    const second = page.waitForResponse(r => r.url().endsWith('/model-broker/generate') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '按预览路线预占并生成', exact: true }).click();
    const cancelled = await body(await second); lastReservation = cancelled.reservation_id; lastJob = cancelled.job_id;
    await page.getByRole('button', { name: '取消本次生成', exact: true }).click();
    await expect.poll(async () => (await body(await request.get(`${base}/model-broker/jobs/${cancelled.reservation_id}`, { headers }))).job.status).toBe('CANCELLED');
    await expect.poll(async () => (await body(await request.get(`${base}/model-broker/jobs/${cancelled.reservation_id}`, { headers }))).ledger.status).toMatch(/SETTLED|RELEASED/);
    expect((await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }))).content).toBe(chapter.content);

    await page.getByLabel('评测任务集标题', { exact: true }).fill('中文协议浏览器任务集');
    await page.getByLabel('样本 1 合成测试输入', { exact: true }).fill('为软件协议测试写一句中文，不调用工具。');
    const savedSet = page.waitForResponse(r => r.url().endsWith('/model-benchmarks/sets') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '保存评测任务集', exact: true }).click();
    const testSet = await body(await savedSet);
    await page.getByLabel('待运行任务集', { exact: true }).selectOption(testSet.id);
    await page.getByLabel('本次评测的本地模型路线', { exact: true }).selectOption(route.route_id);
    const prepared = page.waitForResponse(r => r.url().endsWith('/model-benchmarks/runs') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '建立有界评测运行', exact: true }).click();
    const run = await body(await prepared); expect(run.status).toBe('READY');
    expect((await body(await request.get(`${base}/model-benchmarks/status`, { headers }))).evidence).toHaveLength(0);
    await page.getByRole('button', { name: '执行下一评测样本', exact: true }).click();
    await expect(page.getByText('1 / 1 已完成；每次按钮只执行一个保存的样本。', { exact: true })).toBeVisible();
    const measured = await body(await request.get(`${base}/model-benchmarks/status`, { headers }));
    expect(measured.evidence).toHaveLength(1);
    const evidence = measured.evidence[0];
    expect(evidence.origin).toBe('EXECUTED'); expect(evidence.verification).toBe('SYNTHETIC_PROTOCOL_ONLY');
    expect(evidence.metrics.latency_ms).toBeGreaterThanOrEqual(0); expect(evidence.tokens_per_second).toBeNull(); expect(evidence.quality_score).toBeNull();
    const imported = { set_id: testSet.id, expected_set_version: testSet.version, route_id: route.route_id, route_fingerprint: route.fingerprint,
      input_hash: evidence.input_hash, workflow_hash: route.identity.workflow_hash, model_id: route.model_id,
      runtime_version: route.identity.runtime_version, adapter_hash: route.identity.adapter_hash,
      latency_ms: 25, sample_count: 1, error_count: 0, provenance: 'Synthetic imported declared evidence, not measured in this browser' };
    await page.getByLabel('待导入结果 JSON（核对后提交）', { exact: true }).fill(JSON.stringify(imported));
    await page.getByRole('button', { name: '核对并导入评测证据', exact: true }).click();
    await expect(page.getByText('导入证据已保存，仍标记为未验证。', { exact: true })).toBeVisible();
    const executedCard = page.locator('article.experimental-record').filter({ hasText: '本机执行 ·' });
    await executedCard.getByRole('button', { name: '使此证据失效', exact: true }).click();
    await expect(executedCard).toContainText('历史 / 待复验');
    await page.screenshot({ path: info.outputPath('broker-bounded-evidence-invalidation.png') });
    await quiesce.drain(); await page.reload(); await tools(page);
    await expect(page.getByRole('button', { name: '编辑任务集 中文协议浏览器任务集', exact: true })).toBeVisible();
    const persisted = await body(await request.get(`${base}/model-benchmarks/status`, { headers }));
    expect(persisted.runs).toHaveLength(1); expect(persisted.evidence).toHaveLength(2);
    expect(persisted.evidence.find((row: any) => row.id === evidence.id).evidence_state).toBe('HISTORICAL');
    expect(persisted.evidence.find((row: any) => row.origin === 'IMPORTED_UNVERIFIED').routing_eligible).toBe(false);
  } finally {
    if (nid && lastReservation) {
      const row = await request.get(`${API}/novels/${nid}/experimental/model-broker/jobs/${lastReservation}`, { headers });
      if (row.ok()) { const value = await row.json(); if (value.job && !['COMPLETED', 'FAILED', 'CANCELLED', 'ACCEPTED', 'REJECTED'].includes(value.job.status)) await request.post(`${API}/generation/${lastJob}/cancel`, { headers }); }
    }
    await quiesce();
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status());
  }
});
