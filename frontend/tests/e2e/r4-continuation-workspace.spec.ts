import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function selectProject(page: Page, title: string) {
  await page.goto('/');
  await page.getByRole('button', { name: '切换本机作品', exact: true }).click();
  await page.getByRole('button', { name: title, exact: true }).click();
  await expect(page.locator('.ProseMirror')).toBeVisible();
}

test('post-interop U03 finds an original Scene and opens its exact source editor without generation', async ({ page, request }, info) => {
  let nid = ''; const quiet = createPageQuiescer(page);
  info.annotations.push({ type: 'verification', description: 'Real File original sources, exact scene navigation. Synthetic text only, no model.' });
  try {
    const novel = await body(await request.post(`${API}/novels`, { data: { title: `Continuation scene ${Date.now()}` } })); nid = novel.id;
    const chapter = await body(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Scene source', content: '合成场景检索正文。' } }));
    await body(await request.put(`${API}/novels/${nid}/scenes/scene-target`, { data: { title: '星桥精确场景', chapter_id: chapter.id, purpose: '既有原场景目标' } }));
    await selectProject(page, novel.title); await page.keyboard.press('Control+k');
    const panel = page.getByRole('region', { name: '工作现场工具', exact: true });
    await panel.getByLabel('内容类型', { exact: true }).selectOption('scene');
    await panel.getByLabel('搜索中文名称、别名或正文').fill('星桥');
    await panel.getByRole('button', { name: '打开资料库来源', exact: true }).click();
    await expect(page.getByText('已定位当前记录：星桥精确场景。未更改资料。')).toBeVisible();
    await expect(page.getByLabel('场景标题', { exact: true })).toHaveValue('星桥精确场景');
    expect((await body(await request.get(`${API}/novels/${nid}/scenes`))).find((row: any) => row.id === 'scene-target').purpose).toBe('既有原场景目标');
    await page.screenshot({ path: info.outputPath('u03-exact-original-scene.png'), fullPage: true });
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status()); }
});

test('post-interop U07 confirms and cancels an original import then reopens that exact owner', async ({ page, request }, info) => {
  let nid = ''; const quiet = createPageQuiescer(page);
  info.annotations.push({ type: 'verification', description: 'Real original import queue/CAS and mounted task UI. No provider, retry or execution.' });
  try {
    const novel = await body(await request.post(`${API}/novels`, { data: { title: `Continuation task ${Date.now()}` } })); nid = novel.id;
    const chapter = await body(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Task source', content: '纯合成导入候选来源。' } }));
    const root = `${API}/novels/${nid}/experimental`;
    const job = await body(await request.post(`${root}/imports/jobs`, { data: { chapter_ids: [chapter.id], chunk_size: 8000, overlap: 256, adapter_id: 'local-semantic-rules-v2' } }));
    await selectProject(page, novel.title); await page.keyboard.press('Control+k');
    await page.getByRole('navigation', { name: '工作现场工具分类' }).getByRole('button', { name: '任务中心', exact: true }).click();
    const card = page.getByRole('region', { name: '任务中心 · 原服务实时读取', exact: true }).locator('article.experimental-record').filter({ hasText: job.id });
    await card.getByRole('button', { name: '取消原任务', exact: true }).click();
    expect((await body(await request.get(`${root}/imports/jobs/${job.id}`))).status).toBe('QUEUED');
    await page.getByRole('button', { name: '确认请求取消', exact: true }).click();
    await expect(card).toContainText('已取消');
    expect((await body(await request.get(`${root}/imports/jobs/${job.id}`))).version).toBe(job.version + 1);
    await card.getByRole('button', { name: '打开来源工具', exact: true }).click();
    await expect(page.getByLabel('导入任务', { exact: true })).toHaveValue(job.id);
    await expect(page.getByRole('region', { name: '导入任务状态' })).toContainText('CANCELLED');
    await page.screenshot({ path: info.outputPath('u07-original-import-cancel.png'), fullPage: true });
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status()); }
});

test('post-interop U02 corrupt draft survives reload until explicit local recovery choice', async ({ page, request }, info) => {
  let nid = ''; const quiet = createPageQuiescer(page);
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  try {
    const novel = await body(await request.post(`${API}/novels`, { data: { title: `Continuation recovery ${Date.now()}` } })); nid = novel.id;
    const chapter = await body(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Recovery source', content: '合成后端已保存正文。' } }));
    await selectProject(page, novel.title);
    const key = `ai-novel-studio:draft:file:${chapter.id}`, raw = '{"chapterId":"partial synthetic';
    await page.evaluate(({ key, raw }) => localStorage.setItem(key, raw), { key, raw });
    await page.reload();
    await expect(page.getByRole('alert', { name: '本机草稿恢复需要处理' })).toBeVisible();
    await expect(page.locator('.ProseMirror')).toHaveCount(0);
    expect(await page.evaluate(key => localStorage.getItem(key), key)).toBe(raw);
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: '导出原始草稿记录', exact: true }).click();
    expect((await download).suggestedFilename()).toBe('writing-recovery-original.txt');
    await page.getByRole('button', { name: '丢弃损坏记录并打开后端版本', exact: true }).click();
    await expect(page.locator('.ProseMirror')).toContainText('合成后端已保存正文');
    expect(await page.evaluate(key => localStorage.getItem(key), key)).toBeNull();
    await page.screenshot({ path: info.outputPath('u02-corrupt-draft-recovery.png') });
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status()); }
});
