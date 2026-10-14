# PHASE9_RELEASE_VALIDATION_REPORT — Release Candidate 准备

**分支**：`feature/v2-narrative-platform` ｜ **PR #47**：OPEN / **Draft**（未合并、未发布、未打标签）
**Phase9 起点**：`3304fa6`（任务书给定）｜ **本阶段提交**：`9b12704`（浏览器 8/8 与证据）；本报告与其后的矩阵/文档为同一阶段续接
**原则**：不新增大量模块、不重设计既有系统、不修改 V1 冻结内容、QingJian 只读、不伪造通过；环境缺失记 `BLOCKED_EXTERNAL`，不改测试绕过。

## 1. 阶段状态总表（A–F）

| 阶段 | 事项 | 状态 | 依据 |
| --- | --- | --- | --- |
| **A** | 真实浏览器验收补全（目标 8/8） | **PASS 8/8** | 真实后端（uvicorn + file 存储 + `narrative_production_v2`）+ Vite + **系统 Edge**：`8 passed (14.1s)`，exit 0。见 `PHASE9_BROWSER_ACCEPTANCE_REPORT.md` |
| **B** | Model Center 真实能力验证（Local First 发现） | **PARTIAL（本机多数 NOT_FOUND）** | 见第 2 节：直接探测结果为 NOT_FOUND 为主；未下载、未安装任何模型；`8080` 有服务响应但**身份未证实**，不据此声称 app 可用运行时 |
| **C** | Windows 验收准备 | **PASS（计划已产出）**，执行 **NOT_RUN** | `WINDOWS_VALIDATION_PLAN.md`（安装/卸载、中文与空格路径、首次启动与重启恢复、缓存、DesktopHost、RTX 5080 测试项目、通过标准） |
| **D** | 真实媒体管线准备 | **PASS（计划已产出）**，执行 **NOT_RUN** | `MEDIA_PIPELINE_VALIDATION_PLAN.md`（Text→Image→Video→Audio→Timeline→Export 的输入/模型/输出/检查项/失败处理） |
| **E** | 安装与发布文档整理 | **PARTIAL** | 见第 4 节文档索引与缺口；既有文档丰富，`docs/INSTALLATION.md` 与 `docs/TROUBLESHOOTING.md` 仍是 3–8 行存根 |
| **F** | Release Candidate 整理 | **PARTIAL** | 本报告 + 矩阵更新；RC 结论**不**成立（见第 6 节） |
| — | Content Policy Framework | **RESERVED**（保持） | 未实现 NSFW/Mature，未加按钮/UI 入口/模型过滤；仅字段、接口与兼容性 |

## 2. Stage B — Model Center 真实探测结果（只探测，零下载零安装）

**方法**：对本机已知默认端点做**有界**探测 + 仅检查若干**已知**模型目录 + `Get-Command` 查可执行文件。**未**做全盘扫描，**未**下载/安装任何东西。

| 目标 | 探测 | 结果 |
| --- | --- | --- |
| Ollama | `http://127.0.0.1:11434/api/tags` | **NOT_FOUND**（连接被拒绝）；PATH 无 `ollama` |
| LM Studio | `http://127.0.0.1:1234/v1/models` | **NOT_FOUND**（连接被拒绝）；`~\.cache\lm-studio`、`%LOCALAPPDATA%\LM-Studio` 均不存在 |
| ComfyUI | `http://127.0.0.1:8188/system_stats` | **NOT_FOUND**（连接被拒绝）；`D:\ComfyUI` 不存在；PATH 无 `comfy` |
| llama.cpp | `http://127.0.0.1:8081/health`；PATH `llama-server`/`llama-cli`/`llama-cpp` | `8081` **NOT_FOUND**；PATH 均 **NOT_FOUND**。**`8080` 有服务响应（HTTP 200，151 字节）但身份未证实** —— 本机存在一个本地模型服务（疑似 llama.cpp 系的本地服务），我**没有**验证它是否作为 app 的运行时被识别，故**不**记为可用 |
| 本地模型目录 | `~\.ollama\models`、`~\.cache\huggingface`、`D:\models`、`C:\models`、`D:\PoemSeed\models` | 前四者 **NOT_FOUND**；`D:\PoemSeed\models` **存在但其中 GGUF/Safetensors/ckpt/bin 文件数为 0** |

**结论（诚实口径）**：本机**没有**可供 app 直接发现的 Ollama / LM Studio / ComfyUI 运行时，也没有本地 GGUF/Safetensors 模型文件；`8080` 上的服务身份未证实。因此 **Stage B 的"发现能力"未能在本机得到正面验证**，只得到"缺失即如实 NOT_FOUND"的负面证据。**未模拟存在**。
**app 侧检测面**（既有 owner）为 `GET /api/model-center/models`、`/runtimes`、`/runtimes/{id}/capabilities` 与 `GET /api/projects/{id}/studio/storage`；本轮**未**对运行中的后端逐一取证（`NOT_RUN`），不据前端契约推断后端探测覆盖度。

## 3. Stage A 的关键更正（自我更正，保留历史）

