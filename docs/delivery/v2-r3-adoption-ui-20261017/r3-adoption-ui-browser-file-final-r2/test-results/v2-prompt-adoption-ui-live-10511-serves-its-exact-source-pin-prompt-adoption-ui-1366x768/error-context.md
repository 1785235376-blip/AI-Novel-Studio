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

Locator: getByRole('navigation', { name: '当前创作范围', exact: true }).filter({ hasText: '采用 UI 验收 prompt-adoption-ui-1366x768' })
Expected: visible
Timeout: 25000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 25000ms
  - waiting for getByRole('navigation', { name: '当前创作范围', exact: true }).filter({ hasText: '采用 UI 验收 prompt-adoption-ui-1366x768' })

```

```yaml
- banner:
  - strong: AI Novel
  - text: Studio
  - tablist "创作模块":
    - tab "小说" [selected]
    - tab "图片"
    - tab "视频"
    - tab "资产"
    - tab "声音"
    - tab "主控"
    - tab "插件"
    - tab "工作流"
  - button "打开全局命令": 搜索作品、章节与素材 Ctrl K
  - text: 本机作者
- navigation "当前创作范围": 创作空间：本机作品 / 小说：Adoption UI production control / 故事线：默认故事线 / 创作分支：主线
- main:
  - complementary:
    - text: 小说结构
    - strong: 章节导航
    - heading "作品结构" [level=2]
    - button "新建章节"
    - status:
      - strong: 还没有章节
      - paragraph: 正文目录中还没有章节。创建新章节开始写作，或从已移出章节中恢复。
    - region "已移出章节":
      - heading "已移出章节" [level=3]
      - paragraph: 目前没有已移出章节。
    - text: 工作区
    - strong: 创作工具
    - button "打开功能导航": 功能导航
    - tooltip "打开功能导航"
  - text: 当前章节 未选择章节 0 字 目标 0 / 0 字 第 0 / 0 章
  - progressbar
  - strong: 0%
  - status: 正在打开章节…
  - button "保存" [disabled]
  - strong: 当前还没有打开的章节
  - paragraph: 在左侧新建或选择章节，开始写作。
  - button "收起侧栏" [expanded]
  - complementary:
    - separator "调整检查面板宽度"
    - text: 创作辅助
    - button "收起侧栏"
    - region "当前写作上下文":
      - text: 当前章节
      - strong: 未选择章节
      - text: 从左侧章节树选择章节
    - heading "项目概览" [level=2]
    - paragraph: 设置本小说的创作目标，进度会同步显示在编辑器顶部。
    - text: 目标字数
    - spinbutton "目标字数": "0"
    - text: 目标章节
    - spinbutton "目标章节": "0"
    - text: 截止日期
    - textbox "截止日期"
    - button "保存写作目标" [disabled]
    - heading "AI 写作助手" [level=2]
    - tablist "AI 写作方式":
      - tab "创作下一章" [selected]
      - tab "改写"
      - tab "润色"
      - tab "头脑风暴"
    - text: 文本模型
    - combobox "文本模型":
      - option "尚未选择文本模型" [selected]
    - region "当前模型":
      - strong: 当前模型
      - text: 尚未选择模型
      - status: 选择模型后可查看是否能够开始写作。
    - group "候选方案数量":
      - text: 候选方案
      - button "1" [pressed]
      - button "2"
      - button "3"
    - text: 附加要求（可选）
    - textbox "附加要求（可选）":
      - /placeholder: 例如：保持紧张节奏，突出人物犹豫。
    - text: 写作风格（可选）
    - textbox "写作风格（可选）":
      - /placeholder: 例如：克制、冷峻、短句为主
    - button "克制冷峻 · 短句为主"
    - button "细腻抒情 · 强化感官"
    - button "紧张悬疑 · 加快节奏"
    - button "轻松幽默 · 对话自然"
    - button "生成创作下一章草稿" [disabled]
    - region "生成流程":
      - strong: 生成流程
      - text: 上下文 → 计划 → 草稿 → 审核
      - list:
        - listitem:
          - strong: 读取创作上下文
          - text: 等待 开始生成后读取
        - listitem:
          - strong: 建立生成计划
          - text: 等待 等待任务创建
        - listitem:
          - strong: 生成章节草稿
          - text: 等待 等待生成
        - listitem:
          - strong: 作者审核
          - text: 等待 等待可审核草稿
    - status:
      - strong: 尚未生成草稿
      - paragraph: 选择写作方式并生成后，可在这里预览、比较和决定是否采用。
