import { expect, test, type APIRequestContext, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';

const API = 'http://127.0.0.1:8019/api';
const chapterTitle = '夜港手记';
const refrain = '她把灯留在门边，等待夜航的船只返回。';
const originalProse = `# 合成测试场景\n\n${refrain}\n\n${refrain}`;
const owned = new WeakMap<Page, string[]>();
const quiet = new WeakMap<Page, () => Promise<void>>();
const modelRequests = new WeakMap<Page, string[]>();
type SavedChapter = { id: string; version: number; title: string; content: string };
async function body<T = any>(response: Pick<APIResponse, 'ok' | 'status' | 'text' | 'json'>): Promise<T> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy();
  return response.json();
}
async function project(page: Page) {
  await page.goto('/');
  await page.getByPlaceholder('小说名称').fill(`R4 style judge synthetic ${test.info().testId}`);
  const created = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const novel = await body(await created); owned.get(page)!.push(novel.id);
  await page.getByRole('button', { name: '新建章节', exact: true }).click();
  await page.getByLabel('章节标题', { exact: true }).fill(chapterTitle);
  const added = page.waitForResponse(response => response.url().endsWith(`/novels/${novel.id}/chapters`) && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建章节', exact: true }).click();
  const empty = await body<SavedChapter>(await added);
  // Seed real, saved Markdown through the ordinary versioned chapter endpoint.
  // It includes a heading so raw source offsets cannot be mistaken for editor offsets.
  const chapter = await body<SavedChapter>(await page.request.put(`${API}/chapters/${empty.id}`, { data: { version: empty.version, content: originalProse } }));
  await page.reload();
  await expect(page.locator('.ProseMirror')).toContainText(refrain);
  await expect(page.locator('.editorbar')).toContainText('已保存');
  return { novel, chapter, base: `${API}/novels/${novel.id}/experimental` };
}
async function openTools(page: Page, tab: '风格档案' | '作品审稿') {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: tab, exact: true }).click();
}
async function openOriginalStyles(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const navigation = page.getByRole('navigation', { name: '功能面板导航' });
  const group = navigation.locator('.feature-group__header').filter({ hasText: /^创作/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await navigation.getByRole('button', { name: '创作方案与风格', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('heading', { name: '创作方案与风格', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '刷新记录', exact: true })).toBeEnabled();
}
async function unchanged(request: APIRequestContext, original: SavedChapter) {
  const current = await body<SavedChapter>(await request.get(`${API}/chapters/${original.id}`));
  expect(current.content).toBe(original.content); expect(current.version).toBe(original.version);
}
test.beforeEach(({ page }) => {
  owned.set(page, []); quiet.set(page, createPageQuiescer(page)); modelRequests.set(page, []);
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  page.on('request', request => {
    if (request.method() === 'POST' && /\/api\/(?:generate(?:\/|$)|generation(?:\/|$))|\/experimental\/(?:model-broker|author-context)\/generate(?:\?|$)/.test(request.url())) modelRequests.get(page)!.push(request.url());
  });
  test.info().annotations.push({ type: 'verification', description: 'Real local File API on 8019 and React UI on 5179; synthetic saved Markdown only. No business-response mocks, model calls, paid services or automatic approval. Browser execution is required in CI.' });
});
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) await page.screenshot({ path: info.outputPath('style-judge-failure-before-cleanup.png'), fullPage: true }).catch(() => {});
  await quiet.get(page)!();
  for (const id of owned.get(page) || []) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(id)}`)).status());
});

test('R4 style draft, real sample counts, approval and explicit previewed use reuse the original STYLE record', async ({ page }, info) => {
  const { chapter, base } = await project(page);
  const title = '合成克制文风', instruction = '使用具体动词和短句，允许有意的重复。';
  await openTools(page, '风格档案');
  const panel = page.getByRole('region', { name: '文风分析与档案', exact: true });
  await expect(panel.getByText('还没有风格档案', { exact: true })).toBeVisible();
  expect((await body(await page.request.get(`${base}/style-analysis/analyses`))).items).toHaveLength(0);
  await panel.getByLabel('风格档案标题', { exact: true }).fill(title);
  await panel.getByLabel('可复用风格指令（最多 120 字）', { exact: true }).fill(instruction);
  await panel.getByLabel('参考规则（每行一条，不注入生成请求）', { exact: true }).fill('有意的回环不自动认定为错误。');
  await panel.getByRole('checkbox', { name: `档案来源：${chapterTitle} · v${chapter.version}`, exact: true }).check();
  const saved = page.waitForResponse(response => response.url().endsWith('/style-analysis/profiles') && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '保存风格草稿', exact: true }).click();
  const profile = await body(await saved); expect(profile.kind).toBe('STYLE'); expect(profile.status).toBe('DRAFT');
  await expect(panel.getByRole('button', { name: `审核风格 ${title}`, exact: true })).toBeVisible();
  await panel.getByLabel('分析与预览的风格档案', { exact: true }).selectOption(profile.id);
  await expect(panel.getByRole('button', { name: '预览风格注入内容', exact: true })).toBeDisabled();
  await panel.getByRole('checkbox', { name: `分析样本：${chapterTitle} · v${chapter.version}`, exact: true }).check();
  const analyzed = page.waitForResponse(response => response.url().endsWith('/style-analysis/analyses') && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '分析所选已保存样本', exact: true }).click();
  const analysis = await body(await analyzed); expect(analysis.model_called).toBe(false); expect(analysis.metrics.paragraph_count).toBe(3);
  expect(analysis.samples[0]).toMatchObject({ chapter_id: chapter.id, expected_version: chapter.version, start: 0 });
  const report = panel.getByRole('article', { name: `文风报告 ${analysis.id}`, exact: true });
  await expect(report.getByText('句子数', { exact: true })).toBeVisible(); await expect(report.getByText('段落数', { exact: true })).toBeVisible();
  await unchanged(page.request, chapter);
  const approved = page.waitForResponse(response => response.url().endsWith(`/style-analysis/profiles/${profile.id}/approve`) && response.request().method() === 'POST');
  await panel.getByRole('button', { name: `审核风格 ${title}`, exact: true }).click();
  const current = await body(await approved); expect(current.status).toBe('APPROVED'); expect(current.id).toBe(profile.id); expect(current.version).toBeGreaterThan(profile.version);
  await expect(report).toContainText('旧来源的派生指标已隐藏'); await expect(report.getByText('句子数', { exact: true })).toHaveCount(0);
  // Approval must not silently choose the profile for writing.
  await openOriginalStyles(page); await expect(page.getByText(/已选写作输入：/)).toHaveCount(0);
  await openTools(page, '风格档案');
  await expect(panel.getByRole('button', { name: `编辑风格 ${title}`, exact: true })).toBeVisible();
  await panel.getByLabel('分析与预览的风格档案', { exact: true }).selectOption(profile.id);
  const previewed = page.waitForResponse(response => response.url().endsWith(`/style-analysis/profiles/${profile.id}/preview`) && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '预览风格注入内容', exact: true }).click();
  const preview = await body(await previewed); expect(preview.style_version).toBe(current.version); expect(preview.model_called).toBe(false); expect(preview.context_injection).toBe('INSTRUCTIONS_ONLY');
  const receipt = panel.getByRole('region', { name: '准确风格输入预览', exact: true });
  await expect(receipt.getByLabel('将进入请求的风格指令', { exact: true })).toHaveValue(instruction);
  await expect(receipt.getByRole('button', { name: '明确使用此风格准备写作', exact: true })).toBeDisabled();
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready); await receipt.scrollIntoViewIfNeeded();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.screenshot({ path: info.outputPath(`style-preview-${width}.png`) });
  }
  await receipt.getByRole('checkbox', { name: '已核对风格指令、用途与版本', exact: true }).check();
  const revalidated = page.waitForResponse(response => response.url().endsWith(`/style-analysis/profiles/${profile.id}/preview`) && response.request().method() === 'POST');
  await receipt.getByRole('button', { name: '明确使用此风格准备写作', exact: true }).click();
  expect((await body(await revalidated)).preview_digest).toBe(preview.preview_digest);
  await expect(panel).toHaveCount(0);
  await openOriginalStyles(page); await expect(page.getByText(/已选写作输入：/)).toContainText(title);
  const stored = await body(await page.request.get(`${base}/style-analysis/catalog`));
  expect(stored.styles).toHaveLength(1); expect(stored.styles[0].id).toBe(profile.id);
  await unchanged(page.request, chapter); expect(modelRequests.get(page)).toEqual([]);
  await page.screenshot({ path: info.outputPath('style-explicit-original-writing-selection.png') });
});

test('R4 exact duplicate evidence supports reasoned ignore and hides stale source results before a fresh check', async ({ page }, info) => {
  const { chapter, base } = await project(page);
  await openTools(page, '作品审稿');
  const panel = page.getByRole('region', { name: '叙事证据审阅', exact: true });
  await expect(panel.getByText('还没有审阅记录', { exact: true })).toBeVisible();
  expect((await body(await page.request.get(`${base}/narrative-judge/runs`))).items).toHaveLength(0);
  await expect(panel.getByRole('checkbox', { name: `审阅章节：${chapterTitle} · v${chapter.version}`, exact: true })).toBeChecked();
  const started = page.waitForResponse(response => response.url().endsWith('/narrative-judge/runs') && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '检查所选已保存章节', exact: true }).click();
  const run = await body(await started); expect(run.model_called).toBe(false); expect(run.verification).toBe('DETERMINISTIC_RULES');
  const finding = run.findings.find((row: { code: string }) => row.code === 'EXACT_REPEATED_PARAGRAPH'); expect(finding).toBeTruthy(); expect(finding.evidence).toHaveLength(2);
  for (const proof of finding.evidence) {
    expect(proof.chapter_id).toBe(chapter.id); expect(proof.chapter_version).toBe(chapter.version);
    expect(Array.from(chapter.content).slice(proof.start, proof.end).join('')).toBe(proof.quote);
  }
  const article = panel.getByRole('article', { name: `检查线索 ${finding.id}`, exact: true });
  await expect(article).toContainText('原始 Markdown 字符范围');
  await expect(article.getByRole('button', { name: '记录忽略理由', exact: true })).toBeDisabled();
  await article.getByLabel(`审核理由 ${finding.id}`, { exact: true }).fill('这是合成回环段落，有意重复，保留原文。');
  const reviewed = page.waitForResponse(response => response.url().endsWith(`/narrative-judge/findings/${finding.id}/review`) && response.request().method() === 'POST');
  await article.getByRole('button', { name: '记录忽略理由', exact: true }).click();
  const decision = await body(await reviewed); expect(decision.decision).toBe('IGNORED'); expect(decision.status).toBe('RESOLVED');
  await expect(article.getByRole('button', { name: '重新打开核对', exact: true })).toBeVisible();
  await panel.getByLabel('按审核决定筛选', { exact: true }).selectOption('IGNORED'); await expect(article).toBeVisible();
  await article.getByText('查看已保存的审核理由', { exact: true }).click(); await expect(article).toContainText('这是合成回环段落，有意重复，保留原文。');
  await unchanged(page.request, chapter); await page.screenshot({ path: info.outputPath('judge-reasoned-ignore.png') });
  // Simulate a real second editor saving a new source revision, never a mock response.
  const next = await body<SavedChapter>(await page.request.put(`${API}/chapters/${chapter.id}`, { data: { version: chapter.version, content: '船已靠岸，她提灯走向新的一天。' } }));
  await panel.getByRole('button', { name: '刷新审阅与来源（保留输入）', exact: true }).click();
  await expect(panel.getByText('历史结果已隐藏', { exact: false })).toBeVisible();
  await expect(panel.getByRole('article', { name: `检查线索 ${finding.id}`, exact: true })).toHaveCount(0);
  await expect(panel.getByText(refrain, { exact: false })).toHaveCount(0);
  await expect(panel.getByText('规则未发现匹配线索', { exact: true })).toHaveCount(0);
  const stale = await body(await page.request.get(`${base}/narrative-judge/runs/${run.id}`)); expect(stale.stale).toBe(true); expect(stale.findings).toEqual([]);
  expect(JSON.stringify(stale)).not.toContain(refrain);
  expect((await page.request.post(`${base}/narrative-judge/findings/${finding.id}/review`, { data: { expected_version: decision.version, action: 'reopen', reason: '旧证据不能重新提交。' } })).status()).toBe(409);
  await page.screenshot({ path: info.outputPath('judge-stale-source-redacted.png') });
  const checked = page.waitForResponse(response => response.url().endsWith('/narrative-judge/runs') && response.request().method() === 'POST');
  await panel.getByRole('button', { name: '检查所选已保存章节', exact: true }).click();
  const fresh = await body(await checked); expect(fresh.id).not.toBe(run.id); expect(fresh.stale).toBe(false); expect(fresh.findings).toEqual([]);
  await expect(panel.getByText('规则未发现匹配线索', { exact: true })).toBeVisible();
  await unchanged(page.request, next); expect(modelRequests.get(page)).toEqual([]);
});
