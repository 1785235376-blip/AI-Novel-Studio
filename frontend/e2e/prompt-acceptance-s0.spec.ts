/**
 * R3-U3-D S0 — 入口 Smoke（单一视口，必须连续两次通过）。
 *
 * 只回答一个问题：**真实浏览器能否通过真实 UI 进入一份本用例自己创建的 NEUTRAL_STUDIO
 * 项目，并看到已挂载的 Prompt 工作台。**
 *
 * 两次执行覆盖两种真实前置条件：
 *   第一次：隔离数据根为空；
 *   第二次：同一数据根已存在一个 NEUTRAL_STUDIO 项目（Vite 会自动打开它）。
 * 两次共用同一份用例——入口逻辑必须同时处理这两种情况。
 */
import {expect, test} from '@playwright/test';

import {
  blankProjectName, classifyApi, collectDiagnostics, countPromptPosts, enterOwnedStudio,
  openPromptWorkspace, promptLibrary, promptWorkspace,
} from './promptAcceptanceEntry';

const RUN_ID = process.env.PROMPT_ACCEPTANCE_RUN_ID?.trim() || 'no-run-id';

test('S0 入口：创建本用例专属 NEUTRAL_STUDIO 项目并打开 Prompt 工作台', async ({page}) => {
  const {appErrors, resourceErrors, apiFailures} = collectDiagnostics(page);
  const posts = countPromptPosts(page);

  const owned = await enterOwnedStudio(page, {runId: RUN_ID, label: 's0'});
  test.info().annotations.push({type: 'owned-project', description: JSON.stringify(owned)});

  await openPromptWorkspace(page);
  await expect(promptWorkspace(page)).toBeVisible();

  // 新项目必须是空库，并且显示明确的空状态而不是空白。
  await expect(page.getByText('还没有 Prompt')).toBeVisible({timeout: 25_000});

  const countAfterOpen = posts.value();
  await page.screenshot({
    path: `test-results/s0-${RUN_ID}-${test.info().project.name}-${owned.projectId.slice(0, 8)}.png`,
    fullPage: true,
  });
  posts.dispose();

  // 仅打开工作台不得产生任何写入。
  expect(countAfterOpen, '仅打开工作台不应产生 Prompt 写入').toBe(0);

  // A 类：本项目创建 / 本 OWNED 项目的 Studio 与 Prompt 读写出现非成功响应 → 必须 FAIL。
  const {critical, unrelated} = classifyApi(apiFailures, owned.projectId);
  expect(critical, `本轮 Prompt 关键 API 失败：${critical.map(r => `${r.status} ${r.url}`).join(' | ')}`)
    .toEqual([]);
  // C 类：真正的应用错误 → 必须 FAIL。
  expect(appErrors, `出现应用错误：${appErrors.join(' | ')}`).toEqual([]);
  // B/D 类：记录而不冒充 PASS，也不让无关模块的契约性拒绝伪装成 Prompt 缺陷。
  if (unrelated.length > 0) {
    test.info().annotations.push({
      type: 'unrelated-api-failures',
      description: unrelated.map(r => `${r.status} ${r.url}`).join(' | '),
    });
  }
  if (resourceErrors.length > 0) {
    test.info().annotations.push({type: 'static-resource-404', description: resourceErrors.join(' | ')});
  }
  // 该项目确实是本用例创建的：名称里带本轮 RUN_ID。
  expect(owned.name).toContain(RUN_ID);
  await expect(blankProjectName(page)).toBeHidden();
  await expect(promptLibrary(page)).toBeVisible();
});
