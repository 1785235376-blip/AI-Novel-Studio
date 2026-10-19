# AI Novel Studio V0.7.0 Engineering Edition

本地优先、可迁移的混合 AI 长篇小说生产系统。PostgreSQL 保存已批准事实，Markdown 保存正文，开放文件保存知识源；本地/云端模型只是可替换计算能力。Dify 是可选编排层，核心数据不依赖 Dify。

## 社区与工程入口

- **贡献指南**：[CONTRIBUTING.md](CONTRIBUTING.md) —— 分支/PR 策略、提交规范、最小复现与测试要求、
  Windows / Linux / macOS 人工分步环境、隐私与素材提交规则。
- **架构总览**：[ARCHITECTURE.md](ARCHITECTURE.md) —— 组件关系、单一数据权威、三类图语义、
  版本/CAS/权限/云端授权、媒体流水线、Image Studio → 漫画子能力归属。
- **Issue 模板**：[.github/ISSUE_TEMPLATE](.github/ISSUE_TEMPLATE) —— Bug 必填 SHA/OS/复现步骤/实际与预期/
  数据影响/脱敏确认；Feature 必填用户场景/当前缺口/期望能力/影响模块/验收标准/兼容性/资源预算。
- **本地最小 CI**：[docs/v2/engineering/LOCAL_CI_MINIMUM.md](docs/v2/engineering/LOCAL_CI_MINIMUM.md) ——
  分步执行 LOCAL-01～05（真实 uvicorn + /health、pytest 正确性切片、Vitest/构建/设计 token、
  真实浏览器保存重读旅程、清理），结果与 Git SHA 绑定；这是测试命令集合，**不是**一键安装或一键启动。
- **工程规范与证据**：[docs/v2/engineering/README.md](docs/v2/engineering/README.md)、
  [RUNBOOK.md](docs/v2/engineering/RUNBOOK.md)、[RELEASE_GATES.md](docs/v2/engineering/RELEASE_GATES.md)、
  [DEFECTS_20261019_r1.md](docs/v2/engineering/DEFECTS_20261019_r1.md)、
  [requirements-traceability.json](docs/v2/engineering/requirements-traceability.json)。
- **开源许可**：[LICENSE](LICENSE)（Apache-2.0）、[NOTICE](NOTICE)、
  [LICENSING_AND_THIRD_PARTY.md](LICENSING_AND_THIRD_PARTY.md) —— 用户作品、模型权重、
  字体与第三方依赖的边界。

### 已知限制（不要误读为发布就绪）

- V2 尚未正式发布；Git 注释标签 `v0.1.0-alpha` 是早期**工程源码快照锚点**，
  不是 V1.X RC1、不是 V2 正式版、也不是产品验收 PASS。
- 本阶段不提供 Docker Compose 或任何一键安装 / 一键启动 / 一键部署方案。
- 本机没有已授权的本地模型/GPU 推理证据；Mock 只证明非模型业务行为，不证明 AI 质量。
- 完整真实 PostgreSQL 套件在当前 Windows 主机为 `BLOCKED_ENVIRONMENT`（D-07），
  只有代表性真实 PG 子集通过。
- 宿主 CI 为 `HOSTED_BLOCKED_NO_RUNNER`（历史 Actions runner 未真实启动）；
  保留既有 workflow，不用本地结果冒充宿主 CI。

## 当前状态（V0.7.0）

V0.1 数据与 Agent 架构保留。V0.2 增加 Runtime Registry、Mock/Ollama Streaming、完整 `/api`、Generation Job/SSE/Draft Accept；V0.3 增加 React + TypeScript + Vite + TipTap 三栏 Writer UI。当前机器未发现 Docker、Ollama 或 Cloud Key，真实 Runtime 仍为 PARTIAL。

V1.0 Windows DesktopHost 正在开发验收中，尚未发布。当前已有内部验收 ZIP/EXE 快照（不是公共发行物）；已完成项、前端预留窗口和未完成项见 [`docs/v1_implementation_status.md`](docs/v1_implementation_status.md)，验收矩阵见 [`docs/acceptance_report_20260822.md`](docs/acceptance_report_20260822.md)。

