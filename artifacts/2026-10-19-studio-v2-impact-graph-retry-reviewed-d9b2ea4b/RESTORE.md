# Restore the limited DIF/GRAPH combination

**Full DIF02/GRAPH21, PG, models and full E2E are not accepted. DIF is intent only; GRAPH is explicit confirmed FAILED/schema1/pure-local new QUEUED admission only. Inherited519a browser BLOCKED401 SESSION_REQUIRED;19128/5322 services stopped, no confirmed available same-backend valid Host session; preview/Save/fresh reopen NOT_RUN.**

Unique prerequisite `25f9839459a39f79634b6024d22a5e644ea10da9`. If needed use previous `artifacts/2026-10-19-studio-v2-storyboard-pin-reviewed-25f98394/RESTORE.md` and its chain. Ordinary main/archive report tree is not this product.

After SHA256SUMS, in an independent Git repository containing the prerequisite:

```powershell
git bundle verify ./studio-v2-25f98394-to-d9b2ea4b.bundle
git fetch ./studio-v2-25f98394-to-d9b2ea4b.bundle refs/heads/work/v2-impact-graph-retry-combined-20261019:refs/heads/recovered-impact-graph-retry
git rev-parse recovered-impact-graph-retry
git rev-parse 'recovered-impact-graph-retry^{tree}'
git rev-list --count recovered-impact-graph-retry ^25f9839459a39f79634b6024d22a5e644ea10da9
git diff --name-only 25f9839459a39f79634b6024d22a5e644ea10da9 recovered-impact-graph-retry
git fsck --strict --no-dangling
```

Expect `d9b2ea4b602af099f133e7ef7e954fb7618979ae`, tree `dd365774d7c056b94464c0a2696d8c98f7a7e5a7`, exactly3 new commits and21 reviewed paths. Verify every final file mode/blob/bytes/SHA256 and every new object against MANIFEST with ls-tree/cat-file; no full source/history export needed. The historical unfixed GRAPH commit exists only as the preceding selected step; use the final tip containing2e. Do not infer full functional/browser acceptance or mint credentials from this recovery procedure.
