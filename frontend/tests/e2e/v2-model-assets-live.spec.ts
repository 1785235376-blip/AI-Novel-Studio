import { expect, test, type APIRequestContext, type Page, type TestInfo } from '@playwright/test';
import type { StudioGraphModelCapabilities, StudioGraphRecord, StudioGraphRun } from '../../src/creative/studioGraphTypes';
import type { StudioProviderCatalog, StudioTaskMatchResult, StudioTaskType } from '../../src/creative/studioProviderTypes';

const TOKEN = 'synthetic-m4-browser-existing-host', headers = { 'X-Session-Token': TOKEN };
const fixturePath = '/api/__tests__/v2-model-assets-fixture';
const owned = new WeakMap<APIRequestContext, Set<string>>();
type Receipt = { fixture: string; synthetic: true; mock_calls: number; metadata_probe_attempts: number; blocked_attempts: string[]; quality_verification: 'NOT_RUN'; real_inference: 'NOT_RUN'; model_weights_loaded: false; cloud_calls: 0; create_calls: number; created_asset_ids: string[]; review_metadata_faults: number; fault_armed: boolean; fault_asset_id: string | null; fault_observed_asset_version: number | null; fault_observed_asset_state: string | null };
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
async function screenshotShell(page: Page, info: TestInfo, label: string, region: string) {
  const geometries = [];
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport); await page.evaluate(() => document.fonts.ready);
    await page.getByRole('region', { name: region, exact: true }).scrollIntoViewIfNeeded();
    const geometry = await page.evaluate(() => { const rect = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return { y: r.y, width: r.width, height: r.height }; }; return { header: rect('.global-header'), context: rect('.context-bar'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'), status: rect('.status-bar'), width: document.documentElement.scrollWidth, viewport: innerWidth }; });
    expect(geometry.header).toMatchObject({ y: 0, width: viewport.width, height: 56 }); expect(geometry.context).toMatchObject({ y: 56, height: 44 });
    expect(geometry.sidebar.width).toBe(248); expect(geometry.inspector.width).toBe(340); expect(geometry.status).toMatchObject({ y: viewport.height - 32, height: 32 }); expect(geometry.width).toBeLessThanOrEqual(geometry.viewport);
    geometries.push({ viewport, geometry }); const screenshot = info.outputPath(`${label}-${viewport.width}.png`);
    await page.screenshot({ path: screenshot, fullPage: true }); await info.attach(`${label}-${viewport.width}`, { path: screenshot, contentType: 'image/png' });
  }
  return geometries;
}
test.beforeEach(async ({ request }) => { expect(await (await request.get('/api/novels')).json()).toEqual([]); owned.set(request, new Set()); });
test.afterEach(async ({ page, request }, info) => {
  if (!page.isClosed()) {
    if (info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('m4b-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
    await page.close();
  }
  for (const id of owned.get(request) || []) expect((await request.delete(`/api/novels/${encodeURIComponent(id)}`)).status()).toBe(204);
  expect(await (await request.get('/api/novels')).json()).toEqual([]);
});

test('M4-B original File HTTP UI explains task matching and archives one reviewed model result, recovering a bounded metadata failure without replay', async ({ page, request }, info) => {
  info.annotations.push({ type: 'verification', description: 'Original File/API/UI/WorkflowRun/JobManager/AssetLibraryService. Built-in MockProvider only; one review-metadata fault. No route mocks, real inference, provider probing, weights, paid/cloud APIs, installs or runtime launch. Real-model quality NOT_RUN.' });
  const modelRequests: string[] = [], advisoryRequests: string[] = [], dispatchBodies: unknown[] = [], errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', value => {
    const path = new URL(value.url()).pathname;
    if (/\/graph-runs\/[^/]+\/model\//.test(path)) modelRequests.push(`${value.method()} ${path}`);
    if (/\/graphs\/(provider-contracts|model-match)$/.test(path)) advisoryRequests.push(`${value.method()} ${path}`);
    if (path.endsWith('/model/dispatch')) dispatchBodies.push(value.postDataJSON());
  });
  expect(await receipt(request)).toMatchObject({ mock_calls: 0, create_calls: 0, created_asset_ids: [], review_metadata_faults: 0, blocked_attempts: [] });
  await page.goto('/'); await page.getByLabel('空白项目名称', { exact: true }).fill('M4-B 模型匹配与私有文字资产验收');
  const project = await responseFor(page, '/api/experimental/projects', () => page.getByRole('button', { name: '创建空白项目', exact: true }).click());
  owned.get(request)!.add(project.id); await bindHost(page);
  const base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  await page.getByRole('button', { name: '创作图', exact: true }).click(); await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  const input = await addNode(page, 'text_input', '文本输入');
  await page.getByLabel('作者输入文本', { exact: true }).fill('M4-B 合成作者输入，仅验收既有模型任务、归档与人工审核边界。');
  const model = await addNode(page, 'text_generate', '本地文字模型（需明确调用）');
  await page.getByLabel('本地模型写作指令', { exact: true }).fill('提出一段保留为私有待审核资产的文字草稿。');
  await page.getByLabel('最大输出 token', { exact: true }).fill('128');
  const reviewNode = await addNode(page, 'human_review', '人工审核');
  for (const [source, output, target, inputPort] of [[input, 'text', model, 'text'], [model, 'draft', reviewNode, 'draft']]) {
    await page.getByLabel('起始输出端口', { exact: true }).selectOption(JSON.stringify([source, output]));
    await page.getByLabel('目标输入端口', { exact: true }).selectOption(JSON.stringify([target, inputPort]));
    await page.getByRole('button', { name: '连接所选端口', exact: true }).click();
  }
  const graph = await responseFor(page, base + '/graphs', () => page.getByRole('button', { name: '保存创作图', exact: true }).click()) as StudioGraphRecord;
  expect(graph.definition.schema_version).toBe(2); expect(modelRequests).toEqual([]); expect(advisoryRequests).toEqual([]);
  const graphPath = `${base}/graphs/${graph.id}`;
  const preflight = await responseFor(page, graphPath + '/preflight', () => page.getByRole('button', { name: '核对运行范围', exact: true }).click());
  expect(preflight.executable).toBe(true);
  await page.getByLabel('已核对当前图版本、节点范围与本地处理边界', { exact: true }).check();
  let run = await responseFor(page, graphPath + '/runs', () => page.getByRole('button', { name: '创建本地运行', exact: true }).click()) as StudioGraphRun;
  const path = `${base}/graph-runs/${run.id}`;
  run = await responseFor(page, path + '/execute', () => page.getByRole('button', { name: '执行前置本地节点', exact: true }).click());
  expect(run.model_runtime?.status).toBe('AWAITING_PREVIEW'); expect(modelRequests).toEqual([]);
  const capabilities = await responseFor(page, base + '/graphs/model-capabilities', () => page.getByRole('button', { name: '读取本地模型能力', exact: true }).click(), 'GET') as StudioGraphModelCapabilities;
  expect(capabilities.result_storage).toEqual({ contract: 'creative-graph-text-asset/1', available: true, owner: 'AssetLibraryService', actor_private: true, automatic_model_retry: false });
  const route = capabilities.routes.find(row => row.provider_id === 'mock' && row.model_id === 'mock-writer')!;
  expect(route.available).toBe(true); expect(route.synthetic).toBe(true);
  const providerPanel = page.getByRole('region', { name: '提供方与任务匹配说明', exact: true });
  await expect(providerPanel).toContainText('不会选择执行路由、调用模型或自动回退');
  const catalog = await responseFor(page, base + '/graphs/provider-contracts', () => providerPanel.getByRole('button', { name: '读取提供方契约', exact: true }).click(), 'GET') as StudioProviderCatalog;
  expect(catalog).toMatchObject({ advisory_only: true, dispatch_authorized: false, automatic_fallback: false, quality_verification: 'NOT_RUN' });
  expect(catalog.providers.map(row => row.family)).toEqual(['LOCAL_OLLAMA', 'LM_STUDIO', 'COMFYUI', 'LLAMA_CPP', 'API']);
  for (const item of catalog.providers) expect(item).toMatchObject({ availability: { execution_available: false }, real_model_verification: 'NOT_RUN' });
  await providerPanel.getByText('LM Studio · 预留', { exact: true }).click();
  await expect(providerPanel).toContainText('LM Studio 仍缺少可信本地性证据，不能调用');
  await providerPanel.getByText('云端 API · 预留', { exact: true }).click();
  await expect(providerPanel).toContainText('API 仅预留，不可执行，也不会成为自动回退目标');
  await page.getByLabel('匹配指定路由', { exact: true }).selectOption(route.route_id);
  const matches: StudioTaskMatchResult[] = [];
  for (const task of ['TEXT_GENERATION', 'IMAGE_GENERATION', 'VIDEO_GENERATION'] as StudioTaskType[]) {
    await page.getByLabel('匹配任务类型', { exact: true }).selectOption(task);
    await page.getByLabel('明确将测试适配器纳入匹配；这不是模型调用授权', { exact: true }).check();
    const result = await responseFor(page, base + '/graphs/model-match', () => providerPanel.getByRole('button', { name: '查看任务匹配说明', exact: true }).click()) as StudioTaskMatchResult;
    matches.push(result);
    expect(result).toMatchObject({ advisory_only: true, dispatch_authorized: false, automatic_fallback: false, api_provider: { status: 'RESERVED', execution_available: false } });
    const selected = result.matches.find(row => row.route_id === route.route_id)!;
    expect(selected).toMatchObject({ eligible: task === 'TEXT_GENERATION', execution_authority: false, gpu_fit_verified: false, preferred: true });
    if (task !== 'TEXT_GENERATION') expect(selected.reasons).toContain(`GRAPH_${task.split('_')[0]}_EXECUTION_NOT_ENABLED`);
    await expect(page.getByRole('region', { name: '任务匹配结果', exact: true })).toContainText('仅建议，不授权执行');
    await expect(page.getByLabel('本地文字模型路由', { exact: true })).toHaveValue('');
    expect(modelRequests).toEqual([]); expect((await receipt(request)).mock_calls).toBe(0);
  }
  expect(advisoryRequests.filter(value => value.endsWith('/provider-contracts'))).toHaveLength(1);
  expect(advisoryRequests.filter(value => value.endsWith('/model-match'))).toHaveLength(3);
  const matchGeometries = await screenshotShell(page, info, 'm4b-provider-task-match', '任务匹配结果');
  await page.getByLabel('本地文字模型路由', { exact: true }).selectOption(route.route_id);
  await expect(page.getByRole('button', { name: '预览图节点模型输入', exact: true })).toBeDisabled();
  await page.getByLabel('明确使用测试适配器；不代表真实本地模型推理', { exact: true }).check();
  run = await responseFor(page, path + '/model/preview', () => page.getByRole('button', { name: '预览图节点模型输入', exact: true }).click());
  expect(run.model_runtime?.preview?.execution_available).toBe(true); expect((await receipt(request)).mock_calls).toBe(0);
  await page.getByText('核对完整模型输入', { exact: true }).click();
  await expect(page.getByRole('region', { name: '图节点模型输入预览', exact: true })).toContainText('M4-B 合成作者输入');
  await expect(page.getByRole('region', { name: '图节点模型输入预览', exact: true })).toContainText('成功结果会保存为私有待审核文字资产');
  await expect(page.getByRole('button', { name: '确认调用图节点本地模型', exact: true })).toBeDisabled();
  await page.getByLabel('已核对当前节点、完整输入和本地路由，允许调用一次', { exact: true }).check();
  run = await responseFor(page, path + '/model/dispatch', () => page.getByRole('button', { name: '确认调用图节点本地模型', exact: true }).evaluate(element => {
    (element as HTMLButtonElement).click(); (element as HTMLButtonElement).click();
  }));
  expect(dispatchBodies).toHaveLength(1); expect(dispatchBodies[0]).toMatchObject({ archive_result: true });
  expect(run.asset_output?.state).toBe('PENDING'); expect(run.model_runtime?.execution?.synthetic).toBe(true);
  const until = Date.now() + 15000;
  while (!run.review && Date.now() < until) {
    run = await responseFor(page, path, () => page.getByRole('button', { name: '重新读取当前运行', exact: true }).click(), 'GET');
    if (!run.review) await page.waitForTimeout(25);
  }
  expect(run.review?.draft.origin).toBe('MODEL_PROPOSAL'); expect(run.model_called).toBe(true); expect(run.applied).toBe(false);
  expect(run.asset_output).toMatchObject({ state: 'DRAFT', version: 1, actor_private: true, applied: false, automatic_model_retry: false, quality_verification: 'NOT_RUN' });
  const draft = run;
  const assetId = draft.asset_output!.asset_id!;
  await expect(page.getByRole('region', { name: '私有文字资产回执', exact: true })).toContainText('待审核');
  await expect(page.getByRole('region', { name: '私有文字资产回执', exact: true })).toContainText(assetId);
  await expect(page.getByRole('region', { name: '节点输出审核', exact: true })).toContainText('模型提案（需人工审核）');
  for (let count = 0; count < 3; count++) {
    const same = await responseFor(page, path, () => page.getByRole('button', { name: '重新读取当前运行', exact: true }).click(), 'GET');
    expect(same).toEqual(draft);
  }
  expect(await responseFor(page, path + '/model/refresh', () => page.getByRole('button', { name: '核对图节点模型结果', exact: true }).click())).toEqual(draft);
  expect(await receipt(request)).toMatchObject({ mock_calls: 1, create_calls: 1, created_asset_ids: [assetId], review_metadata_faults: 0 });
  expect((await (await request.get(base + '/assets', { headers })).json()).items).toEqual([]);
  const fault = await request.post(fixturePath + '/fail-next-review-metadata', { headers, data: { confirmed: true, stage: 'review_metadata' } });
  expect(fault.status()).toBe(200); expect(await fault.json()).toMatchObject({ fault_armed: true, fault_asset_id: assetId });
  await page.getByLabel('已阅读本次输出并核对当前审核摘要', { exact: true }).check();
  const failedApproval = page.waitForResponse(value => new URL(value.url()).pathname === path + '/approve' && value.request().method() === 'POST');
  await page.getByRole('button', { name: '批准节点输出', exact: true }).click();
  const failure = await failedApproval; expect(failure.status()).toBe(500); expect(await failure.text()).not.toContain('M4B_TEST_ONLY');
  await expect(page.getByRole('region', { name: '当前创作图运行', exact: true })).toContainText('版本或回执不确定');
  expect(await receipt(request)).toMatchObject({ mock_calls: 1, create_calls: 1, review_metadata_faults: 1, fault_armed: false, fault_observed_asset_version: 1, fault_observed_asset_state: 'DRAFT' });
  // Ordinary reload and original run selection perform the existing GET. No
  // new archive, repair, accept, re-approve or provider action is introduced.
  const modelBeforeReload = [...modelRequests];
  await page.reload(); await bindHost(page); await page.getByRole('button', { name: '创作图', exact: true }).click();
  await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  await page.getByRole('button', { name: '读取运行记录', exact: true }).click();
  const completed = await responseFor(page, path, () => page.getByLabel('已保存运行', { exact: true }).selectOption(draft.id), 'GET') as StudioGraphRun;
  expect(completed).toMatchObject({ status: 'SUCCEEDED', reviewed: true, model_called: true, applied: false, external_calls: 0 });
  expect(completed.asset_output).toMatchObject({ asset_id: assetId, state: 'APPROVED', version: 2, actor_private: true, applied: false, quality_verification: 'NOT_RUN' });
  await expect(page.getByRole('region', { name: '私有文字资产回执', exact: true })).toContainText('已批准');
  await expect(page.getByRole('region', { name: '私有文字资产回执', exact: true })).toContainText('v2');
  expect(modelRequests).toEqual(modelBeforeReload);
  for (let count = 0; count < 3; count++) {
    expect(await responseFor(page, path, () => page.getByRole('button', { name: '重新读取当前运行', exact: true }).click(), 'GET')).toEqual(completed);
  }
  const geometries = await screenshotShell(page, info, 'm4b-model-assets', '私有文字资产回执');
  const final = await receipt(request);
  expect(final).toMatchObject({ synthetic: true, mock_calls: 1, create_calls: 1, created_asset_ids: [assetId], review_metadata_faults: 1, fault_armed: false, blocked_attempts: [], quality_verification: 'NOT_RUN', real_inference: 'NOT_RUN', model_weights_loaded: false, cloud_calls: 0 });
  expect(await (await request.get(`/api/novels/${encodeURIComponent(project.id)}/chapters`)).json()).toEqual([]);
  expect(modelRequests.filter(value => value.endsWith('/preview'))).toHaveLength(1);
  expect(modelRequests.filter(value => value.endsWith('/dispatch'))).toHaveLength(1);
  expect(modelRequests.filter(value => value.endsWith('/refresh'))).toHaveLength(1);
  await expect(page.getByRole('tablist', { name: '创作模块', exact: true }).getByRole('tab')).toHaveText(['小说', '图片', '视频', '资产', '声音', '主控', '插件', '工作流']);
  expect(errors).toEqual([]);
  await info.attach('m4b-original-owner-receipt', { body: JSON.stringify({ project_id: project.id, graph, capabilities, catalog, matches, draft, completed, fixture: final, dispatchBodies, modelRequests, advisoryRequests, geometries, matchGeometries, review_metadata_fault_http_status: 500, recovery: 'ORIGINAL_GET_ON_REOPEN', no_chapters: true, real_inference: 'NOT_RUN' }, null, 2), contentType: 'application/json' });
});
