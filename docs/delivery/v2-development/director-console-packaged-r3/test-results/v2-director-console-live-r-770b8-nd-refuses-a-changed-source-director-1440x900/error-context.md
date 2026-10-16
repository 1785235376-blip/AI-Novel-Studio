# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-director-console-live.spec.ts >> real File Director graph participant saves, reopens and refuses a changed source
- Location: tests\e2e\v2-director-console-live.spec.ts:3:1

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: locator.fill: Test timeout of 90000ms exceeded.
Call log:
  - waiting for getByLabel('空白项目名称', { exact: true })

```

# Page snapshot

```yaml
- main [ref=e3]:
  - heading "AI Novel Studio" [level=1] [ref=e4]
  - paragraph [ref=e5]: 选择创作空间和小说，继续写作。
  - generic [ref=e6]:
    - heading "新建小说" [level=2] [ref=e8]
    - generic [ref=e9]:
      - text: 小说名称
      - textbox "小说名称" [ref=e10]:
        - /placeholder: 输入小说名称
    - button "创建并打开" [disabled] [ref=e11] [cursor=pointer]
  - status [ref=e12]:
    - strong [ref=e13]: 这个创作空间还没有小说
    - paragraph [ref=e14]: 输入小说名称，系统会同时建立默认故事线和主分支。
  - generic [ref=e16]:
    - heading "本机作品" [level=2] [ref=e17]
    - paragraph [ref=e18]: 创建或打开保存在本机的小说。
    - textbox "小说名称" [ref=e19]
    - button "创建小说" [ref=e20] [cursor=pointer]
    - generic [ref=e21]:
      - heading "导入小说" [level=2] [ref=e23]
      - list "导入进度" [ref=e24]:
        - listitem [ref=e25]:
          - generic [ref=e30]: 选择文件
        - listitem [ref=e31]:
          - generic [ref=e37]: 检查章节
        - listitem [ref=e38]:
          - generic [ref=e41]: 导入与资料审核
      - generic [ref=e42] [cursor=pointer]:
        - generic [ref=e47]: 选择小说文件
        - button "选择要导入的小说文件" [ref=e48]
      - paragraph [ref=e49]: 支持 TXT、Markdown、JSON、Word 和 PDF，单个文件不超过 25 MiB。导入前会先生成预览，不会立即改写项目。
      - status [ref=e50]:
        - strong [ref=e51]: 尚未选择文件
        - paragraph [ref=e52]: 选择文件后先检查章节结构，不会立即写入项目。
