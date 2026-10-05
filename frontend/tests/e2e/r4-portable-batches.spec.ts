import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
// Reuse the configured isolated host-session profile, never production login.
const API = 'http://127.0.0.1:8022/api'; const UI = 'http://127.0.0.1:5182';
const TOKEN = 'r4-broker-test-session'; const headers = { 'X-Session-Token': TOKEN };
async function tools(page: Page, label: string) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: label, exact: true }).click();
}
test('J15 portable ZIP new-project restore and J10 explicit serial batch without auto dispatch', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); const projects: string[] = []; const mutations: string[] = [];
  info.annotations.push({ type: 'verification', description: 'Authored real File API/React journey, NOT_RUN locally: Chromium launch EPERM; no retry. No real model, paid calls or GPU claims.' });
  page.on('request', req => { if (req.method() === 'POST') mutations.push(req.url()); });
  try {
    await page.addInitScript(token => localStorage.setItem('studio.session', token), TOKEN); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('U14 U16 synthetic portable journey');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); const novel = await (await creating).json(); projects.push(novel.id);
    const created = await request.post(`${API}/novels/${novel.id}/chapters`, { headers, data: { title: '合成潮汐', content: '甲🙂。 the the 潮汐！！' } }); expect(created.ok()).toBeTruthy(); const chapter = await created.json();
    await page.reload(); await tools(page, '项目便携与资源恢复');
    const portable = page.getByRole('region', { name: '项目便携与资源恢复', exact: true });
    await portable.getByLabel(/合成潮汐 · v/).check();
    const exporting = page.waitForResponse(r => r.url().endsWith('/portable-projects/export') && r.request().method() === 'POST');
    await portable.getByRole('button', { name: '创建所选章节便携包', exact: true }).click(); const exported = await (await exporting).json();
    const zip = await request.get(`${API}/novels/${novel.id}/experimental/portable-projects/records/${exported.id}/file?expected_version=1`, { headers }); expect(zip.ok()).toBeTruthy();
    await portable.getByLabel('选择便携 ZIP 文件').setInputFiles({ name: 'synthetic-portable.zip', mimeType: 'application/zip', buffer: await zip.body() });
    const preflight = page.waitForResponse(r => r.url().endsWith('/portable-projects/import-preflight') && r.request().method() === 'POST');
    await portable.getByRole('button', { name: '仅预检便携包', exact: true }).click(); expect((await preflight).ok()).toBeTruthy();
    expect(mutations.filter(url => url.endsWith('/restore'))).toHaveLength(0);
    await portable.getByLabel('已核对本记录与缺失项，确认创建新项目副本').check();
    const restoring = page.waitForResponse(r => /\/portable-projects\/records\/[^/]+\/restore$/.test(r.url()));
    await portable.getByRole('button', { name: '确认恢复到新项目', exact: true }).click(); const restored = await (await restoring).json(); projects.push(restored.target_id);
    expect(restored.target_id).not.toBe(novel.id); expect(restored.id_map.chapters.c0001).not.toBe(chapter.id);
    const original = await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }); expect((await original.json()).version).toBe(1);
    await page.screenshot({ path: info.outputPath('portable-new-project-receipt.png'), fullPage: true });
    await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '安全批处理', exact: true }).click();
    const batches = page.getByRole('region', { name: '安全批处理与执行预检', exact: true }); await batches.getByLabel(/合成潮汐 · v/).check(); await batches.getByLabel('导出所选章节').check();
    const checking = page.waitForResponse(r => r.url().endsWith('/safe-batches/preflight'));
    await batches.getByRole('button', { name: '仅预检所选批次', exact: true }).click(); const preview = await (await checking).json(); expect(preview.status).toBe('PREFLIGHT');
    expect(mutations.filter(url => url.endsWith('/dispatch-next'))).toHaveLength(0);
    await batches.getByLabel('已核对本批次来源版本、权限、资源与 0 USD 预算').check();
    await batches.getByRole('button', { name: '确认此批次快照与预算', exact: true }).click(); await expect(batches.getByRole('button', { name: '执行下一阶段', exact: true })).toBeEnabled();
    expect(mutations.filter(url => url.endsWith('/dispatch-next'))).toHaveLength(0);
    const running = page.waitForResponse(r => r.url().endsWith('/dispatch-next'));
    await batches.getByRole('button', { name: '执行下一阶段', exact: true }).click(); const stage = await (await running).json();
    expect(stage.items[0].status).toBe('COMPLETED'); expect(stage.items[1].status).toBe('PENDING');
    await batches.getByRole('button', { name: '停止此批次后续阶段', exact: true }).click(); await expect(batches).toContainText('CANCELLED');
    expect(mutations.filter(url => url.endsWith('/dispatch-next'))).toHaveLength(1);
    await page.screenshot({ path: info.outputPath('batch-one-stage-and-stop.png'), fullPage: true });
  } finally {
    await quiet(); for (const id of projects.reverse()) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${id}`, { headers })).status());
  }
});
