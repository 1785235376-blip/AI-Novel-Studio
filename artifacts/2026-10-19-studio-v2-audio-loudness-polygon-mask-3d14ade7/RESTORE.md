# 增量恢复

本目录的 `studio-v2-04fd0fa4-to-3d14ade7.bundle` 是增量包，必须先有产品前置 `04fd0fa47a8349510aaf0fcbebbc776d60ac21b7`。普通 main 或归档分支的工作树不是该产品前置。

前置 04fd 的上一归档位于同一分支 `artifacts/2026-10-19-studio-v2-graph-groups-budget-recovery-comic-framing-04fd0fa4/`；按其中 RESTORE.md / MANIFEST.json 的链恢复（该包前置为 d6d1259d）。已有 04fd 的本地仓库可直接执行：

```powershell
git bundle verify ./studio-v2-04fd0fa4-to-3d14ade7.bundle
git fetch ./studio-v2-04fd0fa4-to-3d14ade7.bundle refs/heads/work/v2-audio-image-04fd-combined-20261019:refs/heads/recovered-audio-image-3d14ade7
git rev-parse recovered-audio-image-3d14ade7
git rev-parse 'recovered-audio-image-3d14ade7^{tree}'
git diff --name-only 04fd0fa47a8349510aaf0fcbebbc776d60ac21b7 recovered-audio-image-3d14ade7
```

预期提交 `3d14ade722814ea3b4472c1c166466597f3b53f5`，树 `07128c616b2e6808476db16a54d374cb455a75bf`，16 个路径与 MANIFEST.json 相同。先对下载文件运行 SHA256SUMS 校验，再逐项核对 MANIFEST 的文件 SHA256/Git blob、产品新增对象的类型/字节/hash。随后可用独立 worktree 查看恢复结果，不覆盖现有工作区。

测试、独立轻审探针和必要脱敏日志位于 evidence-sanitized.zip。evidence-inventory.json 记录原始/脱敏哈希；本包的组合 smoke 与作者历史证据分开。完整原套件没有在组合中重新执行。
