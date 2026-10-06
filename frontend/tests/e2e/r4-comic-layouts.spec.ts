import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
const owned = new WeakMap<Page, string[]>(); const quiet = new WeakMap<Page, () => Promise<void>>();
async function openComic(page: Page) {
  if (!(await page.getByRole('navigation', { name: '实验功能' }).isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /功能导航/ }).first().click(); const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  }
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '漫画与 Webtoon', exact: true }).click();
}
function storedZipEntries(data: Buffer) {
  const entries = new Map<string, Buffer>(); let cursor = 0;
  while (data.readUInt32LE(cursor) === 0x04034b50) {
    expect(data.readUInt16LE(cursor + 8)).toBe(0); // deliberately deterministic stored ZIP, no executable container
    const length = data.readUInt32LE(cursor + 18); const nameLength = data.readUInt16LE(cursor + 26); const extraLength = data.readUInt16LE(cursor + 28);
    const name = data.subarray(cursor + 30, cursor + 30 + nameLength).toString('utf8'); const start = cursor + 30 + nameLength + extraLength;
    expect(/^(segment-\d{3}\.png|manifest\.json|OFL\.txt)$/.test(name)).toBe(true); entries.set(name, data.subarray(start, start + length)); cursor = start + length;
  }
  expect(data.readUInt32LE(cursor)).toBe(0x02014b50); return entries;
}
test.beforeEach(({ page }) => {
  owned.set(page, []); quiet.set(page, createPageQuiescer(page)); page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  test.info().annotations.push({ type: 'verification', description: 'Actual React + File API + pinned Pillow/OFL CJK raster. Labeled synthetic test image, no model or artwork quality claim. Local Chromium NOT_RUN (verified EPERM); this authored journey runs in hosted Linux gate.' });
});
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('comic-failure.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!(); for (const nid of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());
});

