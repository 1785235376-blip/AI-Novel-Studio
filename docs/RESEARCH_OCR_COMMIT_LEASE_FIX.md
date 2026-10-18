# Keep original project incarnation leases through Research commits

A follow-up source audit found that the coordinator's `with store.transaction(...), lease():` order released the project-incarnation lease before the underlying Research transaction committed. The new deterministic regression runs the original real store and inspects lease depth in the current writer thread at its commit boundary. It failed on the previous implementation (`native-ocr-commit-lease-red`: 1 failed, 17 deselected). This proves the ordering defect, not a demonstrated cross-project authorization exploit.

Preview, claim, result publication and failure updates now reuse the original broker `_owned_transaction` helper. Its ExitStack holds the original scope-then-project lease until the scope transaction has committed. Native Research cancel/review/invalidate retain a deferred original lease entered by their existing in-transaction guard through the original ReviewAdapterJobs action commit. No second persistence or workflow owner is introduced. Generic run/recover actions cannot start or reset a native receipt; original native execution and reconciliation ownership remains required. Non-native behavior is unchanged.

Verification:
- File green: 21 passed, 21 PostgreSQL cases deselected, including existing Research and mounted route regressions.
- PostgreSQL green: 22 passed, 22 File cases deselected; reused original UTF8 test database OID 16384, server stopped. Includes the added generic run/recover refusal and unchanged raw-state assertions.
- Final focused File/catalog/PUBLIC: 7 passed, 1 PostgreSQL case deselected, actual offline PUBLIC wheel included.
- The commit-boundary regression exercises native preview, actual native OCR dispatch/publication and human review; no mock replaces the actual File or PostgreSQL transaction.
- API source binding refreshed; 2365 mounted method/path entries remain. Frontend source is unchanged in this slice.

Earlier passing reports and the new RED are retained. Full orphan reconciliation and production browser acceptance remain pending.

Remote heads were rechecked at 2026-10-18 10:05 UTC: main fed2404c8e30b44061b7139dced45b7f3301601c; PR #47 a072cf907f574ae7cfebcc8f413e2f1a7fa4a6e3; PR #48 58bbaad11360330d51f49fc2bb78a955a26469f0. Both PRs remain open drafts; no overwrite, merge or Release occurred.
