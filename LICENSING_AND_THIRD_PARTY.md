# 许可范围与第三方声明

本文件是仓库根目录 [LICENSE](LICENSE)（Apache License 2.0）的**边界说明**，本身不授予任何额外权利。若本文件与 `LICENSE` 正文冲突，以 `LICENSE` 为准；若与第三方组件自身的许可证冲突，以该组件自身的许可证为准。

- 项目：AI-Novel-Studio / PoemSeed Studio
- 代码库：<https://github.com/1785235376-blip/AI-Novel-Studio>
- 许可证：Apache License 2.0，SPDX 标识符 `Apache-2.0`
- 版权持有人：`1785235376-blip`（GitHub 仓库所有者；项目 Git 历史中的提交来自该账户或其自动化 Coding Agent 提交）
- 版权年份：2026（仓库首次提交为 2026-08-26）
- `LICENSE` 正文：Apache-2.0 标准文本，11,357 字节，SHA256 `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4`

> 说明：以上权利信息来自本仓库可核对的 Git/GitHub 事实，未虚构个人或组织法律名称。如权利人希望在版权行中补充法定名称，可直接修改 `LICENSE`/`NOTICE` 的版权行，这不改变许可证条款。

## 1. 许可证覆盖范围

以下项目自有内容按 Apache-2.0 发布（除文件内另有声明者）：

- 后端与本地协议源码：`app/`、`local_interop_protocol/`、`local_interop_desktop/`、`interop-reference/`、`desktop-host/`、`native/`
- 前端源码：`frontend/src/`、`frontend/tests/`、`frontend/e2e/` 及各 Playwright/Vite/Vitest 配置
- 契约与模式：`contracts/`、`schemas/`
- 脚本与工程配置：`scripts/`、`.github/`（含 CI 工作流与本地检查工具）、`config/`、`database/`
- 提示词与示例工作流：`prompts/`、`workflows/`
- 测试：`tests/`（其中人工生成或项目自产的测试素材）
- 文档与工程证据：`docs/`、根目录 Markdown 文档、`AI_NOVEL_STUDIO_*.md` 等
- 项目自产的 UI 截图、Playwright trace、日志归档与压缩证据包

“自有”指本仓库历史中由本项目作者编写的内容，不含第三方复制片段。当前审计未发现被复制进来的第三方源码目录；依赖通过 `pyproject.toml` 与 `frontend/pnpm-lock.yaml` 管理，不 vendor 进仓库。

## 2. 明确不在本项目许可证覆盖范围内的内容

| 类别 | 内容与位置 | 依据 / 处理 |
| --- | --- | --- |
| 用户作品 | `novel_data/` 下用户小说、导入稿件、导出文档（`novel_data/` 未被 Git 跟踪；仓库不包含用户小说正文） | 版权归用户所有，随源码发布不构成对用户作品的授权 |
| 模型权重 | 仓库不含 `.gguf`/`.safetensors`/`.onnx`/`.pt` 等权重文件 | 模型由用户按其自身许可证在本地取得；本项目只做发现与调用 |
| 第三方依赖 | Python（pip）与 Node（pnpm）依赖及其传递依赖 | 各自许可证；见第 3 节兼容性审查 |
| 字体 | `assets/fonts/OFL.txt` 是 **Noto Sans SC** 的 SIL OFL 1.1 许可文本；字体二进制**不在仓库内** | 见第 4 节 |
| 第三方工具证据 | `docs/delivery/**` 中的 Playwright trace、压缩包、模型许可证文本摘录 | 仅为工程证据；其中第三方名称/商标仅作指称，不表示背书或再许可 |
| 名称与商标 | “AI Novel Studio”、“PoemSeed Studio”、界面标识 | Apache-2.0 第 6 条不授予商标或名称许可 |

## 3. 直接依赖许可证（Apache-2.0 兼容性审查）

