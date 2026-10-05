import { test, expect, type Page } from '@playwright/test';
const API = 'http://127.0.0.1:8016/api';
const ownedProjects = new WeakMap<Page, { api: string; id: string }[]>();
function rememberProject(page: Page, id: string, api = API) { ownedProjects.get(page)!.push({ api, id }); }
async function body(response: any) { expect(response.ok(), await response.text()).toBeTruthy(); return response.json(); }
async function project(page: Page, text = 'Alice said hello in Harbor. One day the secret would return.') {
  const existing = await body(await page.request.get(`${API}/novels`));
  expect(existing.length, 'Isolated synthetic backend must be empty after owned-fixture teardown').toBe(0);
  await page.goto('/');
  await page.getByPlaceholder('小说名称').fill(`R3 synthetic ${Date.now()}`);
  const created = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await body(await created);
  rememberProject(page, novel.id);
  await page.getByRole('button', { name: '新建章节', exact: true }).click();
  await page.getByLabel('章节标题').fill('R3 synthetic chapter');
  const chapterResponse = page.waitForResponse(response => response.url().endsWith(`/novels/${novel.id}/chapters`) && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建章节', exact: true }).click();
  const chapter = await body(await chapterResponse);
  await page.locator('.ProseMirror').fill(text);
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('.editorbar')).toContainText('已保存');
  return { novel, chapter };
}
async function openWorkbench(page: Page, tab = '分层规划') {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('region', { name: 'Experimental 工作台' })).toBeVisible();
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: tab, exact: true }).click();
}
async function tab(page: Page, name: string) { await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name, exact: true }).click(); }
test.beforeEach(({ page }) => {
  ownedProjects.set(page, []);
  test.info().annotations.push({ type: 'verification', description: 'Actual File API + browser, synthetic fixtures. Planning/image MOCK_ONLY; no paid provider, GPU, TTS quality or literary-quality verification.' });
});
test.afterEach(async ({ page, request }) => {
  // The File app intentionally auto-opens an existing novel. Restore the empty
  // per-run fixture state after success OR failure, deleting only IDs this test
  // actually created. Never enumerate/delete another test's or user's projects.
  for (const owned of ownedProjects.get(page) || []) {
    const response = await request.delete(`${owned.api}/novels/${encodeURIComponent(owned.id)}`);
    expect([200, 204, 404], `cleanup of owned synthetic project ${owned.id}`).toContain(response.status());
  }
  ownedProjects.delete(page);
});

test('R3 default off and V1 acceptance override keep Experimental absent', async ({ page, request }) => {
  for (const port of [8017, 8018]) {
    const flags = await body(await request.get(`http://127.0.0.1:${port}/api/experimental/features`));
    expect(flags.default_enabled).toBe(false); expect(Object.values(flags.features).every(value => value === false)).toBe(true);
    expect((await request.get(`http://127.0.0.1:${port}/api/novels/unknown/experimental/planning/graphs`)).status()).toBe(404);
  }
  await page.goto('http://127.0.0.1:5177');
  await page.getByPlaceholder('小说名称').fill('V1 frozen workflow synthetic');
  const created = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  rememberProject(page, (await body(await created)).id, 'http://127.0.0.1:8017/api');
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  await expect(page.getByRole('button', { name: '实验工作台', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '版本历史', exact: true })).toBeVisible();
});

