# 4060 → 5080

旧机运行 backup/migrate，复制备份；新机安装 Docker/Ollama，restore，按 Manifest 重装模型，修改 Model Profile，运行 health-check。小说、Canon、Prompt、Workflow 不重建。4060 使用单个 7B/8B Q4；5080 可按需使用 14B Writer + 8B Utility，无需同时常驻。

