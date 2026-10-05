# A10 — Layered Research Library

Status: **EXTEND, deterministic local workflow implemented**. The optional OCR,
vector and visual-understanding adapters are **NOT_CONFIGURED**. Real browser,
Windows and real PostgreSQL execution are separate gates, not implied by local
File tests. No model/provider call is made by this package.

## Reuse and composition

The pre-existing `app/import_parsers.py` binary base64 decoder is reused. Its
legacy flat DOCX/PDF text APIs remain unchanged: they do not preserve page
citations or impose this package's hostile-input/process bounds. A10 therefore
adds bounded citation-preserving extraction rather than changing the frozen
project-import semantics. DOCX tabs and line breaks follow the existing decoder
convention. Installing the now-declared PDF dependency also exercises the old
real-parser branch; fallback-only tests explicitly select dependency absence.

- The existing `V1CapabilityService` research records remain the metadata
  authority for their IDs. A10 projects their current excerpt and metadata live,
  locally, under `legacy:<id>`; it does not copy or migrate them. Their sidecar is
  still a durable **File sidecar even in a PostgreSQL profile**. URLs in old
  records are never fetched automatically. Existing editor/delete routes remain
  responsible for old records; changing or deleting one invalidates its A10
  citations and all source-derived views on the next read.
- New imports extend research with the existing `ExperimentalStore` scope
  document and native File/PostgreSQL transaction model. Collections are
  `research_sources` and `research_notes`, not a second standalone database.
  Original source bytes are retained locally as base64, alongside extraction and
  provenance. Existing schemas are not migrated or overwritten.
- Original setting adoption uses `WorldService.create_research_draft` and
  `world_records`, retaining native versioned review history. These private
  research-derived candidates carry `research_sources`, stay outside Canon, and
  have an A10-only source-authorized review/reopen flow. Generic world read,
  review, edit, Canon and inbox projections omit them. Canon promotion is not
  available from this workflow.
- Composition: `ResearchLibraryService(store, novels, chapters, legacy=..., world=...)`
  and `create_research_library_router(service, authorize, require_flag)`.
- `research_library_v2` requires explicit `semantic_import_v2` and
  `temporal_story_graph_v2`, whose world dependency must also be enabled. Exact
  server allowlist, default OFF and V1 acceptance override apply. The root owns
  composition, capability registry, shared fixture and feature matrix updates.

## Actual user actions

Open Experimental → 创作资料库. Choose a local TXT/MD/DOCX/PDF/PNG/JPEG/WebP,
enter title/author/source/version/usage information, choose private or current
project/branch-author visibility, and import explicitly. Source access time and
content digest are recorded by the server. Original files can be explicitly
downloaded as attachments with `nosniff`, never rendered inline by the library.

- UTF-8 TXT/MD paragraphs and bounded DOCX XML paragraphs are extracted locally.
- PDF text is parsed by **pypdf 6.19.0**, with page and paragraph citations. The
  parser is an isolated local child process, not a model or external service.
- Image and textless/scanned PDF pages have source-only page citations, empty
  extracted text, and explicit OCR/visual-understanding-not-configured labels.
  A manual note can cite the original page without pretending it was understood.
- A local literal search returns only current accessible paragraphs. Selected
  citations can be traced to exact extracted paragraph/page evidence and source
  version/digest. Paragraph display is paginated in groups of 20.
- Save an author-owned research note with exact citations; inspect backreferences;
  explicitly preview selected research data. The preview is labeled untrusted
  data and is never injected automatically into generation or character context.
- Write an original fictional setting, select source citations, explicitly
  acknowledge originality, save a setting draft, then review or reopen it.
  Verbatim whole-paragraph adoption is rejected. The acknowledgement is not an
  automated originality or copyright assessment.
- Revoke/delete a source or reduce its access. Its active listing/search/context,
  notes and derived setting projections disappear as appropriate, including
  inaccessible titles/counts. Current-source checks defeat old citation reuse.

## Acquisition and input boundaries

The webpage action is a separate POST requiring `confirm_fetch: true`. Opening
this panel, reading old records and searching offline never perform a fetch.
Only public HTTP(S) on its standard port is supported, without credentials,
cookies, browser scripts, proxies, remote images or embedded media. Access errors
are not bypassed. HTML becomes inert plain text. All source content is data;
it cannot run tools, plugins, JavaScript, XML entities or shell commands.

- Request body: 6 MiB before JSON parsing, including chunked input, 15-second
  body-read limit; existing flag/author authority is checked before body parsing.
- Local file: 4 MiB; extracted text: 1,000,000 characters; 5,000 bounded
  paragraphs; PDF: at most 1,000 pages. Each displayed paragraph is at most
  8,000 characters. The source store is capped at 100 records including
  tombstones and approximately 32 MiB of encoded bytes plus extracted text.
- DOCX: at most 1,000 archive members, 12 MiB total expanded size, 8 MiB/member,
  compression-ratio checks, no encrypted entries, duplicate/traversal/absolute/
  symlink paths, DTD/entity declarations or UTF-16 XML ambiguity. Relationships
  never authorize IO. No archive entry is extracted to a filesystem path.
- PDF: 8-second wall timeout, 5-second CPU and 384 MiB address-space limits on
  POSIX, bounded content streams and output; encrypted/malformed PDFs rejected.
  Windows does not provide POSIX `resource` limits, so native Windows memory
  containment is **NOT_VERIFIED**. Wall-clock and input/output bounds still apply.
