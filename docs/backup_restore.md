# Backup & Restore

PostgreSQL 使用 named volume 保持运行持久性、pg_dump 提供可迁移备份。正文、Prompt、Workflow、配置与知识源从宿主目录复制并生成 SHA-256 清单。模型 blob 排除，仅复制 model_manifest。Restore 默认拒绝覆盖已有小说。

