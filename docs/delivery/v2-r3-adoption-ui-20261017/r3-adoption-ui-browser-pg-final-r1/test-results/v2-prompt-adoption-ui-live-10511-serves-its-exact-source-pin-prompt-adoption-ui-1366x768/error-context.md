# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-prompt-adoption-ui-live.spec.ts >> isolated original button commits bound Prompt and reload preserves its exact source pin
- Location: tests\e2e\v2-prompt-adoption-ui-live.spec.ts:19:1

# Error details

```
TimeoutError: locator.click: Timeout 25000ms exceeded.
Call log:
  - waiting for getByRole('region', { name: '创作文档', exact: true }).getByRole('button', { name: /真实分镜 prompt-adoption-ui-1366x768/ })

```

# Page snapshot

```yaml
- generic [ref=f1e3]:
  - banner [ref=f1e4]:
    - generic "AI Novel Studio" [ref=f1e5]:
      - generic [ref=f1e9]:
        - strong [ref=f1e10]: AI Novel
        - generic [ref=f1e11]: Studio
    - tablist "创作模块" [ref=f1e12]:
      - tab "小说" [ref=f1e13] [cursor=pointer]
      - tab "图片" [selected] [ref=f1e17] [cursor=pointer]
      - tab "视频" [ref=f1e23] [cursor=pointer]
      - tab "资产" [ref=f1e28] [cursor=pointer]
      - tab "声音" [ref=f1e32] [cursor=pointer]
      - tab "主控" [ref=f1e38] [cursor=pointer]
      - tab "插件" [ref=f1e52] [cursor=pointer]
      - tab "工作流" [ref=f1e56] [cursor=pointer]
    - button "打开全局命令" [ref=f1e62] [cursor=pointer]:
      - generic [ref=f1e66]: 搜索作品、章节与素材
      - generic [ref=f1e67]: Ctrl K
    - generic [ref=f1e68]:
      - generic [ref=f1e69]: L
      - generic [ref=f1e70]: local-author
  - navigation "当前创作范围" [ref=f1e71]:
    - generic [ref=f1e72]: 创作空间：我的创作空间
    - generic [ref=f1e73]: /
    - generic [ref=f1e74]: 项目：采用 UI 验收 prompt-adoption-ui-1366x768
    - generic [ref=f1e75]: /
    - generic [ref=f1e76]: 故事线：Default Storyline
    - generic [ref=f1e77]: /
    - generic [ref=f1e78]: 创作分支：main
  - main [ref=f1e79]:
    - complementary [ref=f1e80]:
      - generic [ref=f1e81]:
        - heading "独立创作" [level=2] [ref=f1e82]
        - paragraph [ref=f1e83]: 图片、视频和声音共享项目资产。连接其它模块由你决定。
        - button "返回项目列表" [ref=f1e84] [cursor=pointer]
        - group [ref=f1e85]:
          - generic "创作意图与推荐布局" [ref=f1e86] [cursor=pointer]
          - option "空白" [selected]
          - option "文本"
          - option "图片"
          - option "视频"
          - option "声音"
          - option "剪辑"
          - option "混合"
        - group [ref=f1e87]:
          - generic "项目存储" [ref=f1e88] [cursor=pointer]
    - generic [ref=f1e90]:
      - generic "独立工作区内容" [ref=f1e91]:
        - button "创作开始" [ref=f1e92] [cursor=pointer]
        - button "任务中心" [ref=f1e93] [cursor=pointer]
        - button "素材工作区" [pressed] [ref=f1e94] [cursor=pointer]
        - button "创作图" [ref=f1e95] [cursor=pointer]
        - button "制作操作" [ref=f1e96] [cursor=pointer]
        - region "界面模式" [ref=f1e97]:
          - heading "界面模式" [level=3] [ref=f1e98]
          - radiogroup "界面模式选择" [ref=f1e99]:
            - radio "新手模式" [ref=f1e100] [cursor=pointer]
            - radio "专业模式" [checked] [disabled] [ref=f1e101]
          - paragraph [ref=f1e102]: 新手模式与专业模式共用同一份项目、素材、任务与图谱数据；切换只改变界面呈现，不会转换、复制或删除任何内容。
      - generic [ref=f1e103]:
        - heading "Prompt 工作台" [level=2] [ref=f1e105]
        - paragraph [ref=f1e106]: 在这里创建和修订手写 Prompt。保存只会新增一个不可变修订，不会覆盖旧版本； 这里不会调用任何模型，也不会因为输入而自动创建内容。
        - generic [ref=f1e107]:
          - region "Prompt 列表" [ref=f1e108]:
            - generic [ref=f1e109]:
              - button "新建 Prompt" [ref=f1e110] [cursor=pointer]
              - button "重新读取" [ref=f1e111] [cursor=pointer]
            - generic [ref=f1e112]:
              - generic [ref=f1e113]: 搜索
              - searchbox "搜索" [ref=f1e114]
              - generic [ref=f1e115]: 用途
              - combobox "用途" [ref=f1e116]:
                - option "全部" [selected]
                - option "IMAGE"
                - option "VIDEO"
                - option "AUDIO"
                - option "TEXT"
              - generic [ref=f1e117]: 状态
              - combobox "状态" [ref=f1e118]:
                - option "全部" [selected]
                - option "草稿"
                - option "已审核"
            - list [ref=f1e119]:
              - listitem [ref=f1e120]:
                - button "IMAGE · 638b228a · 修订 1 已审核" [ref=f1e121] [cursor=pointer]:
                  - generic [ref=f1e122]: IMAGE · 638b228a · 修订 1
                  - generic [ref=f1e123]: 已审核
          - region "Prompt 编辑器" [ref=f1e126]:
            - status [ref=f1e127]: 尚无未保存修改
            - text: 正文
            - textbox "正文" [ref=f1e128]
            - paragraph [ref=f1e129]: 按 UTF-8 字节计最长 64 KiB。不会自动去除空格、换行或 emoji。
            - text: Negative Prompt
            - textbox "Negative Prompt" [ref=f1e130]
            - generic [ref=f1e131]:
              - generic [ref=f1e132]:
                - generic [ref=f1e133]: 用途
                - combobox "用途" [ref=f1e134]:
                  - option "IMAGE" [selected]
                  - option "VIDEO"
                  - option "AUDIO"
                  - option "TEXT"
              - generic [ref=f1e135]:
                - generic [ref=f1e136]: 模型偏好
                - textbox "模型偏好" [ref=f1e137]
              - generic [ref=f1e138]:
                - generic [ref=f1e139]: Seed
                - textbox "Seed" [ref=f1e140]
            - text: 参数（JSON，不会执行）
            - textbox "参数（JSON，不会执行）" [ref=f1e141]
            - group "引用绑定（逗号或空格分隔 ID）" [ref=f1e142]:
              - generic [ref=f1e144]: 角色 ID
              - textbox "角色 ID" [ref=f1e145]
              - generic [ref=f1e146]: 场景 ID
              - textbox "场景 ID" [ref=f1e147]
              - generic [ref=f1e148]: 镜头 ID
              - textbox "镜头 ID" [ref=f1e149]
              - generic [ref=f1e150]: 参考素材 ID
              - textbox "参考素材 ID" [ref=f1e151]
            - text: 修改备注
            - textbox "修改备注" [ref=f1e152]
            - text: 修改原因
            - textbox "修改原因" [ref=f1e153]
            - generic [ref=f1e154]:
              - button "保存为新 Prompt" [ref=f1e155] [cursor=pointer]
              - button "放弃本地修改" [ref=f1e156] [cursor=pointer]
            - generic [ref=f1e157]:
              - term [ref=f1e158]: 家族
              - definition [ref=f1e159]: （新建）
              - term [ref=f1e160]: 基准修订
              - definition [ref=f1e161]: （新建）
              - term [ref=f1e162]: 基准资产
              - definition [ref=f1e163]: （新建）
              - term [ref=f1e164]: 请求标识
              - definition [ref=f1e165]: （未提交）
      - generic [ref=f1e166]:
        - heading "独立素材工作区" [level=2] [ref=f1e168]
        - paragraph [ref=f1e169]: 无需小说、章节或模型，导入素材即可保存和导出。
        - paragraph [ref=f1e170]: 上传会保存文件，并记录“外部导入”；许可默认未指定，可在来源声明中补充。下载原始文件保留原格式，不进行重新编码。
        - generic [ref=f1e171]: 手工导入可用 · 不需要模型
      - generic [ref=f1e172]:
        - generic [ref=f1e173]:
          - heading "资产库" [level=2] [ref=f1e174]
          - button "上传资产" [ref=f1e175] [cursor=pointer]
        - generic [ref=f1e179]:
          - generic [ref=f1e180]:
            - text: 查找资产
            - searchbox "查找资产" [ref=f1e181]
          - generic [ref=f1e182]:
            - text: 类型筛选
            - combobox "类型筛选" [ref=f1e183]:
              - option "全部" [selected]
              - option "图片"
              - option "视频"
              - option "音频"
          - generic [ref=f1e184]: 1 项资产
          - button "回收站" [ref=f1e185] [cursor=pointer]
        - paragraph [ref=f1e186]: 删除后原素材进入回收站，可恢复。已绑定的参考需重新审核后才能参与检索。
        - article "资产 prompt-638b228a-r1.txt" [ref=f1e188]:
          - button "检查资产 prompt-638b228a-r1.txt" [ref=f1e189] [cursor=pointer]:
            - generic [ref=f1e190]:
              - strong [ref=f1e191]: prompt-638b228a-r1.txt
              - generic [ref=f1e192]: 1 KB
            - paragraph [ref=f1e193]: text/plain · 9623b32cec2a
            - paragraph [ref=f1e194]: 已保存 · v3 · 来源待声明
          - generic [ref=f1e195]:
            - button "下载" [ref=f1e196] [cursor=pointer]
            - button "删除资产" [ref=f1e200] [cursor=pointer]
      - generic [ref=f1e205]:
        - generic [ref=f1e206]:
          - heading "素材浏览器" [level=2] [ref=f1e207]
          - generic [ref=f1e208]:
            - button "网格" [pressed] [ref=f1e209] [cursor=pointer]
            - button "列表" [ref=f1e210] [cursor=pointer]
            - button "重新读取素材" [ref=f1e211] [cursor=pointer]
        - form "素材筛选" [ref=f1e212]:
          - generic [ref=f1e213]:
            - generic [ref=f1e214]: 搜索素材
            - searchbox "搜索素材" [ref=f1e215]
          - generic [ref=f1e216]:
            - generic [ref=f1e217]: 媒体种类
            - combobox "媒体种类" [ref=f1e218]:
              - option "全部（0）" [selected]
              - option "图片（0）"
              - option "视频（0）"
              - option "音频（0）"
              - option "未核实（0）"
          - generic [ref=f1e219]:
            - generic [ref=f1e220]: 用途标签
            - combobox "用途标签" [ref=f1e221]:
              - option "全部" [selected]
              - option "角色（0）"
              - option "环境（0）"
              - option "道具（0）"
              - option "未打标签（0）"
          - generic [ref=f1e222]:
            - generic [ref=f1e223]: 审核标记
            - combobox "审核标记" [ref=f1e224]:
              - option "全部" [selected]
              - option "无审核标记（0）"
              - option "待审核草稿（0）"
              - option "已批准（0）"
              - option "已驳回（0）"
          - generic [ref=f1e225]:
            - generic [ref=f1e226]: 创建时间
            - combobox "创建时间" [ref=f1e227]:
              - option "全部" [selected]
              - option "未记录时间（0）"
              - option "今天（0）"
              - option "近 7 天（0）"
              - option "近 30 天（0）"
              - option "更早（0）"
          - generic [ref=f1e228]:
            - generic [ref=f1e229]: 引用情况
            - combobox "引用情况" [ref=f1e230]:
              - option "全部" [selected]
              - option "已被引用（0）"
              - option "未被引用（0）"
              - option "引用情况未核实（0）"
          - button "清除筛选" [disabled] [ref=f1e232]
          - paragraph [ref=f1e233]: 搜索只匹配已读取的元数据（文件名、类型、标签、审核标记、引用摘要）， 不会扫描磁盘、不会打开未授权内容。
          - paragraph [ref=f1e234]: 标记为 角色 / 环境 / 道具 只是作者用途标签， 不改变素材的媒体种类（图片 / 视频 / 音频）。
        - alert [ref=f1e235]:
          - text: 素材目录数据不可用，请重新读取。
          - generic [ref=f1e236]: · 代码 ASSET_BROWSER_LIST_INVALID
        - generic [ref=f1e237]:
          - generic [ref=f1e238]:
            - generic [ref=f1e239]:
              - status [ref=f1e240]: 显示 0 / 0 条。只显示已读取的前若干条；继续加载会再读取下一页，绝不一次拉取全部高清素材。
              - generic [ref=f1e241]:
                - generic [ref=f1e242]: 每页条数
                - combobox "每页条数" [ref=f1e243]:
                  - option "8 条"
                  - option "24 条" [selected]
                  - option "48 条"
                  - option "96 条"
            - generic [ref=f1e244]:
              - list "素材列表"
              - status [ref=f1e245]: 当前筛选没有匹配的素材；已读取的素材仍然保留。
          - region "素材详情" [ref=f1e247]:
            - status [ref=f1e248]:
              - strong [ref=f1e249]: 未选择素材
              - paragraph [ref=f1e250]: 从素材网格或列表选择一项，才会按需读取它的版本、来源与引用。
        - paragraph [ref=f1e251]: 缩略图按需读取（缩略图只在需要时按原下载接口读取，不预取整库。）。 引用关系当前不可读，引用情况显示为未核实，不会当作"未被引用"。
        - paragraph [ref=f1e252]: 新的来源版本只显示差异；只有你明确选择才会更新绑定，绝不自动更新所有任务 / 镜头 / 片段。
    - button "收起侧栏" [expanded] [ref=f1e253] [cursor=pointer]
    - complementary [ref=f1e257]:
      - separator "调整检查面板宽度" [ref=f1e258]
      - generic [ref=f1e259]:
        - generic [ref=f1e260]: 创作辅助
        - button "收起侧栏" [ref=f1e261] [cursor=pointer]
      - region "资产检查面板" [ref=f1e265]:
        - generic [ref=f1e266]: Inspector
        - status [ref=f1e267]:
          - strong [ref=f1e268]: 未选择资产
          - paragraph [ref=f1e269]: 从资产网格选择一个项目以查看真实预览和元数据。
  - contentinfo [ref=f1e270]:
    - text: 已保存 · 独立素材 · 模型调用记录见运行回执
    - button "问助手" [ref=f1e272] [cursor=pointer]
```

