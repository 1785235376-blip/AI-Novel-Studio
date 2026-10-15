/**
 * R3-U3-D —— 两套 Prompt 验收脚本共用的入口 helper。
 *
 * 为什么要共用：S0 与主业务套件此前各自假设“一定会出现空白项目表单”，于是当隔离数据根里
 * 已经有项目、Vite 自动打开了它时，两边都卡在同一个入口错误上——一次环境问题被误报成
 * 多个业务缺陷。这里只做一件事：**按真实界面分类当前状态，然后创建一份本用例专用的
 * NEUTRAL_STUDIO 项目**，并用授权接口证明进入的确实是这个新项目。
 *
 * 纪律：
 * - 不注入 React state、不伪造 AppShell、不跳过 `entry_kind` 核验、不加登录后门；
 * - 不把 `Promise.race` 里先超时的 `null` 当成一个页面状态；用有界轮询做确定性分类；
 * - `waitForResponse` 只在真正点击创建按钮之前注册，避免悬空超时。
 */
import {expect, type Locator, type Page} from '@playwright/test';

export const studioSwitcher = (page: Page) => page.locator('[aria-label="独立工作区内容"]');
export const blankProjectName = (page: Page) => page.getByLabel('空白项目名称', {exact: true});
export const promptWorkspace = (page: Page) => page.getByRole('heading', {name: 'Prompt 工作台'});
export const promptLibrary = (page: Page) => page.getByRole('region', {name: 'Prompt 列表'});

export type EntryState = 'ENTRY' | 'STUDIO' | 'NOVEL' | 'UNKNOWN';

/**
 * 可靠的同源 POST 计数器。
 *
 * 闭包保存计数，由 `page.on('request')` **同步**递增。绝不把自定义字段写到 Playwright 的
 * `Page` 实例上（那不是浏览器的 `window`），也不在事件回调里异步 `page.evaluate`。
 * 只匹配真实 Prompt 创建/修订的 POST，测试结束必须 `dispose()`。
 */
export function countPromptPosts(page: Page) {
  let count = 0;
  const urls: string[] = [];
  const handler = (request: {method: () => string; url: () => string}) => {
    const url = request.url();
    if (request.method() === 'POST' && /\/api\/projects\/[^/]+\/studio\/prompts(\/|$|\?)/.test(url)) {
      count += 1;
      urls.push(url);
    }
  };
  page.on('request', handler as never);
  return {
    value: () => count,
    urls: () => [...urls],
    dispose: () => page.off('request', handler as never),
  };
}

/** 有界轮询分类：返回**第一个**真正可见的状态，而不是先超时的那个。 */
async function classify(page: Page, timeout: number): Promise<EntryState> {
  // NOTE: the top-level 小说/图片/… tablist belongs to the always-rendered AppShell and is
  // visible on the project ENTRY screen too, so it must NOT be used as a "novel screen"
  // signal — doing so misclassified a perfectly good entry page as NOVEL and raised
  // WRONG_TEST_ROOT against a project this very helper had created. Only the two states we
  // can identify reliably are returned; anything else is UNKNOWN and fails loudly with
  // evidence rather than being guessed at.
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    if (await blankProjectName(page).isVisible().catch(() => false)) return 'ENTRY';
    if (await studioSwitcher(page).isVisible().catch(() => false)) return 'STUDIO';
    await page.waitForTimeout(250);
  }
  return 'UNKNOWN';
}

/** 只有确实处于小说编辑面时才判定 NOVEL：必须看到正文编辑面且不在项目入口。 */
async function looksLikeNovelScreen(page: Page): Promise<boolean> {
  const entry = await blankProjectName(page).isVisible().catch(() => false);
  const studio = await studioSwitcher(page).isVisible().catch(() => false);
  if (entry || studio) return false;
  // 小说编辑面的稳定标志：章节/正文编辑区，而不是顶层的模块标签。
  return page.getByRole('textbox', {name: /正文|章节内容/}).first().isVisible().catch(() => false);
}

export type OwnedProject = {projectId: string; name: string; entryKind: string};

/**
 * 进入**本用例自己创建**的 NEUTRAL_STUDIO 项目。
 *
 * 三种真实状态：
 *  - ENTRY：直接创建；
 *  - STUDIO：先用真实 UI 的“返回项目列表”回到项目入口，再创建（**不复用**别人的项目）；
 *  - NOVEL：隔离环境不应出现，报 `WRONG_TEST_ROOT` 并保留证据，绝不把它当独立 Studio。
 */
