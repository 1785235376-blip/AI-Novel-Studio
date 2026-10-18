# Bounded JPEG and WebP Comic page archives

Product checkpoint: 3a33b6d3fdf8c964ee1281178d6edb0bcece9e9e. IMAGE-COMIC-18 and full V2 remain PARTIAL / NOT ACCEPTED.

## Delivered

Original Image Studio Comic publication now exports ordered full-page JPEG or WebP ZIP reading copies. Format, quality and lossy/lossless mode are explicit and bound to the current approved book/page/source snapshot. Existing PNG CBZ and PDF identities remain unchanged. Rendering, source privacy, actor/scope/incarnation, approvals, cumulative budgets and the final authority check reuse the original owners; no queue, storage owner or automatic promotion was introduced.

JPEG is lossy even at quality100. WebP lossless is actually redecoded and RGB-compared before release. Generated PNG and encoded-result geometry are checked before decode allocation. Private EXIF/ICC/path metadata is discarded; the output manifest uses fixed numbered filenames and public reading-copy information. No editable layers/text, print or color-profile fidelity is claimed.

## Explicit capacity and transport boundaries

A request admits at most1,048,576 aggregate page pixels, at most8 pages, and2048 pixels per side. These are separate limits: one1024-square page fits, not8 full-size pages. Codec work reserves256 bytes/pixel plus8MiB/page; output reserves8 bytes/pixel plus64KiB/page and4MiB metadata/license before allocation. JPEG uses baseline/nonoptimized/nonprogressive encoding; WebP uses fixed method0, with lossless quality0 selecting low effort. These conservative engineering bounds are not a hard OS memory/wall-clock guarantee against native codec defects.

New archive downloads opt into64MiB capped streaming through both experimental and mounted Image transports, with redirect rejection, bounded retained bytes/bookkeeping and a second Blob-size guard before hashing/saving. No blanket limit was imposed on unrelated media. A producer can deliver an already allocated chunk; the application does not accumulate beyond its cap. Real browser/network acceptance remains open.

## Evidence, without repeating unchanged full suites

- Pinned-font File corpus:239 passed,231 PG parameters deselected. Frontend and two affected backend/test files changed during that run; its raw receipt and source-change flag are preserved.
- Affected new archive suite rerun:94 passed,88 PG parameters deselected. Exact reconciliation of1,522 backend/test/script inputs identifies only the codec header guard and archive test changes; their stable rerun is retained. These counts overlap and are not additive.
- Integrated real PostgreSQL:102 passed,108 non-PG cases deselected. Includes new archives and focused existing CBZ/PDF/source-return/layer/CJK compatibility. Existing UTF8 PostgreSQL17.11/OID16384 reused; all14 table hashes match before/after; server stopped.
- Frontend:260 focused plus34 neighboring/mounted Image tests passed; types, production build, token lint and discovery passed. All1,637 recorded frontend inputs match the integrated source. The exact source-stable worker build was copied and hash-verified under an owned immutable runtime directory instead of repeating unchanged build/tests.
- PUBLIC wheel/catalog:6 passed. Catalog2509 operations; fingerprint ad9e7e0c8882681f08b586bf9cdcb18464df43a9cd5f76a6de5491620ba2e15e. Private backend remains excluded.
- Final PG/PUBLIC receipts match all3,158 unchanged integrated source paths.

Independent backend review exercised real1024-square entropy images: JPEG100 and WebP100 changed pixels, while lossless WebP round-tripped exact RGB. Independent UI review passed260 focused tests and verified current pins, dirty/lifecycle/ABA gates, strict format options and stream limits. This is codec/jsdom evidence, not Windows/reader/print acceptance.

## Preserved failures and limits

Initial test runs used a basetemp outside the required owned profile; corrected invocation did not change product behavior. Reviewer/root hardening moved verification header checks before decode and added capped response streaming. Failed raw receipts, source reconciliation and final evidence remain available; no reconstructed logs are passed off as original evidence.

Long/high-resolution publication, native Windows codec/runtime, real readers/browser/screen-reader and full product acceptance remain open. Previous source1ccbce1c is independently archived at a946bafd7dd2d1ef171c389ba8b1e2af23966b7f, exact parent36ff75ce:14 artifacts /5,527,238 bytes. This is an archive bundle, not a main/PR update or release. Fixed-layout EPUB is separate ongoing isolated work, not yet integrated or accepted.
