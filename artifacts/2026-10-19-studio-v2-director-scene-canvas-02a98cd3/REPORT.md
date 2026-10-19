# Reviewed limited increment: scene Director handoff and catalog loading

Product base: `d78d50589a07f1ff428fbc9e93453f32876648d2`. Combined product: `02a98cd3019e41cf80765cb1b0343c58daaf6a68`; tree `4854c3dcad801f5f6bff768a37faa79c8d28adb9`.
Archive parent expected at preparation: `c8712d93220715e61561e733d788b6c3f7d28d17`. This directory is an archive append, not a Release or complete V2 acceptance. The archive branch's ordinary tree is not the current product source tree.

The two cherry-picks preserve the exact original patches: 72b60f4b → dd8147fe (scene-scoped child Director handoff), 95e1f915 → 02a98cd3 (directory-loading settlement). Nine final changed file blobs match original95 exactly; every other d78 file, including reserved DSH areas, is unchanged. The incremental bundle contains only this delta and has d78 as its sole external prerequisite.

The handoff reuses the original child-DRAFT owner, re-reads parent/child versions and digest, previews the exact pin, and requires explicit confirmation before one original Graph/history insertion. It does not auto-save, connect, execute or inherit approval. JSON object-member order is compared semantically while array order and values remain exact. The loading fix adds settlement only at the two guarded successful catalog-adoption sites; existing permission, selected/catalog epochs, draft/saving checks, ABA fences and guarded finally behavior remain.

## Evidence and boundaries

- **72b source snapshot:** 46 direct regressions passed. Real original HTTP created the scoped child, verified the pin, inserted/undid/redid and saved Graph v2. The same full browser attempt later timed out in a redundant post-reload directory-read step: `scene72b/browser-save-partial.log` is a partial failure, not a passing full E2E. A separate fresh native reopen of that same saved Graph/child passed with zero additional writes (`browser-separate-reopen.log` and network/result JSON).
- **95e1 source snapshot:** old product had two race regressions red; final targeted suite has 12 passes. A fixture-only requested-route correction and its original failure remain recorded. The shortest real-HTTP diagnostic gated delivery of an unchanged original app.main response; it did not fabricate API data. Before the fix all eight Graph GETs finished 200 while loading remained set; on committed95 all ten GETs finished200, late response/repeated refresh left controls enabled, Graph writes0. This is controlled response timing, not cold-network/model/GPU validation. The pre-fix broad title capture selected a media field; conclusions use exact Graph loading/button signals plus pending-request/controller traces.
- **Combined02a on d78:** only three mounted smoke cases were run (handoff/history/explicit Save/reopen and both loading-adoption paths), plus one TypeScript check and one production Vite build, all passed. Existing large-chunk warning remains. Old46/full12 suites and the full real-browser chain were not rerun on this combined base. Counts belong to their stated snapshots and must not be summed.
- Parent reported independent72b key probes passed and shared-loading95 P2 closed; private reviewer history is not republished. PostgreSQL, live model/GPU/cloud quality, external-NLE interoperability and complete V2 acceptance are not claimed.

`evidence-sanitized.zip` contains selected logs, synthetic-only HTTP responses/state records, three inspected UI screenshots, validation/source mapping, and per-file hashes. Absolute executor paths/ANSI controls were sanitized with original/public hashes recorded. No actual Host credential, raw Host trace, private runtime profile/database, dependencies, models, fonts or dist is included.

## Incremental recovery

First recover a complete verified d78 prerequisite from [the prior public recovery instructions](https://github.com/1785235376-blip/AI-Novel-Studio/blob/c8712d93220715e61561e733d788b6c3f7d28d17/artifacts/2026-10-19-studio-v2-prompt-asset-ux-d78d5058/RESTORE.md). Verify SHA256SUMS, then use an isolated repository:

```sh
git bundle verify /absolute/path/studio-v2-director-d78d5058-to-02a98cd3.bundle
git fetch /absolute/path/studio-v2-director-d78d5058-to-02a98cd3.bundle refs/heads/work/v2-director-scene-d78-combined-20261019:refs/heads/recovered-director-02a
git rev-parse recovered-director-02a
git fsck --full --strict
```

Expected tip `02a98cd3019e41cf80765cb1b0343c58daaf6a68`. MANIFEST.json records the tree, exact nine-file map and introduced object inventory. Never reset an existing user workspace. Immutable public downloads, parent/path/hash checks and isolated restoration are performed after publication; those later receipts are separate from these sealed execution snapshots.