# Test source

```ts
  1   | import { createHash } from 'node:crypto';
  2   | import { expect, test, type APIResponse } from '@playwright/test';
  3   | import { openPromptWorkspace, promptLibrary } from '../../e2e/promptAcceptanceEntry';
  4   | 
  5   | const FIRST = '  采用成功闭环 第一版\n逐字中文与 emoji 🙂  \n';
  6   | const NEWER = '  来源家族第二版；不应自动替换已采用修订 🎬\n';
  7   | const CONSENT = '我已核对来源正文、修订与当前镜头版本，确认替换画面提示词。';
  8   | const canonical = (value: unknown): string => {
  9   |   if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  10  |   if (value !== null && typeof value === 'object') {
  11  |     const row = value as Record<string, unknown>;
  12  |     return `{${Object.keys(row).sort().map(key => `${JSON.stringify(key)}:${canonical(row[key])}`).join(',')}}`;
  13  |   }
  14  |   const rendered = JSON.stringify(value);
  15  |   if (rendered === undefined) throw new Error('Canonical owner data contains undefined.');
  16  |   return rendered;
  17  | };
  18  | 
  19  | test('isolated original button commits bound Prompt and reload preserves its exact source pin', async ({ page, request }, info) => {
  20  |   const token = process.env.STUDIO_PROMPT_ADOPTION_UI_BROWSER_TOKEN;
  21  |   if (!token) throw new Error('The isolated launcher must obtain an original packaged bootstrap session.');
  22  |   const errors: string[] = [], calls: { method: string; path: string; status: number }[] = [];
  23  |   page.on('pageerror', error => errors.push(error.message));
  24  |   page.on('response', response => {
  25  |     const path = new URL(response.url()).pathname;
  26  |     if (path.startsWith('/api/')) calls.push({ method: response.request().method(), path, status: response.status() });
  27  |   });
  28  |   const exact = async (response: APIResponse, status: number) => {
  29  |     expect(response.status(), await response.text()).toBe(status);
  30  |     return response.json();
  31  |   };
  32  |   const admin = '/api/collaboration/admin/workspaces/workspace-a';
  33  |   const projectGlobalHeaders = { 'X-Session-Token': token };
  34  |   let headers: Record<string, string> = projectGlobalHeaders;
  35  |   let projectId = '';
  36  |   const title = `采用 UI 验收 ${info.project.name}`;
  37  |   const boardTitle = `真实分镜 ${info.project.name}`;
  38  |   try {
  39  |     const project = await exact(await request.post(`${admin}/projects`, { headers,
  40  |       data: { title, genre: '' } }), 201);
  41  |     projectId = project.id;
  42  |     const navigation = await exact(await request.get(`${admin}/navigation`, { headers }), 200);
  43  |     const path = navigation.eligible_paths.find((row: { project_id: string }) => row.project_id === projectId);
  44  |     expect(path).toBeTruthy(); headers = { ...headers, 'X-Branch-ID': path.branch_id };
  45  |     const studio = `/api/projects/${projectId}/studio`;
  46  |     await exact(await request.post(`${studio}/activate`, { headers }), 200);
  47  |     // These original legacy records are explicitly project-global. Their real
  48  |     // route refuses a branch header rather than pretending to be a branch source.
  49  |     const character = await exact(await request.put(`/api/novels/${projectId}/characters/ui-bound-character`,
  50  |       { headers: projectGlobalHeaders, data: { name: '采用时真实角色目标' } }), 200);
  51  |     const characters = await exact(await request.get(`/api/novels/${projectId}/characters`, { headers: projectGlobalHeaders }), 200);
  52  |     const originalCharacter = characters.find((row: { id: string }) => row.id === character.id);
  53  |     expect(originalCharacter).toBeTruthy();
  54  |     const characterDigest = createHash('sha256').update(canonical(originalCharacter)).digest('hex');
  55  |     const creative = `/api/novels/${projectId}/experimental/creative/documents`;
  56  |     const script = await exact(await request.post(creative, { headers, data: { mode: 'SCREENPLAY',
  57  |       title: `真实来源剧本 ${info.project.name}`, source_independent: true,
  58  |       scenes: [{ id: 'real-ui-scene', sequence: 1, heading: 'INT. ROOM - DAY', action: 'A visitor arrives.' }] } }), 201);
  59  |     const board = await exact(await request.post(`${creative}/${script.id}/derive`, { headers,
  60  |       data: { expected_version: script.version, mode: 'STORYBOARD', title: boardTitle, shot_policy: 'SCENE' } }), 201);
  61  |     expect(board.shots).toHaveLength(1);
  62  |     const shotId = board.shots[0].id;
  63  |     const ownerPath = `${creative}/${board.id}`;
  64  |     const adoptionPath = `${studio}/documents/${board.id}/shots/${shotId}/prompt-adoption`;
  65  |     const projectionPath = `${studio}/documents/${board.id}/prompt-adoption`;
  66  | 
  67  |     // Reconnect, project choice and module changes are all existing product UI.
  68  |     // A full reload can return to the entry screen or restore the same project.
  69  |     const enterProject = async () => {
  70  |       await page.goto('/');
  71  |       const currentScope = page.getByRole('navigation', { name: '当前创作范围', exact: true }).filter({ hasText: title });
  72  |       await expect.poll(async () =>
  73  |         await page.getByText('连接已有创作空间', { exact: true }).isVisible()
  74  |         || await page.getByLabel('访问凭证', { exact: true }).isVisible()
  75  |         || await page.getByRole('button', { name: '我的创作空间', exact: true }).isVisible()
  76  |         || await currentScope.isVisible(), { timeout: 30_000 }).toBe(true);
  77  |       if (await page.getByText('连接已有创作空间', { exact: true }).isVisible()) {
  78  |         await page.getByText('连接已有创作空间', { exact: true }).click();
  79  |         await expect(page.getByLabel('访问凭证', { exact: true })).toBeVisible();
  80  |       }
  81  |       if (await page.getByLabel('访问凭证', { exact: true }).isVisible()) {
  82  |         await page.getByLabel('访问凭证', { exact: true }).fill(token);
  83  |         await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  84  |         await expect(page.getByRole('button', { name: '我的创作空间', exact: true })).toBeVisible();
  85  |       }
  86  |       const workspace = page.getByRole('button', { name: '我的创作空间', exact: true });
  87  |       const projectChoice = page.getByRole('button', { name: new RegExp(title) });
  88  |       if (await workspace.isVisible()) {
  89  |         await workspace.click();
  90  |         await expect(projectChoice).toBeVisible();
  91  |       }
  92  |       if (await projectChoice.isVisible()) await projectChoice.click();
  93  |       await expect(currentScope).toBeVisible();
  94  |     };
  95  |     const openBoard = async () => {
  96  |       await page.getByRole('tab', { name: '小说', exact: true }).click();
  97  |       await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  98  |       await page.getByRole('tab', { name: /^分镜/ }).click();
  99  |       await page.getByRole('region', { name: '创作文档', exact: true })
> 100 |         .getByRole('button', { name: new RegExp(boardTitle) }).click();
      |                                                                ^ TimeoutError: locator.click: Timeout 25000ms exceeded.
  101 |       await page.getByRole('button', { name: '按需打开镜头工作区', exact: true }).click();
  102 |       const shots = page.getByRole('region', { name: '分镜工作区', exact: true });
  103 |       await shots.getByRole('button', { name: '读取已保存分镜', exact: true }).click();
  104 |       await shots.getByRole('button', { name: `镜头 1（身份 ${shotId}）`, exact: true }).click();
  105 |       return shots;
  106 |     };
  107 |     const pin = async () => {
  108 |       const show = page.getByRole('button', { name: '查看 Prompt 采用来源', exact: true });
  109 |       if (await show.isVisible()) await show.click();
  110 |       const value = page.locator('.prompt-adoption-record');
  111 |       await expect(value).toBeVisible();
  112 |       return value;
  113 |     };
  114 | 
  115 |     await enterProject();
  116 |     await openPromptWorkspace(page);
  117 |     await page.getByRole('button', { name: '新建 Prompt', exact: true }).click();
  118 |     await page.getByLabel('正文', { exact: true }).fill(FIRST);
  119 |     await page.getByLabel('角色 ID', { exact: true }).fill(character.id);
  120 |     const creating = page.waitForResponse(response => new URL(response.url()).pathname === `${studio}/prompts`
  121 |       && response.request().method() === 'POST');
  122 |     await page.getByRole('button', { name: '保存为新 Prompt', exact: true }).click();
  123 |     const creation = await creating;
  124 |     expect(creation.status(), await creation.text()).toBe(201);
  125 |     expect(creation.request().postDataJSON().character_ids).toEqual([character.id]);
  126 |     const source = await creation.json();
  127 |     await expect(page.locator('.prompt-status')).toContainText('已保存');
  128 | 
  129 |     await openBoard();
  130 |     await page.getByRole('button', { name: '核对 Prompt 采用条件', exact: true }).click();
  131 |     const operation = page.getByRole('region', { name: 'Prompt 采用操作', exact: true });
  132 |     await operation.getByRole('combobox', { name: 'Prompt 来源家族', exact: true }).selectOption(source.family_id);
  133 |     await operation.getByRole('button', { name: '读取所选 Prompt 修订', exact: true }).click();
  134 |     await expect(operation).toContainText('采用成功闭环 第一版');
  135 |     const approving = page.waitForResponse(response => new URL(response.url()).pathname
  136 |       === `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/approve`
  137 |       && response.request().method() === 'POST');
  138 |     await operation.getByRole('button', { name: '批准所选 Prompt 修订', exact: true }).click();
  139 |     expect((await approving).status()).toBe(200);
  140 |     const sourceBodyPath = `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/body`;
  141 |     const body = await exact(await request.get(sourceBodyPath, { headers }), 200);
  142 |     expect(body).toMatchObject({ value: FIRST, verified: true, available: true });
  143 |     const before = await exact(await request.get(ownerPath, { headers }), 200);
  144 |     const target = await exact(await request.get(projectionPath, { headers }), 200);
  145 |     expect(target.write_enabled).toBe(true);
  146 |     expect(target.version).toBe(before.version);
  147 |     await expect(operation).toContainText(source.family_id);
  148 |     await expect(operation).toContainText(source.asset_id);
  149 |     await expect(operation).toContainText(body.digest);
  150 |     const adopt = operation.getByRole('button', { name: '采用到当前镜头', exact: true });
  151 |     await expect(adopt).toBeDisabled();
  152 |     await operation.scrollIntoViewIfNeeded();
  153 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-form.png'), fullPage: true });
  154 |     await adopt.scrollIntoViewIfNeeded();
  155 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-checkbox.png'), fullPage: true });
  156 |     await operation.getByRole('checkbox', { name: CONSENT, exact: true }).check();
  157 |     await expect(adopt).toBeEnabled();
  158 |     const adopting = page.waitForResponse(response => new URL(response.url()).pathname === adoptionPath
  159 |       && response.request().method() === 'POST');
  160 |     // The successful adoption is ONLY this original product button click.
  161 |     await adopt.click();
  162 |     const response = await adopting;
  163 |     expect(response.status(), await response.text()).toBe(200);
  164 |     const originalRequest = response.request().postDataJSON();
  165 |     const receipt = await response.json();
  166 |     expect(originalRequest).toMatchObject({ shot_id: shotId, family_id: source.family_id, asset_id: source.asset_id,
  167 |       revision: 1, expected_digest: body.digest, expected_version: before.version, expected_digest_target: target.digest });
  168 |     expect(receipt).toMatchObject({ committed: true, replayed: false, document_id: board.id,
  169 |       shot_id: shotId, version: before.version + 1 });
  170 |     const proof = receipt.adoption;
  171 |     expect(proof).toMatchObject({ document_id: board.id, shot_id: shotId, family_id: source.family_id,
  172 |       asset_id: source.asset_id, revision: 1, digest: body.digest, target_version: before.version,
  173 |       target_digest: target.digest, result_version: before.version + 1, request_id: originalRequest.request_id,
  174 |       source_binding_contract: 'prompt-adoption-bindings/1', source_bindings_verified: true });
  175 |     expect(proof.source_snapshot).toHaveLength(1);
  176 |     expect(proof.source_snapshot[0]).toMatchObject({ kind: 'CHARACTER', id: character.id,
  177 |       owner: 'NovelService.characters', digest: characterDigest, resolution: 'KNOWN', verification: 'WRITE_TIME_OWNER_LEASE' });
  178 |     expect(proof.source_snapshot[0].project_incarnation).toBeTruthy();
  179 |     expect(JSON.stringify(proof)).not.toContain(character.name);
  180 |     const committed = await exact(await request.get(ownerPath, { headers }), 200);
  181 |     expect(committed.version).toBe(before.version + 1);
  182 |     expect(committed.shots.find((row: { id: string }) => row.id === shotId).frame_prompt).toBe(FIRST);
  183 |     expect(committed.prompt_adoptions).toHaveLength(1);
  184 |     expect(committed.prompt_adoptions[0]).toEqual(proof);
  185 |     await expect(page.getByText('已回读确认 Prompt 采用；可查看固定的 Prompt 采用来源。', { exact: true })).toBeVisible();
  186 |     await page.locator('.creative-shot-card').first().click();
  187 |     await expect(page.getByRole('textbox', { name: '画面描述', exact: true })).toHaveValue(FIRST);
  188 |     await page.getByRole('textbox', { name: '画面描述', exact: true }).scrollIntoViewIfNeeded();
  189 |     const firstPin = await pin();
  190 |     await expect(firstPin).toContainText(source.asset_id);
  191 |     await expect(firstPin).toContainText(body.digest);
  192 |     await expect(firstPin).toContainText('仍然生效');
  193 |     await firstPin.scrollIntoViewIfNeeded();
  194 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-committed-pin.png'), fullPage: true });
  195 | 
  196 |     // A captured original DTO is replayed only as an additional idempotency
  197 |     // check. It is never presented as the successful UI interaction above.
  198 |     const replay = await exact(await request.post(adoptionPath, { headers, data: originalRequest }), 200);
  199 |     expect(replay).toMatchObject({ committed: true, replayed: true, version: committed.version });
  200 |     expect(replay.adoption).toEqual(proof);
```