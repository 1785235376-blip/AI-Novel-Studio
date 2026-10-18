# Research author-entered license and verification notes

RESEARCH-03 gains two bounded optional metadata strings in the original source
owner: license_statement and verification_note (each at most 4000 characters).
They are author declarations only, not verified licensing, commercial-use
permission, factual truth or a trust score. No URL is fetched from either field.
The original private/project access, current-incarnation checks and citation
version rules remain authoritative.

The original Research source form, selected-source panel and citation view now
allow explicit editing and display these declarations. They travel with source
versions and resolved evidence. Existing context previews still mark all evidence
untrusted and forbid instructions. Changing notes increments the original source
version, invalidates old citations, preserves original history and can be restored
through the existing private-source version restore.

Older clients that omit the two new fields on metadata edits or file replacement
preserve previously saved declarations. Explicit empty strings clear them. Old
records without the fields display an unknown/unfilled state; no automatic
migration or invented verification date is added.

Evidence: research-declarations-file-ui-r1: 29 File/backend checks, 14 UI checks
and TypeScript PASS; research-declarations-pg-r1: 12 real PostgreSQL checks PASS
on the existing owned GREEN database (reuse, not a fresh-database claim), server
stopped. Tests include reopen, old-client edits, file replacement, explicit clear,
history/restore, stale references, limits, original source UI and the previous
incarnation regression. Counts overlap previous slices. No full suite, production
rebuild, product browser or release-readiness upgrade.
