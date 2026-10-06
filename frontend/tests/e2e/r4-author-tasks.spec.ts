import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';

const API = 'http://127.0.0.1:8023/api', UI = 'http://127.0.0.1:5183';
async function checked(response: APIResponse): Promise<any> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json();
}
async function tasks(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '工作现场', exact: true }).click();
  await page.getByRole('navigation', { name: '工作现场工具分类' }).getByRole('button', { name: '任务中心', exact: true }).click();
}

test('U07 original author job is reopened from its exact task with original Diff and version guard', async ({ page }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '', jid = '';
  info.annotations.push({ type: 'verification', description: 'Actual React/File API and original JobManager, shipped deterministic mock_standin adapter in isolated author-scope profile. No route mocks, real model, credential, paid API, acceptance or second executor.' });
  try {
    await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('U07 original author task synthetic');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await checked(await creating)).id;
    await page.getByRole('button', { name: '新建章节', exact: true }).click();
    await page.getByLabel('章节标题', { exact: true }).fill('原任务来源');
    const adding = page.waitForResponse(r => r.url().endsWith(`/novels/${nid}/chapters`) && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建章节', exact: true }).click(); const chapter = await checked(await adding);
    const manuscript = '合成正文任务，门外有一盏灯。';
    await page.locator('.ProseMirror').fill(manuscript);
    await page.getByRole('button', { name: '保存', exact: true }).click(); await expect(page.locator('.editorbar')).toContainText('已保存');
    const saved = await checked(await page.request.get(`${API}/chapters/${chapter.id}`));
    const created = await checked(await page.request.post(`${API}/generate/continue`, { data: {
      novel_id: nid, chapter_id: chapter.id, instruction: 'PRIVATE_TASK_PROMPT 合成协议短稿', profile: 'LOCAL_ONLY',
      provider_id: 'deepseek', model_id: 'deepseek-chat',
    } })); jid = created.job_id;
    await expect.poll(async () => (await checked(await page.request.get(`${API}/generation/${jid}`))).status).toBe('COMPLETED');
    const flags = await checked(await page.request.get(`${API}/experimental/features`));
    expect(flags.features['experimental.workspace_tools_v2']).toBe(true);
    expect(flags.features['experimental.model_broker_v2']).toBe(false);
    const projected = await checked(await page.request.get(`${API}/novels/${nid}/experimental/workspace/tasks`));
    const row = projected.items.find((value: any) => value.authority === 'author_generation' && value.id === jid);
    expect(row.source).toEqual({ kind: 'generation', id: jid, chapter_id: chapter.id, version: saved.version });
    expect(JSON.stringify(projected)).not.toContain('PRIVATE_TASK_PROMPT');
    expect(JSON.stringify(projected)).not.toContain(manuscript);
    let posts = 0; page.on('request', request => { if (request.method() === 'POST' && /\/(generate|generation)\//.test(request.url())) posts++; });
    await tasks(page);
    const card = page.getByRole('region', { name: '任务中心 · 原服务实时读取', exact: true }).locator('article.experimental-record').filter({ hasText: jid });
    await expect(card).toContainText('已完成');
    await card.getByRole('button', { name: '打开原生成草稿', exact: true }).click();
    await expect(page.locator('.novel-draft-review')).toBeVisible();
    await expect(page.getByRole('button', { name: '采用草稿', exact: true })).toBeEnabled();
    await page.getByRole('tab', { name: '差异', exact: true }).click(); await expect(page.locator('.novel-diff')).toBeVisible();
    expect((await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).version).toBe(saved.version);
    // Reopen the same source after a normal manuscript edit. Existing version
    // guards must prevent accepting the now-stale original job.
    await page.locator('.ProseMirror').fill(manuscript + ' 作者已修改来源。');
    await page.getByRole('button', { name: '保存', exact: true }).click(); await expect(page.locator('.editorbar')).toContainText('已保存');
    const newer = await checked(await page.request.get(`${API}/chapters/${chapter.id}`));
    expect(newer.version).toBeGreaterThan(saved.version);
    await tasks(page); await expect(card).toContainText('来源已变化');
    await card.getByRole('button', { name: '打开原生成草稿', exact: true }).click();
    await expect(page.getByRole('button', { name: '采用草稿', exact: true })).toBeDisabled();
    expect((await checked(await page.request.get(`${API}/generation/${jid}`))).base_chapter_version).toBe(saved.version);
    expect((await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).content).toBe(newer.content);
    expect(posts).toBe(0);
    await page.screenshot({ path: info.outputPath('u07-original-task-stale-review.png'), fullPage: true });
  } finally {
    await quiesce();
    if (jid) await page.request.post(`${API}/generation/${jid}/cancel`);
    if (nid) expect([200, 204, 404]).toContain((await page.request.delete(`${API}/novels/${encodeURIComponent(nid)}`)).status());
  }
});
