# 增量恢复

唯一外部前置 `8e17abe2262333459bcfd8d59da4b1998ff3d5f7`。若无此前置，按同分支 `artifacts/2026-10-19-studio-v2-local-subgraph-frontend-reviewed-8e17abe2/RESTORE.md` 恢复既有链；普通main/归档工作树不是产品树。

先按SHA256SUMS核对下载文件，再在已有前置的隔离Git库内：

```powershell
git bundle verify ./studio-v2-8e17abe2-to-a9974f24.bundle
git fetch ./studio-v2-8e17abe2-to-a9974f24.bundle refs/heads/work/v2-audio-denoise-8e17-combined-20261019:refs/heads/recovered-denoise
git rev-parse recovered-denoise
git rev-parse 'recovered-denoise^{tree}'
git diff --name-only 8e17abe2262333459bcfd8d59da4b1998ff3d5f7 recovered-denoise
git fsck --strict --no-dangling
```

预期产品 `a9974f24e7c556e3379f750f50d621be1255a05f`，树 `b397cca10b3f8e0c0dcdeecd5218ced25ba1e3d3`，新增2提交，12个路径与MANIFEST.file_mapping一致。可只用 `git cat-file` / `git ls-tree` 核对对象和blob的类型、字节、SHA256及mode，无需导出整棵历史源码树。临时导出文件删除前，先核对相同blob已在保留Git库和下载bundle恢复库中。

测试包和原始红/绿日志见 denoise-tests-evidence-sanitized.zip。PG BLOCKED，真实语音质量及全E2E未验收。
