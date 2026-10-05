import {expect, test, type Page} from '@playwright/test';

// Synthetic metadata and mocked host requests only. These browser checks do not
// start a Runtime, read host directories or claim real model inference coverage.
const model = (id: string, name: string, modality: string, runtimeType = 'COMFYUI') => ({
  id, candidate_id: id, display_name: name, model_id: id, family: name.toUpperCase(), modality,
  declared_capabilities: [modality], verified_capabilities: [], runtime_id: runtimeType.toLowerCase(),
  runtime_type: runtimeType, source: runtimeType, model_name: `${name}.safetensors`, local_path: '',
  status: 'DISCOVERED', compatible: 'NOT_VERIFIED', verified: false, enabled: false, license_required: true, license_confirmed: false,
  validated_at: null as string | null, validation_notes: ['INFERENCE_NOT_RUN'], enable_eligible: false, enable_blockers: ['VALIDATION_REQUIRED'],
  evidence: {model_listed: true, model_file_exists: null, loader_nodes: ['ExampleLoader'], workflow_status: 'NOT_CONFIGURED', generation_verified: false},
});
async function setup(page: Page, populated = false) {
  const calls: {method: string; path: string; body: unknown}[] = [];
  const qwen = model('qwen', 'Qwen3 local', 'TEXT', 'OLLAMA');
  let currentScan: Record<string, unknown> | null = populated ? {id: 'scan-one', status: 'PARTIAL', runtimes: [{id: 'ollama', name: 'Ollama', type: 'OLLAMA', endpoint: 'http://127.0.0.1:11434', status: 'RUNNING', management: 'EXTERNAL', version: '0.9'}], candidates: [qwen, model('qwen-image', 'Qwen Image', 'IMAGE'), model('minimax', 'MiniMax H3', 'VIDEO'), model('rife', 'RIFE', 'INTERPOLATION'), model('unknown', 'Unknown', 'UNKNOWN')], errors: [{runtime_id: 'a1111', code: 'NOT_FOUND'}]} : null;
  let registrations: ReturnType<typeof model>[] = [];
  await page.addInitScript(() => {localStorage.setItem('studio.session', 'local-ai-browser-test');});
  await page.route('**/api/**', async route => {
    const request = route.request(), path = new URL(request.url()).pathname;
    if (path.startsWith('/api/model-center/local-ai')) {
      calls.push({method: request.method(), path, body: request.postDataJSON()});
      if (path === '/api/model-center/local-ai') return route.fulfill({json: {scan: currentScan, registrations, settings: {scan_roots: [], runtimes: []}, hardware: {platform: 'Windows', architecture: 'AMD64', cpu: 'Fixture CPU', ram_bytes: 32 * 1024 ** 3, gpus: [{vendor: 'NVIDIA', name: 'Fixture GPU', dedicated_vram_bytes: 16 * 1024 ** 3}], status: 'DETECTED', notes: []}, workflow_adapters: []}});
      if (path.endsWith('/scan')) {currentScan = {id: 'scan-one', status: 'COMPLETED', runtimes: [], candidates: [qwen], errors: []}; return route.fulfill({json: currentScan});}
      if (path.endsWith('/validate')) {Object.assign(qwen, {validated_at: '2026-10-05T00:00:00Z', verified_capabilities: ['TEXT'], enable_eligible: false, enable_blockers: ['LICENSE_VALIDATION_REQUIRED'], status: 'LICENSE_REQUIRED'}); return route.fulfill({json: qwen});}
      if (path.endsWith('/register')) {registrations = [{...qwen}]; return route.fulfill({json: registrations[0]});}
      if (path.endsWith('/registrations/qwen') && request.method() === 'PUT') {
        const body = request.postDataJSON();
        Object.assign(qwen, {license_confirmed: body.license_confirmed === true, enable_eligible: body.license_confirmed === true, enable_blockers: body.license_confirmed === true ? [] : ['LICENSE_VALIDATION_REQUIRED'], status: body.license_confirmed === true ? 'VALIDATION_REQUIRED' : 'LICENSE_REQUIRED'});
        registrations = [{...qwen}]; return route.fulfill({json: registrations[0]});
      }
      if (path.endsWith('/enable')) {
        if (!registrations[0]?.license_confirmed || !registrations[0]?.enable_eligible || request.postDataJSON()?.confirmed !== true) return route.fulfill({status: 409, json: {code: 'LOCAL_AI_ENABLE_BLOCKED'}});
        registrations = [{...qwen, enabled: true}]; return route.fulfill({json: registrations[0]});
      }
      return route.fulfill({status: 404, json: {code: 'TEST_UNEXPECTED_REQUEST'}});
    }
    if (path === '/api/model-center/health') return route.fulfill({json: {status: 'READY', mutation_authorization: {can_mutate: true, mutation_auth_mode: 'TRUSTED_SESSION'}}});
    if (/\/api\/model-center\/(models|runtimes|pipelines)$/.test(path)) return route.fulfill({json: {items: []}});
    return route.fulfill({status: 503, json: {code: 'TEST_UNRELATED_SERVICE_UNAVAILABLE', message: 'Synthetic fixture boundary'}});
  });
  await page.goto('/');
  await page.getByRole('tab', {name: '主控', exact: true}).click();
  await page.getByRole('tab', {name: '模型中心', exact: true}).click();
  await expect(page.locator('.local-ai')).toBeVisible();
  await expect(page.getByText('Fixture CPU', {exact: true})).toBeVisible();
  return calls;
}

