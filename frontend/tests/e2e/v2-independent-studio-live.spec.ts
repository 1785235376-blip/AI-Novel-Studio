import { createHash } from 'node:crypto';
import { execFile } from 'node:child_process';
import fs from 'node:fs/promises';
import path from 'node:path';
import { promisify } from 'node:util';
import { expect, test, type APIRequestContext, type APIResponse, type Page, type TestInfo } from '@playwright/test';
import type { StudioAsset, StudioCreatedProject, StudioOverview } from '../../src/creative/studioClient';
import { verifyInstalledMediaTools } from '../../../scripts/v2_media_prerequisites.mjs';

// These tests must run against their own initially empty File server. Inventory
// is never treated as ownership: only successful create responses are cleaned.
const ownedIDs = new WeakMap<APIRequestContext, Set<string>>();
const ownedPages = new WeakMap<APIRequestContext, Page>();
const filename = 'independent-synthetic-image.png';
// A complete, CRC-correct 16 x 16 PNG used by the real decoder, not a MIME stub.
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAAAFklEQVR4nGMQSFhAEmIY1TCqYfhqAAALcBAQO3WHHAAAAABJRU5ErkJggg==', 'base64');
const digest = (bytes: Buffer) => createHash('sha256').update(bytes).digest('hex');
const studio = (projectId: string) => `/api/projects/${encodeURIComponent(projectId)}/studio`;
const ownedPath = (projectId: string) => `/api/novels/${encodeURIComponent(projectId)}`;
const executeFixtureTool = promisify(execFile);

async function makeSyntheticVideo(info: TestInfo): Promise<Buffer> {
  const destination = info.outputPath('fixture', 'independent-synthetic-video.mp4');
  await fs.mkdir(path.dirname(destination), { recursive: true });
  const bounded = { timeout: 20000, maxBuffer: 64 * 1024, killSignal: 'SIGTERM' as const };
  try {
    // Only this new VIDEO fixture probes installed decoders. The protected CI
    // job and legacy browser journeys do not acquire provisioning side effects.
    const tools = await verifyInstalledMediaTools();
    await info.attach('independent-video-installed-tools', { body: JSON.stringify(tools, null, 2), contentType: 'application/json' });
    await executeFixtureTool('ffprobe', ['-version'], bounded);
    await executeFixtureTool('ffmpeg', ['-nostdin', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=32x32:r=5:d=0.4', '-an', '-c:v', 'libx264', '-threads', '1', '-filter_threads', '1', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', destination], bounded);
    const probe = await executeFixtureTool('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=codec_name,width,height:format=duration', '-of', 'json', destination], bounded);
    const metadata = JSON.parse(probe.stdout);
    expect(metadata.streams[0]).toMatchObject({ codec_name: 'h264', width: 32, height: 32 });
    expect(Number(metadata.format.duration)).toBeGreaterThan(0); expect(Number(metadata.format.duration)).toBeLessThan(1);
  } catch (cause) {
    if (cause && typeof cause === 'object' && 'receipt' in cause) {
      await info.attach('independent-video-prerequisite-failure', { body: JSON.stringify(cause.receipt, null, 2), contentType: 'application/json' });
    }
    throw new Error('Real VIDEO acceptance requires installed FFmpeg/ffprobe with libx264 and a decodable 32×32, sub-second H.264/yuv420p MP4. The prerequisite failed; no playback or MIME stub is substituted.', { cause });
  }
  const bytes = await fs.readFile(destination);
  expect(bytes.length).toBeGreaterThan(0); expect(bytes.length).toBeLessThan(64 * 1024);
  await info.attach('independent-synthetic-video-fixture', { path: destination, contentType: 'video/mp4' });
  return bytes;
}