export async function enterOwnedStudio(
  page: Page, options: {runId: string; label: string},
): Promise<OwnedProject> {
  const {runId, label} = options;
  await page.goto('/');

  let state = await classify(page, 30_000);
  if (state === 'STUDIO') {
    // 本机已自动打开一个既有 Studio 项目：走真实入口返回项目列表。
    await page.getByRole('button', {name: '返回项目列表', exact: true}).click();
    state = await classify(page, 20_000);
  }
  if (await looksLikeNovelScreen(page)) {
    const novels = await page.request.get('/api/novels');
    const body = (await novels.text()).slice(0, 200);
    throw new Error(`WRONG_TEST_ROOT: 隔离数据根出现了普通小说编辑面，拒绝把它当作独立 Studio。`
      + ` /api/novels=${body} url=${page.url()}`);
  }
  if (state !== 'ENTRY') {
    const snapshot = (await page.locator('body').innerText()).replace(/\s+/g, ' ').slice(0, 300);
    throw new Error(`ENTRY_BLOCKED: 无法识别入口状态（${state}）url=${page.url()} 文本片段=${snapshot}`);
  }

  // RUN_ID + 用例标识 + 唯一后缀：同一轮里每个用例都得到自己的项目身份。
  const name = `Prompt 验收 ${runId} ${label} ${Date.now()}`;
  await blankProjectName(page).fill(name);

  // 监听器必须在点击之前注册，但只在真正要点击时注册。
  const creation = page.waitForResponse(
    response => response.url().includes('/api/experimental/projects')
      && response.request().method() === 'POST',
    {timeout: 30_000});
  await page.getByRole('button', {name: '创建空白项目', exact: true}).click();
  const created = await creation;
  expect(created.ok(), `创建项目返回 ${created.status()}`).toBeTruthy();
  const createdBody = (await created.json()) as {id?: string};
  expect(createdBody.id, '创建响应必须带项目 id').toBeTruthy();
  const projectId = createdBody.id as string;

  // 用授权入口证明进入的是**这次创建**的 NEUTRAL_STUDIO 项目。
  const studio = await page.request.get(`/api/projects/${projectId}/studio`);
  expect(studio.ok(), `GET /studio 返回 ${studio.status()}`).toBeTruthy();
  const studioBody = (await studio.json()) as {project?: {id?: string; entry_kind?: string}};
  expect(studioBody.project?.id).toBe(projectId);
  expect(studioBody.project?.entry_kind, '必须是 NEUTRAL_STUDIO 项目').toBe('NEUTRAL_STUDIO');

  await expect(studioSwitcher(page)).toBeVisible({timeout: 30_000});
  return {projectId, name, entryKind: studioBody.project?.entry_kind as string};
}

/** 打开素材工作区里的 Prompt 工作台。 */
export async function openPromptWorkspace(page: Page): Promise<void> {
  await page.getByRole('button', {name: '素材工作区', exact: true}).click();
  await expect(promptWorkspace(page)).toBeVisible({timeout: 25_000});
  await expect(promptLibrary(page)).toBeVisible({timeout: 25_000});
}

/**
 * 收集本用例的失败证据。
 *
 * 区分两类“控制台错误”：
 *  - `appErrors`：真正的应用错误（未捕获异常、React 报错）。任何一个都必须让用例失败；
 *  - `resourceErrors`：静态资源 404（浏览器对 /favicon.ico 之类会记一条 console error）。
 *    这类不是产品缺陷，单独记录并在收据里报告，不冒充应用故障，也不被静默忽略。
 * 同时单独记录所有 `/api` 失败响应，那才是真正的接口问题。
 */
export function collectDiagnostics(page: Page) {
  const appErrors: string[] = [];
  const resourceErrors: string[] = [];
  const failedHttp: string[] = [];
  page.on('pageerror', error => appErrors.push(String(error).slice(0, 300)));
  page.on('console', message => {
    if (message.type() !== 'error') return;
    const text = message.text().slice(0, 300);
    // Chromium words a failed subresource fetch exactly like this; the URL is in the
    // network log, not the message, so classify by that phrasing only.
    if (/Failed to load resource: the server responded with a status of \d+/.test(text)) {
      resourceErrors.push(text);
    } else {
      appErrors.push(text);
    }
  });
  page.on('response', response => {
    if (response.status() >= 400 && response.url().includes('/api/')) {
      failedHttp.push(`${response.status()} ${response.url()}`);
    }
  });
  return {appErrors, resourceErrors, failedHttp};
}

export type {Locator};
