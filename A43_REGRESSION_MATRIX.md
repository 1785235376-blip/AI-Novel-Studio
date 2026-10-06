# A43 regression matrix

This matrix distinguishes assertion scope from execution. Final-source hosted receipts are still pending. Supplemental local Python is 3.12.14; locked hosted Python is 3.12.9. Opposite-profile skips never count as passes.

| Requirement | Assertion/owner | Execution status |
|---|---|---|
| Original A43-01/02 observation scripts | Unchanged portable appendix scripts against exact ad1a90d | Reproduced locally and in locked hosted baseline |
| Original A43-03 synthetic Session observation | Original portable appendix script, explicitly synthetic | Reproduced; not PostgreSQL evidence |
| A43-03 actual database wrong-object move/save | Original repositories + migrations; UUID/document/version readback and formal assertion | Actual PostgreSQL16.15 baseline RED, raw JUnit/JSON verified |
| Recursive rich text and unsupported-node atomicity | New rich-document tests | File supplemental GREEN; PG final CI pending |
| Original editor lists/marks/quotes/code/hardBreak and exact coordinates | Actual TipTap Editor, shared Python/JS coordinate fixture | Supplemental 3 new +7 original Editor tests pass; no Editor feature removed |
| Original export snapshot/queue/DOCX/EPUB/PDF full text | New tests use original NovelService/ExportJobService | File supplemental GREEN; PG final CI pending |
| Deleted-last/delete-all/archive/history/restart/collision | New File identity lifecycle tests and shared reference matrix | File supplemental checks; final exact-source regression pending |
| Same ID/version move, old URL/save/CAS/history/UUID | Original API aliases in both namespaces | File supplemental matrix GREEN; actual PG pending |
| Queued source results/acceptance after move/deletion | Original JobManager and repositories; no provider call | File supplemental matrix GREEN; actual PG pending |
| Warm cache/graph/context snapshots/search source/export queue | Original source-owning services | File supplemental matrix GREEN; actual PG pending |
| Concurrent move/save | Finite deterministic barrier, immutable logical owner | File supplemental matrix GREEN; actual PG pending |
| Legacy copy with no allocation log | Safe typed-UUID new identity; old numeric alias rejected | File supplemental matrix GREEN; actual PG pending |
| Existing contradictory history/references | Retain original bytes and quarantine unresolved ownership | File supplemental copy tests; actual PG migration pending |
| Parser/path/namespace collision | Canonical typed UUID and numeric syntax; tombstone uniqueness | New safety tests; final results pending |
| Additive migration/packaged boot/OFF/ON/V1/checksum/failure/readiness | Original packaged runner plus mandatory identity chain | Supplemental local checks; actual PG/native pending |
| Original full backend inventory/skip rules/strict aggregate | Existing suite_coverage + postgres_gate + reconciliation | Final exact-source File +2 PG shards pending |
| Original UI/build/browser/Interop/Windows | Existing unchanged workflow gates | Final exact-source runs pending |

The reference matrix applies nine journeys across File/PG, /api and /api/v1, experimental OFF/ON/forced-V1, and trusted-numeric/legacy-qualified identity namespaces. This is synthetic repository/API integration coverage, not independent historical review or real-model/native interactive acceptance.

The final deterministic inventory update must retain all 7,492 original backend nodes, relative ordering, source assertions and existing skip maps. Added nodes are reviewed explicitly. No original finite timeout or PostgreSQL gate is relaxed. Separate overlapping suites are not summed into a misleading total.

F00 remains INTEGRATED; 39 features remain PARTIAL. Historical independent review stays BLOCKED. All existing real-environment NOT_RUN/LOCAL_REQUIRED boundaries remain.
