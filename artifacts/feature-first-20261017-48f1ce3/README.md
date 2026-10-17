# Feature-first Studio V2 development checkpoint

This archive preserves 29 original commits after 468457706f64d9b8cc793b9a6fa39fa4b354aa15 through 48f1ce3ae5eecfcab2bed1452abc4823dfd51f9f. Source, focused tests, reports and original successful/failed logs are inside the Git bundle. The archive storage commit is not the source commit.

Later increments prioritize functionality per the owner's instruction: planning-source batch forks, subtitle text replacement, canvas dependency inspection, storyboard timing, Director conflict comparison, NLE source/caption wiring, explicit subtitle burn-in/ASR/alignment UI, and an opt-in Aliyun text preset. Earlier commits contain actual original File/PostgreSQL and application process evidence. Read each scope separately; later UI checks use mocked transport and do not establish native model or browser quality.

There is no new installer or rebuilt test package here. Full current-source regression, production build and canonical inventory refresh are deferred. Last fully reconciled inventory is c03b369 and must not be represented as covering later source hashes. Existing blockers, failures and partial product states remain. This is not a Release, full V2 acceptance, or a percentage-complete claim.

## Safe restoration

Use a full clone and preserve existing work. Restore the earlier archive prerequisites, including artifacts/director-audio-primary-20261017-4684577, before verifying this incremental bundle. Choose a new destination branch. No reset, checkout over local work, force update or merge is required.

```sh
(cd artifacts/feature-first-20261017-48f1ce3 && sha256sum -c SHA256SUMS)
git bundle verify artifacts/feature-first-20261017-48f1ce3/continuation.bundle
git fetch artifacts/feature-first-20261017-48f1ce3/continuation.bundle refs/heads/work/dot-director-transport-20261017:refs/heads/recovered/studio-feature-first-20261017
```

Then read docs/V2_CONTINUATION_20261017.md and the linked feature reports. This upload changes only the existing archive branch. It does not update main, merge PRs or create a formal release. Archive CI skipping is not a passing product gate.

The bounded static scan classified all 147 matches as inherited synthetic negative-test IDs or the new literal do-not-display metadata-exclusion fixture. There were no unclassified matches; this is not an absolute guarantee of secret absence.
