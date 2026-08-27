# V1.0 Windows DesktopHost 验收状态

> 状态：开发验收记录（2026-08-22）。本文件不是发布公告；当前生成的是内部验收包，不是正式发行物，也不能据此宣称 V1.0 已发布。

## 验收结论

当前版本可以在本地模拟数据上验收主要创作、导入、资产和导出路径；DesktopHost 的启动引导、安全会话和 WebView2 隔离 profile 已在验收 staging 上通过，但还不能通过 V1.0 冻结门禁。DesktopHost 是正式目标，浏览器只用于开发辅助。

本次桌面启动证据使用 `D:\小说\AI-Novel-Studio-v1.0-acceptance-20260822-final`（验收 staging，不是发布安装包）及运行时目录 `D:\小说\AI-Novel-Studio-desktop-acceptance-runtime-r5e`。目录名称中的 `final` 仅表示本轮验收快照，不代表 V1.0 发布。

验收 ZIP 快照路径为 `D:\小说\AI-Novel-Studio-v1.0-acceptance-20260822-final\AI-Novel-Studio-Windows-DesktopHost-acceptance.zip`；对应 EXE 外壳为同目录下的 `AI-Novel-Studio-Windows-DesktopHost-acceptance-setup.exe`。二者只用于本地验收和复现，不是最终发行物。

| 验收域 | 结果 | 证据/说明 |
| --- | --- | --- |
| `/api` 与 `/api/v1` 兼容、统一错误体、request ID | 通过 | 双前缀路由、`X-Request-ID` 和 `{detail,code,message,details,request_id}` 已接入 |
| 导入与知识库审核 | 通过（基础闭环） | TXT/Markdown/JSON/DOCX/PDF 解析；候选不自动写入；审核记录支持 GET 恢复、PUT 编辑、POST 接受/拒绝/暂缓 |
| 资产库 | 通过（基础闭环） | 上传、元数据、SHA-256、认证下载、删除、缩略图；单文件 25 MiB、文件名/MIME/base64 安全校验 |
| 异步导出 | 通过（已实现格式） | JSON/TXT/Markdown、最小 DOCX/EPUB、剧本/镜头表/分镜预览；队列进度、取消、重试、启动恢复、幂等 |
| 导出可追溯性 | 通过（基础闭环） | 创建时不可变 snapshot、章节来源版本、资源 available/missing 清单、分支权限上下文、artifact SHA-256 |
| DesktopHost 凭据边界 | 通过（协议/安全测试） | Provider 密钥只由桌面运行时输入；不进入前端持久化、日志、URL、测试或导出；正式打包后端使用进程内 vault |
| DesktopHost 启动与安全会话 | 通过（验收 staging） | `host.status=DESKTOP_SESSION_READY`；trace 依次包含 `WEBVIEW_RUNTIME_FOUND`、`WEBVIEW_CORE_READY`、`BOOTSTRAP_HTTP_200`、`BOOTSTRAP_READY`、`NAVIGATION_COMPLETED`。运行时使用中文路径，UTF-8 管道和隔离 profile 校验已通过 |
| DesktopHost Provider/资产/导入/导出 UI 逐项验收 | 待人工逐项 | 本轮证据覆盖启动、会话交换和 WebView 导航；Provider 凭据输入、资产上传/预览/下载/删除、导入审核和各格式导出仍需在 DesktopHost 窗口逐项记录，不能用浏览器或协议测试替代 |
| ZIP 安装与安装后启动 | 通过 | ZIP 内置 `Install-AI-Novel-Studio.ps1` 在隔离用户目录 exit 0；安装后的真实 Application 目录再次达到 `APPLICATION_READY`，前端加载、回收、loopback 与敏感值检查均通过 |
| IExpress EXE 外壳 | 通过（隔离验收） | 采用 .NET ZipFile 解压后，外层 EXE 在隔离用户目录完成安装并干净 exit 0；快捷入口和必需运行时文件齐全 |
| PDF 正式导出 | 已实现（基础闭环） | API 可生成、持久化并下载有效 PDF artifact；运行时优先使用可嵌入字体，无字体时使用标准 STSong-Light CID 回退；严格发行模式可拒绝未嵌入字体 |
| 标准影视剧本/镜头表/分镜 | 未完成 | 当前为确定性预览和 CSV/Markdown，尚未完成行业排版与资源打包 |
| PostgreSQL parity（运行时实例） | 通过（目标回归） | bundled PostgreSQL 16.4 实例按正式 packaged migration runner 完成基线采用与 017 迁移；repository/lore/identity/concurrency/context 聚焦回归 **27 passed, 4 skipped**。仍需在全新环境执行一次完整安装、备份恢复和 checksum 门禁 |
| 干净环境、备份恢复、Windows package smoke/checksum | 未完成/待环境 | 需在可写的干净 Windows 环境执行；当前只生成内部验收快照，不是最终发行物 |

## 已验证命令结果

