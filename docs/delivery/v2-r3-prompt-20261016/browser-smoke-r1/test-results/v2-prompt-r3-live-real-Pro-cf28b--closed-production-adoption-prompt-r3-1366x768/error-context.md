# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-prompt-r3-live.spec.ts >> real Prompt authoring, immutable revision, browser HTTP tombstone, and closed production adoption
- Location: tests\e2e\v2-prompt-r3-live.spec.ts:7:1

# Error details

```
Error: expect(received).toBe(expected) // Object.is equality

Expected: 404
Received: 200
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
    - generic [ref=e74]: 项目：Prompt R3 浏览器 prompt-r3-1366x768
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
          - generic "创作意图与推荐布局" [ref=e86] [cursor=pointer]
          - option "空白" [selected]
          - option "文本"
          - option "图片"
          - option "视频"
          - option "声音"
          - option "剪辑"
          - option "混合"
        - group [ref=e87]:
          - generic "项目存储" [ref=e88] [cursor=pointer]
    - generic [ref=e90]:
      - generic "独立工作区内容" [ref=e91]:
        - button "创作开始" [ref=e92] [cursor=pointer]
        - button "任务中心" [ref=e93] [cursor=pointer]
        - button "素材工作区" [pressed] [ref=e94] [cursor=pointer]
        - button "创作图" [ref=e95] [cursor=pointer]
        - button "制作操作" [ref=e96] [cursor=pointer]
        - region "界面模式" [ref=e97]:
          - heading "界面模式" [level=3] [ref=e98]
          - radiogroup "界面模式选择" [ref=e99]:
            - radio "新手模式" [ref=e100] [cursor=pointer]
            - radio "专业模式" [checked] [disabled] [ref=e101]
          - paragraph [ref=e102]: 新手模式与专业模式共用同一份项目、素材、任务与图谱数据；切换只改变界面呈现，不会转换、复制或删除任何内容。
      - generic [ref=e103]:
        - heading "Prompt 工作台" [level=2] [ref=e105]
        - paragraph [ref=e106]: 在这里创建和修订手写 Prompt。保存只会新增一个不可变修订，不会覆盖旧版本； 这里不会调用任何模型，也不会因为输入而自动创建内容。
        - generic [ref=e107]:
          - region "Prompt 列表" [ref=e108]:
            - generic [ref=e109]:
              - button "新建 Prompt" [ref=e110] [cursor=pointer]
              - button "重新读取" [ref=e111] [cursor=pointer]
            - generic [ref=e112]:
              - generic [ref=e113]: 搜索
              - searchbox "搜索" [ref=e114]
              - generic [ref=e115]: 用途
              - combobox "用途" [ref=e116]:
                - option "全部" [selected]
                - option "IMAGE"
                - option "VIDEO"
                - option "AUDIO"
                - option "TEXT"
              - generic [ref=e117]: 状态
              - combobox "状态" [ref=e118]:
                - option "全部" [selected]
                - option "草稿"
                - option "已审核"
            - list [ref=e119]:
              - listitem [ref=e120]:
                - button "IMAGE · 7c9136e4 · 修订 1 草稿" [active] [ref=e121] [cursor=pointer]:
                  - generic [ref=e122]: IMAGE · 7c9136e4 · 修订 1
                  - generic [ref=e123]: 草稿
          - generic [ref=e125]:
            - region "Prompt 编辑器" [ref=e126]:
              - status [ref=e127]: 已保存（服务器已确认）
              - status [ref=e128]: 服务器上这一修订的正文状态是「正文已删除」， 下方显示的内容**不是**完整正文，编辑前请先核对。
              - text: 正文
              - textbox "正文" [ref=e129]: 私有 Prompt 第二版 保留原始换行 🎬
              - paragraph [ref=e130]: 按 UTF-8 字节计最长 64 KiB。不会自动去除空格、换行或 emoji。
              - text: Negative Prompt
              - textbox "Negative Prompt" [ref=e131]
              - generic [ref=e132]:
                - generic [ref=e133]:
                  - generic [ref=e134]: 用途
                  - combobox "用途" [ref=e135]:
                    - option "IMAGE" [selected]
                    - option "VIDEO"
                    - option "AUDIO"
                    - option "TEXT"
                - generic [ref=e136]:
                  - generic [ref=e137]: 模型偏好
                  - textbox "模型偏好" [ref=e138]
                - generic [ref=e139]:
                  - generic [ref=e140]: Seed
                  - textbox "Seed" [ref=e141]
              - text: 参数（JSON，不会执行）
              - textbox "参数（JSON，不会执行）" [ref=e142]
              - group "引用绑定（逗号或空格分隔 ID）" [ref=e143]:
                - generic [ref=e145]: 角色 ID
                - textbox "角色 ID" [ref=e146]
                - generic [ref=e147]: 场景 ID
                - textbox "场景 ID" [ref=e148]
                - generic [ref=e149]: 镜头 ID
                - textbox "镜头 ID" [ref=e150]
                - generic [ref=e151]: 参考素材 ID
                - textbox "参考素材 ID" [ref=e152]
              - text: 修改备注
              - textbox "修改备注" [ref=e153]
              - text: 修改原因
              - textbox "修改原因" [ref=e154]
              - generic [ref=e155]:
                - button "保存新版本" [disabled] [ref=e156]
                - button "放弃本地修改" [ref=e157] [cursor=pointer]
              - generic [ref=e158]:
                - term [ref=e159]: 家族
                - definition [ref=e160]: 7c9136e4-6ca8-42ae-b2ef-5955d4803788
                - term [ref=e161]: 基准修订
                - definition [ref=e162]: "2"
                - term [ref=e163]: 基准资产
                - definition [ref=e164]: 74a4e6bb-6214-4262-9467-bff18081f008
                - term [ref=e165]: 请求标识
                - definition [ref=e166]: （未提交）
            - region "版本历史" [ref=e167]:
              - heading "版本历史" [level=3] [ref=e168]
              - status [ref=e169]: 这个家族的修订链**不完整**（有删除、缺失或重复的修订）。 下面显示的不是一段可信的完整历史，请不要把某一版当作权威最新版。
              - list [ref=e170]:
                - listitem [ref=e171]:
                  - generic [ref=e172]: 修订 2
                  - generic [ref=e173]: 当前
                  - generic [ref=e174]: 已删除 / 不可读
                  - code [ref=e175]: 74a4e6bb
                - listitem [ref=e176]:
                  - generic [ref=e177]: 修订 1
                  - code [ref=e178]: 9d87330f
              - list [ref=e179]:
                - listitem [ref=e180]: REVISION_UNAVAILABLE asset_id=74a4e6bb-6214-4262-9467-bff18081f008 detail=asset is deleted or no longer readable
              - heading "版本比较" [level=3] [ref=e181]
              - generic [ref=e182]:
                - generic [ref=e183]: 对比旧版
                - combobox "对比旧版" [ref=e184]:
                  - option "修订 1" [selected]
                  - option "修订 2（不可读）"
                - generic [ref=e185]: 与新版
                - combobox "与新版" [ref=e186]:
                  - option "修订 1"
                  - option "修订 2" [selected]
                - button "比较正文" [ref=e187] [cursor=pointer]
      - generic [ref=e188]:
        - heading "独立素材工作区" [level=2] [ref=e190]
        - paragraph [ref=e191]: 无需小说、章节或模型，导入素材即可保存和导出。
        - paragraph [ref=e192]: 上传会保存文件，并记录“外部导入”；许可默认未指定，可在来源声明中补充。下载原始文件保留原格式，不进行重新编码。
        - generic [ref=e193]: 手工导入可用 · 不需要模型
      - generic [ref=e194]:
        - generic [ref=e195]:
          - heading "资产库" [level=2] [ref=e196]
          - button "上传资产" [ref=e197] [cursor=pointer]
        - status [ref=e201]:
          - strong [ref=e202]: 暂无资产
          - paragraph [ref=e203]: 上传图片或其他创作素材。
        - generic [ref=e204]:
          - generic [ref=e205]:
            - text: 查找资产
            - searchbox "查找资产" [ref=e206]
          - generic [ref=e207]:
            - text: 类型筛选
            - combobox "类型筛选" [ref=e208]:
              - option "全部" [selected]
              - option "图片"
              - option "视频"
              - option "音频"
          - generic [ref=e209]: 0 项资产
          - button "回收站" [ref=e210] [cursor=pointer]
        - paragraph [ref=e211]: 删除后原素材进入回收站，可恢复。已绑定的参考需重新审核后才能参与检索。
      - generic [ref=e213]:
        - generic [ref=e214]:
          - heading "素材浏览器" [level=2] [ref=e215]
          - generic [ref=e216]:
            - button "网格" [pressed] [ref=e217] [cursor=pointer]
            - button "列表" [ref=e218] [cursor=pointer]
            - button "重新读取素材" [ref=e219] [cursor=pointer]
        - form "素材筛选" [ref=e220]:
          - generic [ref=e221]:
            - generic [ref=e222]: 搜索素材
            - searchbox "搜索素材" [ref=e223]
          - generic [ref=e224]:
            - generic [ref=e225]: 媒体种类
            - combobox "媒体种类" [ref=e226]:
              - option "全部（0）" [selected]
              - option "图片（0）"
              - option "视频（0）"
              - option "音频（0）"
              - option "未核实（0）"
          - generic [ref=e227]:
            - generic [ref=e228]: 用途标签
            - combobox "用途标签" [ref=e229]:
              - option "全部" [selected]
              - option "角色（0）"
              - option "环境（0）"
              - option "道具（0）"
              - option "未打标签（0）"
          - generic [ref=e230]:
            - generic [ref=e231]: 审核标记
            - combobox "审核标记" [ref=e232]:
              - option "全部" [selected]
              - option "无审核标记（0）"
              - option "待审核草稿（0）"
              - option "已批准（0）"
              - option "已驳回（0）"
          - generic [ref=e233]:
            - generic [ref=e234]: 创建时间
            - combobox "创建时间" [ref=e235]:
              - option "全部" [selected]
              - option "未记录时间（0）"
              - option "今天（0）"
              - option "近 7 天（0）"
              - option "近 30 天（0）"
              - option "更早（0）"
          - generic [ref=e236]:
            - generic [ref=e237]: 引用情况
            - combobox "引用情况" [ref=e238]:
              - option "全部" [selected]
              - option "已被引用（0）"
              - option "未被引用（0）"
              - option "引用情况未核实（0）"
          - button "清除筛选" [disabled] [ref=e240]
          - paragraph [ref=e241]: 搜索只匹配已读取的元数据（文件名、类型、标签、审核标记、引用摘要）， 不会扫描磁盘、不会打开未授权内容。
          - paragraph [ref=e242]: 标记为 角色 / 环境 / 道具 只是作者用途标签， 不改变素材的媒体种类（图片 / 视频 / 音频）。
        - status [ref=e243]:
          - strong [ref=e244]: 此项目暂无素材
          - paragraph [ref=e245]: 此项目当前没有可读取的素材。
        - generic [ref=e246]:
          - generic [ref=e247]:
            - generic [ref=e248]:
              - status [ref=e249]: 显示 0 / 0 条。只显示已读取的前若干条；继续加载会再读取下一页，绝不一次拉取全部高清素材。
              - generic [ref=e250]:
                - generic [ref=e251]: 每页条数
                - combobox "每页条数" [ref=e252]:
                  - option "8 条"
                  - option "24 条" [selected]
                  - option "48 条"
                  - option "96 条"
            - generic [ref=e253]:
              - list "素材列表"
              - status [ref=e254]: 当前筛选没有匹配的素材；已读取的素材仍然保留。
          - region "素材详情" [ref=e256]:
            - status [ref=e257]:
              - strong [ref=e258]: 未选择素材
              - paragraph [ref=e259]: 从素材网格或列表选择一项，才会按需读取它的版本、来源与引用。
        - paragraph [ref=e260]: 缩略图按需读取（缩略图只在需要时按原下载接口读取，不预取整库。）。 引用关系当前不可读，引用情况显示为未核实，不会当作"未被引用"。
        - paragraph [ref=e261]: 新的来源版本只显示差异；只有你明确选择才会更新绑定，绝不自动更新所有任务 / 镜头 / 片段。
    - button "收起侧栏" [expanded] [ref=e262] [cursor=pointer]
    - complementary [ref=e266]:
      - separator "调整检查面板宽度" [ref=e267]
      - generic [ref=e268]:
        - generic [ref=e269]: 创作辅助
        - button "收起侧栏" [ref=e270] [cursor=pointer]
      - region "资产检查面板" [ref=e274]:
        - generic [ref=e275]: Inspector
        - status [ref=e276]:
          - strong [ref=e277]: 未选择资产
          - paragraph [ref=e278]: 从资产网格选择一个项目以查看真实预览和元数据。
  - contentinfo [ref=e279]:
    - text: 已保存 · 独立素材 · 模型调用记录见运行回执
    - button "问助手" [ref=e281] [cursor=pointer]
```