Phase8 曾记录 **7/8、START BLOCKED**。原因有二：当时**未启动后端**；且提交 `3304fa6` 中的 spec 是**较早的点探版本**。Phase9 提交了**竞态版**（`Promise.race`）并启动真实后端 → **8/8**。两处记录都保留，未覆盖历史。
**同时记录两个环境事实**：①Vite 只绑 IPv6 `[::1]`，base URL 必须用 `http://localhost:5173`（否则 8 项全失败）；②Vite 曾在运行中静默退出一次（exit 1）。
**数据库参与的浏览器验收 = `BLOCKED_EXTERNAL`**：仓库既有 `frontend/playwright.config.ts` 硬编码 `../.venv\Scripts\python.exe`（不存在）且后端端口 8000 属 Windows 排除区间。

## 4. Stage E — 发布文档索引与缺口（只核查，不改写历史文档）

| 需要 | 既有文档 | 状态 |
| --- | --- | --- |
| 总览 | `README.md`（41 行） | **PARTIAL**（偏短，未覆盖 V2 Studio 的六界面与验收入口） |
| 安装 | `docs/INSTALLATION.md`（= `docs/installation.md`，**3 行存根**） | **PARTIAL**（存根；安装器流程未记录） |
| 用户指南 | `USER_ACCEPTANCE_GUIDE.md`（根目录，存在） | **PARTIAL**（存在；未与 Phase9 的八项浏览器验收对齐） |
| 模型设置 | `LOCAL_AI_DISCOVERY.md`、`LOCAL_AI_WINDOWS_ACCEPTANCE.md`、`AI_NOVEL_STUDIO_V2_LOCAL_MODEL_INTEGRATION.md` | **PARTIAL**（存在；与 Stage B 的实测 NOT_FOUND 结论尚未合并） |
| 故障排查 | `docs/TROUBLESHOOTING.md`（**8 行存根**） | **PARTIAL**（存根） |
| Windows 验收 | `AI_NOVEL_STUDIO_V2_WINDOWS_ACCEPTANCE_PLAN.md` + 本阶段 `WINDOWS_VALIDATION_PLAN.md` | **PASS（计划层）** |
| 架构/接口 | `AI_NOVEL_STUDIO_V2_ARCHITECTURE.md`、`API_CATALOG.md`、`FINAL_PRODUCT_SURFACE_MAP.md` | **PASS（既有）** |
| 冻结边界 | `V1_SCOPE_FREEZE.md` | **PASS（既有，未改）** |

**本轮未新增重复文档**（避免与既有 80+ 份文档冲突）；缺口（安装器流程、故障排查条目、README 的 V2 六界面与验收入口）如实记为 **PARTIAL**，建议作为独立文档任务，而不是在本阶段临时杜撰内容。

## 5. 测试分层执行情况（本阶段）

| 层 | 内容 | 状态 |
| --- | --- | --- |
| 快速验证 | Unit / API / TypeScript / Build | **PASS（既有基线）**：Phase9 起点 `3304fa6` 已含 UI 层 30 files / 446+ tests、`tsc -b` 0、`vite build` 通过 |
| 集成验证 | File / PostgreSQL / Browser | **File + 真实 PostgreSQL PASS**（`phase8-policy.json` 56/43、`phase8-policy-pg.json` 8/1）；**Browser PASS 8/8**（本阶段） |
| 最终验证 | Windows / GPU / 真实模型 | **NOT_RUN**（属用户或授权后的验收；计划见 C/D） |

## 6. Release Candidate 结论（**不成立**，如实）

**本阶段未把 V2 判定为 Release Candidate**。理由：安装/卸载、中文与空格路径、DesktopHost 可信会话、GPU 与真实模型、真实媒体管线、真实导地产包、完整 CI 均 **NOT_RUN**；托管 CI 仍 `BLOCKED_ACCOUNT_PLATFORM`；S10 仍无真实执行证据；S12 仅契约层；Model Center 的本地发现能力在本机**未能正面验证**。
**已达成**：真实浏览器 8/8（六界面 + 中文 + 键盘）、真实 PostgreSQL 与 File 双后端证据、Content Policy 预留（RESERVED）与旧项目兼容、两份可执行验证计划、诚实文档索引。
**未升级任何未经验证项**：M4 PARTIAL、M5–M9 LOCAL_REQUIRED、V1 冻结、F00 INTEGRATED + 39 PARTIAL 均保持原状态。

## 7. 外部阻塞（`BLOCKED_EXTERNAL`）

| 项 | 阻塞点 | 解除条件 |
| --- | --- | --- |
| PostgreSQL 参与的浏览器验收 | 既有 e2e 配置缺 `../.venv` 且端口 8000 被 Windows 排除 | 修环境（建 venv 或换端口），**不改测试绕过** |
| 完整 CI | 账户账单锁（作业 0 步启动） | 账单问题解除 |
| GPU / 真实模型 / 媒体管线 | 本机无可用本地运行时与模型文件（Stage B 实测） | 操作者提供运行时与模型；**禁止自动下载** |
| Windows 安装版验收 | 无安装包与干净环境 | 构建安装包 + 干净 Windows 用户环境 |
