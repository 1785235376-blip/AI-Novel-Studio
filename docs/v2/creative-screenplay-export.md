# Creative-owned screenplay text exports

Development checkpoint: M4-D, roadmap TEXT-15. The existing Creative document
store remains the only owner of these screenplays. This is a read-only format
adapter, not another screenplay repository, generation queue or manuscript edit.

## Author workflow

1. Open the V2 creative workspace and select Screenplay. A project without novel
   chapters can create an explicitly independent screenplay.
2. Edit the ordered scenes, action, dialogue and delivery; save the draft.
3. Select Fountain, Word DOCX or Markdown in the screenplay text export panel.
   The panel exports the saved revision and is unavailable while local edits,
   conflicts, another operation or a disabled capability remain unresolved.
4. Keep the original JSON export for all structured metadata. Text formats are
   projections, not complete backups or importable Creative snapshots.

The browser checks the returned version, MIME, byte capacity and actual SHA-256
before offering a download. Pending exports are cancelled or discarded when the
document/session is replaced, editing resumes or access is revoked. A failed
download does not save a draft or change the stored document.

## API

`GET /api/novels/{nid}/experimental/creative/documents/{rid}/screenplay-export`

Required query parameters:

- `format`: `fountain`, `docx` or `markdown`.
- `expected_version`: the exact positive saved document version.

The existing session and branch headers, `domain.read` authority,
`narrative_production_v2` flag and V1 acceptance-off boundary apply. Readers may
export documents they can read. No host model authority or provider permission
is acquired by an export.

Successful responses have the exact format MIME, a server-ID-based attachment
filename, `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`,
`X-Creative-Document-Version`, `X-Creative-Document-Digest` and
`X-Content-SHA256`. The latter identifies the actual returned bytes, not a
serialized JSON wrapper. Existing JSON `/export` behavior is unchanged.

Encoding occurs outside storage transactions. Before and after encoding the
service verifies the saved version/digest, current project incarnation, bound
chapter/document versions, source privacy and original request authority.
Stale versions/sources, archived records and revoked scope fail closed through
the original error model. The server returns no partial output on an error.

## Format mapping and limits

- Original industry encoders provide all three formats. The adapter explicitly
  maps Creative `speaker` to character, `delivery` to parenthetical, and saved
  `version` to the existing revision field.
- Scene order, headings, action, dialogue and emotion are preserved as text.
  Separately authored location/time are also included as visible context so an
  authored slugline cannot hide them.
- Allowlisted provenance includes document ID/version/digest and bound source
  evidence. Unrelated manuscript text, assets and private service records are
  not fetched while exporting.
- Structured character IDs, director metadata, shots and history belong in the
  JSON export. Text formats do not claim to encode every Creative field.
- Empty screenplays and unsupported formats are rejected. Each result is
  bounded to 8,000,000 encoded bytes, without truncating authored text.
- Existing Fountain safety limits remain: ambiguous note delimiters, multiline
  character cues and unsupported parenthetical syntax can be rejected. DOCX or
  Markdown remains available for text Fountain cannot safely represent.

## Evidence boundaries

File/PostgreSQL contract tests, an independent fountain-js parser, DOCX ZIP/XML
inspection, API byte receipts, UI cancellation/identity tests and a real
HTTP/File route exercise are separate checks. A DOCX structural check is not a
claim of visual layout acceptance in Microsoft Word. The hosted browser case
adds chapterless save/reopen/download and three desktop widths; local Chromium
was blocked before page execution by an OS socket permission error.

See [M4-D report](../../MILESTONE_M4D_REPORT.md) for exact source-bound results,
retained failed attempts and the previous hosted-CI failure boundary.
