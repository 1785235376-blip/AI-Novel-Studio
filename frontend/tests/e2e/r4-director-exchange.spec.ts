import { readFile } from 'node:fs/promises';
import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
const owned = new WeakMap<Page, string[]>();
const quiet = new WeakMap<Page, () => Promise<void>>();
async function openPanel(page: Page, name: string) {
  if (!(await page.getByRole('navigation', { name: '实验功能' }).isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click();
    await page.keyboard.press('Escape');
  }
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name, exact: true }).click();
}
test.beforeEach(({ page }) => {
  owned.set(page, []); quiet.set(page, createPageQuiescer(page));
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  test.info().annotations.push({ type: 'verification', description: 'Real File API, React and pinned official OTIO native parser; synthetic project/media references. No generation or target NLE. Authored browser journey; local browser NOT_RUN due verified Chromium EPERM.' });
});
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('director-exchange-failure.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!();
  for (const nid of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(nid)}`)).status());
});

test('J14 and A08: draft, original comparison, original approval, actual OTIO download and import round trip', async ({ page }, info) => {
  const dispatched: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /generate|execute|dispatch/.test(request.url())) dispatched.push(request.url()); });
  await page.goto('/');
  await page.getByPlaceholder('小说名称').fill(`Synthetic camera ${test.info().testId}`);
  const creating = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await (await creating).json(); owned.get(page)!.push(novel.id);
  const chapter = await page.request.post(`${API}/novels/${novel.id}/chapters`, { data: { title: '合成港口', content: '小岚站在码头，观察远方的合成灯塔。' } }); expect(chapter.status()).toBe(201);
  let screenplay = await (await page.request.post(`${API}/novels/${novel.id}/screenplays`, { data: { title: '合成港口镜头' } })).json();
  screenplay = await (await page.request.post(`${API}/novels/${novel.id}/screenplays/${screenplay.id}/approve`, { data: { expected_version: screenplay.edit_version } })).json();
  screenplay = await (await page.request.post(`${API}/novels/${novel.id}/screenplays/${screenplay.id}/shots`, { data: { expected_version: screenplay.edit_version } })).json();
  expect(screenplay.shots).toHaveLength(1);
  await openPanel(page, '镜头导演');
  const director = page.getByRole('region', { name: '镜头导演与空间检查', exact: true });
  await director.getByLabel('导演方案来源剧本').selectOption(screenplay.id);
  await director.getByLabel('候选镜头方案名称').fill('合成港口近景');
  await director.getByLabel('镜头 1 景别', { exact: true }).selectOption('CLOSE');
  await director.getByLabel('镜头 1 场景目的', { exact: true }).fill('强调等待与空间距离');
  const saving = page.waitForResponse(response => response.url().endsWith('/director/plans') && response.request().method() === 'POST');
  await director.getByRole('button', { name: '保存候选镜头草稿', exact: true }).click();
  const plan = await (await saving).json(); expect(plan.status).toBe('DRAFT');
  const before = await (await page.request.get(`${API}/novels/${novel.id}/screenplays`)).json(); expect(before[0].edit_version).toBe(screenplay.edit_version);
  await expect(director.getByText('INSUFFICIENT_EVIDENCE', { exact: true })).toBeVisible();
  await director.getByRole('checkbox', { name: '对比方案 合成港口近景', exact: true }).check();
  await director.getByRole('button', { name: '读取原镜头与候选对比', exact: true }).click();
  const apply = director.getByRole('button', { name: '采用方案 合成港口近景 为镜头草稿', exact: true }); await expect(apply).toBeDisabled();
  await director.getByRole('checkbox', { name: '已核对原镜头、候选字段与旧产物失效影响', exact: true }).check();
  const applying = page.waitForResponse(response => response.url().endsWith(`/director/plans/${plan.id}/apply`)); await apply.click();
  const applied = await (await applying).json(); expect(applied.shot_status).toBe('DRAFT'); expect(applied.edit_version).toBe(screenplay.edit_version + 1);
  screenplay = await (await page.request.post(`${API}/novels/${novel.id}/screenplays/${screenplay.id}/shots/approve`, { data: { expected_version: applied.edit_version } })).json(); expect(screenplay.shot_status).toBe('APPROVED');
  await openPanel(page, 'OTIO 剪辑交换');
  const exchange = page.getByRole('region', { name: 'OTIO 剪辑交换', exact: true });
  await exchange.getByLabel('OTIO 来源剧本').selectOption(screenplay.id);
  await exchange.getByLabel('交换时间基准帧率').selectOption('24000/1001');
  const capturing = page.waitForResponse(response => response.url().endsWith('/timeline-exchange/from-screenplay')); await exchange.getByRole('button', { name: '创建镜头 OTIO 交换副本', exact: true }).click();
  const record = await (await capturing).json(); expect(record.summary.tracks[0].duration_seconds).toEqual({ numerator: 5, denominator: 1 });
  const card = exchange.getByRole('article', { name: `OTIO 交换记录 ${record.id}`, exact: true });
  await expect(card).toContainText('缺少媒体引用'); await expect(card.getByRole('button', { name: '下载新的 OTIO 文件' })).toBeDisabled();
  await card.getByRole('checkbox').check(); const downloading = page.waitForEvent('download'); await card.getByRole('button', { name: '下载新的 OTIO 文件' }).click();
  const download = await downloading; expect(download.suggestedFilename()).toMatch(/^timeline-.*\.otio$/);
  const output = info.outputPath(download.suggestedFilename()); await download.saveAs(output); const native = JSON.parse(await readFile(output, 'utf8')); expect(native.OTIO_SCHEMA).toMatch(/^Timeline\./);
  await exchange.getByLabel('选择本地 OTIO 文件').setInputFiles(output);
  const importing = page.waitForResponse(response => response.url().endsWith('/timeline-exchange/import')); await exchange.getByRole('button', { name: '检查并保存 OTIO 交换副本', exact: true }).click();
  const imported = await (await importing).json(); expect(imported.summary).toEqual(record.summary); expect(imported.id).not.toBe(record.id);
  await exchange.getByLabel('选择本地 OTIO 文件').setInputFiles('tests/e2e/fixtures/r4-exchange.otio');
  const lossImport = page.waitForResponse(response => response.url().endsWith('/timeline-exchange/import')); await exchange.getByRole('button', { name: '检查并保存 OTIO 交换副本', exact: true }).click();
  const lossRecord = await (await lossImport).json(); expect(lossRecord.loss_report.some((row: { code: string }) => row.code === 'APPLICATION_METADATA_MIX_SUBTITLES_NOT_REPRESENTED')).toBe(true);
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`otio-${width}.png`) });
  }
  expect(dispatched).toEqual([]); await expect(exchange).toContainText('Resolve / Premiere 打开验证：NOT_RUN');
});
