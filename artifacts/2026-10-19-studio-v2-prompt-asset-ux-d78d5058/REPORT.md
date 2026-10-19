# Studio V2 limited Prompt/asset UX increment

Product base `8c1b4b197e57ce7ae070f0e4f7d4e36c805a360f` → combined `d78d50589a07f1ff428fbc9e93453f32876648d2`. Expected archive parent `0c0ac1019244d3b7ad6913e46b33cee8155357ef`.

This increment adds direct previous/next navigation between Prompt revision differences and improves the original asset library filename search/file-kind browsing. It includes the reviewed same-ID navigation scope correction: a fresh explicit target can clear stale filters and reveal the asset without automatically selecting it; ordinary refresh and callback rebuilding preserve search/type/order. Existing read/selection/permission/write owners remain intact.

The accepted Prompt `87d517fc` and asset `c39bf18c` + `368e86cb` patches were applied without conflict as `5ca580e9`, `d019605b`, `d78d5058`. Stable patch IDs and all seven final file blobs match. Every other file from8c, including Host/NLE and the three DSH-reserved UX areas, remains unchanged.

Limited integration checks: four focused component fixture smoke cases across the two modules passed (3.26 s), followed by one original `pnpm build` (`tsc -b && vite build`). No old suites were repeated. Source before/after hashes are identical; generated dist hashes are recorded separately. The independent Prompt four-probe and asset two-probe P2 closure reports are retained, not rerun or promoted into new full-suite evidence.

This is component fixture/compile integration evidence. Full original-entry backend E2E remains deferred. Prior three-viewport component geometry does not constitute full backend E2E or an approved pixel baseline. Native IME/macOS hardware, larger regression matrices and full Studio V2 acceptance are not claimed. Prior NLE/Host evidence is a retained base, not a live acceptance run of these new UX features.

Public files contain only the8c→d78 incremental source/test bundle, this report, sanitized necessary logs/review evidence and checksums. No raw Host/session/network trace, private runtime profile, credential or private user data is included. No main/source branch, PR, Tag or Release is modified by this archive addition.

See [RESTORE.md](RESTORE.md), [MANIFEST.json](MANIFEST.json), and [SHA256SUMS](SHA256SUMS).
