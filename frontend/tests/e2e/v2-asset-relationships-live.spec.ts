import { expect, test, type APIRequestContext, type Page } from '@playwright/test';
import type { StudioAsset, StudioCreatedProject, StudioRelationshipGraph } from '../../src/creative/studioClient';

const ownedProjects = new WeakMap<APIRequestContext, Set<string>>();
const ownedPages = new WeakMap<APIRequestContext, Page>();

test.beforeEach(async ({ request }) => {
  expect(await (await request.get('/api/novels')).json(), 'An isolated server is required; unowned projects must never be removed.').toEqual([]);
  ownedProjects.set(request, new Set());
});
test.afterEach(async ({ request }, info) => {
  const page = ownedPages.get(request);
  if (page && !page.isClosed()) {
    if (info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
    await page.close();
  }
  const owned = ownedProjects.get(request);
  for (const id of owned || []) {
    const response = await request.delete(`/api/novels/${encodeURIComponent(id)}`);
    expect(response.status(), `Delete only this test's confirmed synthetic project ${id}: ${await response.text()}`).toBe(204);
  }
  if (owned) expect(await (await request.get('/api/novels')).json()).toEqual([]);
});

const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAFklEQVR4nGMQSFhAEmIY1TCqYfhqAAALcBAQO3WHHAAAAABJRU5ErkJggg==', 'base64');
async function importImage(page: Page, base: string, filename: string) {
  // A received lineage response alone is not the upload-ready UI state.
  const input = page.getByLabel('选择要上传的资产文件', { exact: true });
  await expect(input).toBeEnabled();
  await expect(page.getByRole('button', { name: '上传资产', exact: true })).toBeEnabled();
  const response = page.waitForResponse(value => new URL(value.url()).pathname.startsWith(`${base}/assets/`) && new URL(value.url()).pathname.endsWith('/lineage') && value.request().method() === 'PUT');
  await input.setInputFiles({ name: filename, mimeType: 'image/png', buffer: png });
  const saved = await response; expect(saved.ok(), await saved.text()).toBe(true);
  const asset = await saved.json() as StudioAsset;
  await expect(page.getByRole('region', { name: '资产检查面板', exact: true })).toContainText(asset.id);
  await expect(input).toBeEnabled();
  await expect(page.getByRole('button', { name: '上传资产', exact: true })).toBeEnabled();
  return asset;
}

test('real File optional asset relationships persist, protect targets and remove explicitly with no chapter prerequisite', async ({ page, request }, info) => {
  info.annotations.push({ type: 'verification', description: 'Real File HTTP and browser, decoded synthetic PNGs, original asset metadata versions. No route mocks or model calls. Only successful synthetic project IDs are cleaned up.' });
  ownedPages.set(request, page);
  let owned: string | undefined;
  const mutations: string[] = [];
  page.on('request', value => { const path = new URL(value.url()).pathname; if (path.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(value.method())) mutations.push(`${value.method()} ${path}`); });
  await page.goto('/'); await page.getByLabel('空白项目名称', { exact: true }).fill('可选关联合成验收');
  const create = page.waitForResponse(value => new URL(value.url()).pathname === '/api/experimental/projects' && value.request().method() === 'POST');
  await page.getByRole('button', { name: '创建空白项目', exact: true }).click();
  const created = await create;
  if (created.status() === 201) { const value = await created.json() as StudioCreatedProject; if (typeof value.id === 'string' && value.id) { owned = value.id; ownedProjects.get(request)!.add(value.id); } }
  expect(created.status()).toBe(201); expect(owned).toBeTruthy();
  const base = `/api/projects/${encodeURIComponent(owned!)}/studio`;
  const overview = await (await request.get(base)).json(); expect(overview.capabilities.media_validator_configured, 'A real media validator is required; do not silently skip this proof.').toBe(true);
  await expect(page.getByRole('button', { name: '上传资产', exact: true })).toBeEnabled();
  const source = await test.step('Import source image and wait for the upload controls to be ready', () => importImage(page, base, 'relationship-source.png'));
  const target = await test.step('Import target image and wait for the upload controls to be ready', () => importImage(page, base, 'relationship-target.png'));
  await page.getByRole('button', { name: '检查资产 relationship-source.png', exact: true }).click();
  await page.getByRole('button', { name: '可选资产关联', exact: true }).click();
  await expect(page.getByText('尚未添加关联。独立导入和导出无需关联。', { exact: true })).toBeVisible();
  await page.getByLabel('关联目标', { exact: true }).selectOption({ label: 'relationship-target.png · v2' });
  await page.getByLabel('关联理由', { exact: true }).fill('手工构图参考，不执行任务');
  await expect(page.getByRole('button', { name: '保存来源声明', exact: true })).toBeDisabled();
  const add = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/assets/${source.id}/relationships` && value.request().method() === 'POST');
  await page.getByRole('button', { name: '保存关联', exact: true }).click();
  const added = await add; expect(added.status()).toBe(201);
  const related = await added.json() as StudioAsset;
  expect(related.version).toBe(3); expect(related.relationships).toHaveLength(1);
  expect(related.relationships![0]).toMatchObject({ type: 'REFERENCES', state: 'CURRENT', expected: { kind: 'ASSET', id: target.id, version: 2, digest: target.sha256 }, reason: '手工构图参考，不执行任务' });
  await expect(page.getByText('关联已保存，原文件和引用内容未改变。', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('region', { name: '资产检查面板', exact: true })).toContainText(source.id);
  await page.getByRole('button', { name: '可选资产关联', exact: true }).click();
  await expect(page.getByText('关联时 v2 · 当前 v2', { exact: true })).toBeVisible();
  await expect(page.getByText('理由：手工构图参考，不执行任务', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '读取项目关联概览', exact: true }).click();
  await expect(page.getByRole('region', { name: '项目关联概览', exact: true })).toContainText('2 个资产 · 1 条关联');
  const graph = await (await request.get(`${base}/relationships`)).json() as StudioRelationshipGraph;
  expect(graph).toMatchObject({ graph_kind: 'ASSET_RELATIONSHIPS', executable: false, knowledge_graph: false, automatic_regeneration: false });
  const blockedDelete = await request.delete(`${base}/assets/${target.id}?expected_version=${target.version}`);
  expect(blockedDelete.ok()).toBe(false); expect(await blockedDelete.text()).toContain('CREATIVE_ASSET_IN_USE');
  expect((await (await request.get(`${base}/assets/${target.id}`)).json()).deleted_at).toBeNull();
  const screenshot = info.outputPath('optional-relationships-persisted.png'); await page.screenshot({ path: screenshot, fullPage: true }); await info.attach('optional-relationships-persisted', { path: screenshot, contentType: 'image/png' });
  await page.getByRole('button', { name: '移除关联 参考', exact: true }).click();
  await expect(page.getByRole('button', { name: '确认移除', exact: true })).toBeDisabled();
  await page.getByLabel('确认移除此关联', { exact: true }).check();
  const remove = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/assets/${source.id}/relationships/${related.relationships![0].id}` && value.request().method() === 'DELETE');
  await page.getByRole('button', { name: '确认移除', exact: true }).click();
  const removed = await remove; expect(removed.ok(), await removed.text()).toBe(true);
  expect(await removed.json()).toMatchObject({ id: source.id, version: 4, sha256: source.sha256, relationships: [] });
  expect((await (await request.get(`${base}/assets`)).json()).items).toHaveLength(2);
  expect(await (await request.get(`/api/novels/${encodeURIComponent(owned!)}/chapters`)).json()).toEqual([]);
  const modelWrites = mutations.filter(path => /\/(models?|providers?|generate|generation|execute|dispatch|director-proposals)(\/|$)|\/media\/tasks(\/|$)/.test(path)); expect(modelWrites).toEqual([]);
  await info.attach('optional-relationships-receipt', { body: JSON.stringify({ project_id: owned, source_id: source.id, target_id: target.id, source_versions: [2, 3, 4], target_version: 2, no_chapters: true, no_model_mutations: true, mutations, graph }, null, 2), contentType: 'application/json' });
});
