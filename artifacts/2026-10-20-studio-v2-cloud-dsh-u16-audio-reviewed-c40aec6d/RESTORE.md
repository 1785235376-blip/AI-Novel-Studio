# Restore reviewed DSH U16 + Audio integration

Required product prerequisite: `b8371a48816b852176d45151eb9a0e3618a32c07` from [the pinned preceding archive](https://github.com/1785235376-blip/AI-Novel-Studio/blob/88fe0e10cd4c8c3892c5c3108056057133c4c46f/artifacts/2026-10-20-studio-v2-cloud-authoring-reviewed-b8371a48/RESTORE.md), including its original chain. Neither main nor the archive branch is the product tree. Keep the existing recovery refs and worktree changes.

Check SHA256SUMS, then use a separate Git database containing the verified prerequisite:

```sh
git bundle verify /path/to/studio-v2-b8371a48-to-c40aec6d.bundle
git fetch /path/to/studio-v2-b8371a48-to-c40aec6d.bundle refs/heads/work/cloud-dsh-integration-20261020:refs/heads/recovered-cloud-dsh-u16-audio
git rev-parse recovered-cloud-dsh-u16-audio
git rev-parse 'recovered-cloud-dsh-u16-audio^{tree}'
git rev-list --count recovered-cloud-dsh-u16-audio ^b8371a48816b852176d45151eb9a0e3618a32c07
git fsck --strict --no-dangling
```

Expected tip `c40aec6d7ccf5162bef7a2a054ff45b6baf2b13b`, tree `d1e9a1da44cc6beca2fa8daf6fb0e0a719c5b704`, nine new commits, 34 changed paths, 95 introduced raw Git objects and exactly one external prerequisite `b8371a48816b852176d45151eb9a0e3618a32c07`. MANIFEST.json binds every changed source blob and all introduced raw Git object payloads. The bundle PACK count also equals 95.

Extract verify_package.py from the evidence ZIP and run `python verify_package.py ARTIFACT_DIRECTORY RESTORED_GIT_REPOSITORY`. It checks payload and ZIP hashes, object IDs/lengths/SHA256, exact replay postimages and correction blobs, 28 preserved prior paths, all 3,437 final test source hashes, independent final receipt and strict fsck.

Six patch bodies are included for audit, not reapplication. Their original source commit IDs are declared metadata, not independently reconstructed identity; new replay commit IDs and parents are listed in the source-binding JSON. The separate corrective commit must remain in the recovered product. Original review-stage failed fixtures and historical status statements must not be treated as current product failures or new acceptance.

All REPORT.md limits apply. PostgreSQL, real Host, Windows/native, real model/GPU and full E2E remain unaccepted. No browser retry or bypass is requested. Dependencies are excluded and must be supplied through an authorized environment.
