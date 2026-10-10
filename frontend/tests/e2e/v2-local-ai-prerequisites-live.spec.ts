import {expect, test, request as independentRequest, type APIRequestContext, type APIResponse, type Page} from '@playwright/test';
import type {AIEnvironmentReport, LocalAiScanScope, LocalDiscoveryScan, LocalDiscoverySnapshot} from '../../src/localAiDiscoveryApi';

const TOKEN = 'synthetic-m3-browser-existing-host';
const SECOND_TOKEN = 'synthetic-m3-browser-second-host';
const headers = {'X-Session-Token': TOKEN};
const root = '/api/model-center/local-ai';
const fixtureRoot = '/api/__tests__/v2-discovery-fixture';
const owned = new WeakMap<APIRequestContext, Set<string>>();
type PrerequisiteSeed = {fixture: string; catalogue_model_id: string; catalogue_component_id: string;
  object_info_bytes: number; object_info_sha256: string};
type FixtureReceipt = {synthetic: boolean; probe_calls: {endpoint: string; path: string; method: string; body: null}[];
  hardware_calls: number; scan_id: string | null; scan_status: string | null; registrations: number;
  enabled_registrations: number; launch_attempts: number; blocked_attempts: string[]; model_weights_loaded: false;
  inference_status: 'NOT_RUN'; windows_acceptance: 'NOT_RUN';
  synthetic_metadata_fixtures: {name: string; bytes: number; sha256: string}[];
  synthetic_prerequisite_fixture?: PrerequisiteSeed};

async function body<T>(response: Pick<APIResponse, 'ok' | 'status' | 'text' | 'json'>): Promise<T> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBe(true);
  return response.json() as Promise<T>;
}
const receipt = async (request: APIRequestContext, token = TOKEN) => body<FixtureReceipt>(await request.get(fixtureRoot,
  {headers: {'X-Session-Token': token}}));

async function bindHostAndOpenModels(page: Page) {
  // Feature navigation remains owned by NOVEL even when reload restores CONTROL.
  await page.getByRole('tablist', {name: '创作模块', exact: true}).getByRole('tab', {name: '小说', exact: true}).click();
  await page.getByRole('button', {name: '打开功能导航', exact: true}).click();
  const navigation = page.getByRole('navigation', {name: '功能面板导航', exact: true});
  const group = navigation.locator('.feature-group__header').filter({hasText: '协作'});
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await navigation.getByRole('button', {name: 'Agent 团队', exact: true}).click();
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('本机访问凭证', {exact: true})).toHaveValue('');
  await page.getByLabel('本机访问凭证', {exact: true}).fill(TOKEN);
  const validation = page.waitForResponse(value => new URL(value.url()).pathname === '/api/local-session');
  await page.getByRole('button', {name: '验证并绑定本机会话', exact: true}).click();
  expect(await body(await validation)).toEqual({session_mode: 'LOCAL_HOST', actor_id: 'synthetic-m3-browser-author'});
  const reading = page.waitForResponse(value => new URL(value.url()).pathname === root && value.request().method() === 'GET');
  await page.getByRole('tablist', {name: '创作模块', exact: true}).getByRole('tab', {name: '主控', exact: true}).click();
  await page.getByRole('tablist', {name: '主控设置', exact: true}).getByRole('tab', {name: '模型中心', exact: true}).click();
  const snapshot = await reading;
  expect(snapshot.status()).toBe(200);
  expect(snapshot.request().headers()['x-session-token']).toBe(TOKEN);
}

test.afterEach(async ({page, request}, info) => {
  try {if (!page.isClosed()) await page.close();}
  finally {
    const cleanup = await independentRequest.newContext({baseURL: String(info.project.use.baseURL), timeout: 10000});
    try {
      for (const id of owned.get(request) || []) expect((await cleanup.delete(`/api/novels/${encodeURIComponent(id)}`)).status()).toBe(204);
      expect(await body(await cleanup.get('/api/novels'))).toEqual([]);
    } finally {await cleanup.dispose();}
  }
});

