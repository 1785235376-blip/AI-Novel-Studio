# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-prompt-adoption-ui-live.spec.ts >> isolated original button commits bound Prompt and reload preserves its exact source pin
- Location: tests\e2e\v2-prompt-adoption-ui-live.spec.ts:19:1

# Error details

```
Error: expect(locator).toHaveValue(expected) failed

Locator: getByLabel('画面描述', { exact: true })
Expected: "  采用成功闭环 第一版
逐字中文与 emoji 🙂··
"
Timeout: 25000ms
Error: element(s) not found

Call log:
  - Expect "toHaveValue" with timeout 25000ms
  - waiting for getByLabel('画面描述', { exact: true })

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
  - text: local-author
- navigation "当前创作范围": 创作空间：我的创作空间 / 小说：采用 UI 验收 prompt-adoption-ui-1366x768 / 故事线：Default Storyline / 创作分支：main
- main:
  - complementary:
    - text: Asset Browser
    - heading "创作资产" [level=2]
    - button "返回经典工作区"
    - region "创作文档":
      - heading "当前阶段文档" [level=3]
      - button "真实分镜 prompt-adoption-ui-1366x768 v2 · 1 场景" [pressed]:
        - strong: 真实分镜 prompt-adoption-ui-1366x768
        - text: v2 · 1 场景
    - button "世界 World"
    - button "人物 Character"
    - button "场景 Scene" [pressed]
    - button "镜头 Shot"
    - button "音频 Audio"
    - button "视频 Video"
    - text: 筛选资产
    - searchbox "筛选资产"
    - button "INT. ROOM - DAY 场景 1":
      - strong: INT. ROOM - DAY
      - text: 场景 1
  - navigation "项目创作阶段":
    - text: 叙事制作 · V2 实验功能
    - tablist "创作模式":
      - tab "小说 Novel · 0":
        - strong: 小说
        - text: Novel · 0
      - tab "剧本 Screenplay · 1":
        - strong: 剧本
        - text: Screenplay · 1
      - tab "导演 Director · 0":
        - strong: 导演
        - text: Director · 0
      - tab "分镜 Storyboard · 1" [selected]:
        - strong: 分镜
        - text: Storyboard · 1
      - tab "制作 Production · 0":
        - strong: 制作
        - text: Production · 0
  - tabpanel "分镜 Storyboard · 1":
    - region "创作画布":
      - text: Creative Canvas
      - heading "真实分镜 prompt-adoption-ui-1366x768" [level=2]
      - text: 已保存 · v2
      - button "新建文档"
      - button "保存草稿" [disabled]
      - button "建立制作计划"
      - button "导出"
      - button "历史"
      - group "创作文档内容":
        - text: 创作文档内容 文档标题
        - textbox "文档标题": 真实分镜 prompt-adoption-ui-1366x768
        - text: 来源：服务端绑定的创作文档
        - region "项目视觉目标":
          - heading "项目视觉目标" [level=3]
          - text: 尚未设定
          - paragraph: 导演目标随当前文档版本保存。明确建立分镜草稿时才传递到新文档；修改目标不会自动改写场景或执行媒体。
          - text: 视觉风格
          - textbox "视觉风格"
          - text: 整体氛围
          - textbox "整体氛围"
          - group: 展开色彩、节奏与参考作品
        - button "添加场景"
        - button "添加镜头"
        - button "SCENE 01 INT. ROOM - DAY" [pressed]:
          - text: SCENE 01
          - strong: INT. ROOM - DAY
        - region "当前场景":
          - text: 场景标题
          - textbox "场景标题": INT. ROOM - DAY
          - text: 场景地点
          - textbox "场景地点"
          - text: 场景时间
          - textbox "场景时间"
          - text: 场景情绪
          - textbox "场景情绪"
          - text: 动作与叙事
          - textbox "动作与叙事": A visitor arrives.
        - region "分镜画布":
          - button "镜头卡片" [pressed]
          - button "镜头列表"
          - text: 1 镜头 · 5 秒
          - article:
            - button "SHOT 01 5s 采用成功闭环 第一版 逐字中文与 emoji 🙂 INT. ROOM - DAY · MEDIUM · STATIC" [pressed]:
              - strong: SHOT 01
              - text: 5s
              - paragraph: 采用成功闭环 第一版 逐字中文与 emoji 🙂
              - text: INT. ROOM - DAY · MEDIUM · STATIC
            - button "前移镜头 1" [disabled]: 前移
            - button "后移镜头 1" [disabled]: 后移
          - region "选中镜头预览":
            - heading "SHOT 01 · 创作预览" [level=3]
            - code: f3ef66d6-1fb3-447d-8e0c-732721b579f0
            - paragraph: 采用成功闭环 第一版 逐字中文与 emoji 🙂
            - paragraph: 构图待设定 · EYE_LEVEL · STATIC · 5 秒
            - paragraph: 角色：未指定 · 情绪：
            - paragraph: 声音：未指定
            - text: 这是作者分镜数据的预览。保存后可在创作图绑定此文档版本；图片生成与人工审核仍分别确认。
          - region "镜头 1 参数":
            - heading "镜头 1 · 参数" [level=3]
            - text: 镜头所属场景
            - combobox "镜头所属场景":
              - option "INT. ROOM - DAY" [selected]
            - text: 镜头时长（秒）
            - spinbutton "镜头时长（秒）": "5"
            - text: 镜头景别
            - textbox "镜头景别": MEDIUM
            - text: 镜头角度
            - textbox "镜头角度": EYE_LEVEL
            - text: 镜头运动
            - textbox "镜头运动": STATIC
            - text: 镜头与焦距
            - textbox "镜头与焦距"
            - text: 光线设计
            - textbox "光线设计"
            - text: 环境设计
            - textbox "环境设计"
            - text: 构图
            - textbox "构图"
            - text: 色彩
            - textbox "色彩"
            - text: 声音设计
            - textbox "声音设计"
            - text: 画面描述
            - textbox "画面描述": 采用成功闭环 第一版 逐字中文与 emoji 🙂
            - text: 镜头动作
            - textbox "镜头动作": A visitor arrives.
            - text: 镜头角色（用、分隔）
            - textbox "镜头角色（用、分隔）"
            - text: 镜头情绪
            - textbox "镜头情绪"
            - group: 展开视频生成意图
            - group: 展开镜头连续性与导演来源
  - region "制作时间轴":
    - text: Production Timeline
    - heading "制作序列" [level=2]
    - text: 1 段 · 5s 结构化计划 · 尚未渲染媒体
    - list:
      - listitem:
        - button "0s → 5s 镜头 1 5s":
          - text: 0s → 5s
          - strong: 镜头 1
          - text: 5s
  - button "收起侧栏" [expanded]
  - complementary:
    - separator "调整检查面板宽度"
    - text: 创作辅助
    - button "收起侧栏"
    - heading "分镜生产检查器" [level=2]
    - paragraph: 来源：真实分镜 prompt-adoption-ui-1366x768 · v2。原文档保存、素材审核与生产任务分别操作。
    - button "明确读取已保存创作回执"
    - button "按需打开镜头工作区" [expanded]
    - region "分镜工作区":
      - heading "导演与分镜" [level=2]
      - text: 项目 94501e0a-c87c-46bd-b97b-d4e5cb2376c3 文档 e05e9f14-bed3-4628-b387-af308feeffa5 等待原分镜审核
      - button "读取已保存分镜"
      - button "重新读取"
      - status: 已回读确认 Prompt 采用；可查看固定的 Prompt 采用来源。
      - region "分镜镜头清单":
        - heading "镜头清单" [level=3]
        - text: 1 个镜头
        - list:
          - listitem:
            - button "镜头 1（身份 f3ef66d6-1fb3-447d-8e0c-732721b579f0）" [pressed]: SHOT 1 f3ef66d6-1fb3-447d-8e0c-732721b579f0 采用成功闭环 第一版 逐字中文与 emoji 🙂 时长 5 秒 景别 MEDIUM 机位 EYE_LEVEL 运动 STATIC v2 尚无正式绑定 来源有变化（1 条证据） 下一步：准备图片请求草稿（不派发）
            - status: DIRECTOR_SOURCE_UNAVAILABLE：原分镜记下的上游文档 92fb31f3-1c57-4239-8763-f41b3912f3f2 目前读不到，无法确认它是否仍然是同一版本。
            - text: 位置 1（显示序号 1）
            - button "移到最前" [disabled]
            - button "上移" [disabled]
            - button "下移" [disabled]
            - button "移到最后" [disabled]
      - heading "镜头详情 · SHOT 1" [level=2]
      - text: 身份 f3ef66d6-1fb3-447d-8e0c-732721b579f0 显示序号 1 镜头版本 v2 未绑定正式图片 未绑定正式视频
      - term: 所属场景
      - definition: real-ui-scene
      - term: 时长（秒）
      - definition: "5"
      - term: 景别
      - definition: MEDIUM
      - term: 机位角度
      - definition: EYE_LEVEL
      - term: 摄影机运动
      - definition: STATIC
      - term: 镜头/焦段
      - definition: 原文档未提供
      - term: 构图
      - definition: 原文档未提供
      - term: 光线
      - definition: 原文档未提供
      - term: 色彩
      - definition: 原文档未提供
      - term: 环境
      - definition: 原文档未提供
      - term: 音效
      - definition: 原文档未提供
      - term: 声音
      - definition: 原文档未提供
      - region "原文档证据":
        - heading "原文档证据" [level=4]
        - paragraph: 这些字段读到了：number、scene_id、duration_seconds、framing。
        - paragraph: 这些字段原文档没有提供：lighting、characters、director_note_ids、continuity、image_binding、video_binding、audio。
        - group: 镜头内容摘要（原 owner 的 shot_digest）
      - region "相邻镜头":
        - heading "相邻镜头" [level=4]
        - paragraph: 前一个：这是第一个镜头（边界，不回绕）
        - paragraph: 后一个：这是最后一个镜头（边界，不回绕）
        - paragraph: 原文档声明的邻居：前 未声明 · 后 未声明（声明值就是原文档事实，本工作区不改写它）。
      - region "镜头引用":
        - heading "引用与一致性要求" [level=4]
        - paragraph: 角色：原文档未提供
        - paragraph: 关联导演备注：原文档未提供
        - paragraph: 原文档没有声明一致性要求（这里不会替你判断"连续性没问题"）。
      - region "参考比较":
        - heading "参考比较" [level=4]
        - button "只读比较绑定素材与镜头版本" [disabled]
        - paragraph: 这个镜头还没有正式绑定的候选素材。
        - list:
          - listitem:
            - text: DIRECTOR_SOURCE_UNAVAILABLE 原分镜记下的上游文档 92fb31f3-1c57-4239-8763-f41b3912f3f2 目前读不到，无法确认它是否仍然是同一版本。
            - code: 92fb31f3-1c57-4239-8763-f41b3912f3f2 v1
      - region "镜头下一步":
        - heading "下一步可做的事" [level=4]
        - list:
          - listitem: 准备图片请求草稿（不派发）
          - listitem: 核对并批准当前分镜版本
          - listitem: 准备视频请求草稿（不派发）
        - button "准备图片请求草稿"
        - button "准备视频请求草稿"
        - button "准备时间线底稿请求"
        - paragraph: 这是一张草稿卡片：不会入队、不会调用模型、不会改写原文档或时间线。
      - button "查看 Prompt 采用来源"
      - region "Prompt 采用操作":
        - button "核对 Prompt 采用条件"
      - heading "送往…" [level=2]
      - paragraph: 这里只形成草稿。目标模块是否执行、何时执行，由拿到这张卡的界面与它自己的 owner 决定；本工作区永远不会替你执行。
      - group "目标模块":
        - text: 目标模块
        - radio "图片候选（IMAGE）" [checked]
        - text: 图片候选（IMAGE）
        - radio "视频候选（VIDEO）"
        - text: 视频候选（VIDEO）
        - radio "时间线底稿（TIMELINE）"
        - text: 时间线底稿（TIMELINE）
      - button "形成 图片候选 草稿"
      - status: 还没有形成草稿。形成后这里会逐条列出目标模块将要引用的原版本。
      - paragraph: 这是一张草稿卡片：不会入队、不会调用模型、不会改写原文档或时间线。
      - paragraph: 草稿不包含请求标识、任务标识或执行开关，所以它没有被派发的可能。若目标模块当前不可用，请使用原模块的界面。
      - text: 图片：原图片界面 视频：原视频界面 时间线：原时间线界面
      - button "目标模块不可用"
      - heading "导演目标" [level=2]
      - paragraph: 导演是可选的创作节点，不是其它模块的"核心权威"：这里不改写镜头、不撤销批准，也不会因为改目标就覆盖已经批准的下游结果。
      - status: 还没有读到导演目标。这里不会编造目标；请先读取导演文档，或使用原导演界面创建。
      - region "AI 建议（待审）":
        - heading "AI 建议（待审，与原文档已采用内容分开）" [level=4]
        - paragraph: "这些是原 owner 的 `director-proposals` 记录，状态不是\"已批准\"；它们**没有**生效，也不能被这里直接采用。"
        - paragraph: 没有读到待审建议（或本工作区没有提供读取入口）。
        - button "只读读取导演调度建议"
      - button "按需打开导演工作台"
      - button "按需打开角色与场景圣经"
    - text: AI Director
    - heading "导演协作与审核" [level=2]
    - heading "从剧本准备导演建议" [level=2]
    - paragraph: 本地规则辅助会整理场景调度草案。不会调用模型；采用后新增独立导演文档。
    - text: 导演建议来源剧本
    - combobox "导演建议来源剧本":
      - option "选择已保存剧本"
      - option "真实来源剧本 prompt-adoption-ui-1366x768 · v1" [selected]
    - group: 本次导演建议的视觉目标（可选）
    - button "准备待审导演建议"
    - heading "建议审核队列" [level=2]
    - button "刷新"
    - status:
      - strong: 没有待审导演建议
      - paragraph: 手动编辑始终可用。只有明确核对并采用建议才会创建导演文档。
    - region "本地 AI 环境摘要":
      - heading "本地 AI 环境" [level=2]
      - text: 尚未检测
      - paragraph: 仅检测运行后端的主机；云端结果不代表你的电脑。
      - status: 到模型中心先预览检测范围，再确认查找已有服务；常用模型目录需明确选择。
      - paragraph: 真实推理：NOT_RUN。Windows 实机验收：NOT_RUN。发现模型不会自动启用或加载。
      - button "打开模型中心"
      - button "重新读取"
    - heading "模型与执行能力" [level=2]
    - paragraph: 模型调用需要已配置且可用的 Provider。此工作区不会自动启动模型或渲染音视频。
    - button "打开模型控制中心"
- contentinfo:
  - text: 保存：正在打开章节… · 连接：协作服务
  - button "问助手"
  - text: · V2 STORYBOARD · 无未保存创作草稿
```

