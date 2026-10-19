# Incremental recovery

First recover verified source `b484b528a1e3b66ab79947363914b5b75047a013` using [the previous public instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/757fcb9c16a1120f4e8dee0a971007e9f0269120/artifacts/2026-10-19-studio-v2-audio-timecode-3d-views-b484b528/RESTORE.md). Verify SHA256SUMS, then use an isolated repository with the complete b484 prerequisite.

```sh
git bundle verify /absolute/path/studio-v2-b484b528-to-cfc4264b.bundle
git fetch /absolute/path/studio-v2-b484b528-to-cfc4264b.bundle refs/heads/work/v2-plugin-docs-b484-combined-20261019:refs/heads/recovered-plugin-docs-cfc
git rev-parse recovered-plugin-docs-cfc
git rev-parse 'recovered-plugin-docs-cfc^{tree}'
git fsck --full --strict
```

Expected tip `cfc4264be11cdbc2811ffc8f38f688c866150e1c`, tree `42940eb3d75320872ed0b57cb1097228612e76f4`. The bundle contains2 source commits and exactly one external prerequisite `b484b528a1e3b66ab79947363914b5b75047a013`. MANIFEST.json records introduced object hashes, both patches and all4 final blobs. Archive ordinary files are not the current product source tree. Never reset/overwrite a user workspace. Verification uses the previously verified downloaded-publicca seed plus fresh immutable publicca→b484 download, then this newly downloaded b484→cfc bundle without alternates and with no cfc objects before its fetch.
