# 前端增量恢复与校验

本包唯一外部前置 `494cf355a4057a977e736fee4bb39130881cd089`。若尚无此前置，先按同分支 `artifacts/2026-10-19-studio-v2-local-subgraph-backend-494cf355/RESTORE.md` 的既有链恢复；本轮包没有重带该后端源码。普通 main/归档工作树不是产品前置。

在已有前置的独立仓库内，先对下载文件按 SHA256SUMS 校验，再执行：

```powershell
git bundle verify ./studio-v2-494cf355-to-8e17abe2.bundle
git fetch ./studio-v2-494cf355-to-8e17abe2.bundle refs/heads/work/v2-local-subgraph-client-review-fix-20261019:refs/heads/recovered-local-subgraph-frontend
git rev-parse recovered-local-subgraph-frontend
git rev-parse 'recovered-local-subgraph-frontend^{tree}'
git diff --name-only 494cf355a4057a977e736fee4bb39130881cd089 recovered-local-subgraph-frontend
git fsck --strict --no-dangling
```

预期产品提交 `8e17abe2262333459bcfd8d59da4b1998ff3d5f7`，直接父 `0ec1991024bd1ed4bac57a6ab61c0a3057aa3320`，树 `97dc9525587a7f0576eb332d2788eb4ef23fbd52`。只有两个新增提交、14个前端路径，与 MANIFEST.file_mapping 逐项核对 mode/blob/bytes/SHA256；所有新增对象的类型/bytes/SHA256 也在 MANIFEST.object_inventory。

原独立反例和红绿日志、必要测试包及验收边界位于 frontend-tests-evidence-sanitized.zip / TEST-PACK.md。还原代码不代表已验收 PG 或完整 E2E；PG状态为 BLOCKED。
