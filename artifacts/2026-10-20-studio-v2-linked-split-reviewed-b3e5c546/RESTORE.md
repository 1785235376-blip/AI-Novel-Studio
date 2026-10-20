# Restore reviewed linked split

Schema7 DEFAULT OFF. Live Host/PG/models/full E2E NOT_ACCEPTED; inherited519a401 SESSION_REQUIRED unresolved. One saved1x VIDEO/AUDIO pair splits by common relative elapsed time, preserving offset.

Unique prerequisite `98ce5423e619e311aa574c73288bef8fe8fe1dd1` comes from `artifacts/2026-10-20-studio-v2-conditions-canvas-reviewed-98ce5423/RESTORE.md` at archive `99d759f0101c49593ff7d616f34c4942c06da47b` and its prior chain. Ordinary main/archive report trees are not this product. Verify SHA256SUMS. In an independent Git database already containing98ce:

```powershell
git bundle verify ./studio-v2-98ce5423-to-b3e5c546.bundle
git fetch ./studio-v2-98ce5423-to-b3e5c546.bundle refs/heads/work/v2-linked-split-after-conditions-20261020:refs/heads/recovered-linked-split
git rev-parse recovered-linked-split
git rev-parse 'recovered-linked-split^{tree}'
git rev-list --count recovered-linked-split ^98ce5423e619e311aa574c73288bef8fe8fe1dd1
git diff --name-only 98ce5423e619e311aa574c73288bef8fe8fe1dd1 recovered-linked-split
git fsck --strict --no-dangling
```

Expect `b3e5c546da946bb3557cc1122f7ecd0808f57223`, tree `ff7a6fefd5dffe60c8be201b24f05c092b541ecb`,1 commit,10 paths,20 objects. Check final modes/blobs/lengths/SHA256 and new object type/size/cat-file digests against MANIFEST. ZIP evidence-index.json hashes every other payload and records original source hashes. No credentials/model execution/flag enablement required. Adapt combined/run-validation.py local paths to an isolated restored workspace with authorized existing dependencies to reproduce only the four affected checks plus one TS/build.
