# Original-generator text artifact recovery — recovered public-base edition

Status: PARTIAL. This is a tests/docs/synthetic-evidence-only package on public Export owner baseline efd083c2b25a63a2aad3c0fc5415314d9dbc7ca3 (tree78cdf349da72058b32b66eee7ad0f9746d520db2). App tree44f0a0fe8780611d1440687f799f5d13cb40714c is unchanged. One new self-contained test file is the only executable delta.

## Recovery and authorization boundary
The previous local 07f29a66 package and its unpublished bd85784c coexistence parent were lost after environment reset. We did not recover or silently publish that parent. The text test was reimplemented on the already-public efd baseline, with newly executed evidence and a new freeze. Old receipts/counts are not reused: in particular, the old 170-case run included unpublished coexistence helpers and does not describe this edition. No unpublished TaskCenter TTL/single-reader code, combined TCP helpers or prior coexistence docs are included. Those guarantees are not newly established here.

User authorized publication of this branch's tests, documentation and sanitized synthetic evidence at 2026-10-28 04:10:57 UTC, excluding real data/credentials, main changes, force-pushes and Releases. This document records local verification; it is not a remote publication receipt. The root coordinator owns any authorized upload and remote readback.

## What the new 12 cases establish
Original File repositories and ChapterService create one synthetic Unicode chapter with multiple paragraphs. Original NovelService snapshot capture and TXT, Markdown and JSON rendering run inside original ExportJobService child processes. Wrappers only pause after original rendering or after original progress95 (artifact persisted, success not yet committed); no result or job row is manufactured.

Across two gates, normal completion/POSIX killed-owner recovery and three formats: live B startup must not render, recover A or overwrite persisted artifact bytes/mtime; edits to actual live manuscript/title after capture must not leak into the durable snapshot result. Recovered C renderer bytes equal the original snapshot output. TXT additionally has a literal independent expected byte sequence, and JSON is parsed for the original novel title/chapter identity. All cases require a real persisted artifact (not merely inline download fallback), exact bytes, SHA256, size, download equality, original snapshot, correct recovery count and successful terminal state. Fresh D startup must not render or change artifact bytes/mtime or lifecycle observation.

JSON carries generated fixture metadata: within-run bytes are compared against the original snapshot, not asserted constant across independent runs. All input is synthetic. No network model, GPU or external service participates.

## Negative control and independent review
A separate checkout deliberately discards snapshot forwarding; both dead-recovery TXT gates fail at C renderer byte comparison because later live text leaks. Its clearly labeled negative-only.patch is evidence, NOT production code or a fix, and was never applied to the final source. This proves test sensitivity, not a newly found production bug. Read-only independent review confirms original-owner execution, gate placement, file-existence checks, absence of unpublished helper imports and a clean production diff.

## Frozen evidence
RESULTS.json, logs, XML and receipts report the new exact freeze, module paths, before/after hashes and exit codes. Both final groups exit0, all source hashes unchanged, no foreign app modules. Groups overlap and must not be added. The regression group includes the public baseline's Export plus existing DOCX/PDF tests; it deliberately excludes unpublished TaskCenter coexistence helpers. Existing binary tests passing does not establish binary recovery coverage.

## Remaining boundaries
PARTIAL: no binary document process-recovery proof, multi-chapter ordering proof, actual Windows recovery, PostgreSQL, browser or hosted CI. No exactly-once external side effects, distributed locks or strong ABA guarantees. No additional asset-query or TaskCenter budget coverage. Known unrelated asset failures are not repaired or reclassified. This package finds no new production defect and modifies no app, frontend, SDK or Work integration branch.