test('R3 planning browser hierarchy CRUD, compare, approval, history and stale fencing', async ({ page, request }, info) => {
  const { novel, chapter } = await project(page);
  const original = await body(await request.get(`${API}/chapters/${chapter.id}`));
  await openWorkbench(page);
  await page.getByLabel('规划名称', { exact: true }).fill('海港规划');
  await page.getByRole('button', { name: '创建项目规划', exact: true }).click();
  await expect(page.getByRole('button', { name: 'PROJECT · 海港规划' })).toBeVisible();
  await page.getByRole('button', { name: '添加 VOLUME 子节点' }).click();
  await expect(page.getByRole('heading', { name: '编辑 VOLUME' })).toBeVisible();
  await page.getByRole('button', { name: '添加 CHAPTER 子节点' }).click();
  await expect(page.getByRole('heading', { name: '编辑 CHAPTER' })).toBeVisible();
  await page.getByRole('button', { name: '添加 SCENE 子节点' }).click();
  await expect(page.getByRole('heading', { name: '编辑 SCENE' })).toBeVisible();
  await page.getByLabel('节点标题', { exact: true }).fill('场景目标');
  await page.getByLabel('目标', { exact: true }).fill('找到海港秘密');
  await page.getByRole('button', { name: '保存节点', exact: true }).click();
  await expect(page.getByText('节点已保存', { exact: true })).toBeVisible();
  await page.getByRole('combobox', { name: '规划模板', exact: true }).selectOption('multiple-endings');
  await page.getByRole('button', { name: '生成 Mock 双方案' }).click();
  const first = page.getByRole('article', { name: '方案 Mock option 1', exact: true }), second = page.getByRole('article', { name: '方案 Mock option 2', exact: true });
  await first.getByRole('checkbox').check(); await second.getByRole('checkbox').check();
  await page.getByRole('button', { name: '比较已选方案', exact: true }).click();
  await expect(page.getByRole('region', { name: '规划方案比较' })).toContainText('结局意图');
  await page.getByRole('region', { name: '规划方案比较' }).screenshot({ path: info.outputPath('planning-compare.png') });
  expect((await body(await request.get(`${API}/chapters/${chapter.id}`))).version).toBe(original.version);
  await first.getByRole('button', { name: '批准规划', exact: true }).click();
  await expect(first).toContainText('APPROVED'); await expect(second.getByRole('button', { name: '批准规划' })).toBeDisabled();
  expect((await body(await request.get(`${API}/chapters/${chapter.id}`))).content).toBe(original.content);
  await first.getByRole('button', { name: '归档方案' }).click();
  await expect(first).toContainText('ARCHIVED');
  await first.getByRole('button', { name: '方案历史' }).click();
  await page.getByRole('region', { name: '规划方案历史' }).screenshot({ path: info.outputPath('planning-history.png') });
  await page.getByRole('button', { name: '恢复历史 v1', exact: true }).click();
  await expect(first).toContainText('REVIEW'); await expect(first).toContainText('STALE');
  await page.reload(); await openWorkbench(page);
  const graphs = await body(await request.get(`${API}/novels/${novel.id}/experimental/planning/graphs`));
  const graph = await body(await request.get(`${API}/novels/${novel.id}/experimental/planning/graphs/${graphs.items[0].id}`));
  expect(graph.nodes.map((row: any) => row.level).sort()).toEqual(['CHAPTER', 'PROJECT', 'SCENE', 'VOLUME']);
  await page.getByRole('button', { name: 'SCENE · 场景目标', exact: true }).click();
  await expect(page.getByLabel('目标', { exact: true })).toHaveValue('找到海港秘密');
});

test('R3 chunked import browser pause/resume, evidence review and checkpoint commit', async ({ page, request }) => {
  const { novel } = await project(page);
  await openWorkbench(page, '长篇导入');
  await page.getByRole('button', { name: '创建分块导入', exact: true }).click();
  const job = page.getByRole('region', { name: '导入任务状态' });
  await expect(job).toContainText('QUEUED'); await page.getByRole('button', { name: '暂停导入' }).click();
  await expect(job).toContainText('PAUSED'); await page.getByRole('button', { name: '恢复导入' }).click();
  await page.getByRole('button', { name: '处理下一分块' }).click(); await expect(job).toContainText('NEEDS_REVIEW');
  const candidates = page.locator('article[aria-label^="导入候选"]'); await expect(candidates.first()).toBeVisible();
  const count = await candidates.count(); expect(count).toBeGreaterThan(0);
  for (let index = 0; index < count; index++) { await candidates.nth(index).getByText('原文证据（章节 / 版本 / offset / hash）', { exact: true }).click(); await expect(candidates.nth(index)).toContainText('chapter_id'); await candidates.nth(index).getByRole('checkbox').check(); }
  await page.getByRole('button', { name: '批量批准已选候选' }).click();
  await expect(candidates.first()).toContainText('APPROVED');
  await page.getByRole('checkbox', { name: /我已核对/ }).check(); await page.getByRole('button', { name: '提交已批准导入' }).click();
  await expect(job).toContainText('COMMITTED');
  const saved = await body(await request.get(`${API}/novels/${novel.id}/experimental/imports/jobs`));
  expect(saved.items[0].applied).toBe(true);
  await page.reload(); await openWorkbench(page, '长篇导入'); await expect(page.getByRole('region', { name: '导入任务状态' })).toContainText('COMMITTED');
});

