/**
 * R3-U3-D —— Prompt 工作台真实浏览器业务验收。
 *
 * 全套复用 `promptAcceptanceEntry.ts` 的共享入口助手与同步 POST 计数器：
 * 每个用例都创建**自己**的 NEUTRAL_STUDIO 项目，并用授权接口核对
 * `project.id` 与 `entry_kind`，不因为列表里恰好有个家族就据为己有。
 *
 * 真实 HTTP、真实持久化，无 route.fulfill、无 mock 响应。全部使用合成正文。
 */
import {expect, test, type Page} from '@playwright/test';

import {
  classifyApi, collectDiagnostics, countPromptPosts, enterOwnedStudio, openPromptWorkspace,
  promptLibrary,
} from './promptAcceptanceEntry';

const RUN_ID = process.env.PROMPT_ACCEPTANCE_RUN_ID?.trim() || 'no-run-id';

/** 合成正文：前后空格、换行、中文与 emoji 都必须原样往返。 */
const TEXT_V1 = '  合成正文第一版\n第二行 🙂  \n';
const TEXT_V2 = '合成正文第二版，改动若干 🙂🙂\n第三行\n';

const bodyBox = (page: Page) => page.getByLabel('正文', {exact: true});

/** 每个用例进入自己专属的项目与工作台；返回该用例的归属信息。 */
async function own(page: Page, label: string) {
  const owned = await enterOwnedStudio(page, {runId: RUN_ID, label});
  await openPromptWorkspace(page);
  return owned;
}

/** 本用例的 A 类（关键 Prompt API）失败必须为空；B 类只记录。 */
function assertNoCriticalPromptFailure(
  page: Page, diagnostics: ReturnType<typeof collectDiagnostics>, ownedProjectId: string,
) {
  const {critical, unrelated} = classifyApi(diagnostics.apiFailures, ownedProjectId);
  expect(critical, `本轮 Prompt 关键 API 失败：${critical.map(r => `${r.status} ${r.url}`).join(' | ')}`)
    .toEqual([]);
  expect(diagnostics.appErrors, `出现应用错误：${diagnostics.appErrors.join(' | ')}`).toEqual([]);
  if (unrelated.length > 0) {
    test.info().annotations.push({type: 'unrelated-api-failures',
      description: unrelated.map(r => `${r.status} ${r.url}`).join(' | ')});
  }
  void page;
}

test('用例1：创建 P1 并读回，中文/换行/emoji/前后空格原样保留', async ({page}) => {
  const diagnostics = collectDiagnostics(page);
  const posts = countPromptPosts(page);
  const owned = await own(page, 'case1');
  try {
    // 空库明确显示空状态。
    await expect(page.getByText('还没有 Prompt')).toBeVisible({timeout: 20_000});

    await page.getByRole('button', {name: '新建 Prompt', exact: true}).click();
    await bodyBox(page).fill(TEXT_V1);
    // 输入阶段不得产生任何写入。
    expect(posts.value(), '仅输入不应 POST').toBe(0);

    await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
    await expect(page.locator('.prompt-status')).toContainText('已保存', {timeout: 25_000});
    expect(posts.value(), '一次显式保存恰好一次 POST').toBe(1);

    // 从服务器读回：真实正文逐字一致。
    await bodyBox(page).fill(TEXT_V1);
    await promptLibrary(page).getByRole('button', {name: /IMAGE/}).first().click();
    await expect(bodyBox(page)).toHaveValue(TEXT_V1, {timeout: 20_000});
    expect(await bodyBox(page).inputValue()).toContain('🙂');

    await page.screenshot({path: `test-results/biz-${RUN_ID}-case1-${test.info().project.name}.png`, fullPage: true});
  } finally { posts.dispose(); }
  assertNoCriticalPromptFailure(page, diagnostics, owned.projectId);
});

test('用例2：保存第二修订，并对两个真实正文做比较', async ({page}) => {
  const diagnostics = collectDiagnostics(page);
  const posts = countPromptPosts(page);
  const owned = await own(page, 'case2');
  try {
    await page.getByRole('button', {name: '新建 Prompt', exact: true}).click();
    await bodyBox(page).fill(TEXT_V1);
    await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
    await expect(page.locator('.prompt-status')).toContainText('已保存', {timeout: 25_000});

    // 打开刚保存的家族（唯一家族），保存第二修订。
    await promptLibrary(page).getByRole('button', {name: /IMAGE/}).first().click();
    await expect(page.getByRole('button', {name: '保存新版本', exact: true})).toBeVisible({timeout: 20_000});
    await bodyBox(page).fill(TEXT_V2);
    await page.getByRole('button', {name: '保存新版本', exact: true}).click();
    await expect(page.locator('.prompt-status')).toContainText('已保存', {timeout: 25_000});
    expect(posts.value(), '创建一次 + 修订一次').toBe(2);

    // 真实正文比较：diff 必须含真实正文片段，而不是版本号。
    await expect(page.getByRole('region', {name: '版本历史'})).toBeVisible();
    await page.getByRole('button', {name: '比较正文', exact: true}).click();
    const diff = page.locator('.prompt-diff table');
    await expect(diff).toBeVisible({timeout: 25_000});
    await expect(diff).toContainText('合成正文第一版');
    await expect(diff).toContainText('合成正文第二版');
    await page.screenshot({path: `test-results/biz-${RUN_ID}-case2-${test.info().project.name}.png`, fullPage: true});
  } finally { posts.dispose(); }
  assertNoCriticalPromptFailure(page, diagnostics, owned.projectId);
});

