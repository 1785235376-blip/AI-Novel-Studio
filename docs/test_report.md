# Test Report

覆盖 Context 人物选择、Cloud Secret 省略/脱敏、年龄冲突、死亡人物、Secret Leak、Provider 回退、原子写入和 Pending Canon 闭环。

- PASS：全部 Python 文件 AST 语法校验。
- PASS：Context 只选择本章相关人物。
- PASS：LOCAL_ONLY Secret 原文从 Cloud Context 省略；REDACT_BEFORE_CLOUD 原文被约束占位符替换。
- PASS：年龄、死亡人物与提前泄密检查。
- PASS：Primary 不可用时回退 Local Provider。
- PASS：章节原子持久化、Summary 与 Pending Canon 文件生成。
- PARTIAL：捆绑 Python 未安装 pytest，故以无字节码等价断言脚本执行；正式环境仍应运行 `python -m pytest`。
- PARTIAL：Docker 重启、真实 Local/Hybrid、Dify、SQL dump restore/migration 因运行时依赖缺失未执行。

## V0.2/V0.3

- STATIC VERIFIED：新增 Python 文件 AST 通过；PowerShell 全部解析通过；前端必需结构存在。
- MOCK VERIFIED：Mock Streaming；生成完成前正文不变；Accept 后正文变更并产生 Pending Canon。
- PARTIAL：FastAPI 未安装，API 路由未做真实 ASGI 请求测试。
- PARTIAL：frontend node_modules 未安装，TypeScript/Vite/Vitest 未实际执行。
- NOT VERIFIED：Docker/PostgreSQL/Ollama/Cloud Provider/Dify。

## V0.4

- REAL VERIFIED：项目 Python 依赖安装；FastAPI 导入；TestClient health/novels 200。
- REAL VERIFIED：TypeScript 5.9.3 `tsc --noEmit`。
- LOCAL VERIFIED：Document round-trip、版本递增、409 冲突基础、History Restore、Job Repository。
- STATIC VERIFIED：全 Python AST、PowerShell parse。
- PARTIAL：pytest 8 项显示 100% 断言通过，但 runner 汇总后未退出并被外层超时终止。
- PARTIAL：Vite/Vitest 因沙箱拒绝 `.vite-temp` 写入而失败；依赖已经下载。
- NOT VERIFIED：Docker/PostgreSQL/Ollama/Cloud Provider。

## V0.4.5

- REAL VERIFIED：FastAPI TestClient 完整作者 API 流程。
- REAL VERIFIED：TypeScript type-check、Vite production build。
- REAL VERIFIED：Vitest 5/5。
- MOCK VERIFIED：Selection Rewrite→Draft→Accept→History→Pending Canon 编辑审批。
- NOT VERIFIED：真实 Ollama/Cloud、Docker/PostgreSQL、浏览器 E2E。

## V0.4.8.1 Repository Abstraction

- STATIC VERIFIED：Python AST、PowerShell、TypeScript。
- LOCAL VERIFIED：File Factory 共用 data root；postgres/unknown 不静默回退。
- LOCAL VERIFIED：旧 Path Context 与 ContextService 输出完全一致。
- LOCAL VERIFIED：Repository Contract 6/6 断言显示通过；pytest 仍有既知 teardown hang，外层超时终止。
- LOCAL VERIFIED：Services/Contracts 完整作者流程（Create→Save→Mock Rewrite→Accept→History→Pending→Approve→Restore）。
- PARTIAL：临时 Uvicorn HTTP 尝试超时，未作为通过证据。
- NOT VERIFIED：PostgreSQL Repository/Runtime（本阶段明确不实现）。
