import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
const originals = ['甲🙂é拿起灯。', '乙保留加粗。', '丙回望港口。'];
const doc = { type: 'doc', content: originals.map((text, i) => ({ type: 'paragraph', content: [{ type: 'text', text, ...(i === 1 ? { marks: [{ type: 'bold' }] } : {}) }] })) };
async function checked(response: APIResponse): Promise<any> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json();
}
async function open(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '选区修订与保护', exact: true }).click();
}

test('J03 actual File UI: stale patch rejected, reselected two-block adoption preserves the unapproved rich paragraph and immutable history', async ({ page }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '';
  const calls: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /\/(?:author-context\/generate|generate\/)/.test(request.url())) calls.push(request.url()); });
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  info.annotations.push({ type: 'verification', description: 'Authored real local File/React journey; no response mocks/model calls. Browser execution NOT_RUN where Chromium EPERM is known. Does not establish model quality.' });
  try {
    await page.goto('/');
    await page.getByPlaceholder('小说名称').fill(`R4 revision synthetic ${info.testId}`);
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    nid = (await checked(await created)).id;
    await page.getByRole('button', { name: '新建章节', exact: true }).click();
    await page.getByLabel('章节标题', { exact: true }).fill('合成修订');
    const added = page.waitForResponse(r => r.url().endsWith(`/novels/${nid}/chapters`) && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建章节', exact: true }).click();
    const empty = await checked(await added);
    let chapter = await checked(await page.request.put(`${API}/chapters/${empty.id}`, { data: { version: empty.version, document: doc } }));
    const base = `${API}/novels/${nid}/experimental/revisions`;
    // Prepare an actual draft from exact server catalog anchors, then exercise
    // stale rejection through the mounted React review UI.
    const catalog = await checked(await page.request.get(base + '/catalog?chapter_id=' + encodeURIComponent(chapter.id)));
    const selection = { chapter_id: chapter.id, chapter_version: chapter.version, from_pos: catalog.blocks[0].from_pos, to_pos: catalog.blocks[2].to_pos, text: originals.join('\n') };
    const captured = await checked(await page.request.post(base + '/selection', { data: selection }));
    await checked(await page.request.post(base + '/proposals', { data: { selection, selection_digest: captured.selection_digest, replacements: captured.blocks.map((b: any, i: number) => ({ anchor_id: b.anchor_id, text: originals[i] + '初稿改' })) } }));
    await page.reload(); await open(page);
    await page.getByRole('button', { name: '审核此修订', exact: true }).click();
    await page.getByLabel('区块 1 决定', { exact: true }).selectOption('accept');
    const externallyChanged = { ...doc, content: doc.content.map((node, i) => i === 0 ? { ...node, content: [{ type: 'text', text: '外部新版本🙂é' }] } : node) };
    chapter = await checked(await page.request.put(`${API}/chapters/${chapter.id}`, { data: { version: chapter.version, document: externallyChanged } }));
    await page.getByRole('button', { name: '预览所选区块与检查点', exact: true }).click();
    await expect(page.getByRole('alert').filter({ hasText: /版本或来源已改变/ })).toBeVisible();
    expect((await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).document).toEqual(externallyChanged);
    await page.reload();
    // Capture real TipTap selection with Chinese, emoji, combining characters.
    const editor = page.locator('.ProseMirror'); await expect(editor).toContainText('外部新版本');
    await editor.evaluate(root => { const range = document.createRange(); range.setStart(root.firstChild!.firstChild!, 0); range.setEnd(root.lastChild!.lastChild!, root.lastChild!.lastChild!.textContent!.length); const selection = window.getSelection()!; selection.removeAllRanges(); selection.addRange(range); document.dispatchEvent(new Event('selectionchange')); });
    await page.getByRole('button', { name: '修订选区与逐段接受', exact: true }).click();
    await page.getByRole('button', { name: '校验编辑器选区', exact: true }).click();
    await page.getByLabel('区块 1 候选文字', { exact: true }).fill('批准第一段🙂é');
    await page.getByLabel('区块 2 候选文字', { exact: true }).fill('候选第二段但不批准');
    await page.getByLabel('区块 3 候选文字', { exact: true }).fill('批准第三段。');
    await page.getByRole('button', { name: '保存候选并逐项审核', exact: true }).click();
    await page.getByLabel('区块 1 决定', { exact: true }).selectOption('accept');
    await page.getByLabel('区块 3 决定', { exact: true }).selectOption('accept');
    await page.getByRole('button', { name: '预览所选区块与检查点', exact: true }).click();
    await expect(page.getByRole('button', { name: '确认仅应用所选决定', exact: true })).toBeDisabled();
    await page.getByLabel('已核对所选区块与原版本检查点').check();
    await page.getByRole('button', { name: '确认仅应用所选决定', exact: true }).click();
    await expect.poll(async () => (await checked(await page.request.get(`${API}/chapters/${chapter.id}`))).version).toBe(chapter.version + 1);
    const final = await checked(await page.request.get(`${API}/chapters/${chapter.id}`));
    expect(final.document.content[0].content[0].text).toBe('批准第一段🙂é');
    expect(final.document.content[1]).toEqual(doc.content[1]);
    expect(final.document.content[2].content[0].text).toBe('批准第三段。');
    const originalHistory = await checked(await page.request.get(`${API}/chapters/${chapter.id}/history`));
    const rows = Array.isArray(originalHistory) ? originalHistory : originalHistory.items;
    expect(rows.find((row: any) => row.version === chapter.version).document).toEqual(externallyChanged);
    expect(calls).toEqual([]);
    await page.screenshot({ path: info.outputPath('revision-two-block-review.png'), fullPage: true });
  } finally {
    await quiesce(); if (nid) expect([200, 204, 404]).toContain((await page.request.delete(`${API}/novels/${encodeURIComponent(nid)}`)).status());
  }
});
