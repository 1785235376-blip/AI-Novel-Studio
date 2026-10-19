# Durable industry screenplay exports

Use the existing authenticated `POST /api/exports?novel_id=...` flow with
`{"format":"screenplay-fountain"}` or `{"format":"screenplay-docx"}`.
`screenplay-standard` remains an accepted alias for `screenplay-fountain`.
The v1 alias works identically. Fountain downloads use `.fountain` and
`text/x-fountain`; Word downloads use `.docx` and the OOXML document media type.

The queue captures the project at creation and renders the last screenplay in
that captured list, matching the established screenplay selection behavior.
Subsequent edits or reordering cannot alter that job. The document records its
snapshot ID and captured chapter versions and screenplay revisions. Interrupted
jobs resume from the persisted snapshot. Explicit retry creates a new attempt
with a fresh snapshot, preserving existing queue behavior.

Read/download, cancellation, and retry use the existing project/branch permission
checks. Idempotency keys are scoped to project and persisted permission context;
reusing a key in a different branch or actor context cannot return another
scope's job. Renderer failures never retry against live data. Invalid screenplay
schemas fail with `EXPORT_SCHEMA_INVALID` and structured issues.

Industry formats are intentionally unavailable on the legacy synchronous novel
export endpoint. Resource packages, arbitrary resource loaders, and filesystem
paths are not exposed by the queue. No provider execution is involved.

The legacy eight-column shot-list CSV retains its headers and column order,
with standard CSV quoting for embedded newlines, commas, and quotation marks.
