# Restore limited pin-fork code integration

**Browser BLOCKED:401 SESSION_REQUIRED; original19128/5322 services stopped; no confirmed available valid same-backend Host session. Authenticated feature preview/Save/fresh reopen NOT_RUN. PG/full E2E not accepted. Restoring this product does not complete these acceptance steps.**

Unique prerequisite `6b9be9c852f4ac68509f56f64c2abc2df95ae02c`. If needed use preceding `artifacts/2026-10-19-studio-v2-cutout-webp-reviewed-6b9be9c8/RESTORE.md` and its chain. Ordinary main/archive report tree is not the product tree.

After SHA256SUMS, in an isolated Git repository with that prerequisite:

```powershell
git bundle verify ./studio-v2-6b9be9c8-to-25f98394.bundle
git fetch ./studio-v2-6b9be9c8-to-25f98394.bundle refs/heads/work/v2-storyboard-pin-webp-combined-20261019:refs/heads/recovered-storyboard-pin
git rev-parse recovered-storyboard-pin
git rev-parse 'recovered-storyboard-pin^{tree}'
git diff --name-only 6b9be9c852f4ac68509f56f64c2abc2df95ae02c recovered-storyboard-pin
git fsck --strict --no-dangling
```

Expected `25f9839459a39f79634b6024d22a5e644ea10da9`, parent `6b9be9c852f4ac68509f56f64c2abc2df95ae02c`, tree `dad693abc7f85da648c8967847cd11876c5e87d7`, one new commit/five reviewed paths. Match MANIFEST file mode/blob/bytes/SHA256 and every incremental object using ls-tree/cat-file. No full source/history export needed. Do not create credentials or bypass auth to turn the retained blocker into claimed acceptance.
