# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-director-console-live.spec.ts >> real File Director graph participant saves, reopens and refuses a changed source
- Location: tests\e2e\v2-director-console-live.spec.ts:3:1

# Error details

```
Error: {"detail":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"code":"EXPERIMENTAL_FEATURE_DISABLED","message":"EXPERIMENTAL_FEATURE_DISABLED","details":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"request_id":"7d4472ee-a02e-4579-9f64-8c54c40af253"}

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
      - tab "小说" [selected] [ref=e13] [cursor=pointer]
      - tab "图片" [ref=e17] [cursor=pointer]
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
        - generic [ref=e82]:
          - generic [ref=e83]: 小说结构
          - strong [ref=e84]: 章节导航
        - generic [ref=e85]:
          - button "打开 V2 创作工作台" [ref=e87] [cursor=pointer]
          - generic [ref=e88]:
            - generic [ref=e89]:
              - heading "作品结构" [level=2] [ref=e90]
              - button "新建章节" [ref=e91] [cursor=pointer]
            - status [ref=e92]: 正在加载章节
            - region [ref=e93]:
              - heading "已移出章节" [level=3] [ref=e94]
              - paragraph [ref=e95]: 目前没有已移出章节。
        - generic [ref=e96]:
          - generic [ref=e97]: 工作区
          - strong [ref=e98]: 创作工具
        - generic [ref=e100]:
          - button "打开功能导航" [ref=e102] [cursor=pointer]: 功能导航
          - tooltip "打开功能导航"
    - generic [ref=e107]:
      - generic [ref=e109]:
        - generic [ref=e110]:
          - generic [ref=e111]:
            - generic [ref=e112]: 当前章节
            - generic [ref=e113]: 未选择章节
          - generic [ref=e114]: 0 字
        - generic [ref=e115]:
          - status [ref=e116]: 正在打开章节…
          - button "保存" [disabled] [ref=e119]
      - generic [ref=e121]:
        - strong [ref=e122]: 当前还没有打开的章节
        - paragraph [ref=e123]: 在左侧新建或选择章节，开始写作。
    - button "收起侧栏" [expanded] [ref=e124] [cursor=pointer]
    - complementary [ref=e128]:
      - separator "调整检查面板宽度" [ref=e129]
      - generic [ref=e130]:
        - generic [ref=e131]: 创作辅助
        - button "收起侧栏" [ref=e132] [cursor=pointer]
      - generic [ref=e136]:
        - region "当前写作上下文" [ref=e137]:
          - generic [ref=e138]: 当前章节
          - strong [ref=e139]: 未选择章节
          - generic [ref=e140]: 从左侧章节树选择章节
        - paragraph [ref=e142]: 正在加载写作目标…
        - generic [ref=e143]:
          - heading "AI 写作助手" [level=2] [ref=e145]
          - tablist "AI 写作方式" [ref=e146]:
            - tab "创作下一章" [selected] [ref=e147] [cursor=pointer]
            - tab "改写" [ref=e148] [cursor=pointer]
            - tab "润色" [ref=e149] [cursor=pointer]
            - tab "头脑风暴" [ref=e150] [cursor=pointer]
          - generic [ref=e151]:
            - text: 文本模型
            - combobox "文本模型" [ref=e152]:
              - option "尚未选择文本模型" [selected]
          - region [ref=e153]:
            - generic [ref=e154]:
              - strong [ref=e155]: 当前模型
              - generic [ref=e156]: 尚未选择模型
            - status [ref=e157]: 选择模型后可查看是否能够开始写作。
          - group "候选方案数量" [ref=e158]:
            - generic [ref=e159]: 候选方案
            - button "1" [pressed] [ref=e160] [cursor=pointer]
            - button "2" [ref=e161] [cursor=pointer]
            - button "3" [ref=e162] [cursor=pointer]
          - generic [ref=e163]:
            - text: 附加要求（可选）
            - textbox "附加要求（可选）" [ref=e164]:
              - /placeholder: 例如：保持紧张节奏，突出人物犹豫。
          - generic [ref=e165]:
            - text: 写作风格（可选）
            - textbox "写作风格（可选）" [ref=e166]:
              - /placeholder: 例如：克制、冷峻、短句为主
          - generic "写作风格预设" [ref=e167]:
            - button "克制冷峻 · 短句为主" [ref=e168] [cursor=pointer]
            - button "细腻抒情 · 强化感官" [ref=e169] [cursor=pointer]
            - button "紧张悬疑 · 加快节奏" [ref=e170] [cursor=pointer]
            - button "轻松幽默 · 对话自然" [ref=e171] [cursor=pointer]
          - button "生成创作下一章草稿" [disabled] [ref=e173]
          - region [ref=e174]:
            - generic [ref=e176]:
              - strong [ref=e177]: 生成流程
              - generic [ref=e178]: 上下文 → 计划 → 草稿 → 审核
            - list [ref=e179]:
              - listitem [ref=e180]:
                - generic [ref=e184]:
                  - generic [ref=e185]:
                    - strong [ref=e186]: 读取创作上下文
                    - generic [ref=e187]: 等待
                  - generic [ref=e188]: 开始生成后读取
              - listitem [ref=e189]:
                - generic [ref=e193]:
                  - generic [ref=e194]:
                    - strong [ref=e195]: 建立生成计划
                    - generic [ref=e196]: 等待
                  - generic [ref=e197]: 等待任务创建
              - listitem [ref=e198]:
                - generic [ref=e202]:
                  - generic [ref=e203]:
                    - strong [ref=e204]: 生成章节草稿
                    - generic [ref=e205]: 等待
                  - generic [ref=e206]: 等待生成
              - listitem [ref=e207]:
                - generic [ref=e211]:
                  - generic [ref=e212]:
                    - strong [ref=e213]: 作者审核
                    - generic [ref=e214]: 等待
                  - generic [ref=e215]: 等待可审核草稿
          - status [ref=e216]:
            - strong [ref=e217]: 尚未生成草稿
            - paragraph [ref=e218]: 选择写作方式并生成后，可在这里预览、比较和决定是否采用。
  - contentinfo [ref=e219]:
    - text: 保存：正在打开章节… · 连接：协作服务 · AI 任务：无运行任务
    - button "问助手" [ref=e221] [cursor=pointer]
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
      |                                                      ^ Error: {"detail":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"code":"EXPERIMENTAL_FEATURE_DISABLED","message":"EXPERIMENTAL_FEATURE_DISABLED","details":{"code":"EXPERIMENTAL_FEATURE_DISABLED","feature":"ai_execution_v2"},"request_id":"7d4472ee-a02e-4579-9f64-8c54c40af253"}
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
  54  |     await page.reload();
  55  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  56  |     await page.getByRole('button', { name: '核对并恢复本机图草稿', exact: true }).click();
  57  |     await expect(page.getByLabel('创作图标题', { exact: true })).toHaveValue('浏览器恢复的文本图');
  58  |     await page.getByRole('button', { name: /^选择节点 文本输入/ }).click();
  59  |     await expect(page.getByLabel('作者输入文本', { exact: true })).toHaveValue('真实浏览器中保留的作者文本 🎬');
  60  |     const savingText = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  61  |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  62  |     const textGraph = await exact(await savingText, 201);
  63  |     expect(textGraph.definition.nodes[0].parameters.text).toBe('真实浏览器中保留的作者文本 🎬');
  64  |     await page.screenshot({ path: info.outputPath('canvas-text-draft-restored.png'), fullPage: true });
  65  |     await page.getByRole('button', { name: '新建空图', exact: true }).click();
  66  |     await page.getByLabel('创作图标题', { exact: true }).fill('导演控制台来源绑定');
  67  |     await page.getByRole('button', { name: '明确读取导演、分镜与视觉制作节点目录', exact: true }).click();
  68  |     await page.getByLabel('确认将当前兼容草稿采用为图片图 v4，保持原资产绑定与人工审核', { exact: true }).check();
  69  |     await page.getByRole('button', { name: '明确采用图片图 v4', exact: true }).click();
  70  |     await page.getByLabel('节点类型', { exact: true }).selectOption('director_plan');
  71  |     await page.getByRole('button', { name: '明确读取已保存导演与分镜文档', exact: true }).click();
  72  |     await page.getByLabel('原创作文档', { exact: true }).selectOption(document.id);
  73  |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  74  |     const region = page.getByRole('region', { name: '图节点导演控制台', exact: true });
  75  |     await expect(region).toBeVisible();
  76  |     expect(calls.filter(row => row.path === `${base}/director/workspace/${document.id}`)).toEqual([]);
  77  |     await region.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  78  |     await expect(region.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  79  |     await expect(region.locator('.director-intent__list > li')).toHaveCount(7);
  80  |     await page.evaluate(() => document.fonts.ready);
  81  |     await page.screenshot({ path: info.outputPath('director-console-expanded.png'), fullPage: true });
  82  |     const creatingGraph = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  83  |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  84  |     const graph = await exact(await creatingGraph, 201);
  85  |     expect(graph.definition.nodes).toHaveLength(1);
  86  |     expect(graph.definition.nodes[0].parameters.document_snapshot).toEqual({ id: source.id, version: source.version, digest: source.digest });
  87  | 
  88  |     await page.reload();
  89  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  90  |     await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  91  |     await page.getByRole('button', { name: `选择节点 导演节点（已保存文档） · ${graph.definition.nodes[0].id}`, exact: true }).click();
  92  |     await page.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  93  |     await expect(page.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  94  | 
  95  |     await exact(await request.put(`${documentUrl}/${document.id}`, { headers, data: { ...content, expected_version: document.version,
  96  |       visual_target: { ...content.visual_target, style: '已修改但未重绑的视觉方向' } } }), 200);
  97  |     await page.getByRole('button', { name: '重新读取原文档', exact: true }).click();
  98  |     await expect(page.getByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/)).toBeVisible();
  99  |     await expect(page.getByLabel('导演意图', { exact: true })).toHaveCount(0);
  100 |     await expect(page.getByText('已修改但未重绑的视觉方向', { exact: true })).toHaveCount(0);
  101 |     await page.screenshot({ path: info.outputPath('director-console-stale-refusal.png'), fullPage: true });
  102 |     expect(errors).toEqual([]);
  103 |     expect(calls.filter(row => !['GET', 'HEAD', 'OPTIONS'].includes(row.method)
  104 |       && /\/(graph-runs|dispatch|generate|director-proposals|media\/tasks)(\/|$)/.test(row.path))).toEqual([]);
  105 |     const stored = await exact(await request.get(`${base}/graphs/${graph.id}`, { headers }), 200);
  106 |     expect(stored.version).toBe(graph.version);
  107 |     expect(stored.definition.nodes[0].parameters.document_snapshot).toEqual(graph.definition.nodes[0].parameters.document_snapshot);
  108 |     await info.attach('real-owner-pins-and-network', { body: JSON.stringify({ project: project.id, source, graph: stored,
  109 |       page_errors: errors, calls }, null, 2), contentType: 'application/json' });
  110 |   } finally {
  111 |     if (info.status !== info.expectedStatus && !page.isClosed()) {
  112 |       await page.screenshot({ path: info.outputPath('director-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
  113 |     }
  114 |     await info.attach('director-console-network-and-errors', { body: JSON.stringify({ errors, calls }, null, 2), contentType: 'application/json' });
  115 |     for (const id of owned) expect((await request.delete(`${workspace}/projects/${encodeURIComponent(id)}`, { headers })).status()).toBe(204);
```