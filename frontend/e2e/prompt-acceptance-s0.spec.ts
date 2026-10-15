/**
 * R3-U3-D S0 — 入口 Smoke（单一视口）。
 *
 * 只回答一个问题：**真实浏览器能否通过真实 UI 进入一个自己创建的 NEUTRAL_STUDIO 项目，
 * 并看到已挂载的 Prompt 工作台。** 在 S0 通过之前不跑任何业务用例，避免把“入口阻塞”
 * 误报成“业务 18/18 失败”。
 *
 * 证据：创建请求的真实响应、`GET /api/projects/{id}/studio` 的 entry_kind、
 * 控制台错误、合成界面截图。所有数据均为合成内容。
 */
import {expect, test, type Page} from '@playwright/test';

const RUN_ID = process.env.PROMPT_ACCEPTANCE_RUN_ID?.trim() || 'local';

const switcher = (page: Page) => page.locator('[aria-label="独立工作区内容"]');

/** 可靠的同源 POST 计数器：闭包保存计数，由 request 事件**同步**递增。
 *  不给 Playwright 的 Page 实例写自定义字段，也不在事件里异步 evaluate。 */
function countPosts(page: Page, pattern: RegExp) {
  let count = 0;
  const handler = (request: {method: () => string; url: () => string}) => {
    if (request.method() === 'POST' && pattern.test(request.url())) count += 1;
  };
  page.on('request', handler as never);
  return {value: () => count, dispose: () => page.off('request', handler as never)};
}

const studioPosts = (page: Page) => countPosts(page, /\/api\/projects\/[^/]+\/studio\/prompts(\/|$|\?)/);

test('S0 入口：真实 UI 创建 NEUTRAL_STUDIO 项目并打开 Prompt 工作台', async ({page}) => {
  const consoleErrors: string[] = [];
  const failedHttp: string[] = [];
  page.on('console', message => {
    if (message.type() === 'error') consoleErrors.push(message.text().slice(0, 300));
  });
  page.on('response', response => {
    const status = response.status();
    const url = response.url();
    if (status >= 400 && url.includes('/api/')) failedHttp.push(`${status} ${url}`);
  });
  const posts = studioPosts(page);

  // 项目创建的真实响应必须被捕获，才能证明这个项目是**本用例自己创建的**。
  const creation = page.waitForResponse(
    response => response.url().includes('/api/experimental/projects')
      && response.request().method() === 'POST',
    {timeout: 30_000});

  await page.goto('/');

  // 隔离的空数据根下，本机项目入口应当直接出现；若应用恢复了别的项目则立即报清楚。
  const blankName = page.getByLabel('空白项目名称', {exact: true});
  try {
    await blankName.waitFor({state: 'visible', timeout: 25_000});
  } catch {
    const bodyText = (await page.locator('body').innerText()).slice(0, 400);
    throw new Error(`ENTRY_BLOCKED: 没有出现“空白项目名称”表单。`
      + `当前界面文本片段：${bodyText.replace(/\s+/g, ' ')}`);
  }

  const projectName = `Prompt 验收 ${RUN_ID} ${test.info().project.name} ${Date.now()}`;
  await blankName.fill(projectName);
  await page.getByRole('button', {name: '创建空白项目', exact: true}).click();

  const created = await creation;
  const createdBody = (await created.json()) as {id?: string; studio_ready?: boolean;
    requires_scope_selection?: boolean};
  expect(created.ok(), `创建项目返回 ${created.status()}`).toBeTruthy();
  expect(createdBody.id, '创建响应必须带项目 id').toBeTruthy();
  // 记录真实字段，供收据使用；studio_ready 未确认为真则不得继续。
  test.info().annotations.push({type: 'project', description: JSON.stringify(createdBody)});

  // 独立 Studio 只对 entry_kind=NEUTRAL_STUDIO 的项目挂载，必须用授权入口核对。
  const studio = await page.request.get(`/api/projects/${createdBody.id}/studio`);
  expect(studio.ok(), `GET /studio 返回 ${studio.status()}`).toBeTruthy();
  const studioBody = (await studio.json()) as {project?: {id?: string; entry_kind?: string}};
  expect(studioBody.project?.id).toBe(createdBody.id);
  expect(studioBody.project?.entry_kind, '必须是 NEUTRAL_STUDIO 项目').toBe('NEUTRAL_STUDIO');

  // UI 上必须真的挂载独立工作区，然后进入素材工作区。
  await expect(switcher(page)).toBeVisible({timeout: 30_000});
  await page.getByRole('button', {name: '素材工作区', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Prompt 工作台'})).toBeVisible({timeout: 20_000});
  await expect(page.getByRole('region', {name: 'Prompt 列表'})).toBeVisible({timeout: 20_000});

  // 空库必须显示明确的空状态，而不是空白。
  await expect(page.getByText('还没有 Prompt')).toBeVisible({timeout: 20_000});

  const countAfterOpen = posts.value();
  await page.screenshot({path: `test-results/s0-entry-${RUN_ID}.png`, fullPage: true});
  posts.dispose();

  // 打开工作台本身不得产生任何写入。
  expect(countAfterOpen, '仅打开工作台不应产生 Prompt 写入').toBe(0);
  expect(failedHttp, `出现失败 HTTP：${failedHttp.join(' | ')}`).toEqual([]);
  expect(consoleErrors, `出现控制台错误：${consoleErrors.join(' | ')}`).toEqual([]);
});
