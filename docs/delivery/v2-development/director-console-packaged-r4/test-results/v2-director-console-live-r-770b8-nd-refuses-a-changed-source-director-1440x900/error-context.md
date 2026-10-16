# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-director-console-live.spec.ts >> real File Director graph participant saves, reopens and refuses a changed source
- Location: tests\e2e\v2-director-console-live.spec.ts:3:1

# Error details

```
Error: {"detail":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"code":"EXPERIMENTAL_FEATURE_DISABLED","message":"EXPERIMENTAL_FEATURE_DISABLED","details":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"request_id":"1fc165a3-b85e-452f-9dc0-c33fb92b63b1"}

expect(received).toBe(expected) // Object.is equality

Expected: 200
Received: 404
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
      - generic [ref=e69]: L
      - generic [ref=e70]: local-author
  - navigation "当前创作范围" [ref=e71]:
    - generic [ref=e72]: 创作空间：我的创作空间
    - generic [ref=e73]: /
    - generic [ref=e74]: 小说：导演控制台验收 director-1440x900
    - generic [ref=e75]: /
    - generic [ref=e76]: 故事线：Default Storyline
    - generic [ref=e77]: /
    - generic [ref=e78]: 创作分支：main
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
      - status [ref=e94]: 正在核对项目与权限…
      - status [ref=e95]:
        - strong [ref=e96]: 当前会话无权访问此项目
        - paragraph [ref=e97]: 私人预览已关闭。重新核对身份与范围后再打开。
    - button "收起侧栏" [expanded] [ref=e98] [cursor=pointer]
    - complementary [ref=e102]:
      - separator "调整检查面板宽度" [ref=e103]
      - generic [ref=e104]:
        - generic [ref=e105]: 创作辅助
        - button "收起侧栏" [ref=e106] [cursor=pointer]
      - status [ref=e110]:
        - strong [ref=e111]: 权限失效
        - paragraph [ref=e112]: 重新核对身份与项目范围后再打开。
  - contentinfo [ref=e113]:
    - text: 权限失效 · 独立素材 · 模型调用记录见运行回执
    - button "问助手" [ref=e115] [cursor=pointer]
```

# Test source

