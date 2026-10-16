# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-director-console-live.spec.ts >> real File Director graph participant saves, reopens and refuses a changed source
- Location: tests\e2e\v2-director-console-live.spec.ts:3:1

# Error details

```
Test timeout of 90000ms exceeded.
```

```
Error: apiRequestContext.delete: Target page, context or browser has been closed
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
    - generic [ref=f1e74]: 项目：导演控制台验收 director-1440x900
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
          - option "空白" [disabled] [selected]
          - option "文本" [disabled]
          - option "图片" [disabled]
          - option "视频" [disabled]
          - option "声音" [disabled]
          - option "剪辑" [disabled]
          - option "混合" [disabled]
        - group [ref=f1e87]:
          - generic "项目存储" [ref=f1e88] [cursor=pointer]
    - generic [ref=f1e90]:
      - generic "独立工作区内容" [ref=f1e91]:
        - button "创作开始" [ref=f1e92] [cursor=pointer]
        - button "任务中心" [ref=f1e93] [cursor=pointer]
        - button "素材工作区" [ref=f1e94] [cursor=pointer]
        - button "创作图" [pressed] [ref=f1e95] [cursor=pointer]
        - button "制作操作" [ref=f1e96] [cursor=pointer]
        - region "界面模式" [ref=f1e97]:
          - heading "界面模式" [level=3] [ref=f1e98]
          - radiogroup "界面模式选择" [ref=f1e99]:
            - radio "新手模式" [ref=f1e100] [cursor=pointer]
            - radio "专业模式" [checked] [disabled] [ref=f1e101]
          - paragraph [ref=f1e102]: 新手模式与专业模式共用同一份项目、素材、任务与图谱数据；切换只改变界面呈现，不会转换、复制或删除任何内容。
      - region "本机图草稿恢复" [ref=f1e103]:
        - status [ref=f1e104]: 本机自动恢复当前仅支持不含外部引用的文本图 v1 / v2。当前图输入只保留在本页；请明确保存到服务端。
      - region "独立创作图编辑器" [ref=f1e105]:
        - generic [ref=f1e106]:
          - heading "创作图 · 手工编排" [level=2] [ref=f1e108]
          - paragraph [ref=f1e109]: 空图和不相连的组件都可以保存。导演备注可选，可随时移除；连接类型由服务端定义。
          - paragraph [ref=f1e110]: 可选本地文字模型节点需单独预览输入并明确确认一次调用。每次运行最多一个文字模型节点，输出必须人工审核；不自动调用、重试或转云端。
          - paragraph [ref=f1e111]: 图片图 v4：资产引用 → 图片参考与权重 → 图片提示词 → 图片生成 → 媒体审核 → 正式素材。各节点可独立编排；最多四个图片生成节点。保存、预览、入队、执行和审核分别操作，真实推理与完整流程验收仍待完成。
          - button "明确读取图片节点目录" [ref=f1e112] [cursor=pointer]
          - button "明确读取视频图节点目录" [ref=f1e113] [cursor=pointer]
          - button "明确读取导演、分镜与视觉制作节点目录" [ref=f1e114] [cursor=pointer]
          - paragraph [ref=f1e115]: 已读取视觉制作扩展：已保存导演与分镜版本 → 镜头提示词 → 风格 → 图片生成；或正式图片 → 超分 → 原媒体审核。控制 Adapter 尚未执行，模型质量验收待完成。
          - generic [ref=f1e116]:
            - button "新建空图" [ref=f1e117] [cursor=pointer]
            - button "刷新创作图目录" [ref=f1e118] [cursor=pointer]
          - generic [ref=f1e119]:
            - text: 已保存创作图
            - combobox "已保存创作图" [ref=f1e120]:
              - option "未选择已保存图" [selected]
              - option "浏览器恢复的文本图 · v1"
          - generic [ref=f1e121]:
            - text: 创作图标题
            - textbox "创作图标题" [ref=f1e122]: 导演控制台来源绑定
          - generic [ref=f1e123]: 尚未保存 · 未保存修改
          - generic [ref=f1e124]:
            - button "保存创作图" [ref=f1e125] [cursor=pointer]
            - button "撤销图编辑" [ref=f1e126] [cursor=pointer]
            - button "重做图编辑" [disabled] [ref=f1e127]
            - button "重新读取创作图" [disabled] [ref=f1e128]
        - region "媒体图版本" [ref=f1e129]:
          - paragraph [ref=f1e130]: 当前图格式：v4。旧图保持原行为，升级只在明确保存后生效，不自动执行。
        - region "添加与连接节点" [ref=f1e131]:
          - generic [ref=f1e132]:
            - text: 节点类型
            - combobox "节点类型" [ref=f1e133]:
              - option "文本输入"
              - option "文本引用"
              - option "资产引用"
              - option "媒体审核入库"
              - option "图片参考与权重"
              - option "图片提示词"
              - option "图片生成（需分别确认）"
              - option "图片风格"
              - option "图片超分（需分别确认）"
              - option "导演节点（已保存文档）" [selected]
              - option "分镜节点（已保存文档）"
              - option "分镜镜头提示词"
          - button "明确读取已保存导演与分镜文档" [ref=f1e134] [cursor=pointer]
          - generic [ref=f1e135]:
            - text: 原创作文档
            - combobox "原创作文档" [ref=f1e136]:
              - option "选择当前已保存版本" [selected]
              - option "有明确视觉方向的导演文档 · v1"
          - paragraph [ref=f1e137]: 只绑定原文档 ID、版本与摘要，不创建副本。文档修改或权限变化后旧绑定不可继续采用；新节点不执行模型、不改写作品。
          - button "添加节点" [disabled] [ref=f1e138]
          - generic [ref=f1e139]:
            - text: 起始输出端口
            - combobox "起始输出端口" [ref=f1e140]:
              - option "选择输出端口" [selected]
          - generic [ref=f1e141]:
            - text: 目标输入端口
            - combobox "目标输入端口" [ref=f1e142]:
              - option "选择输入端口" [selected]
          - button "连接所选端口" [disabled] [ref=f1e143]
        - region "画布操作栏" [ref=f1e144]:
          - region "节点面板" [ref=f1e145]:
            - heading "节点面板" [level=3] [ref=f1e146]
            - generic [ref=f1e147]:
              - generic [ref=f1e148]:
                - generic [ref=f1e149]: 搜索节点
                - searchbox "搜索节点" [ref=f1e150]
              - generic [ref=f1e151]:
                - generic [ref=f1e152]: 节点分类
                - combobox "节点分类" [ref=f1e153]:
                  - option "全部分类" [selected]
                  - option "文本与草稿"
                  - option "资产引用"
                  - option "媒体与时间线"
                  - option "图片图 v4 节点"
                  - option "导演与分镜"
                  - option "视频图 v5 节点"
            - paragraph [ref=f1e154]: 只读现存目录：共 12 个节点定义，当前命中 12 个。分类与检索都只在本机内存中进行，不会因为检索而调用模型。
            - list [ref=f1e155]:
              - listitem [ref=f1e156]:
                - button "文本输入 text_input 可执行 输出 text TEXT 命中 ALL · 定义不调用模型" [ref=f1e157] [cursor=pointer]:
                  - generic [ref=f1e158]:
                    - strong [ref=f1e159]: 文本输入
                    - code [ref=f1e160]: text_input
                    - generic [ref=f1e161]: 可执行
                  - generic [ref=f1e163]:
                    - text: 输出
                    - generic [ref=f1e164]: text
                    - text: TEXT
                  - generic [ref=f1e165]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e166]:
                - button "文本引用 text_reference 可执行 输入 text TEXT · 必填 输出 text TEXT 命中 ALL · 定义不调用模型" [ref=f1e167] [cursor=pointer]:
                  - generic [ref=f1e168]:
                    - strong [ref=f1e169]: 文本引用
                    - code [ref=f1e170]: text_reference
                    - generic [ref=f1e171]: 可执行
                  - generic [ref=f1e172]:
                    - generic [ref=f1e173]:
                      - text: 输入
                      - generic [ref=f1e174]: text
                      - text: TEXT · 必填
                    - generic [ref=f1e175]:
                      - text: 输出
                      - generic [ref=f1e176]: text
                      - text: TEXT
                  - generic [ref=f1e177]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e178]:
                - button "资产引用 asset_reference 可执行 输出 asset ASSET_REF 命中 ALL · 定义不调用模型" [ref=f1e179] [cursor=pointer]:
                  - generic [ref=f1e180]:
                    - strong [ref=f1e181]: 资产引用
                    - code [ref=f1e182]: asset_reference
                    - generic [ref=f1e183]: 可执行
                  - generic [ref=f1e185]:
                    - text: 输出
                    - generic [ref=f1e186]: asset
                    - text: ASSET_REF
                  - generic [ref=f1e187]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e188]:
                - button "媒体审核入库 media_review 可执行 输入 candidate MEDIA_CANDIDATE · 必填 输出 asset ASSET_REF 命中 ALL · 定义不调用模型" [ref=f1e189] [cursor=pointer]:
                  - generic [ref=f1e190]:
                    - strong [ref=f1e191]: 媒体审核入库
                    - code [ref=f1e192]: media_review
                    - generic [ref=f1e193]: 可执行
                  - generic [ref=f1e194]:
                    - generic [ref=f1e195]:
                      - text: 输入
                      - generic [ref=f1e196]: candidate
                      - text: MEDIA_CANDIDATE · 必填
                    - generic [ref=f1e197]:
                      - text: 输出
                      - generic [ref=f1e198]: asset
                      - text: ASSET_REF
                  - generic [ref=f1e199]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e200]:
                - button "图片参考与权重 image_reference 可执行 输入 source_1 ASSET_REF 输入 source_2 ASSET_REF 输入 source_3 ASSET_REF 输入 source_4 ASSET_REF 输入 source_5 ASSET_REF 输出 references IMAGE_REFERENCES 命中 ALL · 定义不调用模型" [ref=f1e201] [cursor=pointer]:
                  - generic [ref=f1e202]:
                    - strong [ref=f1e203]: 图片参考与权重
                    - code [ref=f1e204]: image_reference
                    - generic [ref=f1e205]: 可执行
                  - generic [ref=f1e206]:
                    - generic [ref=f1e207]:
                      - text: 输入
                      - generic [ref=f1e208]: source_1
                      - text: ASSET_REF
                    - generic [ref=f1e209]:
                      - text: 输入
                      - generic [ref=f1e210]: source_2
                      - text: ASSET_REF
                    - generic [ref=f1e211]:
                      - text: 输入
                      - generic [ref=f1e212]: source_3
                      - text: ASSET_REF
                    - generic [ref=f1e213]:
                      - text: 输入
                      - generic [ref=f1e214]: source_4
                      - text: ASSET_REF
                    - generic [ref=f1e215]:
                      - text: 输入
                      - generic [ref=f1e216]: source_5
                      - text: ASSET_REF
                    - generic [ref=f1e217]:
                      - text: 输出
                      - generic [ref=f1e218]: references
                      - text: IMAGE_REFERENCES
                  - generic [ref=f1e219]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e220]:
                - button "图片提示词 image_prompt 可执行 输入 text TEXT 输入 references IMAGE_REFERENCES 输出 prompt IMAGE_PROMPT 命中 ALL · 定义不调用模型" [ref=f1e221] [cursor=pointer]:
                  - generic [ref=f1e222]:
                    - strong [ref=f1e223]: 图片提示词
                    - code [ref=f1e224]: image_prompt
                    - generic [ref=f1e225]: 可执行
                  - generic [ref=f1e226]:
                    - generic [ref=f1e227]:
                      - text: 输入
                      - generic [ref=f1e228]: text
                      - text: TEXT
                    - generic [ref=f1e229]:
                      - text: 输入
                      - generic [ref=f1e230]: references
                      - text: IMAGE_REFERENCES
                    - generic [ref=f1e231]:
                      - text: 输出
                      - generic [ref=f1e232]: prompt
                      - text: IMAGE_PROMPT
                  - generic [ref=f1e233]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e234]:
                - button "图片生成（需分别确认） image_generate 可执行 输入 prompt IMAGE_PROMPT · 必填 输入 source ASSET_REF 输入 mask ASSET_REF 输出 candidate MEDIA_CANDIDATE 命中 ALL · 定义不调用模型" [ref=f1e235] [cursor=pointer]:
                  - generic [ref=f1e236]:
                    - strong [ref=f1e237]: 图片生成（需分别确认）
                    - code [ref=f1e238]: image_generate
                    - generic [ref=f1e239]: 可执行
                  - generic [ref=f1e240]:
                    - generic [ref=f1e241]:
                      - text: 输入
                      - generic [ref=f1e242]: prompt
                      - text: IMAGE_PROMPT · 必填
                    - generic [ref=f1e243]:
                      - text: 输入
                      - generic [ref=f1e244]: source
                      - text: ASSET_REF
                    - generic [ref=f1e245]:
                      - text: 输入
                      - generic [ref=f1e246]: mask
                      - text: ASSET_REF
                    - generic [ref=f1e247]:
                      - text: 输出
                      - generic [ref=f1e248]: candidate
                      - text: MEDIA_CANDIDATE
                  - generic [ref=f1e249]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e250]:
                - button "图片风格 image_style 可执行 输入 prompt IMAGE_PROMPT · 必填 输出 prompt IMAGE_PROMPT 命中 ALL · 定义不调用模型" [ref=f1e251] [cursor=pointer]:
                  - generic [ref=f1e252]:
                    - strong [ref=f1e253]: 图片风格
                    - code [ref=f1e254]: image_style
                    - generic [ref=f1e255]: 可执行
                  - generic [ref=f1e256]:
                    - generic [ref=f1e257]:
                      - text: 输入
                      - generic [ref=f1e258]: prompt
                      - text: IMAGE_PROMPT · 必填
                    - generic [ref=f1e259]:
                      - text: 输出
                      - generic [ref=f1e260]: prompt
                      - text: IMAGE_PROMPT
                  - generic [ref=f1e261]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e262]:
                - button "图片超分（需分别确认） image_upscale 可执行 输入 source ASSET_REF · 必填 输出 candidate MEDIA_CANDIDATE 命中 ALL · 定义不调用模型" [ref=f1e263] [cursor=pointer]:
                  - generic [ref=f1e264]:
                    - strong [ref=f1e265]: 图片超分（需分别确认）
                    - code [ref=f1e266]: image_upscale
                    - generic [ref=f1e267]: 可执行
                  - generic [ref=f1e268]:
                    - generic [ref=f1e269]:
                      - text: 输入
                      - generic [ref=f1e270]: source
                      - text: ASSET_REF · 必填
                    - generic [ref=f1e271]:
                      - text: 输出
                      - generic [ref=f1e272]: candidate
                      - text: MEDIA_CANDIDATE
                  - generic [ref=f1e273]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e274]:
                - button "导演节点（已保存文档） director_plan 可执行 已选 输出 direction DIRECTOR_PLAN 命中 ALL · 定义不调用模型" [pressed] [ref=f1e275] [cursor=pointer]:
                  - generic [ref=f1e276]:
                    - strong [ref=f1e277]: 导演节点（已保存文档）
                    - code [ref=f1e278]: director_plan
                    - generic [ref=f1e279]: 可执行
                    - generic [ref=f1e280]: 已选
                  - generic [ref=f1e282]:
                    - text: 输出
                    - generic [ref=f1e283]: direction
                    - text: DIRECTOR_PLAN
                  - generic [ref=f1e284]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e285]:
                - button "分镜节点（已保存文档） storyboard_plan 可执行 输入 direction DIRECTOR_PLAN 输出 storyboard STORYBOARD_DATA 命中 ALL · 定义不调用模型" [ref=f1e286] [cursor=pointer]:
                  - generic [ref=f1e287]:
                    - strong [ref=f1e288]: 分镜节点（已保存文档）
                    - code [ref=f1e289]: storyboard_plan
                    - generic [ref=f1e290]: 可执行
                  - generic [ref=f1e291]:
                    - generic [ref=f1e292]:
                      - text: 输入
                      - generic [ref=f1e293]: direction
                      - text: DIRECTOR_PLAN
                    - generic [ref=f1e294]:
                      - text: 输出
                      - generic [ref=f1e295]: storyboard
                      - text: STORYBOARD_DATA
                  - generic [ref=f1e296]: 命中 ALL · 定义不调用模型
              - listitem [ref=f1e297]:
                - button "分镜镜头提示词 storyboard_prompt 可执行 输入 storyboard STORYBOARD_DATA · 必填 输出 prompt IMAGE_PROMPT 命中 ALL · 定义不调用模型" [ref=f1e298] [cursor=pointer]:
                  - generic [ref=f1e299]:
                    - strong [ref=f1e300]: 分镜镜头提示词
                    - code [ref=f1e301]: storyboard_prompt
                    - generic [ref=f1e302]: 可执行
                  - generic [ref=f1e303]:
                    - generic [ref=f1e304]:
                      - text: 输入
                      - generic [ref=f1e305]: storyboard
                      - text: STORYBOARD_DATA · 必填
                    - generic [ref=f1e306]:
                      - text: 输出
                      - generic [ref=f1e307]: prompt
                      - text: IMAGE_PROMPT
                  - generic [ref=f1e308]: 命中 ALL · 定义不调用模型
            - button "添加所选节点（由原控制器执行）" [ref=f1e310] [cursor=pointer]
            - paragraph [ref=f1e311]: 节点预算：已用 0 / 上限 24（取自 CATALOG_MEDIA_LIMITS）。达到任一上限时，本工具会说明原因并建议拆分工作流；它不会抬高任何节点或任务上限。
            - paragraph [ref=f1e312]: 添加与保存仍由原创作图控制器完成：本面板只选择节点类型并调用它，不直接改图、不发请求。
          - region "选择与历史" [ref=f1e313]:
            - heading "选择与历史" [level=3] [ref=f1e314]
            - list [ref=f1e315]:
              - listitem [ref=f1e316]:
                - generic [ref=f1e317]: "0"
                - text: 已选节点
              - listitem [ref=f1e318]:
                - generic [ref=f1e319]: 框选命中：未提供（框选由原画布负责，本栏不编造数字）
              - listitem [ref=f1e320]: 受保护节点 0 个
              - listitem [ref=f1e321]: 本地折叠 0 · 分组 0 · 标注 0
            - status [ref=f1e322]: 当前没有选中节点：可在原画布上单击或框选，或用下方受保护节点按钮。
            - generic [ref=f1e323]:
              - button "只选择全部受保护节点（0）" [disabled] [ref=f1e324]
              - button "清空选择" [disabled] [ref=f1e325]
            - generic [ref=f1e326]:
              - button "撤销本地草稿编辑（可撤销 2 步）" [ref=f1e327] [cursor=pointer]
              - button "重做本地草稿编辑（可重做 0 步）" [disabled] [ref=f1e328]
            - paragraph [ref=f1e329]:
              - text: 撤销/重做
              - strong [ref=f1e330]: 只回退本地草稿操作
              - text: ；已经发生的模型调用与费用、远端任务与已提交的审核都不会被撤销或回滚。撤销也不能移除已保存的资产绑定（原控制器会拒绝并说明）。
            - paragraph [ref=f1e331]: "折叠、分组与标注只是本页会话内的呈现状态：它们不会写入已保存的创作图，也不会随图另存。要持久化它们，需要由原图契约所有者先做一次带类型、向后兼容的扩展（见 `canvasOpsTypes.ts` 顶部说明）。"
          - region "连接建议" [ref=f1e332]:
            - heading "连接建议" [level=3] [ref=f1e333]
            - generic [ref=f1e334]:
              - generic [ref=f1e335]:
                - generic [ref=f1e336]: 连接建议 · 起始输出端口
                - combobox "连接建议 · 起始输出端口" [ref=f1e337]:
                  - option "选择输出端口" [selected]
              - generic [ref=f1e338]:
                - generic [ref=f1e339]: 连接建议 · 目标输入端口
                - combobox "连接建议 · 目标输入端口" [ref=f1e340]:
                  - option "选择输入端口" [selected]
            - paragraph [ref=f1e341]: 待连接来源：尚未选择有效的起始输出端口（请选择现存节点上由目录声明的输出端口）
            - heading [level=4] [ref=f1e342]:
              - text: 兼容目标（由目录端口声明与
              - code [ref=f1e343]: connectionIssue
              - text: 判定）
            - status [ref=f1e344]: 选择起始输出端口后，这里会列出端口类型一致的候选目标。
            - button "连接所选端口（由原控制器执行）" [disabled] [ref=f1e346]
            - status [ref=f1e347]:
              - paragraph [ref=f1e348]:
                - strong [ref=f1e349]: 本地连接检查通过
                - text: ·
                - code [ref=f1e350]: CONNECTION_LEGAL
                - text: （LEGAL）
              - paragraph [ref=f1e351]: 本地端口检查通过（类型一致、无环、输入端口未被占用）。连接合法性最终仍由服务端校验决定。
            - paragraph [ref=f1e352]:
              - text: 本面板不提供绕过入口：类型不匹配、未审核候选、过期来源绑定与缺失必填输入都会在这里以原所有者的结果说明，连接仍由原控制器的
              - code [ref=f1e353]: connect()
              - text: 与
              - code [ref=f1e354]: connectionIssue
              - text: 判定。服务端校验、版本与摘要校验永远不会被跳过。
          - region "变更影响" [ref=f1e355]:
            - heading "变更影响" [level=3] [ref=f1e356]
            - paragraph [ref=f1e357]:
              - text: 当前草稿差异分类：
              - generic [ref=f1e358]: 可能影响生成
              - code [ref=f1e359]: GENERATION_AFFECTING
            - list [ref=f1e360]:
              - listitem [ref=f1e361]: 与已保存版本比较：尚无已保存版本
              - listitem [ref=f1e362]: 未保存修改：无
              - listitem [ref=f1e363]: 节点 0 个 · 连接 0 条
            - status [ref=f1e364]:
              - text: 尚无已保存版本可比：未保存内容一律按
              - code [ref=f1e365]: GENERATION_AFFECTING
              - text: 保守处理，直到你明确保存并由原服务端返回版本与摘要。
            - list [ref=f1e366]:
              - listitem [ref=f1e367]: 缺少可比较的已保存定义，或定义结构不符合原图契约，本地无法证明差异只影响呈现。
            - paragraph [ref=f1e368]:
              - text: 原因码：
              - code [ref=f1e369]: NOT_COMPARABLE
            - paragraph [ref=f1e370]:
              - text: 移动卡片（只改变节点位置）
              - strong [ref=f1e371]: 不会重新运行模型
              - text: ：坐标不是执行输入，本工具也不会因为布局、折叠、分组或标注而调用模型、入队任务或提交审核。 只有上面的原因码涉及参数、来源绑定、节点或连接变化时，才需要在原运行流程中重新预览并逐项确认。
            - paragraph [ref=f1e372]:
              - text: 本判断只基于本地草稿，
              - strong [ref=f1e373]: 永远不会绕过原图的版本与摘要校验
              - text: ：保存仍按
              - code [ref=f1e374]: expected_version
              - text: 进行，执行仍需已审核的预览摘要，撤销/重做也不会回滚已发生的调用与费用。
          - region "自动布局预览" [ref=f1e375]:
            - heading "自动布局预览（确定性，只改坐标）" [level=3] [ref=f1e376]
            - paragraph [ref=f1e377]:
              - text: 若应用自动布局：会分为 0 列，移动 0 个节点的坐标；差异分类为
              - code [ref=f1e378]: PRESENTATION
              - text: （原因：NO_CHANGE）。它不会改动参数、来源绑定、启用状态、连接或图格式。
            - paragraph [ref=f1e379]:
              - text: 自动布局是纯函数结果，必须由原控制器的
              - code [ref=f1e380]: change()
              - text: 提交才能进入本地撤销/重做栈；本批冻结的 props 未包含该回调，因此这里只做预览，绝不直接修改草稿。
        - region "节点图画布" [ref=f1e381]:
          - generic "节点图画布工具" [ref=f1e382]:
            - group "画布操作方式" [ref=f1e383]:
              - button "选择节点" [pressed] [ref=f1e384] [cursor=pointer]
              - button "平移画布" [ref=f1e387] [cursor=pointer]
            - button "缩小节点图" [ref=f1e393] [cursor=pointer]
            - status "节点图缩放" [ref=f1e397]: 100%
            - button "放大节点图" [ref=f1e398] [cursor=pointer]
            - status [ref=f1e402]: 0 个节点 · 0 条连接
            - button "删除所选图节点" [disabled] [ref=f1e403]
          - group "节点图交互区域" [ref=f1e407]:
            - paragraph: 从节点目录添加第一个节点，再选择输入和输出端口连接。
          - paragraph [ref=f1e408]: 拖动节点移动；空白处框选；Shift 多选；Alt 拖动或平移工具移动视图；Ctrl / ⌘ + 滚轮缩放。选中节点后可用方向键移动、Delete 删除，Esc 取消操作。
          - list "节点图连接" [ref=f1e409]
        - region "图连接列表" [ref=f1e410]:
          - heading "已保存到草稿的连接" [level=3] [ref=f1e411]
          - paragraph [ref=f1e412]: 暂无连接；不相连节点可以独立保存。
          - list
        - region "创作图运行与审核" [ref=f1e413]:
          - heading "节点运行" [level=3] [ref=f1e414]
          - paragraph [ref=f1e415]: 先核对保存图与节点范围。前置节点使用原工作流；模型和媒体节点分别预览、确认与执行。媒体 schema 3 核对原资产版本与内容，审核后才供下游采用。
          - paragraph [ref=f1e416]: 先保存创作图，再核对选中节点的运行范围。
          - status [ref=f1e417]: 创作图有未保存修改，请先保存后运行。
          - button "核对运行范围" [disabled] [ref=f1e418]
          - button "读取运行记录" [disabled] [ref=f1e419]
          - region "可选本地文字模型执行" [ref=f1e420]:
            - heading "可选本地文字模型执行" [level=3] [ref=f1e421]
            - paragraph [ref=f1e422]: 先读取能力并选择本地路由，再核对完整输入并明确调用一次。不会自动安装、启动模型、调用、重试或转云端。结果仍需人工审核，不写入正文。
            - paragraph [ref=f1e423]: 云端 API：预留，当前不可执行。实际推理质量验收：未运行。
            - button "读取本地模型能力" [disabled] [ref=f1e424]
            - region "提供方与任务匹配说明" [ref=f1e425]:
              - heading "提供方与任务匹配说明" [level=4] [ref=f1e426]
              - paragraph [ref=f1e427]: 只读取契约与筛选说明，不会选择执行路由、调用模型或自动回退。提供方声明的能力与已验证的适配器契约分别显示；真实推理验收尚未运行。
              - button "读取提供方契约" [disabled] [ref=f1e428]
            - paragraph [ref=f1e429]: 先保存图并创建运行；保存和创建都不会调用模型。
    - button "收起侧栏" [expanded] [ref=f1e430] [cursor=pointer]
    - complementary [ref=f1e434]:
      - separator "调整检查面板宽度" [ref=f1e435]
      - generic [ref=f1e436]:
        - generic [ref=f1e437]: 创作辅助
        - button "收起侧栏" [ref=f1e438] [cursor=pointer]
      - region "创作图节点检查器" [ref=f1e442]:
        - status [ref=f1e443]:
          - strong [ref=f1e444]: 未选择图节点
          - paragraph [ref=f1e445]: 在画布或键盘节点列表中选择一个节点，编辑其参数和位置。
  - contentinfo [ref=f1e446]:
    - text: 未保存或待核对 · 创作图 · 模型调用记录见运行回执
    - button "问助手" [ref=f1e448] [cursor=pointer]
```

