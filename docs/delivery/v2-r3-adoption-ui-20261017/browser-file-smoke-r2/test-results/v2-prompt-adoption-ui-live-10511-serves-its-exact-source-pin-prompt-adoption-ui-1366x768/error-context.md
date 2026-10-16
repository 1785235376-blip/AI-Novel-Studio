# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-prompt-adoption-ui-live.spec.ts >> isolated original button commits bound Prompt and reload preserves its exact source pin
- Location: tests\e2e\v2-prompt-adoption-ui-live.spec.ts:19:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: getByText('采用 UI 验收 prompt-adoption-ui-1366x768', { exact: true }).first()
Expected: visible
Timeout: 25000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 25000ms
  - waiting for getByText('采用 UI 验收 prompt-adoption-ui-1366x768', { exact: true }).first()

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
- navigation "当前创作范围": 创作空间：我的创作空间 / 项目：采用 UI 验收 prompt-adoption-ui-1366x768 / 故事线：Default Storyline / 创作分支：main
- main:
  - complementary:
    - heading "独立创作" [level=2]
    - paragraph: 图片、视频和声音共享项目资产。连接其它模块由你决定。
    - button "返回项目列表"
    - group: 创作意图与推荐布局
    - group: 项目存储
  - button "创作开始"
  - button "任务中心"
  - button "素材工作区" [pressed]
  - button "创作图"
  - button "制作操作"
  - region "界面模式":
    - heading "界面模式" [level=3]
    - radiogroup "界面模式选择":
      - radio "新手模式"
      - radio "专业模式" [checked] [disabled]
    - paragraph: 新手模式与专业模式共用同一份项目、素材、任务与图谱数据；切换只改变界面呈现，不会转换、复制或删除任何内容。
  - heading "Prompt 工作台" [level=2]
  - paragraph: 在这里创建和修订手写 Prompt。保存只会新增一个不可变修订，不会覆盖旧版本； 这里不会调用任何模型，也不会因为输入而自动创建内容。
  - region "Prompt 列表":
    - button "新建 Prompt"
    - button "重新读取"
    - text: 搜索
    - searchbox "搜索"
    - text: 用途
    - combobox "用途":
      - option "全部" [selected]
      - option "IMAGE"
      - option "VIDEO"
      - option "AUDIO"
      - option "TEXT"
    - text: 状态
    - combobox "状态":
      - option "全部" [selected]
      - option "草稿"
      - option "已审核"
    - status:
      - strong: 还没有 Prompt
      - paragraph: 这里只会显示当前身份有权读取的 Prompt。可以新建一份手写草稿。
    - list
  - region "Prompt 编辑器":
    - status: 尚无未保存修改
    - text: 正文
    - textbox "正文"
    - paragraph: 按 UTF-8 字节计最长 64 KiB。不会自动去除空格、换行或 emoji。
    - text: Negative Prompt
    - textbox "Negative Prompt"
    - text: 用途
    - combobox "用途":
      - option "IMAGE" [selected]
      - option "VIDEO"
      - option "AUDIO"
      - option "TEXT"
    - text: 模型偏好
    - textbox "模型偏好"
    - text: Seed
    - textbox "Seed"
    - text: 参数（JSON，不会执行）
    - textbox "参数（JSON，不会执行）"
    - group "引用绑定（逗号或空格分隔 ID）":
      - text: 引用绑定（逗号或空格分隔 ID） 角色 ID
      - textbox "角色 ID"
      - text: 场景 ID
      - textbox "场景 ID"
      - text: 镜头 ID
      - textbox "镜头 ID"
      - text: 参考素材 ID
      - textbox "参考素材 ID"
    - text: 修改备注
    - textbox "修改备注"
    - text: 修改原因
    - textbox "修改原因"
    - button "保存为新 Prompt"
    - button "放弃本地修改"
    - term: 家族
    - definition: （新建）
    - term: 基准修订
    - definition: （新建）
    - term: 基准资产
    - definition: （新建）
    - term: 请求标识
    - definition: （未提交）
  - heading "独立素材工作区" [level=2]
  - paragraph: 无需小说、章节或模型，导入素材即可保存和导出。
  - paragraph: 上传会保存文件，并记录“外部导入”；许可默认未指定，可在来源声明中补充。下载原始文件保留原格式，不进行重新编码。
  - text: 手工导入可用 · 不需要模型
  - heading "资产库" [level=2]
  - button "上传资产"
  - status:
    - strong: 暂无资产
    - paragraph: 上传图片或其他创作素材。
  - text: 查找资产
  - searchbox "查找资产"
  - text: 类型筛选
  - combobox "类型筛选":
    - option "全部" [selected]
    - option "图片"
    - option "视频"
    - option "音频"
  - text: 0 项资产
  - button "回收站"
  - paragraph: 删除后原素材进入回收站，可恢复。已绑定的参考需重新审核后才能参与检索。
  - heading "素材浏览器" [level=2]
  - button "网格" [pressed]
  - button "列表"
  - button "重新读取素材"
  - form "素材筛选":
    - text: 搜索素材
    - searchbox "搜索素材"
    - text: 媒体种类
    - combobox "媒体种类":
      - option "全部（0）" [selected]
      - option "图片（0）"
      - option "视频（0）"
      - option "音频（0）"
      - option "未核实（0）"
    - text: 用途标签
    - combobox "用途标签":
      - option "全部" [selected]
      - option "角色（0）"
      - option "环境（0）"
      - option "道具（0）"
      - option "未打标签（0）"
    - text: 审核标记
    - combobox "审核标记":
      - option "全部" [selected]
      - option "无审核标记（0）"
      - option "待审核草稿（0）"
      - option "已批准（0）"
      - option "已驳回（0）"
    - text: 创建时间
    - combobox "创建时间":
      - option "全部" [selected]
      - option "未记录时间（0）"
      - option "今天（0）"
      - option "近 7 天（0）"
      - option "近 30 天（0）"
      - option "更早（0）"
    - text: 引用情况
    - combobox "引用情况":
      - option "全部" [selected]
      - option "已被引用（0）"
      - option "未被引用（0）"
      - option "引用情况未核实（0）"
    - button "清除筛选" [disabled]
    - paragraph: 搜索只匹配已读取的元数据（文件名、类型、标签、审核标记、引用摘要）， 不会扫描磁盘、不会打开未授权内容。
    - paragraph: 标记为 角色 / 环境 / 道具 只是作者用途标签， 不改变素材的媒体种类（图片 / 视频 / 音频）。
  - status:
    - strong: 此项目暂无素材
    - paragraph: 此项目当前没有可读取的素材。
  - status: 显示 0 / 0 条。只显示已读取的前若干条；继续加载会再读取下一页，绝不一次拉取全部高清素材。
  - text: 每页条数
  - combobox "每页条数":
    - option "8 条"
    - option "24 条" [selected]
    - option "48 条"
    - option "96 条"
  - list "素材列表"
  - status: 当前筛选没有匹配的素材；已读取的素材仍然保留。
  - region "素材详情":
    - status:
      - strong: 未选择素材
      - paragraph: 从素材网格或列表选择一项，才会按需读取它的版本、来源与引用。
  - paragraph: 缩略图按需读取（缩略图只在需要时按原下载接口读取，不预取整库。）。 引用关系当前不可读，引用情况显示为未核实，不会当作"未被引用"。
  - paragraph: 新的来源版本只显示差异；只有你明确选择才会更新绑定，绝不自动更新所有任务 / 镜头 / 片段。
  - button "收起侧栏" [expanded]
  - complementary:
    - separator "调整检查面板宽度"
    - text: 创作辅助
    - button "收起侧栏"
    - region "资产检查面板":
      - text: Inspector
      - status:
        - strong: 未选择资产
        - paragraph: 从资产网格选择一个项目以查看真实预览和元数据。
