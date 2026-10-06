import { readFile } from 'node:fs/promises';
import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function workspace(page: Page, name: string) {
  if (!(await page.getByRole('navigation', { name: '实验功能' }).isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  }
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name, exact: true }).click();
}
async function createNovel(page: Page, api: string, title: string) {
  await page.getByPlaceholder('小说名称').fill(title);
  const response = page.waitForResponse(r => r.url() === `${api}/novels` && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click(); return body(await response);
}
test('Wave 5: extended read-only templates instantiate an original Agent with durable SDK contract and no dispatch', async ({ page, request }, info) => {
  const api = 'http://127.0.0.1:8022/api', headers = { 'X-Session-Token': 'r4-broker-test-session' };
  const quiet = createPageQuiescer(page); let nid = ''; const dispatch: string[] = [];
  page.on('request', req => { if (req.method() === 'POST' && /\/generate|\/dispatch|\/execute|\/runs$/.test(req.url())) dispatch.push(req.url()); });
  info.annotations.push({ type: 'verification', description: 'Real React/File API hosted journey. Local browser NOT_RUN (known platform block, not retried). No model or third-party executable calls.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto('http://127.0.0.1:5182');
    nid = (await createNovel(page, api, `Wave5 templates ${info.testId}`)).id;
    await workspace(page, '本地模板库'); const library = page.getByRole('region', { name: '本地模板库', exact: true });
    const catalog = await body(await request.get(`${api}/novels/${nid}/experimental/template-library`, { headers }));
    expect(catalog.items).toHaveLength(9); expect(catalog.extended_items).toHaveLength(5); expect(catalog.permission_grants).toEqual([]);
    for (const type of ['novel', 'genre', 'world', 'agent', 'story_structure']) {
      await library.getByLabel('模板类型', { exact: true }).selectOption(type);
      const entry = catalog.extended_items.find((r: any) => r.package.manifest.type === type);
      await library.getByLabel('选择本地模板').selectOption(entry.id); await expect(library).toContainText('只读声明导入');
    }
    await library.getByLabel('模板类型', { exact: true }).selectOption('agent'); await library.getByLabel('选择本地模板').selectOption('synthetic-agent');
    const copying = page.waitForResponse(r => r.url().endsWith('/template-library/instances') && r.request().method() === 'POST');
    await library.getByRole('button', { name: '复制为本项目版本' }).click(); const copied = await body(await copying);
    expect(copied.linked_target.feature).toBe('declarative_agents_v2');
    await workspace(page, 'Agent 与 Workflow'); const agents = page.getByRole('region', { name: 'Agent 与 Workflow', exact: true });
    await agents.getByLabel('已保存的 Agent 定义').selectOption(copied.linked_target.id);
    await expect(agents.getByLabel('Adapter 运行时要求')).toHaveValue('TRUSTED_IN_PROCESS_LOCAL');
    await expect(agents.getByLabel('LOCAL_RULES', { exact: true })).toBeChecked();
    await agents.getByRole('button', { name: '验证 Workflow 图与权限' }).click();
    await expect(agents.getByText('Adapter 能力、运行时与 Schema 合约')).toBeVisible();
    const definitions = await body(await request.get(`${api}/novels/${nid}/experimental/declarative-agents/definitions`, { headers }));
    expect(definitions.items.find((r: any) => r.id === copied.linked_target.id).definition.agent.review_required).toBe(true);
    await quiet.drain(); await page.reload(); await workspace(page, 'Agent 与 Workflow');
    await agents.getByLabel('已保存的 Agent 定义').selectOption(copied.linked_target.id);
    await expect(agents.getByLabel('Adapter 运行时要求')).toHaveValue('TRUSTED_IN_PROCESS_LOCAL');
    expect(dispatch).toEqual([]);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) { await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); await page.screenshot({ path: info.outputPath(`wave5-sdk-${width}.png`) }); }
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${api}/novels/${nid}`, { headers })).status()); }
});

test('Wave 5: comic image brief, character appearance, scene chain, restart and source invalidation', async ({ page, request }, info) => {
  const api = 'http://127.0.0.1:8019/api'; const quiet = createPageQuiescer(page); let nid = ''; const dispatch: string[] = [];
  page.on('request', req => { if (req.method() === 'POST' && /\/generate|\/dispatch|\/execute/.test(req.url())) dispatch.push(req.url()); });
  info.annotations.push({ type: 'verification', description: 'Real React/File API original approved synthetic assets. No model, final-artwork or local-browser verification claim.' });
  try {
    await page.goto('http://127.0.0.1:5179'); nid = (await createNovel(page, api, `Wave5 comic ${info.testId}`)).id;
    const base = `${api}/novels/${nid}`;
    await body(await request.post(`${base}/chapters`, { data: { title: 'Synthetic scene', content: 'Alice studies a tide map.' } }));
    await body(await request.put(`${base}/characters/alice`, { data: { name: 'Alice', personality: 'Careful' } }));
    let source = await body(await request.post(`${base}/screenplays`, { data: { title: 'Wave5 source' } }));
    source = await body(await request.post(`${base}/screenplays/${source.id}/approve`, { data: { expected_version: source.edit_version } }));
    source = await body(await request.post(`${base}/screenplays/${source.id}/shots`, { data: { expected_version: source.edit_version } }));
    const bytes = await readFile('tests/e2e/fixtures/r5-comic-SYNTHETIC-TEST-ASSET.png');
    const asset = await body(await request.post(`${base}/assets`, { data: { novel_id: nid, filename: 'SYNTHETIC-APPEARANCE.png', content_base64: bytes.toString('base64'), media_type: 'image/png' } }));
    const approved = await body(await request.post(`${base}/experimental/comic-layouts/images/${asset.id}/approve`, { data: { expected_version: asset.version } }));
    await workspace(page, '漫画与 Webtoon'); const comic = page.getByRole('region', { name: '漫画与 Webtoon 排版', exact: true });
    await comic.getByLabel('漫画来源剧本').selectOption(source.id);
    await comic.getByLabel('格框 1 已批准图片').selectOption(asset.id);
    await comic.getByLabel('格框 1 关联人物').selectOption('alice');
    await comic.getByLabel('格框 1 图片简报').fill('Alice studies a tide map; preserve her blue coat.');
    await comic.getByLabel('格框 1 Alice 外观参考').selectOption(asset.id);
    await comic.getByLabel('格框 1 Alice 外观说明').fill('Approved synthetic appearance reference.');
    const saving = page.waitForResponse(r => r.url().endsWith('/comic-layouts/records') && r.request().method() === 'POST');
    await comic.getByRole('button', { name: '保存漫画布局草稿' }).click(); const row = await body(await saving);
    expect(row.document.panels[0].appearance_references[0]).toMatchObject({ character_id: 'alice', asset_id: asset.id, expected_asset_version: approved.version });
    expect(row.scene_ids[row.document.panels[0].id]).toBe(source.shots[0].scene_id);
    await quiet.drain(); await page.reload(); await workspace(page, '漫画与 Webtoon');
    await comic.getByRole('button', { name: `打开布局 ${row.document.title}`, exact: true }).click();
    await expect(comic.getByLabel('格框 1 图片简报')).toHaveValue('Alice studies a tide map; preserve her blue coat.');
    await expect(comic.getByLabel('格框 1 Alice 外观参考')).toHaveValue(asset.id);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) { await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true); await page.screenshot({ path: info.outputPath(`wave5-comic-${width}.png`) }); }
    await body(await request.put(`${base}/characters/alice`, { data: { name: 'Alice', personality: 'Changed current characterization' } }));
    await comic.getByRole('button', { name: '刷新漫画来源与记录' }).click();
    await expect(comic).toContainText('来源、授权或图片已变化');
    await expect(comic.getByLabel('格框 1 图片简报')).toHaveCount(0);
    const records = await body(await request.get(`${base}/experimental/comic-layouts/records`));
    expect(records.items[0].stale).toBe(true); expect(records.items[0].document).toBeUndefined();
    expect((await request.post(`${base}/experimental/comic-layouts/records/${row.id}/preflight`, { data: { expected_version: row.version } })).status()).toBe(409);
    expect(dispatch).toEqual([]);
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${api}/novels/${nid}`)).status()); }
});
