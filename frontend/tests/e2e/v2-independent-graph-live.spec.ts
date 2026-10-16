import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { StudioGraphRecord, StudioGraphRun } from '../../src/creative/studioGraphTypes';

const owned = new WeakMap<APIRequestContext, Set<string>>();
const pages = new WeakMap<APIRequestContext, Page>();
test.beforeEach(async ({ request }) => {
  expect(await (await request.get('/api/novels')).json(), 'The synthetic graph server must be empty; do not remove unowned projects.').toEqual([]);
  owned.set(request, new Set());
});
test.afterEach(async ({ request }, info) => {
  const page = pages.get(request);
  if (page && !page.isClosed()) {
    if (info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('graph-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
    await page.close();
  }
  for (const id of owned.get(request) || []) {
    const response = await request.delete(`/api/novels/${encodeURIComponent(id)}`);
    expect(response.status(), `Only delete this test's confirmed project: ${await response.text()}`).toBe(204);
  }
  if (owned.has(request)) expect(await (await request.get('/api/novels')).json()).toEqual([]);
});
async function responseFor(page: Page, path: string, method: string, action: () => Promise<unknown>) {
  const pending = page.waitForResponse(value => new URL(value.url()).pathname === path && value.request().method() === method);
  await action(); const result = await pending;
  expect(result.ok(), `${method} ${path}: ${result.status()} ${await result.text()}`).toBe(true);
  return result.json();
}
async function addNode(page: Page, type: string, label: string) {
  await page.getByLabel('节点类型', { exact: true }).selectOption(type);
  await page.getByRole('button', { name: '添加节点', exact: true }).click();
  const name = await page.getByRole('button', { name: new RegExp(`^选择节点 ${label} · `) }).getAttribute('aria-label');
  expect(name).toBeTruthy(); return name!.split(' · ')[1];
}

test('real independent typed graph saves empty and disconnected drafts, reopens, and reviews an original local workflow without model calls', async ({ page, request }, info) => {
  pages.set(request, page);
  info.annotations.push({ type: 'verification', description: 'Real scoped File HTTP, original WorkflowRun, manual text and local recipe. No route mocks, providers, media jobs or required chapter/Director.' });
  const mutations: string[] = [];
  page.on('request', value => { const path = new URL(value.url()).pathname; if (path.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(value.method())) mutations.push(`${value.method()} ${path}`); });
  await page.goto('/'); await page.getByLabel('空白项目名称', { exact: true }).fill('独立创作图合成验收');
  const project = await responseFor(page, '/api/experimental/projects', 'POST', () => page.getByRole('button', { name: '创建空白项目', exact: true }).click());
  expect(typeof project.id).toBe('string'); owned.get(request)!.add(project.id);
  const base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  await page.getByRole('button', { name: '创作图', exact: true }).click();
  await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  await page.getByLabel('创作图标题', { exact: true }).fill('可独立保存的图');
  const empty = await responseFor(page, `${base}/graphs`, 'POST', () => page.getByRole('button', { name: '保存创作图', exact: true }).click()) as StudioGraphRecord;
  expect(empty.definition.nodes).toEqual([]); expect(empty.definition.edges).toEqual([]); expect(empty.version).toBe(1);
  expect((await (await request.get(`${base}/graphs/${empty.id}/runs`)).json()).items).toEqual([]);
  await expect(page.getByText('创作图已保存 · v1。没有自动创建运行。', { exact: true })).toBeVisible();
  await page.reload(); await page.getByRole('button', { name: '创作图', exact: true }).click();
  await page.getByLabel('已保存创作图', { exact: true }).selectOption(empty.id);
  await expect(page.getByLabel('创作图标题', { exact: true })).toHaveValue('可独立保存的图');
  const text = await addNode(page, 'text_input', '文本输入');
  await page.getByLabel('作者输入文本', { exact: true }).fill('合成作者文本。手工节点独立运行，最终结果由作者审核。');
  const sourceButton = page.getByRole('button', { name: `选择节点 文本输入 · ${text}`, exact: true });
  await sourceButton.focus(); await sourceButton.press('ArrowRight');
  await expect(page.getByLabel('节点 X', { exact: true })).toHaveValue('32');
  const draft = await addNode(page, 'draft_prepare', '本地草稿整理');
  const review = await addNode(page, 'human_review', '人工审核');
  await addNode(page, 'director_note', '导演备注');
  await page.getByLabel('可选导演备注', { exact: true }).fill('此备注可以完全移除');
  await page.getByRole('button', { name: '移除当前节点', exact: true }).click();
  const disconnected = await responseFor(page, `${base}/graphs/${empty.id}`, 'PUT', () => page.getByRole('button', { name: '保存创作图', exact: true }).click()) as StudioGraphRecord;
  expect(disconnected.definition.nodes.map(node => node.definition_id)).toEqual(['text_input', 'draft_prepare', 'human_review']);
  expect(disconnected.definition.edges).toEqual([]);
  await expect(page.getByLabel('起始输出端口', { exact: true })).toBeEnabled();
  for (const [source, output, target, input] of [[text, 'text', draft, 'text'], [draft, 'draft', review, 'draft']]) {
    await page.getByLabel('起始输出端口', { exact: true }).selectOption(JSON.stringify([source, output]));
    await page.getByLabel('目标输入端口', { exact: true }).selectOption(JSON.stringify([target, input]));
    await page.getByRole('button', { name: '连接所选端口', exact: true }).click();
  }
  await page.getByRole('button', { name: '放大节点图', exact: true }).click();
  await expect(page.getByLabel('节点图缩放', { exact: true })).toHaveText('120%');
  const connected = await responseFor(page, `${base}/graphs/${empty.id}`, 'PUT', () => page.getByRole('button', { name: '保存创作图', exact: true }).click()) as StudioGraphRecord;
  expect(connected.version).toBe(3); expect(connected.definition.edges).toHaveLength(2); expect(connected.definition.viewport.zoom).toBeCloseTo(1.2);
  await expect(page.getByRole('button', { name: '核对运行范围', exact: true })).toBeEnabled();
  const preflight = await responseFor(page, `${base}/graphs/${empty.id}/preflight`, 'POST', () => page.getByRole('button', { name: '核对运行范围', exact: true }).click());
  expect(preflight).toMatchObject({ executable: true, external_calls: 0, model_called: false, expected_version: 3 });
  await expect(page.getByRole('button', { name: '创建本地运行', exact: true })).toBeDisabled();
  await page.getByLabel('已核对当前图版本、节点范围与本地处理边界', { exact: true }).check();
  const run = await responseFor(page, `${base}/graphs/${empty.id}/runs`, 'POST', () => page.getByRole('button', { name: '创建本地运行', exact: true }).click()) as StudioGraphRun;
  expect(run).toMatchObject({ status: 'QUEUED', model_called: false, external_calls: 0, applied: false });
  const waiting = await responseFor(page, `${base}/graph-runs/${run.id}/execute`, 'POST', () => page.getByRole('button', { name: '执行本地节点', exact: true }).click()) as StudioGraphRun;
  expect(waiting.status).toBe('WAITING_APPROVAL'); expect(waiting.review?.draft.text).toContain('合成作者文本');
  await expect(page.getByRole('region', { name: '节点输出审核', exact: true })).toContainText('合成作者文本');
  await expect(page.getByRole('button', { name: '批准节点输出', exact: true })).toBeDisabled();
  await page.getByLabel('已阅读本次输出并核对当前审核摘要', { exact: true }).check();
  const completed = await responseFor(page, `${base}/graph-runs/${run.id}/approve`, 'POST', () => page.getByRole('button', { name: '批准节点输出', exact: true }).click()) as StudioGraphRun;
  expect(completed).toMatchObject({ status: 'SUCCEEDED', reviewed: true, model_called: false, external_calls: 0, applied: false });
  expect(completed.deadline_at).toBe(run.deadline_at);
  expect(await (await request.get(`/api/novels/${encodeURIComponent(project.id)}/chapters`)).json()).toEqual([]);
  expect(mutations.filter(value => /\/(providers?|models?|media\/tasks|generation|generate|dispatch|director-proposals)(\/|$)/.test(value))).toEqual([]);
  await expect(page.getByRole('tablist', { name: '创作模块', exact: true }).getByRole('tab')).toHaveText(['小说', '图片', '视频', '资产', '声音', '主控', '插件', '工作流']);
  const geometry = await page.evaluate(() => {
    const rect = (selector: string) => { const r = document.querySelector(selector)!.getBoundingClientRect(); return { y: r.y, width: r.width, height: r.height }; };
    return { header: rect('.global-header'), context: rect('.context-bar'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'), status: rect('.status-bar'), pageWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth };
  });
  expect(geometry.header).toMatchObject({ y: 0, height: 56, width: 1440 }); expect(geometry.context).toMatchObject({ y: 56, height: 44, width: 1440 });
  expect(geometry.sidebar.width).toBe(248); expect(geometry.inspector.width).toBe(340); expect(geometry.status).toMatchObject({ y: 868, height: 32, width: 1440 }); expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.viewportWidth);
  const screenshot = info.outputPath('independent-graph-local-review.png'); await page.screenshot({ path: screenshot, fullPage: true }); await info.attach('independent-graph-local-review', { path: screenshot, contentType: 'image/png' });
  await info.attach('independent-graph-original-workflow-receipt', { body: JSON.stringify({ project_id: project.id, graph: connected, preflight, run: completed, mutations, geometry, no_chapters: true }, null, 2), contentType: 'application/json' });
});

for (const profile of ['default-off', 'acceptance-mode']) {
  test(`${profile}: independent graph remains unavailable without its server gate`, async ({ page, request }) => {
    pages.set(request, page);
    await page.goto('/');
    await expect(page.getByRole('button', { name: '创建空白项目', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '创作图', exact: true })).toHaveCount(0);
    const catalog = await request.get('/api/projects/unowned-gate-probe/studio/graphs/catalog');
    expect(catalog.status()).toBe(404);
    expect(await (await request.get('/api/novels')).json()).toEqual([]);
  });
}