- contentinfo:
  - text: 已保存 · 独立素材 · 模型调用记录见运行回执
  - button "问助手"
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
  71  |       await expect.poll(async () =>
  72  |         await page.getByText('连接已有创作空间', { exact: true }).isVisible()
  73  |         || await page.getByLabel('访问凭证', { exact: true }).isVisible()
  74  |         || await page.getByRole('button', { name: '我的创作空间', exact: true }).isVisible()
  75  |         || await page.getByText(title, { exact: true }).first().isVisible(), { timeout: 30_000 }).toBe(true);
  76  |       if (await page.getByText('连接已有创作空间', { exact: true }).isVisible()) {
  77  |         await page.getByText('连接已有创作空间', { exact: true }).click();
  78  |         await expect(page.getByLabel('访问凭证', { exact: true })).toBeVisible();
  79  |       }
  80  |       if (await page.getByLabel('访问凭证', { exact: true }).isVisible()) {
  81  |         await page.getByLabel('访问凭证', { exact: true }).fill(token);
  82  |         await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  83  |         await expect(page.getByRole('button', { name: '我的创作空间', exact: true })).toBeVisible();
  84  |       }
  85  |       const workspace = page.getByRole('button', { name: '我的创作空间', exact: true });
  86  |       const projectChoice = page.getByRole('button', { name: new RegExp(title) });
  87  |       if (await workspace.isVisible()) {
  88  |         await workspace.click();
  89  |         await expect(projectChoice).toBeVisible();
  90  |       }
  91  |       if (await projectChoice.isVisible()) await projectChoice.click();
