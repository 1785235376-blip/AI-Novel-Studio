import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api'; const UI = 'http://127.0.0.1:5182';
const TOKEN = 'r4-broker-test-session'; const headers = { 'X-Session-Token': TOKEN };
async function checked(response: Pick<APIResponse, 'ok' | 'status' | 'text' | 'json'>): Promise<any> { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function open(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '项目分叉与合并', exact: true }).click();
}
test('B09 real local fork, rich three-way conflict choice, original CAS merge and checkpoint recovery', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); const projects: string[] = []; const writes: string[] = [];
  info.annotations.push({ type: 'verification', description: 'Authored original File/API/React B09 journey; no response mocks or collaboration-branch claim. Local Chromium previously blocked by EPERM and not retried; hosted runtime evidence must be observed separately.' });
  page.on('request', r => { if (r.method() === 'POST' && r.url().includes('/project-forks/')) writes.push(r.url()); });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    expect(await page.evaluate(() => [localStorage.getItem('studio.session'), localStorage.getItem('studio.scope')])).toEqual([null, null]);
    await page.getByPlaceholder('小说名称').fill(`B09 synthetic ${info.testId}`);
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); const novel = await checked(await creating); projects.push(novel.id);
    const chapter = await checked(await request.post(`${API}/novels/${novel.id}/chapters`, { headers, data: { title: '合成分叉章节', content: '双边基线。\n\n中间段落。\n\n单边基线。' } }));
    const original = await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }));
    original.document.content[1].content[0].marks = [{ type: 'bold' }];
    const baseline = await checked(await request.put(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers, data: { version: original.version, document: original.document } }));
    await page.reload(); await open(page); const panel = page.getByRole('region', { name: '项目分叉与合并', exact: true });
    await panel.getByLabel('新分叉项目名称', { exact: true }).fill('合成备用路线');
    await panel.getByLabel(/合成分叉章节 · v/).check();
    const preflight = page.waitForResponse(r => r.url().endsWith('/project-forks/preflight'));
    await panel.getByRole('button', { name: '仅预检所选分叉', exact: true }).click(); const pre = await checked(await preflight);
    expect(writes.filter(url => url.endsWith('/create'))).toHaveLength(0);
    await expect(panel.getByRole('button', { name: '确认创建新项目分叉', exact: true })).toBeDisabled();
    await panel.getByLabel('已核对所选章节与媒体许可，创建此新项目分叉', { exact: true }).check();
    const forking = page.waitForResponse(r => r.url().endsWith(`/project-forks/${pre.id}/create`));
    await panel.getByRole('button', { name: '确认创建新项目分叉', exact: true }).click(); const fork = await checked(await forking); projects.push(fork.target_id);
    const targetId = fork.id_map.chapters[chapter.id]; expect(targetId).not.toBe(chapter.id);
    const copied = await checked(await request.get(`${API}/chapters/${encodeURIComponent(targetId)}`, { headers }));
    expect(copied.document).toEqual(baseline.document);
    expect((await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }))).version).toBe(baseline.version);
    const left = structuredClone(baseline.document); left.content[1].content[0].text = '原稿的双边改文。';
    const right = structuredClone(copied.document); right.content[1].content[0].text = '副本的双边改文。'; right.content[3].content[0].text = '只在副本改变的末段。';
    const checkpoint = await checked(await request.put(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers, data: { version: baseline.version, document: left } }));
    await checked(await request.put(`${API}/chapters/${encodeURIComponent(targetId)}`, { headers, data: { version: copied.version, document: right } }));
    await panel.getByRole('button', { name: '刷新分叉与合并记录', exact: true }).click();
    await panel.getByRole('button', { name: '比较基线、原稿与副本', exact: true }).click();
    const comparison = panel.getByRole('region', { name: '三方合并预览', exact: true });
    await expect(comparison.getByText('双边基线。', { exact: true }).first()).toBeVisible();
    await expect(comparison.getByText('原稿的双边改文。', { exact: true })).toBeVisible();
    await expect(comparison.getByText('副本的双边改文。', { exact: true })).toBeVisible();
    await expect(comparison.getByRole('button', { name: '确认检查点并合并', exact: true })).toBeDisabled();
    await comparison.getByLabel('合成分叉章节 冲突 1 选择', { exact: true }).selectOption('FORK');
    await expect(comparison.getByRole('button', { name: '确认检查点并合并', exact: true })).toBeDisabled();
    await panel.getByRole('button', { name: '更新合并预览', exact: true }).click();
    await expect(comparison.getByText(/待解决冲突 0 项/)).toBeVisible();
    expect(writes.filter(url => url.endsWith('/apply'))).toHaveLength(0);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); const bounds = await panel.boundingBox();
      expect(bounds!.width).toBeGreaterThan(200); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
      await page.screenshot({ path: info.outputPath(`project-fork-three-way-${width}.png`), fullPage: true });
    }
    await comparison.getByLabel('已逐项核对三方差异，建立检查点并合并回原稿', { exact: true }).check();
    const merging = page.waitForResponse(r => r.url().endsWith(`/project-forks/${fork.id}/apply`));
    await comparison.getByRole('button', { name: '确认检查点并合并', exact: true }).click(); const done = await checked(await merging);
    expect(done.status).toBe('COMPLETED'); expect(writes.filter(url => url.endsWith('/apply'))).toHaveLength(1);
    const merged = await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }));
    expect(merged.document).toEqual(right); expect(merged.document.content[1].content[0].marks).toEqual([{ type: 'bold' }]);
    await panel.getByRole('button', { name: '核对检查点与当前结果', exact: true }).click();
    const recovery = panel.getByRole('region', { name: '检查点恢复预览', exact: true });
    await expect(recovery.getByRole('button', { name: '确认恢复检查点', exact: true })).toBeDisabled();
    await recovery.getByLabel('已核对当前内容，明确恢复此合并前检查点为新版本', { exact: true }).check();
    const restoring = page.waitForResponse(r => r.url().endsWith(`/project-forks/merges/${done.id}/restore`));
    await recovery.getByRole('button', { name: '确认恢复检查点', exact: true }).click(); expect((await checked(await restoring)).status).toBe('RESTORED');
    const restored = await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }));
    expect(restored.document).toEqual(checkpoint.document); expect(restored.version).toBeGreaterThan(merged.version);
    expect((await request.get(`${API}/novels/${fork.target_id}`, { headers })).ok()).toBeTruthy();
    expect((await request.get(`${API}/novels/${novel.id}`, { headers })).ok()).toBeTruthy();
  } finally {
    await quiet(); for (const id of projects.reverse()) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(id)}`, { headers })).status());
  }
});
