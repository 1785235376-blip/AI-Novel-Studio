# Restore advisory portable cache budget

No real-user cache cleanup, Windows privilege/link changes, PG/Host/fullE2E acceptance. Windows1314 symlink runtime remains unaccepted; only static guards were inspected. Audio/U16 NOT_INCLUDED; schema7 DEFAULT OFF.

Unique prerequisite `19d90d51eed4a9683c4290592dd91495125e5fcf` comes from `artifacts/2026-10-20-studio-v2-plugin-resource-reviewed-19d90d51/RESTORE.md` at archive `7f0d2f98047463102b3f2d920f2b7e31ba11d2aa` and its prior chain. Ordinary main/archive report checkout is not the product. Verify SHA256SUMS. In an independent Git database already containing19d90d51:

```powershell
git bundle verify ./studio-v2-19d90d51-to-9ce5e243.bundle
git fetch ./studio-v2-19d90d51-to-9ce5e243.bundle refs/heads/work/v2-portable-budget-reviewed-20261020:refs/heads/recovered-portable-budget
git rev-parse recovered-portable-budget
git rev-parse 'recovered-portable-budget^{tree}'
git rev-list --count recovered-portable-budget ^19d90d51eed4a9683c4290592dd91495125e5fcf
git diff --name-only 19d90d51eed4a9683c4290592dd91495125e5fcf recovered-portable-budget
git fsck --strict --no-dangling
```

Expect exact original `9ce5e243f925f6fb5141046758045c59b1dca46f`, tree `2255f4321611f125b0a7a12da1f52f9a61df6f6e`,1 commit,8 paths,18 objects. Verify file modes/blobs/lengths/SHA256 and every new object type/length/cat-file digest against MANIFEST. ZIP evidence-index.json hashes every other payload and records original source hashes. Do not replay the patch onto this already retained source commit.

Adapt combined/run-validation.py local paths only to a newly isolated workspace with authorized existing dependencies. It selects3 disposable original File fixture cases and2 Mock panel cases plus one TS/build. All data/profile/basetemp must stay below owned .runtime; memory credentials/offline/mock settings are recorded. No symlink runtime test, real user cache, installed Host or PG is needed. The first collection-only stop and corrected module-prefix selection are retained; it did not execute extra tests or change product source.
