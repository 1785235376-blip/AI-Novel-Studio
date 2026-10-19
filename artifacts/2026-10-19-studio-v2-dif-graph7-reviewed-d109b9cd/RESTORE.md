# Restore the bounded DIF/schema7 combination

Schema7 DEFAULT OFF. This is File/API proof, not browser/full E2E; PG/real models/GPU not accepted. Inherited519a BLOCKED401 SESSION_REQUIRED; preview/Save/fresh reopen NOT_RUN. Proxy excluded.

Unique prerequisite `638374a689f9cc0c022b0d5603c1c1d8724111a3` comes from `artifacts/2026-10-19-studio-v2-timeline-links-reviewed-638374a6/RESTORE.md` at archive84654bcd677c231b36e41990a4981c01fabd600f. Recover that chain first. It already contains original Video a667, Image and links. Ordinary main/archive tree is not the product.

Verify SHA256SUMS, then in an independent Git database containing638:

```powershell
git bundle verify ./studio-v2-638374a6-to-d109b9cd.bundle
git fetch ./studio-v2-638374a6-to-d109b9cd.bundle refs/heads/work/v2-dif-graph7-combined-20261019:refs/heads/recovered-dif-graph7
git rev-parse recovered-dif-graph7
git rev-parse 'recovered-dif-graph7^{tree}'
git rev-list --count recovered-dif-graph7 ^638374a689f9cc0c022b0d5603c1c1d8724111a3
git diff --name-only 638374a689f9cc0c022b0d5603c1c1d8724111a3 recovered-dif-graph7
git fsck --strict --no-dangling
```

Expect tip `d109b9cd857415265b7acecfb19cf89143641cdc`, tree `bc7772ccbfda6c89b56ea7853e3b140836e3afeb`,4 new commits,22 paths,52 objects. Verify each file mode/blob/length/SHA256 and each object type/size/cat-file digest against MANIFEST. ZIP hashes are in evidence-index.json. Do not replay a667 or author local dependency copies ee694b4b/6c836692. No credential/model/OS change is needed for object recovery.