async function read<T>(request: APIRequestContext, url: string): Promise<T> {
  const response = await request.get(url);
  expect(response.ok(), `${url}: HTTP ${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json() as Promise<T>;
}
async function rememberCreated(request: APIRequestContext, response: Pick<APIResponse, 'status' | 'json'>): Promise<StudioCreatedProject | undefined> {
  if (response.status() !== 201) return undefined;
  const value = await response.json() as StudioCreatedProject;
  expect(typeof value.id, 'A successful project create must return its exact canonical ID.').toBe('string');
  expect(value.id.length).toBeGreaterThan(0);
  expect(ownedIDs.has(request), 'Fixture ownership must exist before any project is created.').toBe(true);
  ownedIDs.get(request)!.add(value.id);
  return value;
}
async function capture(page: Page, info: TestInfo, name: string) {
  const path = info.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await info.attach(name, { path, contentType: 'image/png' });
}

test.beforeEach(async ({ request, page }) => {
  ownedIDs.set(request, new Set());
  ownedPages.set(request, page);
  expect(await read(request, '/api/novels'), 'Independent studio acceptance requires an empty isolated server; unowned inventory must never be removed.').toEqual([]);
});
test.afterEach(async ({ request }, info) => {
  const page = ownedPages.get(request);
  if (page && !page.isClosed()) {
    if (info.status !== info.expectedStatus) await capture(page, info, 'independent-studio-failure-before-cleanup').catch(() => {});
    await page.close();
  }
  for (const id of ownedIDs.get(request) || []) {
    const response = await request.delete(ownedPath(id));
    expect(response.status(), `Delete only confirmed synthetic project ${id}: ${await response.text()}`).toBe(204);
    expect(await response.text()).toBe('');
  }
  expect(await read(request, '/api/novels'), 'Only owned fixtures were deleted; unexpected inventory is preserved and reported.').toEqual([]);
});

test('real File independent studio imports, persists, reopens and exports an image with no chapters or model mutation', async ({ page, request }, info) => {
  info.annotations.push({ type: 'verification', description: 'Real File server, HTTP, Vite and Chromium; real decoded synthetic PNG bytes. No app response mocks, image model, GPU, paid provider or cloud execution.' });
  const pageErrors: string[] = [], mutations: { method: string; path: string }[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('request', incoming => {
    const path = new URL(incoming.url()).pathname;
    if (path.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(incoming.method())) mutations.push({ method: incoming.method(), path });
  });
  await page.goto('/');
  await page.getByLabel('空白项目名称', { exact: true }).fill('独立素材浏览器合成验收');
  const creating = page.waitForResponse(response => new URL(response.url()).pathname === '/api/experimental/projects' && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建空白项目', exact: true }).click();
  const createdResponse = await creating;
  // Record owned IDs before any later business assertion can fail.
  const project = await rememberCreated(request, createdResponse);
  expect(createdResponse.status()).toBe(201);
  expect(project).toMatchObject({ studio_ready: true, requires_scope_selection: false });
  const projectId = project!.id, base = studio(projectId);
  await expect(page.getByText('无需小说、章节或模型，导入素材即可保存和导出。', { exact: true })).toBeVisible();
  await expect(page.getByRole('tab', { name: '图片', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('navigation', { name: '当前创作范围', exact: true }).getByText(`项目：${project!.title}`, { exact: true })).toBeVisible();
  await expect(page.locator('.ProseMirror')).toHaveCount(0);
  await expect(page.getByRole('button', { name: '上传资产', exact: true })).toBeEnabled();
  const overview = await read<StudioOverview>(request, base);
  expect(overview.project).toEqual({ id: projectId, title: project!.title, entry_kind: 'NEUTRAL_STUDIO' });
  expect(overview.preferences).toMatchObject({ intents: [], preset: 'BLANK', custom_intent: '' });
  expect(overview.capabilities).toMatchObject({ can_mutate: true, model_required: false, chapter_required: false, intent_is_permission: false });
  expect(overview.capabilities.media_validator_configured, 'Real PNG import proof requires the configured media validator; this is never silently skipped.').toBe(true);
  expect(await read(request, `${ownedPath(projectId)}/chapters`)).toEqual([]);

  const importing = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/assets` && response.request().method() === 'POST');
  const declaring = page.waitForResponse(response => new URL(response.url()).pathname.startsWith(`${base}/assets/`) && new URL(response.url()).pathname.endsWith('/lineage') && response.request().method() === 'PUT');
  await page.getByLabel('选择要上传的资产文件', { exact: true }).setInputFiles({ name: filename, mimeType: 'image/png', buffer: png });
  const importedResponse = await importing;
  expect(importedResponse.status()).toBe(201);
  const imported = await importedResponse.json() as StudioAsset;
  expect(imported).toMatchObject({ novel_id: projectId, filename, kind: 'image', media_type: 'image/png', size: png.length, sha256: digest(png), version: 1 });
  const declaredResponse = await declaring;
  expect(declaredResponse.ok(), await declaredResponse.text()).toBeTruthy();
  const declared = await declaredResponse.json() as StudioAsset;
  expect(declared.id).toBe(imported.id);
  expect(declared.version).toBe(2);
  expect(declared.provenance).toMatchObject({ origin: 'EXTERNAL_IMPORT', integrity: 'VERIFIED', license: { label: 'UNSPECIFIED' }, license_verification: 'AUTHOR_DECLARATION_NOT_LEGAL_VERIFICATION', parents: [], sources: [], stale: false });
  await expect(page.getByText('资产与外部导入来源已保存。', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: `检查资产 ${filename}`, exact: true })).toBeVisible();
  const inspector = page.getByRole('region', { name: '资产检查面板', exact: true });
  await expect(inspector).toContainText(digest(png));
  await expect(inspector.getByRole('img', { name: filename, exact: true })).toBeVisible();
  await expect(page.getByRole('region', { name: '独立资产来源', exact: true })).toContainText('EXTERNAL_IMPORT');
  expect((await read<{ items: StudioAsset[] }>(request, `${base}/assets`)).items).toEqual([declared]);
  await capture(page, info, 'independent-image-imported-with-lineage');

  // Refresh reads the original server-owned project and asset; browser hints
  // are neither fixtures nor substitutes for persistence.
  await page.reload();
  await expect(page.getByText('无需小说、章节或模型，导入素材即可保存和导出。', { exact: true })).toBeVisible();
  await expect(page.getByRole('tab', { name: '图片', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(inspector).toContainText(imported.id);
  await expect(page.getByRole('region', { name: '独立资产来源', exact: true })).toContainText('版本 v2');
  expect(await read<StudioAsset>(request, `${base}/assets/${encodeURIComponent(imported.id)}`)).toEqual(declared);

  await page.getByRole('button', { name: '返回项目列表', exact: true }).click();
  await expect(page.getByLabel('空白项目名称', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: project!.title, exact: true }).click();
  await expect(page.getByRole('navigation', { name: '当前创作范围', exact: true }).getByText(`项目：${project!.title}`, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: `检查资产 ${filename}`, exact: true })).toBeVisible();
  await page.getByRole('button', { name: `检查资产 ${filename}`, exact: true }).click();
  await expect(inspector).toContainText(digest(png));

  const downloadEvent = page.waitForEvent('download');
  await inspector.getByRole('button', { name: '下载原始文件', exact: true }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe(filename);
  const destination = info.outputPath('independent-original-export.png');
  await download.saveAs(destination);
  const bytes = await fs.readFile(destination);
  expect(bytes.equals(png)).toBe(true);
  expect(digest(bytes)).toBe(declared.sha256);
  await info.attach('independent-original-export', { path: destination, contentType: 'image/png' });

  const geometryReceipts = [];
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080], [2560, 1440]]) {
    await page.setViewportSize({ width, height });
    await page.evaluate(() => document.fonts.ready);
    await expect(page.getByRole('navigation', { name: '当前创作范围', exact: true })).toBeVisible();
    await expect(page.getByRole('tablist', { name: '创作模块', exact: true }).getByRole('tab')).toHaveText(['小说', '图片', '视频', '资产', '声音', '主控', '插件', '工作流']);
    const geometry = await page.evaluate(() => {
      const rect = (selector: string) => {
        const value = document.querySelector(selector)!.getBoundingClientRect();
        return { x: value.x, y: value.y, width: value.width, height: value.height };
      };
      return { header: rect('.global-header'), context: rect('.context-bar'), body: rect('.workspace-body'),
        sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'), status: rect('.status-bar'),
        switcher: rect('.module-switcher'), pageWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth };
    });
    expect(geometry.header).toMatchObject({ y: 0, height: 56, width });
    expect(geometry.context).toMatchObject({ y: 56, height: 44, width });
    expect(geometry.body).toMatchObject({ y: 100, height: height - 132, width });
    expect(geometry.sidebar.width).toBe(248);
    expect(geometry.inspector.width).toBe(340);
    expect(geometry.status).toMatchObject({ y: height - 32, height: 32, width });
    expect(geometry.switcher.y).toBe(0);
    expect(geometry.pageWidth).toBeLessThanOrEqual(geometry.viewportWidth);
    geometryReceipts.push({ viewport: { width, height }, geometry });
    await capture(page, info, `independent-studio-${width}x${height}`);
  }
  expect(await read(request, `${ownedPath(projectId)}/chapters`)).toEqual([]);
  expect((await read<{ items: unknown[] }>(request, `${ownedPath(projectId)}/experimental/creative/documents`)).items).toEqual([]);
  const storage = await read<{ assets: { count: number; bytes: number }; trash: { count: number }; physical_cleanup_available: boolean }>(request, `${base}/storage`);
  expect(storage).toMatchObject({ assets: { count: 1, bytes: png.length }, trash: { count: 0 }, physical_cleanup_available: false });
  expect(mutations.filter(row => row.path === '/api/experimental/projects')).toHaveLength(1);
  expect(mutations.filter(row => row.path === `${base}/assets`)).toHaveLength(1);
  expect(mutations.filter(row => row.path.endsWith('/lineage'))).toHaveLength(1);
  const modelMutations = mutations.filter(row => /\/(models?|model-center|model-broker|providers?|generation|generate|execute|dispatch|director-proposals)(\/|$)|\/media\/tasks(\/|$)/.test(row.path));
  expect(modelMutations).toEqual([]);
  expect(pageErrors).toEqual([]);
  await info.attach('independent-studio-real-file-receipt', { body: JSON.stringify({ project_id: projectId, asset_id: imported.id, asset_version: declared.version, entry_kind: overview.project.entry_kind, no_chapters: true, no_creative_documents: true, no_model_mutations: true, download_sha256: digest(bytes), imported_sha256: digest(png), mutations, geometry: geometryReceipts }, null, 2), contentType: 'application/json' });
});

