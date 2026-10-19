# Incremental recovery

Prerequisite: an independently verified repository containing `02a98cd3019e41cf80765cb1b0343c58daaf6a68` and its reachable source objects. The previous archive commit `787152a1e6db0c1a4c617a4f987df4bc90ee11cb` contains the02 prerequisite package. Retain its earlier recovery chain; this increment does not duplicate it.

Verify SHA256SUMS after downloading, then use a separate repository containing the prerequisite:

```sh
git bundle verify /absolute/path/studio-v2-02a98cd3-to-f4a53278.bundle
git fetch /absolute/path/studio-v2-02a98cd3-to-f4a53278.bundle refs/heads/work/v2-asset-prompt-02-combined-20261019:refs/heads/recovered-asset-prompt-f4a53278
git rev-parse recovered-asset-prompt-f4a53278
git fsck --connectivity-only --no-dangling
```

Expected head: `f4a5327866007efa0a6bd3261086114216955a7b`. MANIFEST.json records its exact tree, three commit mappings, seven changed file blobs and SHA256 hashes, full tree-entry digest and source blob count. Compare the restored tree and seven-file delta; every other02 file must remain unchanged. Verify all checksum entries and ZIP integrity. These are recovery checks, requiring no application test rerun. Component/compile evidence limits remain unchanged.
