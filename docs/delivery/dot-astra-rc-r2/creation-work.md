# D03/D05/D06/D07/D14 authoring integration

Actual Astra changes on the inherited f8c141c baseline:

- Source privacy reviews bind project/chapter/branch, current chapter version and SHA-256. The inspector has an explicit control; unknown, stale, corrupt or revoked policies deny future cloud egress. Already dispatched requests cannot be recalled.
- Generation ownership is verified before the idempotency cache. Keys bind trusted actor/workspace/project/branch and chapter; mismatched request content returns 409. Variant-group reads authorize every job. Raw output remains Draft and existing Accept/history/conflict behavior stays protected.
- Structured author plans include STYLE/PLOT and manual history/geography/civilization/ability/psychology records, persistent versions, source references, explicit approval, compare, archive and restore-to-new-draft. Approved style/plot inputs are used by generation and rechecked before dispatch. Manual world records are not claimed to be autonomous semantic engines.
- Comments/replies bind a chapter revision and optional exact quote; stale/missing anchors are visible, resolve/reopen and actor history persist, and backend scope equality isolates branches.
- Local knowledge extraction uses overlapping bounded windows and exact source offsets/hash/version; English/Chinese heuristics are labeled. Same spelling in different chapters is not silently assumed to identify one person.
- Existing-project/chapter review now creates local candidates immediately, preserving editable fields. Empty selection never expands to all candidates. Review edits have CAS; corruption is explicit and cannot be overwritten as an empty store.
- Acceptance uses durable per-candidate checkpoints. It is not a single cross-entity database transaction. Ambiguous interruption and changed targets require review, preserve partial progress and never report full acceptance.
- Import AI analysis rechecks current identity, source versions/hash, stored restrictions/secrets, explicit chapter policy and explicit excerpt consent immediately before controlled provider dispatch. Concurrent review edits prevent late AI replacement.

Existing tests were deliberately adjusted where a prior expectation represented the old contract: synthetic idempotency fixtures now provide a valid chapter at the mandatory ownership check, old global cache seeds use the new scoped digest envelope, and mock catalog records include explicit execution_mode. No failure was skipped or xfailed to obtain a pass.

Focused evidence and full final-SHA runs are listed in TEST_RESULTS. Real model quality/remote calls, interactive Windows and user acceptance remain separate NOT_RUN gates.