test('R3 world browser records, unified inbox filtering/domain review and deterministic findings', async ({ page, request }, info) => {
  const { novel } = await project(page);
  await openWorkbench(page, '世界与人物');
  await page.getByLabel('世界记录标题', { exact: true }).fill('合成历史事件');
  await page.getByLabel('类型数据（JSON；真实人物 / 地点 / 规则 ID）').fill('{"time":1,"description":"港口建立","relations":[]}');
  await page.getByRole('button', { name: '创建世界候选', exact: true }).click();
  const record = page.getByRole('article', { name: '世界记录 合成历史事件' }); await expect(record).toContainText('REVIEW');
  await tab(page, '统一审核');
  await page.getByRole('combobox', { name: '审核领域', exact: true }).selectOption('world'); await page.getByLabel('搜索审核项', { exact: true }).fill('合成历史事件');
  await page.getByRole('button', { name: '筛选审核项' }).click();
  const item = page.getByRole('article', { name: /审核项 world 合成历史事件/ }); await expect(item).toContainText('source_hash'); await expect(item).toContainText('LOCAL_ONLY');
  await expect(page.getByRole('button', { name: '批量批准已选审核项' })).toBeDisabled();
  await item.getByRole('button', { name: '驳回此审核项' }).click(); await expect(item).toContainText('REJECTED');
  await item.getByRole('button', { name: '重开审核此审核项' }).click(); await item.getByRole('button', { name: '批准此审核项' }).click(); await expect(item).toContainText('APPROVED');
  await item.screenshot({ path: info.outputPath('unified-inbox-reviewed.png') });
  const canon = await body(await request.get(`${API}/novels/${novel.id}/experimental/world/canon`)); expect(canon.items).toHaveLength(1);
  await tab(page, '世界与人物'); await page.getByRole('button', { name: '检查世界连续性' }).click(); await expect(page.getByRole('region', { name: '世界连续性结果' })).toContainText('DETERMINISTIC_RULES');
});

test('R3 team Recipe browser execution remains a human-approved artifact', async ({ page, request }) => {
  const { chapter } = await project(page); const original = await body(await request.get(`${API}/chapters/${chapter.id}`));
  await openWorkbench(page, '创作团队'); await page.getByLabel('团队任务指令').fill('用合成原文验证创作流程'); await page.getByRole('button', { name: '创建团队任务' }).click();
  const run = page.getByRole('article', { name: '团队任务 outline_chapter_editor' });
  await run.getByRole('button', { name: '暂停团队任务' }).click(); await expect(run).toContainText('PAUSED');
  await run.getByRole('button', { name: '恢复团队任务' }).click(); await run.getByRole('button', { name: '执行本地 Recipe' }).click();
  await expect(run).toContainText('WAITING_APPROVAL'); expect((await body(await request.get(`${API}/chapters/${chapter.id}`))).version).toBe(original.version);
  await run.getByRole('button', { name: '人工批准团队产物' }).click(); await expect(run).toContainText('SUCCEEDED');
  await run.getByRole('button', { name: '团队执行历史' }).click(); await expect(page.getByText('团队执行历史记录', { exact: true })).toBeVisible();
  expect((await body(await request.get(`${API}/chapters/${chapter.id}`))).content).toBe(original.content);
});

