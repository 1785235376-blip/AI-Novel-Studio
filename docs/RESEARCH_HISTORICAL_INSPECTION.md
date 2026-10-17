# A10 exact historical inspection

This additive read is separate from current citation resolution. History metadata and explicit original downloads remain unchanged. A user can open an active source's history, select an old version and enter the original citation's paragraph (or unread page) and SHA-256 digest. The inspector requests exactly that location; it does not fetch on mount, list old paragraphs, search history, download a file, restore a version, repair a note, select a citation, call a provider, or inject context.

## Contract

GET `/novels/{nid}/experimental/research-library/sources/{rid}/history/{version}/inspect`, under the original mounted API prefixes. Required query fields: `expected_current_version`, `paragraph`, `quote_sha256`; page-only references additionally require `page` and paragraph zero.

Uses original ResearchLibraryService, original retained snapshots, current authorization and scope transaction. Requires original author, current ACTIVE source, exact expected current version, an older ACTIVE revision, matching source/project/scope/author/original creation identity, and exact citation hash/location. Rejects unavailable or mismatched locations without disclosing text. One paragraph is capped at 8,000 characters; page-only inspection returns an empty-text, not-understood marker.

Response uses `historical_citation`, `historical_only: true`, `usable_as_current_evidence: false`, `current_version`, `text`, `page`, and `not_understood`. It intentionally has no current evidence `citation` field. HTTP responses use the existing no-store route policy. React renders text nodes, never HTML, Markdown, links, or remote media.

Current resolve, context, note repair, adoption, approval and restoration remain unchanged. Old citation versions continue to fail current resolution even after inspection.

## UI fencing

Explicit input edits, cancellation, source/version/status changes, client replacement, parent selection/refresh epochs and unmount abort and invalidate pending work. Epoch fencing survives A→B→A and transports that ignore abort. Response flags, pinned reference, current version, text bound and page shape are validated before display. The component has no write/selection callback.

## Project incarnation boundary

New mounted imports pin the original CreativeProjectStore incarnation before extraction/fetch and recheck before storage. The read-only endpoint requires the current row and exact retained revision to carry that same current owner pin. Unbound legacy rows are never rebound, migrated or rewritten by inspection. Existing resolve/download/history/restore contracts are not broadened by this feature. An explicit constructor switch leaves legacy direct service users unchanged; the original mounted service enables new import pins. Original owner markers are used, never a second identity registry.

The route checks the owner again after projection and final authorization, including local mode. Source/version/status/client/revision-list changes retire UI responses, including ABA and transports that ignore abort.

## Verification status

Candidate slice, not integrated or released. A real File reproduction first failed because same-public-ID recreation exposed the old historical paragraph. Original retained scope bytes were kept unchanged. The added incarnation guard rejects it; new-owner positive history and rejection of unbound current/revision records are covered. Later tests also cover recreation during extraction and after local response projection.

Current File regression: 172 passed / 134 deselected, original research coverage included. Earlier real PostgreSQL scope: 84 passed / 84 deselected; final expanded PG rerun pending. UI: 67 tests across six files, forced TypeScript build, production Vite build and token guard passed. Browser/geometry acceptance remains blocked by the verified browser environment; no screenshot or live-provider success is claimed. PUBLIC packaging and integrated inventory still pending.

Failed logs are retained: initial reincarnation reproduction; a new mounted test incorrectly recreated a title-generated ID instead of the fixture's explicit ID; a new UI test omitted a required sessionToken; a copied diagnostic probe requested a Director module absent from this branch. Only these new test/probe inputs were corrected. Original tests, runners and gates were not weakened.
