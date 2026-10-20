# Restore this conditional canvas slice

Schema7 DEFAULT OFF. Host real browser remains BLOCKED/NOT_RUN; PG/real models/full E2E NOT_ACCEPTED. Existing519a401 SESSION_REQUIRED remains unresolved. d946 linked splitting is not included.

Unique prerequisite `11b53ede67259f7c2d81fb495e1b1dcfdfb7ce9c` is recovered using prior `artifacts/2026-10-19-studio-v2-proxy-p2-reviewed-11b53ede/RESTORE.md` at archivea74c483993fef6bacc113354969b50d62d7baef5 and its chain. Ordinary main/archive report tree is not this product.

Verify SHA256SUMS. In an independent Git database already containing11b:

```powershell
git bundle verify ./studio-v2-11b53ede-to-98ce5423.bundle
git fetch ./studio-v2-11b53ede-to-98ce5423.bundle refs/heads/work/v2-conditions-canvas-reviewed-20261020:refs/heads/recovered-conditions-canvas
git rev-parse recovered-conditions-canvas
git rev-parse 'recovered-conditions-canvas^{tree}'
git rev-list --count recovered-conditions-canvas ^11b53ede67259f7c2d81fb495e1b1dcfdfb7ce9c
git diff --name-only 11b53ede67259f7c2d81fb495e1b1dcfdfb7ce9c recovered-conditions-canvas
git fsck --strict --no-dangling
```

Expect exact original `98ce5423e619e311aa574c73288bef8fe8fe1dd1`, tree `5209377b7cfae7f07ddd240b411ab11d362d1e4b`,1 commit,20 paths,31 objects. Verify every file mode/blob/length/SHA256 and new object type/size/cat-file digest against MANIFEST. ZIP payload hashes and source hashes are in evidence-index.json; public-content-safety.json records sanitization. Recovery needs no real credentials, model execution or global condition enablement.
