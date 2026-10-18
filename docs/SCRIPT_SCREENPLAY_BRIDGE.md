# Explicit saved Script to Screenplay staging bridge

The original Creative derive owner now accepts SCREENPLAY only from a saved SCRIPT and only with the explicit TEXT_CHUNKS policy. The operation preserves all source text in order as scene action chunks of at most 16000 Unicode code points (up to four chunks for the existing 64000-character Script bound). This fits both the original Scene and downstream Shot action limits. It does not infer semantic scenes, characters, dialogue, camera choices or literary quality.

The new document is a DRAFT with original source version/digest/incarnation binding. Its provenance retains source purpose, the exact chunk rule and human-review requirement. Original Script content is unchanged. Source edits or permission retirement remain fenced by the original Creative owner. The existing derive transaction and common record-publication helper are reused; no parallel store, scheduler or execution path exists. Existing Storyboard and Production derivation parameters remain unchanged.

The existing Creative Workspace shows a read-only bounded chunk preview and an unchecked confirmation. It sends one request through the original mutation/uncertainty owner only after confirmation. Dirty, blocked, busy, unavailable and retired source contexts cannot apply old consent. A mismatched successful response is treated as uncertain and retained for manual directory verification, not automatically replayed. New stage identity, source version/digest shape and exact reconstructed text are checked before opening the response. No model or media call is made.

This bridge does not admit generic SCRIPT directly to the Director model/proposal contract. The separately saved structured SCREENPLAY can use the original Director review path. A genuine PostgreSQL check staged text, generated explicitly rule-assisted pending suggestions, performed original human review and reopened the Director record; direct SCRIPT proposal admission remained rejected. This proves the data/review bridge, not live model analysis.

Verification:
- Final backend/File plus original stage, catalog and PUBLIC package selection: 14 passed, 8 PostgreSQL cases deselected; includes an actual offline wheel.
- Real PostgreSQL new bridge and unchanged prior stage contracts: 8 passed, 8 File cases deselected; reused OID 16384, stopped.
- Additional original Director-review chain: 1 PostgreSQL passed, 1 File case skipped by the PG harness; server stopped. No File pass is claimed for that additional case.
- UI: 28 passed, followed by successful TypeScript, actual Vite build and token guard.
- Original failed receipts are retained. The first implementation used 32000-character Scene chunks and the long downstream test correctly rejected them at Shot.action's 16000 limit. Product chunks were tightened to 16000 without truncating text. A new HTTP test's expected status was corrected to the existing route's 201 contract. The later TypeScript failure involved optional RequestInit in new test assertions; those annotations were corrected without weakening assertions.

API method/path count remains 2367; source fingerprint beb7bbf98edb01b6b5c9278af364a5127fa00c7c127e54b05956b4d98aeb12a7. Whole-product browser, real model/video quality and release acceptance remain separate. Native browser restrictions were not bypassed. No main merge, Release or paid API was used.
