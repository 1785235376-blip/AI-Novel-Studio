# V1.0 acceptance scope freeze

- Frozen Draft PR: #37 (`work/dot-astra-v1-rc-r2`).
- Frozen commit: `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`.
- V1 acceptance, its Windows package and its recorded evidence remain tied to that commit. R3 does not alter that branch, PR or package.
- Post-V1 branch: `work/post-v1-feature-forward-r3`, stacked on the frozen branch. This is Experimental development, not a release, merge or production deployment.
- V1 acceptance does not require any R3 Experimental feature.

## Compatibility

All new domain endpoints live under `/api/novels/{id}/experimental/` (and the existing `/api/v1` alias). Each domain checks a server-owned default-off flag. The feature-status endpoint is read-only. Existing routes, response schemas, manuscript formats, legacy records and migration history remain intact.

Experimental metadata uses separate scope documents. File storage is atomic and cross-process locked; PostgreSQL uses the additive `019_experimental_scope_documents.sql` table with transactional row locking. Both preserve project/workspace/storyline/branch scope. Disabling flags leaves new records intact and inaccessible through experimental endpoints. Downgrade requires no legacy data conversion; export new metadata before any separately authorized table removal.

## Explicit opt-in and complete opt-out

`EXPERIMENTAL_FEATURES` is an allowlist of comma-separated names, for example `advanced_planning_v2,unified_review_inbox`. Unknown names and wildcard values do not enable features. Unset or empty means all off. `V1_ACCEPTANCE_MODE=true` overrides every allowlist and disables all Experimental features. No browser setting can enable a server feature.

No opt-in authorizes a paid provider call, credentials, executable plugins or unreviewed manuscript/Canon changes. Plugin execution remains DENY_ALL. Real-provider quality and interactive Windows acceptance must be reported separately from deterministic and mock evidence.
