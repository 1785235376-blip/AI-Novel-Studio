import { expect, test, type Page, type APIResponse } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api', UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
async function checked(response: APIResponse): Promise<any> { expect(response.ok(), `${response.status()} ${await response.text()}`).toBeTruthy(); return response.json(); }
async function open(page: Page, feature: string) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ }); if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: feature, exact: true }).click();
}
test('Wave5 accepted translation memory and explicit pinned Universe keep original authority after restart', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); let nid = ''; const modelCalls: string[] = [];
  info.annotations.push({ type: 'verification', description: 'Real original File/API/React journey. No response mocks or model calls. Local browser platform-BLOCKED; execution evidence is hosted only.' });
  page.on('request', r => { if (r.method() === 'POST' && /author-context\/generate|\/generate\//.test(r.url())) modelCalls.push(r.url()); });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI); await page.getByPlaceholder('小说名称').fill(`Wave5 extended ${info.testId}`);
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST'); await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await checked(await creating)).id;
    const chapter = await checked(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: 'Wave5 source', content: 'Port arrival.' } }));
    const original = await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }));
    const base = `${API}/novels/${nid}/experimental/language-editions`;
    async function edition(title: string) { return checked(await request.post(base, { headers, data: { title, source_language: 'en', target_language: 'ar', chapters: [{ chapter_id: original.id, chapter_version: original.version }] } })); }
    let source = await edition('Reviewed source'); const dest = await edition('Memory destination');
    const first = `${base}/${source.id}/segments/${source.segments[0].id}`;
    source = await checked(await request.put(first, { headers, data: { expected_version: source.version, text: 'ترجمة مراجعة للذاكرة' } }));
    source = await checked(await request.post(first + '/review', { headers, data: { expected_version: source.version, action: 'submit' } }));
    const term = await checked(await request.post(first + '/preview', { headers, data: { expected_version: source.version } }));
    await checked(await request.post(first + '/review', { headers, data: { expected_version: source.version, action: 'accept', preview_digest: term.preview_digest } }));
    await page.reload(); await open(page, '多语言版本与术语');
    await page.getByRole('button', { name: 'Memory destination · ar · v1', exact: true }).click();
    await page.getByRole('button', { name: '查找完全匹配翻译记忆', exact: true }).click(); await expect(page.getByText('ترجمة مراجعة للذاكرة', { exact: true })).toBeVisible();
    const adopting = page.waitForResponse(r => r.url().endsWith('/memory-adopt'));
    await page.getByRole('button', { name: '采用此记忆为待审草稿', exact: true }).click(); const adopted = await checked(await adopting);
    expect(adopted.segments[0].status).toBe('DRAFT'); await expect(page.getByLabel('第 1 段译文', { exact: true })).toHaveValue('ترجمة مراجعة للذاكرة');
    await page.getByRole('button', { name: '读取本段译文历史', exact: true }).click();
    const restoring = page.waitForResponse(r => r.url().endsWith('/restore'));
    await page.getByRole('button', { name: '恢复 v1 为新草稿', exact: true }).click(); expect((await checked(await restoring)).segments[0].target_text).toBe('');
    await checked(await request.put(`${API}/novels/${nid}/locations/wave5-port`, { headers, data: { name: 'Wave5 Port', privacy_level: 'CLOUD_ALLOWED' } }));
    await page.reload(); await open(page, '项目分叉与合并'); await page.getByRole('button', { name: '打开系列世界观快照', exact: true }).click();
    const panel = page.getByRole('region', { name: 'Shared Universe 版本固定', exact: true });
    await panel.getByLabel('Universe 标识', { exact: true }).fill('tide-series'); await panel.getByLabel('世界观快照名称', { exact: true }).fill('First frozen world');
    await panel.getByLabel('地点：Wave5 Port', { exact: true }).check(); await panel.getByLabel('世界观本地复制许可', { exact: true }).fill('Synthetic author-owned');
    await panel.getByLabel('我有权为这些作品保留所选资料的本地只读快照', { exact: true }).check();
    await panel.getByRole('button', { name: '预览不可变世界观快照', exact: true }).click();
    const snapshotResponse = page.waitForResponse(r => r.url().endsWith('/universe/snapshots') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '确认创建只读世界观快照', exact: true }).click(); const snapshot = await checked(await snapshotResponse);
    await expect(panel.getByLabel('要固定的世界观快照', { exact: true }).locator('option', { hasText: 'First frozen world' })).toHaveCount(1);
    await panel.getByLabel('要固定的世界观快照', { exact: true }).selectOption(snapshot.id); await panel.getByLabel('系列作品', { exact: true }).selectOption(nid); await panel.getByLabel('作品关系', { exact: true }).selectOption('MAIN_NOVEL');
    await panel.getByRole('button', { name: '比较作品固定版本', exact: true }).click(); await expect(panel.getByRole('button', { name: '确认固定此作品世界观版本', exact: true })).toBeDisabled();
    await panel.getByLabel('我确认仅为此作品固定这个世界观版本', { exact: true }).check(); const pinnedResponse = page.waitForResponse(r => r.url().endsWith('/universe/pins') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '确认固定此作品世界观版本', exact: true }).click(); const pinned = await checked(await pinnedResponse); expect(pinned.snapshot_id).toBe(snapshot.id);
    await checked(await request.put(`${API}/novels/${nid}/locations/wave5-port`, { headers, data: { name: 'Future Port', privacy_level: 'CLOUD_ALLOWED' } }));
    await panel.getByRole('button', { name: '刷新世界观快照与固定版本', exact: true }).click(); await expect(panel.getByText('原资料已变化，此作品仍使用原固定快照。', { exact: true })).toBeVisible();
    const all = await checked(await request.get(`${API}/novels/${nid}/experimental/project-forks/universe/snapshots`, { headers })); expect(all.items[0].records['locations:wave5-port'].name).toBe('Wave5 Port');
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) { await page.setViewportSize({ width, height }); const bounds = await panel.boundingBox(); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width); await page.screenshot({ path: info.outputPath(`wave5-universe-${width}.png`), fullPage: true }); }
    await page.reload(); await open(page, '项目分叉与合并'); await page.getByRole('button', { name: '打开系列世界观快照', exact: true }).click(); await expect(page.getByText(/tide-series · 快照 v1 · 引用 v1 · PINNED/)).toBeVisible();
    const final = await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers })); expect(final.document).toEqual(original.document); expect(final.version).toBe(original.version); expect(modelCalls).toEqual([]);
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status()); }
});
