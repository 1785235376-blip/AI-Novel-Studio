import { expect, test, type Page } from '@playwright/test';
const scope = { workspaceId: 'workspace-v2', projectId: 'project-v2', storylineId: 'storyline-v2', branchId: 'branch-v2', workspaceName: '创作工作区', projectName: '星海残章', storylineName: '主线', branchName: '当前草稿' };
const scene = { id: 'scene', sequence: 1, source_chapter_id: null, heading: 'INT. 旧车站 - 夜', time: '夜间', location: '旧车站', characters: [], action: '她在空旷的月台上停下，远处传来列车的回声。', dialogue: [], emotion: '警觉', director_notes: [] };
const shot = { id: 'shot', number: 1, scene_id: 'scene', shot_size: 'MEDIUM', camera_angle: 'EYE_LEVEL', camera_motion: 'STATIC', duration_seconds: 5, frame_prompt: '站台远景，人物独自站在灯光边缘。', composition: '人物位于画面左侧', color: '冷色', action: '人物回头', dialogue: [], sound_effect: '', lens: '35mm', lighting: '低调侧光', environment: '夜间旧车站', sound: '风声与列车回声', director_notes: [] };
const document = { id: 'storyboard', mode: 'STORYBOARD', title: '车站 · 分镜', source_chapter_ids: [], source_independent: true, scenes: [scene], director_notes: [], shots: [shot], video_plan: null, version: 1, status: 'DRAFT', source_evidence: {}, created_at: '2026-10-09T00:00:00Z', updated_at: '2026-10-09T00:00:00Z', actor_id: 'author' };
async function seed(page: Page, enabled = true) {
  const creativeRequests: string[] = [];
  await page.addInitScript(scope => { localStorage.setItem('studio.session', 'visual-session'); localStorage.setItem('studio.scope', JSON.stringify(scope)); }, scope);
  await page.route('**/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.includes('/experimental/creative')) {
      creativeRequests.push(path); expect(route.request().headers()['x-session-token']).toBe('visual-session'); expect(route.request().headers()['x-branch-id']).toBe(scope.branchId);
      if (path.endsWith('/capabilities')) return route.fulfill({ json: { enabled, modes: ['SCREENPLAY', 'DIRECTOR', 'STORYBOARD', 'PRODUCTION'], can_mutate: true } });
      if (path.endsWith('/documents')) return route.fulfill({ json: { items: [document] } });
      return route.fulfill({ json: { items: [] } });
    }
    if (path.endsWith('/bootstrap')) return route.fulfill({ json: { actor: { actor_id: 'author', session_id: 'session', client_id: 'client' }, scope: { workspace_id: scope.workspaceId, project_id: scope.projectId, storyline_id: scope.storylineId, branch_id: scope.branchId }, capabilities: {} } });
    if (path.endsWith('/experimental/features')) return route.fulfill({ json: { experimental: enabled, default_enabled: false, features: { 'experimental.narrative_production_v2': enabled } } });
    if (path.endsWith('/chapters/archived')) return route.fulfill({ json: [] });
    if (path.endsWith('/writing-goal')) return route.fulfill({ json: { current_words: 0, target_words: 0, current_chapters: 0, target_chapters: 0, words_progress: 0, chapters_progress: 0 } });
    if (path.endsWith('/creation-reference-data')) return route.fulfill({ json: { characters: [{ id: 'character', name: '林遥' }], locations: [{ id: 'station', name: '旧车站' }], story_routes: [] } });
    if (path.endsWith('/assets')) return route.fulfill({ json: [{ id: 'sound', filename: 'station-ambience.wav', kind: 'AUDIO', media_type: 'audio/wav', size: 24000 }] });
    if (path.endsWith('/local-ai/environment')) return route.fulfill({ status: 404, json: { code: 'EXPERIMENTAL_FEATURE_DISABLED' } });
    return route.fulfill({ json: { items: [] } });
  });
  return creativeRequests;
}
async function open(page: Page) {
  await page.goto('/');
  const entry = page.getByTestId('chapter-tree-scroll').getByRole('button', { name: '打开 V2 创作工作台', exact: true });
  await expect(entry).toBeVisible();
  await entry.scrollIntoViewIfNeeded();
  const placement = await entry.evaluate(element => {
    const rect = element.getBoundingClientRect();
    const launcher = document.querySelector('.feature-launcher__toggle')!.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return { receivesPointer: hit === element || (hit !== null && element.contains(hit)), overlapsLauncher: rect.left < launcher.right && rect.right > launcher.left && rect.top < launcher.bottom && rect.bottom > launcher.top };
  });
  expect(placement.receivesPointer).toBe(true);
  expect(placement.overlapsLauncher).toBe(false);
  await page.getByRole('button', { name: '打开功能导航', exact: true }).click();
  await expect(page.getByRole('navigation', { name: '功能面板导航', exact: true })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: '打开功能导航', exact: true })).toBeFocused();
  await entry.click();
  await expect(page.getByRole('tablist', { name: '创作模式', exact: true })).toBeVisible();
}

test('V2 remains off with no creative API requests', async ({ page }) => { const requests = await seed(page, false); await page.goto('/'); await expect(page.locator('.app-shell')).toBeVisible(); await expect(page.getByRole('button', { name: '打开 V2 创作工作台' })).toHaveCount(0); expect(requests).toHaveLength(0); });

test('keyboard stages and cancelled exit preserve unsaved creative content', async ({ page }) => { await seed(page); await open(page); const novel = page.getByRole('tab', { name: /^小说 Novel/ }); await novel.focus(); await page.keyboard.press('ArrowRight'); await expect(page.getByRole('tab', { name: /^剧本 Screenplay/ })).toBeFocused(); await page.getByLabel('文档标题', { exact: true }).fill('保留此草稿'); await page.getByRole('button', { name: '返回经典工作区' }).click(); await expect(page.getByText('离开会关闭未保存的创作草稿。可以取消离开，先保存或导出。')).toBeVisible(); await page.getByRole('button', { name: '继续编辑', exact: true }).click(); await expect(page.getByLabel('文档标题', { exact: true })).toHaveValue('保留此草稿'); await page.getByRole('tab', { name: /^制作 Production/ }).click(); await page.getByRole('tab', { name: /^剧本 Screenplay/ }).click(); await expect(page.getByLabel('文档标题', { exact: true })).toHaveValue('保留此草稿'); });

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) test(`V2 shared-shell geometry ${viewport.width}x${viewport.height}`, async ({ page }, info) => { await page.setViewportSize(viewport); await seed(page); await open(page); await page.getByRole('tab', { name: /^分镜 Storyboard/ }).click(); await page.evaluate(() => document.fonts.ready); const sizes = await page.evaluate(() => { const rect = (selector: string) => { const bounds = document.querySelector(selector)!.getBoundingClientRect(); return { width: bounds.width, height: bounds.height }; }; return { header: rect('.global-header'), context: rect('.context-bar'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'), status: rect('.status-bar'), scroll: document.documentElement.scrollWidth, viewport: innerWidth }; }); expect(sizes.header.height).toBe(56); expect(sizes.context.height).toBe(44); expect(sizes.sidebar.width).toBe(248); expect(sizes.inspector.width).toBe(340); expect(sizes.status.height).toBe(32); expect(sizes.scroll).toBeLessThanOrEqual(sizes.viewport); await page.screenshot({ path: info.outputPath(`storyboard-${viewport.width}.png`), fullPage: true }); });
