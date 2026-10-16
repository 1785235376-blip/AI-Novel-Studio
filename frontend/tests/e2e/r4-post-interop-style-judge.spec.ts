import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
const owned = new WeakMap<Page, string[]>(), quiet = new WeakMap<Page, ReturnType<typeof createPageQuiescer>>();
async function body(response: Pick<APIResponse, 'ok' | 'status' | 'text' | 'json'>) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function editorReadsReady(page: Page, historyVersion?: number) {
  // Prose visibility alone does not establish that the original history and
  // privacy response bodies have been consumed by their mounted controls.
  const history = page.locator('.revision-panel');
  if (historyVersion === undefined) await expect(history.getByText('暂无历史版本', { exact: true })).toBeVisible();
  else await expect(history.getByRole('navigation', { name: '版本记录时间线', exact: true })).toContainText(`版本 ${historyVersion}`);
  const privacy = page.getByRole('region', { name: '正文外发策略', exact: true });
  await privacy.locator('summary').click();
  const choice = privacy.getByRole('combobox', { name: '当前章节正文与选区', exact: true });
  await expect(choice).toBeEnabled(); await expect(choice).toHaveValue('LOCAL_ONLY');
  await privacy.locator('summary').click();
}
async function createProject(page: Page, content: string) {
  await page.goto('/'); await page.getByPlaceholder('小说名称').fill(`Continuation style judge ${test.info().testId}`);
  const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click(); const novel = await (await created).json(); owned.get(page)!.push(novel.id);
  await page.getByRole('button', { name: '新建章节', exact: true }).click(); await page.getByLabel('章节标题', { exact: true }).fill('合成回环');
  const added = page.waitForResponse(r => r.url().endsWith(`/novels/${novel.id}/chapters`) && r.request().method() === 'POST');
  await page.getByRole('button', { name: '创建章节', exact: true }).click(); const createdChapter = await body(await added);
  // File chapter creation returns raw metadata; GET owns the versioned document.
  const chapter = await body(await page.request.get(`${API}/chapters/${createdChapter.id}`));
  expect(Number.isInteger(chapter.version)).toBe(true);
  await test.step('Finish original editor reads before changing the fixture source', async () => {
    await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toContainText('合成回环');
    await editorReadsReady(page);
  });
  const saved = await body(await page.request.put(`${API}/chapters/${chapter.id}`, { data: { version: chapter.version, content } }));
  await test.step('Drain existing page requests before the fixture reload', () => quiet.get(page)!.drain());
  await page.reload(); await expect(page.locator('.editorbar')).toContainText('已保存');
  await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toContainText(content.split('\n')[0]);
  await test.step('Finish reloaded history and privacy before leaving the editor', () => editorReadsReady(page, chapter.version));
  expect(await body(await page.request.get(`${API}/chapters/${chapter.id}`))).toEqual(saved);
  return { novel, chapter: saved, base: `${API}/novels/${novel.id}/experimental` };
}
async function tools(page: Page, tab: string) {
  await page.getByRole('button', { name: /功能导航/ }).first().click(); const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: tab, exact: true }).click();
}
test.beforeEach(({ page }) => { owned.set(page, []); quiet.set(page, createPageQuiescer(page)); page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss()); test.info().annotations.push({ type: 'verification', description: 'Synthetic saved sources, real production File API and React controls. No HTTP mocks or model calls. Hosted Chromium required; known local platform block not retried.' }); });
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('continuation-judge-failure.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!(); for (const id of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${id}`)).status());
});
test('intentional decisions suppress a fresh exact-evidence finding while saved original-room revision tasks persist', async ({ page }, info) => {
  const original = '她把灯留在门边，等待夜航的船只返回。\n\n她把灯留在门边，等待夜航的船只返回。';
  const { chapter, base } = await createProject(page, original); await tools(page, '作品审稿'); const panel = page.getByRole('region', { name: '叙事证据审阅', exact: true });
  const started = page.waitForResponse(r => r.url().endsWith('/narrative-judge/runs') && r.request().method() === 'POST'); await panel.getByRole('button', { name: '检查所选已保存章节', exact: true }).click(); const first = await (await started).json(); const finding = first.findings[0];
  const article = panel.getByRole('article', { name: `检查线索 ${finding.id}`, exact: true }); await article.getByRole('button', { name: '准备修订任务', exact: true }).click();
  await article.getByLabel(`修订任务标题 ${finding.id}`, { exact: true }).fill('核对合成回环'); await article.getByLabel(`修订负责人 ${finding.id}`, { exact: true }).selectOption('local-author'); await article.getByLabel(`修订审核人 ${finding.id}`, { exact: true }).selectOption('local-author');
  const created = page.waitForResponse(r => r.url().endsWith(`/findings/${finding.id}/revision-task`) && r.request().method() === 'POST'); await article.getByRole('button', { name: '明确创建修订任务', exact: true }).click(); const task = (await (await created).json()).task; await expect(article).toContainText('已保存任务：核对合成回环');
  await article.getByLabel(`审核理由 ${finding.id}`, { exact: true }).fill('有意的回环，不要再次提示相同证据。'); await article.getByRole('button', { name: '标为有意安排，不再重复提示', exact: true }).click(); await expect(article).toBeHidden();
  await expect(panel.getByText('有意安排的重复线索已收起。选择“有意安排”可查看或重新打开。')).toBeVisible(); expect((await body(await page.request.get(`${base}/review-inbox?domain=narrative_judge`))).items).toHaveLength(0);
  // Compare the complete authoritative saved document, including serializer
  // whitespace and version, rather than the pre-serialization input string.
  const room = await body(await page.request.get(`${base}/writer-room`)); expect(room.items.some((row: { id: string }) => row.id === task.id)).toBe(true); expect(await body(await page.request.get(`${API}/chapters/${chapter.id}`))).toEqual(chapter);
  const current = await body(await page.request.put(`${API}/chapters/${chapter.id}`, { data: { version: chapter.version, content: '新加入的无关开头。\n\n' + original } })); await panel.getByRole('button', { name: '刷新审阅与来源（保留输入）', exact: true }).click(); await expect(panel.getByText('历史结果已隐藏', { exact: false })).toBeVisible();
  const rerun = page.waitForResponse(r => r.url().endsWith('/narrative-judge/runs') && r.request().method() === 'POST'); await panel.getByRole('button', { name: '检查所选已保存章节', exact: true }).click(); const fresh = await (await rerun).json(); expect(fresh.findings[0].decision).toBe('INTENTIONAL'); expect(fresh.findings[0].evidence[0].chapter_version).toBe(current.version);
  await panel.getByLabel('按审核决定筛选', { exact: true }).selectOption('INTENTIONAL'); const inherited = panel.getByRole('article', { name: `检查线索 ${fresh.findings[0].id}`, exact: true }); await expect(inherited).toBeVisible(); await expect(inherited).toContainText('旧检查的私人理由未复制');
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) { await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready); expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true); await page.screenshot({ path: info.outputPath(`intentional-review-${width}.png`) }); }
  await test.step('Drain existing page requests before reopening persisted intentional decisions', () => quiet.get(page)!.drain());
  await page.reload();
  await test.step('Finish persisted chapter history and privacy before reopening Judge', () => editorReadsReady(page, chapter.version));
  await tools(page, '作品审稿'); await panel.getByLabel('查看审阅记录', { exact: true }).selectOption(fresh.id); await panel.getByLabel('按审核决定筛选', { exact: true }).selectOption('INTENTIONAL'); await expect(panel.getByRole('article', { name: `检查线索 ${fresh.findings[0].id}`, exact: true })).toBeVisible();
});
test('two saved style samples retain independent sentence counts and native source positions', async ({ page }) => {
  const { novel, chapter, base } = await createProject(page, 'First unfinished sample'); const createdSecond = await body(await page.request.post(`${API}/novels/${novel.id}/chapters`, { data: { title: '第二份合成样本', content: 'Second unfinished sample' } }));
  const second = await body(await page.request.get(`${API}/chapters/${createdSecond.id}`)); expect(Number.isInteger(second.version)).toBe(true);
  await tools(page, '风格档案'); const panel = page.getByRole('region', { name: '文风分析与档案', exact: true }); await panel.getByLabel('风格档案标题', { exact: true }).fill('独立来源测量'); await panel.getByLabel('可复用风格指令（最多 120 字）', { exact: true }).fill('Use concrete nouns.');
  await panel.getByRole('checkbox', { name: `档案来源：${chapter.title} · v${chapter.version}`, exact: true }).check(); await panel.getByRole('checkbox', { name: `档案来源：${second.title} · v${second.version}`, exact: true }).check();
  const created = page.waitForResponse(r => r.url().endsWith('/style-analysis/profiles') && r.request().method() === 'POST'); await panel.getByRole('button', { name: '保存风格草稿', exact: true }).click(); const profile = await (await created).json();
  await panel.getByLabel('分析与预览的风格档案', { exact: true }).selectOption(profile.id); await panel.getByLabel('分析语言', { exact: true }).selectOption('en'); await panel.getByRole('checkbox', { name: `分析样本：${chapter.title} · v${chapter.version}`, exact: true }).check(); await panel.getByRole('checkbox', { name: `分析样本：${second.title} · v${second.version}`, exact: true }).check();
  const analyzed = page.waitForResponse(r => r.url().endsWith('/style-analysis/analyses') && r.request().method() === 'POST'); await panel.getByRole('button', { name: '分析所选已保存样本', exact: true }).click(); const report = await (await analyzed).json(); expect(report.metrics.sentence_count).toBe(2); expect(report.sample_metrics).toHaveLength(2); expect(report.model_opinion_state).toBe('NOT_REQUESTED');
  await expect(panel.getByText('Deterministic Metric · 确定性测量', { exact: true })).toBeVisible(); await expect(panel.getByText(/Model Opinion：尚未请求模型意见/)).toBeVisible(); await panel.getByText('来源样本 1 的独立测量与原文位置', { exact: true }).click(); await expect(panel.getByLabel('样本 1 段落 1 原文', { exact: true })).toHaveValue('First unfinished sample');
  const repeated = page.waitForResponse(r => r.url().endsWith('/style-analysis/analyses') && r.request().method() === 'POST'); await panel.getByRole('button', { name: '分析所选已保存样本', exact: true }).click(); expect((await (await repeated).json()).id).toBe(report.id); expect((await body(await page.request.get(`${base}/style-analysis/analyses`))).items).toHaveLength(1);
});