# Test source

```ts
  15  |   const exact = async (response: APIResponse, status: number) => {
  16  |     expect(response.status(), await response.text()).toBe(status); return response.json();
  17  |   };
  18  |   info.annotations.push({ type: 'verification', description: 'Actual File owner, HTTP routes, rendered React and installed Edge. Authored synthetic text only; no response mocks, model inference or provider calls.' });
  19  |   const enterWorkspace = async () => {
  20  |     await page.getByText('连接已有创作空间', { exact: true }).click();
  21  |     await page.getByLabel('访问凭证', { exact: true }).fill(token);
  22  |     await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  23  |     await page.getByRole('button', { name: '我的创作空间', exact: true }).click();
  24  |   };
  25  |   try {
  26  |     // The original admin and activation owners prepare one authorized project.
  27  |     // Authentication and selecting it still use the shipped browser entry.
  28  |     const response = await request.post(`${workspace}/projects`, { headers,
  29  |       data: { title: `导演控制台验收 ${info.project.name}`, genre: '' } });
  30  |     if (response.status() === 201) { const row = await response.json(); if (typeof row.id === 'string') owned.push(row.id); }
  31  |     const project = await exact(response, 201), base = `/api/projects/${encodeURIComponent(project.id)}/studio`;
  32  |     const navigation = await exact(await request.get(`${workspace}/navigation`, { headers }), 200);
  33  |     const scope = navigation.eligible_paths.find((path: { project_id: string }) => path.project_id === project.id);
  34  |     expect(scope).toBeTruthy(); headers = { ...headers, 'X-Branch-Id': scope.branch_id };
  35  |     await exact(await request.post(`${base}/activate`, { headers }), 200);
  36  |     await page.goto('/'); await enterWorkspace();
  37  |     await page.getByRole('button', { name: new RegExp(`导演控制台验收 ${info.project.name}`) }).click();
  38  |     const content = { mode: 'DIRECTOR', title: '有明确视觉方向的导演文档', source_independent: true,
  39  |       source_chapter_ids: [], scenes: [], director_notes: [], shots: [], video_plan: null,
  40  |       visual_target: { style: '冷峻写实', atmosphere: '压抑', color: '青蓝低饱和', rhythm: '缓急交替', reference_works: [] } };
  41  |     const documentUrl = `/api/novels/${encodeURIComponent(project.id)}/experimental/creative/documents`;
  42  |     const document = await exact(await request.post(documentUrl, { data: content, headers }), 201);
  43  |     const catalog = await exact(await request.get(`${base}/graphs/planning-documents`, { headers }), 200);
  44  |     const source = catalog.documents.find((row: { id: string }) => row.id === document.id);
  45  |     expect(source).toMatchObject({ id: document.id, version: document.version, mode: 'DIRECTOR' });
  46  | 
  47  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  48  |     await expect(page.getByLabel('创作图标题', { exact: true })).toBeEnabled();
  49  |     await page.getByLabel('创作图标题', { exact: true }).fill('浏览器恢复的文本图');
  50  |     await page.getByLabel('节点类型', { exact: true }).selectOption('text_input');
  51  |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  52  |     await page.getByRole('textbox', { name: '作者输入文本', exact: true }).fill('真实浏览器中保留的作者文本 🎬');
  53  |     await expect.poll(() => page.evaluate(() => Object.entries(localStorage).filter(([key]) => key.startsWith('studio-graph-draft:v1:'))
  54  |       .some(([, value]) => value.includes('真实浏览器中保留的作者文本')))).toBe(true);
  55  |     await page.reload();
  56  |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  57  |     await page.getByRole('button', { name: '核对并恢复本机图草稿', exact: true }).click();
  58  |     await expect(page.getByLabel('创作图标题', { exact: true })).toHaveValue('浏览器恢复的文本图');
  59  |     await page.getByRole('button', { name: /^选择节点 文本输入/ }).click();
  60  |     await expect(page.getByRole('textbox', { name: '作者输入文本', exact: true })).toHaveValue('真实浏览器中保留的作者文本 🎬');
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
  73  |     await page.getByRole('combobox', { name: /^原创作文档/ }).selectOption(document.id);
  74  |     await page.getByRole('button', { name: '添加节点', exact: true }).click();
  75  |     const region = page.getByRole('region', { name: '图节点导演控制台', exact: true });
  76  |     await expect(region).toBeVisible();
  77  |     expect(calls.filter(row => row.path === `${base}/director/workspace/${document.id}`)).toEqual([]);
  78  |     await region.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  79  |     await expect(region.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  80  |     await expect(region.locator('.director-intent__list > li')).toHaveCount(7);
  81  |     const geometry = await page.evaluate(() => {
  82  |       const rect = (selector: string) => { const value = document.querySelector(selector)!.getBoundingClientRect();
  83  |         return { width: value.width, height: value.height, y: value.y }; };
  84  |       return { header: rect('.global-header'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'),
  85  |         scroll_width: document.documentElement.scrollWidth, viewport_width: innerWidth };
  86  |     });
  87  |     expect(geometry.header).toMatchObject({ height: 56, y: 0 });
  88  |     expect(geometry.sidebar.width).toBe(248); expect(geometry.inspector.width).toBe(340);
  89  |     expect(geometry.scroll_width).toBeLessThanOrEqual(geometry.viewport_width);
  90  |     await info.attach('real-shell-geometry', { body: JSON.stringify(geometry), contentType: 'application/json' });
  91  |     await page.evaluate(() => document.fonts.ready);
  92  |     await page.screenshot({ path: info.outputPath('director-console-expanded.png'), fullPage: true });
  93  |     const creatingGraph = page.waitForResponse(value => new URL(value.url()).pathname === `${base}/graphs` && value.request().method() === 'POST');
  94  |     await page.getByRole('button', { name: '保存创作图', exact: true }).click();
  95  |     const graph = await exact(await creatingGraph, 201);
  96  |     expect(graph.definition.nodes).toHaveLength(1);
  97  |     expect(graph.definition.nodes[0].parameters.document_snapshot).toEqual({ id: source.id, version: source.version, digest: source.digest });
  98  | 
  99  |     await page.reload();
  100 |     await page.getByRole('button', { name: '创作图', exact: true }).click();
  101 |     await page.getByLabel('已保存创作图', { exact: true }).selectOption(graph.id);
  102 |     await page.getByRole('button', { name: `选择节点 导演节点（已保存文档） · ${graph.definition.nodes[0].id}`, exact: true }).click();
  103 |     await page.getByRole('button', { name: '展开导演控制台并核对来源', exact: true }).click();
  104 |     await expect(page.getByLabel('导演意图', { exact: true })).toContainText('冷峻写实');
  105 | 
  106 |     await exact(await request.put(`${documentUrl}/${document.id}`, { headers, data: { ...content, expected_version: document.version,
  107 |       visual_target: { ...content.visual_target, style: '已修改但未重绑的视觉方向' } } }), 200);
  108 |     await page.getByRole('button', { name: '重新读取原文档', exact: true }).click();
  109 |     await expect(page.getByText(/CREATIVE_GRAPH_PLANNING_DOCUMENT_CHANGED/)).toBeVisible();
  110 |     await expect(page.getByLabel('导演意图', { exact: true })).toHaveCount(0);
  111 |     await expect(page.getByText('已修改但未重绑的视觉方向', { exact: true })).toHaveCount(0);
  112 |     await page.screenshot({ path: info.outputPath('director-console-stale-refusal.png'), fullPage: true });
  113 |     expect(errors).toEqual([]);
  114 |     expect(calls.filter(row => !['GET', 'HEAD', 'OPTIONS'].includes(row.method)
> 115 |       && /\/(graph-runs|dispatch|generate|director-proposals|media\/tasks)(\/|$)/.test(row.path))).toEqual([]);
      |                                                         ^ Error: apiRequestContext.delete: Target page, context or browser has been closed
  116 |     const stored = await exact(await request.get(`${base}/graphs/${graph.id}`, { headers }), 200);
  117 |     expect(stored.version).toBe(graph.version);
  118 |     expect(stored.definition.nodes[0].parameters.document_snapshot).toEqual(graph.definition.nodes[0].parameters.document_snapshot);
  119 |     await info.attach('real-owner-pins-and-network', { body: JSON.stringify({ project: project.id, source, graph: stored,
  120 |       page_errors: errors, calls }, null, 2), contentType: 'application/json' });
  121 |   } finally {
  122 |     if (info.status !== info.expectedStatus && !page.isClosed()) {
  123 |       await page.screenshot({ path: info.outputPath('director-failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
  124 |     }
  125 |     await info.attach('director-console-network-and-errors', { body: JSON.stringify({ errors, console_errors: consoleErrors, calls }, null, 2), contentType: 'application/json' });
  126 |     for (const id of owned) expect((await request.delete(`${workspace}/projects/${encodeURIComponent(id)}`, { headers })).status()).toBe(204);
  127 |   }
  128 | });
  129 | 
```