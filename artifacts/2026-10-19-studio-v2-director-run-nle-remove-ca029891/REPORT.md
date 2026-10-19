# Reviewed limited increment: Director run overview and NLE selected removal

Product `f4a5327866007efa0a6bd3261086114216955a7b` → `ca029891abc51265b2f483414316c30ddfdacd08`; tree `3a078bf693c5991924670e9c40deecef091cb605`. Expected archive parent `dcc952bc68974c648200f424a3e7d4973e6d9711`. This append preserves all other f4 source entries; the archive branch's ordinary tree is not the current product source tree. This is not a Release or complete V2 acceptance.

The original Director patch `8b7b4e50` maps to `2b59d912`; NLE `b18d5497` maps to `ca029891`. Both stable patch IDs and all12 final file blobs match the reviewed originals. DSH, Audio/3D workbench and Asset/Prompt reserved work is unchanged.

Director comparison windows now explicitly read the original run directory, then the chosen run receipt, projecting only saved-version structural branch status. Shared/disabled descendants and missing statuses remain explicit. Original controller location leaves draft/history unchanged. No automatic query/poll/save/execute is introduced. Owner/version, busy, ABA, stale callback and late-result checks remain.

NLE selected removal previews the exact original non-ripple `clip.remove` batch and applies it through one original local history change. It preserves unselected clips, source pins, timing, captions, tracks and total duration. Invalid/locked/missing/duplicate/oversized targets, empty resulting tracks and dangling incoming transitions reject the whole batch. Descriptor and generation guards reject partial, foreign, ripple and old callback requests. Save remains explicit through the original CAS owner.

## Evidence by snapshot

- Original Director8b: 15 targeted tests and3 UI checks passed. An initial synthetic getRun mismatch failed correctly, then its fixture was corrected; the original failure is retained.
- Original NLEb18: 8 unique targeted cases passed across a first7/8 run and the corrected failed fixture1/1. The original schema rejected a transition opacity mismatch; no product/assertion weakening was used. Four isolated component geometry viewports passed.
- Independent cross reviews: three critical cases per feature passed; neither found a blocking issue. A reviewer initially counted existing Graph setup GET serialization as a new write; the corrected probe verifies its counter stays1→1 after overview/location. Both logs are retained.
- Combinedca: only two mounted smoke cases were selected, with12 cases filtered out: original Graph/controller location, and original NLE delete/Undo/Redo/explicit mocked CAS save/reopen. Both passed. One TypeScript `tsc -b` and one production Vite build passed; existing large-chunk warning remains. Original complete suites were not rerun. Counts above belong to their stated snapshots and are not additive.

The smoke/reviews use synthetic client fixtures, not real backend/media/model acceptance. Full V2, original-entry real backend E2E, native media rendering/IME/performance, external NLE interoperability and model/GPU quality are not claimed.

`evidence-sanitized.zip` includes selected logs/reviews, two fixture screenshots, source mapping, original/public provenance and per-file hashes. Executor paths/ANSI controls were sanitized. Runtime profiles, actual Host/session credentials, raw traces, DBs, dependencies, models, fonts and dist are excluded. See RESTORE.md for the sole f4 prerequisite and incremental recovery. Public download/parent/path/hash and isolated restoration receipts are produced after publication, separately from these sealed execution snapshots.
