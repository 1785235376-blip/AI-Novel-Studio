import { test, expect, type Page, type APIResponse } from '@playwright/test';
const API = 'http://127.0.0.1:8057/api', nid = 'surface-branch-book';
const scope = { workspaceId: 'surface-branch-workspace', projectId: nid, storylineId: 'surface-branch-story', branchId: 'surface-branch-a' };
const headers = (token: string) => ({ 'X-Session-Token': token, 'X-Branch-Id': scope.branchId });
async function checked(response: APIResponse) { expect(response.ok(), await response.text()).toBeTruthy(); return response.json(); }
async function enter(page: Page, token: string) {
  await page.addInitScript(({ token, scope }) => { localStorage.setItem('studio.session', token); localStorage.setItem('studio.scope', JSON.stringify(scope)); }, { token, scope });
  await page.goto('/'); await expect(page.locator('.app-shell')).toBeVisible();
  await page.locator('.novel-tree-select').filter({ hasText: '合成分支正文' }).click();
  await expect(page.locator('.ProseMirror')).toContainText('BRANCH_BASE_SYNTHETIC');
}
async function openBranch(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '协作分支正文', exact: true }).click();
}

test('two real browser writers retain branch CAS conflict and fork with no mainline overwrite', async ({ page, browser, request }, info) => {
  info.annotations.push({ type: 'verification', description: 'Real File host, real branch APIs, original rich editor, two trusted synthetic principals. No route mocks, model, GPU, credentials or production transport.' });
  const secondContext = await browser.newContext({ baseURL: 'http://127.0.0.1:5217', viewport: { width: 1440, height: 900 } });
  const second = await secondContext.newPage();
  try {
    await enter(page, 'surface-writer-a'); await enter(second, 'surface-writer-b');
    const base = `${API}/novels/${nid}/experimental/branch-manuscript`;
    const before = (await checked(await request.get(base + '/chapters', { headers: headers('surface-writer-a') }))).items[0];
    await page.locator('.ProseMirror').fill('CLIENT_A_BRANCH_EDIT_SYNTHETIC');
    const savedResponse = page.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes('/chapters/'));
    await page.getByRole('button', { name: '保存', exact: true }).click(); expect((await savedResponse).status()).toBe(200);
    await second.locator('.ProseMirror').fill('CLIENT_B_STALE_DRAFT_SYNTHETIC');
    const conflict = second.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes('/chapters/'));
    await second.getByRole('button', { name: '保存', exact: true }).click(); expect((await conflict).status()).toBe(409);
    await expect(second.getByRole('dialog')).toBeVisible();
    await expect(second.getByRole('dialog')).toContainText('CLIENT_B_STALE_DRAFT_SYNTHETIC');
    const current = await checked(await request.get(base + '/chapters/' + encodeURIComponent(before.id), { headers: headers('surface-writer-a') }));
    expect(current.version).toBe(2); expect(current.content).toContain('CLIENT_A_BRANCH_EDIT_SYNTHETIC');
    await openBranch(page);
    const panel = page.getByRole('region', { name: '协作分支正文', exact: true });
    await panel.getByRole('button', { name: '读取已授权来源章节', exact: true }).click();
    await panel.getByLabel(/主线保留章节 · 来源 v1/).check();
    await panel.getByRole('button', { name: '建立分叉预检', exact: true }).click();
    await expect(panel.getByRole('button', { name: '确认分叉到当前分支', exact: true })).toBeDisabled();
    await panel.getByLabel('已核对来源和版本，复制到当前分支', { exact: true }).check();
    await panel.getByRole('button', { name: '确认分叉到当前分支', exact: true }).click();
    await expect(panel.getByRole('button', { name: '在原编辑器打开 主线保留章节', exact: true })).toBeVisible();
    const mainline = await checked(await request.get(`${API}/novels/${nid}/chapters`, { headers: { 'X-Session-Token': 'surface-writer-a' } }));
    expect(mainline).toHaveLength(1); expect(mainline[0].version).toBe(1); expect(mainline[0].content).toContain('MAINLINE_UNCHANGED_SYNTHETIC');
    await page.screenshot({ path: info.outputPath('branch-fork-real-api.png'), fullPage: true });
    await second.screenshot({ path: info.outputPath('branch-cas-original-editor.png'), fullPage: true });
  } finally { await secondContext.close(); }
});
