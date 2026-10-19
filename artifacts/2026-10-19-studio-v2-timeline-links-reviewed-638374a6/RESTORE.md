# Restore the separate links batch

Hostbrowser/PG/real models/full E2E NOT_ACCEPTED. Inherited519a remains BLOCKED401 SESSION_REQUIRED; preview/Save/fresh reopen NOT_RUN. Condition5c5a/proxy/new DIF excluded.

Unique prerequisite `a814ba30bfbd6d753267d6d0e07472f4302581ed` is the product from prior `artifacts/2026-10-19-studio-v2-video-image-reviewed-a814ba30/RESTORE.md` in archive e49db23f9e7cdeb6ffb560d4d4a986133066221d. Recover its chain first. Ordinary main/archive report tree is not this product.

Verify SHA256SUMS. In an independent Git database already containing a814:

```powershell
git bundle verify ./studio-v2-a814ba30-to-638374a6.bundle
git fetch ./studio-v2-a814ba30-to-638374a6.bundle refs/heads/work/v2-video-image-links-reviewed-20261019:refs/heads/recovered-timeline-links
git rev-parse recovered-timeline-links
git rev-parse 'recovered-timeline-links^{tree}'
git rev-list --count recovered-timeline-links ^a814ba30bfbd6d753267d6d0e07472f4302581ed
git diff --name-only a814ba30bfbd6d753267d6d0e07472f4302581ed recovered-timeline-links
git fsck --strict --no-dangling
```

Expect tip `638374a689f9cc0c022b0d5603c1c1d8724111a3`, tree `0906c267813ac7f67a8da4f317f288005459cfd6`,1 commit,12 files,22 new objects. Check all file mode/blob/length/SHA256 and object type/size/cat-file digest against MANIFEST, and every ZIP payload against evidence-index.json. No full source export, model or credential is needed for recovery.