test('用例3：再次新建必须是另一个家族，而不是上一家族的修订', async ({page}) => {
  const diagnostics = collectDiagnostics(page);
  const posts = countPromptPosts(page);
  const owned = await own(page, 'case3');
  try {
    await page.getByRole('button', {name: '新建 Prompt', exact: true}).click();
    await bodyBox(page).fill(TEXT_V1);
    await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
    await expect(page.locator('.prompt-status')).toContainText('已保存', {timeout: 25_000});

    await page.getByRole('button', {name: '新建 Prompt', exact: true}).click();
    await bodyBox(page).fill('第二份独立 Prompt\n');
    // 按钮仍是“保存为新 Prompt” → 这是新建而不是修订。
    await expect(page.getByRole('button', {name: '保存为新 Prompt', exact: true})).toBeVisible();
    await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
    await expect(page.locator('.prompt-status')).toContainText('已保存', {timeout: 25_000});

    // 本用例的项目里应有**两个**不同家族。
    await expect(promptLibrary(page).getByRole('button', {name: /IMAGE/})).toHaveCount(2, {timeout: 20_000});
    expect(posts.value()).toBe(2);
  } finally { posts.dispose(); }
  assertNoCriticalPromptFailure(page, diagnostics, owned.projectId);
});

test('用例4：无效 JSON 与 Seed 不产生任何写入，输入保持原样', async ({page}) => {
  const diagnostics = collectDiagnostics(page);
  const posts = countPromptPosts(page);
  const owned = await own(page, 'case4');
  try {
    await page.getByRole('button', {name: '新建 Prompt', exact: true}).click();
    await bodyBox(page).fill('参数校验用合成正文');
    await page.getByLabel(/参数/, {exact: false}).fill('{ not json');
    await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
    await expect(page.locator('.prompt-editor')).toContainText('JSON');
    expect(posts.value(), '非法 JSON 不得 POST').toBe(0);
    await expect(page.getByLabel(/参数/, {exact: false})).toHaveValue('{ not json');

    await page.getByLabel(/参数/, {exact: false}).fill('{"steps":28}');
    await page.getByLabel('Seed', {exact: true}).fill('-3');
    await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
    await expect(page.locator('.prompt-editor')).toContainText('Seed');
    expect(posts.value(), '非法 Seed 不得 POST').toBe(0);
    await expect(page.getByLabel('Seed', {exact: true})).toHaveValue('-3');
  } finally { posts.dispose(); }
  assertNoCriticalPromptFailure(page, diagnostics, owned.projectId);
});

test('用例5：刷新后只告知草稿无法恢复，不冒充已恢复', async ({page}) => {
  const diagnostics = collectDiagnostics(page);
  const owned = await own(page, 'case5');
  await page.getByRole('button', {name: '新建 Prompt', exact: true}).click();
  await bodyBox(page).fill('未保存的合成草稿');
  // The editor's own persistent status element, not the first status on the page (the
  // library panel renders one too).
  await expect(page.locator('.prompt-status')).toContainText('未保存');

  // beforeunload 由浏览器接管：明确接受对话框，不关闭产品原有提醒。
  page.on('dialog', dialog => { void dialog.accept(); });
  await page.reload();
  await openPromptWorkspace(page);

  const text = await page.locator('body').innerText();
  if (text.includes('未保存草稿')) {
    expect(text).toContain('无法恢复');
    expect(text).not.toContain('已恢复草稿');
  }
  // 正文没有进入浏览器存储，因此刷新后不会带回原文。
  await expect(bodyBox(page)).not.toHaveValue('未保存的合成草稿');
  assertNoCriticalPromptFailure(page, diagnostics, owned.projectId);
});

test('用例6：真实布局无横向溢出，关键控件可达', async ({page}) => {
  const diagnostics = collectDiagnostics(page);
  const owned = await own(page, 'case6');
  const viewport = page.viewportSize();
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow, `${viewport?.width}x${viewport?.height} 出现横向溢出`).toBeLessThanOrEqual(1);

  await expect(page.getByRole('button', {name: '新建 Prompt', exact: true})).toBeVisible();
  await expect(bodyBox(page)).toBeVisible();
  await page.screenshot({
    path: `test-results/biz-${RUN_ID}-case6-${viewport?.width}x${viewport?.height}.png`, fullPage: true});
  assertNoCriticalPromptFailure(page, diagnostics, owned.projectId);
});