test('B06: missing art, original image review, CJK bubbles, undo, raster review and byte-identical segmented export', async ({ page }, info) => {
  const generation: string[] = []; page.on('request', request => { if (request.method() === 'POST' && /generate|execute|dispatch/.test(request.url())) generation.push(request.url()); });
  await page.goto('/'); await page.getByPlaceholder('小说名称').fill(`Synthetic comic ${test.info().testId}`);
  const creating = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST'); await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await (await creating).json(); owned.get(page)!.push(novel.id); const base = `${API}/novels/${novel.id}`;
  expect((await page.request.post(`${base}/chapters`, { data: { title: '合成测试章节', content: '小岚看着合成测试的山景。' } })).status()).toBe(201);
  let source = await (await page.request.post(`${base}/screenplays`, { data: { title: '合成漫画镜头' } })).json();
  source = await (await page.request.post(`${base}/screenplays/${source.id}/approve`, { data: { expected_version: source.edit_version } })).json();
  source = await (await page.request.post(`${base}/screenplays/${source.id}/shots`, { data: { expected_version: source.edit_version } })).json();
  const imageBytes = await readFile('tests/e2e/fixtures/r5-comic-SYNTHETIC-TEST-ASSET.png');
  const asset = await (await page.request.post(`${base}/assets`, { data: { novel_id: novel.id, filename: 'SYNTHETIC-TEST-ASSET.png', content_base64: imageBytes.toString('base64'), media_type: 'image/png' } })).json();
  const capabilities = await (await page.request.get(`${base}/experimental/comic-layouts/catalog`)).json(); expect(capabilities.renderer.available).toBe(true); expect(capabilities.font.available).toBe(true);
  await openComic(page); const comic = page.getByRole('region', { name: '漫画与 Webtoon 排版', exact: true });
  await comic.getByLabel('漫画来源剧本').selectOption(source.id); await comic.getByLabel('布局预设').selectOption('WEBTOON');
  const savingMissing = page.waitForResponse(response => response.url().endsWith('/comic-layouts/records') && response.request().method() === 'POST');
  await comic.getByRole('button', { name: '保存漫画布局草稿' }).click(); let row = await (await savingMissing).json(); expect(row.status).toBe('DRAFT');
  await comic.getByRole('button', { name: '预检并渲染当前布局' }).click(); await expect(comic).toContainText('缺少已批准图片'); await expect(comic.getByRole('button', { name: '下载已批准漫画分段' })).toBeDisabled();
  await comic.getByLabel('待核对的原图片').selectOption(asset.id); await comic.getByRole('button', { name: '查看原图片像素' }).click();
  const assetReview = comic.getByRole('checkbox', { name: '已查看此用户图片，并确认可用于漫画排版' }); await expect(assetReview).toBeEnabled(); await assetReview.check();
  await comic.getByRole('button', { name: '批准此用户图片' }).click(); await expect(comic).toContainText('已记录原图库图片的人工批准');
  await comic.getByLabel('格框 1 已批准图片').selectOption(asset.id); await comic.getByRole('button', { name: '添加格框 1 气泡', exact: true }).click();
  await comic.getByLabel('格框 1 气泡 1 文字', { exact: true }).fill('中文对白：这是合成测试素材，不代表最终美术。');
  await comic.getByLabel('格框 1 气泡 1 横坐标', { exact: true }).fill('56'); await comic.getByRole('button', { name: '撤销本地排版' }).click();
  await expect(comic.getByLabel('格框 1 气泡 1 横坐标', { exact: true })).toHaveValue('40');
  const saving = page.waitForResponse(response => response.url().endsWith(`/comic-layouts/records/${row.id}`) && response.request().method() === 'PUT');
  await comic.getByRole('button', { name: '保存漫画布局草稿' }).click(); row = await (await saving).json();
  await comic.getByRole('button', { name: '预检并渲染当前布局' }).click(); await expect(comic.getByRole('img', { name: '漫画分段 1，待审草稿' })).toBeVisible();
  for (const screenWidth of ['320', '360', '768']) { await comic.getByLabel('漫画预览屏宽').selectOption(screenWidth); await expect(comic.getByLabel('实际漫画分段像素')).toHaveCSS('width', `${screenWidth}px`); }
  await expect(comic.getByRole('button', { name: '批准当前漫画布局' })).toBeDisabled();
  await comic.getByRole('checkbox', { name: '已核对图片、阅读顺序、所有裁切与分段警告，并批准此布局版本' }).check();
  const approving = page.waitForResponse(response => response.url().endsWith(`/comic-layouts/records/${row.id}/approve`)); await comic.getByRole('button', { name: '批准当前漫画布局' }).click(); row = await (await approving).json(); expect(row.status).toBe('APPROVED');
  await comic.getByRole('button', { name: '预检并渲染当前布局' }).click(); await expect(comic.getByRole('button', { name: '下载已批准漫画分段' })).toBeEnabled();
  const downloading = page.waitForEvent('download'); await comic.getByRole('button', { name: '下载已批准漫画分段' }).click(); const download = await downloading;
  expect(download.suggestedFilename()).toBe('comic-segments.zip'); const zipPath = info.outputPath('comic-segments.zip'); await download.saveAs(zipPath);
  const entries = storedZipEntries(await readFile(zipPath)); const manifest = JSON.parse(entries.get('manifest.json')!.toString()); expect(manifest.segments).toHaveLength(2); expect(entries.get('OFL.txt')!.toString()).toContain('SIL OPEN FONT LICENSE');
  for (const segment of manifest.segments) {
    const preview = await page.request.get(`${base}/experimental/comic-layouts/records/${row.id}/segments/${segment.index}?expected_version=${row.version}`);
    expect(preview.headers()['cache-control']).toBe('no-store'); const actual = await preview.body(); expect(actual.equals(entries.get(segment.filename)!)).toBe(true);
    expect(createHash('sha256').update(actual).digest('hex')).toBe(segment.sha256); expect(actual.subarray(1, 4).toString()).toBe('PNG');
  }
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) { await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true); await page.screenshot({ path: info.outputPath(`comic-${width}.png`) }); }
  const original = await (await page.request.get(`${base}/screenplays`)).json(); expect(original[0].edit_version).toBe(source.edit_version); expect(generation).toEqual([]);
  // Ordinary editing revokes approval and long dialogue is a real renderer blocker.
  await comic.getByLabel('格框 1 气泡 1 文字', { exact: true }).fill('超出气泡的中文'.repeat(100));
  await comic.getByRole('button', { name: '保存漫画布局草稿' }).click(); await comic.getByRole('button', { name: '预检并渲染当前布局' }).click(); await expect(comic).toContainText('文字超出气泡');
  await expect(comic.getByRole('button', { name: '下载已批准漫画分段' })).toBeDisabled();
});
