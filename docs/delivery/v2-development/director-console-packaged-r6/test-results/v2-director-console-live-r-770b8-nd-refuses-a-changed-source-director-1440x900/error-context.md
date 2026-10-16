# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-director-console-live.spec.ts >> real File Director graph participant saves, reopens and refuses a changed source
- Location: tests\e2e\v2-director-console-live.spec.ts:3:1

# Error details

```
Error: expect(locator).toHaveValue(expected) failed

Locator: getByLabel('作者输入文本', { exact: true })
Expected: "真实浏览器中保留的作者文本 🎬"
Timeout: 15000ms
Error: element(s) not found

Call log:
  - Expect "toHaveValue" with timeout 15000ms
  - waiting for getByLabel('作者输入文本', { exact: true })

```

```yaml
- banner:
  - strong: AI Novel
  - text: Studio
  - tablist "创作模块":
    - tab "小说"
    - tab "图片" [selected]
    - tab "视频"
    - tab "资产"
    - tab "声音"
    - tab "主控"
    - tab "插件"
    - tab "工作流"
  - button "打开全局命令": 搜索作品、章节与素材 Ctrl K
  - text: local-author
- navigation "当前创作范围": 创作空间：我的创作空间 / 项目：导演控制台验收 director-1440x900 / 故事线：Default Storyline / 创作分支：main
- main:
  - complementary:
    - heading "独立创作" [level=2]
    - paragraph: 图片、视频和声音共享项目资产。连接其它模块由你决定。
    - button "返回项目列表"
    - group: 创作意图与推荐布局
    - group: 项目存储
  - button "创作开始"
  - button "任务中心"
  - button "素材工作区"
  - button "创作图" [pressed]
  - button "制作操作"
  - region "界面模式":
    - heading "界面模式" [level=3]
    - radiogroup "界面模式选择":
      - radio "新手模式"
      - radio "专业模式" [checked] [disabled]
    - paragraph: 新手模式与专业模式共用同一份项目、素材、任务与图谱数据；切换只改变界面呈现，不会转换、复制或删除任何内容。
  - region "本机图草稿恢复":
    - status: 文本图草稿已保留在本机 · 23:03:51。服务端版本、审核与运行仍需明确操作。
  - region "独立创作图编辑器":
    - heading "创作图 · 手工编排" [level=2]
    - paragraph: 空图和不相连的组件都可以保存。导演备注可选，可随时移除；连接类型由服务端定义。
    - paragraph: 可选本地文字模型节点需单独预览输入并明确确认一次调用。每次运行最多一个文字模型节点，输出必须人工审核；不自动调用、重试或转云端。
    - paragraph: 媒体图 v3 使用原任务服务逐项入队和执行。候选只能进入人工审核，审核后的当前素材才能用于下游。每图最多四个媒体制作节点；本机与完整流程验收仍待完成。
    - button "明确读取图片节点目录"
    - button "明确读取视频图节点目录"
    - button "明确读取导演、分镜与视觉制作节点目录"
    - button "新建空图"
    - button "刷新创作图目录"
    - text: 已保存创作图
    - combobox "已保存创作图":
      - option "未选择已保存图" [selected]
    - text: 创作图标题
    - textbox "创作图标题": 浏览器恢复的文本图
    - text: 尚未保存 · 未保存修改
    - button "保存创作图"
    - button "撤销图编辑" [disabled]
    - button "重做图编辑" [disabled]
    - button "重新读取创作图" [disabled]
    - status: 已恢复本机文本图草稿。尚未保存到服务端，也未创建或执行运行。
    - region "媒体图版本":
      - paragraph: 当前图格式：v1。旧图保持原行为，升级只在明确保存后生效，不自动执行。
      - checkbox "确认升级为媒体图 v3；已有资产引用将可以作为当前版本来源执行读取"
      - text: 确认升级为媒体图 v3；已有资产引用将可以作为当前版本来源执行读取
      - button "明确升级当前草稿为媒体图 v3" [disabled]
    - region "添加与连接节点":
      - text: 节点类型
      - combobox "节点类型":
        - option "文本输入" [selected]
        - option "文本引用"
        - option "本地草稿整理"
        - option "手工处理"
        - option "导演备注"
        - option "人工审核"
        - option "资产引用"
        - option "本地文字模型（需明确调用）"
        - option "媒体制作（需分别确认）"
        - option "媒体审核入库"
        - option "时间线剪辑与导出（需分别确认）"
      - button "添加节点"
      - text: 起始输出端口
      - combobox "起始输出端口":
        - option "选择输出端口" [selected]
        - option "文本输入 · node_543d06764ef044fb972fa236b586049e · text (TEXT)"
      - text: 目标输入端口
      - combobox "目标输入端口":
        - option "选择输入端口" [selected]
      - button "连接所选端口" [disabled]
    - region "画布操作栏":
      - region "节点面板":
        - heading "节点面板" [level=3]
        - text: 搜索节点
        - searchbox "搜索节点"
        - text: 节点分类
        - combobox "节点分类":
          - option "全部分类" [selected]
          - option "文本与草稿"
          - option "资产引用"
          - option "媒体与时间线"
          - option "图片图 v4 节点"
          - option "导演与分镜"
          - option "视频图 v5 节点"
        - paragraph: 只读现存目录：共 11 个节点定义，当前命中 11 个。分类与检索都只在本机内存中进行，不会因为检索而调用模型。
        - list:
          - listitem:
            - button "文本输入 text_input 可执行 已选 输出 text TEXT 命中 ALL · 定义不调用模型" [pressed]:
              - strong: 文本输入
              - code: text_input
              - text: 可执行 已选 输出 text TEXT 命中 ALL · 定义不调用模型
          - listitem:
            - button "文本引用 text_reference 可执行 输入 text TEXT · 必填 输出 text TEXT 命中 ALL · 定义不调用模型":
              - strong: 文本引用
              - code: text_reference
              - text: 可执行 输入 text TEXT · 必填 输出 text TEXT 命中 ALL · 定义不调用模型
          - listitem:
            - button "本地草稿整理 draft_prepare 可执行 输入 text TEXT · 必填 输入 direction DIRECTOR_NOTES 输出 draft DRAFT 命中 ALL · 定义不调用模型":
              - strong: 本地草稿整理
              - code: draft_prepare
              - text: 可执行 输入 text TEXT · 必填 输入 direction DIRECTOR_NOTES 输出 draft DRAFT 命中 ALL · 定义不调用模型
          - listitem:
            - button "手工处理 manual_transform 可执行 输入 text TEXT · 必填 输入 direction DIRECTOR_NOTES 输出 draft DRAFT 命中 ALL · 定义不调用模型":
              - strong: 手工处理
              - code: manual_transform
              - text: 可执行 输入 text TEXT · 必填 输入 direction DIRECTOR_NOTES 输出 draft DRAFT 命中 ALL · 定义不调用模型
          - listitem:
            - button "导演备注 director_note 可执行 输出 direction DIRECTOR_NOTES 命中 ALL · 定义不调用模型":
              - strong: 导演备注
              - code: director_note
              - text: 可执行 输出 direction DIRECTOR_NOTES 命中 ALL · 定义不调用模型
          - listitem:
            - button "人工审核 human_review 可执行 输入 draft DRAFT · 必填 命中 ALL · 定义不调用模型":
              - strong: 人工审核
              - code: human_review
              - text: 可执行 输入 draft DRAFT · 必填 命中 ALL · 定义不调用模型
          - listitem:
            - button "资产引用 asset_reference 可执行 输出 asset ASSET_REF 命中 ALL · 定义不调用模型":
              - strong: 资产引用
              - code: asset_reference
              - text: 可执行 输出 asset ASSET_REF 命中 ALL · 定义不调用模型
          - listitem:
            - button "本地文字模型（需明确调用） text_generate 可执行 输入 text TEXT · 必填 输入 direction DIRECTOR_NOTES 输出 draft DRAFT 命中 ALL · 定义不调用模型":
              - strong: 本地文字模型（需明确调用）
              - code: text_generate
              - text: 可执行 输入 text TEXT · 必填 输入 direction DIRECTOR_NOTES 输出 draft DRAFT 命中 ALL · 定义不调用模型
          - listitem:
            - button "媒体制作（需分别确认） media_generate 可执行 输入 text TEXT 输入 draft DRAFT 输入 source ASSET_REF 输出 candidate MEDIA_CANDIDATE 命中 ALL · 定义不调用模型":
              - strong: 媒体制作（需分别确认）
              - code: media_generate
              - text: 可执行 输入 text TEXT 输入 draft DRAFT 输入 source ASSET_REF 输出 candidate MEDIA_CANDIDATE 命中 ALL · 定义不调用模型
          - listitem:
            - button "媒体审核入库 media_review 可执行 输入 candidate MEDIA_CANDIDATE · 必填 输出 asset ASSET_REF 命中 ALL · 定义不调用模型":
              - strong: 媒体审核入库
              - code: media_review
              - text: 可执行 输入 candidate MEDIA_CANDIDATE · 必填 输出 asset ASSET_REF 命中 ALL · 定义不调用模型
          - listitem:
            - button "时间线剪辑与导出（需分别确认） timeline_export 可执行 输入 source_1 ASSET_REF 输入 source_2 ASSET_REF 输入 source_3 ASSET_REF 输入 source_4 ASSET_REF 输入 source_5 ASSET_REF 输入 source_6 ASSET_REF 输入 source_7 ASSET_REF 输入 source_8 ASSET_REF 输出 candidate MEDIA_CANDIDATE 命中 ALL · 定义不调用模型":
              - strong: 时间线剪辑与导出（需分别确认）
              - code: timeline_export
              - text: 可执行 输入 source_1 ASSET_REF 输入 source_2 ASSET_REF 输入 source_3 ASSET_REF 输入 source_4 ASSET_REF 输入 source_5 ASSET_REF 输入 source_6 ASSET_REF 输入 source_7 ASSET_REF 输入 source_8 ASSET_REF 输出 candidate MEDIA_CANDIDATE 命中 ALL · 定义不调用模型
        - button "添加所选节点（由原控制器执行）"
        - paragraph: 节点预算：已用 1 / 上限 16（取自 CATALOG_LIMITS）。达到任一上限时，本工具会说明原因并建议拆分工作流；它不会抬高任何节点或任务上限。
        - paragraph: 添加与保存仍由原创作图控制器完成：本面板只选择节点类型并调用它，不直接改图、不发请求。
      - region "选择与历史":
        - heading "选择与历史" [level=3]
        - list:
          - listitem: 1 已选节点
          - listitem: 框选命中：未提供（框选由原画布负责，本栏不编造数字）
          - listitem: 受保护节点 0 个
          - listitem: 本地折叠 0 · 分组 0 · 标注 0
        - button "定位 node_543d06764ef044fb972fa236b586049e"
        - button "只选择全部受保护节点（0）" [disabled]
        - button "清空选择"
        - button "折叠 node_543d06764ef044fb972fa236b586049e（仅本地）"
        - button "撤销本地草稿编辑（可撤销 0 步）" [disabled]
        - button "重做本地草稿编辑（可重做 0 步）" [disabled]
        - paragraph:
          - text: 撤销/重做
          - strong: 只回退本地草稿操作
          - text: ；已经发生的模型调用与费用、远端任务与已提交的审核都不会被撤销或回滚。撤销也不能移除已保存的资产绑定（原控制器会拒绝并说明）。
        - paragraph: "折叠、分组与标注只是本页会话内的呈现状态：它们不会写入已保存的创作图，也不会随图另存。要持久化它们，需要由原图契约所有者先做一次带类型、向后兼容的扩展（见 `canvasOpsTypes.ts` 顶部说明）。"
      - region "连接建议":
        - heading "连接建议" [level=3]
        - text: 连接建议 · 起始输出端口
        - combobox "连接建议 · 起始输出端口":
          - option "选择输出端口" [selected]
          - option "文本输入 · node_543d06764ef044fb972fa236b586049e · text (TEXT)"
        - text: 连接建议 · 目标输入端口
        - combobox "连接建议 · 目标输入端口":
          - option "选择输入端口" [selected]
        - paragraph: 待连接来源：尚未选择有效的起始输出端口（请选择现存节点上由目录声明的输出端口）
        - heading "兼容目标（由目录端口声明与 connectionIssue 判定）" [level=4]:
          - text: 兼容目标（由目录端口声明与
          - code: connectionIssue
          - text: 判定）
        - status: 选择起始输出端口后，这里会列出端口类型一致的候选目标。
        - button "连接所选端口（由原控制器执行）" [disabled]
        - status:
          - paragraph:
            - strong: 本地连接检查通过
            - text: ·
            - code: CONNECTION_LEGAL
            - text: （LEGAL）
          - paragraph: 本地端口检查通过（类型一致、无环、输入端口未被占用）。连接合法性最终仍由服务端校验决定。
        - paragraph:
          - text: 本面板不提供绕过入口：类型不匹配、未审核候选、过期来源绑定与缺失必填输入都会在这里以原所有者的结果说明，连接仍由原控制器的
          - code: connect()
          - text: 与
          - code: connectionIssue
          - text: 判定。服务端校验、版本与摘要校验永远不会被跳过。
      - region "变更影响":
        - heading "变更影响" [level=3]
        - paragraph:
          - text: 当前草稿差异分类： 可能影响生成
          - code: GENERATION_AFFECTING
        - list:
          - listitem: 与已保存版本比较：尚无已保存版本
          - listitem: 未保存修改：有
          - listitem: 节点 1 个 · 连接 0 条
        - status:
          - text: 尚无已保存版本可比：未保存内容一律按
          - code: GENERATION_AFFECTING
          - text: 保守处理，直到你明确保存并由原服务端返回版本与摘要。
        - list:
          - listitem: 缺少可比较的已保存定义，或定义结构不符合原图契约，本地无法证明差异只影响呈现。
        - paragraph:
          - text: 原因码：
          - code: NOT_COMPARABLE
        - paragraph:
          - text: 移动卡片（只改变节点位置）
          - strong: 不会重新运行模型
          - text: ：坐标不是执行输入，本工具也不会因为布局、折叠、分组或标注而调用模型、入队任务或提交审核。 只有上面的原因码涉及参数、来源绑定、节点或连接变化时，才需要在原运行流程中重新预览并逐项确认。
        - paragraph:
          - text: 本判断只基于本地草稿，
          - strong: 永远不会绕过原图的版本与摘要校验
          - text: ：保存仍按
          - code: expected_version
          - text: 进行，执行仍需已审核的预览摘要，撤销/重做也不会回滚已发生的调用与费用。
      - region "自动布局预览":
        - heading "自动布局预览（确定性，只改坐标）" [level=3]
        - paragraph:
          - text: 若应用自动布局：会分为 1 列，移动 1 个节点的坐标；差异分类为
          - code: PRESENTATION
          - text: （原因：POSITION_CHANGED）。它不会改动参数、来源绑定、启用状态、连接或图格式。
        - paragraph:
          - text: 自动布局是纯函数结果，必须由原控制器的
          - code: change()
          - text: 提交才能进入本地撤销/重做栈；本批冻结的 props 未包含该回调，因此这里只做预览，绝不直接修改草稿。
    - region "节点图画布":
      - group "画布操作方式":
        - button "选择节点" [pressed]:
          - img
        - button "平移画布":
          - img
      - button "缩小节点图":
        - img
      - status "节点图缩放": 100%
      - button "放大节点图":
        - img
      - status: 已选 1 个节点
      - button "删除所选图节点":
        - img
      - group "节点图交互区域":
        - article:
          - button "选择节点 文本输入 · node_543d06764ef044fb972fa236b586049e" [pressed]:
            - strong: 文本输入
            - text: node_543d06764ef044fb972fa236b586049e · v1 启用
          - button "文本输入 node_543d06764ef044fb972fa236b586049e 输出端口 text · TEXT": 输出 · text TEXT
      - paragraph: 拖动节点移动；空白处框选；Shift 多选；Alt 拖动或平移工具移动视图；Ctrl / ⌘ + 滚轮缩放。选中节点后可用方向键移动、Delete 删除，Esc 取消操作。
      - list "节点图连接"
    - region "图连接列表":
      - heading "已保存到草稿的连接" [level=3]
      - paragraph: 暂无连接；不相连节点可以独立保存。
      - list
    - region "创作图运行与审核":
      - heading "节点运行" [level=3]
      - paragraph: 先核对保存图与节点范围。前置节点使用原工作流；模型和媒体节点分别预览、确认与执行。媒体 schema 3 核对原资产版本与内容，审核后才供下游采用。
      - paragraph: 先保存创作图，再核对选中节点的运行范围。
      - status: 创作图有未保存修改，请先保存后运行。
      - button "核对运行范围" [disabled]
      - button "读取运行记录" [disabled]
      - region "可选本地文字模型执行":
        - heading "可选本地文字模型执行" [level=3]
        - paragraph: 先读取能力并选择本地路由，再核对完整输入并明确调用一次。不会自动安装、启动模型、调用、重试或转云端。结果仍需人工审核，不写入正文。
        - paragraph: 云端 API：预留，当前不可执行。实际推理质量验收：未运行。
        - button "读取本地模型能力" [disabled]
        - region "提供方与任务匹配说明":
          - heading "提供方与任务匹配说明" [level=4]
          - paragraph: 只读取契约与筛选说明，不会选择执行路由、调用模型或自动回退。提供方声明的能力与已验证的适配器契约分别显示；真实推理验收尚未运行。
          - button "读取提供方契约" [disabled]
        - paragraph: 先保存图并创建运行；保存和创建都不会调用模型。
  - button "收起侧栏" [expanded]
  - complementary:
    - separator "调整检查面板宽度"
    - text: 创作辅助
    - button "收起侧栏"
    - region "创作图节点检查器":
      - heading "文本输入" [level=2]
      - paragraph: node_543d06764ef044fb972fa236b586049e · 定义 v1
      - checkbox "启用当前节点" [checked]
      - text: 启用当前节点 作者输入文本
      - textbox "作者输入文本": 真实浏览器中保留的作者文本 🎬
      - text: 节点 X
      - spinbutton "节点 X": "24"
      - text: 节点 Y
      - spinbutton "节点 Y": "24"
      - button "移除当前节点"
      - paragraph: 移除节点只修改本图，不删除任何原资产、章节或运行记录。
- contentinfo:
  - text: 未保存或待核对 · 创作图 · 模型调用记录见运行回执
  - button "问助手"
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
  15  |     expect(response.status(), await response.text()).toBe(status); return response.json();
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
> 59  |     await expect(page.getByLabel('作者输入文本', { exact: true })).toHaveValue('真实浏览器中保留的作者文本 🎬');
      |                                                              ^ Error: expect(locator).toHaveValue(expected) failed
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
  116 |   }
  117 | });
  118 | 
```