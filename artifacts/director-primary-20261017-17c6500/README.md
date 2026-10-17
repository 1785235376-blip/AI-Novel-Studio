# Director primary-verified development archive

This archive preserves 8 original Git commits after `5a6f697bccf2127b1bbfd62bb422311edc8c4afe`, through `17c6500852359a99bfb023ae173e87d686c67829`, plus four actual PUBLIC test artifacts. Original code commit: `3f49631`. Git author metadata and original SHAs remain inside the bundle. This archive branch's own HEAD is a separate storage commit, not the original source HEAD.

Implemented and checked: private Director lifecycle status, cooperative cancellation, exact adopted-DRAFT reconciliation, explicit versioned HTTP action transport over the original owners, and strict frontend observation/planning contracts. Production application construction has NOT enabled the new routes, and the new action UI is not mounted. This is a partial development delivery, not V2 completion, a Release, or real-model/browser acceptance.

Primary final checks: 271 backend tests passed, 97 PostgreSQL-only cases deselected; 161 UI tests in 8 files passed; TypeScript, production build and token guard passed; 87 PUBLIC packaging tests passed. Two actual wheels and two actual sdists were reread against current source payloads. Scope counts overlap earlier runs and must not be added. Separate-agent review, real PostgreSQL, browser, Windows, GPU and live-provider quality validation were not performed.

The original failed logs are retained in source history, including a pending-read generation-snapshot race, the frontend's rejection of valid planning evidence, and a PUBLIC manifest-order failure. Fixes did not weaken original tests or public isolation. See `docs/DIRECTOR_MODEL_TRANSPORT_PROGRESS.md` and the indexed evidence after restoring the source.

## Restore without rewriting existing branches

Use a full clone, not a shallow clone. First follow the prior archive's restore instructions at `artifacts/verified-20261017/README.md`; that reconstructs the original `5a6f697` prerequisite from its split bundle. Keep your own changes untouched.

From the clone root, verify and restore:

```sh
(cd artifacts/director-primary-20261017-17c6500 && sha256sum -c SHA256SUMS)
git bundle verify artifacts/director-primary-20261017-17c6500/director.bundle
git fetch artifacts/director-primary-20261017-17c6500/director.bundle refs/heads/work/dot-director-transport-20261017:refs/heads/recovered/studio-director-20261017
```

If the destination branch already exists, choose a new unused local branch name. Do not reset or force-update it. No installation or execution of the archived wheels/sdists is required to verify their hashes.

Main and PR #47/#48 are not changed by publishing this archive. CI is intentionally skipped for the archival commit; skipped CI is not PASS. Source files, original logs and local test archives are retained.
