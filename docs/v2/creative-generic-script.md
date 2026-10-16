# Generic authored Script on the Creative owner

Roadmap TEXT-17 is implemented as a document type in the existing Screenplay
workspace. The five professional workspace stages stay intact. A Script is not
a screenplay with invented scenes, a second asset repository, or a model job.

## Author workflow

Open the V2 creative workspace, choose Screenplay, then **新建独立通用脚本**.
Enter a title, purpose and body, and save. No novel chapter, model or scene is
required. Purposes are Custom, Advertisement, MV narration, Podcast, Game
dialogue, Presentation and Short video. These classify authored text; they do
not imply a specialized editor, generation quality, audio or video rendering.

The original Creative list, CAS edit, history, reviewed restoration, project
scope/incarnation and privacy/source fences own this document. Restoration
creates a new current version and retains previous versions. Unsaved text stays
in page memory; the existing exit/discard warning and export of unsaved drafts
remain available. An uncertain save or conflict preserves and locks the local
draft until the user reconciles it. No automatic manuscript or Canon edit occurs.

After saving, choose TXT, Markdown or Word DOCX. TXT and Markdown contain the
exact authored body, including whitespace and newlines. DOCX uses the existing
text export encoder with the title and body. JSON remains the complete metadata
and source/version export. Downloading does not save or revise a document.

## Typed contract and API

`CreativeDocumentIn.mode = SCRIPT` adds `script: { purpose, body }`. The body is
a nonblank strict string, at most 64,000 characters; no truncation occurs. A
Script cannot simultaneously carry scenes, director notes, shots or a video
plan. Other document types cannot carry Script content. Existing document type
immutability and source binding rules remain in force. Old snapshots missing
the optional field are read without rewriting their stored bytes or digest.

Existing routes perform creation, listing, reads, edits, history, restoration,
archive and JSON export. Enabled capabilities include `SCRIPT` and map it to
`SCREENPLAY` in `document_type_stages`. Disabled/V1 acceptance capabilities
retain their existing response and reject protected routes.

The additive read-only route is:

`GET /api/novels/{nid}/experimental/creative/documents/{rid}/script-export?format=txt|markdown|docx&expected_version=N`

The `/api/v1` alias is provided by the existing router. The original
`domain.read` scope and session/branch authority apply. Encoding happens
outside storage transactions, followed by authority, incarnation, source
privacy/version and document CAS/digest rechecks. Replies are private,
`no-store`, `nosniff`, bounded to 8,000,000 actual bytes and carry exact version,
document digest and byte SHA256. XML-invalid control characters are rejected
for DOCX instead of silently stripped; exact-text formats remain available.

The original download client verifies MIME, capacity, version, digest syntax
and actual SHA256. A pending response cannot download after editing, document
replacement, unmount, session change or revocation. No arbitrary Markdown is
rendered as HTML in this workspace.

## Remaining boundaries

This slice supplies manual authoring and versioned export, not every TEXT-17 or
M4 acceptance criterion. Typed reuse as a Graph source, model-assisted generic
Script proposals, richer branch-story editing and source-aware chapter
adaptation remain separate work. No new Graph node registry or execution queue
is introduced. Browser geometry and native Word rendering are distinct from
component tests and DOCX structural inspection. See the stage report for actual
results and inherited failed observations.
