# Restore readonly plugin resource and developer entry slices

Mock resource reads and static Git-snapshot docs validation only; installed plugin Host/PG/fullE2E and execution/marketplace/whole-ecosystem acceptance are excluded. Schema7 DEFAULT OFF.

Unique prerequisite `a8ac7dff36c94e3b58d2edc7116708ef4e42f742` is recovered from `artifacts/2026-10-20-studio-v2-bound-draft-reviewed-a8ac7dff/RESTORE.md` at archive `c6a263ff355c024dced9726592e8eda9187e470d` and its prior chain. Ordinary main/archive report checkouts are not the product. Verify SHA256SUMS. In an independent Git database already containinga8ac7dff:

```powershell
git bundle verify ./studio-v2-a8ac7dff-to-19d90d51.bundle
git fetch ./studio-v2-a8ac7dff-to-19d90d51.bundle refs/heads/work/v2-plugin-resource-docs-reviewed-20261020:refs/heads/recovered-plugin-resource
git rev-parse recovered-plugin-resource
git rev-parse 'recovered-plugin-resource^{tree}'
git rev-list --reverse recovered-plugin-resource ^a8ac7dff36c94e3b58d2edc7116708ef4e42f742
git diff --name-only a8ac7dff36c94e3b58d2edc7116708ef4e42f742 recovered-plugin-resource
git fsck --strict --no-dangling
```

Expect product `19d90d51eed4a9683c4290592dd91495125e5fcf`, tree `27e7584a5f5603debc630e4a634342b0a1eb337c`,2 commits ordered15a4b52c then19d90d51,7 paths,15 objects. Both source commits are already retained; do not replay their patches on this tip. Verify final file modes/blobs/lengths/SHA256 and every new object type/length/cat-file digest against MANIFEST. ZIP evidence-index.json hashes every other entry and records original source hashes.

Adapt combined/run-validation.py and check-docs.py local paths in an isolated restored workspace using authorized existing dependencies. Include the two tracked tests/fixtures JSON files already listed by the worktree setup. Only3 Mock resource tests,4 static Git-snapshot links and one TS/build are selected. No Host/model/credential or plugin installation/execution is required. Static link checks do not establish public HTTP availability.