# Test source

```ts
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
  100 |         .getByRole('button', { name: new RegExp(boardTitle) }).click();
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
  154 |     await operation.getByRole('checkbox', { name: CONSENT, exact: true }).scrollIntoViewIfNeeded();
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
> 187 |     await expect(page.getByLabel('画面描述', { exact: true })).toHaveValue(FIRST);
      |                                                            ^ Error: expect(locator).toHaveValue(expected) failed
  188 |     await page.getByLabel('画面描述', { exact: true }).scrollIntoViewIfNeeded();
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
  201 |     expect(await exact(await request.get(ownerPath, { headers }), 200)).toEqual(committed);
  202 |     const reused = await request.post(adoptionPath, { headers, data: { ...originalRequest, expected_digest: 'f'.repeat(64) } });
  203 |     expect(reused.status()).toBe(409);
  204 |     expect((await reused.json()).detail.code).toBe('PROMPT_ADOPTION_REQUEST_REUSED');
  205 |     expect(await exact(await request.get(ownerPath, { headers }), 200)).toEqual(committed);
  206 | 
  207 |     // A real page reload and existing product navigation must reconstruct the
  208 |     // owner state and pinned source. No React state or localStorage is injected.
  209 |     await enterProject();
  210 |     await openBoard();
  211 |     await page.locator('.creative-shot-card').first().click();
  212 |     await expect(page.getByLabel('画面描述', { exact: true })).toHaveValue(FIRST);
  213 |     const reopenedPin = await pin();
  214 |     await expect(reopenedPin).toContainText(source.family_id);
  215 |     await expect(reopenedPin).toContainText(`${source.asset_id} · r1`);
  216 |     await expect(reopenedPin).toContainText(body.digest);
  217 |     await expect(reopenedPin).toContainText('仍然生效');
  218 |     const reopened = await exact(await request.get(ownerPath, { headers }), 200);
  219 |     expect(reopened).toEqual(committed);
  220 |     expect(calls.filter(call => call.method === 'POST' && call.path === adoptionPath)).toHaveLength(1);
  221 |     await reopenedPin.scrollIntoViewIfNeeded();
  222 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-reopened-pin.png'), fullPage: true });
  223 | 
  224 |     // Advancing the source family cannot silently repin this historical shot.
  225 |     await page.getByRole('button', { name: '返回经典工作区', exact: true }).click();
  226 |     await page.getByRole('tab', { name: '图片', exact: true }).click();
  227 |     await openPromptWorkspace(page);
  228 |     await promptLibrary(page).getByRole('button', { name: /IMAGE/ }).filter({ hasText: source.family_id.slice(0, 8) }).click();
  229 |     await page.getByLabel('正文', { exact: true }).fill(NEWER);
  230 |     const revising = page.waitForResponse(response => new URL(response.url()).pathname === `${studio}/prompts/${source.family_id}/revisions`
  231 |       && response.request().method() === 'POST');
  232 |     await page.getByRole('button', { name: '保存新版本', exact: true }).click();
  233 |     expect((await revising).status()).toBe(201);
  234 |     await expect(page.locator('.prompt-status')).toContainText('已保存');
  235 |     await openBoard();
  236 |     const historicalPin = await pin();
  237 |     await expect(historicalPin).toContainText(`${source.asset_id} · r1`);
  238 |     await expect(historicalPin).toContainText(body.digest);
  239 |     await expect(historicalPin).toContainText('存在更新版本，需要重新采用');
  240 |     expect(await exact(await request.get(ownerPath, { headers }), 200)).toEqual(committed);
  241 |     await historicalPin.scrollIntoViewIfNeeded();
  242 |     await page.screenshot({ path: info.outputPath('real-ui-adoption-historical-source-pin.png'), fullPage: true });
  243 |     const geometry = await page.evaluate(() => ({ width: innerWidth,
  244 |       scrollWidth: document.documentElement.scrollWidth,
  245 |       headerHeight: document.querySelector('.global-header')!.getBoundingClientRect().height }));
  246 |     expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width);
  247 |     expect(geometry.headerHeight).toBe(56);
  248 |     expect(errors).toEqual([]);
  249 |     expect(calls.filter(call => !['GET', 'HEAD', 'OPTIONS'].includes(call.method)
  250 |       && /\/(dispatch|generate|graph-runs|media\/tasks|jobs)(\/|$)/.test(call.path))).toEqual([]);
  251 |     await info.attach('redacted-original-ui-adoption', { body: JSON.stringify({ isolated_acceptance: true,
  252 |       production_literal_gate: false, response_mocks: false, ui_button_post_status: 200,
  253 |       request: originalRequest, receipt, owner_before: before, owner_committed: committed,
  254 |       owner_reopened: reopened, source_family_advanced_without_repin: true, same_request_replayed_without_revision: true,
  255 |       declared_binding_verification: 'write-time observation; not current dependency liveness',
  256 |       model_execution: 'NOT_REQUESTED', model_counter: 'NOT_INSTRUMENTED', geometry, calls }), contentType: 'application/json' });
  257 |   } finally {
  258 |     if (projectId) {
  259 |       const cleanup = await request.delete(`${admin}/projects/${projectId}`, { headers });
  260 |       expect(cleanup.status(), await cleanup.text()).toBe(204);
  261 |     }
  262 |   }
  263 | });
  264 | 
```