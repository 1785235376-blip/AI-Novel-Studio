import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function checked(response: APIResponse): Promise<any> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json();
}
async function openSearch(page: Page, kind: string, title: string) {
  await page.keyboard.press('Control+k');
  const search = page.getByRole('region', { name: '工作现场工具', exact: true });
  await search.getByLabel('内容类型', { exact: true }).selectOption(kind);
  await search.getByLabel('搜索中文名称、别名或正文').fill(title);
  await search.getByRole('button', { name: '打开资料库来源', exact: true }).click();
}
async function selectProject(page: Page, url: string, title: string) {
  await page.goto(url);
  await page.getByRole('button', { name: '切换本机作品', exact: true }).click();
  await page.getByRole('button', { name: title, exact: true }).click();
  await expect(page.locator('.ProseMirror')).toBeVisible();
}

test('U03 structured results focus original world, rule, graph and asset records without mutations', async ({ page, request }, info) => {
  let nid = ''; const quiet = createPageQuiescer(page), executions: string[] = [];
  page.on('request', value => { if (value.method() === 'POST' && /\/(?:generate|dispatch|approve|reject)$/.test(value.url())) executions.push(value.url()); });
  try {
    const novel = await checked(await request.post(`${API}/novels`, { data: { title: `Structured search ${Date.now()}` } })); nid = novel.id;
    const created = await checked(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: '原资料来源', content: '合成测试正文，导航不会改写。' } }));
    // File creation returns legacy metadata; the original document read owns CAS.
    const chapter = await checked(await request.get(`${API}/chapters/${created.id}`));
    expect(Number.isInteger(chapter.version)).toBe(true); expect(chapter.version).toBeGreaterThanOrEqual(1);
    const base = `${API}/novels/${nid}/experimental`;
    for (const [kind, title] of [['CIVILIZATION', '星桥组织精确来源'], ['ABILITY', '记忆能力精确来源']])
      await checked(await request.post(base + '/world/records', { data: { kind, title, data: { name: title } } }));
    await checked(await request.post(base + '/story-graph/records', { data: { kind: 'STORY_CONCEPT', title: '铜钥图谱精确来源', chapter_id: chapter.id, data: { concept_type: 'OBJECT', description: '不索引的合成图谱正文' } } }));
    const evidence = await checked(await request.post(`${API}/novels/${nid}/lore/evidence`, { data: { source_id: 'structured-search-fixture', excerpt: '合成规则证据' } }));
    await checked(await request.post(`${API}/novels/${nid}/world-rules`, { data: { payload: { statement: '过桥规则精确来源', forbidden_terms: [] }, relations: [{ evidence_id: evidence.id, relevance: 'PRIMARY' }] } }));
    await checked(await request.post(`${API}/novels/${nid}/assets`, { data: { novel_id: nid, filename: '原资产精确来源.txt', content_base64: 'U1lOVEhFVElD', media_type: 'text/plain', kind: 'file' } }));
    await selectProject(page, '/', novel.title);
    const sources = [['organization', '星桥组织精确来源', '世界记录 星桥组织精确来源'], ['rule', '记忆能力精确来源', '世界记录 记忆能力精确来源'], ['rule', '过桥规则精确来源', '世界规则 过桥规则精确来源'], ['story_graph', '铜钥图谱精确来源', '图谱记录 铜钥图谱精确来源'], ['asset', '原资产精确来源', '资产 原资产精确来源.txt']];
    for (const [kind, title, label] of sources) {
      await openSearch(page, kind, title);
      const original = page.getByRole('article', { name: label, exact: true });
      await expect(original).toHaveAttribute('aria-current', 'true'); await expect(original).toBeFocused();
      await page.screenshot({ path: info.outputPath(`u03-original-${kind}-${sources.findIndex(row => row[1] === title)}.png`), fullPage: true });
    }
    const afterNavigation = await checked(await request.get(`${API}/chapters/${chapter.id}`));
    expect(afterNavigation.version).toBe(chapter.version);
    expect(afterNavigation.content).toBe(chapter.content);
    expect(executions).toEqual([]);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBe(0);
      await page.screenshot({ path: info.outputPath(`u03-original-asset-${width}.png`), fullPage: true });
    }
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status()); }
});

test('U03 workflow definitions reopen their exact original owner without creating a run', async ({ page, request }, info) => {
  const api = 'http://127.0.0.1:8022/api', headers = { 'X-Session-Token': 'r4-broker-test-session' };
  let nid = ''; const quiet = createPageQuiescer(page), executions: string[] = [];
  page.on('request', value => { if (value.method() === 'POST' && /\/workflows\/[^/]+\/runs$/.test(value.url())) executions.push(value.url()); });
  try {
    await page.setExtraHTTPHeaders(headers);
    const novel = await checked(await request.post(`${api}/novels`, { headers, data: { title: `Search workflow ${Date.now()}` } })); nid = novel.id;
    await checked(await request.post(`${api}/novels/${nid}/chapters`, { headers, data: { title: '原流程来源', content: '合成流程正文。' } }));
    const definition = await checked(await request.post(`${api}/workflows`, { headers, data: { novel_id: nid, title: '原审批流程精确来源', nodes: [{ id: 'gate', type: 'manual_approval', name: 'Review', config: {} }], edges: [] } }));
    await selectProject(page, 'http://127.0.0.1:5182', novel.title);
    await openSearch(page, 'workflow', definition.title);
    await expect(page.getByLabel(`工作流定义 ${definition.title}`, { exact: true })).toBeFocused();
    await expect(page.getByRole('region', { name: '工作流运行记录' })).toContainText(definition.title);
    expect((await checked(await request.get(`${api}/workflows/${definition.id}/runs`, { headers }))).items).toEqual([]);
    expect(executions).toEqual([]);
    await page.screenshot({ path: info.outputPath('u03-original-workflow-definition.png'), fullPage: true });
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${api}/novels/${nid}`, { headers })).status()); }
});