> 92  |       await expect(page.getByText(title, { exact: true }).first()).toBeVisible();
      |                                                                    ^ Error: expect(locator).toBeVisible() failed
  93  |     };
  94  |     const openBoard = async () => {
  95  |       await page.getByRole('button', { name: '小说', exact: true }).click();
  96  |       await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  97  |       await page.getByRole('tab', { name: /^分镜/ }).click();
  98  |       await page.getByRole('region', { name: '创作文档', exact: true })
  99  |         .getByRole('button', { name: new RegExp(boardTitle) }).click();
  100 |       await page.getByRole('button', { name: '按需打开镜头工作区', exact: true }).click();
  101 |       const shots = page.getByRole('region', { name: '分镜工作区', exact: true });
  102 |       await shots.getByRole('button', { name: '读取已保存分镜', exact: true }).click();
  103 |       await shots.getByRole('button', { name: `镜头 1（身份 ${shotId}）`, exact: true }).click();
  104 |       return shots;
  105 |     };
  106 |     const pin = async () => {
  107 |       const show = page.getByRole('button', { name: '查看 Prompt 采用来源', exact: true });
  108 |       if (await show.isVisible()) await show.click();
  109 |       const value = page.locator('.prompt-adoption-record');
  110 |       await expect(value).toBeVisible();
  111 |       return value;
  112 |     };
  113 | 
  114 |     await enterProject();
  115 |     await openPromptWorkspace(page);
  116 |     await page.getByRole('button', { name: '新建 Prompt', exact: true }).click();
  117 |     await page.getByLabel('正文', { exact: true }).fill(FIRST);
  118 |     await page.getByLabel('角色 ID', { exact: true }).fill(character.id);
  119 |     const creating = page.waitForResponse(response => new URL(response.url()).pathname === `${studio}/prompts`
  120 |       && response.request().method() === 'POST');
  121 |     await page.getByRole('button', { name: '保存为新 Prompt', exact: true }).click();
  122 |     const creation = await creating;
  123 |     expect(creation.status(), await creation.text()).toBe(201);
  124 |     expect(creation.request().postDataJSON().character_ids).toEqual([character.id]);
  125 |     const source = await creation.json();
  126 |     await expect(page.locator('.prompt-status')).toContainText('已保存');
  127 | 
  128 |     await openBoard();
  129 |     await page.getByRole('button', { name: '核对 Prompt 采用条件', exact: true }).click();
  130 |     const operation = page.getByRole('region', { name: 'Prompt 采用操作', exact: true });
  131 |     await operation.getByLabel('Prompt 来源家族', { exact: true }).selectOption(source.family_id);
  132 |     await operation.getByRole('button', { name: '读取所选 Prompt 修订', exact: true }).click();
  133 |     await expect(operation).toContainText('采用成功闭环 第一版');
  134 |     const approving = page.waitForResponse(response => new URL(response.url()).pathname
  135 |       === `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/approve`
  136 |       && response.request().method() === 'POST');
  137 |     await operation.getByRole('button', { name: '批准所选 Prompt 修订', exact: true }).click();
  138 |     expect((await approving).status()).toBe(200);
  139 |     const sourceBodyPath = `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/body`;
  140 |     const body = await exact(await request.get(sourceBodyPath, { headers }), 200);
  141 |     expect(body).toMatchObject({ value: FIRST, verified: true, available: true });
  142 |     const before = await exact(await request.get(ownerPath, { headers }), 200);
  143 |     const target = await exact(await request.get(projectionPath, { headers }), 200);
  144 |     expect(target.write_enabled).toBe(true);
  145 |     expect(target.version).toBe(before.version);
  146 |     await expect(operation).toContainText(source.family_id);
  147 |     await expect(operation).toContainText(source.asset_id);
  148 |     await expect(operation).toContainText(body.digest);
  149 |     const adopt = operation.getByRole('button', { name: '采用到当前镜头', exact: true });
  150 |     await expect(adopt).toBeDisabled();
  151 |     await operation.scrollIntoViewIfNeeded();
  152 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-form.png'), fullPage: true });
  153 |     await operation.getByRole('checkbox', { name: CONSENT, exact: true }).scrollIntoViewIfNeeded();
  154 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-checkbox.png'), fullPage: true });
  155 |     await operation.getByRole('checkbox', { name: CONSENT, exact: true }).check();
  156 |     await expect(adopt).toBeEnabled();
  157 |     const adopting = page.waitForResponse(response => new URL(response.url()).pathname === adoptionPath
  158 |       && response.request().method() === 'POST');
  159 |     // The successful adoption is ONLY this original product button click.
  160 |     await adopt.click();
  161 |     const response = await adopting;
  162 |     expect(response.status(), await response.text()).toBe(200);
  163 |     const originalRequest = response.request().postDataJSON();
  164 |     const receipt = await response.json();
  165 |     expect(originalRequest).toMatchObject({ shot_id: shotId, family_id: source.family_id, asset_id: source.asset_id,
  166 |       revision: 1, expected_digest: body.digest, expected_version: before.version, expected_digest_target: target.digest });
  167 |     expect(receipt).toMatchObject({ committed: true, replayed: false, document_id: board.id,
  168 |       shot_id: shotId, version: before.version + 1 });
  169 |     const proof = receipt.adoption;
  170 |     expect(proof).toMatchObject({ document_id: board.id, shot_id: shotId, family_id: source.family_id,
  171 |       asset_id: source.asset_id, revision: 1, digest: body.digest, target_version: before.version,
  172 |       target_digest: target.digest, result_version: before.version + 1, request_id: originalRequest.request_id,
  173 |       source_binding_contract: 'prompt-adoption-bindings/1', source_bindings_verified: true });
  174 |     expect(proof.source_snapshot).toHaveLength(1);
  175 |     expect(proof.source_snapshot[0]).toMatchObject({ kind: 'CHARACTER', id: character.id,
  176 |       owner: 'NovelService.characters', digest: characterDigest, resolution: 'KNOWN', verification: 'WRITE_TIME_OWNER_LEASE' });
  177 |     expect(proof.source_snapshot[0].project_incarnation).toBeTruthy();
  178 |     expect(JSON.stringify(proof)).not.toContain(character.name);
  179 |     const committed = await exact(await request.get(ownerPath, { headers }), 200);
  180 |     expect(committed.version).toBe(before.version + 1);
  181 |     expect(committed.shots.find((row: { id: string }) => row.id === shotId).frame_prompt).toBe(FIRST);
  182 |     expect(committed.prompt_adoptions).toHaveLength(1);
  183 |     expect(committed.prompt_adoptions[0]).toEqual(proof);
  184 |     await expect(page.getByText('已回读确认 Prompt 采用；可查看固定的 Prompt 采用来源。', { exact: true })).toBeVisible();
  185 |     await page.locator('.creative-shot-card').first().click();
  186 |     await expect(page.getByLabel('画面描述', { exact: true })).toHaveValue(FIRST);
  187 |     await page.getByLabel('画面描述', { exact: true }).scrollIntoViewIfNeeded();
  188 |     const firstPin = await pin();
  189 |     await expect(firstPin).toContainText(source.asset_id);
  190 |     await expect(firstPin).toContainText(body.digest);
  191 |     await expect(firstPin).toContainText('仍然生效');
  192 |     await firstPin.scrollIntoViewIfNeeded();
```