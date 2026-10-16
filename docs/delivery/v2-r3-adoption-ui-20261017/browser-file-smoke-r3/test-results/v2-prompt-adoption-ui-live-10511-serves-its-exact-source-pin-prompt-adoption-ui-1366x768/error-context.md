# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-prompt-adoption-ui-live.spec.ts >> isolated original button commits bound Prompt and reload preserves its exact source pin
- Location: tests\e2e\v2-prompt-adoption-ui-live.spec.ts:19:1

# Error details

```
TimeoutError: locator.selectOption: Timeout 25000ms exceeded.
Call log:
  - waiting for getByRole('region', { name: 'Prompt 采用操作', exact: true }).getByLabel('Prompt 来源家族', { exact: true })

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
    - generic [ref=e74]: 小说：采用 UI 验收 prompt-adoption-ui-1366x768
    - generic [ref=e75]: /
    - generic [ref=e76]: 故事线：Default Storyline
    - generic [ref=e77]: /
    - generic [ref=e78]: 创作分支：main
  - main [ref=e79]:
    - complementary [ref=e80]:
      - generic "资产浏览器" [ref=e81]:
        - generic [ref=e82]:
          - generic [ref=e83]: Asset Browser
          - heading "创作资产" [level=2] [ref=e84]
          - button "返回经典工作区" [ref=e85] [cursor=pointer]
        - region "创作文档" [ref=e86]:
          - heading "当前阶段文档" [level=3] [ref=e87]
          - button "真实分镜 prompt-adoption-ui-1366x768 v1 · 1 场景" [pressed] [ref=e88] [cursor=pointer]:
            - strong [ref=e89]: 真实分镜 prompt-adoption-ui-1366x768
            - generic [ref=e90]: v1 · 1 场景
        - generic "资产类别" [ref=e91]:
          - button "世界 World" [ref=e92] [cursor=pointer]:
            - generic [ref=e96]:
              - text: 世界
              - generic [ref=e97]: World
          - button "人物 Character" [ref=e98] [cursor=pointer]:
            - generic [ref=e104]:
              - text: 人物
              - generic [ref=e105]: Character
          - button "场景 Scene" [pressed] [ref=e106] [cursor=pointer]:
            - generic [ref=e112]:
              - text: 场景
              - generic [ref=e113]: Scene
          - button "镜头 Shot" [ref=e114] [cursor=pointer]:
            - generic [ref=e118]:
              - text: 镜头
              - generic [ref=e119]: Shot
          - button "音频 Audio" [ref=e120] [cursor=pointer]:
            - generic [ref=e125]:
              - text: 音频
              - generic [ref=e126]: Audio
          - button "视频 Video" [ref=e127] [cursor=pointer]:
            - generic [ref=e130]:
              - text: 视频
              - generic [ref=e131]: Video
        - generic [ref=e132]:
          - generic [ref=e133]: 筛选资产
          - searchbox "筛选资产" [ref=e134]
        - generic "Scene 资产" [ref=e135]:
          - button "INT. ROOM - DAY 场景 1" [ref=e136] [cursor=pointer]:
            - strong [ref=e137]: INT. ROOM - DAY
            - generic [ref=e138]: 场景 1
    - generic [ref=e140]:
      - navigation "项目创作阶段" [ref=e141]:
        - generic [ref=e142]:
          - text: 叙事制作 · V2
          - generic [ref=e143]: 实验功能
        - tablist "创作模式" [ref=e144]:
          - tab "小说 Novel · 0" [ref=e145] [cursor=pointer]:
            - generic [ref=e148]:
              - strong [ref=e149]: 小说
              - generic [ref=e150]: Novel · 0
          - tab "剧本 Screenplay · 1" [ref=e151] [cursor=pointer]:
            - generic [ref=e157]:
              - strong [ref=e158]: 剧本
              - generic [ref=e159]: Screenplay · 1
          - tab "导演 Director · 0" [ref=e160] [cursor=pointer]:
            - generic [ref=e164]:
              - strong [ref=e165]: 导演
              - generic [ref=e166]: Director · 0
          - tab "分镜 Storyboard · 1" [selected] [ref=e167] [cursor=pointer]:
            - generic [ref=e172]:
              - strong [ref=e173]: 分镜
              - generic [ref=e174]: Storyboard · 1
          - tab "制作 Production · 0" [ref=e175] [cursor=pointer]:
            - generic [ref=e178]:
              - strong [ref=e179]: 制作
              - generic [ref=e180]: Production · 0
      - tabpanel "分镜 Storyboard · 1" [ref=e181]:
        - region "创作画布" [ref=e182]:
          - generic [ref=e183]:
            - generic [ref=e184]:
              - generic [ref=e185]: Creative Canvas
              - heading "真实分镜 prompt-adoption-ui-1366x768" [level=2] [ref=e186]
              - generic [ref=e187]: 已保存 · v1
            - generic [ref=e188]:
              - button "新建文档" [ref=e189] [cursor=pointer]
              - button "保存草稿" [disabled] [ref=e193]
              - button "建立制作计划" [ref=e198] [cursor=pointer]
              - button "导出" [ref=e199] [cursor=pointer]
              - button "历史" [ref=e203] [cursor=pointer]
          - group "创作文档内容" [ref=e208]:
            - generic [ref=e210]:
              - generic [ref=e211]: 文档标题
              - textbox "文档标题" [ref=e212]: 真实分镜 prompt-adoption-ui-1366x768
            - generic [ref=e213]: 来源：服务端绑定的创作文档
            - region "项目视觉目标" [ref=e215]:
              - generic [ref=e216]:
                - heading "项目视觉目标" [level=3] [ref=e217]
                - generic [ref=e218]: 尚未设定
              - paragraph [ref=e219]: 导演目标随当前文档版本保存。明确建立分镜草稿时才传递到新文档；修改目标不会自动改写场景或执行媒体。
              - generic [ref=e220]:
                - generic [ref=e221]:
                  - generic [ref=e222]: 视觉风格
                  - textbox "视觉风格" [ref=e223]
                - generic [ref=e224]:
                  - generic [ref=e225]: 整体氛围
                  - textbox "整体氛围" [ref=e226]
              - group [ref=e227]:
                - generic "展开色彩、节奏与参考作品" [ref=e228]
            - generic [ref=e229]:
              - button "添加场景" [ref=e230] [cursor=pointer]
              - button "添加镜头" [ref=e232] [cursor=pointer]
            - generic "场景选择" [ref=e234]:
              - button "SCENE 01 INT. ROOM - DAY" [pressed] [ref=e235] [cursor=pointer]:
                - generic [ref=e236]: SCENE 01
                - strong [ref=e237]: INT. ROOM - DAY
            - region "当前场景" [ref=e238]:
              - generic [ref=e239]:
                - generic [ref=e240]:
                  - generic [ref=e241]: 场景标题
                  - textbox "场景标题" [ref=e242]: INT. ROOM - DAY
                - generic [ref=e243]:
                  - generic [ref=e244]: 场景地点
                  - textbox "场景地点" [ref=e245]
                - generic [ref=e246]:
                  - generic [ref=e247]: 场景时间
                  - textbox "场景时间" [ref=e248]
                - generic [ref=e249]:
                  - generic [ref=e250]: 场景情绪
                  - textbox "场景情绪" [ref=e251]
              - generic [ref=e252]:
                - generic [ref=e253]: 动作与叙事
                - textbox "动作与叙事" [ref=e254]: A visitor arrives.
            - region "分镜画布" [ref=e255]:
              - generic "分镜视图" [ref=e256]:
                - button "镜头卡片" [pressed] [ref=e257] [cursor=pointer]
                - button "镜头列表" [ref=e258] [cursor=pointer]
                - generic [ref=e259]: 1 镜头 · 5 秒
              - article [ref=e261]:
                - button "SHOT 01 5s 填写画面描述 INT. ROOM - DAY · MEDIUM · STATIC" [pressed] [ref=e262] [cursor=pointer]:
                  - generic [ref=e263]:
                    - strong [ref=e264]: SHOT 01
                    - generic [ref=e265]: 5s
                  - paragraph [ref=e266]: 填写画面描述
                  - generic [ref=e267]: INT. ROOM - DAY · MEDIUM · STATIC
                - generic [ref=e268]:
                  - button "前移镜头 1" [disabled] [ref=e269]: 前移
                  - button "后移镜头 1" [disabled] [ref=e272]: 后移
              - region "选中镜头预览" [ref=e275]:
                - heading "SHOT 01 · 创作预览" [level=3] [ref=e276]
                - code [ref=e277]: 7f9aca8d-81f7-4838-8fc3-f4b3f53413b0
                - paragraph [ref=e278]: A visitor arrives.
                - paragraph [ref=e279]: 构图待设定 · EYE_LEVEL · STATIC · 5 秒
                - paragraph [ref=e280]: 角色：未指定 · 情绪：
                - paragraph [ref=e281]: 声音：未指定
                - generic [ref=e282]: 这是作者分镜数据的预览。保存后可在创作图绑定此文档版本；图片生成与人工审核仍分别确认。
              - region "镜头 1 参数" [ref=e283]:
                - heading "镜头 1 · 参数" [level=3] [ref=e284]
                - generic [ref=e285]:
                  - generic [ref=e286]:
                    - generic [ref=e287]: 镜头所属场景
                    - combobox "镜头所属场景" [ref=e288]:
                      - option "INT. ROOM - DAY" [selected]
                  - generic [ref=e289]:
                    - generic [ref=e290]: 镜头时长（秒）
                    - spinbutton "镜头时长（秒）" [ref=e291]: "5"
                  - generic [ref=e292]:
                    - generic [ref=e293]: 镜头景别
                    - textbox "镜头景别" [ref=e294]: MEDIUM
                  - generic [ref=e295]:
                    - generic [ref=e296]: 镜头角度
                    - textbox "镜头角度" [ref=e297]: EYE_LEVEL
                  - generic [ref=e298]:
                    - generic [ref=e299]: 镜头运动
                    - textbox "镜头运动" [ref=e300]: STATIC
                  - generic [ref=e301]:
                    - generic [ref=e302]: 镜头与焦距
                    - textbox "镜头与焦距" [ref=e303]
                  - generic [ref=e304]:
                    - generic [ref=e305]: 光线设计
                    - textbox "光线设计" [ref=e306]
                  - generic [ref=e307]:
                    - generic [ref=e308]: 环境设计
                    - textbox "环境设计" [ref=e309]
                  - generic [ref=e310]:
                    - generic [ref=e311]: 构图
                    - textbox "构图" [ref=e312]
                  - generic [ref=e313]:
                    - generic [ref=e314]: 色彩
                    - textbox "色彩" [ref=e315]
                  - generic [ref=e316]:
                    - generic [ref=e317]: 声音设计
                    - textbox "声音设计" [ref=e318]
                - generic [ref=e319]:
                  - generic [ref=e320]: 画面描述
                  - textbox "画面描述" [ref=e321]
                - generic [ref=e322]:
                  - generic [ref=e323]: 镜头动作
                  - textbox "镜头动作" [ref=e324]: A visitor arrives.
                - generic [ref=e325]:
                  - generic [ref=e326]:
                    - generic [ref=e327]: 镜头角色（用、分隔）
                    - textbox "镜头角色（用、分隔）" [ref=e328]
                  - generic [ref=e329]:
                    - generic [ref=e330]: 镜头情绪
                    - textbox "镜头情绪" [ref=e331]
                - group [ref=e332]:
                  - generic "展开视频生成意图" [ref=e333]
                - group [ref=e334]:
                  - generic "展开镜头连续性与导演来源" [ref=e335]
                  - option "未绑定" [selected]
                  - option "未绑定" [selected]
      - region "制作时间轴" [ref=e336]:
        - generic [ref=e337]:
          - generic [ref=e338]:
            - generic [ref=e339]: Production Timeline
            - heading "制作序列" [level=2] [ref=e340]
          - generic [ref=e341]: 1 段 · 5s
          - generic [ref=e342]: 结构化计划 · 尚未渲染媒体
        - list [ref=e343]:
          - listitem [ref=e344]:
            - button "0s → 5s 镜头 1 5s" [ref=e345] [cursor=pointer]:
              - generic [ref=e346]: 0s → 5s
              - strong [ref=e347]: 镜头 1
              - generic [ref=e348]: 5s
    - button "收起侧栏" [expanded] [ref=e349] [cursor=pointer]
    - complementary [ref=e353]:
      - separator "调整检查面板宽度" [ref=e354]
      - generic [ref=e355]:
        - generic [ref=e356]: 创作辅助
        - button "收起侧栏" [ref=e357] [cursor=pointer]
      - generic [ref=e361]:
        - heading "分镜生产检查器" [level=2] [ref=e363]
        - paragraph [ref=e364]: 来源：真实分镜 prompt-adoption-ui-1366x768 · v1。原文档保存、素材审核与生产任务分别操作。
        - button "明确读取已保存创作回执" [ref=e365] [cursor=pointer]
      - button "按需打开镜头工作区" [expanded] [ref=e366] [cursor=pointer]
      - region "分镜工作区" [ref=e367]:
        - generic [ref=e368]:
          - heading "导演与分镜" [level=2] [ref=e369]
          - generic [ref=e370]: 项目 f64cc155-58b5-430e-afa2-d6ebf40c9dad
          - generic [ref=e371]: 文档 4aec825d-ddb1-4fcf-9f7a-54505d0bbdae
          - generic [ref=e372]: 等待原分镜审核
          - button "读取已保存分镜" [ref=e373] [cursor=pointer]
          - button "重新读取" [ref=e374] [cursor=pointer]
        - generic [ref=e375]:
          - region "分镜镜头清单" [ref=e376]:
            - generic [ref=e377]:
              - heading "镜头清单" [level=3] [ref=e378]
              - generic [ref=e379]: 1 个镜头
            - list [ref=e380]:
              - listitem [ref=e381]:
                - button "镜头 1（身份 7f9aca8d-81f7-4838-8fc3-f4b3f53413b0）" [pressed] [ref=e382] [cursor=pointer]:
                  - generic [ref=e383]: SHOT 1
                  - generic [ref=e384]: 7f9aca8d-81f7-4838-8fc3-f4b3f53413b0
                  - generic [ref=e385]: A visitor arrives.
                  - generic [ref=e386]:
                    - generic [ref=e387]: 时长 5 秒
                    - generic [ref=e388]: 景别 MEDIUM
                    - generic [ref=e389]: 机位 EYE_LEVEL
                    - generic [ref=e390]: 运动 STATIC
                  - generic [ref=e391]:
                    - generic [ref=e392]: v1
                    - generic [ref=e393]: 尚无正式绑定
                    - generic [ref=e394]: 来源有变化（1 条证据）
                  - generic [ref=e395]: 下一步：准备图片请求草稿（不派发）
                - status [ref=e396]: DIRECTOR_SOURCE_UNAVAILABLE：原分镜记下的上游文档 7e44e189-1b03-44d1-aec3-bd1cc99138d5 目前读不到，无法确认它是否仍然是同一版本。
                - generic [ref=e397]:
                  - generic [ref=e398]: 位置 1（显示序号 1）
                  - button "移到最前" [disabled] [ref=e399]
                  - button "上移" [disabled] [ref=e400]
                  - button "下移" [disabled] [ref=e401]
                  - button "移到最后" [disabled] [ref=e402]
          - generic [ref=e403]:
            - generic [ref=e404]:
              - heading "镜头详情 · SHOT 1" [level=2] [ref=e406]
              - generic [ref=e407]:
                - generic [ref=e408]: 身份 7f9aca8d-81f7-4838-8fc3-f4b3f53413b0
                - generic [ref=e409]: 显示序号 1
                - generic [ref=e410]: 镜头版本 v1
                - generic [ref=e411]: 未绑定正式图片
                - generic [ref=e412]: 未绑定正式视频
              - generic [ref=e413]:
                - generic [ref=e414]:
                  - term [ref=e415]: 所属场景
                  - definition [ref=e416]: real-ui-scene
                - generic [ref=e417]:
                  - term [ref=e418]: 时长（秒）
                  - definition [ref=e419]: "5"
                - generic [ref=e420]:
                  - term [ref=e421]: 景别
                  - definition [ref=e422]: MEDIUM
                - generic [ref=e423]:
                  - term [ref=e424]: 机位角度
                  - definition [ref=e425]: EYE_LEVEL
                - generic [ref=e426]:
                  - term [ref=e427]: 摄影机运动
                  - definition [ref=e428]: STATIC
                - generic [ref=e429]:
                  - term [ref=e430]: 镜头/焦段
                  - definition [ref=e431]: 原文档未提供
                - generic [ref=e432]:
                  - term [ref=e433]: 构图
                  - definition [ref=e434]: 原文档未提供
                - generic [ref=e435]:
                  - term [ref=e436]: 光线
                  - definition [ref=e437]: 原文档未提供
                - generic [ref=e438]:
                  - term [ref=e439]: 色彩
                  - definition [ref=e440]: 原文档未提供
                - generic [ref=e441]:
                  - term [ref=e442]: 环境
                  - definition [ref=e443]: 原文档未提供
                - generic [ref=e444]:
                  - term [ref=e445]: 音效
                  - definition [ref=e446]: 原文档未提供
                - generic [ref=e447]:
                  - term [ref=e448]: 声音
                  - definition [ref=e449]: 原文档未提供
              - region "原文档证据" [ref=e450]:
                - heading "原文档证据" [level=4] [ref=e451]
                - paragraph [ref=e452]: 这些字段读到了：number、scene_id、duration_seconds、framing。
                - paragraph [ref=e453]: 这些字段原文档没有提供：lighting、characters、director_note_ids、continuity、image_binding、video_binding、audio。
                - group [ref=e454]:
                  - generic "镜头内容摘要（原 owner 的 shot_digest）" [ref=e455]
              - region "相邻镜头" [ref=e456]:
                - heading "相邻镜头" [level=4] [ref=e457]
                - paragraph [ref=e458]: 前一个：这是第一个镜头（边界，不回绕）
                - paragraph [ref=e459]: 后一个：这是最后一个镜头（边界，不回绕）
                - paragraph [ref=e460]: 原文档声明的邻居：前 未声明 · 后 未声明（声明值就是原文档事实，本工作区不改写它）。
              - region "镜头引用" [ref=e461]:
                - heading "引用与一致性要求" [level=4] [ref=e462]
                - paragraph [ref=e463]: 角色：原文档未提供
                - paragraph [ref=e464]: 关联导演备注：原文档未提供
                - paragraph [ref=e465]: 原文档没有声明一致性要求（这里不会替你判断"连续性没问题"）。
              - region "参考比较" [ref=e466]:
                - heading "参考比较" [level=4] [ref=e467]
                - button "只读比较绑定素材与镜头版本" [disabled] [ref=e468]
                - paragraph [ref=e469]: 这个镜头还没有正式绑定的候选素材。
                - list [ref=e470]:
                  - listitem [ref=e471]:
                    - generic [ref=e472]: DIRECTOR_SOURCE_UNAVAILABLE
                    - text: 原分镜记下的上游文档 7e44e189-1b03-44d1-aec3-bd1cc99138d5 目前读不到，无法确认它是否仍然是同一版本。
                    - code [ref=e473]: 7e44e189-1b03-44d1-aec3-bd1cc99138d5 v1
              - region "镜头下一步" [ref=e474]:
                - heading "下一步可做的事" [level=4] [ref=e475]
                - list [ref=e476]:
                  - listitem [ref=e477]: 准备图片请求草稿（不派发）
                  - listitem [ref=e478]: 核对并批准当前分镜版本
                  - listitem [ref=e479]: 准备视频请求草稿（不派发）
                - button "准备图片请求草稿" [ref=e480] [cursor=pointer]
                - button "准备视频请求草稿" [ref=e481] [cursor=pointer]
                - button "准备时间线底稿请求" [ref=e482] [cursor=pointer]
                - paragraph [ref=e483]: 这是一张草稿卡片：不会入队、不会调用模型、不会改写原文档或时间线。
            - button "查看 Prompt 采用来源" [ref=e485] [cursor=pointer]
            - region "Prompt 采用操作" [ref=e486]:
              - button "核对 Prompt 采用条件" [ref=e487] [cursor=pointer]
              - generic [ref=e488]:
                - heading "采用 Prompt 到当前镜头" [level=2] [ref=e490]
                - paragraph [ref=e491]: 采用会替换当前镜头的画面提示词，并使分镜重新等待审核。
                - generic [ref=e492]:
                  - term [ref=e493]: 目标文档
                  - definition [ref=e494]: 4aec825d-ddb1-4fcf-9f7a-54505d0bbdae · v1
                  - term [ref=e495]: 目标镜头
                  - definition [ref=e496]: 7f9aca8d-81f7-4838-8fc3-f4b3f53413b0
                  - term [ref=e497]: 目标摘要
                  - definition [ref=e498]:
                    - code [ref=e499]: 4c39f3c22985c4ea17b4e093ff92f79bfdfccb3292a13764271e030add82424a
                - generic [ref=e500]:
                  - text: Prompt 来源家族
                  - combobox "Prompt 来源家族" [ref=e501]:
                    - option "选择来源家族" [selected]
                    - option "fc0f37a0-e3e6-4ad0-9fa8-ddae574cc11a · r1 · IMAGE"
                - button "读取所选 Prompt 修订" [disabled] [ref=e502]
                - generic [ref=e503]:
                  - checkbox "我已核对来源正文、修订与当前镜头版本，确认替换画面提示词。" [disabled] [ref=e504]
                  - text: 我已核对来源正文、修订与当前镜头版本，确认替换画面提示词。
                - button "采用到当前镜头" [disabled] [ref=e505]
            - generic [ref=e506]:
              - heading "送往…" [level=2] [ref=e508]
              - paragraph [ref=e509]: 这里只形成草稿。目标模块是否执行、何时执行，由拿到这张卡的界面与它自己的 owner 决定；本工作区永远不会替你执行。
              - group "目标模块" [ref=e510]:
                - generic [ref=e512]:
                  - radio "图片候选（IMAGE）" [checked] [ref=e513]
                  - text: 图片候选（IMAGE）
                - generic [ref=e514]:
                  - radio "视频候选（VIDEO）" [ref=e515]
                  - text: 视频候选（VIDEO）
                - generic [ref=e516]:
                  - radio "时间线底稿（TIMELINE）" [ref=e517]
                  - text: 时间线底稿（TIMELINE）
              - button "形成 图片候选 草稿" [ref=e518] [cursor=pointer]
              - status [ref=e519]: 还没有形成草稿。形成后这里会逐条列出目标模块将要引用的原版本。
              - paragraph [ref=e520]: 这是一张草稿卡片：不会入队、不会调用模型、不会改写原文档或时间线。
              - paragraph [ref=e521]: 草稿不包含请求标识、任务标识或执行开关，所以它没有被派发的可能。若目标模块当前不可用，请使用原模块的界面。
              - generic [ref=e522]:
                - generic [ref=e523]: 图片：原图片界面
                - generic [ref=e524]: 视频：原视频界面
                - generic [ref=e525]: 时间线：原时间线界面
                - button "目标模块不可用" [ref=e526] [cursor=pointer]
            - generic [ref=e527]:
              - heading "导演目标" [level=2] [ref=e529]
              - paragraph [ref=e530]: 导演是可选的创作节点，不是其它模块的"核心权威"：这里不改写镜头、不撤销批准，也不会因为改目标就覆盖已经批准的下游结果。
              - status [ref=e531]: 还没有读到导演目标。这里不会编造目标；请先读取导演文档，或使用原导演界面创建。
              - region "AI 建议（待审）" [ref=e532]:
                - heading "AI 建议（待审，与原文档已采用内容分开）" [level=4] [ref=e533]
                - paragraph [ref=e534]: "这些是原 owner 的 `director-proposals` 记录，状态不是\"已批准\"；它们**没有**生效，也不能被这里直接采用。"
                - paragraph [ref=e535]: 没有读到待审建议（或本工作区没有提供读取入口）。
                - button "只读读取导演调度建议" [ref=e536] [cursor=pointer]
            - generic [ref=e537]:
              - button "按需打开导演工作台" [ref=e538] [cursor=pointer]
              - button "按需打开角色与场景圣经" [ref=e539] [cursor=pointer]
      - generic "AI 导演面板" [ref=e541]:
        - generic [ref=e542]:
          - generic [ref=e543]: AI Director
          - heading "导演协作与审核" [level=2] [ref=e544]
        - generic [ref=e545]:
          - heading "从剧本准备导演建议" [level=2] [ref=e547]
          - paragraph [ref=e548]: 本地规则辅助会整理场景调度草案。不会调用模型；采用后新增独立导演文档。
          - generic [ref=e549]:
            - generic [ref=e550]: 导演建议来源剧本
            - combobox "导演建议来源剧本" [ref=e551]:
              - option "选择已保存剧本"
              - option "真实来源剧本 prompt-adoption-ui-1366x768 · v1" [selected]
          - group [ref=e552]:
            - generic "本次导演建议的视觉目标（可选）" [ref=e553] [cursor=pointer]
          - button "准备待审导演建议" [ref=e554] [cursor=pointer]
        - generic [ref=e555]:
          - generic [ref=e556]:
            - heading "建议审核队列" [level=2] [ref=e557]
            - button "刷新" [ref=e558] [cursor=pointer]
          - status [ref=e559]:
            - strong [ref=e560]: 没有待审导演建议
            - paragraph [ref=e561]: 手动编辑始终可用。只有明确核对并采用建议才会创建导演文档。
        - region "本地 AI 环境摘要" [ref=e562]:
          - generic [ref=e563]:
            - heading "本地 AI 环境" [level=2] [ref=e564]
            - generic [ref=e565]: 尚未检测
          - paragraph [ref=e566]: 仅检测运行后端的主机；云端结果不代表你的电脑。
          - status [ref=e567]: 到模型中心先预览检测范围，再确认查找已有服务；常用模型目录需明确选择。
          - paragraph [ref=e568]: 真实推理：NOT_RUN。Windows 实机验收：NOT_RUN。发现模型不会自动启用或加载。
          - generic [ref=e569]:
            - button "打开模型中心" [ref=e570] [cursor=pointer]
            - button "重新读取" [ref=e571] [cursor=pointer]
        - generic [ref=e572]:
          - heading "模型与执行能力" [level=2] [ref=e574]
          - paragraph [ref=e575]: 模型调用需要已配置且可用的 Provider。此工作区不会自动启动模型或渲染音视频。
          - button "打开模型控制中心" [ref=e576] [cursor=pointer]
  - contentinfo [ref=e577]:
    - text: 保存：正在打开章节… · 连接：协作服务
    - button "问助手" [ref=e579] [cursor=pointer]
    - generic [ref=e583]: · V2 STORYBOARD · 无未保存创作草稿
```

# Test source

```ts
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
> 132 |     await operation.getByLabel('Prompt 来源家族', { exact: true }).selectOption(source.family_id);
      |                                                                ^ TimeoutError: locator.selectOption: Timeout 25000ms exceeded.
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
  187 |     await expect(page.getByLabel('画面描述', { exact: true })).toHaveValue(FIRST);
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
```