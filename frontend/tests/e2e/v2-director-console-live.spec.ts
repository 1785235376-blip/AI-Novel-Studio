import { expect, test, type APIResponse } from '@playwright/test';

test('real File Director graph participant saves, reopens and refuses a changed source', async ({ page, request }, info) => {
  const owned: string[] = [], errors: string[] = [], consoleErrors: string[] = [], calls: { method: string; path: string; status?: number }[] = [];
  const token = process.env.STUDIO_DIRECTOR_BROWSER_TOKEN;
  if (!token) throw new Error('Start the original packaged bootstrap launcher before this acceptance; no synthetic session is substituted.');
  const workspace = '/api/collaboration/admin/workspaces/workspace-a';
  let headers: Record<string, string> = { 'X-Session-Token': token };
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('request', value => { const path = new URL(value.url()).pathname;
    if (path.startsWith('/api/')) calls.push({ method: value.method(), path }); });
  page.on('response', value => { const path = new URL(value.url()).pathname;
    if (path.startsWith('/api/')) calls.push({ method: value.request().method(), path, status: value.status() }); });
  const exact = async (response: APIResponse, status: number) => {
    expect(response.status(), await response.text()).toBe(status); return response.json();
  };
  info.annotations.push({ type: 'verification', description: 'Actual File owner, HTTP routes, rendered React and installed Edge. Authored synthetic text only; no response mocks, model inference or provider calls.' });
  const enterWorkspace = async () => {
    await page.getByText('连接已有创作空间', { exact: true }).click();
    await page.getByLabel('访问凭证', { exact: true }).fill(token);
    await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
    await page.getByRole('button', { name: '我的创作空间', exact: true }).click();
  };
  try {
    // The original admin and activation owners prepare one authorized project.
    // Authentication and selecting it still use the shipped browser entry.
    const response = await request.post(`${workspace}/projects`, { headers,
      data: { title: `导演控制台验收 ${info.project.name}`, genre: '' } });
    if (response.status() === 201) { const row = await response.json(); if (typeof row.id === 'string') owned.push(row.id); }
    const project = await exact(response, 201), base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
    const navigation = await exact(await request.get(`${workspace}/navigation`, { headers }), 200);
    const scope = navigation.eligible_paths.find((path: { project_id: string }) => path.project_id === project.id);
    expect(scope).toBeTruthy(); headers = { ...headers, 'X-Branch-Id': scope.branch_id };
    await exact(await request.post(`${base}/activate`, { headers }), 200);
    await page.goto('/'); await enterWorkspace();
    await page.getByRole('button', { name: new RegExp(`导演控制台验收 ${info.project.name}`) }).click();
    const content = { mode: 'DIRECTOR', title: '有明确视觉方向的导演文档', source_independent: true,
      source_chapter_ids: [], scenes: [], director_notes: [], shots: [], video_plan: null,
      visual_target: { style: '冷峻写实', atmosphere: '压抑', color: '青蓝低饱和', rhythm: '缓急交替', reference_works: [] } };
    const documentUrl = `/api/novels/${encodeURIComponent(project.id)}/experimental/creative/documents`;
    const document = await exact(await request.post(documentUrl, { data: content, headers }), 201);
    const catalog = await exact(await request.get(`${base}/graphs/planning-documents`, { headers }), 200);
    const source = catalog.documents.find((row: { id: string }) => row.id === document.id);
    expect(source).toMatchObject({ id: document.id, version: document.version, mode: 'DIRECTOR' });

    await page.getByRole('button', { name: '创作图', exact: true }).click();
    await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
    await page.getByLabel('创作图标题', { exact: true }).fill('浏览器恢复的文本图');
    await page.getByLabel('节点类型', { exact: true }).selectOption('text_input');
    await page.getByRole('button', { name: '添加节点', exact: true }).click();
    await page.getByRole('textbox', { name: '作者输入文本', exact: true }).fill('真实浏览器中保留的作者文本 🎬');
    await expect.poll(() => page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.startsWith('studio-graph-draft:v1:'))
      .some(([, value]) => value.includes('真实浏览器中保留的作者文本')))).toBe(true);
    await page.reload();
    await page.getByRole('button', { name: '创作图', exact: true }).click();
    await page.getByRole('button', { name: '核对并恢复本机图草稿', exact: true }).click();
    await expect(page.getByLabel('创作图标题', { exact: true })).toHaveValue('浏览器恢复的文本图');
    await page.getByRole('button', { name: /^选择节点 文本输入/ }).click();
    await expect(page.getByRole('textbox', { name: '作者输入文本', exact: true })).toHaveValue('真实浏览器中保留的作者文本 🎬');
    const savingText = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
    await page.getByRole('button', { name: '保存创作图', exact: true }).click();
    const textGraph = await exact(await savingText, 201);
    expect(textGraph.definition.nodes[0].parameters.text).toBe('真实浏览器中保留的作者文本 🎬');
    await page.screenshot({ path: info.outputPath('canvas-text-draft-restored.png'), fullPage: true });
    await page.getByRole('button', { name: '新建空图', exact: true }).click();
    await page.getByLabel('创作图标题', { exact: true }).fill('导演控制台来源绑定');
    await page.getByRole('button', { name: '明确读取导演、分镜与视觉制作节点目录', exact: true }).click();
    await page.getByLabel('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核', { exact: true }).check();
    await page.getByRole('button', { name: '明确采用图片图 v4', exact: true }).click();
    await page.getByLabel('节点类型', { exact: true }).selectOption('director_plan');
    await page.getByRole('button', { name: '明确读取已保存导演与分镜文档', exact: true }).click();
    await page.getByRole('combobox', { name: /^原创作文档/ }).selectOption(document.id);
    await page.getByRole('button', { name: '添加节点', exact: true }).click();
    const region = page.getByRole('region', { name: '图节点导演控制台', exact: true });
    await expect(region).toBeVisible();
    expect(calls.filter(row => row.path === `${base}/director/workspace/${document.id}`)).toEqual([]);
    await region.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
    await expect(region.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
    await expect(region.locator('.director-intent__list > li')).toHaveCount(7);
    const geometry = await page.evaluate(() => {
      const rect = (selector: string) => { const value = document.querySelector(selector)!.getBoundingClientRect();
        return { width: value.width, height: value.height, y: value.y }; };
      return { header: rect('.global-header'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'),
        scroll_width: document.documentElement.scrollWidth, viewport_width: innerWidth };
    });
    expect(geometry.header).toMatchObject({ height: 56, y: 0 });
    expect(geometry.sidebar.width).toBe(248); expect(geometry.inspector.width).toBe(340);
    expect(geometry.scroll_width).toBeLessThanOrEqual(geometry.viewport_width);
    await info.attach('real-shell-geometry', { body: JSON.stringify(geometry), contentType: 'application/json' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: info.outputPath('director-console-expanded.png'), fullPage: true });
    await region.locator('[data-field="visual_goal"]').scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('director-console-intent-scrolled.png'), fullPage: true });
    await region.locator('[data-field="performance_direction"]').scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('director-console-intent-lower.png'), fullPage: true });
    const creatingGraph = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
    await page.getByRole('button', { name: '保存创作图', exact: true }).click();
    const graph = await exact(await creatingGraph, 201);
    expect(graph.definition.nodes).toHaveLength(1);
    expect(graph.definition.nodes[0].parameters.document_snapshot).toEqual({ id: source.id, version: source.version, digest: source.digest });

    await page.reload();
    await page.getByRole('button', { name: '创作图', exact: true }).click();
    await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
    await page.getByRole('button', { name: `选择节点 导演节点（已保存文档） · ${graph.definition.nodes[0].id}`, exact: true }).click();
    await page.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
    await expect(page.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');

    await exact(await request.put(`${documentUrl}/${document.id}`, { headers, data: { ...content, expected_version: document.version,
      visual_target: { ...content.visual_target, style: '已修改但未重绑的视觉方向' } } }), 200);
    await page.getByRole('button', { name: '重新读取原文档', exact: true }).click();
    await expect(page.getByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/)).toBeVisible();
    await expect(page.getByLabel('导演意图', { exact: true })).toHaveCount(0);
    await expect(page.getByText('已修改但未重绑的视觉方向', { exact: true })).toHaveCount(0);
    await page.screenshot({ path: info.outputPath('director-console-stale-refusal.png'), fullPage: true });
    expect(errors).toEqual([]);
    expect(calls.filter(row => !['GET', 'HEAD', 'OPTIONS'].includes(row.method)
      && /\/(graph-runs|dispatch|generate|director-proposals|media\/tasks)(\/|$)/.test(row.path))).toEqual([]);
    const stored = await exact(await request.get(`${base}/graphs/${graph.id}`, { headers }), 200);
    expect(stored.version).toBe(graph.version);
    expect(stored.definition.nodes[0].parameters.document_snapshot).toEqual(graph.definition.nodes[0].parameters.document_snapshot);
    await info.attach('real-owner-pins-and-network', { body: JSON.stringify({ project: project.id, source, graph: stored,
      page_errors: errors, calls }, null, 2), contentType: 'application/json' });
  } finally {
    if (info.status !== info.expectedStatus && !page.isClosed()) {
      await page.screenshot({ path: info.outputPath('director-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
    }
    await info.attach('director-console-network-and-errors', { body: JSON.stringify({ errors, console_errors: consoleErrors, calls }, null, 2), contentType: 'application/json' });
    for (const id of owned) expect((await request.delete(`${workspace}/projects/${encodeURIComponent(id)}`, { headers })).status()).toBe(204);
  }
});