test('M3 prerequisites original File HTTP UI separates advertisements and unknown catalogue requirements', async ({page, request}, info) => {
  info.annotations.push({type: 'verification', description: 'Original File/HTTP/UI, scan and host owners. Explicit bounded synthetic object_info and catalogue declarations; no route mocks, model files loaded, network model probe, real hardware, inference, Windows or paid API.'});
  owned.set(request, new Set());
  expect(await body(await request.get('/api/novels'))).toEqual([]);
  // This third serial journey requires the old consent and files journeys. No
  // previous scan, metadata fixture, receipt, identity or data is reset here.
  const before = await receipt(request);
  expect(before.synthetic).toBe(true);
  expect(before.scan_status).toBe('COMPLETED');
  expect(before.synthetic_metadata_fixtures).toHaveLength(3);
  expect(before.hardware_calls).toBe(2);
  expect(before.probe_calls).toHaveLength(14);
  expect(before.synthetic_prerequisite_fixture).toBeUndefined();
  const previousReport = await body<AIEnvironmentReport>(await request.get(`${root}/environment`, {headers}));
  expect(previousReport.scan_id).toBe(before.scan_id);
  expect(previousReport.model_files).toHaveLength(3);
  expect(previousReport.workflow_prerequisites?.components).toEqual([]);
  const seededResponse = await request.post(`${fixtureRoot}/seed-prerequisites`,
    {headers, data: {fixture: 'workflow-prerequisites-only-v1', confirmed: true}});
  expect(seededResponse.status()).toBe(201);
  expect(seededResponse.headers()['cache-control']).toBe('no-store');
  const seeded = await body<{synthetic: true; prerequisite_fixture: PrerequisiteSeed; model_weights_loaded: false}>(seededResponse);
  expect(seeded.synthetic).toBe(true); expect(seeded.model_weights_loaded).toBe(false);
  expect(seeded.prerequisite_fixture.object_info_bytes).toBeLessThan(512);
  expect(seeded.prerequisite_fixture.object_info_sha256).toMatch(/^[a-f0-9]{64}$/);
  const afterSeed = await receipt(request);
  expect(afterSeed).toEqual({...before, synthetic_prerequisite_fixture: seeded.prerequisite_fixture});
  expect(await body(await request.get(`${root}/environment`, {headers}))).toEqual(previousReport);

  const mutations: string[] = [], pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('request', value => {
    const path = new URL(value.url()).pathname;
    if (path.startsWith(root) && !['GET', 'HEAD', 'OPTIONS'].includes(value.method())) mutations.push(`${value.method()} ${path}`);
  });
  await page.goto('/');
  await page.getByLabel('小说名称', {exact: true}).fill('M3 合成工作流前置条件观察');
  const creating = page.waitForResponse(value => new URL(value.url()).pathname === '/api/novels' && value.request().method() === 'POST');
  await page.getByRole('button', {name: '创建小说', exact: true}).click();
  const created = await creating;
  if (created.status() === 201) {const row = await created.json(); if (typeof row.id === 'string' && row.id) owned.get(request)!.add(row.id);}
  expect(created.status()).toBe(201); expect(owned.get(request)!.size).toBe(1);
  await bindHostAndOpenModels(page);
  const discovery = page.locator('.local-ai');
  const observation = page.getByRole('region', {name: '本次扫描的工作流前置条件观察', exact: true});
  await expect(discovery.getByText('COMPLETED', {exact: true})).toBeVisible();
  await expect(observation).toContainText('本次没有可显示的组件声明');
  expect(await receipt(request)).toEqual(afterSeed);
  expect(mutations).toEqual([]);

  const previewing = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/onboarding/scan-scope`);
  await discovery.getByRole('button', {name: '重新预览检测范围', exact: true}).click();
  const scope = await body<LocalAiScanScope>(await previewing);
  expect(scope.execution_scope).toBe('BACKEND_HOST');
  expect(scope.include_common_model_dirs).toBe(false);
  expect(scope.roots).toEqual([]);
  const consent = page.getByRole('region', {name: '确认后端主机检测范围', exact: true});
  await expect(consent.getByRole('checkbox')).not.toBeChecked();
  expect(await receipt(request)).toEqual(afterSeed);
  const confirming = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/onboarding/scan` && value.request().method() === 'POST');
  await consent.getByRole('button', {name: '确认此范围并检测', exact: true}).click();
  const confirmed = await confirming;
  expect(confirmed.status()).toBe(202);
  expect(confirmed.request().headers()['x-session-token']).toBe(TOKEN);
  expect(confirmed.request().postDataJSON()).toEqual({scope_digest: scope.scope_digest, confirmed: true});
  const job = await body<LocalDiscoveryScan>(confirmed);
  expect(job.id).not.toBe(before.scan_id);
  expect(job.status).toBe('RUNNING');
  expect(job.workflow_prerequisites).toMatchObject({schema_version: 1, scan_id: job.id, scan_status: 'RUNNING'});
  expect(job.workflow_prerequisites!.workflows).toHaveLength(1);
  expect(job.workflow_prerequisites!.workflows[0].evidence_status).toBe('NOT_SCANNED');
  expect(job.workflow_prerequisites!.workflows[0].nodes.every(node => node.observation === 'unknown')).toBe(true);
  expect(job.workflow_prerequisites!.workflows[0].loader).toMatchObject({observation: 'unknown', advertised_count: null, candidate_ids: []});
  // Distinctive new evidence fences the prior scan's COMPLETED badge/article.
  await expect(observation).toContainText('服务广告条目：1');
  await expect(observation.getByText('目录组件声明（1）', {exact: true})).toBeVisible();
  await expect(discovery.getByText('COMPLETED', {exact: true})).toBeVisible();
  await expect(observation.getByRole('article')).toHaveCount(1);
  const report = await body<AIEnvironmentReport>(await request.get(`${root}/environment`, {headers}));
  expect(report.scan_id).toBe(job.id);
  expect(report.model_files).toEqual([]);
  expect(report.inference_status).toBe('NOT_RUN'); expect(report.windows_acceptance).toBe('NOT_RUN');
  const proof = report.workflow_prerequisites!;
  expect(proof).toMatchObject({schema_version: 1, scan_id: job.id, scan_status: 'COMPLETED', definition_status: 'COMPLETE'});
  expect(proof.workflows).toHaveLength(1);
  const workflow = proof.workflows[0];
  expect(workflow).toMatchObject({adapter_id: 'comfy-sd-checkpoint-v1', evidence_status: 'COMPLETE', metadata_status: 'NOT_VERIFIED', inference_status: 'NOT_RUN'});
  expect(Object.fromEntries(workflow.nodes.map(node => [node.node_class, node.observation]))).toEqual({
    CheckpointLoaderSimple: 'observed', KSampler: 'observed', EmptyLatentImage: 'observed',
    CLIPTextEncode: 'observed', VAEDecode: 'observed', SaveImage: 'not_observed',
  });
  expect(workflow.loader).toMatchObject({node_class: 'CheckpointLoaderSimple', input_field: 'ckpt_name', observation: 'observed', advertised_count: 1});
  const snapshot = await body<LocalDiscoverySnapshot>(await request.get(root, {headers}));
  expect(snapshot.scan?.workflow_prerequisites).toEqual(proof);
  expect((await body<LocalDiscoveryScan>(await request.get(`${root}/scan/${job.id}`, {headers}))).workflow_prerequisites).toEqual(proof);
  expect(workflow.loader.candidate_ids).toEqual(snapshot.scan!.candidates.filter(row => row.runtime_id === workflow.runtime_id && row.model_name === 'synthetic-prerequisite-sdxl.safetensors').map(row => row.id));
  expect(workflow.loader.candidate_ids).toHaveLength(1);
  expect(snapshot.registrations).toEqual([]);
  expect(proof.components).toEqual([{model_id: 'synthetic-prerequisite-catalogue-only', model_display_name: 'Synthetic catalogue requirement',
    component_id: 'synthetic-prerequisite-text-encoder', component_type: 'TEXT_ENCODER', observation: 'unknown',
    reason: 'NO_COMPONENT_IDENTITY_EVIDENCE', metadata_status: 'NOT_VERIFIED', inference_status: 'NOT_RUN'}]);

  const workflowCard = observation.getByRole('article', {name: 'Stable Diffusion checkpoint (T2I) 工作流观察', exact: true});
  await expect(workflowCard.getByText('有界响应已检查（COMPLETE）', {exact: true})).toBeVisible();
  await expect(workflowCard.getByText('元数据验证：NOT_VERIFIED · 实际生成：NOT_RUN', {exact: true})).toBeVisible();
  await expect(workflowCard).toContainText('CheckpointLoaderSimple.ckpt_name · 已观察到（observed）');
  await expect(workflowCard).toContainText('服务广告条目：1');
  await expect(workflowCard).toContainText('可对应同次 Runtime 候选：1');
  await expect(workflowCard.locator('details')).not.toHaveAttribute('open', '');
  await workflowCard.getByText('查看所需节点（6）', {exact: true}).click();
  await expect(workflowCard.getByText('KSampler · 已观察到（observed）', {exact: true})).toBeVisible();
  await expect(workflowCard.getByText('SaveImage · 本次未观察到（not_observed）', {exact: true})).toBeVisible();
  await expect(observation).toContainText('本次未观察到不等于未安装');
  await expect(observation).toContainText('不表示这些组件已安装或属于上述工作流');
  const components = observation.locator('details').filter({has: page.getByText('目录组件声明（1）', {exact: true})});
  await expect(components).not.toHaveAttribute('open', '');
  await components.getByText('目录组件声明（1）', {exact: true}).click();
  await expect(components.getByRole('listitem')).toHaveCount(1);
  await expect(components.getByRole('listitem')).toContainText('synthetic-prerequisite-text-encoder · TEXT_ENCODER · 未知（unknown）');
  await expect(components).toContainText('组件身份无对应证据');

  const terminal = await receipt(request);
  expect(terminal.hardware_calls).toBe(before.hardware_calls + 1);
  expect(terminal.probe_calls.length).toBe(before.probe_calls.length + 7);
  expect(terminal.probe_calls.filter(call => call.path === '/object_info')).toHaveLength(3);
  expect(terminal.probe_calls.every(call => call.method === 'GET' && call.body === null)).toBe(true);
  expect(terminal.synthetic_metadata_fixtures).toEqual(before.synthetic_metadata_fixtures);
  expect(terminal.registrations).toBe(0); expect(terminal.enabled_registrations).toBe(0);
  expect(terminal.launch_attempts).toBe(0); expect(terminal.model_weights_loaded).toBe(false);
  expect(terminal.blocked_attempts).toEqual([]);
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({width, height}); await page.evaluate(() => document.fonts.ready);
    await observation.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({path: info.outputPath(`m3-prerequisite-observations-${width}.png`)});
  }
  // Reload clears the ephemeral host owner. Explicitly rebind through the real
  // UI to read the same scan; expand/read operations never request another scan.
  await page.reload();
  await expect(observation).toHaveCount(0);
  await bindHostAndOpenModels(page);
  await expect(observation.getByRole('article')).toHaveCount(1);
  await expect(workflowCard).toContainText('服务广告条目：1');
  expect(await body(await request.get(`${root}/environment`, {headers}))).toEqual(report);
  expect(await receipt(request)).toEqual(terminal);
  expect(mutations).toEqual([`POST ${root}/onboarding/scan`]);

  // The final new journey may revoke only its already-existing synthetic host.
  // A denied read must clear private prerequisite evidence without any scan.
  expect((await request.post(`${fixtureRoot}/revoke-current-host`, {headers, data: {confirmed: true}})).status()).toBe(204);
  const deniedPreview = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/onboarding/scan-scope`);
  await discovery.getByRole('button', {name: '重新预览检测范围', exact: true}).click();
  expect((await deniedPreview).status()).toBe(401);
  await expect(observation).toHaveCount(0);
  await expect(discovery.getByText(/已失效或权限不足/)).toBeVisible();
  expect((await request.get(`${root}/environment`, {headers})).status()).toBe(401);
  expect(await receipt(request, SECOND_TOKEN)).toEqual(terminal);
  expect(mutations).toEqual([`POST ${root}/onboarding/scan`]);
  expect(pageErrors).toEqual([]);
  await info.attach('m3-prerequisite-observation-receipt', {body: JSON.stringify({proof: 'SYNTHETIC_ADVERTISEMENTS_ORIGINAL_FILE_HTTP_UI',
    before, seeded, terminal, scan_id: job.id, workflow_prerequisites: proof, revoked_read_status: 401,
    actual_hardware: 'NOT_RUN', actual_model_inference: 'NOT_RUN', windows_native: 'NOT_RUN', paid_api: 'NOT_RUN'}, null, 2), contentType: 'application/json'});
});
