# Director and Audio primary-verified continuation archive

This fixed archive preserves 14 original commits after 17c6500 through 468457706f64d9b8cc793b9a6fa39fa4b354aa15, plus four actual PUBLIC test packages. Original Git SHAs and metadata are inside the bundle; this branch's storage commit is not the source commit.

The Director changes add an explicit versioned client, original Graph authority boundaries, uncertain-review preservation, exact adopted-DRAFT reopening, and the capability-gated original proposal panel. The Audio fix resolves the five recorded listing diagnostic failures without changing original tests or weakening get/execution/review immutable checks.

This remains a partial product candidate. Production Director route construction is not enabled. Real browser, PostgreSQL, Windows, GPU and live-model acceptance are not complete; independent-agent review was unavailable. Do not treat this archive as a Release or V2 completion. Counts describe separate documented scopes and must not be blindly added.

Director checkpoint: 275 backend checks passed (97 PostgreSQL-only deselected), 332 UI checks across 24 files, TypeScript/build/token checks passed. Audio checkpoint: 79 listing/integrity/compatibility, 231 contract/API and 117 CPU-media/Audio-API checks passed, with PostgreSQL exclusions documented. Fresh TypeScript/build/token and 87 PUBLIC package checks passed. Two actual wheels and two sdists were read back against all current included payloads. The 17,505-row inventory is collection only.

Original failures, successful raw logs and report source are retained inside Git history. Read docs/V2_CONTINUATION_20261017.md, docs/DIRECTOR_MODEL_CLIENT_PROGRESS.md and docs/AUDIO_LISTING_DIAGNOSTIC_PRECEDENCE.md after restoring. Static scan hits were all inherited synthetic credential-shaped negative-test IDs; no unclassified hit was found. This is not an absolute guarantee of secret absence.

## Restore without overwriting work

Use a full clone. First follow artifacts/verified-20261017/README.md and then artifacts/director-primary-20261017-17c6500/README.md to restore the prerequisite source objects. Preserve your own changes and choose a fresh destination branch name.

```sh
(cd artifacts/director-audio-primary-20261017-4684577 && sha256sum -c SHA256SUMS)
git bundle verify artifacts/director-audio-primary-20261017-4684577/continuation.bundle
git fetch artifacts/director-audio-primary-20261017-4684577/continuation.bundle refs/heads/work/dot-director-transport-20261017:refs/heads/recovered/studio-director-audio-20261017
```

Do not force-update an existing destination. Verification does not require installing or executing the packages. Main, PR #47 and PR #48 are not changed by this archival upload. Archival CI is intentionally skipped; skipped CI is not a passing product gate.
