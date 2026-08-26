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

已知静态验证结果：

- 前端 `npm run build` 通过。
- Python 核心模块 `py_compile` 通过。
- Provider 回归测试 `tests/test_provider_retry.py` 为 3 passed。
- 插件执行运行时当前明确关闭，禁止假设插件可执行。
- 桌面端 UI 重构尚未开始，当前功能冻结后再进行。

请不要把构建通过等同于生产可用；重点指出真实 Provider、桌面运行和数据迁移方面的残余风险。
