# Separate reviewed Timeline links integration

Product `638374a689f9cc0c022b0d5603c1c1d8724111a3`, tree `0906c267813ac7f67a8da4f317f288005459cfd6`, unique prerequisite `a814ba30bfbd6d753267d6d0e07472f4302581ed`. This batch adds only reviewed links source `a8d3030215a4975f07045ebdbb71c354dffb8ea2` (original parent d9), mapped to `638374a689f9cc0c022b0d5603c1c1d8724111a3` on the already published Video/Image product. Patch bytes and stable patch ID match; exactly1 commit,12 paths,22 new objects. All12 final blobs equal the source. Every other a814 base path is unchanged. No conflicts or extra product edits.

Scope: optional schema2 VIDEO/AUDIO clip pair metadata, bounded15 disjoint pairs; exact offset, explicit link/unlink, original edits/whole DTO lock and source fences, pair movement with original history/CAS. Old unlinked absence stays absent and old digests are not rewritten. Audio-only schema3/schema1 remain closed. UI keeps linked movement on original tracks. Retained links require explicit unlink before independent trim/split/slip/source/speed changes. No render, inference, auto Save, new owner/store or full external exchange preservation.

## Minimal combined verification

Three CPU/File checks pass: original persistent link/move/history/CAS/reopen/unlink; retained pair whole DTO bypass/offset and closed legacy schema rejection; prior Video decoded order/trim/atomic creation/exact replay/fresh owner receipt compatibility. One controlled-client editor/history/CAS smoke passes,4 skipped. TypeScript/build each ran once and passed; existing large chunk warning retained. Independent3/3 review plus author13 backend/51 frontend and desktop fixture evidence retained, not rerun.

Restored from the minimal bundle in an existing independent no-alternates database:1 new commit,12 final file hashes,all22 new object digests,strict fsck PASS. Seven top-level files only. SHA256SUMS covers the six other files; MANIFEST lists five nonrecursive payload hashes, source mapping and every new object; ZIP evidence-index records each evidence hash and original source hash. Local paths normalized; no credential-shaped values detected.

## Limits and preserved blockers

Hostbrowser, PostgreSQL, GPU/real models/paid APIs and full E2E NOT_ACCEPTED. Broader EDIT04/AUDIO09/V2, linked trim/split propagation, UI cross-track movement and external interchange are outside this accepted slice. Controlled-client/fixture screenshots are not live Host/backend E2E.

Inherited519a remains BLOCKED401 SESSION_REQUIRED: original19128/5322 services stopped; no confirmed existing same-backend valid Host session; preview/explicit Save/fresh browser reopen NOT_RUN. No credential search/read/create or bypass. Demo18913/5293 preserved. The author's previously cleanup-denied evidence directory remains untouched; no deletion/move/retry of it was attempted here.

Condition5c5a stays frozen/default-off pending DIF permission wiring. Proxy4f46c328, new DIF and other unreviewed lanes are excluded. No real models, paid calls, services or OS/GPU/ACL/credential changes; no main merge/force/Tag/Release. Archive requires exact previous public head e49db23f9e7cdeb6ffb560d4d4a986133066221d and only this seven-file directory, normal non-force push. Preserve Git/public evidence and original worktrees; clean only recoverable owned copies after public readback.
