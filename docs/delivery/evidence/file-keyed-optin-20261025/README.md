# Default-off experimental keyed File generation

Follow-up to reviewed local integration `d76acaa68d0a273f492702a496fd51f8bf061ac8`,
which directly includes canonical M5 `18c8744b4c2f208cbfe5607ad1d672b7dcb8e58c`.
This private M6 follow-up is not part of the approved M5 publication. No public
writes, frontend changes, or live configuration changes were performed.

## Compatibility contract

`ENABLE_EXPERIMENTAL_FILE_KEYED_GENERATION` uses the existing Settings/environment
mechanism and defaults to false. Only new admission consults the switch, before
route or composition inspection. Default LOCAL_ONLY keyed requests retain their
original unbound generation, cancel and retry behavior. All four earlier legacy
fixture profile changes were removed: idempotency, admission, worker-authority
and variant fixtures are byte-for-byte canonical M5 versions again.

Explicit opt-in retains the full narrow captured-owner/source/state contract and
bad eligible composition still refuses, never downgrades. Opt-in bound cancel,
retry and staged variants remain unsupported (409). This is a working opt-in
vertical slice, not default-wide protection or a completed bound retry feature.
Turning the switch off affects new admissions only: captured live work retains
its exact issued grant and fences; existing bindings, receipt replay and manual
adoption are preserved, while restored/copied jobs gain no execution authority.

The production change is six added lines across Settings and admission. M5 final
root/physical-owner/leaf checks and M6 source/state/capability checks are untouched.
The old 682/30 counts are historical, not evidence for this follow-up.

## New verification

- Final full combined regression: **691 passed, 3 live-PostgreSQL skips**,
  zero failures, no deselection, 161.42 seconds. Includes actual concurrent
  same-key admission, all original M5/M6 selections and the eight new controls.
- Independent review: **41 passed**, 60.90 seconds. Previous 30 probes rerun,
  eight new compatibility cases, three additional independent switch probes.
  Includes client payload cannot opt in, live bound completion after switch-off,
  unchanged receipt replay, cold no-execution and actual HTTP manual adoption.
- Production/test hashes unchanged across both frozen runs. Supplementary
  concurrency probe matches its frozen historical source and integrity check.

Exact commands, stdout/XML, before/after hashes, six-line production patch and
canonical fixture equality evidence are in `implementation/`. Independent
report and frozen inputs are in `independent/OPTIN_REVIEW.md` and
`independent/optin-freeze/`.
Focused suite: 49 passed (41 existing opt-in cases plus 8 new default/toggle/env
controls). Restored canonical legacy suites: 173 passed. These are overlapping
selections, not counts to add to the final aggregate.

Production manifest SHA256:
`7a6bcd2663e4ce353c52e12052e986d1f0dbe09cd47a10c72445a81a07920c57`.
The portable runner unsets the experimental flag before imports; actual activation
fixtures explicitly opt in. Real Mock streams and original HTTP cancel/retry
handlers are used, not synthetic precompleted rows or replaced guards.

Live PostgreSQL, real model inference, Windows and frontend remain NOT_RUN.
Specialized Graph Mock seams/passive projections do not certify full live
Graph/director/OCR execution. Raw prior failures remain in historical evidence.
