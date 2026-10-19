# Incremental restoration

Prerequisite: an existing verified repository containing commit `333f384a125068a4e7714b347f687f5dc2034123` and its reachable objects. That base was published by the prior archive directory `artifacts/2026-10-19-studio-v2-ordinary-page-timeline-host333f-9b-recovery` at archive commit `14a7779e126565e74ca73679e8d71ecee9393281`. This small bundle intentionally does not duplicate that prior recovery chain.

After verifying every SHA256SUMS entry in the downloaded directory, run in an isolated repository that has the prerequisite:

```sh
git bundle verify /absolute/path/studio-v2-nle-333f-to-8c1b4b19.bundle
git fetch /absolute/path/studio-v2-nle-333f-to-8c1b4b19.bundle refs/heads/work/v2-host-nle-combined-20261019:refs/heads/recovered-nle-8c1b4b19
git rev-parse recovered-nle-8c1b4b19
```

Expected head: `8c1b4b197e57ce7ae070f0e4f7d4e36c805a360f`. MANIFEST.json records its tree, three exact commit mappings, 18 final file blobs and SHA256 content hashes. Compare those after restoration. No tests need to run to verify the download/recovery; existing execution evidence is in the sanitized ZIP. Source and generated dist checks have separate meanings.

Opt-in smoke sources remain under `test-package/` inside the ZIP. They require the original application and an independently prepared synthetic local runtime; private Host/session configuration is deliberately not distributed. Keep temporary Playwright sources outside normal Vitest discovery and remove temporary copies after use.
