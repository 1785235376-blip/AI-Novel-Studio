# Restore schema7 local author-draft recovery

Schema7 DEFAULT OFF. This is authoring-only localStorage recovery. Tests use JSDOM/Mock transport. Live Host, File/API, PG, models/GPU/fullE2E are not newly accepted.

Unique prerequisite `503e4a207de487eb8d6879790713c29f805a71ca` is recovered from `artifacts/2026-10-20-studio-v2-linked-trim-reviewed-503e4a20/RESTORE.md` at archive `28ff2fdbea9cb9b64040aa24dbce284f3b146a81` and its prior chain. Ordinary main/archive report checkout is not this product. Verify SHA256SUMS first. In an independent Git database already containing503e4a20:

```powershell
git bundle verify ./studio-v2-503e4a20-to-7883878a.bundle
git fetch ./studio-v2-503e4a20-to-7883878a.bundle refs/heads/work/v2-condition-draft-after-trim-20261020:refs/heads/recovered-condition-draft
git rev-parse recovered-condition-draft
git rev-parse 'recovered-condition-draft^{tree}'
git rev-list --count recovered-condition-draft ^503e4a207de487eb8d6879790713c29f805a71ca
git diff --name-only 503e4a207de487eb8d6879790713c29f805a71ca recovered-condition-draft
git fsck --strict --no-dangling
```

Expect `7883878ae862326ff3ca256d9a111d8462920fe0`, tree `e8d3774ccc3e9e75d7190b3429636ce77f9d807a`,1 commit,5 paths,11 objects. Check final file modes/blobs/lengths/SHA256 and object types/lengths/cat-file digests against MANIFEST. ZIP evidence-index.json hashes every other payload with original source hashes. Adapt combined/run-validation.py local paths for the three minimal recovery cases and one TS/build using authorized existing dependencies. No credentials/models/condition enablement needed.

Correction for prior trim restore metadata is included in corrections/PATH_COUNT_CORRECTION.md. The prior count is11; paths=10 remains retained as an explicitly corrected historical typo, with no old published bytes or hashes changed.
