# Restore the reviewed WebP product

Unique prerequisite `9d95cabbd111718e55063ef61f4b9249410a2432`. If needed, restore it via preceding `artifacts/2026-10-19-studio-v2-storyboard-camera-reviewed-9d95cabb/RESTORE.md` and its prerequisite chain. Ordinary main or the archive report tree is not the product tree.

After checking SHA256SUMS, in an isolated Git repository containing that prerequisite:

```powershell
git bundle verify ./studio-v2-9d95cabb-to-6b9be9c8.bundle
git fetch ./studio-v2-9d95cabb-to-6b9be9c8.bundle refs/heads/work/v2-local-media-capability-20261019-night5:refs/heads/recovered-cutout-webp
git rev-parse recovered-cutout-webp
git rev-parse 'recovered-cutout-webp^{tree}'
git diff --name-only 9d95cabbd111718e55063ef61f4b9249410a2432 recovered-cutout-webp
git fsck --strict --no-dangling
```

Expected commit `6b9be9c852f4ac68509f56f64c2abc2df95ae02c`, parent `9d95cabbd111718e55063ef61f4b9249410a2432`, tree `359e9261ee0813997d977baaef34ef7adfb19387`, one new commit and eleven reviewed paths. Verify every final file and incremental object against MANIFEST via ls-tree/cat-file without exporting full source/history. IMAGE-17 remains PARTIAL; PG and full E2E not accepted.
