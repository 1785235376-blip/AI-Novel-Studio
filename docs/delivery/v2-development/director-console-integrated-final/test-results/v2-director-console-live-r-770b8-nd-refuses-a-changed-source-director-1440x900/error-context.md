# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-director-console-live.spec.ts >> real File Director graph participant saves, reopens and refuses a changed source
- Location: tests\e2e\v2-director-console-live.spec.ts:3:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 201
Received: 400
```

# Test source

```ts
  1   | import { expect, test, type APIResponse } from '@playwright/test';
  2   | 
  3   | test('real File Director graph participant saves, reopens and refuses a changed source', async ({ page, request }, info) => {
  4   |   const owned: string[] = [], errors: string[] = [], consoleErrors: string[] = [], calls: { method: string; path: string; status?: number }[] = [];
  5   |   const token = process.env.STUDIO_DIRECTOR_BROWSER_TOKEN;
  6   |   if (!token) throw new Error('Start the original packaged bootstrap launcher before this acceptance; no synthetic session is substituted.');
  7   |   const workspace = '/api/collaboration/admin/workspaces/workspace-a';
  8   |   let headers: Record<string, string> = { 'X-Session-Token': token };
  9   |   page.on('pageerror', error => errors.push(error.message));
  10  |   page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  11  |   page.on('request', value => { const path = new URL(value.url()).pathname;
  12  |     if (path.startsWith('/api/')) calls.push({ method: value.method(), path }); });
  13  |   page.on('response', value => { const path = new URL(value.url()).pathname;
  14  |     if (path.startsWith('/api/')) calls.push({ method: value.request().method(), path, status: value.status() }); });
  15  |   const exact = async (response: APIResponse, status: number) => {
> 16  |     expect(response.status(), await response.text()).toBe(status); return response.json();
      |                                                      ^ Error: expect(received).toBe(expected) // Object.is equality
  17  |   };
  18  |   info.annotations.push({ type: 'verification', description: 'Actual File owner, HTTP routes, rendered React and installed Edge. Authored synthetic text only; no response mocks, model inference or provider calls.' });
  19  |   const enterWorkspace = async () => {
  20  |     await page.getByText('连接已有创作空间', { exact: true }).click();
  21  |     await page.getByLabel('访问凭证', { exact: true }).fill(token);
  22  |     await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  23  |     await page.getByRole('button', { name: '我的创作空间', exact: true }).click();
  24  |   };
  25  |   try {
  26  |     // The original admin and activation owners prepare one authorized project.
  27  |     // Authentication and selecting it still use the shipped browser entry.
  28  |     const response = await request.post(`${workspace}/projects`, { headers,
  29  |       data: { title: `导演控制台验收 ${info.project.name}`, genre: '' } });
  30  |     if (response.status() === 201) { const row = await response.json(); if (typeof row.id === 'string') owned.push(row.id); }
  31  |     const project = await exact(response, 201), base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  32  |     const navigation = await exact(await request.get(`${workspace}/navigation`, { headers }), 200);
  33  |     const scope = navigation.eligible_paths.find((path: { project_id: string }) => path.project_id === project.id);
  34  |     expect(scope).toBeTruthy(); headers = { ...headers, 'X-Branch-Id': scope.branch_id };
  35  |     await exact(await request.post(`${base}/activate`, { headers }), 200);
  36  |     await page.goto('/'); await enterWorkspace();
  37  |     await page.getByRole('button', { name: new RegExp(`导演控制台验收 ${info.project.name}`) }).click();
  38  |     const content = { mode: 'DIRECTOR', title: '有明确视觉方向的导演文档', source_independent: true,
  39  |       source_chapter_ids: [], scenes: [], director_notes: [], shots: [], video_plan: null,
  40  |       visual_target: { style: '冷峻写实', atmosphere: '压抑', color: '青蓝低饱和', rhythm: '缓急交替', reference_works: [] } };
  41  |     const documentUrl = `/api/novels/${encodeURIComponent(project.id)}/experimental/creative/documents`;
  42  |     const document = await exact(await request.post(documentUrl, { data: content, headers }), 201);
  43  |     const catalog = await exact(await request.get(`${base}/graphs/planning-documents`, { headers }), 200);
  44  |     const source = catalog.documents.find((row: { id: string }) => row.id === document.id);
  45  |     expect(source).toMatchObject({ id: document.id, version: document.version, mode: 'DIRECTOR' });
  46  | 
  47  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  48  |     await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  49  |     await page.getByLabel('创作图标题', { exact: true }).fill('浏览器恢复的文本图');
  50  |     await page.getByLabel('节点类型', { exact: true }).selectOption('text_input');
  51  |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  52  |     await page.getByRole('textbox', { name: '作者输入文本', exact: true }).fill('真实浏览器中保留的作者文本 🎬');
  53  |     await expect.poll(() => page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.startsWith('studio-graph-draft:v1:'))
  54  |       .some(([, value]) => value.includes('真实浏览器中保留的作者文本')))).toBe(true);
  55  |     await page.reload();
  56  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  57  |     await page.getByRole('button', { name: '核对并恢复本机图草稿', exact: true }).click();
  58  |     await expect(page.getByLabel('创作图标题', { exact: true })).toHaveValue('浏览器恢复的文本图');
  59  |     await page.getByRole('button', { name: /^选择节点 文本输入/ }).click();
  60  |     await expect(page.getByRole('textbox', { name: '作者输入文本', exact: true })).toHaveValue('真实浏览器中保留的作者文本 🎬');
  61  |     const savingText = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  62  |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  63  |     const textGraph = await exact(await savingText, 201);
  64  |     expect(textGraph.definition.nodes[0].parameters.text).toBe('真实浏览器中保留的作者文本 🎬');
  65  |     await page.screenshot({ path: info.outputPath('canvas-text-draft-restored.png'), fullPage: true });
  66  |     await page.getByRole('button', { name: '新建空图', exact: true }).click();
  67  |     await page.getByLabel('创作图标题', { exact: true }).fill('导演控制台来源绑定');
  68  |     await page.getByRole('button', { name: '明确读取导演、分镜与视觉制作节点目录', exact: true }).click();
  69  |     await page.getByLabel('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核', { exact: true }).check();
  70  |     await page.getByRole('button', { name: '明确采用图片图 v4', exact: true }).click();
  71  |     await page.getByLabel('节点类型', { exact: true }).selectOption('director_plan');
  72  |     await page.getByRole('button', { name: '明确读取已保存导演与分镜文档', exact: true }).click();
  73  |     await page.getByRole('combobox', { name: /^原创作文档/ }).selectOption(document.id);
  74  |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  75  |     const region = page.getByRole('region', { name: '图节点导演控制台', exact: true });
  76  |     await expect(region).toBeVisible();
  77  |     expect(calls.filter(row => row.path === `${base}/director/workspace/${document.id}`)).toEqual([]);
  78  |     await region.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  79  |     await expect(region.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  80  |     await expect(region.locator('.director-intent__list > li')).toHaveCount(7);
  81  |     const geometry = await page.evaluate(() => {
  82  |       const rect = (selector: string) => { const value = document.querySelector(selector)!.getBoundingClientRect();
  83  |         return { width: value.width, height: value.height, y: value.y }; };
  84  |       return { header: rect('.global-header'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'),
  85  |         scroll_width: document.documentElement.scrollWidth, viewport_width: innerWidth };
  86  |     });
  87  |     expect(geometry.header).toMatchObject({ height: 56, y: 0 });
  88  |     expect(geometry.sidebar.width).toBe(248); expect(geometry.inspector.width).toBe(340);
  89  |     expect(geometry.scroll_width).toBeLessThanOrEqual(geometry.viewport_width);
  90  |     await info.attach('real-shell-geometry', { body: JSON.stringify(geometry), contentType: 'application/json' });
  91  |     await page.evaluate(() => document.fonts.ready);
  92  |     await page.screenshot({ path: info.outputPath('director-console-expanded.png'), fullPage: true });
  93  |     await region.locator('[data-field="visual_goal"]').scrollIntoViewIfNeeded();
  94  |     await page.screenshot({ path: info.outputPath('director-console-intent-scrolled.png'), fullPage: true });
  95  |     await region.locator('[data-field="performance_direction"]').scrollIntoViewIfNeeded();
  96  |     await page.screenshot({ path: info.outputPath('director-console-intent-lower.png'), fullPage: true });
  97  |     const creatingGraph = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  98  |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  99  |     const graph = await exact(await creatingGraph, 201);
  100 |     expect(graph.definition.nodes).toHaveLength(1);
  101 |     expect(graph.definition.nodes[0].parameters.document_snapshot).toEqual({ id: source.id, version: source.version, digest: source.digest });
  102 | 
  103 |     await page.reload();
  104 |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  105 |     await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  106 |     await page.getByRole('button', { name: `选择节点 导演节点（已保存文档） · ${graph.definition.nodes[0].id}`, exact: true }).click();
  107 |     await page.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  108 |     await expect(page.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  109 | 
  110 |     await exact(await request.put(`${documentUrl}/${document.id}`, { headers, data: { ...content, expected_version: document.version,
  111 |       visual_target: { ...content.visual_target, style: '已修改但未重绑的视觉方向' } } }), 200);
  112 |     await page.getByRole('button', { name: '重新读取原文档', exact: true }).click();
  113 |     await expect(page.getByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/)).toBeVisible();
  114 |     await expect(page.getByLabel('导演意图', { exact: true })).toHaveCount(0);
  115 |     await expect(page.getByText('已修改但未重绑的视觉方向', { exact: true })).toHaveCount(0);
  116 |     await page.screenshot({ path: info.outputPath('director-console-stale-refusal.png'), fullPage: true });
```