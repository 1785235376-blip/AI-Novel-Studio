# V1.0 实现状态（Windows DesktopHost 目标）

> 状态日期：2026-08-22  
> 这是一份开发验收记录，不是发布声明。当前版本仍未发布；已生成的 ZIP/EXE 只是内部验收快照，不是最终发行物。

## 总结

后端已经具备较完整的 V0.7 工程基础，但还没有达到 V1.0 完成态。`/api` 旧路由和 `/api/v1` 兼容路由同时保留；桌面端是正式验收目标，浏览器仅用于开发辅助。

## 已完成并已接入前端

| 能力 | 当前状态 | 备注 |
| --- | --- | --- |
| DesktopHost 安全会话 | 已实现 | 启动引导、会话交换、WebView 导航锁定、运行时 Provider 凭据白名单通道均已存在；密钥不进入前端持久化、日志、URL 或测试。 |
| API 兼容与错误合同 | 已实现 | 旧 `/api` 与 `/api/v1` 并行；统一错误体与 `X-Request-ID` 已接入。 |
| 小说/章节/版本/故事资料库 | 已实现 | 本机文件后端与协作 API 均有对应路径。 |
| 生成任务 | 已实现 | SSE、取消、重试、接受、幂等和断线恢复基础流程已接入。 |
| 导入 | 第一阶段完成 | TXT、Markdown、JSON、DOCX、PDF 预览与导入已接入；知识库候选不会自动写入，桌面端已提供基础接受/拒绝/暂缓审核窗口。 |
| 资产库 | 已实现 | 上传、列表、元数据、SHA-256、下载、删除、缩略图预览与幂等已接入；当前增加 25 MiB、文件名、MIME 校验。 |
| 影视制作链路 | 基础完成 | Screenplay → shots → storyboard → transitions → asset tasks 的 API 和桌面 UI 已存在。 |
| 导出任务 | 基础闭环完成 | 异步队列和 JSON/TXT/Markdown、DOCX/EPUB、PDF、剧本/镜头表/分镜确定性预览已接入；任务具备持久进度、取消、失败/取消重试、启动恢复、创建时不可变快照、来源版本、资源可用/缺失清单、权限上下文与服务自有 artifact（SHA-256）。PDF 在无可分发字体时使用标准 STSong-Light CID 回退，并保留严格嵌入字体门禁。 |
| 前端桌面壳 | 已实现 | 三栏 AppShell、固定“小说/图片/视频”模块切换、Token 化样式、状态反馈和错误展示已完成。 |

## 尚未完成（按优先级）

### P1：V1.0 验收前必须补齐

- 影视剧本、镜头表、分镜的行业标准排版和资源打包（当前已提供确定性预览与基础文档结构导出）。导出快照、资源缺失清单、服务自有 artifact 和分支权限校验已补齐；PDF 已可生成和下载，正式发行仍建议随包提供授权明确的 CJK 字体并开启严格嵌入字体门禁。
- 知识库候选审核的逐项编辑、审核记录持久化和再次打开恢复已补齐（GET/PUT review；旧 POST 兼容），仍可继续增加更细粒度的逐项字段审计。
- Windows DesktopHost 使用干净 WebView2 profile 的启动、Provider 凭据输入、资产库、导入、导出全流程验收。
- 干净环境全回归、真实 PostgreSQL parity、备份/恢复验证、Windows package smoke 和 checksum 记录。

### P2：已预留，后续接入

- Research Assistant 本地 sidecar CRUD 已接入窗口（筛选/编辑/版本冲突/删除确认，不读取外部网络）；评论、真实插件执行和 DAG 运行时仍待增强。
- Character Evolution 可手动记录到 sidecar，不会从正文自动抽取成长。voice/audio/video 窗口已挂接但 fail-closed；visual memory 未实现。
- 资产实体关联、派生缩略图和压缩包安全限制（基础单文件大小、文件名和 MIME 校验已完成）。
- Transition 的 camera motion、emotional reason、motion prompt 与连续性约束。
- 独立 screenplay 实体、版本和审计存储，以及发布前文档/版本清理。

## 前端预留窗口与服务归属

前端不会伪造尚未存在的结果。下列窗口已经显示服务归属和预留 API 前缀，后端补齐后可直接替换占位内容：

| 窗口 | 服务归属 | 预留 API |
| --- | --- | --- |
| 项目概览 | Project Overview / workspace summary | `/api/v1/novels/{id}/overview`（已接入真实计数、待处理项、近期活动和写作目标；不是占位） |
| 一致性检查 | Narrative Consistency Engine | `/api/v1/novels/{id}/continuity/scan-chapter`（主路径读当前章节正文+故事资料库；不依赖 `ENABLE_CONTINUITY_RULES`；JSON 粘贴仍在高级区。不是模型评审） |
| 研究资料 | Research Assistant | `/api/v1/novels/{id}/research`（durable sidecar `v1_capabilities/research.json` 已接入窗口；不读取外部网络） |
| 项目设置 | Provider / Plugin / Permission Manager | `/api/v1/providers`、`/api/v1/plugins` |
| 导出中心中的 PDF | Document Export Service | `/api/v1/exports`（PDF 已接入；严格嵌入字体与行业排版仍受发行门禁约束） |
| 能力路线图 | 多个待接入服务的统一导航 | 各卡片标注对应 `/api/v1` 前缀 |

## 验证记录

详细的验收矩阵、阻塞和冻结前门禁见 [`docs/v1_acceptance_status.md`](v1_acceptance_status.md)。

- 前端 TypeScript 检查：通过。
- 前端 Vite 生产构建：通过（开发验证目录；不是安装包）。
- 导出任务/API/错误合同聚焦测试：23 passed（环境警告除外）；导入、资产、影视制作链路聚焦回归 16 passed。
- 新增导出 snapshot/artifact 与知识库审核持久化聚焦测试：2 passed；portable staged entry 检查：2 passed。
- 前端完整 Vitest 回归：143 passed（40 个测试文件）；设计令牌检查通过（16 个样式文件）。桌面壳几何回归 3 passed，IMAGE/VIDEO 视觉基线 2 passed，冲突与版本恢复视觉流程 2 passed。
- NOVEL 视觉基线仍需设计审阅：当前导航已加入导入、资产库、导出中心和能力路线图等真实入口，生产截图与旧基线存在有意内容差异；未自动覆盖旧快照。
- 本地 Mock Provider 联调：通过；临时数据目录中完成创建小说 → 异步 TXT/DOCX/EPUB 导出 → `/api/v1` 下载（202 → succeeded → 200），并验证旧 `/api` 别名；未调用真实 AI。
- DesktopHost 协议、组合与进程聚焦测试：通过；验收 staging `r5e` 在中文路径和隔离 WebView2 profile 下达到 `DESKTOP_SESSION_READY`，trace 完成 runtime → core → bootstrap 200 → navigation；UTF-8 管道修复已进入 fresh host publish。仍需干净 Windows 窗口级 Provider/资产/导入/导出人工验收。
- DesktopHost 打包进程安全边界聚焦测试：19 passed（使用内存凭据后端）；正式打包后端会清理常见 Provider 环境密钥，并强制 `CREDENTIAL_VAULT_BACKEND=memory`，凭据只在本次进程生命周期内存在。
- 未调用真实 AI 服务，也未使用或写入任何真实 API Key。