test('R3 media browser registry, real mock image tasks, compare, approved lineage and honest embeddings', async ({ page, request }, info) => {
  const { novel } = await project(page);
  await openWorkbench(page, '媒体 Adapter'); await expect(page.getByRole('heading', { name: 'Qwen-Image', exact: true })).toBeVisible(); await expect(page.getByText('ADAPTER_REQUIRED', { exact: true }).first()).toBeVisible();
  await tab(page, '封面与分镜'); await page.getByLabel('封面标题', { exact: true }).fill('海港合成封面'); await page.getByLabel('封面调色板（逗号分隔）').fill('navy, sand'); await page.getByRole('button', { name: '保存封面 Brief' }).click();
  await page.getByRole('button', { name: '创建 Mock 图像任务' }).click(); await page.getByRole('button', { name: '执行 Mock 图像任务' }).click();
  const first = page.getByRole('article', { name: '媒体候选 1', exact: true }), second = page.getByRole('article', { name: '媒体候选 2', exact: true });
  await expect(first.getByRole('img')).toBeVisible(); await first.getByRole('checkbox').check(); await second.getByRole('checkbox').check();
  await page.getByRole('button', { name: '比较已选媒体候选' }).click(); await expect(page.getByRole('region', { name: '媒体候选比较' }).getByRole('img')).toHaveCount(2);
  await page.getByRole('region', { name: '媒体候选比较' }).screenshot({ path: info.outputPath('media-mock-comparison.png') });
  const before = await body(await request.get(`${API}/novels/${novel.id}/assets`)); expect(before).toHaveLength(0);
  await first.getByRole('button', { name: '批准媒体为资产' }).click(); await expect(first).toContainText('APPROVED');
  const assets = await body(await request.get(`${API}/novels/${novel.id}/assets`)); expect(assets).toHaveLength(1);
  const proposals = await body(await request.get(`${API}/novels/${novel.id}/experimental/media/proposals`)); expect(proposals.items.find((row: any) => row.status === 'APPROVED').lineage.verification).toBe('MOCK_ONLY');
  await tab(page, '视觉 Embedding'); await expect(page.getByText('NOT_CONFIGURED', { exact: true })).toBeVisible(); await expect(page.getByRole('button', { name: '查询向量' })).toBeDisabled();
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
    const geometry = await page.evaluate(() => { const box = (selector: string) => document.querySelector(selector)!.getBoundingClientRect(); const panel = document.querySelector('.experimental-workbench')!; return { header: box('.global-header').height, context: box('.context-bar').height, sidebar: box('.workspace-sidebar').width, inspector: box('.workspace-inspector').width, status: box('.status-bar').height, overflow: panel.scrollWidth - panel.clientWidth, pageOverflow: document.documentElement.scrollWidth - innerWidth }; });
    expect(geometry).toEqual({ header: 56, context: 44, sidebar: 248, inspector: 340, status: 32, overflow: 0, pageOverflow: 0 });
    await page.screenshot({ path: info.outputPath(`experimental-${width}x${height}.png`), fullPage: true });
  }
});

test('R3 audiobook browser ambiguous attribution, voices, timeline and unmeasured manifest', async ({ page, request }, info) => {
  const { novel } = await project(page, '她低声说：“去海港。”');
  await body(await request.put(`${API}/novels/${novel.id}/characters/char-r3`, { data: { id: 'char-r3', name: 'Alice', aliases: [] } }));
  await openWorkbench(page, '有声书 V2');
  for (const [label, value] of [['声音 Profile 名称', 'Synthetic voice'], ['声音 Provider ID', 'mock-provider'], ['声音 Model ID', 'mock-model'], ['Voice ID', 'mock-voice'], ['声音许可说明', 'Synthetic fixture only; no real voice or TTS run']]) await page.getByLabel(label, { exact: true }).fill(value);
  await page.getByRole('button', { name: '保存声音 Profile' }).click(); await page.getByRole('button', { name: '保存人物声音映射' }).click();
  await page.getByRole('button', { name: '创建对白序列计划' }).click(); const plan = page.getByRole('region', { name: '有声计划详情' });
  const dialogue = plan.getByRole('article', { name: '有声片段 DIALOGUE' }); await expect(dialogue).toContainText('NEEDS_REVIEW'); await expect(page.getByRole('button', { name: '批准有声计划' })).toBeDisabled();
  await dialogue.getByLabel('片段人物 ID（旁白为 __narrator__）').fill('char-r3'); await dialogue.getByRole('combobox', { name: '片段声音 Profile', exact: true }).selectOption({ label: 'Synthetic voice' }); await dialogue.getByRole('checkbox', { name: '已人工核对白归属' }).check(); await dialogue.getByRole('button', { name: '保存片段归属与风格' }).click();
  await expect(dialogue).toContainText('REVIEWED'); await page.getByLabel('轨道名称', { exact: true }).fill('合成环境轨道槽'); await page.getByRole('button', { name: '添加混音轨道槽位' }).click();
  await page.getByRole('button', { name: '查看时长清单' }).click(); await expect(page.getByText('实测时长清单', { exact: true })).toBeVisible(); await expect(plan).toContainText('UNMEASURED'); await expect(page.getByRole('button', { name: '查看片段字幕' })).toBeDisabled();
  await page.getByRole('button', { name: '批准有声计划' }).click(); await expect(plan).toContainText('APPROVED');
  await dialogue.screenshot({ path: info.outputPath('audiobook-reviewed-attribution.png') });
  const plans = await body(await request.get(`${API}/novels/${novel.id}/experimental/audiobook/plans`)); expect(plans.items[0].duration_ms).toBeNull(); expect(plans.items[0].tracks).toHaveLength(1);
});
