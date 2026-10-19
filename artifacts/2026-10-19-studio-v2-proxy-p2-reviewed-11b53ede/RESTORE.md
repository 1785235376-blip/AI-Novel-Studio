# Restore the P2-fixed proxy batch

Use final tip with609 fix; the historical first proxy commit alone has the known source-switch P2. Schema7 DEFAULT OFF. PG/real models/full E2E/Hostbrowser remain NOT_ACCEPTED; inherited519a BLOCKED401 SESSION_REQUIRED, browser preview/Save/fresh reopen NOT_RUN.

Unique prerequisite `d109b9cd857415265b7acecfb19cf89143641cdc` is from `artifacts/2026-10-19-studio-v2-dif-graph7-reviewed-d109b9cd/RESTORE.md` at archive28c5bb2ef10fd17b2dac75acf141b00ef9abea58. Recover that chain first. Image,Video,DIF,schema7,links are already present; do not replay bec46. Ordinary main/archive report tree is not this product.

Verify SHA256SUMS, then in an independent Git database containing d109:

```powershell
git bundle verify ./studio-v2-d109b9cd-to-11b53ede.bundle
git fetch ./studio-v2-d109b9cd-to-11b53ede.bundle refs/heads/work/v2-proxy-after-dif-graph7-20261019:refs/heads/recovered-proxy-p2
git rev-parse recovered-proxy-p2
git rev-parse 'recovered-proxy-p2^{tree}'
git rev-list --count recovered-proxy-p2 ^d109b9cd857415265b7acecfb19cf89143641cdc
git diff --name-only d109b9cd857415265b7acecfb19cf89143641cdc recovered-proxy-p2
git fsck --strict --no-dangling
```

Expect final `11b53ede67259f7c2d81fb495e1b1dcfdfb7ce9c`, tree `6809bcd13d9d739228e05a5abf2e6c1a21086401`,2 commits,15 files,32 objects. Verify file mode/blob/length/SHA256 and each new object type/size/cat-file digest against MANIFEST. ZIP payload hashes are in evidence-index.json. No full source export, credential, model or GPU change needed for recovery.
