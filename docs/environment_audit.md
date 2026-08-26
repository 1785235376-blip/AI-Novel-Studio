# 环境审计（2026-08-09）

## 结果

| 项目 | 状态 |
|---|---|
| Windows | Windows 11（用户提供；受限会话无法读取 CIM 详细版本） |
| CPU / RAM | i9-13900 系列（用户提供）；RAM 数值未能从受限会话读取 |
| GPU | NVIDIA GeForce RTX 4060 Laptop GPU，8188 MiB VRAM |
| NVIDIA / CUDA | Driver 572.42；nvidia-smi 报告 CUDA 12.8 |
| Docker / Compose | Missing |
| WSL2 | 命令存在，但系统提示尚未安装 Linux/WSL 组件 |
| Ollama / 模型 | Missing；无模型列表可读 |
| Git | 2.53.0.windows.3（Codex bundled） |
| Python / Node | 系统 PATH 未发现；Codex 临时运行时可用于开发验证，但不应作为部署依赖 |
| PostgreSQL / Dify | 未发现 CLI、容器或可复用实例 |
| 端口 | 80/443/3000/3001/5001/5432/8000/8080/11434 未发现监听冲突 |
| 磁盘 | 受限会话未返回 CIM 数值；安装前需人工确认至少 30GB 空闲 |
| Cloud Provider | OpenAI/Anthropic/Google/Gemini/DeepSeek/OpenRouter 均 Missing（未输出任何 Key） |
| 工作区 | `D:\小说` 初始为空，可安全创建 `AI-Novel-Studio` |

## 安全部署方案

不修改驱动、不重置 Docker/WSL、不停止未知服务、不批量下载模型。先安装 Docker Desktop/WSL2 与 Ollama；使用独立 Compose project、容器名、named volume 和宿主绑定目录；PostgreSQL 主机端口用 54329。4060 只常驻一个 Q4 级 7B/8B 模型，共享 Utility/Writer/Review 角色。默认开发期先用 LOCAL_ONLY；配置一个 Cloud Provider 后再切 HYBRID。安装前再次检查磁盘和端口。

