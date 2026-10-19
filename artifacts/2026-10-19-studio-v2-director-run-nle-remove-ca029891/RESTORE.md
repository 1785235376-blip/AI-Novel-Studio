# Incremental recovery

Archive files are not the current product tree. First recover verified source `f4a5327866007efa0a6bd3261086114216955a7b` using the [previous public recovery instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/dcc952bc68974c648200f424a3e7d4973e6d9711/artifacts/2026-10-19-studio-v2-asset-producer-prompt-find-f4a53278/RESTORE.md), which in turn require verified02. Verify SHA256SUMS before using this bundle in an isolated repository with the complete f4 prerequisite.

```sh
git bundle verify /absolute/path/studio-v2-f4a53278-to-ca029891.bundle
git fetch /absolute/path/studio-v2-f4a53278-to-ca029891.bundle refs/heads/work/v2-director-run-f4-combined-20261019:refs/heads/recovered-director-nle-ca
git rev-parse recovered-director-nle-ca
git rev-parse 'recovered-director-nle-ca^{tree}'
git fsck --full --strict
```

Expected tip `ca029891abc51265b2f483414316c30ddfdacd08` and tree `3a078bf693c5991924670e9c40deecef091cb605`. The bundle has exactly one external prerequisite, `f4a5327866007efa0a6bd3261086114216955a7b`, and two source commits. MANIFEST.json records introduced-object hashes, both patch mappings and all12 final blobs. Do not reset or overwrite an existing user workspace. Local verification starts from a previously verified downloaded-public02 seed, downloads the immutable public02→f4 bundle and verifies f4, then restores this newly downloaded f4→ca bundle without alternates. No ca objects may exist before that final fetch.