## 启动与停止

1. 安装 Docker Desktop 与 Ollama，并确认 WSL2 可用。
2. 复制 `.env.example` 为 `.env`，至少修改 `POSTGRES_PASSWORD`；不要提交 `.env`。
3. 按 `config/model_manifest.json` 安装一个 7B/8B 模型。
4. 执行 `scripts/start.ps1`，访问 Writer UI `http://localhost:3000`，API 文档 `http://localhost:8000/docs`。
5. 停止仅本项目：`scripts/stop.ps1`。

## 创作

样例小说位于 `novel_data/novels/sample_novel`。修改 `.env` 的 `CREATION_PROFILE` 为 `LOCAL_ONLY`、`HYBRID` 或 `QUALITY`。HYBRID/QUALITY 需设置 Provider、模型名和相应 Key；Key 缺失时路由应回退到本地，而不是返回不明 500。

没有模型时将 `.env` 设为 `MOCK_PROVIDER=true`。AI 结果只进入 Draft Preview；Accept 后才会原子写入章节、更新 Summary 并产生 Pending Canon。

## 模型与 Provider

本地默认 Ollama。`LLMProvider` 统一 `generate/stream/health_check/get_model_info/estimate_usage`；OpenAI Compatible 适配器可用于 OpenAI、DeepSeek、OpenRouter 类接口，Anthropic/Gemini 原生协议预留但尚未实现。

### 凭据保险库与发布门禁

`CREDENTIAL_VAULT_BACKEND` 可设为 `auto`、`windows`、`keyring` 或 `memory`；`CREDENTIAL_VAULT_SERVICE` 指定系统钥匙串 service 名，默认 `AI-Novel-Studio`。`CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK` 在开发环境可设为 `true`，packaged 构建必须为 `false`。`memory` 仅限当前进程，不跨重启，也不在多 worker 之间共享；只有 `windows` / `keyring` 提供跨进程持久凭据。所有凭据状态响应的 `secret` 恒为 `null`。

`GET /api/release/readiness` 聚合凭据、Session 边界、Provider、packaged bootstrap 与插件隔离状态。packaged 环境中凭据不可持久、允许 memory fallback 或 bootstrap/Session 不完整时，门禁返回 `BLOCKED`。

## 备份、恢复、迁移

运行 `scripts/backup.ps1` 生成含校验清单的备份；模型 blob 不复制。恢复使用 `scripts/restore.ps1 -BackupPath ...`，已有小说默认拒绝覆盖。4060→5080 使用 `scripts/migrate.ps1 -Destination ...`，新机器仅需重装模型并改 Profile。

## 测试

安装 Python 3.11+ 后执行 `python -m pip install -e .[dev]` 与 `python -m pytest`。详见 `docs/test_report.md`。

## V2 分支（`feature/v2-narrative-platform`）验证状态

本节只记录**已核实**事实；未执行的项一律 `NOT_RUN`，不会因为存在旧报告而升级。
状态词表只用 `IMPLEMENTED` / `PARTIAL` / `BLOCKED` / `LOCAL_REQUIRED` / `NOT_RUN`。

### 校验运行器（本工作区实测）

工作区：`Worktrees/studio-v2-audio-editing-20261014`；
解释器：`C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe`；
始终设置 `PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`。

pytest **必须**经运行器，直接运行会 `KeyError: 'PROJECT_ROOT'`：

```powershell
python scripts/run_v2_checks.py <label> -- python -m pytest <files> -q `
  --basetemp .runtime/v2-checks/<label>/pytest -p no:cacheprovider
```

真实 PostgreSQL（可复用便携集群，**不**安装系统服务；运行器结束时正常停止）：

```powershell
python scripts/run_v2_postgres_checks.py --pg-bin <便携 PG bin> --data <集群数据目录> `
  --port 55433 --database v2_<新库名> --fresh-database <label> `
  -- <python 绝对路径> -m pytest <files> -q --basetemp <已存在的目录> -p no:cacheprovider