test('real File independent VIDEO imports, decodes, reopens and exports original bytes without chapters or director', async ({ page, request }, info) => {
  info.annotations.push({ type: 'verification', description: 'Real File server and HTTP, Vite and Chromium; a real libx264/yuv420p MP4 produced by installed FFmpeg with bounded execution. Positive browser video metadata is required. No provider, GPU, chapter, director, route mocks or playback stubs.' });
  const videoBytes = await makeSyntheticVideo(info), videoFilename = 'independent-synthetic-video.mp4';
  const pageErrors: string[] = [], mutations: { method: string; path: string }[] = [];
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('request', incoming => { const path = new URL(incoming.url()).pathname; if (path.startsWith('/api/') && !['GET', 'HEAD', 'OPTIONS'].includes(incoming.method())) mutations.push({ method: incoming.method(), path }); });
  await page.goto('/');
  await page.getByLabel('空白项目名称', { exact: true }).fill('独立视频浏览器合成验收');
  const creating = page.waitForResponse(response => new URL(response.url()).pathname === '/api/experimental/projects' && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建空白项目', exact: true }).click();
  const createdResponse = await creating, project = await rememberCreated(request, createdResponse);
  expect(createdResponse.status()).toBe(201); expect(project).toMatchObject({ studio_ready: true, requires_scope_selection: false });
  const projectId = project!.id, base = studio(projectId);
  await expect(page.getByText('无需小说、章节或模型，导入素材即可保存和导出。', { exact: true })).toBeVisible();
  const overview = await read<StudioOverview>(request, base);
  expect(overview.capabilities.media_validator_configured, 'Real video import requires configured FFmpeg/ffprobe; unavailable tools are a failed prerequisite.').toBe(true);
  expect(overview.capabilities).toMatchObject({ model_required: false, chapter_required: false });
  await page.getByRole('tab', { name: '视频', exact: true }).click();
  await expect(page.getByRole('tab', { name: '视频', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('button', { name: '上传资产', exact: true })).toBeEnabled();
  const importing = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/assets` && response.request().method() === 'POST');
  const declaring = page.waitForResponse(response => new URL(response.url()).pathname.startsWith(`${base}/assets/`) && new URL(response.url()).pathname.endsWith('/lineage') && response.request().method() === 'PUT');
  await page.getByLabel('选择要上传的资产文件', { exact: true }).setInputFiles({ name: videoFilename, mimeType: 'video/mp4', buffer: videoBytes });
  const importedResponse = await importing; expect(importedResponse.status()).toBe(201);
  const imported = await importedResponse.json() as StudioAsset;
  expect(imported).toMatchObject({ novel_id: projectId, filename: videoFilename, kind: 'video', media_type: 'video/mp4', size: videoBytes.length, sha256: digest(videoBytes), version: 1 });
  const declaredResponse = await declaring; expect(declaredResponse.ok(), await declaredResponse.text()).toBe(true);
  const declared = await declaredResponse.json() as StudioAsset;
  expect(declared).toMatchObject({ id: imported.id, version: 2, provenance: { origin: 'EXTERNAL_IMPORT', integrity: 'VERIFIED', parents: [], sources: [] } });
  const inspector = page.getByRole('region', { name: '资产检查面板', exact: true });
  const player = inspector.getByLabel(`${videoFilename} 视频预览`, { exact: true });
  await expect(player).toBeVisible();
  await expect.poll(() => player.evaluate(node => { const media = node as HTMLVideoElement; return { loaded: media.readyState >= 1, width: media.videoWidth, height: media.videoHeight, duration: media.duration > 0 && media.duration < 1, error: media.error?.code ?? null }; }), { message: 'Chromium must load actual positive video metadata, dimensions and duration without a decode error.' }).toEqual({ loaded: true, width: 32, height: 32, duration: true, error: null });
  await capture(page, info, 'independent-video-imported-with-real-metadata');
  await page.reload();
  await expect(page.getByRole('tab', { name: '视频', exact: true })).toHaveAttribute('aria-selected', 'true');
  await expect(inspector).toContainText(imported.id);
  await expect(player).toBeVisible(); await expect.poll(() => player.evaluate(node => (node as HTMLVideoElement).videoWidth)).toBe(32);
  expect(await read<StudioAsset>(request, `${base}/assets/${encodeURIComponent(imported.id)}`)).toEqual(declared);
  await page.getByRole('button', { name: '返回项目列表', exact: true }).click();
  await expect(page.getByLabel('空白项目名称', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: project!.title, exact: true }).click();
  await expect(page.getByRole('tab', { name: '视频', exact: true })).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('button', { name: `检查资产 ${videoFilename}`, exact: true }).click();
  await expect(inspector).toContainText(imported.id);
  const downloadEvent = page.waitForEvent('download'); await inspector.getByRole('button', { name: '下载原始文件', exact: true }).click();
  const download = await downloadEvent; expect(download.suggestedFilename()).toBe(videoFilename);
  const exportedPath = info.outputPath('independent-original-export.mp4'); await download.saveAs(exportedPath);
  const exportedBytes = await fs.readFile(exportedPath); expect(exportedBytes.equals(videoBytes)).toBe(true); expect(digest(exportedBytes)).toBe(imported.sha256);
  await info.attach('independent-original-video-export', { path: exportedPath, contentType: 'video/mp4' });
  expect(await read(request, `${ownedPath(projectId)}/chapters`)).toEqual([]);
  expect((await read<{ items: unknown[] }>(request, `${ownedPath(projectId)}/experimental/creative/documents`)).items).toEqual([]);
  expect(mutations.filter(row => row.path === `${base}/assets`)).toHaveLength(1); expect(mutations.filter(row => row.path.endsWith('/lineage'))).toHaveLength(1);
  expect(mutations.filter(row => /\/(models?|model-center|model-broker|providers?|generation|generate|execute|dispatch|director-proposals)(\/|$)|\/media\/tasks(\/|$)/.test(row.path))).toEqual([]);
  expect(pageErrors).toEqual([]);
  await capture(page, info, 'independent-video-reopened-original-export');
  await info.attach('independent-video-real-file-receipt', { body: JSON.stringify({ project_id: projectId, asset_id: imported.id, version: declared.version, module: 'VIDEO', decoder_metadata: { width: 32, height: 32, duration_positive_under_one_second: true }, no_chapters: true, no_creative_documents: true, no_model_mutations: true, imported_sha256: digest(videoBytes), exported_sha256: digest(exportedBytes), mutations }, null, 2), contentType: 'application/json' });
});

async function expectNeutralEntryDisabled(page: Page, request: APIRequestContext, info: TestInfo, mode: string) {
  await page.goto('/');
  await expect(page.getByPlaceholder('小说名称', { exact: true })).toBeVisible();
  await expect(page.getByLabel('空白项目名称', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '创建空白项目', exact: true })).toHaveCount(0);
  const response = await request.post('/api/experimental/projects', { data: { title: 'Blocked neutral synthetic fixture' } });
  await rememberCreated(request, response);
  expect(response.status()).toBe(404);
  expect(await read(request, '/api/novels')).toEqual([]);
  const flags = await read<{ runtime_features: Record<string, boolean>; surface_features: Record<string, boolean> }>(request, '/api/experimental/features');
  expect(flags.runtime_features['experimental.narrative_production_v2']).toBe(false);
  expect(flags.surface_features['experimental.narrative_production_v2']).toBe(false);
  await capture(page, info, `independent-studio-${mode}-hidden`);
}

test('default-off independent studio entry is absent and neutral project writes are rejected', async ({ page, request }, info) => {
  await expectNeutralEntryDisabled(page, request, info, 'default-off');
});

test('acceptance-mode independent studio stays absent despite an enabled narrative feature setting', async ({ page, request }, info) => {
  info.annotations.push({ type: 'verification', description: 'Dedicated real File server configured with narrative_production_v2 enabled and V1_ACCEPTANCE_MODE=true. The acceptance override must hide the entry and deny neutral project writes.' });
  await expectNeutralEntryDisabled(page, request, info, 'acceptance-mode');
});
