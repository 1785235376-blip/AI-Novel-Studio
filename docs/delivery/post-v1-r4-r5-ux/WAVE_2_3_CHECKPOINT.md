# R4 writing and production checkpoint

Validated code revision: `780809280915db663a47aad8a4fc7cab6d884376`, tree `8879f43c2ec244d52b6fdbb862185bc93a21ebd9`. This document is added after that immutable validation; it changes no runtime source.

This staged increment extends A05/A06/A07/A09/A13, A02/A03/A01/A10/A11 and U05/U06, with corresponding real frontend forms and original-authority API wiring. It includes implementation repairs for the two reported second-slice defects. The independent follow-up review remains BLOCKED; implementation test success does not close it.

## Exact local checks

- Full File-compatible backend: **2,820 passed, 9 skipped, 543 actual-PostgreSQL-only deselected** (211.75 seconds).
- Full frontend: **814 passed, 6 optional HTTP tests skipped** across 142 passing files.
- TypeScript, production build and design-token guard: PASS.
- Build warning retained: App chunk 860.96 kB minified, 247.31 kB gzip. No threshold was increased to hide it.
- This checkpoint's hosted PostgreSQL and browser journeys remain pending until remote CI executes. Local Chromium cannot launch in the available sandbox; no browser result is inferred from unit tests.

Earlier `fc9e39ddcb1084da213f1463b76ded21a11c71c1` had a fully green PR run, including 30 browser tests across all suites. Its duplicate push PostgreSQL job reached the 20-minute timeout; one targeted rerun was accepted. That earlier evidence is not this larger checkpoint's result.

## Boundaries

All experimental features remain server-owned, exact-allowlist and default OFF; V1 mode forces them OFF. Original human review, source/version/actor/privacy checks and final-dispatch validation remain the authority. Synthetic transport capture and synthetic image replay establish deterministic plumbing only. Real language/image/audio quality, paid providers, GPU runtimes, native Windows IME and target external applications are not verified here.

Manual/rule-based simulator, research extraction and citation drafts, partial revisions and locks work without a model. Unsupported branch-isolated manuscript writes and unimplemented cross-domain replay are explicitly blocked. Source or scope changes invalidate stale candidates rather than applying them to a new target. See each package document and FEATURE_MATRIX.json for remaining scope.