- contentinfo:
  - text: 保存：正在打开章节… · 连接：本机 · AI 任务：无运行任务
  - button "问助手"
```

# Test source

```ts
  1   | import { createHash } from 'node:crypto';
  2   | import { expect, test, type APIResponse } from '@playwright/test';
  3   | import { openPromptWorkspace, promptLibrary, studioSwitcher } from '../../e2e/promptAcceptanceEntry';
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
> 93  |       await expect(currentScope).toBeVisible();
      |                                  ^ Error: expect(locator).toBeVisible() failed
  94  |       // Scope is restored before the original App overview/entry effect ends.
  95  |       // Wait for its real IMAGE destination and loaded workspace before asking
  96  |       // the original module navigation to open the storyboard.
  97  |       await expect(page.getByRole('tab', { name: '图片', exact: true })).toHaveAttribute('aria-selected', 'true');
  98  |       await expect(studioSwitcher(page)).toBeVisible();
  99  |     };
  100 |     const openBoard = async () => {
  101 |       await page.getByRole('tab', { name: '小说', exact: true }).click();
  102 |       await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  103 |       await page.getByRole('tab', { name: /^分镜/ }).click();
  104 |       await page.getByRole('region', { name: '创作文档', exact: true })
  105 |         .getByRole('button', { name: new RegExp(boardTitle) }).click();
  106 |       await page.getByRole('button', { name: '按需打开镜头工作区', exact: true }).click();
  107 |       const shots = page.getByRole('region', { name: '分镜工作区', exact: true });
  108 |       await shots.getByRole('button', { name: '读取已保存分镜', exact: true }).click();
  109 |       await shots.getByRole('button', { name: `镜头 1（身份 ${shotId}）`, exact: true }).click();
  110 |       return shots;
  111 |     };
  112 |     const pin = async () => {
  113 |       const show = page.getByRole('button', { name: '查看 Prompt 采用来源', exact: true });
  114 |       if (await show.isVisible()) await show.click();
  115 |       const value = page.locator('.prompt-adoption-record');
  116 |       await expect(value).toBeVisible();
  117 |       return value;
  118 |     };
  119 | 
  120 |     await enterProject();
  121 |     await openPromptWorkspace(page);
  122 |     await page.getByRole('button', { name: '新建 Prompt', exact: true }).click();
  123 |     await page.getByLabel('正文', { exact: true }).fill(FIRST);
  124 |     await page.getByLabel('角色 ID', { exact: true }).fill(character.id);
  125 |     const creating = page.waitForResponse(response => new URL(response.url()).pathname === `${studio}/prompts`
  126 |       && response.request().method() === 'POST');
  127 |     await page.getByRole('button', { name: '保存为新 Prompt', exact: true }).click();
  128 |     const creation = await creating;
  129 |     expect(creation.status(), await creation.text()).toBe(201);
  130 |     expect(creation.request().postDataJSON().character_ids).toEqual([character.id]);
  131 |     const source = await creation.json();
  132 |     await expect(page.locator('.prompt-status')).toContainText('已保存');
  133 | 
  134 |     await openBoard();
  135 |     await page.getByRole('button', { name: '核对 Prompt 采用条件', exact: true }).click();
  136 |     const operation = page.getByRole('region', { name: 'Prompt 采用操作', exact: true });
  137 |     await operation.getByRole('combobox', { name: 'Prompt 来源家族', exact: true }).selectOption(source.family_id);
  138 |     await operation.getByRole('button', { name: '读取所选 Prompt 修订', exact: true }).click();
  139 |     await expect(operation).toContainText('采用成功闭环 第一版');
  140 |     const approving = page.waitForResponse(response => new URL(response.url()).pathname
  141 |       === `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/approve`
  142 |       && response.request().method() === 'POST');
  143 |     await operation.getByRole('button', { name: '批准所选 Prompt 修订', exact: true }).click();
  144 |     expect((await approving).status()).toBe(200);
  145 |     const sourceBodyPath = `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/body`;
  146 |     const body = await exact(await request.get(sourceBodyPath, { headers }), 200);
  147 |     expect(body).toMatchObject({ value: FIRST, verified: true, available: true });
  148 |     const before = await exact(await request.get(ownerPath, { headers }), 200);
  149 |     const target = await exact(await request.get(projectionPath, { headers }), 200);
  150 |     expect(target.write_enabled).toBe(true);
  151 |     expect(target.version).toBe(before.version);
  152 |     await expect(operation).toContainText(source.family_id);
  153 |     await expect(operation).toContainText(source.asset_id);
  154 |     await expect(operation).toContainText(body.digest);
  155 |     const adopt = operation.getByRole('button', { name: '采用到当前镜头', exact: true });
  156 |     await expect(adopt).toBeDisabled();
  157 |     await operation.scrollIntoViewIfNeeded();
  158 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-form.png'), fullPage: true });
  159 |     await adopt.scrollIntoViewIfNeeded();
  160 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-checkbox.png'), fullPage: true });
  161 |     await operation.getByRole('checkbox', { name: CONSENT, exact: true }).check();
  162 |     await expect(adopt).toBeEnabled();
  163 |     const adopting = page.waitForResponse(response => new URL(response.url()).pathname === adoptionPath
  164 |       && response.request().method() === 'POST');
  165 |     // The successful adoption is ONLY this original product button click.
  166 |     await adopt.click();
  167 |     const response = await adopting;
  168 |     expect(response.status(), await response.text()).toBe(200);
  169 |     const originalRequest = response.request().postDataJSON();
  170 |     const receipt = await response.json();
  171 |     expect(originalRequest).toMatchObject({ shot_id: shotId, family_id: source.family_id, asset_id: source.asset_id,
  172 |       revision: 1, expected_digest: body.digest, expected_version: before.version, expected_digest_target: target.digest });
  173 |     expect(receipt).toMatchObject({ committed: true, replayed: false, document_id: board.id,
  174 |       shot_id: shotId, version: before.version + 1 });
  175 |     const proof = receipt.adoption;
  176 |     expect(proof).toMatchObject({ document_id: board.id, shot_id: shotId, family_id: source.family_id,
  177 |       asset_id: source.asset_id, revision: 1, digest: body.digest, target_version: before.version,
  178 |       target_digest: target.digest, result_version: before.version + 1, request_id: originalRequest.request_id,
  179 |       source_binding_contract: 'prompt-adoption-bindings/1', source_bindings_verified: true });
  180 |     expect(proof.source_snapshot).toHaveLength(1);
  181 |     expect(proof.source_snapshot[0]).toMatchObject({ kind: 'CHARACTER', id: character.id,
  182 |       owner: 'NovelService.characters', digest: characterDigest, resolution: 'KNOWN', verification: 'WRITE_TIME_OWNER_LEASE' });
  183 |     expect(proof.source_snapshot[0].project_incarnation).toBeTruthy();
  184 |     expect(JSON.stringify(proof)).not.toContain(character.name);
  185 |     const committed = await exact(await request.get(ownerPath, { headers }), 200);
  186 |     expect(committed.version).toBe(before.version + 1);
  187 |     expect(committed.shots.find((row: { id: string }) => row.id === shotId).frame_prompt).toBe(FIRST);
  188 |     expect(committed.prompt_adoptions).toHaveLength(1);
  189 |     expect(committed.prompt_adoptions[0]).toEqual(proof);
  190 |     await expect(page.getByText('已回读确认 Prompt 采用；可查看固定的 Prompt 采用来源。', { exact: true })).toBeVisible();
  191 |     await page.locator('.creative-shot-card').first().click();
  192 |     await expect(page.getByRole('textbox', { name: '画面描述', exact: true })).toHaveValue(FIRST);
  193 |     await page.getByRole('textbox', { name: '画面描述', exact: true }).scrollIntoViewIfNeeded();
```