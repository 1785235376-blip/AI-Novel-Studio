import { expect, test, type APIResponse } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8023/api', UI = 'http://127.0.0.1:5183';
async function checked(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }

test('U08 original Research citation is pinned into exact request, excluded and invalidated on replacement', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); let nid = '';
  const modelCalls: string[] = [];
  page.on('request', row => { if (row.method() === 'POST' && /author-context\/generate/.test(row.url())) modelCalls.push(row.url()); });
  info.annotations.push({ type: 'verification', description: 'Original React/File services, synthetic Research content, real preview builder. No provider or model dispatch.' });
  try {
    const novel = await checked(await request.post(`${API}/novels`, { data: { title: `U08 explicit sources ${Date.now()}` } })); nid = novel.id;
    await checked(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Synthetic source', content: 'PRIMARY_MANUSCRIPT_CANARY' } }));
    const base = `${API}/novels/${nid}/experimental`;
    const file = { title: 'Native synthetic reference', filename: 'reference.txt', content_base64: Buffer.from('RESEARCH_SOURCE_CANARY').toString('base64') };
    const source = await checked(await request.post(`${base}/research-library/sources/import`, { data: file }));
    await page.goto(UI); await page.getByRole('button', { name: '切换本机作品', exact: true }).click(); await page.getByRole('button', { name: novel.title, exact: true }).click();
    const panel = page.locator('.novel-ai-panel'); await expect(page.locator('.ProseMirror')).toBeVisible();
    await panel.getByLabel('文本模型', { exact: true }).selectOption('deepseek:deepseek-chat');
    await panel.getByLabel('正文范围', { exact: true }).selectOption('NONE');
    await panel.getByLabel('添加来源类型').selectOption('RESEARCH'); await panel.getByRole('button', { name: '读取可添加来源', exact: true }).click();
    await panel.getByRole('button', { name: '添加并固定 Native synthetic reference · 段落 1', exact: true }).click();
    let pending = page.waitForResponse(row => row.url().endsWith('/author-context/preview'));
    await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click(); const initial = await checked(await pending);
    expect(initial.request.prompt).toContain('RESEARCH_SOURCE_CANARY'); expect(initial.request.prompt).not.toContain('PRIMARY_MANUSCRIPT_CANARY');
    expect(initial.request.context.explicit_sources.items[0].citation).toEqual(source.paragraphs[0].citation);
    await panel.getByLabel(`包含手动来源 ${source.id}`, { exact: true }).uncheck(); await expect(panel.getByText('请求已预检', { exact: true })).toHaveCount(0);
    pending = page.waitForResponse(row => row.url().endsWith('/author-context/preview')); await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click();
    expect((await checked(await pending)).request.prompt).not.toContain('RESEARCH_SOURCE_CANARY');
    await checked(await request.put(`${base}/research-library/sources/${source.id}/file`, { data: { ...file, expected_version: source.version, content_base64: Buffer.from('NEW_RESEARCH_CANARY').toString('base64') } }));
    pending = page.waitForResponse(row => row.url().endsWith('/author-context/preview')); await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click();
    expect([404, 409]).toContain((await pending).status()); await expect(panel.getByText('请求已预检', { exact: true })).toHaveCount(0); expect(modelCalls).toEqual([]);
    await page.screenshot({ path: info.outputPath('u08-source-replaced-recheck.png'), fullPage: true });
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status()); }
});
