# PHASE8 — Studio Release Preparation + Content Policy Framework Reservation

**分支**：`feature/v2-narrative-platform`（PR #47 保持 **Draft**，未合并、未发布、未打标签）
**阶段基线**：任务书给出 `1eb2e2c`；**实际起点为 `70c8d63`**（`1eb2e2c` 之后还有三次收口提交：`961cd5b` 最终冻结收据 r11–r13、`70c8d63` r10 冻结标志分歧定案）。本报告以 `70c8d63` 为起点。
**阶段原则**：不新增大量能力、不重构核心架构、不新增第二套系统；以"整理到接近发布候选 + 预留 + 验收准备"为主。

## 1. 状态总表

| # | Phase8 事项 | 状态 | 依据 |
| --- | --- | --- | --- |
| 1 | 首次体验 / Startup Flow（新建、打开、恢复项目） | **IMPLEMENTED** | `frontend/src/onboarding/`（14 文件 / 96 tests）：空白项目创建、意图与预设、resume 定位（`studioWorkspaceResume`）；集成在 `START` 视图 |
| 2 | Creative Intent 仅作 AI 理解方向（可跳过、可修改、可混合） | **IMPLEMENTED** | 意图为多选且只影响建议（`IntentPicker.test.tsx`"multi-selects and states that intent only affects recommendations"）；空白基线可与任意意图共存；混合由"多选 + 自定义意图"表达 |
| 3 | Production Workspace（当前项目/进度/任务/素材/模块/导出；始终知道"我在哪、下一步是什么"） | **PARTIAL** | 六个事实分散在既有视图中：`PRODUCTION`（阶段/媒体/时间线）、`TASKS`（任务中心）、`ASSETS`（素材）、`PRODUCTION` 内按需的模型中心与导出交接；"下一步"由 `frontend/src/guide/`（UX-08，74 tests，只从已加载 owner 事实推导并**逐条引用来源**）给出。**未**做成单一"工作台摘要"面板，故为 PARTIAL |
| 4 | Task Center 统一状态（Running / Waiting Review / Completed / Failed / Cancelled / Unknown） | **IMPLEMENTED** | `frontend/src/taskcenter/`（15 文件）：逐字转写 owner 的 41 个阶段 + 审核态；owner 未定义的状态**如实显示 UNKNOWN**（`TaskCenter.test.tsx`"renders a status the owner does not define as the honest UNKNOWN state"）；**不隐藏失败**（FAILED 与 EMPTY 分离） |
| 5 | Asset Browser 增强（搜索/分类/预览/版本/引用关系；显示来源 Text/Image/Video/Audio/Shot；查看被哪些模块使用） | **IMPLEMENTED**（含诚实边界） | `frontend/src/assetbrowser/`（18 文件 / 88 tests）：筛选面 + 列表/网格共用选择、详情、版本对比、互斥预览、"送往…"只传引用；**来源与引用关系只按 owner 声明显示**，owner 未声明时显示**未核实**而非猜测（关系投影只声明 ASSET/CHAPTER/SCREENPLAY 目标） |
| 6 | Model Center UX（Local First；检测 Ollama / LM Studio / ComfyUI / llama.cpp / 本地模型目录；显示名称/类型/能力/显存/状态；**禁止自动下载**） | **PARTIAL** | `frontend/src/modelcenter/`（13 文件 / 99 tests）：区分**声明 vs 实测**能力、显示 owner 上报的运行时状态与阻塞事实、**结构上无法触发下载/准备/修复/扫描**（客户端只发 `GET`，契约拒绝任何声称自动清理/迁移/外部扫描的载荷）。**未验证**后端运行时探测是否覆盖上述五种本地来源；前端只呈现 owner 事实，不自行探测 |
| 7 | Content Policy Framework 预留 | **RESERVED**（非 IMPLEMENTED） | 见第 2 节 |
| 8 | 浏览器与视觉验收准备 | **见第 3 节**（BLOCKED / 依据实测记录） | — |
| 9 | Phase9（Windows / GPU / 真实模型 / 完整 CI / 安装流程）准备 | **NOT_RUN** | 见第 5 节 |

## 2. Content Policy Framework = RESERVED

**目标**：为未来项目级创作策略（STANDARD / MATURE / CUSTOM）预留扩展位。**不**实现 NSFW、**不**新增审核系统、**不**改用户流程、**不**解除任何限制。

| 预留位置 | 状态 | 现状 | 刻意不存在 |
| --- | --- | --- | --- |
| Project / Workspace | RESERVED | 复用既有偏好 owner 的可选 `content_policy`（`STANDARD|MATURE|RESTRICTED|CUSTOM`），缺省/历史值一律读作 **STANDARD**；不新建存储 | 无 UI 开关、无 Mature/NSFW 按钮、无策略驱动的模块/服务商/导出限制 |
| 旧项目兼容（本阶段的硬要求） | **DONE** | 偏好 wire 投影冻结为既有字段并用 `row.get`（旧行既不 `KeyError` 也不泄漏新键）；写入时 `None` 表示"不修改"，避免无关编辑静默重置策略 | 无迁移文件、无 schema 变更 |
| Asset | RESERVED | `asset_policy_for(project_policy)`：资产继承来源项目策略，缺省 STANDARD | **不改动资产 owner、不加资产字段**、不改变既有资产读写行为 |
| Model Registry | RESERVED | `model_content_policy_support(entry)` 接受 **Phase8 规定的映射形状** `{"STANDARD": true, "MATURE": false}`（仅 `True` 计入，未知策略名丢弃），并保留早期列表形状兼容；缺省 `("STANDARD",)` | **不过滤、不隐藏、不启用、不启动**任何模型 |
| Export | RESERVED | `export_notice(project_policy)` 返回未来包通知描述符（`rendered:false`、`blocking:false`） | 不渲染、**不阻塞导出**、不改变任何导出结果 |
| 安全边界 | UNCHANGED | 明确写入代码与文档：策略**不是**绕过安全策略、**不是**自动允许内容；未来仍需用户责任、平台规则、年龄限制与内容管理 | 未放松任何既有限制 |

