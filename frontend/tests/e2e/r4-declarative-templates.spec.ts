import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
// A06 dependency uses the same isolated trusted development profile as broker
// tests. This journey never enables a model or calls a model/generation API.
const API = 'http://127.0.0.1:8022/api';
const UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function tools(page: Page, name: string) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name, exact: true }).click();
}

test('B01/B02 local template copy, declarative authoring, original node execution, review, restart and stale-source rejection', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '';
  const forbidden: string[] = [];
  page.on('request', req => { if (req.method() === 'POST' && /\/generate|\/dispatch|\/trigger-agent|\/agent-queue\//.test(req.url())) forbidden.push(req.url()); });
  info.annotations.push({ type: 'verification', description: 'Authored real React and File API journey with original local Workflow recipes. No mocked routes, model or external service. Local Chromium NOT_RUN: known platform EPERM, not retried. Hosted run must establish its own receipt.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('B01-B02 synthetic local templates');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    const novel = await body(await creating); nid = novel.id;
    const base = `${API}/novels/${nid}/experimental`;
    const createdChapter = await body(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: '合成潮汐', content: '林舟等潮落。\n同伴举起合成地图。' } }));
    // The original editor GET initializes the File rich-document representation.
    // Compare exact authoritative content after that boundary, not the raw POST echo.
    const chapter = await body(await request.get(`${API}/chapters/${createdChapter.id}`, { headers }));
    await tools(page, '本地模板库');
    const library = page.getByRole('region', { name: '本地模板库', exact: true });
    await library.getByLabel('选择本地模板').selectOption('planning-three-act');
    await expect(library.getByRole('figure', { name: '模板结构预览' })).toContainText('CC0-1.0');
    await library.getByRole('button', { name: '收藏模板', exact: true }).click();
    await expect(library.getByRole('button', { name: '取消收藏', exact: true })).toBeVisible();
    await library.getByRole('button', { name: '填入安装预览', exact: true }).click();
    await library.getByRole('button', { name: '预检并比较目录', exact: true }).click();
    await library.getByRole('button', { name: '确认安装这个版本', exact: true }).click();
    const copiedPlanning = page.waitForResponse(r => r.url().endsWith('/template-library/instances') && r.request().method() === 'POST');
    await library.getByRole('button', { name: '复制为本项目版本', exact: true }).click();
    const planningCopy = await body(await copiedPlanning);
    const planning = await body(await request.get(`${base}/planning/templates`, { headers }));
    expect(planning.items.some((row: any) => row.id === planningCopy.linked_target.id)).toBe(true);
    await library.getByLabel('仅卸载目录记录，保留全部项目副本与已创建作品').check();
    await library.getByRole('button', { name: '卸载本地目录记录', exact: true }).click();
    const copies = await body(await request.get(`${base}/template-library/instances`, { headers }));
    expect(copies.items.some((row: any) => row.id === planningCopy.id)).toBe(true);
    await library.getByLabel('选择本地模板').selectOption('local-review-workflow');
    const copiedWorkflow = page.waitForResponse(r => r.url().endsWith('/template-library/instances') && r.request().method() === 'POST');
    await library.getByRole('button', { name: '复制为本项目版本', exact: true }).click();
    const workflowCopy = await body(await copiedWorkflow);
    await page.screenshot({ path: info.outputPath('template-library-offline-copy.png'), fullPage: true });

    await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: 'Agent 与 Workflow', exact: true }).click();
    const agents = page.getByRole('region', { name: 'Agent 与 Workflow', exact: true });
    await agents.getByLabel('已保存的 Agent 定义').selectOption(workflowCopy.linked_target.id);
    await agents.getByLabel('角色提示词').fill('整理合成素材；这段提示词不授予任何工具权限。');
    await agents.getByLabel('运行时限（秒）').fill('120');
    await agents.getByRole('button', { name: '保存 Agent 新版本', exact: true }).click();
    await expect(agents).toContainText(`已保存定义 ${workflowCopy.linked_target.id} · v2`);
    await agents.getByRole('button', { name: '验证 Workflow 图与权限', exact: true }).click();
    await expect(agents).toContainText('拓扑顺序：prepare → review → artifact');
    await agents.getByLabel('测试输入 source_text').fill('原创合成林舟寻找潮汐地图。');
    await agents.getByLabel('已核对已保存图版本、输入来源、工具范围和限额').check();
    const creatingRun = page.waitForResponse(r => /\/declarative-agents\/definitions\/[^/]+\/runs$/.test(r.url()) && r.request().method() === 'POST');
    await agents.getByRole('button', { name: '创建已核对的测试运行', exact: true }).click();
    const queued = await body(await creatingRun); expect(queued.status).toBe('QUEUED'); expect(queued.dispatch_trace).toHaveLength(0);
    await agents.getByRole('button', { name: '执行本地节点到审核点', exact: true }).click();
    await expect(agents).toContainText('状态 WAITING_APPROVAL');
    await expect(agents.getByRole('article', { name: '节点结果 prepare' })).toContainText('原创合成林舟寻找潮汐地图。');
    await expect(agents.getByRole('button', { name: '批准当前审核节点', exact: true })).toBeDisabled();
    await agents.getByLabel('已查看逐节点结果，仅批准草稿材料，不写入正文或 Canon').check();
    const approving = page.waitForResponse(r => r.url().endsWith(`/declarative-agents/runs/${queued.id}/approve`) && r.request().method() === 'POST');
    await agents.getByRole('button', { name: '批准当前审核节点', exact: true }).click();
    const completed = await body(await approving); expect(completed.status).toBe('SUCCEEDED'); expect(completed.model_called).toBe(false); expect(completed.applied).toBe(false);
    expect(completed.dispatch_trace.map((row: any) => row.node_id)).toEqual(['prepare', 'review', 'artifact']);
    expect((await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }))).content).toBe(chapter.content);
    await page.screenshot({ path: info.outputPath('declarative-original-workflow-reviewed.png'), fullPage: true });
    await quiesce.drain(); await page.reload(); await tools(page, 'Agent 与 Workflow');
    await agents.getByLabel('查看 Workflow 运行').selectOption(queued.id);
    await expect(agents).toContainText('状态 SUCCEEDED');

    // Current source/graph fences are exercised through the actual composed API.
    const definitions = await body(await request.get(`${base}/declarative-agents/definitions`, { headers }));
    const definition = definitions.items.find((row: any) => row.id === workflowCopy.linked_target.id);
    const sourced = await body(await request.post(`${base}/declarative-agents/definitions/${definition.id}/runs`, { headers, data: { expected_version: definition.version, reviewed_definition_digest: definition.definition_digest, source_version: chapter.version, chapter_ids: [chapter.id], input: {}, request_id: 'browser-current-source' } }));
    await body(await request.put(`${API}/chapters/${chapter.id}`, { headers, data: { version: chapter.version, content: '合成来源已修改。', source: 'USER' } }));
    expect((await request.post(`${base}/declarative-agents/runs/${sourced.id}/execute`, { headers, data: { expected_version: sourced.version } })).status()).toBe(409);
    await agents.getByRole('button', { name: '刷新授权目录与记录', exact: true }).click();
    await agents.getByLabel('查看 Workflow 运行').selectOption(sourced.id);
    await expect(agents).toContainText('定义或来源已变化');
    await expect(agents.getByRole('button', { name: '执行本地节点到审核点', exact: true })).toBeDisabled();
    expect(forbidden).toEqual([]);
  } finally {
    if (!page.isClosed() && info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('declarative-templates-failure.png'), fullPage: true }).catch(() => {});
    await quiesce();
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status());
  }
});
