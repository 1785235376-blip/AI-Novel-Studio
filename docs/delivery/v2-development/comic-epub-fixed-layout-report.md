# IMAGE-COMIC-18: bounded raster EPUB reading copy (PARTIAL)

## Scope and original owner

The existing Image/Comic book publication panel can request a fixed-layout EPUB reading copy from the original book/chapter/page owner. There is no new editor, book owner, engine, approval store, export job or persistence path. The original current-source/approved-page renderer, actor/scope/incarnation checks and publication budgets remain authoritative.

The new request is explicitly `format: comic-epub-fixed-raster-v1`, `language: und`, plus the existing required version and LTR/RTL direction. `und` is an explicit unspecified-language choice. No author, ISBN or content language is inferred. Export binds the exact format, language, saved page order, direction and original page approval pins to its digest. All pages and source/authority checks run again after the complete ZIP is closed and before bytes return. Original PNG/CBZ, PDF, JPEG and WebP request schemas and digest bindings are unchanged.

## Actual package

- First local ZIP entry is the exact uncompressed `mimetype` payload `application/epub+zip`, without extra fields.
- `META-INF/container.xml` resolves the OPF package.
- `EPUB/package.opf` uses EPUB package version 3.0 (the package-version value for EPUB 3), a manifest, ordered spine and required identifier/title/language/modified metadata.
- Each saved page has an escaped XHTML document with its own pixel viewport and one generated relative PNG path. The PNG bytes come directly from the existing flattened RGB renderer.
- Fixed-layout metadata declares pre-paginated layout, auto orientation and no spreads. Spine progression is the requested LTR/RTL; it does not reverse saved pages or rearrange panels.
- The local XHTML navigation document follows saved chapter-then-page order. Paths and resource IDs are generated, never derived from user titles.
- Titles are escaped as XML text. XML 1.0-illegal controls/surrogates and empty/ASCII-whitespace-only titles fail closed in EPUB admission. Titles cannot introduce HTML, scripts, forms, remote references or filesystem paths.
- The package contains no actor, owner IDs, source payloads, asset paths, author or ISBN. Its opaque identifier is the publication digest. Modification time is actual UTC serialization time, so the whole EPUB byte hash may vary between exports; original-format byte behavior is unchanged.

## Bounded work

The existing whole-request source/decode/render/encoded-byte budgets and 64 MiB output cap remain active. Before metadata escaping, XML/nav/manifest assembly, decoding or rendering, EPUB additionally admits the entire book:

- XML document cap: 64 KiB
- Total reserved metadata cap: 1 MiB
- Conservative metadata reservation: 16 KiB + 18 × book-title characters + sum(4 KiB + 18 × page-title characters)
- Navigation and OPF have their own whole-document bounds before joins/encoding
- Output reservation: 4 × total pixels + 64 KiB × page count + reserved metadata + 64 KiB

The 4-bytes-per-pixel allowance conservatively covers the original RGB PNG/zlib stream; page overhead covers PNG framing and ZIP headers/directory. Actual metadata writes are also checked against per-document and request reservations. These are bounded reading-copy limits, not a general-purpose encoder, hard CPU timeout or print-quality guarantee.

## Verification and limits

Structural tests parse the actual ZIP, container, OPF and XHTML using Python's XML/ZIP libraries and decode PNGs with Pillow. They assert first-entry bytes, reference closure, MIME types, manifest/spine/navigation order, per-page viewports, LTR/RTL, absence of private data and exact PNG hashes compared with original CBZ renders. Additional tests cover malicious and illegal titles, explicit metadata options, format/digest drift, no mutation, cumulative budgets, current approval/owner/actor/scope/source/privacy changes, authority revocation after ZIP serialization, and original layer visibility/opacity and CJK raster bytes.

Independent EPUBCheck: **NOT_RUN**. No executable or searched installed EPUBCheck distribution was found; no tool was installed or downloaded. Real EPUB reading-system/browser acceptance: **NOT_RUN**. ZIP/XML/Pillow structural success is not EPUB 3.3 conformance certification or cross-reader acceptance.

This remains a raster-only reading copy: no searchable/editable text, limited accessibility, no meaningful content text alternatives, no print fidelity/bleed/color-profile guarantee and no verified source-image rights. Full Comic completion, general language metadata editing, project archives and full EPUB/print conformance are not claimed.

Verification receipts are retained alongside this report. PostgreSQL execution is owned by the integrating root task, not this implementation worker. No browser, network service, provider/model/paid API, package install, push, release or user-machine operation was used for this slice.

### Builder verification evidence

- `comic-epub-backend-compat.json/.log`: **326 passed**, 309 PostgreSQL variants deselected, zero skips. This combined run exercised original CBZ/PNG, PDF, JPEG/WebP, raster layers and actual pinned CJK glyphs using the existing font/fontTools installation.
- The runner truthfully flags concurrent source changes: only the frontend EPUB test file changed during that run. `comic-epub-backend-source-reconciliation.json` checks all 1,501 non-frontend hashes from the pre-run snapshot against the final source freeze, with zero changed or missing files. Backend results remain tied to the exact verified source rather than relabeling the receipt.
- Independent reviewer verification is separate; its CJK prerequisite skip does not claim builder coverage. The builder's actual CJK pass above does not imply EPUB reader acceptance.
- Earlier focused backend receipt: 85 passed, one missing-fontTools prerequisite skip, 78 PostgreSQL variants deselected. The combined builder check supersedes that skip.
- A newly launched unchanged-suite repeat was interrupted at the coordinator's request; it is not claimed as a pass. Verification uses the original actual run and exact source reconciliation.
- `comic-epub-frontend-final.json/.log`: **369 passed**, source snapshot unchanged, covering EPUB/client/mounted authority and stale-state cases, original publication formats, bounded transport and shell/primitives/routes.
- `comic-epub-frontend-build-final.json/.log`: TypeScript, production Vite build and UI token guard **PASS**, source snapshot unchanged. Existing build chunk-size warnings remain; no browser/visual/geometry or reader acceptance is inferred from the build.
