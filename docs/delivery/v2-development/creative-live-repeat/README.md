# Creative live HTTP repeat regression

Both runs execute the unchanged three HTTP/File scenarios twice against the same Playwright-managed server. They reuse the same title-derived novel IDs, verify 201 create/204 delete and empty inventories, and retain all original lifecycle, source, manuscript, version and document-count assertions. No randomized fixture IDs or assertion weakening.

| Evidence | Result | Meaning |
| --- | --- | --- |
| [Before fix](before-fix/source-identity.json) | 4 passed, 2 failed | Recreating deleted project IDs resurrected retained creative rows; lifecycle returned 5 documents rather than 1, and scope scenario returned 2 rather than 1. |
| [First backend fix](after-fix/source-identity.json) | 6 passed, 0 failed | Owner-incarnation protection fences earlier creative records while retaining historical bytes. |

Each folder contains the original run log, JUnit XML, Playwright JSON results, backend/Vite logs and available failure traces. Source identities distinguish recorded hashes from reconstructed pre-fix backend blobs. Earlier evidence is preserved unchanged.

These are real HTTP/File results, not browser acceptance. Browser gestures, layout and screenshots remain pending the hosted Chromium run. No PostgreSQL process or paid provider was used in these runs. A final stable backend rerun will be recorded separately if the backend changes.

## Final stable backend

[Final stable receipt](final-stable/source-identity.json): 6 passed, 0 failed, 0 skipped in 14.8s after bounded marker validation. Config, live spec and all three changed backend modules have identical before/after SHA-256 hashes. This supersedes the first backend fix for current-source verification while preserving both earlier runs unchanged. HTTP/File results only; hosted browser acceptance remains separate.
