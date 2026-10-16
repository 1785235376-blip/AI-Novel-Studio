# Original regression retained: invalidated Research vector receipts

The first complete integrated local source tree, `50edbbc93f949ce7ca1133a3d4b02d4d70af6a93`, was not published as a commit. Its full File regression collected and executed all 8,626 nodes: 5,727 passed, 2,898 skipped under the original profile rules, and one failed. Separate real two-process TCP synchronization passed 2/2. This is supplemental local Python 3.12.14 evidence, not hosted PostgreSQL proof.

The retained original failure was `test_post_interop_wave3_research.py::test_research_vector_rebuild_query_atomic_source_revoke_and_author_isolation[file]`. The newer permission-aware record read incorrectly rejected the source owner's erased-vector invalidation receipt after source deletion. The original test and assertion remain unchanged.

The correction lives in the existing `EmbeddingService.records` owner. It permits an INVALIDATED receipt only when the index owner is also the exact archived Research source owner, the project and complete scope still match, every retained vector is INVALIDATED and erased, and the current Research feature guard succeeds. A former reader of a revoked shared source remains denied. No source is restored, vector queried, provider called, permission granted, or automatic rebuild performed.

`tests/test_surface_embedding_invalidation_receipts.py` adds File/real-PostgreSQL-parameterized checks for deletion and revocation across restart, unrelated actors, formerly shared source revocation, erased-vector integrity, and feature revocation. The focused original/new Research and semantic suite passed 51 local File tests with 50 unchanged opposite-profile skips; three source-bound API catalog tests also passed. These focused results do not replace the corrected immutable tree's full hosted checks.

Final source and execution receipts, including any subsequent failures, must identify their exact commit/tree independently. Historical failures and the historical independent-review BLOCKED status remain intact.