### 验证（File + 真实 PostgreSQL 双后端）

| 项 | 结果 | 收据 |
| --- | --- | --- |
| File 后端（含 Phase7 与 studio seam 同时回归） | **PASS 56 passed / 43 skipped** | `docs/delivery/v2-development/phase8-policy.json` |
| 真实 PostgreSQL（owned 集群，fresh 库、20 迁移、空库证明、正常停止） | **PASS 8 passed / 1 skipped** | `docs/delivery/v2-development/phase8-policy-pg.json` |

新增/覆盖的测试（对应本阶段第 8 节要求）：

1. **旧项目无 `content_policy` → 读取正常且默认 STANDARD**（`test_a_legacy_row_without_the_field_still_reads_as_standard`：走真实 `_preferences` 读取路径 + wire 投影逐字节比对）。
2. **新项目默认 STANDARD**（`test_a_new_project_defaults_to_standard`）。
3. **未知 policy 拒绝**（`test_an_unknown_policy_is_refused`：`NSFW`、`"STANDARD "`、`"standard"`、空串、`CUSTOM_POLICY` 全部拒绝；无 setter 的旁路值也降级为 STANDARD）。
4. **Asset 读取无字段不失败**（`test_no_owner_outside_the_reservation_reads_the_reserved_field`：有界源码守卫证明 `app/` 内**只有**预留模块 + 偏好 owner 触及该字段——唯一例外是**既有且无关**的 `app/experimental/interactive_story.py:701` 的互动故事保留策略串，已带理由列入允许清单）。
5. **Export 不因缺少字段失败**（同上守卫 + `export_notice(None)` 的 `blocking:false`）。
6. 追加：**无关偏好编辑不得重置已保存策略**（真实 owner CAS 证明，File + PG 双后端）；**Phase8 映射形状**（`{"STANDARD": true, "MATURE": false}` 等 9 组断言）。

## 3. 浏览器与视觉验收准备

见 `docs/v2/phase8-browser-acceptance.md`（由专门的准备线产出）：浏览器能力实测、`frontend/e2e/` 入口点、六个界面（START / TASKS / ASSETS / MODEL CENTER / PRODUCTION / DELIVERY）逐项状态，以及把 BLOCKED 转成真实验收所需的操作步骤。**jsdom 通过不构成浏览器验收**，二者分开记录。

## 4. 明确未做 / 未声称

- **不是发布就绪**：M4 PARTIAL、M5–M9 LOCAL_REQUIRED、V1 冻结、F00 INTEGRATED + 39 PARTIAL 均未改变；托管 CI 仍 `BLOCKED_ACCOUNT_PLATFORM`（账单锁，从未启动，不计为通过）。
- **未执行**：真实 Windows 安装版验收、GPU 与真实模型、重型渲染、真实导出/打包产包、完整 CI、真实项目迁移。
- 前端全部证据仍为 **jsdom / 协议夹具**级别。
- 既有环境级失败（非本阶段引入）：`tests/test_v2_audio_wav_controls.py` 2 failed（96 kHz 边界）、`tests/test_v2_media_prerequisites.py` 10 failed（POSIX-only shim）；二者在 `app/` 零改动前提下失败。
- 青简（QingJian）**未修改、未联动、未启动**；仅保留协议与禁用扩展位。

## 5. Phase9 准备清单（Final Validation Preparation）

| 项 | 当前状态 | 需要什么才能转为通过 |
| --- | --- | --- |
| Windows 安装版验收 | NOT_RUN | 构建安装包 + 在干净 Windows 用户环境安装、启动、走通 START→PRODUCTION→DELIVERY |
| GPU / 真实模型验收 | NOT_RUN | 本机可用 GPU 与本地模型运行时；一次真实生成并核验产物 |
| 真实 CPU 媒体管线（S10） | NOT_RUN | 授权在本机跑一次真实渲染/导出并核验字节与时长 |
| 完整 CI | BLOCKED | 账户账单问题解除后，GitHub Actions 才能启动（当前 0 步启动） |
| 安装/升级流程与回滚 | NOT_RUN | 安装包签名、升级路径、回滚脚本与验证 |
| 浏览器验收 | 见第 3 节 | 提供浏览器二进制并启动应用后运行 `frontend/e2e/` |
| 真实项目迁移 | NOT_RUN | 用真实旧项目数据执行迁移并核对内容与策略字段 |

## 6. 工程规则遵守情况

保持既有 Asset Owner、Model Center、Review、Version、Controller —— **未新建第二套系统**；未修改 `main`；未 Release；未 Merge PR；未修改 QingJian；未删除历史证据；未使用 `git reset --hard` / `git clean` / force push / `git add -A`；所有提交使用显式路径。受保护 UI 面（`AppShell`、`GlobalHeader`、`ModuleSwitcher`、`ContextBar`、`StatusBar`、`tokens.css`、`primitives.tsx`、`moduleRegistry.tsx`）**未改动**。
