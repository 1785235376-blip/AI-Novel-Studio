# Incremental recovery

First recover source `d6d1259d95cbd95335f38d98deb12f443d4f1d08` using [the previous public instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/11de2c3b8f5e07ea67377aa90c38f66bb2b99b33/artifacts/2026-10-19-studio-v2-graph-reconnect-comic-group-model-price-d6d1259d/RESTORE.md). Verify SHA256SUMS and use an isolated repository containing the complete d6 prerequisite.

```sh
git bundle verify /absolute/path/studio-v2-d6d1259d-to-04fd0fa4.bundle
git fetch /absolute/path/studio-v2-d6d1259d-to-04fd0fa4.bundle refs/heads/work/v2-graph-budget-comic-d6-combined-20261019:refs/heads/recovered-graph-budget-comic-04
git rev-parse recovered-graph-budget-comic-04
git rev-parse 'recovered-graph-budget-comic-04^{tree}'
git fsck --full --strict
```

Expected tip `04fd0fa47a8349510aaf0fcbebbc776d60ac21b7`, tree `c8f98275af6e00f7382aa118707e5d10716f75ed`. Exactly3 source commits and one external prerequisite `d6d1259d95cbd95335f38d98deb12f443d4f1d08`. MANIFEST.json includes introduced-object hashes,3 patch/stage mappings and14 final blobs. The ordinary archive tree is not current product source. Never reset or overwrite a user workspace. Verification uses the previously verified downloaded-public cfc seed, freshly downloads the immutable public cfc-to-d6 bundle, then downloads this d6-to-04 bundle into a second isolated repository with no alternates and no04 tip object before fetching it.