```

# Test source

```ts
  1  | import { expect, test, type APIResponse } from '@playwright/test';
  2  | 
  3  | test('real File Director graph participant saves, reopens and refuses a changed source', async ({ page, request }, info) => {
  4  |   const owned: string[] = [], errors: string[] = [], calls: { method: string; path: string; status?: number }[] = [];
  5  |   const token = process.env.STUDIO_DIRECTOR_BROWSER_TOKEN;
  6  |   if (!token) throw new Error('Start the original packaged bootstrap launcher before this acceptance; no synthetic session is substituted.');
  7  |   const workspace = '/api/collaboration/admin/workspaces/workspace-a';
  8  |   let headers: Record<string, string> = { 'X-Session-Token': token };
  9  |   page.on('pageerror', error => errors.push(error.message));
  10 |   page.on('request', value => { const path = new URL(value.url()).pathname;
  11 |     if (path.startsWith('/api/')) calls.push({ method: value.method(), path }); });
  12 |   page.on('response', value => { const path = new URL(value.url()).pathname;
  13 |     if (path.startsWith('/api/')) calls.push({ method: value.request().method(), path, status: value.status() }); });
  14 |   const exact = async (response: APIResponse, status: number) => {
  15 |     expect(response.status(), await response.text()).toBe(status); return response.json();
  16 |   };
  17 |   info.annotations.push({ type: 'verification', description: 'Actual File owner, HTTP routes, rendered React and installed Edge. Authored synthetic text only; no response mocks, model inference or provider calls.' });
  18 |   const enterWorkspace = async () => {
  19 |     await page.getByText('连接已有创作空间', { exact: true }).click();
  20 |     await page.getByLabel('访问凭证', { exact: true }).fill(token);
  21 |     await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  22 |     await page.getByRole('button', { name: '我的创作空间', exact: true }).click();
  23 |   };
  24 |   try {
  25 |     await page.goto('/'); await enterWorkspace();
> 26 |     await page.getByLabel('空白项目名称', { exact: true }).fill(`导演控制台验收 ${info.project.name}`);
     |                                                      ^ Error: locator.fill: Test timeout of 90000ms exceeded.
  27 |     const creating = page.waitForResponse(value => new URL(value.url()).pathname === `${workspace}/projects` && value.request().method() === 'POST');
  28 |     await page.getByRole('button', { name: '创建空白项目', exact: true }).click();
  29 |     const response = await creating;
  30 |     if (response.status() === 201) { const row = await response.json(); if (typeof row.id === 'string') owned.push(row.id); }
  31 |     const project = await exact(response, 201), base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  32 |     const navigation = await exact(await request.get(`${workspace}/navigation`, { headers }), 200);
  33 |     const scope = navigation.eligible_paths.find((path: { project_id: string }) => path.project_id === project.id);
  34 |     expect(scope).toBeTruthy(); headers = { ...headers, 'X-Branch-Id': scope.branch_id };
  35 |     const content = { mode: 'DIRECTOR', title: '有明确视觉方向的导演文档', source_independent: true,
  36 |       source_chapter_ids: [], scenes: [], director_notes: [], shots: [], video_plan: null,
  37 |       visual_target: { style: '冷峻写实', atmosphere: '压抑', color: '青蓝低饱和', rhythm: '缓急交替', reference_works: [] } };
  38 |     const documentUrl = `/api/novels/${encodeURIComponent(project.id)}/experimental/creative/documents`;
  39 |     const document = await exact(await request.post(documentUrl, { data: content, headers }), 201);
  40 |     const catalog = await exact(await request.get(`${base}/graphs/planning-documents`, { headers }), 200);
  41 |     const source = catalog.documents.find((row: { id: string }) => row.id === document.id);
  42 |     expect(source).toMatchObject({ id: document.id, version: document.version, mode: 'DIRECTOR' });
  43 | 
  44 |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  45 |     await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  46 |     await page.getByLabel('创作图标题', { exact: true }).fill('导演控制台来源绑定');
  47 |     await page.getByRole('button', { name: '明确读取导演、分镜与视觉制作节点目录', exact: true }).click();
  48 |     await page.getByLabel('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核', { exact: true }).check();
  49 |     await page.getByRole('button', { name: '明确采用图片图 v4', exact: true }).click();
  50 |     await page.getByLabel('节点类型', { exact: true }).selectOption('director_plan');
  51 |     await page.getByRole('button', { name: '明确读取已保存导演与分镜文档', exact: true }).click();
  52 |     await page.getByLabel('原创作文档', { exact: true }).selectOption(document.id);
  53 |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  54 |     const region = page.getByRole('region', { name: '图节点导演控制台', exact: true });
  55 |     await expect(region).toBeVisible();
  56 |     expect(calls.filter(row => row.path === `${base}/director/workspace/${document.id}`)).toEqual([]);
  57 |     await region.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  58 |     await expect(region.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  59 |     await expect(region.locator('.director-intent__list > li')).toHaveCount(7);
  60 |     await page.evaluate(() => document.fonts.ready);
  61 |     await page.screenshot({ path: info.outputPath('director-console-expanded.png'), fullPage: true });
  62 |     const creatingGraph = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  63 |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  64 |     const graph = await exact(await creatingGraph, 201);
  65 |     expect(graph.definition.nodes).toHaveLength(1);
  66 |     expect(graph.definition.nodes[0].parameters.document_snapshot).toEqual({ id: source.id, version: source.version, digest: source.digest });
  67 | 
  68 |     await page.reload(); await enterWorkspace();
  69 |     await page.getByRole('button', { name: new RegExp(`导演控制台验收 ${info.project.name}`) }).click();
  70 |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  71 |     await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  72 |     await page.getByRole('button', { name: `选择节点 导演节点（已保存文档） · ${graph.definition.nodes[0].id}`, exact: true }).click();
  73 |     await page.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  74 |     await expect(page.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  75 | 
  76 |     await exact(await request.put(`${documentUrl}/${document.id}`, { headers, data: { ...content, expected_version: document.version,
  77 |       visual_target: { ...content.visual_target, style: '已修改但未重绑的视觉方向' } } }), 200);
  78 |     await page.getByRole('button', { name: '重新读取原文档', exact: true }).click();
  79 |     await expect(page.getByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/)).toBeVisible();
  80 |     await expect(page.getByLabel('导演意图', { exact: true })).toHaveCount(0);
  81 |     await expect(page.getByText('已修改但未重绑的视觉方向', { exact: true })).toHaveCount(0);
  82 |     await page.screenshot({ path: info.outputPath('director-console-stale-refusal.png'), fullPage: true });
  83 |     expect(errors).toEqual([]);
  84 |     expect(calls.filter(row => !['GET', 'HEAD', 'OPTIONS'].includes(row.method)
  85 |       && /\/(graph-runs|dispatch|generate|director-proposals|media\/tasks)(\/|$)/.test(row.path))).toEqual([]);
  86 |     const stored = await exact(await request.get(`${base}/graphs/${graph.id}`, { headers }), 200);
  87 |     expect(stored.version).toBe(graph.version);
  88 |     expect(stored.definition.nodes[0].parameters.document_snapshot).toEqual(graph.definition.nodes[0].parameters.document_snapshot);
  89 |     await info.attach('real-owner-pins-and-network', { body: JSON.stringify({ project: project.id, source, graph: stored,
  90 |       page_errors: errors, calls }, null, 2), contentType: 'application/json' });
  91 |   } finally {
  92 |     if (info.status !== info.expectedStatus && !page.isClosed()) {
  93 |       await page.screenshot({ path: info.outputPath('director-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
  94 |     }
  95 |     await info.attach('director-console-network-and-errors', { body: JSON.stringify({ errors, calls }, null, 2), contentType: 'application/json' });
  96 |     for (const id of owned) expect((await request.delete(`${workspace}/projects/${encodeURIComponent(id)}`, { headers })).status()).toBe(204);
  97 |   }
  98 | });
  99 | 
```