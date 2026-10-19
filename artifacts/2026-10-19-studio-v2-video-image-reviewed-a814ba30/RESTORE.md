# Restore bounded Video/Image combination

Hostbrowser/PG/real models/full E2E NOT_ACCEPTED. Inherited519a browser BLOCKED401 SESSION_REQUIRED; preview/Save/fresh reopen NOT_RUN. Condition5c5a/links/proxy/new DIF not included.

Unique prerequisite `d9b2ea4b602af099f133e7ef7e954fb7618979ae`: recover using prior `artifacts/2026-10-19-studio-v2-impact-graph-retry-reviewed-d9b2ea4b/RESTORE.md` and its prerequisite chain. Ordinary main/archive tree is not the product.

Verify SHA256SUMS first. In an independent Git database already containing d9:

```powershell
git bundle verify ./studio-v2-d9b2ea4b-to-a814ba30.bundle
git fetch ./studio-v2-d9b2ea4b-to-a814ba30.bundle refs/heads/work/v2-video-image-reviewed-20261019:refs/heads/recovered-video-image
git rev-parse recovered-video-image
git rev-parse 'recovered-video-image^{tree}'
git rev-list --count recovered-video-image ^d9b2ea4b602af099f133e7ef7e954fb7618979ae
git diff --name-only d9b2ea4b602af099f133e7ef7e954fb7618979ae recovered-video-image
git fsck --strict --no-dangling
```

Expect tip `a814ba30bfbd6d753267d6d0e07472f4302581ed`, tree `f901eb64ef09d4d91e8fc188eba7c3f4f781a600`,2 commits,29 paths and49 objects. Verify each file mode/blob/length/SHA256 and each new object type/size/cat-file digest against MANIFEST. ZIP evidence-index hashes cover its evidence payloads. No full source export or credential/model execution is needed for recovery.
