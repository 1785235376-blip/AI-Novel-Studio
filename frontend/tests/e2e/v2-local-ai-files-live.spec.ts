import {expect, test, request as independentRequest, type APIRequestContext, type APIResponse, type Page} from '@playwright/test';
import type {AIEnvironmentReport, LocalAiScanScope, LocalDiscoveryScan} from '../../src/localAiDiscoveryApi';

const TOKEN = 'synthetic-m3-browser-existing-host';
const headers = {'X-Session-Token': TOKEN};
const root = '/api/model-center/local-ai';
const owned = new WeakMap<APIRequestContext, Set<string>>();
type FixtureReceipt = {synthetic: boolean; probe_calls: unknown[]; hardware_calls: number; scan_id: string | null;
  scan_status: string | null; registrations: number; enabled_registrations: number; launch_attempts: number;
  blocked_attempts: string[]; model_weights_loaded: false; synthetic_metadata_fixtures: {name: string; bytes: number; sha256: string}[]};

async function body<T>(response: Pick<APIResponse, 'ok' | 'status' | 'text' | 'json'>): Promise<T> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBe(true);
  return response.json() as Promise<T>;
}
const receipt = async (request: APIRequestContext) => body<FixtureReceipt>(await request.get('/api/__tests__/v2-discovery-fixture', {headers}));

