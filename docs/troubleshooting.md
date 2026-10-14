# Troubleshooting

- Docker Missing：安装并启动 Docker Desktop，不要重置已有数据。
- Ollama unavailable：确认 11434 与模型名，运行 model-check.ps1。
- HYBRID Key Missing：切 LOCAL_ONLY 或配置对应 Key。
- 54329 冲突：只修改本项目 POSTGRES_PORT。
- 500：先检查 `/health`、容器日志和 `.env` 字段，日志中不得粘贴 Key。

## Phase9 实测环境事实（2026-10-14，V2 Studio / `feature/v2-narrative-platform`）

以下条目均为**本机真实执行**中遇到并核实的问题，供发布前排查使用；**未**修改任何测试来绕过它们。

- **浏览器验收全部失败（连不上页面）**：Vite 在本机只绑定 **IPv6 `[::1]:5173`**。用 `http://127.0.0.1:5173` 会整批失败；请设 `STUDIO_ACCEPTANCE_BASE_URL=http://localhost:5173`。排查：`netstat -ano | findstr :5173`。
- **不想下载浏览器**：验收入口默认使用**已安装的系统浏览器**（`channel=msedge`，可用 `STUDIO_ACCEPTANCE_CHANNEL=chrome`）。**不要**运行 `playwright install`（会下载）。本机 `%LOCALAPPDATA%\ms-playwright` 不存在也能跑通。
- **后端端口 8000 绑定失败**：端口 8000 落在 Windows 排除区间（`netsh interface ipv4 show excludedportrange` 含 `8000 8000`）。请换端口（本阶段用 8100）并让前端 `V061_API_URL` 指向它。
- **仓库既有 e2e 配置跑不起来**：`frontend/playwright.config.ts` 硬编码 `../.venv\Scripts\python.exe`（本机不存在）。请创建该 venv 或改用 `playwright.studio-release.config.ts`；**不要**改测试绕过。
- **Vite 静默退出**：曾在验收运行中 `exit 1` 且无报错，导致偶发失败；重跑前先确认端口仍在监听。
- **STUDIO 界面显示"不要重复派发/结果未知"**：这是**正确**行为（UNKNOWN 不重放）。不要用重试按钮绕过；请读取原回执。
- **素材/导出读取显示"未核实"**：owner 未声明该关系时的**正确**呈现（不猜测）。见 `docs/v2/ux-product/DECISIONS.md` D13。
- **AI 任务显示 UNKNOWN 而非失败**：owner 未定义该状态时的**正确**呈现；FAILED 与 EMPTY 是不同状态。
- **本地模型未被发现**：Model Center 只呈现 owner 事实，**不会**自行探测或下载。Phase9 实测本机 Ollama(11434)/LM Studio(1234)/ComfyUI(8188) 均未运行，PATH 无 `ollama`/`llama-server`，探测目录内无 GGUF/Safetensors。端口 8080 有服务响应但身份未证实。请先启动你自己的本地运行时。
- **`ffmpeg`/`ffprobe` 相关测试在本机失败**：`tests/test_v2_media_prerequisites.py` 的合成 shim 是 POSIX shebang 脚本，属**测试自身不可移植**（真实 ffmpeg 存在于 `D:\ffmpeg`）；`tests/test_v2_audio_wav_controls.py` 另有 2 项 96 kHz 边界失败。二者均为**既有环境级**，不代表产品缺陷，也不得为通过而改断言。
- **PostgreSQL 验收怎么跑**：本项目可复用既有便携 PostgreSQL（`D:\PoemSeed\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL\bin`，16.15），用 `scripts/run_v2_postgres_checks.py` 启动 owned 集群（非特权回环端口），**不要**安装系统级服务。


