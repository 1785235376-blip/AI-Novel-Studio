import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { inflateRawSync } from 'node:zlib';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function checked(response: APIResponse): Promise<any> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json();
}
async function open(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '互动故事与导出', exact: true }).click();
}
test('B07 real File/React author choices, verify two endings, exact review, independent ZIP and stale-source fence', async ({ page }, info) => {
  const quiesce = createPageQuiescer(page); let nid = ''; const modelCalls: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /\/(?:author-context\/generate|generate\/)/.test(request.url())) modelCalls.push(request.url()); });
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  info.annotations.push({ type: 'verification', description: 'Authored real File/React B07 journey, no response mocks or models. Local Chromium launch EPERM established, not retried. Target RenPy runtime NOT_RUN. Hosted run must be observed before PASS.' });
  try {
    await page.goto('/'); await page.getByPlaceholder('小说名称').fill(`B07 synthetic ${info.testId}`);
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await checked(await created)).id;
    const createdChapter = await checked(await page.request.post(`${API}/novels/${nid}/chapters`, { data: { title: '合成互动来源', content: '阿青来到城门。这里将分成两条剧情路线。' } }));
    // Capture the original editor's normalized, versioned baseline before derived work.
    const chapter = await checked(await page.request.get(`${API}/chapters/${createdChapter.id}`));
    const originalHistory = await checked(await page.request.get(`${API}/chapters/${chapter.id}/history`));
    const base = `${API}/novels/${nid}/experimental`;
    const graph = await checked(await page.request.post(base + '/planning/graphs', { data: { title: '合成城门入口', links: { chapter_ids: [chapter.id] } } }));
    const endings: any[] = [];
    for (const title of ['港口节点', '山岭节点']) endings.push(await checked(await page.request.post(base + '/planning/nodes', { data: { graph_id: graph.id, parent_id: graph.root_node_id, level: 'VOLUME', title } })));
    await page.reload(); await open(page);
    await page.getByLabel('互动故事名称', { exact: true }).fill('两条合成结局');
    await page.getByLabel('原规划图', { exact: true }).selectOption(graph.id);
    for (const name of ['合成城门入口', '港口节点', '山岭节点']) await page.getByLabel(name, { exact: true }).check();
    await page.getByRole('button', { name: '创建互动改编', exact: true }).click();
    await expect(page.getByLabel('对白或叙述', { exact: true })).toBeVisible();
    await page.getByLabel('对白或叙述', { exact: true }).fill('请选择 “[literal]” {plain} 〖ruby🙂é');
    await page.getByLabel('新变量名称', { exact: true }).fill('trusted');
    await page.getByLabel('变量初始值', { exact: true }).selectOption('true');
    await page.getByRole('button', { name: '添加有界变量', exact: true }).click();
    await page.getByRole('button', { name: '添加互动选择', exact: true }).click();
    await page.getByLabel('选择 1 文案', { exact: true }).fill('去港口');
    await page.getByLabel('选择 1 目标', { exact: true }).selectOption(endings[0].id);
    await page.getByLabel('选择 1 条件', { exact: true }).fill('trusted');
    await page.getByRole('button', { name: '添加互动选择', exact: true }).click();
    await page.getByLabel('选择 2 文案', { exact: true }).fill('去山岭');
    await page.getByLabel('选择 2 目标', { exact: true }).selectOption(endings[1].id);
    for (const [index, ending] of [[1, '港口归来'], [2, '越过山岭']] as const) {
      await page.getByLabel('当前编辑节点', { exact: true }).selectOption(String(index));
      await page.getByLabel('对白或叙述', { exact: true }).fill(`这是合成结局 ${ending}🙂`);
      await page.getByLabel('结局名称（留空表示非结局）', { exact: true }).fill(ending);
    }
    await page.getByRole('button', { name: '保存互动草稿', exact: true }).click();
    await expect(page.getByText('互动草稿已保存，需要重新审核。', { exact: true })).toBeVisible();
    await expect(page.getByText('可验证结局：港口归来 · 1 次选择', { exact: true })).toBeVisible();
    await expect(page.getByText('可验证结局：越过山岭 · 1 次选择', { exact: true })).toBeVisible();
    for (const [choice, ending] of [['去港口', '港口归来'], ['去山岭', '越过山岭']]) {
      await page.getByRole('button', { name: '从开头试玩', exact: true }).click();
      await page.getByRole('button', { name: choice, exact: true }).click();
      await expect(page.getByText(`结局：${ending}`, { exact: true })).toBeVisible();
    }
    await page.getByRole('button', { name: '提交互动审核', exact: true }).click();
    await page.getByRole('button', { name: '预览互动审核', exact: true }).click();
    await page.getByRole('button', { name: '批准此互动版本', exact: true }).click();
    await page.getByRole('button', { name: '预检互动导出', exact: true }).click();
    await expect(page.getByRole('button', { name: '生成互动故事包', exact: true })).toBeDisabled();
    await page.getByLabel('已核对缺失项与兼容性损失，确认生成独立下载', { exact: true }).check();
    await page.getByRole('button', { name: '生成互动故事包', exact: true }).click();
    const link = page.getByRole('link', { name: /^下载 interactive-story-/ }); await expect(link).toBeVisible();
    const array = await link.evaluate(async node => Array.from(new Uint8Array(await (await fetch((node as HTMLAnchorElement).href)).arrayBuffer())));
    const zip = Buffer.from(array); expect(zip.readUInt32LE(0)).toBe(0x04034b50);
    const compressedLength = zip.readUInt32LE(18), nameLength = zip.readUInt16LE(26), extraLength = zip.readUInt16LE(28);
    const name = zip.subarray(30, 30 + nameLength).toString('utf8'); expect(name.endsWith('/story.json')).toBe(true); expect(name.includes('..')).toBe(false);
    const begin = 30 + nameLength + extraLength;
    const neutral = JSON.parse(inflateRawSync(zip.subarray(begin, begin + compressedLength)).toString('utf8'));
    expect(neutral.schema).toBe('ai-novel-interactive-story/1'); expect(neutral.spec.nodes[0].node_id).toBe(graph.root_node_id);
    expect(neutral.spec.nodes.filter((n: any) => n.ending).length).toBe(2);
    const unchanged = await checked(await page.request.get(`${API}/chapters/${chapter.id}`));
    expect(unchanged.version).toBe(chapter.version); expect(unchanged.content).toBe(chapter.content); expect(unchanged.document).toEqual(chapter.document);
    expect(await checked(await page.request.get(`${API}/chapters/${chapter.id}/history`))).toEqual(originalHistory);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height });
      const panel = page.locator('section[aria-label="互动故事与导出"]');
      expect(await panel.evaluate(node => node.scrollWidth <= node.clientWidth + 2)).toBe(true);
      await page.screenshot({ path: info.outputPath(`interactive-story-${width}.png`), fullPage: true });
    }
    await checked(await page.request.put(`${API}/chapters/${chapter.id}`, { data: { version: chapter.version, content: '原稿已发生改变，必须重新核对。' } }));
    await page.getByRole('button', { name: '核对当前互动版本', exact: true }).click();
    await expect(page.getByText('旧内容已停止展示和导出。', { exact: false })).toBeVisible();
    await expect(page.getByLabel('对白或叙述', { exact: true })).toHaveCount(0);
    await expect(page.getByRole('link', { name: /^下载 interactive-story-/ })).toHaveCount(0);
    expect(modelCalls).toEqual([]);
  } finally {
    await quiesce(); if (nid) expect([200, 204, 404]).toContain((await page.request.delete(`${API}/novels/${encodeURIComponent(nid)}`)).status());
  }
});