- 后端聚焦：导出、DOCX/EPUB、导入审核、资产安全、API alias、协作边界及新增 snapshot/review 测试共 **34 passed**（环境警告除外）。
- 影视制作链路在隔离可写数据目录下复验通过：剧本、镜头、分镜生命周期 **4 passed**；默认中文工作区数据目录的失败是沙箱权限问题，不是业务断言失败。
- 后端全量（README 修复前的同一代码基线）：**586 passed, 22 skipped, 3 failures**；其中 2 项为当前沙箱 Windows Credential Manager 返回 WinError 1312，1 项为随后已补齐的 `packaging/portable/README.md` 缺失。README 补齐后 `tests/test_windows_portable_entry.py` 为 **2 passed**。
- 前端 TypeScript、生产构建、令牌守卫及已记录的壳几何/IMAGE/VIDEO/冲突/版本视觉回归均通过；NOVEL 旧视觉快照因真实新入口造成有意内容差异，需设计审阅后再更新。
- 本地 Mock Provider 完成创建小说 → 异步 TXT/DOCX/EPUB → 下载的 202/成功/200 链路；没有调用真实 AI 服务，也没有使用或写入真实 API Key。
- DesktopHost 协议、组合、进程和打包安全边界聚焦测试通过；验收 staging `r5e` 已进一步完成真实 WebView2 profile 启动并达到 `DESKTOP_SESSION_READY`。`hostdiag-unicode-r5e` 证明中文路径和 UTF-8 管道可用；未调用真实 AI 服务。
- DesktopHost 验收 staging 路径：`D:\小说\AI-Novel-Studio-v1.0-acceptance-20260822-final`；对应 host publish：`D:\小说\AI-Novel-Studio-v1.0-acceptance-20260822-final-host-publish`。这些是开发验收快照，不是最终发布包。
- Windows portable/desktop 关键门禁聚焦回归：**18 passed**（portable entry、packaged migrations、bridge、composition）；版本一致性校验返回 backend/frontend/environment 均为 `0.7.0`。本地沙箱临时目录不可写时会产生环境错误，改用隔离可写临时目录后通过。
- canonical final `Package\Application` 复验同样返回 `application_ready=true`、`frontend=true`、`public_listeners=0`、`secret_exposure=0`、`exit_code=0`；EXE 外壳隔离安装 exit 0。
- 最终快照 SHA-256：ZIP `4EDE43F424CF09EFB706ACC14C8D07F5CAE288DD2D594E5703F36549876ED7F2`；EXE `52B601C50A67BDACDFCD8EA84FFBAA35DA4168947BC09C9957EE3212829C822D`。清单 `acceptance-package-manifest.json`（`B2AD3C1302E312AC432E700083C7BA21A8AD8008541F9B9E772C8625BF8D1D58`）标记 `public_release=false`、版本 `0.7.0 beta`。

## 冻结前阻塞清单

1. 在干净 Windows 环境逐项完成 DesktopHost Provider 输入、资产上传/预览/下载/删除、导入审核和 TXT/Word/PDF/EPUB/影视文档导出，并记录窗口级证据；r5e 已覆盖启动引导、安全会话、中文路径和 WebView2 profile，但不替代这些人工 UI 验收。
2. 为正式发行包选择可随产品分发且授权明确的 CJK 字体并开启严格嵌入字体门禁；基础 PDF artifact、清理、缺失资源和失败恢复测试已通过。
3. 完成标准影视文档排版、资源打包及导出版本/审计展示。
4. 在干净 PostgreSQL、备份恢复和全新 Windows staging 环境重复关键路径，并记录依赖哈希和 checksum。
5. 通过 P0/P1 安全审查、性能门禁和需求追踪矩阵后，才进入冻结；冻结之前不宣称或分发最终发行物。本轮生成的 ZIP/EXE 仅为内部验收快照。

## 前端预留能力与后端归属

这些窗口可以访问，但对尚未实现的服务只显示明确的预留状态，不伪造结果。后续服务可沿现有 `/api/v1` 前缀替换占位实现。

| 窗口 | 归属服务 | 当前 API/状态 |
| --- | --- | --- |
| 项目概览 | Project Overview / workspace summary | `/api/v1/novels/{id}/overview`，已接入真实计数/待处理项/近期活动/写作目标；DesktopHost 窗口项仍待 Windows 人工验收 |
| 一致性检查 | Narrative Consistency Engine | `/api/v1/projects/{project_id}/continuity/*`，基础检查已存在，证据定位仍需补齐 |
| 研究资料 | Research Assistant | `/api/v1/novels/{id}/research`，sidecar CRUD 已接入；窗口级 DH-03/DH-04 仍待 DesktopHost 验收 |
| 设置与插件 | Provider / Plugin / Permission Manager | `/api/v1/providers` 已有基础状态；插件权限管理预留 |
| PDF 与标准影视导出 | Document Export Service | `/api/v1/exports` 已有异步生命周期；PDF 基础闭环已接入，行业标准排版仍待发行门禁 |
| 角色成长与视觉记忆 | Character Evolution / Visual Memory | `/api/v1/characters/{id}/evolution`、`/api/v1/memory`，预留 |
| 工作流与发布门禁 | Workflow / Release Gate | `/api/v1/workflows`、`/api/v1/release-gate`，预留 |