```ts
  1   | import { expect, test, type APIResponse } from '@playwright/test';
  2   | 
  3   | test('real File Director graph participant saves, reopens and refuses a changed source', async ({ page, request }, info) => {
  4   |   const owned: string[] = [], errors: string[] = [], calls: { method: string; path: string; status?: number }[] = [];
  5   |   const token = process.env.STUDIO_DIRECTOR_BROWSER_TOKEN;
  6   |   if (!token) throw new Error('Start the original packaged bootstrap launcher before this acceptance; no synthetic session is substituted.');
  7   |   const workspace = '/api/collaboration/admin/workspaces/workspace-a';
  8   |   let headers: Record<string, string> = { 'X-Session-Token': token };
  9   |   page.on('pageerror', error => errors.push(error.message));
  10  |   page.on('request', value => { const path = new URL(value.url()).pathname;
  11  |     if (path.startsWith('/api/')) calls.push({ method: value.method(), path }); });
  12  |   page.on('response', value => { const path = new URL(value.url()).pathname;
  13  |     if (path.startsWith('/api/')) calls.push({ method: value.request().method(), path, status: value.status() }); });
  14  |   const exact = async (response: APIResponse, status: number) => {
> 15  |     expect(response.status(), await response.text()).toBe(status); return response.json();
      |                                                      ^ Error: {"detail":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"code":"EXPERIMENTAL_FEATURE_DISABLED","message":"EXPERIMENTAL_FEATURE_DISABLED","details":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"request_id":"1fc165a3-b85e-452f-9dc0-c33fb92b63b1"}
  16  |   };
  17  |   info.annotations.push({ type: 'verification', description: 'Actual File owner, HTTP routes, rendered React and installed Edge. Authored synthetic text only; no response mocks, model inference or provider calls.' });
  18  |   const enterWorkspace = async () => {
  19  |     await page.getByText('连接已有创作空间', { exact: true }).click();
  20  |     await page.getByLabel('访问凭证', { exact: true }).fill(token);
  21  |     await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  22  |     await page.getByRole('button', { name: '我的创作空间', exact: true }).click();
  23  |   };
  24  |   try {
  25  |     // The original admin and activation owners prepare one authorized project.
  26  |     // Authentication and selecting it still use the shipped browser entry.
  27  |     const response = await request.post(`${workspace}/projects`, { headers,
  28  |       data: { title: `导演控制台验收 ${info.project.name}`, genre: '' } });
  29  |     if (response.status() === 201) { const row = await response.json(); if (typeof row.id === 'string') owned.push(row.id); }
  30  |     const project = await exact(response, 201), base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  31  |     const navigation = await exact(await request.get(`${workspace}/navigation`, { headers }), 200);
  32  |     const scope = navigation.eligible_paths.find((path: { project_id: string }) => path.project_id === project.id);
  33  |     expect(scope).toBeTruthy(); headers = { ...headers, 'X-Branch-Id': scope.branch_id };
  34  |     await exact(await request.post(`${base}/activate`, { headers }), 200);
  35  |     await page.goto('/'); await enterWorkspace();
  36  |     await page.getByRole('button', { name: new RegExp(`导演控制台验收 ${info.project.name}`) }).click();
  37  |     const content = { mode: 'DIRECTOR', title: '有明确视觉方向的导演文档', source_independent: true,
  38  |       source_chapter_ids: [], scenes: [], director_notes: [], shots: [], video_plan: null,
  39  |       visual_target: { style: '冷峻写实', atmosphere: '压抑', color: '青蓝低饱和', rhythm: '缓急交替', reference_works: [] } };
  40  |     const documentUrl = `/api/novels/${encodeURIComponent(project.id)}/experimental/creative/documents`;
  41  |     const document = await exact(await request.post(documentUrl, { data: content, headers }), 201);
  42  |     const catalog = await exact(await request.get(`${base}/graphs/planning-documents`, { headers }), 200);
  43  |     const source = catalog.documents.find((row: { id: string }) => row.id === document.id);
  44  |     expect(source).toMatchObject({ id: document.id, version: document.version, mode: 'DIRECTOR' });
  45  | 
  46  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  47  |     await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  48  |     await page.getByLabel('创作图标题', { exact: true }).fill('浏览器恢复的文本图');
  49  |     await page.getByLabel('节点类型', { exact: true }).selectOption('text_input');
  50  |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  51  |     await page.getByLabel('作者输入文本', { exact: true }).fill('真实浏览器中保留的作者文本 🎬');
  52  |     await expect.poll(() => page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.startsWith('studio-graph-draft:v1:'))
  53  |       .some(([, value]) => value.includes('真实浏览器中保留的作者文本')))).toBe(true);
  54  |     await page.reload(); await enterWorkspace();
  55  |     await page.getByRole('button', { name: new RegExp(`导演控制台验收 ${info.project.name}`) }).click();
  56  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  57  |     await page.getByRole('button', { name: '核对并恢复本机图草稿', exact: true }).click();
  58  |     await expect(page.getByLabel('创作图标题', { exact: true })).toHaveValue('浏览器恢复的文本图');
  59  |     await page.getByRole('button', { name: /^选择节点 文本输入/ }).click();
  60  |     await expect(page.getByLabel('作者输入文本', { exact: true })).toHaveValue('真实浏览器中保留的作者文本 🎬');
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
  73  |     await page.getByLabel('原创作文档', { exact: true }).selectOption(document.id);
  74  |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  75  |     const region = page.getByRole('region', { name: '图节点导演控制台', exact: true });
  76  |     await expect(region).toBeVisible();
  77  |     expect(calls.filter(row => row.path === `${base}/director/workspace/${document.id}`)).toEqual([]);
  78  |     await region.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  79  |     await expect(region.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  80  |     await expect(region.locator('.director-intent__list > li')).toHaveCount(7);
  81  |     await page.evaluate(() => document.fonts.ready);
  82  |     await page.screenshot({ path: info.outputPath('director-console-expanded.png'), fullPage: true });
  83  |     const creatingGraph = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  84  |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  85  |     const graph = await exact(await creatingGraph, 201);
  86  |     expect(graph.definition.nodes).toHaveLength(1);
  87  |     expect(graph.definition.nodes[0].parameters.document_snapshot).toEqual({ id: source.id, version: source.version, digest: source.digest });
  88  | 
  89  |     await page.reload(); await enterWorkspace();
  90  |     await page.getByRole('button', { name: new RegExp(`导演控制台验收 ${info.project.name}`) }).click();
  91  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  92  |     await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  93  |     await page.getByRole('button', { name: `选择节点 导演节点（已保存文档） · ${graph.definition.nodes[0].id}`, exact: true }).click();
  94  |     await page.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  95  |     await expect(page.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  96  | 
  97  |     await exact(await request.put(`${documentUrl}/${document.id}`, { headers, data: { ...content, expected_version: document.version,
  98  |       visual_target: { ...content.visual_target, style: '已修改但未重绑的视觉方向' } } }), 200);
  99  |     await page.getByRole('button', { name: '重新读取原文档', exact: true }).click();
  100 |     await expect(page.getByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/)).toBeVisible();
  101 |     await expect(page.getByLabel('导演意图', { exact: true })).toHaveCount(0);
  102 |     await expect(page.getByText('已修改但未重绑的视觉方向', { exact: true })).toHaveCount(0);
  103 |     await page.screenshot({ path: info.outputPath('director-console-stale-refusal.png'), fullPage: true });
  104 |     expect(errors).toEqual([]);
  105 |     expect(calls.filter(row => !['GET', 'HEAD', 'OPTIONS'].includes(row.method)
  106 |       && /\/(graph-runs|dispatch|generate|director-proposals|media\/tasks)(\/|$)/.test(row.path))).toEqual([]);
  107 |     const stored = await exact(await request.get(`${base}/graphs/${graph.id}`, { headers }), 200);
  108 |     expect(stored.version).toBe(graph.version);
  109 |     expect(stored.definition.nodes[0].parameters.document_snapshot).toEqual(graph.definition.nodes[0].parameters.document_snapshot);
  110 |     await info.attach('real-owner-pins-and-network', { body: JSON.stringify({ project: project.id, source, graph: stored,
  111 |       page_errors: errors, calls }, null, 2), contentType: 'application/json' });
  112 |   } finally {
  113 |     if (info.status !== info.expectedStatus && !page.isClosed()) {
  114 |       await page.screenshot({ path: info.outputPath('director-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
  115 |     }
```