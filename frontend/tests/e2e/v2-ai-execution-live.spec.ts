import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { StudioGraphModelCapabilities, StudioGraphRecord, StudioGraphRun } from '../../src/creative/studioGraphTypes';

const TOKEN = 'synthetic-m4-browser-existing-host', headers = { 'X-Session-Token': TOKEN };
const fixturePath = '/api/__tests__/v2-ai-execution-fixture';
const owned = new WeakMap<APIRequestContext, Set<string>>();
type Receipt = { fixture: string; synthetic: true; mock_calls: number; metadata_probe_attempts: number; blocked_attempts: string[]; quality_verification: 'NOT_RUN'; real_inference: 'NOT_RUN'; model_weights_loaded: false; cloud_calls: 0 };
async function receipt(request: APIRequestContext): Promise<Receipt> {
  const response = await request.get(fixturePath, { headers }); expect(response.ok(), await response.text()).toBe(true); return response.json();
}
async function responseFor(page: Page, path: string, action: () => Promise<unknown>, method = 'POST') {
  const pending = page.waitForResponse(value => new URL(value.url()).pathname === path && value.request().method() === method);
  await action(); const response = await pending; expect(response.ok(), `${response.status()}: ${await response.text()}`).toBe(true); return response.json();
}
async function bindHost(page: Page) {
  const modules = page.getByRole('tablist', { name: '创作模块', exact: true });
  await modules.getByRole('tab', { name: '小说', exact: true }).click();
  await page.getByRole('button', { name: '打开功能导航', exact: true }).click();
  const navigation = page.getByRole('navigation', { name: '功能面板导航', exact: true });
  const group = navigation.locator('.feature-group__header').filter({ hasText: '协作' });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await navigation.getByRole('button', { name: 'Agent 团队', exact: true }).click(); await page.keyboard.press('Escape');
  await expect(page.getByLabel('本机访问凭证', { exact: true })).toHaveValue('');
  await page.getByLabel('本机访问凭证', { exact: true }).fill(TOKEN);
  const result = await responseFor(page, '/api/local-session', () => page.getByRole('button', { name: '验证并绑定本机会话', exact: true }).click(), 'GET');
  expect(result).toEqual({ session_mode: 'LOCAL_HOST', actor_id: 'synthetic-m4-browser-author' });
  await modules.getByRole('tab', { name: '图片', exact: true }).click();
}
async function addNode(page: Page, kind: string, label: string) {
  await page.getByLabel('节点类型', { exact: true }).selectOption(kind);
  await page.getByRole('button', { name: '添加节点', exact: true }).click();
  const name = await page.getByRole('button', { name: `选择节点 ${label} · `, exact: false }).getAttribute('aria-label');
  expect(name).toBeTruthy(); return name!.split(' · ')[1];
}
test.beforeEach(async ({ request }) => { expect(await (await request.get('/api/novels')).json()).toEqual([]); owned.set(request, new Set()); });
test.afterEach(async ({ page, request }, info) => {
  if (!page.isClosed()) {
    if (info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('m4-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
    await page.close();
  }
  for (const id of owned.get(request) || []) expect((await request.delete(`/api/novels/${encodeURIComponent(id)}`)).status()).toBe(204);
  expect(await (await request.get('/api/novels')).json()).toEqual([]);
});

test('M4 original File HTTP UI explicitly dispatches one built-in mock graph task, reviews, reopens, cancels and revokes without replay', async ({ page, request }, info) => {
  info.annotations.push({ type: 'verification', description: 'Original File/API/UI/WorkflowRun/JobManager; exact built-in MockProvider only. No route mocks, real models, model weights, paid/cloud API, installation or runtime launch. Real inference quality remains NOT_RUN.' });
  const modelRequests: string[] = [], errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', value => { const path = new URL(value.url()).pathname; if (/\/graph-runs\/[^/]+\/model\//.test(path)) modelRequests.push(`${value.method()} ${path}`); });
  const before = await receipt(request); expect(before.mock_calls).toBe(0); expect(before.blocked_attempts).toEqual([]);
  await page.goto('/'); await page.getByLabel('空白项目名称', { exact: true }).fill('M4 合成文字执行验收');
  const project = await responseFor(page, '/api/experimental/projects', () => page.getByRole('button', { name: '创建空白项目', exact: true }).click());
  owned.get(request)!.add(project.id); await bindHost(page);
  const base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  await page.getByRole('button', { name: '创作图', exact: true }).click(); await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  const input = await addNode(page, 'text_input', '文本输入'); await page.getByLabel('作者输入文本', { exact: true }).fill('M4 合成作者输入，仅用于测试适配器和人工审核。');
  const model = await addNode(page, 'text_generate', '本地文字模型（需明确调用）');
  await page.getByLabel('本地模型写作指令', { exact: true }).fill('提出一段待审核的文字草稿。'); await page.getByLabel('最大输出 token', { exact: true }).fill('128');
  const review = await addNode(page, 'human_review', '人工审核');
  for (const [source, output, target, inputPort] of [[input, 'text', model, 'text'], [model, 'draft', review, 'draft']]) {
    await page.getByLabel('起始输出端口', { exact: true }).selectOption(JSON.stringify([source, output]));
    await page.getByLabel('目标输入端口', { exact: true }).selectOption(JSON.stringify([target, inputPort]));
    await page.getByRole('button', { name: '连接所选端口', exact: true }).click();
  }
  const graph = await responseFor(page, base + '/graphs', () => page.getByRole('button', { name: '保存创作图', exact: true }).click()) as StudioGraphRecord;
  expect(graph.definition.schema_version).toBe(2); expect((await receipt(request)).mock_calls).toBe(0); expect(modelRequests).toEqual([]);
  const graphPath = `${base}/graphs/${graph.id}`;
  const preflight = await responseFor(page, graphPath + '/preflight', () => page.getByRole('button', { name: '核对运行范围', exact: true }).click());
  expect(preflight.executable).toBe(true); await page.getByLabel('已核对当前图版本、节点范围与本地处理边界', { exact: true }).check();
  let run = await responseFor(page, graphPath + '/runs', () => page.getByRole('button', { name: '创建本地运行', exact: true }).click()) as StudioGraphRun;
  expect(run.model_runtime?.status).toBe('PENDING'); expect((await receipt(request)).mock_calls).toBe(0);
  const path = `${base}/graph-runs/${run.id}`;
  run = await responseFor(page, path + '/execute', () => page.getByRole('button', { name: '执行前置本地节点', exact: true }).click());
  expect(run.model_runtime?.status).toBe('AWAITING_PREVIEW'); expect(modelRequests).toEqual([]);
  const capabilities = await responseFor(page, base + '/graphs/model-capabilities', () => page.getByRole('button', { name: '读取本地模型能力', exact: true }).click(), 'GET') as StudioGraphModelCapabilities;
  const route = capabilities.routes.find(row => row.provider_id === 'mock' && row.model_id === 'mock-writer')!;
  expect(route.available).toBe(true); expect(route.synthetic).toBe(true);
  await expect(page.getByLabel('本地文字模型路由', { exact: true })).toHaveValue('');
  await page.getByLabel('本地文字模型路由', { exact: true }).selectOption(route.route_id);
  await expect(page.getByRole('button', { name: '预览图节点模型输入', exact: true })).toBeDisabled();
  await page.getByLabel('明确使用测试适配器；不代表真实本地模型推理', { exact: true }).check();
  run = await responseFor(page, path + '/model/preview', () => page.getByRole('button', { name: '预览图节点模型输入', exact: true }).click());
  expect(run.model_runtime?.preview?.execution_available).toBe(true); expect((await receipt(request)).mock_calls).toBe(0);
  await page.getByText('核对完整模型输入', { exact: true }).click();
  await expect(page.getByRole('region', { name: '图节点模型输入预览', exact: true })).toContainText('M4 合成作者输入');
  await expect(page.getByRole('button', { name: '确认调用图节点本地模型', exact: true })).toBeDisabled();
  await page.getByLabel('已核对当前节点、完整输入和本地路由，允许调用一次', { exact: true }).check();
  run = await responseFor(page, path + '/model/dispatch', () => page.getByRole('button', { name: '确认调用图节点本地模型', exact: true }).evaluate(element => {
    (element as HTMLButtonElement).click(); (element as HTMLButtonElement).click();
  }));
  expect(run.model_runtime?.execution?.synthetic).toBe(true);
  expect(modelRequests.filter(value => value.endsWith('/dispatch'))).toHaveLength(1);
  await expect(page.getByRole('button', { name: '暂停运行', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: '确认调用图节点本地模型', exact: true })).toHaveCount(0);
  const until = Date.now() + 15000;
  while (!run.review && Date.now() < until) {
    run = await responseFor(page, path + '/model/refresh', () => page.getByRole('button', { name: '核对图节点模型结果', exact: true }).click());
    if (!run.review) await page.waitForTimeout(25);
  }
  expect(run.review?.draft.origin).toBe('MODEL_PROPOSAL'); expect(run.model_called).toBe(true); expect(run.applied).toBe(false);
  await expect(page.getByRole('region', { name: '节点输出审核', exact: true })).toContainText('模型提案（需人工审核）');
  await expect(page.getByRole('button', { name: '批准节点输出', exact: true })).toBeDisabled();
  await page.getByLabel('已阅读本次输出并核对当前审核摘要', { exact: true }).check();
  const completed = await responseFor(page, path + '/approve', () => page.getByRole('button', { name: '批准节点输出', exact: true }).click()) as StudioGraphRun;
  expect(completed).toMatchObject({ status: 'SUCCEEDED', model_called: true, external_calls: 0, reviewed: true, applied: false });
  expect(completed.model_runtime?.quality_verification).toBe('NOT_RUN'); expect((await receipt(request)).mock_calls).toBe(1);
  const geometries = [];
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport); await page.evaluate(() => document.fonts.ready);
    await page.getByRole('region', { name: '可选本地文字模型执行', exact: true }).scrollIntoViewIfNeeded();
    const geometry = await page.evaluate(() => { const rect = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return { y: r.y, width: r.width, height: r.height }; }; return { header: rect('.global-header'), context: rect('.context-bar'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'), status: rect('.status-bar'), width: document.documentElement.scrollWidth, viewport: innerWidth }; });
    expect(geometry.header).toMatchObject({ y: 0, width: viewport.width, height: 56 }); expect(geometry.context).toMatchObject({ y: 56, height: 44 });
    expect(geometry.sidebar.width).toBe(248); expect(geometry.inspector.width).toBe(340); expect(geometry.status).toMatchObject({ y: viewport.height - 32, height: 32 }); expect(geometry.width).toBeLessThanOrEqual(geometry.viewport);
    geometries.push({ viewport, geometry }); const image = info.outputPath(`m4-text-execution-${viewport.width}.png`);
    await page.screenshot({ path: image, fullPage: true }); await info.attach(`m4-text-execution-${viewport.width}`, { path: image, contentType: 'image/png' });
  }
  const requestsBeforeReload = modelRequests.length;
  await page.reload(); await bindHost(page); await page.getByRole('button', { name: '创作图', exact: true }).click();
  await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  await page.getByRole('button', { name: '读取运行记录', exact: true }).click(); await page.getByLabel('已保存运行', { exact: true }).selectOption(completed.id);
  await expect(page.getByRole('region', { name: '当前创作图运行', exact: true })).toContainText('已完成');
  expect(modelRequests).toHaveLength(requestsBeforeReload); expect((await receipt(request)).mock_calls).toBe(1);
  await page.getByRole('button', { name: '核对运行范围', exact: true }).click(); await page.getByLabel('已核对当前图版本、节点范围与本地处理边界', { exact: true }).check();
  const pending = await responseFor(page, graphPath + '/runs', () => page.getByRole('button', { name: '创建本地运行', exact: true }).click()) as StudioGraphRun;
  const cancelled = await responseFor(page, `${base}/graph-runs/${pending.id}/cancel`, () => page.getByRole('button', { name: '取消运行', exact: true }).click());
  expect(cancelled.status).toBe('CANCELLED'); expect((await receipt(request)).mock_calls).toBe(1);
  await page.getByLabel('已保存运行', { exact: true }).selectOption(completed.id);
  await expect(page.getByRole('region', { name: '当前创作图运行', exact: true })).toContainText(completed.id);
  await expect(page.getByRole('region', { name: '当前创作图运行', exact: true })).toContainText('已完成');
  const final = await receipt(request); expect(final).toMatchObject({ synthetic: true, mock_calls: 1, blocked_attempts: [], quality_verification: 'NOT_RUN', real_inference: 'NOT_RUN', model_weights_loaded: false, cloud_calls: 0 });
  expect(await (await request.get(`/api/novels/${encodeURIComponent(project.id)}/chapters`)).json()).toEqual([]);
  await expect(page.getByRole('tablist', { name: '创作模块', exact: true }).getByRole('tab')).toHaveText(['小说', '图片', '视频', '资产', '声音', '主控', '插件', '工作流']);
  expect((await request.post(fixturePath + '/revoke-current-host', { headers, data: { confirmed: true } })).status()).toBe(204);
  const denied = page.waitForResponse(value => new URL(value.url()).pathname === path && value.request().method() === 'GET');
  await page.getByRole('button', { name: '重新读取当前运行', exact: true }).click(); expect((await denied).status()).toBe(401);
  await expect(page.getByRole('region', { name: '当前创作图运行', exact: true })).toHaveCount(0);
  await expect(page.getByRole('region', { name: '节点输出审核', exact: true })).toHaveCount(0); expect(errors).toEqual([]);
  await info.attach('m4-original-owner-receipt', { body: JSON.stringify({ project_id: project.id, graph, completed, cancelled, fixture: final, modelRequests, geometries, no_chapters: true, real_inference: 'NOT_RUN' }, null, 2), contentType: 'application/json' });
});
