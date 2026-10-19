# Incremental recovery

Prerequisite: a verified repository containing `8c1b4b197e57ce7ae070f0e4f7d4e36c805a360f` and its reachable objects. The base is recoverable from the previous archive at `0c0ac1019244d3b7ad6913e46b33cee8155357ef`, directory `artifacts/2026-10-19-studio-v2-nle-multiselect-ime-cutnav-8c1b4b19`, whose own prerequisite is333f. This package does not duplicate that base chain.

Verify the downloaded SHA256SUMS, then run in an isolated repository with the prerequisite:

```sh
git bundle verify /absolute/path/studio-v2-ux-8c1b4b19-to-d78d5058.bundle
git fetch /absolute/path/studio-v2-ux-8c1b4b19-to-d78d5058.bundle refs/heads/work/v2-ux-combined-20261019:refs/heads/recovered-ux-d78d5058
git rev-parse recovered-ux-d78d5058
```

Expected head: `d78d50589a07f1ff428fbc9e93453f32876648d2`. MANIFEST.json records the expected tree, three fixed commit mappings and seven exact final file blobs/SHA256 hashes. Verify those after recovery; no application test rerun is required for download/bundle integrity verification. Component fixture limits and deferred full E2E remain unchanged.
