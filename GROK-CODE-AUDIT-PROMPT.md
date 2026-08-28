# AI-Novel-Studio V1.0 Code Audit Prompt

请审计随附的 `AI-Novel-Studio` 代码快照。目标是判断当前项目是否达到 V1.0 可交付标准。

请重点检查：

1. 后端 API、数据模型、状态流转和异常处理。
2. 前端入口是否真正挂载，是否存在只创建但未使用的组件。
3. Provider、Credential Vault、Vision、图片生成、视频、TTS 的真实闭环风险。
4. Workflow、Agent 队列、插件 Manifest/权限/运行时隔离。
5. 资产库导入、关联、下载、失败重试和幂等性。
6. 影视化 Pipeline：剧本、场景、镜头、分镜、转场、Motion Task。
7. 安全问题：密钥泄露、任意文件访问、插件代码执行、SSRF、权限绕过。
8. 测试覆盖、构建稳定性、生产部署和桌面运行风险。

请不要修改代码。输出一份审计报告，按严重程度排序：

- Critical / High / Medium / Low findings
- 文件路径和行号
- 复现步骤或证据
- 影响范围
- 修复建议
- 已实现功能与未实现功能清单
- V1.0 阻塞项
- P0/P1/P2 开发优先级

请特别区分：

- 已有 API 但前端未挂载
- 只有 deterministic/mock Provider
- 真实 Provider 尚未验收
- 仅保存元数据但没有实际文件或模型执行
- 状态标记完成但没有真实业务结果

已知静态验证结果（必须与基线绑定；不要把过期数量或过期构建哈希当成当前证据）：

- 基线：`origin/main` `46bee8f4b57f0cc61d69746bf190a88a3fb3d733`，日期 2026-08-28，Linux 隔离沙箱，`STORAGE_BACKEND=file`，未配置真实 Provider，未连接用户数据库。
- 前端 TypeScript：`npx tsc -b` exit 0。
- 前端 Vitest：`npx vitest run` exit 0；本轮 376 passed / 89 files。该数量只对本轮 SHA/日期/环境有效。
- 前端 production build：`npx vite build` exit 0。
- 后端全量 pytest（`python -m pytest -p no:cacheprovider --basetemp=<repo>/.runtime/pytest-temp/safe-maint-20260828`）：exit 1；本轮 766 passed, 36 failed, 27 skipped, 0 xfail。分类见 `docs/test_report.md` 与 `docs/grok_safe_maintenance_audit_20260828.md`。
- 版本一致性：`scripts/validate_release_version.py` exit 0；backend / frontend / environment / `release/version.json` 均为 `0.7.0` / `0.7.0 Beta`。
- 插件执行运行时当前明确关闭。禁止假设插件可执行。Draft PR #12（declarative plugin SDK）未在本轮审核或合并。
- 桌面端 UI 重构已经发生（见 `docs/frontend_ui_ux_refactor_report.md` 等）。这不是 DesktopHost 窗口验收。DH-01 至 DH-08 仍为 `NOT_RUN`，DesktopHost 门禁仍为 `BLOCKED`。

请不要把构建通过等同于生产可用；不要把浏览器、API、Playwright 或启动日志冒充 DesktopHost 窗口业务证据。重点指出真实 Provider、桌面运行和数据迁移方面的残余风险。当前产品声明仍是 `0.7.0 Beta`，不是 V1.0 正式发行物。
