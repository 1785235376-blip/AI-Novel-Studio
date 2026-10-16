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

## 批次 3 验证线补充实测（独立执行，2026-10-14）

以下为本机**实测**结论，用于收紧上表口径；均为**既有/环境级**，`app/**` 在本工作包内无改动：

| 发现 | 实测 | 对本表的影响 |
| --- | --- | --- |
| `tests/test_v2_audio_wav_controls.py` | 46 passed / 20 skipped / **2 failed**：`…[file-96000-2-12.0-10000-32767]` 与 `[…--10000--32768]` 返回 job `FAILED` 而非 `AWAITING_REVIEW`（本机 ffmpeg 8.1.2；根因未在断言输出中证明） | **S10 仍为 NOT_COVERED**，并新增一条已知既有失败；不得据此宣称 CPU 媒体管线可用 |
| `tests/test_v2_media_prerequisites.py` | **10 failed**：其合成 shim 为 shebang 脚本，而 `probe()` 把 PATH 替换为 `tmp_path`（POSIX-only 用例）；真实 ffmpeg/ffprobe 存在于 `D:\ffmpeg` | 同上；属**测试自身不可移植**，非产品缺陷，但必须如实记录 |
| `tests/test_v2_cpu_cutout_pixels.py` / `test_v2_cpu_cutout_owner.py` | 69 passed / 46 passed+46 skipped | S10 的**像素级**部分有既有覆盖，但仍**不是**本工作包的真实管线验收 |
| `tests/test_export_jobs.py` | 18 passed，含 `test_export_job_rejects_unknown_format`（未知格式抛 `ValueError`） | S11 的"不支持格式不能假导出"在**后端 owner 层**有证据；"单条导出不依赖全项目"仍无证据（UX-09） |
| 既有 storyboard/timeline 套件 | 9 个套件 **167 tests PASS**（含 `TimelineSourceEditing.phase6` 的原子准备/显式保存/503 不重放/UNKNOWN 保留） | 为 S09 的"撤销与冲突恢复"提供 owner 层证据；仍缺真实浏览器与真实 PG 的保存冲突复现 |
| 集成映射缺陷 | 验证线发现并已修复（提交 `b2bb623`）：`onEdit` 曾读错 `at_ms`/`target_track_id`，致 duplicate/move 被恒拒（fail-closed） | 提醒：**界面"拒绝"不等于功能正确**；接线类改动必须配测试 |

**口径提醒**：`scripts/check_ui_design_tokens.mjs` 只扫描 `frontend/src/ui`，`tokens` 收据的 PASS **不覆盖**任何功能目录的 CSS；新增目录的令牌合规来自验证线的逐目录扫描，而非该检查。

## 执行范围更正与流程缺陷（批次 4 验证线独立发现，2026-10-14 22:2x）

以下为本表**必须更正**的口径问题，均由独立验证线以反证形式提出：

| 问题 | 事实 | 更正后的表述 |
| --- | --- | --- |
| 本表引用了**未被批次 harness 执行**的测试文件 | 批次 4 验收命令（`run_ux_product_checks.py`）只执行 8 个 UX 目录 + 14 个既有回归文件；`quality` 下列文件**不在**该执行集内：`src/creative/studioWorkspaceResume.test.ts`（S01/S02 模式切换）、`src/creative/StudioSelectLabels.test.tsx` 与 `src/creative/CreativeWorkspace.test.tsx`（S14）、`src/creative/TimelineSourceEditing.phase6.test.tsx`（S09 撤销/保存冲突） | 这些文件确有**执行证据**，但来自 Lead 集成轮的**直接 vitest 运行**（批次 3 集成时 `pnpm exec vitest run src/storyboard src/nle src/creative/IndependentStudio src/creative/CreativeWorkspace.test.tsx` = 16 files/292 tests；批次 1/2 亦直跑过对应套件），**不是**批次 harness 的一部分。正确表述应为"**Lead 直接运行**"，而非"批次收据覆盖"。 |
| 并发写入同一收据路径（§15.3 违规） | 修订 8 有**两次并发运行**（验证线与 Lead 各自执行同一命令），互相覆盖 `ux-product-*-r8.json`。存留集合来自另一次运行 | r8 收据**不是**单次无争用运行的结果；该违规由 Lead 的调度造成（未在启动 harness 前与验证线互斥），已如实记录。 |
| harness 覆盖完整性只按**目录存在**判断 | `frontend` 检查的 `incomplete_coverage` 依据目录是否存在，而非目录内是否有测试 | 若某 UX 目录存在但**无测试**，仍会被记为 PASS；本批次未触发（modelcenter 99 + guide 74 确实执行）。 |
| `types` 检查在**热缓存**下偏弱 | 验证线运行中 `types` PASS，而同一文件的 esbuild 已报错——`tsc -b` 使用了 `frontend/tsconfig.tsbuildinfo` 热缓存 | 需要 `tsc -b --force` 才能作为强证据；后续批次应在冻结前强制重建。 |
| Lead 集成曾**瞬时中断构建** | 修订 8 期间 `IndependentStudioWorkspace.tsx:81` 出现"组件体内 import"（Lead 的编辑失误），使某次 build FAIL，随后修复 | r8 的 all-PASS 是**修复后**的结果；该中断属真实过程记录，不作为产品缺陷保留。 |

**因此**：本表"COVERED"的含义收窄为"**有某次真实执行的测试证据**（可能来自 Lead 直跑而非批次 harness）"；只有同时出现在批次收据中的条目，才是被 harness 独立复核过的。