async function bindHostAndOpenModels(page: Page) {
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
  await page.getByRole('tablist', {name: '创作模块', exact: true}).getByRole('tab', {name: '主控', exact: true}).click();
  await page.getByRole('tablist', {name: '主控设置', exact: true}).getByRole('tab', {name: '模型中心', exact: true}).click();
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

test('M3 files original File HTTP UI reuses observed metadata without claiming inference', async ({page, request}, info) => {
  info.annotations.push({type: 'verification', description: 'Original File/HTTP/UI and discovery worker; explicit closed synthetic metadata fixture. No route mocks, user files, model weights, actual hardware, inference or paid service.'});
  owned.set(request, new Set());
  expect(await body(await request.get('/api/novels'))).toEqual([]);
  // This additive file follows the original consent file in the same serial
  // project and fails closed if that prerequisite is absent. It does not
  // reset that owner's scan, receipts or data to manufacture a clean result.
  const before = await receipt(request);
  expect(before.synthetic).toBe(true);
  expect(before.scan_status).toBe('COMPLETED');
  expect(before.synthetic_metadata_fixtures).toEqual([]);
  const seededResponse = await request.post('/api/__tests__/v2-discovery-fixture/seed-metadata',
    {headers, data: {fixture: 'metadata-only-v1', confirmed: true}});
  expect(seededResponse.status()).toBe(201);
  const seeded = await body<{synthetic: true; metadata_fixtures: {name: string; bytes: number; sha256: string}[]}>(seededResponse);
  expect(seeded.synthetic).toBe(true);
  expect(seeded.metadata_fixtures).toHaveLength(3);
  expect(seeded.metadata_fixtures.reduce((total, row) => total + row.bytes, 0)).toBeLessThan(512);
  const afterSeed = await receipt(request);
  expect(afterSeed.probe_calls).toEqual(before.probe_calls);
  expect(afterSeed.hardware_calls).toBe(before.hardware_calls);
  expect(afterSeed.scan_id).toBe(before.scan_id);

  const mutations: string[] = [], pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('request', value => {
    const path = new URL(value.url()).pathname;
    if (path.startsWith(root) && !['GET', 'HEAD', 'OPTIONS'].includes(value.method())) mutations.push(`${value.method()} ${path}`);
  });
  await page.goto('/');
  await page.getByLabel('小说名称', {exact: true}).fill('M3 合成模型文件观察');
  const creating = page.waitForResponse(value => new URL(value.url()).pathname === '/api/novels' && value.request().method() === 'POST');
  await page.getByRole('button', {name: '创建小说', exact: true}).click();
  const created = await creating;
  if (created.status() === 201) {const row = await created.json(); if (typeof row.id === 'string' && row.id) owned.get(request)!.add(row.id);}
  expect(created.status()).toBe(201); expect(owned.get(request)!.size).toBe(1);
  await bindHostAndOpenModels(page);
  await expect(page.getByRole('button', {name: '预览 AI 检测范围', exact: true})).toBeEnabled();
  expect((await receipt(request)).hardware_calls).toBe(before.hardware_calls);
  expect(mutations).toEqual([]);
  const consent = page.getByRole('region', {name: '确认后端主机检测范围', exact: true});
  await page.getByRole('button', {name: '预览 AI 检测范围', exact: true}).click();
  await expect(consent.getByRole('checkbox')).not.toBeChecked();
  const previewing = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/onboarding/scan-scope`
    && new URL(value.url()).searchParams.get('include_common_model_dirs') === 'true');
  await consent.getByRole('checkbox').check();
  const scope = await body<LocalAiScanScope>(await previewing);
  expect(scope.roots).toHaveLength(1);
  const confirming = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/onboarding/scan` && value.request().method() === 'POST');
  await consent.getByRole('button', {name: '确认此范围并检测', exact: true}).click();
  const confirmed = await confirming;
  expect(confirmed.status()).toBe(202);
  expect(confirmed.request().postDataJSON()).toEqual({scope_digest: scope.scope_digest, confirmed: true});
  const job = await confirmed.json() as LocalDiscoveryScan;
  const observation = page.getByRole('region', {name: '本次扫描的文件与索引观察', exact: true});
  await expect(observation.getByRole('article')).toHaveCount(3);
  await expect(page.getByText('COMPLETED', {exact: true})).toBeVisible();
  const report = await body<AIEnvironmentReport>(await request.get(`${root}/environment`, {headers}));
  expect(report.scan_id).toBe(job.id); expect(report.model_files).toHaveLength(3);
  expect(report.inference_status).toBe('NOT_RUN'); expect(report.windows_acceptance).toBe('NOT_RUN');
  const diffusers = report.model_files.find(row => row.format === 'DIFFUSERS')!;
  expect(diffusers.size_bytes).toBe(seeded.metadata_fixtures.find(row => row.name === 'model_index.json')!.bytes);
  const indexCard = observation.getByRole('article', {name: `${diffusers.name} 文件观察`, exact: true});
  await expect(indexCard).toContainText('索引大小');
  await expect(indexCard).toContainText(`${diffusers.size_bytes} bytes`);
  await expect(indexCard).toContainText('不代表目录或权重总大小');
  await expect(indexCard).toContainText('Runtime 绑定未知');
  await expect(indexCard.getByText(diffusers.path, {exact: true})).not.toBeVisible();
  await expect(observation.getByRole('article', {name: 'synthetic-metadata.safetensors 文件观察', exact: true})).toContainText('Runtime 绑定未知');
  await expect(observation.getByRole('article', {name: 'synthetic-metadata.gguf 文件观察', exact: true})).toContainText('候选 · 未注册');
  await expect(observation).toContainText('未按内容去重');
  await expect(observation.getByText('已授权路由', {exact: true})).toHaveCount(0);
  const terminal = await receipt(request);
  expect(terminal.hardware_calls).toBe(before.hardware_calls + 1);
  expect(terminal.probe_calls.length).toBe(before.probe_calls.length + 7);
  expect(terminal.registrations).toBe(0); expect(terminal.enabled_registrations).toBe(0);
  expect(terminal.launch_attempts).toBe(0); expect(terminal.model_weights_loaded).toBe(false);
  expect(terminal.blocked_attempts).toEqual([]);
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({width, height}); await page.evaluate(() => document.fonts.ready);
    await observation.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({path: info.outputPath(`m3-file-observations-${width}.png`)});
  }
  // The Host credential is intentionally not persisted. Rebind the existing
  // synthetic identity through the real UI before reading the old scan again.
  await page.reload();
  await expect(page.getByRole('region', {name: '本次扫描的文件与索引观察', exact: true})).toHaveCount(0);
  await bindHostAndOpenModels(page);
  await expect(observation.getByRole('article')).toHaveCount(3);
  expect(await receipt(request)).toEqual(terminal);
  expect(mutations).toEqual([`POST ${root}/onboarding/scan`]);
  expect(pageErrors).toEqual([]);
  await info.attach('m3-metadata-observation-receipt', {body: JSON.stringify({seeded, before, terminal, scan_id: job.id,
    proof: 'SYNTHETIC_METADATA_ORIGINAL_FILE_HTTP_UI', inference_status: 'NOT_RUN'}, null, 2), contentType: 'application/json'});
});
