# Incremental recovery

First recover source `cfc4264be11cdbc2811ffc8f38f688c866150e1c` using [the previous public instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/be2d22425fae339c34a0754a0784b8889534e155/artifacts/2026-10-19-studio-v2-plugin-refresh-dev-docs-cfc4264b/RESTORE.md). Verify SHA256SUMS, then use an isolated repository containing the complete cfc prerequisite.

```sh
git bundle verify /absolute/path/studio-v2-cfc4264b-to-d6d1259d.bundle
git fetch /absolute/path/studio-v2-cfc4264b-to-d6d1259d.bundle refs/heads/work/v2-graph-comic-model-cfc-combined-20261019:refs/heads/recovered-graph-comic-model-d6
git rev-parse recovered-graph-comic-model-d6
git rev-parse 'recovered-graph-comic-model-d6^{tree}'
git fsck --full --strict
```

Expected tip `d6d1259d95cbd95335f38d98deb12f443d4f1d08`, tree `78e4f6a50ace1bef19c96bd478ab94a42bbea807`. Exactly4 source commits and one external prerequisite `cfc4264be11cdbc2811ffc8f38f688c866150e1c`. MANIFEST.json contains introduced-object hashes,4 patch mappings, stage mappings and14 final file blobs. The archive ordinary tree is not the current product tree. Never reset/overwrite a user workspace. Verification starts from the previously verified downloaded-public b484 seed, freshly downloads the immutable public b484-to-cfc bundle, then downloads this cfc-to-d6 bundle into a second isolated repository with no alternates and no d6 object before fetching it.
