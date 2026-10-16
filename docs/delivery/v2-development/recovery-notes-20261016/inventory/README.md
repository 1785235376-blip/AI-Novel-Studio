# Recovery-note inventory refresh

Source checkpoint and all three collection HEADs: `f06ad47742e8f5f480208198b61d54f5aac387e4`. The later evidence/manifest commit is not the source or collection checkpoint.

- Review, candidate and separate post-promotion no-write confirmation each collected exactly 15,617 rows with zero errors. Their raw bytes equal the existing committed archive referenced in `compact-source-binding.json`; SHA256 `b921230f2888db9f7be9fd32f1f3e3d2dfaf45c2ce528886897a17ba7fa78ede`. No additional backend rows.
- The unchanged generator produced candidate SHA256 `5590bbfc4ee4c8b287ceea729af9419d19695439ff11a735f64b2a3c37551f79`; independently reviewed bytes were copied to canonical, then confirmed without writing.
- All 1,266 previously protected sources remain exact. The complete 2,577-entry source map differs only in the recovery component hash and newly added notes test. Frozen V1, guards, generator, historical skips and external gates remain unchanged. The separate 11-file frontend/scripts + frontend/e2e provenance is complete and unchanged.
- The clean interpreter was startup-checked with a stdlib-only PathFinder probe, including an actual child rooted in this worktree. No product or pytest imports occurred in that probe. Collection uses the documented sanitized environment and only owned-profile app initialization. No product test bodies or lifecycle fixtures executed.
- The independent frontend receipt covers the same 24 focused cases, not 24 additional unique tests. No full frontend discovery, browser, full product, PostgreSQL, service/provider, or hosted-CI acceptance is claimed.

Per-invocation reports/logs retain actual outputs unchanged. Their historical `.runtime` archive paths are locally preserved; the portable committed raw reference and digest are in `compact-source-binding.json`. Candidate bytes are now the canonical manifest; no redundant large archive or candidate copy is committed. The original focused-run evidence and initial failure remain untouched.

Run from repository root: `node docs/delivery/v2-development/recovery-notes-20261016/inventory/verify.mjs`. This only reads and hashes files; it does not import the product or execute tests. `evidence-files.json` hashes this subfolder; the sibling `independent/evidence-files.json` hashes the independent reports.
