# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-director-console-live.spec.ts >> real File Director graph participant saves, reopens and refuses a changed source
- Location: tests\e2e\v2-director-console-live.spec.ts:3:1

# Error details

```
Error: {"detail":{"code":"SESSION_REQUIRED"},"code":"SESSION_REQUIRED","message":"SESSION_REQUIRED","details":{"code":"SESSION_REQUIRED"},"request_id":"5094158a-8d63-4335-bd21-627fb1fd459b"}

expect(received).toBe(expected) // Object.is equality

Expected: 200
Received: 401
```

# Page snapshot

```yaml
- generic [ref=e3]:
  - banner [ref=e4]:
    - generic "AI Novel Studio" [ref=e5]:
      - generic [ref=e9]:
        - strong [ref=e10]: AI Novel
        - generic [ref=e11]: Studio
    - tablist "创作模块" [ref=e12]:
      - tab "小说" [ref=e13] [cursor=pointer]
      - tab "图片" [selected] [ref=e17] [cursor=pointer]
      - tab "视频" [ref=e23] [cursor=pointer]
      - tab "资产" [ref=e28] [cursor=pointer]
      - tab "声音" [ref=e32] [cursor=pointer]
      - tab "主控" [ref=e38] [cursor=pointer]
      - tab "插件" [ref=e52] [cursor=pointer]
      - tab "工作流" [ref=e56] [cursor=pointer]
    - button "打开全局命令" [ref=e62] [cursor=pointer]:
      - generic [ref=e66]: 搜索作品、章节与素材
      - generic [ref=e67]: Ctrl K
    - generic [ref=e68]:
      - generic [ref=e69]: 本
      - generic [ref=e70]: 本机作者
  - navigation "当前创作范围" [ref=e71]:
    - generic [ref=e72]: 创作空间：本机作品
    - generic [ref=e73]: /
    - generic [ref=e74]: 小说：导演控制台验收 director-1440x900
    - generic [ref=e75]: /
    - generic [ref=e76]: 故事线：默认故事线
    - generic [ref=e77]: /
    - generic [ref=e78]: 创作分支：主线
  - main [ref=e79]:
    - complementary [ref=e80]:
      - generic [ref=e81]:
        - heading "独立创作" [level=2] [ref=e82]
        - paragraph [ref=e83]: 图片、视频和声音共享项目资产。连接其它模块由你决定。
        - button "返回项目列表" [ref=e84] [cursor=pointer]
        - group [ref=e85]:
          - generic "项目存储" [ref=e86] [cursor=pointer]
    - generic [ref=e88]:
      - generic [ref=e89]:
        - heading "独立素材工作区" [level=2] [ref=e91]
        - paragraph [ref=e92]: 无需小说、章节或模型，导入素材即可保存和导出。
        - paragraph [ref=e93]: 上传会保存文件，并记录“外部导入”；许可默认未指定，可在来源声明中补充。下载原始文件保留原格式，不进行重新编码。
      - status [ref=e94]:
        - strong [ref=e95]: 当前会话无权访问此项目
        - paragraph [ref=e96]: 私人预览已关闭。重新核对身份与范围后再打开。
    - button "收起侧栏" [expanded] [ref=e97] [cursor=pointer]
    - complementary [ref=e101]:
      - separator "调整检查面板宽度" [ref=e102]
      - generic [ref=e103]:
        - generic [ref=e104]: 创作辅助
        - button "收起侧栏" [ref=e105] [cursor=pointer]
      - status [ref=e109]:
        - strong [ref=e110]: 权限失效
        - paragraph [ref=e111]: 重新核对身份与项目范围后再打开。
  - contentinfo [ref=e112]:
    - text: 权限失效 · 独立素材 · 模型调用记录见运行回执
    - button "问助手" [ref=e114] [cursor=pointer]
```

# Test source

