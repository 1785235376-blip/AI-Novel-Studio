# Restore reviewed cloud authoring batch

Required product prerequisite: `9ce5e243f925f6fb5141046758045c59b1dca46f` from [the pinned prior restore instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/9d1228ca855342035ae2c86a2837b8e96f7dc849/artifacts/2026-10-20-studio-v2-portable-cache-budget-reviewed-9ce5e243/RESTORE.md), including its prior chain. Main and archive checkouts are not the product. Never apply a patch on top of already retained commits.

Verify SHA256SUMS in this artifact directory, then in an independent Git database already containing the prerequisite:

```sh
git bundle verify /path/to/studio-v2-9ce5e243-to-b8371a48.bundle
git fetch /path/to/studio-v2-9ce5e243-to-b8371a48.bundle refs/heads/work/cloud-authoring-reviewed-20261020:refs/heads/recovered-cloud-authoring
git rev-parse recovered-cloud-authoring
git rev-parse 'recovered-cloud-authoring^{tree}'
git rev-list --count recovered-cloud-authoring ^9ce5e243f925f6fb5141046758045c59b1dca46f
git fsck --strict --no-dangling
```

Expected tip `b8371a48816b852176d45151eb9a0e3618a32c07`; tree `d1abbaaf64d7fd95535ad75ea2470fa288a35579`; six commits (four original feature commits plus two integration-only merges); twenty changed paths; 60 new objects. MANIFEST.json binds every file and every introduced raw Git object payload by object ID, type, byte length and SHA256. Extract verify_package.py from the evidence ZIP and run `python verify_package.py ARTIFACT_DIRECTORY RESTORED_GIT_REPOSITORY` to verify payloads, files, objects, original commit ancestry, ZIP entry hashes and strict fsck.

Integration and author sources retain their original Git IDs. The two merges changed no reviewed final blob. Dependencies and browser binaries are excluded. Follow the evidence ZIP reproduction notes only in an authorized environment; do not bypass the documented browser denial.

All limits in REPORT.md apply. Host, PostgreSQL, real codecs, Windows/native and full E2E are not accepted. The inherited standalone model ABA diagnostic remains failing and is not a production-host claim. Unpublished Audio/U16 inputs are not included.
