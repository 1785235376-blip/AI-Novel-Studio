# AI Novel Studio V0.7.0 Engineering Edition

本地优先、可迁移的混合 AI 长篇小说生产系统。PostgreSQL 保存已批准事实，Markdown 保存正文，开放文件保存知识源；本地/云端模型只是可替换计算能力。Dify 是可选编排层，核心数据不依赖 Dify。

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

## 开源许可

本项目自有源码以 **Apache License 2.0**（SPDX: `Apache-2.0`）发布，见 [LICENSE](LICENSE) 与 [NOTICE](NOTICE)。第三方依赖、字体、模型权重与用户作品的边界见 [LICENSING_AND_THIRD_PARTY.md](LICENSING_AND_THIRD_PARTY.md)：用户小说（`novel_data/`，未被 Git 跟踪）不属于本许可证授权范围，模型权重与字体二进制不随仓库分发。

## 早期 Alpha 源码锚点（v0.1.0-alpha）

Git 注释标签 `v0.1.0-alpha` 是本项目早期公开工程源码快照的锚点，**不是 V1.X RC1、不是 V2 正式版，也不是产品验收 PASS**。该快照只包含 main 上已存在的 V0.7.0 Engineering Edition 源码与许可文件，V2 功能仍在独立分支开发；内部版本号（`release/version.json`、`pyproject.toml`、`frontend/package.json`）保持 `0.7.0`，不以 Tag 冒充正式发布版本。详见 [ALPHA_BASELINE_NOTES.md](ALPHA_BASELINE_NOTES.md)。

## Studio 双画布与单次图像任务

创作画布组织素材与作品位置；选中已保存图片卡片后进入本次图像任务的执行画布，对照时可显式分屏。参数沿原图像任务接口生效，预览、入队、执行、候选审核与采用分别确认。修改单次任务不会写入共享模板；云端未开放的内部步骤保持不可见。

本地图生图路径在入队和执行前分别核对真实命令、来源版本、配方和影响范围。确认只用于当前输入与原预览；输入、来源、范围、客户端或任务版本变化会使旧确认失效，不会自动派发或重放不确定任务。已审核候选通过原记录回到精确卡片，采用前重新核验；历史恢复创建新版本并保留原历史。

源码闭包、类型检查和软件回执测试不等于真实模型推理、GPU、PostgreSQL、原生桌面或安装包验收。真实生成取决于用户配置与明确授权；费用与资源估算缺失时显示未知。此分支不是安装包或正式发布承诺。

公开源码副本保留 `frontend` 中的 `dev`、`build`、`test` 命令。本次精确清单未包含可选的视觉/E2E与开发审计运行器，因此不会在此副本中列出这些未交付的命令；这不代表这些验收已经执行。

## Studio 已保存音频卡片的 WAV 截取

已保存音频卡片可沿原 AudioJob 编辑截取起止毫秒，在入队和实际执行前分别确认本次输入与影响范围。截取使用本机已安装的 FFmpeg，输出 PCM16 WAV；候选须显式审核，再核验并采用到记录中的原卡片。重开后读取原任务，不会自动执行或采用；来源或画布版本冲突会阻断回填。

公开测试用源码合成短 WAV 与软件回执，不包含用户音频或录制输出。真实 CPU 截取验证不代表 TTS 模型、GPU、外部服务、PostgreSQL 或原生桌面已验收。


### Saved video-card CPU trim

Studio can edit one saved video card with the original Timeline owner: explicit apply, preview-bound create/execute confirmations, local FFmpeg processing, candidate playback/review, exact-card CAS adoption, reopen recovery and canvas history restore. The fixed output is silent H.264 MP4 at 640x360/25fps, on a 40ms input grid, up to 120 seconds; source audio is not preserved. This is CPU editing, not video generation or a complete node editor. Source-generated frontend software fixtures are separate from the Python synthetic-video native FFmpeg test. Real model/GPU, external providers, PostgreSQL and live desktop Host E2E are not certified by this increment.


### 双画布：源音轨、音频效果与历史差异

已保存的视频卡片截取可明确选择保留所选范围内的**第一条源音轨**，经原 Timeline/FFmpeg 重新编码为 AAC；这不是无损复制，也不保留全部音轨。省略选项保持原静音行为，源视频没有音轨却要求保留时拒绝执行。音频卡片可编辑有界增益和线性淡入/淡出，输出仍为 48 kHz、双声道 PCM16 WAV；省略与明确 0 保持区分。修改后须重新预览并确认，入队与执行分别确认，不自动执行或采用结果。

历史版本选择会显示资产 pin、卡片布局、分组、视窗等元数据差异，明确确认后由原 CAS owner 创建新版本；不会重新生成或回滚素材。调用者须维持原父 owner 合同：记录/定义改变时推进 owner token，不在同一 owner、同一 version/digest 下原地改写 pin。Panel 自身对这种违约原地 A→B→A 尚未持续观察排队闭包；父 owner-token 更替对照通过。现有证据没有证明标准入口 CAS 或权限绕过，不宣称 standalone Panel 覆盖任意原地写入。

验证边界：本地已安装 FFmpeg 的自建短视频/WAV CPU 处理，以及 React/SDK 软件 HTTP 夹具检查。CPU 截取和效果处理不等于真实 TTS 或视频模型推理。真实 provider/模型/GPU、Host/native GUI、PostgreSQL、本批发布安装包与远端 CI 均未在本增量中验收（NOT_RUN）。UNKNOWN 不重放，候选仍须人工审核并显式采用到原卡片。