```ts
  1  | import { expect, test, type APIResponse } from '@playwright/test';
  2  | 
  3  | test('real File Director graph participant saves, reopens and refuses a changed source', async ({ page, request }, info) => {
  4  |   const owned: string[] = [], errors: string[] = [], calls: { method: string; path: string; status?: number }[] = [];
  5  |   page.on('pageerror', error => errors.push(error.message));
  6  |   page.on('request', value => { const path = new URL(value.url()).pathname;
  7  |     if (path.startsWith('/api/')) calls.push({ method: value.method(), path }); });
  8  |   page.on('response', value => { const path = new URL(value.url()).pathname;
  9  |     if (path.startsWith('/api/')) calls.push({ method: value.request().method(), path, status: value.status() }); });
  10 |   const exact = async (response: APIResponse, status: number) => {
> 11 |     expect(response.status(), await response.text()).toBe(status); return response.json();
     |                                                      ^ Error: {"detail":{"code":"SESSION_REQUIRED"},"code":"SESSION_REQUIRED","message":"SESSION_REQUIRED","details":{"code":"SESSION_REQUIRED"},"request_id":"5094158a-8d63-4335-bd21-627fb1fd459b"}
  12 |   };
  13 |   info.annotations.push({ type: 'verification', description: 'Actual File owner, HTTP routes, rendered React and installed Edge. Authored synthetic text only; no response mocks, model inference or provider calls.' });
  14 |   try {
  15 |     await page.goto('/');
  16 |     await page.getByLabel('空白项目名称', { exact: true }).fill(`导演控制台验收 ${info.project.name}`);
  17 |     const creating = page.waitForResponse(value => new URL(value.url()).pathname === '/api/experimental/projects' && value.request().method() === 'POST');
  18 |     await page.getByRole('button', { name: '创建空白项目', exact: true }).click();
  19 |     const response = await creating;
  20 |     if (response.status() === 201) { const row = await response.json(); if (typeof row.id === 'string') owned.push(row.id); }
  21 |     const project = await exact(response, 201), base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  22 |     const content = { mode: 'DIRECTOR', title: '有明确视觉方向的导演文档', source_independent: true,
  23 |       source_chapter_ids: [], scenes: [], director_notes: [], shots: [], video_plan: null,
  24 |       visual_target: { style: '冷峻写实', atmosphere: '压抑', color: '青蓝低饱和', rhythm: '缓急交替', reference_works: [] } };
  25 |     const documentUrl = `/api/novels/${encodeURIComponent(project.id)}/experimental/creative/documents`;
  26 |     const document = await exact(await request.post(documentUrl, { data: content }), 201);
  27 |     const catalog = await exact(await request.get(`${base}/graphs/planning-documents`), 200);
  28 |     const source = catalog.documents.find((row: { id: string }) => row.id === document.id);
  29 |     expect(source).toMatchObject({ id: document.id, version: document.version, mode: 'DIRECTOR' });
  30 | 
  31 |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  32 |     await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  33 |     await page.getByLabel('创作图标题', { exact: true }).fill('导演控制台来源绑定');
  34 |     await page.getByRole('button', { name: '明确读取导演、分镜与视觉制作节点目录', exact: true }).click();
  35 |     await page.getByLabel('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核', { exact: true }).check();
  36 |     await page.getByRole('button', { name: '明确采用图片图 v4', exact: true }).click();
  37 |     await page.getByLabel('节点类型', { exact: true }).selectOption('director_plan');
  38 |     await page.getByRole('button', { name: '明确读取已保存导演与分镜文档', exact: true }).click();
  39 |     await page.getByLabel('原创作文档', { exact: true }).selectOption(document.id);
  40 |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  41 |     const region = page.getByRole('region', { name: '图节点导演控制台', exact: true });
  42 |     await expect(region).toBeVisible();
  43 |     expect(calls.filter(row => row.path === `${base}/director/workspace/${document.id}`)).toEqual([]);
  44 |     await region.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  45 |     await expect(region.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  46 |     await expect(region.locator('.director-intent__list > li')).toHaveCount(7);
  47 |     await page.evaluate(() => document.fonts.ready);
  48 |     await page.screenshot({ path: info.outputPath('director-console-expanded.png'), fullPage: true });
  49 |     const creatingGraph = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  50 |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  51 |     const graph = await exact(await creatingGraph, 201);
  52 |     expect(graph.definition.nodes).toHaveLength(1);
  53 |     expect(graph.definition.nodes[0].parameters.document_snapshot).toEqual({ id: source.id, version: source.version, digest: source.digest });
  54 | 
  55 |     await page.reload();
  56 |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  57 |     await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  58 |     await page.getByRole('button', { name: `选择节点 导演节点（已保存文档） · ${graph.definition.nodes[0].id}`, exact: true }).click();
  59 |     await page.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  60 |     await expect(page.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  61 | 
  62 |     await exact(await request.put(`${documentUrl}/${document.id}`, { data: { ...content, expected_version: document.version,
  63 |       visual_target: { ...content.visual_target, style: '已修改但未重绑的视觉方向' } } }), 200);
  64 |     await page.getByRole('button', { name: '重新读取原文档', exact: true }).click();
  65 |     await expect(page.getByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/)).toBeVisible();
  66 |     await expect(page.getByLabel('导演意图', { exact: true })).toHaveCount(0);
  67 |     await expect(page.getByText('已修改但未重绑的视觉方向', { exact: true })).toHaveCount(0);
  68 |     await page.screenshot({ path: info.outputPath('director-console-stale-refusal.png'), fullPage: true });
  69 |     expect(errors).toEqual([]);
  70 |     expect(calls.filter(row => !['GET', 'HEAD', 'OPTIONS'].includes(row.method)
  71 |       && /\/(graph-runs|dispatch|generate|director-proposals|media\/tasks)(\/|$)/.test(row.path))).toEqual([]);
  72 |     const stored = await exact(await request.get(`${base}/graphs/${graph.id}`), 200);
  73 |     expect(stored.version).toBe(graph.version);
  74 |     expect(stored.definition.nodes[0].parameters.document_snapshot).toEqual(graph.definition.nodes[0].parameters.document_snapshot);
  75 |     await info.attach('real-owner-pins-and-network', { body: JSON.stringify({ project: project.id, source, graph: stored,
  76 |       page_errors: errors, calls }, null, 2), contentType: 'application/json' });
  77 |   } finally {
  78 |     if (info.status !== info.expectedStatus && !page.isClosed()) {
  79 |       await page.screenshot({ path: info.outputPath('director-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
  80 |     }
  81 |     await info.attach('director-console-network-and-errors', { body: JSON.stringify({ errors, calls }, null, 2), contentType: 'application/json' });
  82 |     for (const id of owned) expect((await request.delete(`/api/novels/${encodeURIComponent(id)}`)).status()).toBe(204);
  83 |   }
  84 | });
  85 | 
```