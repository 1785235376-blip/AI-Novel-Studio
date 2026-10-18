# Source-pinned Director planning CSV

The original CreativeService saved-export path now provides an explicit
GET documents/{id}/director-sheet-export?expected_version=N. It exports only a
saved DIRECTOR document, with original domain.read authority, current project
incarnation/source checks before and after encoding, exact version/digest and
file SHA-256 response headers. No document, asset, proposal, graph or model write.

Rows are sorted by original direction number and include document identity/status,
scene identity/heading/location/time, direction/blocking, camera/duration, acting,
lighting/color/material/transition and optional planning/evidence/performances.
Nested authored detail is JSON inside quoted cells. This is a human-readable
planning sheet, not a film, approved production result or certified NLE interchange.

Encoding is UTF-8 with BOM, quoted CSV fields and CRLF record separators, bounded
to 2,000,000 bytes while appending rows. NUL/unsupported controls and unpaired
surrogates are refused. Formula-like prefixes (ASCII/full-width = + - @, leading
TAB/CR/LF and common preceding whitespace/invisible characters) receive a literal
apostrophe. CSV quoting escapes embedded quotes and separators. Original author
content is unchanged in storage; JSON remains the lossless structured export.

This mitigation is not a universal spreadsheet-security guarantee. Spreadsheet
applications and CSV re-save/reopen can alter escaping; the UI warns against
activating untrusted formulas or external links. Primary reference consulted:
https://owasp.org/www-community/attacks/CSV_Injection (2026-10-18).

The existing Graph Director Console offers explicit saved-sheet download, using
the original text-export transport/hash verifier. Dirty/unknown/inactive or busy
states block it; source/request/availability changes abort and discard old
responses, including availability ABA. Existing screenplay/script clients retain
their formats and 8 MB bound; Director CSV has its own 2 MB bound. The passive new
encoder is listed in the existing public build manifest; no private backend is
added or enabled.

Evidence:
- director-sheet-export-file-ui-r2: 18 backend/File checks, 21 UI checks and
  TypeScript PASS. Original saved/reopened File bytes, literal formula cells,
  Unicode/multiline/quoted fields, post-encode source/authority/capacity rejection,
  original mounted read permissions and hash headers are checked.
- director-sheet-export-pg-r1: 5 genuine PostgreSQL checks PASS on existing GREEN
  OID31303; server stopped. No fresh-database claim for this increment.
- director-sheet-original-clients-r1: 12 unchanged screenplay/script export-client
  checks PASS.
- r1 retained: 13 backend and 21 UI assertions passed, TypeScript rejected the new
  test mock's zero-argument inference; its explicit transport argument types were
  corrected. No original test weakened. r2 also adds full-width/invisible-prefix
  cases after consulting the primary security reference.

No full distribution rebuild, full regression, real product browser, spreadsheet
application compatibility or V2 release-readiness upgrade is claimed.
