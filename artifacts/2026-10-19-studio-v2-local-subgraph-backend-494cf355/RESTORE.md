# Incremental source recovery

First recover source `3d14ade722814ea3b4472c1c166466597f3b53f5` using [the media predecessor instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/2f25ed1aaf4e5d585047d6fd310cb8c35fe3f68d/artifacts/2026-10-19-studio-v2-audio-loudness-polygon-mask-3d14ade7/RESTORE.md). This increment requires exactly that source prerequisite, not the ordinary archive checkout.

```sh
git bundle verify /absolute/path/studio-v2-3d14ade7-to-494cf355.bundle
git fetch /absolute/path/studio-v2-3d14ade7-to-494cf355.bundle refs/heads/work/v2-media-local-subgraph-combined-20261019:refs/heads/restored-local-subgraph-494cf355
git rev-parse restored-local-subgraph-494cf355
git rev-parse 'restored-local-subgraph-494cf355^{tree}'
git fsck --full --strict
```

Expected tip `494cf355a4057a977e736fee4bb39130881cd089`, tree `8dcd1b875f4dd87b4ac1bd8914ebe48de1a23495`; exactly1 introduced source commit,8 final backend files. Verify SHA256SUMS/MANIFEST first. Keep user workspaces intact. Publication verification uses a previously verified downloaded-public04 seed plus a freshly downloaded immutable public04→3d14 bundle, followed by this freshly downloaded3d14→494 bundle in a second isolated bare repository with no alternates and no494 commit before fetch.

Server-only depth1 current-pin local call, no frontend execution entry. PostgreSQL/full-subgraph acceptance is NOT_RUN.
