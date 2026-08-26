# Troubleshooting

- Docker Missing：安装并启动 Docker Desktop，不要重置已有数据。
- Ollama unavailable：确认 11434 与模型名，运行 model-check.ps1。
- HYBRID Key Missing：切 LOCAL_ONLY 或配置对应 Key。
- 54329 冲突：只修改本项目 POSTGRES_PORT。
- 500：先检查 `/health`、容器日志和 `.env` 字段，日志中不得粘贴 Key。

