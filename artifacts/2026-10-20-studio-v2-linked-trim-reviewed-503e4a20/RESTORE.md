# Restore reviewed linked trim

Schema7 DEFAULT OFF. Host/HTTP/PG/models/render/full E2E NOT_ACCEPTED; inherited519a401 SESSION_REQUIRED unresolved. This is one saved1x VIDEO/AUDIO pair common-source-subinterval trim with fixed original timeline starts and offset; no extension/ripple/fade/transition.

Unique prerequisite `b3e5c546da946bb3557cc1122f7ecd0808f57223` comes from `artifacts/2026-10-20-studio-v2-linked-split-reviewed-b3e5c546/RESTORE.md` at archive `d92955d58d68b5d2bda23825bbbbe34d0bab6587` and its prior chain. Original d946 is already present via its b3e5 mapping and must not be reapplied. Ordinary main/archive report trees are not this product. Verify SHA256SUMS. In an independent Git database already containing b3e5:

```powershell
git bundle verify ./studio-v2-b3e5c546-to-503e4a20.bundle
git fetch ./studio-v2-b3e5c546-to-503e4a20.bundle refs/heads/work/v2-linked-trim-after-split-20261020:refs/heads/recovered-linked-trim
git rev-parse recovered-linked-trim
git rev-parse 'recovered-linked-trim^{tree}'
git rev-list --count recovered-linked-trim ^b3e5c546da946bb3557cc1122f7ecd0808f57223
git diff --name-only b3e5c546da946bb3557cc1122f7ecd0808f57223 recovered-linked-trim
git fsck --strict --no-dangling
```

Expect `503e4a207de487eb8d6879790713c29f805a71ca`, tree `5c7899d8f286a224e9d9745e53394f95800e215d`,1 commit,11 paths,21 objects. Check final mode/blob/length/SHA256 and new object type/size/cat-file digest against MANIFEST. ZIP evidence-index.json hashes every other payload and records original source hashes. No credentials/model execution/flag enablement required. Adapt combined/run-validation.py local paths to an isolated restored workspace with authorized existing dependencies to reproduce only the affected trim/split checks and one TS/build.