# Test source

```ts
  15  |   });
  16  |   const exact = async (response: APIResponse, status: number) => {
  17  |     expect(response.status(), await response.text()).toBe(status); return response.json();
  18  |   };
  19  |   const admin = '/api/collaboration/admin/workspaces/workspace-a';
  20  |   let headers: Record<string, string> = { 'X-Session-Token': token };
  21  |   let projectId = '';
  22  |   const posts = countPromptPosts(page);
  23  |   try {
  24  |     const project = await exact(await request.post(`${admin}/projects`, { headers,
  25  |       data: { title: `Prompt R3 浏览器 ${info.project.name}`, genre: '' } }), 201);
  26  |     projectId = project.id;
  27  |     const base = `/api/projects/${encodeURIComponent(projectId)}/studio`;
  28  |     const navigation = await exact(await request.get(`${admin}/navigation`, { headers }), 200);
  29  |     const scope = navigation.eligible_paths.find((value: { project_id: string }) => value.project_id === projectId);
  30  |     expect(scope).toBeTruthy(); headers = { ...headers, 'X-Branch-ID': scope.branch_id };
  31  |     await exact(await request.post(`${base}/activate`, { headers }), 200);
  32  |     await page.goto('/');
  33  |     await page.getByText('连接已有创作空间', { exact: true }).click();
  34  |     await page.getByLabel('访问凭证', { exact: true }).fill(token);
  35  |     await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  36  |     await page.getByRole('button', { name: '我的创作空间', exact: true }).click();
  37  |     await page.getByRole('button', { name: new RegExp(`Prompt R3 浏览器 ${info.project.name}`) }).click();
  38  |     await openPromptWorkspace(page);
  39  |     await page.getByRole('button', { name: '新建 Prompt', exact: true }).click();
  40  |     const editor = page.getByLabel('正文', { exact: true });
  41  |     await editor.fill(TEXT1);
  42  |     expect(posts.value()).toBe(0);
  43  |     const creating = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/prompts` && response.request().method() === 'POST');
  44  |     await page.getByRole('button', { name: '保存为新 Prompt', exact: true }).click();
  45  |     const createdResponse = await creating;
  46  |     expect(createdResponse.status(), await createdResponse.text()).toBe(201);
  47  |     const first = await createdResponse.json();
  48  |     await expect(page.locator('.prompt-status')).toContainText('已保存');
  49  |     await promptLibrary(page).getByRole('button', { name: /IMAGE/ }).first().click();
  50  |     await expect(editor).toHaveValue(TEXT1);
  51  |     const firstBody = `${base}/prompts/${first.family_id}/revisions/${first.asset_id}/body`;
  52  |     expect((await exact(await request.get(firstBody, { headers }), 200)).value).toBe(TEXT1);
  53  |     await editor.fill(TEXT2);
  54  |     const revising = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/prompts/${first.family_id}/revisions` && response.request().method() === 'POST');
  55  |     await page.getByRole('button', { name: '保存新版本', exact: true }).click();
  56  |     const revisedResponse = await revising;
  57  |     expect(revisedResponse.status(), await revisedResponse.text()).toBe(201);
  58  |     const second = await revisedResponse.json();
  59  |     expect(second.family_id).toBe(first.family_id); expect(second.revision).toBe(2);
  60  |     expect(second.asset_id).not.toBe(first.asset_id);
  61  |     expect(posts.value()).toBe(2);
  62  |     const secondBody = `${base}/prompts/${second.family_id}/revisions/${second.asset_id}/body`;
  63  |     expect((await exact(await request.get(firstBody, { headers }), 200)).value).toBe(TEXT1);
  64  |     expect((await exact(await request.get(secondBody, { headers }), 200)).value).toBe(TEXT2);
  65  |     await page.getByRole('button', { name: '比较正文', exact: true }).click();
  66  |     await expect(page.locator('.prompt-diff table')).toContainText('第一版');
  67  |     await expect(page.locator('.prompt-diff table')).toContainText('第二版');
  68  |     await page.screenshot({ path: info.outputPath('real-private-prompt-two-revisions.png'), fullPage: true });
  69  | 
  70  |     // The actual production route remains closed. Build its real source and
  71  |     // target through their original routes; never replace or enable the gate.
  72  |     await exact(await request.post(`${base}/prompts/${second.family_id}/revisions/${second.asset_id}/approve`,
  73  |       { headers, params: { expected_version: second.asset_version } }), 200);
  74  |     const creative = `/api/novels/${projectId}/experimental/creative/documents`;
  75  |     const script = await exact(await request.post(creative, { headers, data: { mode: 'SCREENPLAY',
  76  |       title: 'Production gate target', source_independent: true,
  77  |       scenes: [{ id: 'real-scene', sequence: 1, heading: 'INT. ROOM - DAY', action: 'A visitor arrives.' }] } }), 201);
  78  |     const board = await exact(await request.post(`${creative}/${script.id}/derive`, { headers,
  79  |       data: { expected_version: script.version, mode: 'STORYBOARD', title: 'Gate target', shot_policy: 'SCENE' } }), 201);
  80  |     const target = await exact(await request.get(`${base}/documents/${board.id}/prompt-adoption`, { headers }), 200);
  81  |     const source = await exact(await request.get(secondBody, { headers }), 200);
  82  |     const refusal = await request.post(`${base}/documents/${board.id}/shots/${board.shots[0].id}/prompt-adoption`, { headers,
  83  |       data: { shot_id: board.shots[0].id, family_id: second.family_id, asset_id: second.asset_id,
  84  |         revision: 2, expected_digest: source.digest, expected_version: target.version,
  85  |         expected_digest_target: target.digest, request_id: `closed-${info.project.name}` } });
  86  |     expect(refusal.status()).toBe(503);
  87  |     expect((await refusal.json()).detail.code).toBe('PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED');
  88  |     expect((await exact(await request.get(`${creative}/${board.id}`, { headers }), 200)).version).toBe(board.version);
  89  | 
  90  |     // There is no Prompt delete button in the shipped editor. This is an
  91  |     // explicitly authorized real browser HTTP action, followed by rendered UI
  92  |     // history verification; it is not claimed as a delete-button workflow.
  93  |     const liveAsset = await exact(await request.get(`${base}/assets/${second.asset_id}`, { headers }), 200);
  94  |     const deleted = await page.evaluate(async ({ url, headers }) => {
  95  |       const response = await fetch(url, { method: 'DELETE', headers });
  96  |       return { status: response.status, body: await response.json() };
  97  |     }, { url: `${base}/assets/${second.asset_id}?expected_version=${liveAsset.version}`, headers });
  98  |     expect(deleted.status).toBe(200); expect(deleted.body.deleted_at).toBeTruthy();
  99  |     expect(deleted.body.version).toBe(liveAsset.version + 1);
  100 |     expect(JSON.stringify(deleted.body)).not.toContain('_owner_actor_id');
  101 |     const tombstone = await exact(await request.get(secondBody, { headers }), 200);
  102 |     expect(tombstone).toMatchObject({ state: 'DELETED', value: null, digest: null, available: false, verified: false });
  103 |     expect(JSON.stringify(tombstone)).not.toContain(TEXT2);
  104 |     const detail = await exact(await request.get(`${base}/prompts/${second.family_id}`, { headers }), 200);
  105 |     expect(detail.versions.find((value: { asset_id: string }) => value.asset_id === second.asset_id).available).toBe(false);
  106 |     await promptLibrary(page).getByRole('button', { name: '重新读取', exact: true }).click();
  107 |     await promptLibrary(page).getByRole('button', { name: /IMAGE/ }).first().click();
  108 |     await expect(page.getByRole('region', { name: '版本历史' })).toContainText('已删除 / 不可读');
  109 |     await page.screenshot({ path: info.outputPath('real-private-prompt-tombstone-history.png'), fullPage: true });
  110 |     const repeat = await exact(await request.delete(`${base}/assets/${second.asset_id}`, { headers,
  111 |       params: { expected_version: deleted.body.version } }), 200);
  112 |     expect(repeat.version).toBe(deleted.body.version);
  113 |     const restored = await request.post(`${base}/assets/${second.asset_id}/restore`, { headers,
  114 |       data: { expected_version: deleted.body.version } });
> 115 |     expect(restored.status()).toBe(404); expect((await restored.json()).detail.code).toBe('EXPERIMENTAL_NOT_FOUND');
      |                               ^ Error: expect(received).toBe(expected) // Object.is equality
  116 |     const geometry = await page.evaluate(() => ({ width: innerWidth,
  117 |       scrollWidth: document.documentElement.scrollWidth, headerHeight: document.querySelector('.global-header')!.getBoundingClientRect().height }));
  118 |     expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width); expect(geometry.headerHeight).toBe(56);
  119 |     expect(errors).toEqual([]);
  120 |     expect(calls.filter(value => !['GET', 'HEAD', 'OPTIONS'].includes(value.method)
  121 |       && /\/(dispatch|generate|graph-runs|media\/tasks|jobs)(\/|$)/.test(value.path))).toEqual([]);
  122 |     await info.attach('redacted-real-browser-evidence', { body: JSON.stringify({ production_gate: false,
  123 |       production_adoption_status: 503, ui_authoring: true, deletion_transport: 'real browser HTTP; no delete UI exists',
  124 |       real_persistence: true, response_mocks: false, model_calls_requested: false, geometry, calls }), contentType: 'application/json' });
  125 |   } finally {
  126 |     posts.dispose();
  127 |     if (projectId) {
  128 |       const cleanup = await request.delete(`${admin}/projects/${projectId}`, { headers });
  129 |       expect(cleanup.status(), await cleanup.text()).toBe(204);
  130 |     }
  131 |   }
  132 | });
  133 | 
```