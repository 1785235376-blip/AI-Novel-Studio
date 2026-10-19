# Incremental recovery

First recover complete verified source `ca029891abc51265b2f483414316c30ddfdacd08` using [the previous public instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/179a7d9ffa16736c43728df3a5a2bdffb9a1fae8/artifacts/2026-10-19-studio-v2-director-run-nle-remove-ca029891/RESTORE.md). Verify SHA256SUMS before using this new bundle in an isolated repository.

```sh
git bundle verify /absolute/path/studio-v2-ca029891-to-b484b528.bundle
git fetch /absolute/path/studio-v2-ca029891-to-b484b528.bundle refs/heads/work/v2-audio-3d-ca-combined-20261019:refs/heads/recovered-audio-3d-b484
git rev-parse recovered-audio-3d-b484
git rev-parse 'recovered-audio-3d-b484^{tree}'
git fsck --full --strict
```

Expected tip `b484b528a1e3b66ab79947363914b5b75047a013`, tree `0691adf1c4bb64e85e2db789dcdd0418e117dce5`. There are3 source commits and exactly one external prerequisite `ca029891abc51265b2f483414316c30ddfdacd08`. MANIFEST.json records introduced object hashes, all3 patch mappings and all9 final blobs. The archive branch's ordinary tree is not the current product source tree. Never reset/overwrite a user workspace. Verification uses the previously verified publicf4 seed plus fresh immutable publicf4→ca downloads, then the newly downloaded ca→b484 bundle with no alternates and no b484 objects before its fetch.
