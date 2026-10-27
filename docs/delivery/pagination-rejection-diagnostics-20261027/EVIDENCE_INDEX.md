# Evidence groups (archive member prefixes)

Only **final-immutable-99258ef5/** supplies the final 22-test acceptance claim:

- diagnostic-acceptance.xml and .log: 22 passed.
- diagnostic-acceptance.receipt.json: fixed 99258ef5, exit 0, ~199.596 seconds,
  source hashes unchanged, no foreign modules.
- diagnostic-acceptance-runtime/http-evidence/: six audit receipts, normal /
  reopened / byte-exhausted for each of two aliases.
- The server logs in that group contain the 28 endpoint events summarized in
  the outer evidence/diagnostic-events.json. Its `log` paths are relative to
  this final group, not the exploratory groups.
- Outer evidence/final-receipt.json duplicates that group's receipt byte-for-byte.

**independent-final/** supplies the overlapping final 10-test independent
check, not ten extra tests to add to 22.

All other prefixes are historical/nonacceptance evidence:

- exploratory-hook-not-attached/: first run's attachment bug, full case passed
  but no route diagnosis actually installed.
- exploratory-attached/: successful actual diagnostic attachment, one alias.
- exploratory-unit8/: early eight helper cases before final hardening.
- exploratory-helper-edited/: previously planned final run that crossed a
  helper edit boundary, 10 tests. It is expressly NOT immutable acceptance.
- independent/: initial five-failure/two-pass observer counterexamples and later
  green intermediate versions. Historical filenames red2/red3 do not determine
  outcomes; use the XML and logs.

The raw manifest indexes every member's bytes and SHA256. No historical failure
or incomplete acceptance is discarded or promoted to final status.
