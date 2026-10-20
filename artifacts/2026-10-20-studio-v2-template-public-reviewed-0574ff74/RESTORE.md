# Incremental recovery: reviewed template + PUBLIC closure

First recover product `c40aec6d7ccf5162bef7a2a054ff45b6baf2b13b` and its complete prerequisite history using the [pinned preceding RESTORE](https://github.com/1785235376-blip/AI-Novel-Studio/blob/271f2e2f1ce2ee7c75c07d275b9945e2a92898f2/artifacts/2026-10-20-studio-v2-cloud-dsh-u16-audio-reviewed-c40aec6d/RESTORE.md). Its tree is `d1e9a1da44cc6beca2fa8daf6fb0e0a719c5b704`. The main/archive branch is not the current product checkout.

Use a fresh isolated repository containing that verified base. Do not reset an existing workspace. Check every SHA256SUMS entry before importing. Windows users can use Get-FileHash or the supplied Python verifier; on systems providing sha256sum run `sha256sum -c SHA256SUMS`.

```sh
git bundle verify /absolute/path/studio-v2-c40-to-0574.bundle
git fetch /absolute/path/studio-v2-c40-to-0574.bundle refs/heads/work/v2-template-review-fixes-20261020:refs/heads/recovered-template-public-0574
git rev-parse recovered-template-public-0574
git rev-parse 'recovered-template-public-0574^{tree}'
git rev-list --count recovered-template-public-0574 ^c40aec6d7ccf5162bef7a2a054ff45b6baf2b13b
git fsck --full --strict --no-dangling
python /absolute/path/verify_package.py /absolute/path/ARTIFACT_DIRECTORY /absolute/path/RESTORED_REPOSITORY/.git
```

For a bare repository pass its directory instead of `.git` to the verifier. Expected tip `0574ff74e4d0b40472d26a737172bfac7fec7f5f`, tree `6c4e7ebd30a1835457ab16787026ad7e7b7fefa1`, five new commits, 17 final changed source paths and 50 introduced raw Git objects. The bundle has exactly one external prerequisite: c40. Keep original 330 and 16f identities, their two-parent merge 3c4, separate faeb capacity fix and final 0574 same-batch fix.

`source-delta.zip` is an exact 17-file audit snapshot, not a full source distribution or patch to apply on top of the fetched commits. `evidence-exact.zip` retains historical failed and passing logs with their original bytes and registries; its provenance distinguishes coverage by the original registries. The current final acceptance and remaining limits are in REPORT.md. No dependency or executable installer is provided. Do not interpret deselected symlink/PG cases or mocked Host checks as native/real-Host acceptance.

Local verification used c40-only objects without alternates, confirmed that all five new commits were absent, then imported this exact bundle. Recovered objects, file identities, the merge tree and strict fsck passed. Publication has not occurred; this directory is prepared for review only. No main merge, tag, release, system-setting change or remote write is required to restore it.
