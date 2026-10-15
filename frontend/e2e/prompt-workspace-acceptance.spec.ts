/**
 * R3-U3-D — Prompt 工作台的真实浏览器验收。
 *
 * 这是对**已经在运行的真实应用**的端到端验收：真实后端 + 真实 React + 真实浏览器。
 * 这里不 mock 任何 API 响应、不 stub 组件，也不基于 jsdom 渲染做断言。
 *
 * 前置条件（见 ./README.md）：应用已在 STUDIO_ACCEPTANCE_BASE_URL 运行，
 * 且已启用 `narrative_production_v2`。浏览器由操作者提供，本套件从不下载浏览器。
 *
 * 每个用例都会在这个服务器上创建真实的合成 Prompt 项目。用例只使用合成正文，
 * 绝不读取或截图用户的私有内容。
 */
import {expect, test, type Page} from '@playwright/test';

const switcher = (page: Page) => page.locator('[aria-label="独立工作区内容"]');
const workspace = (page: Page) => page.getByRole('heading', {name: 'Prompt 工作台'});
const library = (page: Page) => page.getByRole('region', {name: 'Prompt 列表'});

/** 合成测试正文：中文、换行、emoji 与前后空格都必须原样保留。 */
const TEXT_V1 = '  合成正文第一版\n第二行 🙂  \n';
const TEXT_V2 = '合成正文第二版，改动若干 🙂🙂\n第三行\n';

/** 进入独立 Studio（复用既有验收套件的幂等入口写法）。 */
async function enterStudio(page: Page): Promise<void> {
  await page.goto('/');
  const ready = switcher(page);
  const blankName = page.getByLabel('空白项目名称', {exact: true});
  const settled = await Promise.race([
    ready.waitFor({state: 'visible', timeout: 30_000}).then(() => 'STUDIO' as const).catch(() => null),
    blankName.waitFor({state: 'visible', timeout: 30_000}).then(() => 'ENTRY' as const).catch(() => null),
  ]);
  if (settled === 'STUDIO') return;
  if (settled === 'ENTRY') {
    await blankName.fill(`Prompt 验收 ${Date.now()}`);
    await page.getByRole('button', {name: '创建空白项目', exact: true}).click();
  }
  await ready.waitFor({state: 'visible', timeout: 30_000});
}

/** 打开素材工作区 → Prompt 工作台。 */
async function openPromptWorkspace(page: Page): Promise<void> {
  await enterStudio(page);
  await page.getByRole('button', {name: '素材工作区', exact: true}).click();
  await expect(workspace(page)).toBeVisible({timeout: 20_000});
  await expect(library(page)).toBeVisible({timeout: 20_000});
}

/** 用「新建 Prompt」建一份草稿并填写正文；默认不保存。 */
async function draftNewPrompt(page: Page, text: string): Promise<void> {
  await page.getByRole('button', {name: '新建 Prompt', exact: true}).click();
  const body = page.getByLabel('正文', {exact: true});
  await body.fill(text);
}

const postCount = (page: Page) => page.__promptPosts ?? 0;

test.beforeEach(async ({page}) => {
  // 计数真实 POST /studio/prompts：用来证明“只有明确点击才会写入”。
  await page.addInitScript(() => {
    (window as unknown as {__promptPosts: number}).__promptPosts = 0;
  });
  page.on('request', request => {
    const url = request.url();
    if (request.method() === 'POST' && /\/studio\/prompts(\/|$)/.test(url)) {
      void page.evaluate(() => {
        const w = window as unknown as {__promptPosts: number};
        w.__promptPosts = (w.__promptPosts ?? 0) + 1;
      });
    }
  });
});

test('真实挂载：能打开 Prompt 工作台并完成一次创建→读回', async ({page}) => {
  await openPromptWorkspace(page);
  await draftNewPrompt(page, TEXT_V1);

  // 输入不写入任何东西。
  expect(await postCount(page)).toBe(0);
  await expect(page.getByRole('status')).toContainText('未保存');

  await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
  // 服务器确认后才显示已保存，并把真实正文显示回来（中文/换行/emoji 原样）。
  await expect(page.getByRole('status')).toContainText('已保存', {timeout: 20_000});
  await expect(page.getByLabel('正文', {exact: true})).toHaveValue(TEXT_V1);
  await expect(library(page).getByRole('button', {name: /IMAGE/}).first()).toBeVisible();
  expect(await postCount(page)).toBe(1);
});