后端直接依赖（`pyproject.toml`；括号内为审计时本机安装版本及其元数据声明的许可证）：

| 依赖 | 用途 | 许可证 |
| --- | --- | --- |
| fastapi（0.141.1） | HTTP API | MIT |
| uvicorn（0.52.1） | ASGI 服务器 | BSD-3-Clause |
| psycopg / psycopg-binary（3.3.4） | PostgreSQL 驱动 | LGPL-3.0-only（作为独立库动态使用，不作为本项目源码的一部分再许可） |
| sqlalchemy（2.0.51） | ORM | MIT |
| httpx（0.28.1） | HTTP 客户端 | BSD-3-Clause |
| pydantic-settings（2.15.0） | 配置 | MIT |
| reportlab（5.0.1） | PDF 导出 | BSD（ReportLab BSD 许可） |
| pypdf（6.19.0） | PDF 处理 | BSD-3-Clause |
| jsonschema（4.26.0） | 契约校验 | MIT |
| pytest（9.1.1） | 测试（开发依赖） | MIT |
| keyring（可选 extra `vault`） | 系统凭据保险库 | MIT（上游声明） |
| fonttools（可选 extra `fontbuild`/`comic`） | 字体派生 | MIT（上游声明） |
| opentimelineio（可选 extra `otio`） | 时间线交换 | Apache-2.0（上游声明） |
| Pillow（可选 extra `comic`） | 图像处理 | MIT-CMU |

前端直接依赖（`frontend/package.json`，许可证读取自安装包 `package.json`）：

| 依赖 | 许可证 |
| --- | --- |
| react、react-dom、@tanstack/react-query、@tiptap/*、zustand、vite、vitest、jsdom、fountain-js、@testing-library/react | MIT |
| lucide-react | ISC |
| typescript、@playwright/test | Apache-2.0 |

上述均为宽松/弱 copyleft 许可证，与以 Apache-2.0 发布本项目源码兼容。**本项目不分发第三方依赖源码**；分发打包产物时须同时遵守各依赖自身许可证（含 LGPL 组件的可替换性要求）。

## 4. 字体边界

- PDF 字体流程只使用 Google Fonts 固定修订的 **Noto Sans SC**（SIL Open Font License 1.1），由 `scripts/prepare_pdf_font.py` 按固定 SHA256 下载、校验并派生 Regular 字重；字体文件不随仓库提交。
- 仓库中的 `assets/fonts/OFL.txt` 即该字体上游 OFL 文本（SHA256 `1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9`），保留用于合规。
- OFL 要求：修改后的字体不得使用原保留字体名发布；本项目只在本地构建产物中使用派生字体，不作为独立字体产品分发。

## 5. 模型与 Provider 边界

- 仓库不包含模型权重，不自动下载模型，不调用收费 API。
- 模型许可证在调用前由 Model Center/Provider 准入流程审查；用户需自行确认本地模型（Ollama/llama.cpp/其他）的许可证。
- `docs/delivery/v2-development/m4c-real-cpu/licenses/Qwen-Apache-2.0.txt` 是历史审查证据（记录已审阅 Qwen 系列模型的 Apache-2.0 许可证文本），不表示仓库分发该模型。

## 6. 贡献与入站许可

提交贡献即表示你有权提交该内容，并同意按 Apache-2.0（与本项目 `LICENSE` 相同）授权本项目使用、修改与再分发；提交第三方代码、字体、图片、模型或测试素材时必须在 Pull Request 中说明来源与许可证，并更新本文件。详见 [CONTRIBUTING.md](CONTRIBUTING.md)（社区基建分支）。

## 7. 报告许可问题

如发现本仓库包含未获授权的内容，或本文件中的边界描述与事实不符，请通过仓库 Issue 模板（非敏感信息）说明具体文件与权利依据；安全类问题请按 `SECURITY` 渠道私下报告，不要在公开 Issue 中粘贴密钥、真实作品或个人路径。
