# UX-PRODUCT 场景覆盖（任务书 S01–S14）

覆盖状态口径（严格）：
- **COVERED** = 有被执行的真实测试证据，且证据直接对应该场景断言；
- **PARTIAL** = 只覆盖部分子句，或只有协议夹具/模拟 HTTP，或后端变体被跳过；
- **NOT_COVERED** = 本工作包内**没有**可引用证据（大多是尚未开始的 UX-09 或需要真实渲染/浏览器/安装版的动作）。

**本文件不把"文件存在"当作覆盖。** 每条给出实际执行的测试名或收据。独立验证线另有一份自己的 S01–S14 表，两者不一致时以**证据**为准并以后者修订本文件。

| ID | 场景（任务书原文） | 状态 | 实际证据（文件 · 用例） | 未覆盖的环境 |
| --- | --- | --- | --- | --- |
| S01 | 空白项目直接进入图片/视频/剪辑，不要求小说、章节或导演文档。 | **COVERED**（前端） | `src/onboarding/studioEntryContract.test.ts`、`useStudioEntry.test.tsx`（空项目入口、意图/预设写入 `POST /api/experimental/projects`）；`src/creative/studioWorkspaceResume.test.ts`（START 视图与空项目定位）；`src/storyboard/*` 断言分镜在**没有**小说/导演文档时仍可独立编辑（只发 1 次 storyboard 读取） | 真实后端往返；`seam` 中 postgres 变体被跳过 |
| S02 | 修改创作意图、切换新手/专业模式，资产、任务、图参数、权限和草稿不被重建或丢弃。 | **COVERED**（呈现层） | `src/creative/studioWorkspaceResume.test.ts`（模式往返/默认/非法值拒绝/合并保留其他字段/不伪造位置）；`IndependentStudio*` 回归（模式切换后草稿与图参数存活） | 未做真实浏览器会话；模式跨浏览器一致未验证（见 DECISIONS D1b） |
| S03 | 有模型与无模型两种入口都能理解并继续相应可用操作；打开模型页不隐式加载/下载。 | **PARTIAL** | 无模型路径：`src/onboarding`+`src/taskcenter`（无模型也能进入并显示可用/不可用原因）；模型路径：**UX-07 本批进行中**，`modelCenterOps` 的 readiness 语义断言"打开页面不触发下载" | 真实模型/GPU 环境；真实下载与准备流程 |
| S04 | 一次请求发生双击或响应丢失，原 owner 最多产生一次实际派发；UNKNOWN 恢复不重放。 | **PARTIAL** | 原 owner 幂等/请求摘要语义由既有 `seam`/`file` 收据覆盖；`src/taskcenter` 对 UNKNOWN 只展示不重发（`taskCenterContract.test.ts`） | 未做真实双击并发压测；未做真实响应丢失注入 |
| S05 | 候选审核绑定原版本/摘要，重复采用、过期来源、权限撤销均正确拒绝或返回原合法结果。 | **PARTIAL** | 既有 owner 套件（`file` 变体）：候选/版本 CAS 与权限撤销路径；`src/storyboard/storyboardOps.test.ts`（候选与来源版本绑定、陈旧来源只报告） | postgres 变体被跳过；未做真实多身份并发 |
| S06 | 同一素材在镜头/节点/时间线复用，替换一处不会隐式改其他引用，影响范围可查看。 | **COVERED**（前端） | `src/assetbrowser/assetBrowserOps.test.ts`（"maps every declared and lineage edge onto the referenced asset"、"counts by kind, relationship and non-current state"、"flags only the references that need a user decision"、"never claims a physical delete and refuses to hide unknown references"）；`useAssetBrowser.test.tsx`（关系读取后盖引用计数与影响） | 后端 postgres 变体；更深层的既有素材复用套件（仅作为既有覆盖引用） |
| S07 | 画布连线类型错误、未审核候选输入、旧资产版本均无法绕过原门禁。 | **COVERED**（消费侧） | `src/canvasops/canvasOps.test.ts`（每行结论等于直接调用 `connectionIssue`；`CANDIDATE_REVIEW_REQUIRED`/`UNREVIEWED_PROPOSAL` 全为 `legal:false`）；`canvasOpsPanels.test.tsx`（"cannot bypass a type mismatch"）；既有 `graphDraft.test.ts` 真值表 | 未执行真实后端门禁；未审核候选只到**协议措辞**层 |
| S08 | 任务中心、素材预览和 Inspector 在项目/身份切换后不显示旧用户的迟到响应。 | **PARTIAL** | 身份/范围守卫（`isCurrent`、epoch、`*_SCOPE_MISMATCH`）由 `src/taskcenter`、`src/assetbrowser`、`src/creative` 的失败态用例覆盖（拒绝读取不得渲染为空） | 未做真实迟到达注入；未做浏览器级身份切换 |
| S09 | 多轨编辑草稿、撤销、保存冲突、重开和原来源替换能恢复到可理解状态，不掩盖数据冲突。 | **PARTIAL** | `src/nle/timelineOps.test.ts`（时间基无漂移、入出点校验、编辑命令映射与**显式拒绝**）；既有控制器自带撤销/保存冲突/重开语义（`useStudioTimelineEditor` 及其套件） | 真实保存冲突与重开未在浏览器/真实 PG 下执行；四类编辑尚未接线（界面明确拒绝） |
| S10 | 小型 CPU 媒体管线在具备原工具时产生真实输出并核验；无工具则清楚阻塞，不用 mock 冒充。 | **NOT_COVERED** | 本工作包**未执行**任何真实渲染；`src/nle` 只断言"预览质量 ≠ 成品导出质量"与 `deliveryReady` 恒 false（不冒充成功） | 全部：真实 CPU 媒体管线、工具缺失阻塞、真实产物核验 |
| S11 | 导出单一文本/图片/音频/视频不依赖全项目完成；不支持格式不能执行假导出。 | **PARTIAL** | `src/nle/timelineOps.test.ts`（不支持的编辑/格式给出机器码+中文拒绝，不执行替代动作）；既有导出面板语义 | 未执行任何真实导出；未验证"单条导出不依赖全项目"的真实往返 |
| S12 | 工程交接包只含明确选择且有权导出的对象，不含模型、依赖目录、凭据或其他项目。 | **NOT_COVERED** | **UX-09 尚未开始** | 全部 |
| S13 | 错误/空数据/无权限/未知结果展示准确，用户能定位恢复动作；真实请求失败不展示成功。 | **COVERED**（夹具级） | `useAssetBrowser.test.tsx:51/63/72`（拒绝读取不得渲染为空）；`assetBrowserClient.test.ts:113/142`；`canvasOpsPanels.test.tsx:135/367`；`useStudioEntry.test.tsx:74`、`TaskCenter.test.tsx:113`、`taskCenterContract.test.ts:76`（不虚构 0%）；`src/storyboard`（读取失败 ≠ "暂无分镜"） | 仅为协议夹具/模拟 HTTP；**无**真实后端往返或浏览器旅程 |
| S14 | 中文输入、键盘焦点、重复标签、常用窗口尺寸与长列表场景不出现已知交互回归。 | **PARTIAL** | 中文文案与**重复标签**的真实回归已修并留证：批次 1 的"图片设计"重复元素、批次 2 的 `起始输出端口` 无障碍名称冲突（`StudioSelectLabels.test.tsx` 恢复全绿）、批次 3 的按需打开（`CreativeWorkspace.test.tsx` 2 项恢复）；长列表有边界拒绝（素材 500 行拒绝而非截断） | **未做**浏览器/视觉与几何验收、键盘焦点与窗口尺寸的真实检查 |

## 结论（诚实口径）

- **COVERED**：S01、S02、S06、S07、S13（其中 S13 仅为夹具级）。
- **PARTIAL**：S03、S04、S05、S08、S09、S11、S14。
- **NOT_COVERED**：S10、S12 —— 前者需要真实 CPU 媒体管线执行，后者属于尚未开始的 UX-09。
- 所有前端场景证据均为 **jsdom/协议夹具**；没有任何一条场景经过真实浏览器视觉验收或真实 Windows 安装版验收。
- 本表不构成发布就绪结论：M4 PARTIAL、M5–M9 LOCAL_REQUIRED、托管 CI `BLOCKED_ACCOUNT_PLATFORM` 均未改变。