```

四个易错点（漏掉会产生与产品无关的失败）：`--user` 是数据库**连接角色**（默认 `postgres`），
不是标签；标签是**位置参数**；`--basetemp` 目录必须**预先存在**；解释器必须写**绝对路径**。

### 本阶段已核实结论

- 创作图节点契约追加测试：**260 passed**（`+142 / −0`，未放宽任何既有断言）。
- `app/model_center/` 是**真实**本地探测栈，但五级中**第②级（Runtime 是否存在）未实现**：
  发现报告不含任何进程事实，因此 `DISCOVERED` 只表示"端点未应答"，**不等于**"没有进程"。
  **发现不等于可运行**。真实 PostgreSQL 上 `tests/test_v2_discovery_runtime_levels.py`
  **4 passed**（空库先验证 → 20 个迁移全部应用 → 服务正常停止）。
- 本机**没有**应用可用的本地运行时：11434 / 1234 / 8188 均拒连；8080 已确认为
  **Strata** 本地模型服务（独立 Python 3.12 安装），**不是**本应用运行时，也未注册到
  Model Center；8100 已被 ASUS `GearLink_KBService.exe` 占用。
- 安装/卸载、打包、DesktopHost 可信会话、GPU 与真实模型执行、真实媒体流水线、
  浏览器复验、完整 CI 全部 `NOT_RUN`；托管 CI 为 `BLOCKED_ACCOUNT_PLATFORM`（账单锁）。
- `CONTENT_POLICY_FRAMEWORK` 仍为 `RESERVED`，未实现任何 NSFW/Mature 能力。

详见 [`PHASE10_RELEASE_HARDENING_REPORT.md`](PHASE10_RELEASE_HARDENING_REPORT.md) 与
[`AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md`](AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md) 的 Phase10 追加区。

### Phase11（RC Gate Closure）已核实事实

- **第②级已补齐**：`app/model_center/runtime_observation.py` 是**只观察**层——不启动、不安装、不下载、不产生任何子进程。五级阶梯：`0 NOT_OBSERVED → 1 DISCOVERED → 2 RUNTIME_AVAILABLE → 3 REACHABLE → 4 CAPABILITY_UNKNOWN → 5 READY`；**仅靠观察永远到不了 `READY`**（32 种证据组合的穷举测试固定这一点）。
- **本机实测**：Ollama 11434 / LM Studio 1234 / ComfyUI 8188 **无任何监听** → `NOT_OBSERVED`（不是 `DISCOVERED`）；8080 的自定义 HTTP 本地端点 → 第④级 `CAPABILITY_UNKNOWN`，监听者已识别（pid 16292、`pythonw.exe`、模型 `qwen3.8-flash-next-iq3_xxs`），**推理未运行**。该服务是 **Strata**，**只观察、未注册、未绑定**。
- **自定义 HTTP 本地注册必须人工确认**：`custom_http_local_registration(user_confirmed=True)`，否则 `CUSTOM_HTTP_LOCAL_USER_CONFIRMATION_REQUIRED`；它只**准备描述符**，不注册、不启用、不生成任务（`generates_tasks=False`、`auto_enabled=False`）。
- **真实浏览器验收已在当前 HEAD 重跑**：**8 passed (14.4s)**，exit 0 —— 系统 Edge + 真实后端（8110）+ 真实 Vite，六个界面加 zh-CN 与键盘用例。后端 8110 是因为 8000 属 Windows 排除区间、8100 已被无关厂商服务占用。
- **媒体链路**只做了**契约预检**（86 passed / 79 skipped / 1 `BLOCKED_EXTERNAL`：本机无 `bash`），真实产物全部 `NOT_RUN` → `MEDIA_PIPELINE_RC_CHECKLIST.md`。
- **Windows / GPU** 部分只做到**清单与实测**（RTX 5080、驱动 591.74、16303 MiB；CUDA = `COMPONENT_FOUND_NOT_VERIFIED`），安装/打包与真实生成仍 `NOT_RUN` → `WINDOWS_GPU_RC_CHECKLIST.md`。
- **RC 结论：`NOT ESTABLISHED`**（未安装、未打包、未真实生成、未完整 CI）→ `PHASE11_RC_GATE_CLOSURE_REPORT.md`。