# story-workflow-pack

这是 **Plugin Contract v1** 的声明式校验示例，不是可执行插件。

## 它做了什么

- 提供一份通过 Pydantic 合同与 JSON Schema 的 `manifest.json`
- 声明两个 JSON 资源：写作预设与工作流模板
- 资源带 SHA-256，供宿主完整性校验

## 它没有做什么

- **不包含** Python、JavaScript、Shell 或任何可执行入口
- **不请求** `network`、`process`、`filesystem.write` 或任何 `model.*` 权限
- **不能** 执行工作流、注册 Provider、读写小说正文或访问 Credential Vault
- **不是** 插件市场、安装器或更新通道

当前宿主状态仍是：

- `execution_mode = declarative`
- `execution_supported = false`
- `isolation = DENY_ALL`

请把本目录当作合同 / Validator 样例，而不是已经能跑的工作流包。
