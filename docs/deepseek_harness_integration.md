# DeepSeek Harness 主控集成边界

## 已确认的上游能力

上游项目：<https://github.com/deepseek-ai/deepseek-harness>

- MIT License
- npm 入口：`@deepseek-ai/dsh`
- 默认以本地 Web 服务运行（`127.0.0.1:3080`）
- 架构是 Cordis 插件系统，官方标注为 developer preview，并明确提示可能发生兼容性破坏变更

## 本项目的集成策略

AI-Novel-Studio 不直接复制 Harness 源码，也不把预览版 Node 依赖打进 FastAPI DesktopHost。主程序保留当前 `GenerationRuntime` 和凭据保险库作为稳定边界；Harness 作为可选的本地主控运行时，通过受限适配器接入。

适配器必须满足：

1. 只把明确授权的工作区上下文发送给 Harness。
2. 默认只读；写入、删除、生成任务、发布和外部网络操作都需要独立工具权限与二次确认。
3. API Key 仍由当前运行时凭据保险库管理，不写入 Harness 配置文件、URL 或日志。
4. Harness 不可用时，控制中心继续使用现有只读 `/api/agent/chat`，不能阻塞写作流程。
5. 所有工具调用记录 provider、model、workspace scope、用户确认和结果摘要，禁止记录凭据与完整隐私上下文。

## 用户习惯记忆

现有 `MemoryService` 面向小说角色与世界记忆，不能直接承担用户偏好。用户习惯应使用独立命名空间（例如写作风格、默认章节长度、常用模型、确认偏好），并遵循：

- 仅保存用户明确确认或反复稳定表现出的偏好；
- 可查看、编辑、删除和一键关闭；
- 不混入小说 Canon、角色记忆或云端 Context Pack；
- 云端请求默认省略，只有用户明确授权才发送；
- 记录来源、时间和置信度，避免把一次性操作当作长期偏好。

## 后续实现顺序

1. 增加 `UserPreferenceService` 与本地持久化/删除 API。
2. 增加 Harness 本地进程健康检查和版本显示，不自动下载或静默启动第三方进程。
3. 定义只读上下文适配器和工具权限清单。
4. 在 DesktopHost 中增加明确的“启用 Harness”开关与首次授权确认。
5. 通过真实 Harness 进程和无 Harness 回退路径分别做回归验证。
