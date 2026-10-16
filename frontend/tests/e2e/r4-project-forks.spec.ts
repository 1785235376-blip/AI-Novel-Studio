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

test('B09 real original structured records map references, review rename conflict and restore checkpoint', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); const projects: string[] = [];
  info.annotations.push({ type: 'verification', description: 'Original File knowledge owners, exact digest CAS, real React field-level merge, no provider and no response mocking. Hosted run required; local Chromium not retried.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill(`B09 structured synthetic ${info.testId}`);
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); const novel = await checked(await creating); projects.push(novel.id);
    const data = { name: '合成角色', current_location: 'harbor', privacy_level: 'LOCAL_ONLY' };
    await checked(await request.put(`${API}/novels/${novel.id}/locations/harbor`, { headers, data: { name: '合成港口', privacy_level: 'LOCAL_ONLY' } }));
    await checked(await request.put(`${API}/novels/${novel.id}/characters/hero`, { headers, data }));
    const chapter = await checked(await request.post(`${API}/novels/${novel.id}/chapters`, { headers, data: { title: '合成组合章节', content: '正文与人物放入同一副本。' } }));
    await page.reload(); await open(page);
    const manuscriptPanel = page.getByRole('region', { name: '项目分叉与合并', exact: true });
    await manuscriptPanel.getByLabel('新分叉项目名称', { exact: true }).fill('合成正文路线');
    await manuscriptPanel.getByLabel(/合成组合章节 · v/).check();
    const manuscriptPreflight = page.waitForResponse(r => r.url().endsWith('/project-forks/preflight'));
    await manuscriptPanel.getByRole('button', { name: '仅预检所选分叉', exact: true }).click(); const manuscriptPre = await checked(await manuscriptPreflight);
    await manuscriptPanel.getByLabel('已核对所选章节与媒体许可，创建此新项目分叉', { exact: true }).check();
    const manuscriptCreating = page.waitForResponse(r => r.url().endsWith(`/project-forks/${manuscriptPre.id}/create`));
    await manuscriptPanel.getByRole('button', { name: '确认创建新项目分叉', exact: true }).click(); const manuscript = await checked(await manuscriptCreating); projects.push(manuscript.target_id);
    await page.getByRole('button', { name: '打开人物与关系分叉', exact: true }).click();
    const panel = page.getByRole('region', { name: '人物地点与关系分叉', exact: true });
    await panel.getByLabel('结构记录目标', { exact: true }).selectOption(manuscript.id);
    await panel.getByLabel('结构分叉项目名称', { exact: true }).fill('合成结构路线');
    await panel.getByLabel('人物：合成角色', { exact: true }).check();
    await expect(panel.getByText(/尚缺引用目标/)).toBeVisible();
    await expect(panel.getByRole('button', { name: '仅预检结构分叉', exact: true })).toBeDisabled();
    await panel.getByLabel('地点：合成港口', { exact: true }).check();
    await panel.getByLabel('所选结构记录的许可说明', { exact: true }).fill('作者原创合成资料');
    await panel.getByLabel('我有权将所选结构记录复制到此本地新项目', { exact: true }).check();
    const preflight = page.waitForResponse(r => r.url().endsWith('/project-forks/structured/preflight'));
    await panel.getByRole('button', { name: '仅预检结构分叉', exact: true }).click(); const pre = await checked(await preflight);
    await expect(panel.getByRole('button', { name: '确认创建结构分叉', exact: true })).toBeDisabled();
    await panel.getByLabel('已核对结构记录、映射与许可，创建此分叉', { exact: true }).check();
    const forking = page.waitForResponse(r => r.url().endsWith(`/structured/${pre.id}/create`));
    await panel.getByRole('button', { name: '确认创建结构分叉', exact: true }).click(); const fork = await checked(await forking); expect(fork.target_id).toBe(manuscript.target_id);
    const copiedChapter = await checked(await request.get(`${API}/chapters/${encodeURIComponent(manuscript.id_map.chapters[chapter.id])}`, { headers }));
    expect(copiedChapter.content).toContain('正文与人物放入同一副本');
    const forkHero = fork.id_map['characters:hero'].split(':')[1]; const forkLocation = fork.id_map['locations:harbor'].split(':')[1];
    const copied = (await checked(await request.get(`${API}/novels/${fork.target_id}/characters`, { headers })))[0];
    expect(copied.current_location).toBe(forkLocation); expect(copied.privacy_level).toBe('LOCAL_ONLY');
    await checked(await request.put(`${API}/novels/${novel.id}/characters/hero`, { headers, data: { ...data, name: '原角色改名' } }));
    await checked(await request.put(`${API}/novels/${fork.target_id}/characters/${forkHero}`, { headers, data: { ...data, current_location: forkLocation, name: '副本角色改名' } }));
    await panel.getByRole('button', { name: '刷新结构分叉记录', exact: true }).click();
    await panel.getByRole('button', { name: '比较结构记录三方差异', exact: true }).click();
    const comparison = panel.getByRole('region', { name: '结构三方合并预览', exact: true });
    await expect(comparison.getByText('合成角色', { exact: true })).toBeVisible();
    await expect(comparison.getByText('原角色改名', { exact: true })).toBeVisible();
    await expect(comparison.getByText('副本角色改名', { exact: true })).toBeVisible();
    await expect(comparison.getByRole('button', { name: '确认结构检查点并合并', exact: true })).toBeDisabled();
    await comparison.getByLabel('原角色改名 名称 结构冲突选择', { exact: true }).selectOption('FORK');
    await panel.getByRole('button', { name: '更新结构合并预览', exact: true }).click();
    await comparison.getByLabel('已核对结构三方差异，建立检查点并合并', { exact: true }).check();
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); const bounds = await panel.boundingBox();
      expect(bounds!.width).toBeGreaterThan(200); expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(width);
      await page.screenshot({ path: info.outputPath(`structured-fork-review-${width}.png`), fullPage: true });
    }
    const merging = page.waitForResponse(r => r.url().endsWith(`/structured/${fork.id}/apply`));
    await comparison.getByRole('button', { name: '确认结构检查点并合并', exact: true }).click(); const done = await checked(await merging); expect(done.status).toBe('COMPLETED');
    expect((await checked(await request.get(`${API}/novels/${novel.id}/characters`, { headers })))[0].name).toBe('副本角色改名');
    await panel.getByRole('button', { name: '核对结构检查点与当前记录', exact: true }).click();
    const recovery = panel.getByRole('region', { name: '结构检查点恢复预览', exact: true });
    await recovery.getByLabel('已核对当前结构记录，明确恢复此检查点', { exact: true }).check();
    const restoring = page.waitForResponse(r => r.url().endsWith(`/structured/merges/${done.id}/restore`));
    await recovery.getByRole('button', { name: '确认恢复结构检查点', exact: true }).click(); expect((await checked(await restoring)).status).toBe('RESTORED');
    expect((await checked(await request.get(`${API}/novels/${novel.id}/characters`, { headers })))[0].name).toBe('原角色改名');
  } finally {
    await quiet(); for (const id of projects.reverse()) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(id)}`, { headers })).status());
  }
});
