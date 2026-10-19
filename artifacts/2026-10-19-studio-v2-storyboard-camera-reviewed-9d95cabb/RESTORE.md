# 增量恢复

唯一前置 `a9974f24e7c556e3379f750f50d621be1255a05f`，可按同分支 `artifacts/2026-10-19-studio-v2-audio-denoise-reviewed-a9974f24/RESTORE.md` 恢复既有链。普通main/归档工作树不是产品版本。

下载后核对SHA256SUMS，在已具备前置的隔离Git库中：

```powershell
git bundle verify ./studio-v2-a9974f24-to-9d95cabb.bundle
git fetch ./studio-v2-a9974f24-to-9d95cabb.bundle refs/heads/work/v2-storyboard-camera-audio-combined-20261019:refs/heads/recovered-camera
git rev-parse recovered-camera
git rev-parse 'recovered-camera^{tree}'
git diff --name-only a9974f24e7c556e3379f750f50d621be1255a05f recovered-camera
git fsck --strict --no-dangling
```

预期提交 `9d95cabbd111718e55063ef61f4b9249410a2432`，树 `ed1b4d6228341d43a3aa225ae92cb4c701d31dad`，仅1新增提交、4前端路径。MANIFEST列出path/mode/blob/bytes/SHA256及所有新增对象；可直接用git cat-file/ls-tree核对，不导出整个历史树。临时导出删除前确认保留Git库、公开下载bundle恢复库中的blob完全一致。PG BLOCKED，完整E2E未验收。
