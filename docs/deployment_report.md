# Deployment Report

## 完成

Phase 0 审计；项目/目录/Git 模板；Compose PostgreSQL 与 Service；Schema/migration；Provider/Router；Canon 数据模型；Knowledge 原件；Agent Prompt；Context Builder；Workflow 蓝图；Profiles；样例小说；离线单元测试；备份/恢复/迁移/导入导出脚本；核心文档。

V0.2/V0.3：Runtime/Model Registry、Ollama/Mock Streaming、Provider 状态、`/api`、Generation Job/SSE/Cancel、Draft Diff/Accept、Agent Registry、React/TipTap Writer UI、Context/Canon Inspector 与 Pending Canon 审批组件。

## PARTIAL

Dify 未安装；Ollama/Docker/PostgreSQL Runtime 未安装；Cloud Key 缺失；FastAPI/Node 项目依赖未安装。故真实后端、前端 build、容器、Ollama 与 Cloud 均 NOT VERIFIED。Anthropic/Gemini 原生 Adapter、章节 Move/Duplicate/Delete、Import/Export UI、Edit+Approve、段落级 Diff、数据库 Repository 切换与结构化日志持久化仍待后续。

## 安全决定

没有安装系统组件、下载模型、停止容器、修改驱动或输出 Secret。PostgreSQL 采用非默认主机端口 54329；正文采用同目录临时文件 + `os.replace`。
