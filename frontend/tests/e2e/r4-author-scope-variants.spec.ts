import { expect, test, type APIResponse } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';

const API = 'http://127.0.0.1:8023/api', UI = 'http://127.0.0.1:5183';
const manuscript = '这是可公开的合成章节。PRIVATE_TAIL_CANARY 不应进入精简请求。甲🙂é提着灯。';
async function checked(response: APIResponse): Promise<any> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json();
}

test('U08 real React source removals and individually reviewed local variant jobs preserve original draft review', async ({ page }, info) => {
  const quiesce = createPageQuiescer(page); let nid = ''; const jobIds: string[] = [];
  info.annotations.push({ type: 'verification', description: 'Actual React/File services; explicitly labeled shipped mock_standin adapter in an isolated author-scope profile. No route response mocks, paid calls, credentials or real model quality claim.' });
  try {
    await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('U08 local synthetic variants');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await checked(await creating)).id;
    await page.getByRole('button', { name: '新建章节', exact: true }).click();
    await page.getByLabel('章节标题', { exact: true }).fill('合成测试章节');
    const adding = page.waitForResponse(r => r.url().endsWith(`/novels/${nid}/chapters`) && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建章节', exact: true }).click(); const chapter = await checked(await adding);
    const editor = page.locator('.ProseMirror'); await editor.fill(manuscript);
    await page.getByRole('button', { name: '保存', exact: true }).click(); await expect(page.locator('.editorbar')).toContainText('已保存');
    const saved = await checked(await page.request.get(`${API}/chapters/${chapter.id}`));
    const panel = page.locator('.novel-ai-panel');
    await panel.getByRole('combobox', { name: '文本模型', exact: true }).selectOption('deepseek:deepseek-chat');
    await expect(panel.locator('.novel-ai-status [role="status"]')).toContainText(/模拟测试/);
    await editor.focus();
    await editor.evaluate(root => {
      const node = root.firstChild!.firstChild!, text = node.textContent!, range = document.createRange();
      range.setStart(node, text.indexOf('甲')); range.setEnd(node, text.length);
      const selection = window.getSelection()!; selection.removeAllRanges(); selection.addRange(range);
      document.dispatchEvent(new Event('selectionchange'));
    });
    await expect(panel.getByRole('region', { name: '本次请求材料范围', exact: true })).toBeVisible();
    await expect(panel.getByLabel('正文范围', { exact: true })).toBeVisible();
    await panel.getByLabel('正文范围', { exact: true }).selectOption('SELECTION_ONLY');
    const selecting = page.waitForResponse(r => r.url().endsWith('/author-context/preview') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click();
    const selected = await checked(await selecting);
    expect(selected.source_strategy).toBe('EXACT_SAVED_SELECTION'); expect(selected.request.context).toEqual({});
    expect(selected.request.prompt).toContain('甲🙂é提着灯。'); expect(selected.request.prompt).not.toContain('PRIVATE_TAIL_CANARY');
    await panel.getByLabel('正文范围', { exact: true }).selectOption('NONE');
    await expect(panel.getByLabel('包含自动上下文整包', { exact: true })).toBeDisabled();
    await expect(panel.getByLabel('包含自动上下文整包', { exact: true })).not.toBeChecked();
    await panel.getByLabel('附加要求（可选）', { exact: true }).fill('写一个简短合成场景。');
    const inspecting = page.waitForResponse(r => r.url().endsWith('/author-context/preview') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click(); const single = await checked(await inspecting);
    expect(single.source_characters).toBe(0); expect(single.request.context).toEqual({});
    expect(single.request.prompt).not.toContain('PRIVATE_TAIL_CANARY');
    await expect(panel.getByRole('button', { name: '生成创作下一章草稿', exact: true })).toBeEnabled();
    await panel.getByRole('group', { name: '候选方案数量' }).getByRole('button', { name: '2', exact: true }).click();
    await expect(panel.getByRole('button', { name: '生成创作下一章草稿', exact: true })).toBeDisabled();
    const reviewing = page.waitForResponse(r => r.url().endsWith('/author-context/preview-variants') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click(); const review = await checked(await reviewing);
    expect(review.count).toBe(2); expect(review.model_called).toBe(false);
    for (let index = 0; index < 2; index++) {
      const row = review.variants[index]; jobIds.push(row.variant.job_id);
      expect(row.request.prompt).toContain(`候选方案 ${index + 1}`); expect(row.request.prompt).not.toContain('PRIVATE_TAIL_CANARY');
      expect(row.request.context).toEqual({});
      await expect(panel.getByLabel(`方案 ${index + 1} 准确生成 Prompt`, { exact: true })).toHaveValue(row.request.prompt);
    }
    expect(review.variants[0].preview_digest).not.toBe(review.variants[1].preview_digest);
    const generating = page.waitForResponse(r => r.url().endsWith('/author-context/generate-variants') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '生成创作下一章草稿', exact: true }).click();
    const generatedResponse = await generating, generated = await checked(generatedResponse);
    const sent = generatedResponse.request().postDataJSON();
    expect(sent.author.request_scope.source_mode).toBe('NONE'); expect(sent.count).toBe(2);
    expect(sent.receipts.map((r: any) => r.preview_digest)).toEqual(review.variants.map((r: any) => r.preview_digest));
    expect(generated.variants.map((r: any) => r.job_id)).toEqual(jobIds);
    for (const id of jobIds) await expect.poll(async () => (await checked(await page.request.get(`${API}/generation/${id}`))).status).toBe('COMPLETED');
    await expect(panel.getByRole('tablist', { name: '候选方案', exact: true })).toContainText('方案 2');
    await expect(panel.getByRole('button', { name: '采用草稿', exact: true })).toBeEnabled();
    expect((await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).version).toBe(saved.version);
    await panel.getByRole('tab', { name: '差异', exact: true }).click(); await expect(panel.locator('.novel-diff')).toBeVisible();
    const repeat = await checked(await page.request.post(`${API}/novels/${nid}/experimental/author-context/generate-variants`, { data: sent }));
    expect(repeat.variants.map((r: any) => r.job_id)).toEqual(jobIds);
    expect((await checked(await page.request.get(`${API}/generation-groups/${review.group_id}`))).count).toBe(2);
    await page.screenshot({ path: info.outputPath('u08-reviewed-variant-diff.png'), fullPage: true });
    // Existing recovery must read the same jobs, without posting another batch.
    let generationPosts = 0; page.on('request', r => { if (r.method() === 'POST' && r.url().includes('/author-context/generate')) generationPosts++; });
    await page.reload(); await expect(page.locator('.novel-draft-review')).toBeVisible();
    expect(generationPosts).toBe(0);
    expect((await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).content).toBe(saved.content);
    await page.locator('.novel-draft-review').getByRole('button', { name: '采用草稿', exact: true }).click();
    await expect.poll(async () => (await checked(await page.request.get(`${API}/generation-groups/${review.group_id}`))).variants.filter((row: any) => row.status === 'ACCEPTED').length).toBe(1);
    expect((await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).content).toBe(saved.content);
    expect(generationPosts).toBe(0);
  } finally {
    await quiesce();
    for (const id of jobIds) await page.request.post(`${API}/generation/${id}/cancel`);
    if (nid) expect([200, 204, 404]).toContain((await page.request.delete(`${API}/novels/${encodeURIComponent(nid)}`)).status());
  }
});

test('U08 identified source exclusion removes dependent summaries from the actual reviewed request', async ({ page }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '', jid = '';
  try {
    await page.goto(UI); await page.getByPlaceholder('小说名称').fill('U08 per-source synthetic receipt');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await checked(await creating)).id;
    await page.getByRole('button', { name: '新建章节', exact: true }).click(); await page.getByLabel('章节标题', { exact: true }).fill('逐项来源测试');
    const adding = page.waitForResponse(r => r.url().endsWith(`/novels/${nid}/chapters`) && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建章节', exact: true }).click(); const chapter = await checked(await adding);
    await page.locator('.ProseMirror').fill('当前合成正文不包含资料中的测试暗语。');
    await page.getByRole('button', { name: '保存', exact: true }).click(); await expect(page.locator('.editorbar')).toContainText('已保存');
    const saved = await checked(await page.request.get(`${API}/chapters/${chapter.id}`));
    await checked(await page.request.put(`${API}/novels/${nid}/characters/removed`, { data: { name: '排除人物', personality: 'EXCLUDED_SOURCE_ITEM_CANARY', privacy_level: 'LOCAL_ONLY' } }));
    await checked(await page.request.put(`${API}/novels/${nid}/characters/kept`, { data: { name: '保留人物', personality: 'RETAINED_SOURCE_ITEM_CANARY', privacy_level: 'LOCAL_ONLY' } }));
    await checked(await page.request.put(`${API}/novels/${nid}`, { data: { long_term_summary: 'EXCLUDED_SOURCE_ITEM_CANARY' } }));
    const panel = page.locator('.novel-ai-panel');
    await panel.getByRole('combobox', { name: '文本模型', exact: true }).selectOption('deepseek:deepseek-chat');
    await panel.getByLabel('附加要求（可选）', { exact: true }).fill('排除人物与保留人物：仅作合成协议测试。');
    let response = page.waitForResponse(r => r.url().endsWith('/author-context/preview') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click(); const initial = await checked(await response);
    const source = initial.source_manifest.items.find((row: any) => row.label === '排除人物');expect(source).toBeTruthy();
    // Selecting an item invalidates and removes the old request preview immediately.
    // Click the real control, then verify new intent in the next actual request;
    // uncheck() would wait for a checked-state on the intentionally removed node.
    const exclusion = panel.getByRole('checkbox', { name: `包含人物：排除人物 · ${source.key.slice(0, 8)}`, exact: true });
    await expect(exclusion).toBeChecked(); await exclusion.click();
    await expect(panel.getByRole('button', { name: '生成创作下一章草稿', exact: true })).toBeDisabled();
    response = page.waitForResponse(r => r.url().endsWith('/author-context/preview') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '检查真实生成请求', exact: true }).click(); const filtered = await checked(await response);
    expect(JSON.stringify(filtered.request)).not.toContain('EXCLUDED_SOURCE_ITEM_CANARY');expect(filtered.request.prompt).toContain('RETAINED_SOURCE_ITEM_CANARY');
    expect(filtered.source_manifest.dependent_context_omitted).toBe(true);expect(filtered.scope_effects.references_omitted_for_source_isolation).toBe(true);
    const generating = page.waitForResponse(r => r.url().endsWith('/author-context/generate') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '生成创作下一章草稿', exact: true }).click(); const generatedResponse = await generating;
    jid = (await checked(generatedResponse)).job_id; const sent = generatedResponse.request().postDataJSON();
    expect(sent.preview_digest).toBe(filtered.preview_digest);expect(sent.request_scope.source_items).toEqual([{ key: source.key, source_digest: source.source_digest, include: false }]);
    await expect.poll(async () => (await checked(await page.request.get(`${API}/generation/${jid}`))).status).toBe('COMPLETED');
    expect((await checked(await page.request.get(`${API}/generation/${jid}`))).request_scope).toEqual(sent.request_scope);
    expect((await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).content).toBe(saved.content);
    await page.screenshot({ path: info.outputPath('u08-source-item-exclusion.png'), fullPage: true });
  } finally { await quiesce(); if (jid) await page.request.post(`${API}/generation/${jid}/cancel`); if (nid) expect([200, 204, 404]).toContain((await page.request.delete(`${API}/novels/${nid}`)).status()); }
});