test('第二个修订可保存，并能对两个真实正文做比较', async ({page}) => {
  await openPromptWorkspace(page);
  await draftNewPrompt(page, TEXT_V1);
  await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('已保存', {timeout: 20_000});

  // 打开刚保存的家族，保存第二修订。
  await library(page).getByRole('button', {name: /IMAGE/}).first().click();
  await expect(page.getByRole('button', {name: '保存新版本', exact: true})).toBeVisible({timeout: 20_000});
  await page.getByLabel('正文', {exact: true}).fill(TEXT_V2);
  await page.getByRole('button', {name: '保存新版本', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('已保存', {timeout: 20_000});

  // 版本历史里应有两个修订，并且可以比较真实正文。
  await expect(page.getByRole('region', {name: '版本历史'})).toBeVisible();
  await page.getByRole('button', {name: '比较正文', exact: true}).click();
  const diff = page.locator('.prompt-diff table');
  await expect(diff).toBeVisible({timeout: 20_000});
  // 逐行差异里必须出现**真实**的正文片段，而不是版本号或摘要。
  await expect(diff).toContainText('合成正文第一版');
  await expect(diff).toContainText('合成正文第二版');
});

test('再次新建必须是另一个家族，而不是上一家族的修订', async ({page}) => {
  await openPromptWorkspace(page);
  await draftNewPrompt(page, TEXT_V1);
  await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('已保存', {timeout: 20_000});

  await draftNewPrompt(page, '第二份独立 Prompt\n');
  // 关键：按钮必须仍然是“保存为新 Prompt”，说明它是新建而不是修订。
  await expect(page.getByRole('button', {name: '保存为新 Prompt', exact: true})).toBeVisible();
  await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
  await expect(page.getByRole('status')).toContainText('已保存', {timeout: 20_000});
  // 列表里应有两个不同的家族。
  await expect(library(page).getByRole('button', {name: /IMAGE/})).toHaveCount(2, {timeout: 20_000});
});

test('无效 JSON 与 Seed 不会发出任何写入，输入保持原样', async ({page}) => {
  await openPromptWorkspace(page);
  await draftNewPrompt(page, '参数校验用正文');
  await page.getByLabel(/参数/, {exact: false}).fill('{ not json');
  await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
  await expect(page.locator('.prompt-editor')).toContainText('JSON');
  expect(await postCount(page)).toBe(0);
  await expect(page.getByLabel(/参数/, {exact: false})).toHaveValue('{ not json');

  await page.getByLabel(/参数/, {exact: false}).fill('{"steps":28}');
  await page.getByLabel('Seed', {exact: true}).fill('-3');
  await page.getByRole('button', {name: '保存为新 Prompt', exact: true}).click();
  await expect(page.locator('.prompt-editor')).toContainText('Seed');
  expect(await postCount(page)).toBe(0);
  await expect(page.getByLabel('Seed', {exact: true})).toHaveValue('-3');
});

test('刷新后被诚实告知草稿无法恢复，不冒充已恢复', async ({page}) => {
  await openPromptWorkspace(page);
  await draftNewPrompt(page, '未保存的合成草稿');
  await expect(page.getByRole('status')).toContainText('未保存');

  await page.reload();
  await openPromptWorkspace(page);
  // 只允许“检测到 + 无法恢复”的措辞；出现“已恢复”即为冒充。
  const notice = page.locator('.prompt-workspace, .prompt-library');
  await expect(notice.first()).toBeVisible();
  const text = await page.locator('body').innerText();
  if (text.includes('未保存草稿')) {
    expect(text).toContain('无法恢复');
    expect(text).not.toContain('已恢复草稿');
  }
  // 正文没有被写入浏览器存储，因此输入框不应带回原文。
  await expect(page.getByLabel('正文', {exact: true})).not.toHaveValue('未保存的合成草稿');
});

test('真实布局在三种视口下没有横向溢出，关键控件可达', async ({page}) => {
  await openPromptWorkspace(page);
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  // 允许 1px 的取整误差，但不允许真正的内容横向溢出。
  expect(overflow).toBeLessThanOrEqual(1);
  await expect(page.getByRole('button', {name: '新建 Prompt', exact: true})).toBeVisible();
  await expect(page.getByLabel('正文', {exact: true})).toBeVisible();
  await page.screenshot({path: `test-results/prompt-workspace-${page.viewportSize()?.width}x${page.viewportSize()?.height}.png`, fullPage: true});
});
