import { expect, test, type APIResponse, type Page } from '@playwright/test';
import http from 'node:http';
import { createHash } from 'node:crypto';
import type { AddressInfo } from 'node:net';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api', UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
const png = 'iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAFklEQVR4nGMQSFhAEmIY1TCqYfhqAAALcBAQO3WHHAAAAABJRU5ErkJggg==';
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function tools(page: Page, name: string) {
  if (!(await page.getByRole('navigation', { name: '实验功能' }).isVisible())) {
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  }
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name, exact: true }).click();
}

test('registered original local-image route composes explicit generation, benchmark, selected refresh and observed replay', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '', registration = '';
  const calls: Record<string, unknown>[] = [];
  const modelDigest = createHash('sha256').update('SYNTHETIC_CHECKPOINT_CONTENT_FOR_PROTOCOL_TEST_ONLY').digest('hex');
  // This is a tiny loopback protocol fixture, not an image model. App routes,
  // discovery/enablement, original LocalImageAdapter, broker and stores are real.
  const server = http.createServer((incoming, response) => {
    response.setHeader('Content-Type', 'application/json');
    if (incoming.method === 'GET' && incoming.url === '/sdapi/v1/sd-models') {
      response.end(JSON.stringify([{ title: 'synthetic-browser-fixture.ckpt', sha256: modelDigest }])); return;
    }
    if (incoming.method === 'POST' && incoming.url === '/sdapi/v1/txt2img') {
      let raw = ''; incoming.on('data', chunk => { raw += chunk; });
      incoming.on('end', () => { calls.push(JSON.parse(raw)); response.end(JSON.stringify({ images: [png] })); }); return;
    }
    response.statusCode = 404; response.end('{}');
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const endpoint = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
  info.annotations.push({ type: 'verification', description: 'Actual React/File/API/original discovery-registry/broker/media composition. Isolated loopback A1111 protocol fixture returns fixed synthetic PNG bytes and an explicitly synthetic checkpoint digest. No app response mocks, GPU, real weights, downloads, credentials, cloud or paid inference. Local Chromium NOT_RUN (known EPERM); hosted CI must establish execution.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('Registered local media protocol fixture');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await body(await creating)).id;
    const base = `${API}/novels/${nid}/experimental`, discovery = `${API}/model-center/local-ai`;
    await body(await request.post(`${discovery}/runtimes`, { headers, data: { name: 'Synthetic A1111 browser fixture', type: 'AUTOMATIC1111', endpoint } }));
    const scan = await body(await request.post(`${discovery}/scan`, { headers }));
    await expect.poll(async () => (await body(await request.get(`${discovery}/scan/${scan.id}`, { headers }))).status, { timeout: 45000 }).not.toBe('RUNNING');
    const scanned = await body(await request.get(`${discovery}/scan/${scan.id}`, { headers }));
    registration = scanned.candidates.find((row: any) => row.runtime_config.endpoint === endpoint).id;
    await body(await request.post(`${discovery}/candidates/${registration}/validate`, { headers }));
    await body(await request.post(`${discovery}/candidates/${registration}/register`, { headers }));
    // License acknowledgment applies only to the fixture bytes declared above.
    await body(await request.put(`${discovery}/registrations/${registration}`, { headers, data: { license_confirmed: true, workflow_adapter_id: '' } }));
    await body(await request.post(`${discovery}/registrations/${registration}/enable`, { headers, data: { confirmed: true } }));
    const route = (await body(await request.get(`${base}/model-broker/status`, { headers }))).candidates.find((row: any) => row.adapter_id === `registered-image:${registration}`);
    expect(route.available).toBe(true); expect(route.synthetic).toBe(false); expect(calls).toHaveLength(0);
    const now = new Date();
    await body(await request.put(`${base}/model-broker/price`, { headers, data: { route_id: route.route_id, route_fingerprint: route.fingerprint, reserve_microusd: 0, source: 'Explicit estimate for zero-provider-fee local synthetic transport fixture', as_of: now.toISOString(), expires_at: new Date(now.getTime() + 3600000).toISOString(), expected_version: 0 } }));
    const reconcile = async () => {
      const ledger = (await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger;
      for (const row of ledger.filter((item: any) => item.status === 'UNKNOWN_UPSTREAM')) {
        expect(row.actual_microusd).toBeNull();
        await body(await request.post(`${base}/model-broker/ledger/${row.id}/reconcile`, { headers, data: { expected_version: row.version, actual_microusd: 0, upstream_terminal_confirmed: true, evidence_note: 'The isolated synthetic HTTP fixture completed and has no paid provider. This is explicit test reconciliation.' } }));
      }
    };
    const chapter = await body(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: '图像来源', content: '她在港口举起一盏灯。' } }));
    const brief = await body(await request.post(`${base}/media/cover-briefs`, { headers, data: { title: 'Registered cover fixture', chapter_ids: [chapter.id], prompt: 'Synthetic protocol input' } }));
    await tools(page, '封面与分镜');
    await page.getByLabel('待生成媒体 Brief', { exact: true }).selectOption(brief.id);
    await page.getByLabel('图像工作流路线', { exact: true }).selectOption(route.adapter_id);
    await page.getByLabel('本地图像 seed', { exact: true }).fill('23');
    const queued = page.waitForResponse(r => r.url().endsWith('/media/tasks') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建本地图像任务', exact: true }).click(); const original = await body(await queued);
    expect(calls).toHaveLength(0);
    await page.getByRole('button', { name: '检查本地图像路线与费用', exact: true }).click();
    await expect(page.getByRole('button', { name: '按预检执行本地图像任务', exact: true })).toBeEnabled();
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      await page.getByRole('region', { name: '已登记本地图像执行', exact: true }).scrollIntoViewIfNeeded();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`registered-media-preflight-${width}.png`) });
    }
    await page.getByRole('button', { name: '按预检执行本地图像任务', exact: true }).click();
    await expect(page.getByRole('article', { name: '媒体任务', exact: true })).toContainText('SUCCEEDED');
    expect(calls).toHaveLength(1); expect(calls[0].seed).toBe(23); await reconcile();
    const before = (await body(await request.get(`${base}/media/tasks`, { headers }))).items.find((row: any) => row.id === original.id);
    expect(before.observed_environment.model_digest).toBe(modelDigest);

    const testSet = await body(await request.post(`${base}/model-benchmarks/sets`, { headers, data: { title: 'Registered image protocol sample', cases: [{ title: 'Synthetic image sample', kind: 'IMAGE_WORKFLOW', prompt: 'Synthetic image only' }] } }));
    await tools(page, '模型路由与评测');
    await page.getByLabel('待运行任务集', { exact: true }).selectOption(testSet.id);
    await page.getByLabel('本次评测的本地模型路线', { exact: true }).selectOption(route.route_id);
    await page.getByRole('button', { name: '建立有界评测运行', exact: true }).click();
    await page.getByRole('button', { name: '执行下一评测样本', exact: true }).click();
    await expect(page.getByText('1 / 1 已完成；每次按钮只执行一个保存的样本。', { exact: true })).toBeVisible();
    const benchmark = (await body(await request.get(`${base}/model-benchmarks/status`, { headers }))).runs[0];
    expect(benchmark.results[0].media_receipt.outputs[0].media.width).toBe(16);
    expect(benchmark.results[0].media_receipt.outputs[0].status).toBe('PENDING_REVIEW'); expect(calls).toHaveLength(2); await reconcile();

    const currentChapter = await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }));
    await body(await request.put(`${API}/chapters/${chapter.id}`, { headers, data: { version: currentChapter.version, content: '她在更新的港口举起一盏灯。' } }));
    await tools(page, '修改影响与更新');
    await page.getByLabel('发生修改的来源', { exact: true }).selectOption(`CHAPTER:${chapter.id}`);
    const selected = page.getByRole('checkbox', { name: new RegExp(`选择更新.*${original.id}`) });
    await selected.check(); await page.getByRole('button', { name: '预检选中的 1 项', exact: true }).click();
    const preparing = page.waitForResponse(r => r.url().includes('/change-impact/preflights/') && r.url().endsWith('/prepare'));
    await page.getByRole('button', { name: '仅准备这些选中更新', exact: true }).click(); const refreshed = (await body(await preparing)).items[0];
    await page.getByRole('button', { name: '执行此选中任务', exact: true }).click();
    await expect(page.getByRole('article', { name: `选择性更新 ${refreshed.task_id}`, exact: true })).toContainText('SUCCEEDED'); expect(calls).toHaveLength(3); await reconcile();

    await tools(page, '资产来源与复现');
    await page.getByLabel('已完成的媒体任务', { exact: true }).selectOption(refreshed.task_id);
    await page.getByRole('button', { name: '记录所选任务清单', exact: true }).click();
    await expect(page.getByRole('region', { name: '生产清单详情', exact: true })).toContainText('seed：23');
    await page.getByRole('button', { name: '检查重放条件', exact: true }).click();
    await expect(page.getByRole('region', { name: '重放预检', exact: true })).toContainText('确定性协议可复现：否');
    await page.getByRole('button', { name: '创建新的重放任务', exact: true }).click();
    await page.getByRole('button', { name: '执行这次本地重放', exact: true }).click();
    await expect(page.getByRole('region', { name: '重放历史', exact: true })).toContainText('SUCCEEDED'); expect(calls).toHaveLength(4);
    const after = (await body(await request.get(`${base}/media/tasks`, { headers }))).items.find((row: any) => row.id === original.id);
    expect(after.proposal_ids).toEqual(before.proposal_ids);
    expect((await body(await request.get(`${API}/novels/${nid}/assets`, { headers })))).toHaveLength(0);
    await page.screenshot({ path: info.outputPath('registered-media-refresh-origin-replay.png'), fullPage: true });
    await reconcile();
  } finally {
    await quiesce();
    if (registration) await request.delete(`${API}/model-center/local-ai/registrations/${registration}`, { headers });
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status());
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
});
