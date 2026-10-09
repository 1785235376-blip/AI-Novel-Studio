import {expect, test, request as independentRequest, type APIRequestContext, type APIResponse, type Page} from '@playwright/test';

const FIRST = 'synthetic-m3-browser-existing-host', SECOND = 'synthetic-m3-browser-second-host';
const root = '/api/model-center/local-ai';
const owned = new WeakMap<APIRequestContext, Set<string>>();
type Receipt = {probe_calls: unknown[]; hardware_calls: number; scan_id: string | null; registrations: number;
  enabled_registrations: number; launch_attempts: number; blocked_attempts: string[]; model_weights_loaded: false};
async function body<T>(response: Pick<APIResponse, 'ok' | 'status' | 'text' | 'json'>): Promise<T> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBe(true);
  return response.json() as Promise<T>;
}
const receipt = async (request: APIRequestContext, token = FIRST) => body<Receipt>(await request.get('/api/__tests__/v2-discovery-fixture', {headers: {'X-Session-Token': token}}));

async function bindAndOpen(page: Page, token: string, actor: string) {
  await page.getByRole('button', {name: '打开功能导航', exact: true}).click();
  const navigation = page.getByRole('navigation', {name: '功能面板导航', exact: true});
  const group = navigation.locator('.feature-group__header').filter({hasText: '协作'});
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await navigation.getByRole('button', {name: 'Agent 团队', exact: true}).click();
  await page.keyboard.press('Escape');
  const unbind = page.getByRole('button', {name: '解绑本机可信会话', exact: true});
  if (await unbind.count()) await unbind.click();
  await page.getByLabel('本机访问凭证', {exact: true}).fill(token);
  const validating = page.waitForResponse(value => new URL(value.url()).pathname === '/api/local-session');
  await page.getByRole('button', {name: '验证并绑定本机会话', exact: true}).click();
  expect(await body(await validating)).toEqual({session_mode: 'LOCAL_HOST', actor_id: actor});
  const snapshot = page.waitForResponse(value => new URL(value.url()).pathname === root && value.request().method() === 'GET');
  await page.getByRole('tablist', {name: '创作模块', exact: true}).getByRole('tab', {name: '主控', exact: true}).click();
  await page.getByRole('tablist', {name: '主控设置', exact: true}).getByRole('tab', {name: '模型中心', exact: true}).click();
  const response = await snapshot;
  expect(response.status()).toBe(200);
  expect(response.request().headers()['x-session-token']).toBe(token);
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

for (const mode of ['default-off', 'acceptance-mode'] as const) test(`M3 legacy ${mode} uses verified host for explicit scan and clears revoked private state`, async ({page, request}, info) => {
  info.annotations.push({type: 'verification', description: 'Real File/HTTP/React with original legacy discovery and existing trusted-session owner. Two fixed synthetic identities and metadata adapters only; no real model, user host, inference or paid API.'});
  owned.set(request, new Set());
  expect(await body(await request.get('/api/novels'))).toEqual([]);
  const before = await receipt(request);
  expect(before.scan_id).toBeNull(); expect(before.hardware_calls).toBe(0); expect(before.probe_calls).toEqual([]);
  const mutations: string[] = [], pageErrors: string[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('request', value => {const path = new URL(value.url()).pathname;
    if (path.startsWith(root) && !['GET', 'HEAD', 'OPTIONS'].includes(value.method())) mutations.push(`${value.method()} ${path}`);
  });
  await page.goto('/');
  await page.getByLabel('小说名称', {exact: true}).fill(`M3 ${mode} 合法主机扫描`);
  const creating = page.waitForResponse(value => new URL(value.url()).pathname === '/api/novels' && value.request().method() === 'POST');
  await page.getByRole('button', {name: '创建小说', exact: true}).click();
  const created = await creating;
  if (created.status() === 201) {const row = await created.json(); if (typeof row.id === 'string' && row.id) owned.get(request)!.add(row.id);}
  expect(created.status()).toBe(201); expect(owned.get(request)!.size).toBe(1);
  await bindAndOpen(page, FIRST, 'synthetic-m3-browser-author');
  const discovery = page.locator('.local-ai');
  await expect(discovery.getByRole('button', {name: '检测本机 AI 环境', exact: true})).toBeEnabled();
  await expect(discovery.getByRole('button', {name: '预览 AI 检测范围', exact: true})).toHaveCount(0);
  expect((await receipt(request)).probe_calls).toEqual([]); expect(mutations).toEqual([]);
  const firstScan = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/scan` && value.request().method() === 'POST');
  await discovery.getByRole('button', {name: '检测本机 AI 环境', exact: true}).click();
  const firstResponse = await firstScan;
  expect(firstResponse.status()).toBe(202);
  expect(firstResponse.request().headers()['x-session-token']).toBe(FIRST);
  await expect(discovery.getByText('COMPLETED', {exact: true})).toBeVisible();
  await expect(discovery.getByText('Synthetic consent fixture CPU', {exact: false})).toBeVisible();
  await expect(page.getByRole('region', {name: '本次扫描的文件与索引观察', exact: true})).toHaveCount(0);
  const firstTerminal = await receipt(request);
  expect(firstTerminal.hardware_calls).toBe(1); expect(firstTerminal.probe_calls).toHaveLength(5);

  // Unsaved synthetic private inputs are never sent to configuration endpoints.
  await discovery.getByRole('button', {name: '配置扫描目录', exact: true}).click();
  await discovery.getByLabel('模型目录（每行一个完整路径）', {exact: true}).fill('/synthetic-private-unsubmitted-models');
  await discovery.getByRole('button', {name: '添加本地 Runtime', exact: true}).click();
  await discovery.getByLabel('Runtime 名称', {exact: true}).fill('synthetic-private-runtime-draft');
  expect((await request.post('/api/__tests__/v2-discovery-fixture/revoke-current-host',
    {headers: {'X-Session-Token': FIRST}, data: {confirmed: true}})).status()).toBe(204);
  const deniedScan = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/scan` && value.request().method() === 'POST');
  await discovery.getByRole('button', {name: '重新扫描', exact: true}).click();
  expect((await deniedScan).status()).toBe(401);
  await expect(discovery.getByText(/已失效或权限不足/)).toBeVisible();
  await expect(discovery.getByRole('region', {name: '系统硬件', exact: true})).toHaveCount(0);
  await expect(discovery.getByRole('form', {name: '扫描目录配置', exact: true})).toHaveCount(0);
  await expect(discovery.getByRole('form', {name: '本地 Runtime 配置', exact: true})).toHaveCount(0);
  expect((await request.get(root, {headers: {'X-Session-Token': FIRST}})).status()).toBe(401);
  expect((await receipt(request, SECOND)).hardware_calls).toBe(1);

  await bindAndOpen(page, SECOND, 'synthetic-m3-browser-author-second');
  await expect(discovery.getByText('Synthetic consent fixture CPU', {exact: false})).toBeVisible();
  expect((await receipt(request, SECOND)).hardware_calls).toBe(1);
  const secondScan = page.waitForResponse(value => new URL(value.url()).pathname === `${root}/scan` && value.request().method() === 'POST');
  await discovery.getByRole('button', {name: '重新扫描', exact: true}).click();
  const secondResponse = await secondScan;
  expect(secondResponse.status()).toBe(202);
  expect(secondResponse.request().headers()['x-session-token']).toBe(SECOND);
  await expect(discovery.getByText('COMPLETED', {exact: true})).toBeVisible();
  const terminal = await receipt(request, SECOND);
  expect(terminal.hardware_calls).toBe(2); expect(terminal.probe_calls).toHaveLength(10);
  expect(terminal.registrations).toBe(0); expect(terminal.enabled_registrations).toBe(0);
  expect(terminal.launch_attempts).toBe(0); expect(terminal.model_weights_loaded).toBe(false); expect(terminal.blocked_attempts).toEqual([]);
  expect(mutations).toEqual([`POST ${root}/scan`, `POST ${root}/scan`, `POST ${root}/scan`]);
  expect(pageErrors).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.screenshot({path: info.outputPath(`m3-legacy-${mode}-verified-host.png`)});
  await info.attach(`m3-legacy-${mode}-host-evidence`, {body: JSON.stringify({proof: 'SYNTHETIC_IDENTITIES_ORIGINAL_FILE_HTTP_UI',
    before, firstTerminal, terminal, revoked_request_status: 401, inference_status: 'NOT_RUN'}, null, 2), contentType: 'application/json'});
});