test('Local AI requires each explicit lifecycle action before routing', async ({page}) => {
  const calls = await setup(page);
  const writes = () => calls.filter(call => call.method !== 'GET');
  await expect(page.getByText('尚未开始扫描', {exact: true})).toBeVisible();
  expect(writes()).toHaveLength(0);
  await page.getByRole('button', {name: '检测本机 AI 环境', exact: true}).click();
  await expect(page.getByRole('button', {name: '注册', exact: true})).toBeDisabled();
  await page.getByRole('button', {name: '验证', exact: true}).click();
  await expect(page.getByRole('button', {name: '注册', exact: true})).toBeEnabled();
  await page.getByRole('button', {name: '注册', exact: true}).click();
  await expect(page.getByText('已注册 · 未启用', {exact: true})).toBeVisible();
  expect(writes().map(call => call.path.split('/').at(-1))).toEqual(['scan', 'validate', 'register']);
  await expect(page.getByRole('button', {name: '启用', exact: true})).toBeDisabled();
  await page.getByRole('button', {name: '配置接入条件', exact: true}).click();
  const license = page.getByRole('checkbox', {name: '我已核对该模型授权，允许在约定用途内使用'});
  await expect(license).not.toBeChecked(); expect(writes()).toHaveLength(3);
  await license.check(); await page.getByRole('button', {name: '保存接入条件', exact: true}).click();
  await expect(page.getByRole('button', {name: '启用', exact: true})).toBeEnabled();
  expect(writes().at(-1)).toMatchObject({method: 'PUT', body: {workflow_adapter_id: '', license_confirmed: true}});
  await page.getByRole('button', {name: '启用', exact: true}).click();
  await expect(page.getByRole('region', {name: '确认启用模型'})).toBeVisible();
  expect(writes()).toHaveLength(4);
  await page.getByRole('button', {name: '确认启用', exact: true}).click();
  await expect(page.getByRole('button', {name: '停用', exact: true})).toBeVisible();
  expect(writes().at(-1)?.body).toEqual({confirmed: true});
});

for (const viewport of [{width: 1366, height: 768}, {width: 1440, height: 900}, {width: 1920, height: 1080}]) {
  test(`Local AI preserves shell and model geometry ${viewport.width}x${viewport.height}`, async ({page}, testInfo) => {
    await page.setViewportSize(viewport); await setup(page, true); await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole('region', {name: 'Video 视频'})).toContainText('MiniMax H3');
    await expect(page.getByRole('region', {name: 'Utilities 工具'})).toContainText('RIFE');
    await expect(page.getByRole('region', {name: 'Image 图片'})).not.toContainText('RIFE');
    await expect(page.locator('.local-ai')).toContainText('Runtime 已列出，文件存在性未独立验证');
    const geometry = await page.evaluate(() => {
      const rect = (selector: string) => document.querySelector(selector)!.getBoundingClientRect();
      const main = document.querySelector('.main-workspace')!;
      return {header: rect('.global-header').height, context: rect('.context-bar').height, status: rect('.status-bar').height, width: document.documentElement.scrollWidth, viewport: innerWidth, mainWidth: main.clientWidth, mainScroll: main.scrollWidth};
    });
    expect(geometry.header).toBe(56); expect(geometry.context).toBe(44); expect(geometry.status).toBe(32);
    expect(geometry.width).toBeLessThanOrEqual(geometry.viewport); expect(geometry.mainScroll).toBeLessThanOrEqual(geometry.mainWidth);
    await page.screenshot({path: testInfo.outputPath(`local-ai-${viewport.width}.png`), fullPage: true});
  });
}