- Web: 10-second overall acquisition deadline including DNS/TLS, at most three
  redirects, maximum 4 MiB response, only UTF-8 text/plain or text/html, no content
  decompression. All DNS answers must be globally routable. A validated numeric
  address is pinned for the socket; TLS verifies the original hostname. Each hop
  is a separately bounded child, and current parent authority is rechecked before
  every connection/redirect and before persistence. No browser/security-warning
  bypass is involved.

Parser selection checked against official sources on 2026-10-05:
[PyPI 6.19.0 release](https://pypi.org/project/pypdf/),
[official changelog](https://pypdf.readthedocs.io/en/stable/meta/CHANGELOG.html),
[security advisories](https://github.com/py-pdf/pypdf/security/advisories), and
[text extraction limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
The current release includes recent malformed-stream/font/token bounds; the
application still treats parsing as hostile and uses process/resource bounds.
This is not a claim that PDF parsing is risk-free.

## Authority, revocation and compatibility

All A10 projections require existing `domain.write`, including source titles,
counts, originals, notes, search, citations and previews. Draft review additionally
requires `domain.review`. Trusted actor/project/branch authority is checked
before and after private projections and before final mutations. Source-private
access belongs to the importing actor; PROJECT shares only within that same
native project/branch author scope. Only the source owner can edit/revoke/delete.
Cross-project and cross-branch references fail closed.

Read projections use one native scope transaction view. Source version/hash
validation governs each citation. There is no persisted automatic prompt cache
or external vector/summary index to leave active. Source mutations atomically
invalidate A10 cache collections if present and mark note/setting dependencies
stale; all derived reads revalidate live authority instead of trusting that flag.
Existing legacy sidecar projections also revalidate live versions; they do not
inherit native PostgreSQL atomicity guarantees.

Research-derived world candidates are deliberately excluded from generic direct
store consumers; the change-impact implementation independently excludes these
rows and any hidden dependency paths. No A10 source is written into old unscoped
research routes. No manuscript, original character knowledge, original Canon,
provider config, runtime, workflow or model installation is changed.

Deletion/revocation creates a tombstone and preserves local bytes for backup/
recovery rather than permanently purging them. There is currently no source
restore UI. Notes or setting drafts dependent on a missing/revoked source remain
stored but unavailable for projection/review until their source can be validly
re-established. There is no automatic rebinding by filename or similar text.

## UI and tested interaction boundary

`ResearchLibraryPanel.tsx` consumes existing Panel, Button, Badge, StatusMessage,
Field and shared experimental layout classes; it does not alter the protected
shell or design tokens. Native semantic controls and live error/status feedback
remain keyboard-accessible. Includes empty/loading/error/permission/conflict
states, expected-version writes, original user input retained on conflict,
explicit reselect-and-review recovery, source-page pagination, duplicate-click
locking, StrictMode-safe reads and delayed-result scope fences. Scope/session
changes clear private derived state and inputs. No HTML is interpreted.

The authored real-API J07 browser journey imports an original synthetic local
file, traces the exact citation, saves a note, reviews an original setting,
checks no Canon write, checks backreferences, then revokes the source and checks
empty search/context/derived visibility. It also defines 1366×768, 1440×900 and
1920×1080 geometry/screenshot checks. It has been listed/type-checked, **not run
locally** because Chromium EPERM was already established. No screenshots or
screen-reader/Windows compatibility results are fabricated.

## Verification receipt

Worker verification used `r2-run.sh` disposable roots, the isolated Python venv,
and pinned pnpm 10.6.5. Parser installed only in that test venv. All content is
small original synthetic text/images/PDF/DOCX; external transport tests use
controlled responses and never visit an outside site.

- Initial focused parser/native-service run: 47 passed; 13 actual-PG cases
  explicitly NOT_RUN/skipped. Additional access-reduction/web-hop tests were
  subsequently added and are included in the final focused receipt.
- Actual mounted API authority suite: 16 File cases passed across `/api` and
  `/api/v1`; 16 real-PG cases deselected locally.
- Final focused + mounted + shared world/story-graph/legacy research regression
  run: 109 passed, 58 real-PG cases deselected, including dependency-present
  and explicitly dependency-absent legacy PDF import cases. Logs: `r4-a10-focused-and-regression.log` and
  `r4-a10-mounted.log` in the task workspace, not committed as bulk artifacts.
- Frontend panel/shared/Workbench: 18 passed (10 A10-specific). TypeScript, UI token guard and
  diff whitespace checks passed. `r4-research-library.spec.ts`: one authored
  browser journey successfully listed; browser execution **NOT_RUN**.
- Backend worker commit: `1d0372810540074b820d736cbaaaa641b1f09ab6`.
  Engineering-tree SHA and consolidated post-composition results are reported
  in the parent checkpoint. These worker results do not certify unrelated
  simultaneous changes or unrun PostgreSQL/browser/Windows/model gates.

## Remaining boundaries

No OCR, embedding/vector search, model-based summaries, image understanding,
semantic search, character-context adoption or automatic Canon promotion. No
paywall/SSO browser import, remote-image loading, HTML execution or outside
model calls. Notes are create/read in this slice; note edit/delete and source
restoration are not exposed. PDF typography/reading-order correctness and
complex DOCX layout are not claimed; exact extracted text and original file/page
remain available for human comparison. Real public-web compatibility, real PG,
Windows process containment, screen-reader testing and visual browser execution
remain independent verification tasks.
