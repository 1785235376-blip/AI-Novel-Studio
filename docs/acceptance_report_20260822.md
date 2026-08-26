# AI-Novel-Studio Windows DesktopHost 内部验收报告

日期：2026-08-22  
范围：Windows DesktopHost、打包运行时、前端生产构建、后端异步导出/导入/资产闭环。  
结论：**内部验收快照可复现；不是 V1.0 公共发布。** 清单中的 `public_release` 为 `false`，版本为 `0.7.0 beta`。

## 交付物

| 物件 | 路径 | SHA-256 |
| --- | --- | --- |
| ZIP 验收包 | `D:\小说\AI-Novel-Studio-v1.0-acceptance-20260822-final\AI-Novel-Studio-Windows-DesktopHost-acceptance.zip` | `4EDE43F424CF09EFB706ACC14C8D07F5CAE288DD2D594E5703F36549876ED7F2` |
| EXE 外层安装器 | `D:\小说\AI-Novel-Studio-v1.0-acceptance-20260822-final\AI-Novel-Studio-Windows-DesktopHost-acceptance-setup.exe` | `52B601C50A67BDACDFCD8EA84FFBAA35DA4168947BC09C9957EE3212829C822D` |
| 包清单 | `D:\小说\AI-Novel-Studio-v1.0-acceptance-20260822-final\acceptance-package-manifest.json` | `B2AD3C1302E312AC432E700083C7BA21A8AD8008541F9B9E772C8625BF8D1D58` |

启动入口：`Package\Application\Launcher\Launch-AI-Novel-Studio.cmd`。安装脚本默认将应用放在当前用户的 `%LOCALAPPDATA%\Programs\AI-Novel-Studio`，用户数据与应用目录分离。

## 已通过

- DesktopHost 隔离启动：`APPLICATION_READY=true`、前端 `200`、DesktopHost `SESSION_READY`、正常回收 `exit_code=0`，只保留 loopback 监听，敏感值暴露计数为 0。
- 最终包复验：直接从 `...-final\Application` 启动得到 `application_ready=true`、`frontend=true`、`public_listeners=0`、`secret_exposure=0`、`exit_code=0`（端口为每次运行随机的 loopback 端口）。
- 中文路径与 UTF-8 管道：`hostdiag-unicode-r5e` 进入 WebView2 core 后完成本地 bootstrap；不再出现旧的 `DESKTOP_ENVELOPE_FAILED`。
- ZIP 内置安装脚本：隔离用户目录安装 exit 0，必需的 DesktopHost、Backend、Runtime/Python、Frontend、Launcher 文件齐全；从安装后的 Application 目录再次通过 `APPLICATION_READY`。
- DesktopHost provenance：最终 Application 中的 DLL SHA-256 与 fresh host publish / provenance manifest 一致（`07069966D8B3064DC984BDD53FF1D660B4A75CE3800752044463F0519A130873`）；最终包内没有 broken junction/reparse entry。
- 前端：TypeScript、生产 Vite 构建、Vitest 40 文件/143 测试、设计令牌守卫通过。
- 后端/打包聚焦：DesktopHost、导出 snapshot/artifact、知识库审核持久化、Windows 安装器测试合计 33 项聚焦回归通过；后端既有全量基线为 586 passed、22 skipped，剩余 Windows Credential Manager 失败是当前沙箱 WinError 1312。
- 功能闭环：`/api` 与 `/api/v1`、统一错误/request ID、幂等、TXT/Markdown/JSON/DOCX/EPUB、剧本/镜头表/分镜预览、资产上传/预览/下载/删除、导入审核记录均已接入；测试使用本地 Mock/确定性数据，没有调用真实 AI 服务。

## 仍需关闭的门禁

1. 在干净交互式 Windows 窗口中逐项记录 Provider 密钥输入、资产上传/预览/下载/删除、TXT/Word/PDF/EPUB/影视文档导出；本报告的协议和启动证据不能替代窗口级人工验收。
2. PDF 正式 artifact、可分发且授权明确的 CJK 字体/渲染器，以及影视行业标准排版和资源打包仍未完成。
3. PostgreSQL parity、备份恢复、全新机器依赖安装、性能/安全冻结门禁仍待执行。
4. IExpress EXE 已在隔离用户目录完成安装并干净 exit 0；仍需在干净交互式 Windows 做一次窗口级复核。PDF/行业排版和人工 UI 门禁仍未关闭。

## 凭据与发布边界

没有使用、输出、写入或请求任何真实 API Key。Provider 密钥只能在 DesktopHost 运行时进入进程内内存通道；不进入前端持久化、日志、URL、测试、导出物或包清单。该快照不应被称为“V1.0 已发布”，也不应直接作为公共发行物分发。
