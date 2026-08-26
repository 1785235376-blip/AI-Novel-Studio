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

## 备份、恢复、迁移

运行 `scripts/backup.ps1` 生成含校验清单的备份；模型 blob 不复制。恢复使用 `scripts/restore.ps1 -BackupPath ...`，已有小说默认拒绝覆盖。4060→5080 使用 `scripts/migrate.ps1 -Destination ...`，新机器仅需重装模型并改 Profile。

## 测试

安装 Python 3.11+ 后执行 `python -m pip install -e .[dev]` 与 `python -m pytest`。详见 `docs/test_report.md`。
