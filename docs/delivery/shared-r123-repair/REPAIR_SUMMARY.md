# R1/R2/R3 shared repair checkpoint

## Source and evidence

Independent DraftPR40 is based on untouchedPR39 `c6f2126115b52e17839d48efea091dc21ec08c61`. The first evidence-only head is `1c88a7dfb821b9ba72425c180bd95ba3140fd079`. All three supplied scripts were preserved unchanged and run separately against a fixed archive before runtime edits. Supplemental local execution used Python3.12.14 with all31 constrained dependency versions matched. Dedicated hosted Python3.12.9 runs37402995698/37403004721 also explicitly reproduced all three known RED observations on untouchedc6f2126. `BASELINE_RED_PYTHON3129.json` retains the actual receipt. Original observations remain defects, even though the evidence harness succeeds at detecting them.

## Before and repaired contracts

- R1 before: both API prefixes accepted a real synthetic Host-issued workspaceA session against workspaceB, disclosed chapter content/raw metadata/overview/goals, and persisted unauthorized goal4321/7. Controls correctly returned401 without token and403 on protected export. After: those same reads/writes return403, no target body or count is disclosed, and no goal mutation persists. Current original membership and read/write/review authority is now explicit across119 route registrations and additional global lists/totals/top-level aliases/creation/import. Positive owner/member, read-only reads and non-mutating denied writes are retained. Exact scope and supported legacy chapter CAS/history semantics are documented in `R1_ROUTE_INVENTORY.md`.
- R2 before: a new read returned401 after session revoke while an established SSE emitted subsequently produced body. After: the revoked subscriber closes without new body; a separately authorized subscriber continues and the shared job remains uncancelled. Checks run before/wake/read/yield and after threadpool handoff at ASGI send. The first repair's idle-disconnect failure remains recorded, and an explicit receive watcher fixes it without weakening its assertion. Already transmitted bytes cannot be recalled.
- R3 before: generation-time reject returned200/REJECTED without cancellation; the worker later persistedCOMPLETED with only the first chunk. After: execution-time and SETTLING reject return409 and leave the draft running; first/last/completion-event barriers all finish with exactly `SYNTHETIC_FIRST_CHUNK_LATE_CHUNK`, matching memory, durable state and HTTP/SSE. Completed and settled review can becomeREJECTED and stays so after reload. Worker/finalizer/recovery locks preserve terminal decisions and once-only accounting, including unknown-use holds and conservative persistence/reconciliation failures. The unchanged original R3 script's post-fix schema error is preserved; explicit new assertions establish the repaired contract.

## Verification layers at this checkpoint

- R1 focused supplemental:469 PASS/456 backend-only SKIP; new R1 suite423 PASS/422 PG counterparts awaiting hosted execution.
- R2 actual loopback supplemental:70 PASS/70 PG counterparts awaiting hosted execution. These are actual network SSE, not an in-process replacement.
- R3 focused supplemental:277 PASS/188 backend-only SKIP; new R3 suite146 PASS/146 PG counterparts awaiting hosted execution.
- Original test files and assertions are unchanged. No skips, permission defaults or original CI test commands were weakened. The extra evidence workflow only proves the old baseline is RED.
- Final acceptance of this repair requires the actual pushed final head's original five CloudCI lanes, with pinned Python3.12.9/Node22.14.0, File and realPostgreSQL16, frontend/unit/type/build/token/browser, Windows compile/native contracts and fresh internal package. These supplemental counts do not substitute for that run. The final parent receipt and DraftPR40 identify its exact SHA/tree/run IDs and conclusions after terminal readback.

## Scope and residual limitations

No new feature, merge, release, deployment, actual backport, paid API, real private project or runtime installation is part of this work. All experiments remain defaultOFF and V1-enforcedOFF. The product matrix remains39 PARTIAL plus F00 INTEGRATED. Real model/GPU/TTS/translation quality, Windows IME/vault/installation and target applications remainNOT_RUN. Original project-level chapter storage is not branch-exclusive manuscript storage. Distributed ownership/atomic cross-host revocation and retroactive transport-buffer removal are not claimed.

The historical independent follow-up review remains platformBLOCKED without restart, rephrasing or rerouting. This ordinary implementation regression neither replaces nor closes that historical review. PR37 `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0` and PR38 `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b` remain frozen. Shared repair backports are candidates only in `BACKPORT_CANDIDATES.md`. OPUS_UI_HANDOFF preserves the403/409/revocation/source/budget boundaries for later separately authorized design work.

## Integration failure history retained

A moving-worktree diagnostic full File run during implementation produced11 failures,4094 passes and1704 expected skips. It is not a fixed-head acceptance receipt: three old generation-boundary unit doubles exposed an over-broad new source lookup, one original packaged-bootstrap test exposed a separate-registry seam, and seven newly added R1 tests were collected while their implementation/fixture inventory was still changing. The original generation context contract is retained, with stronger source lifetime validation specifically on live streams. Packaged project/list authority now resolves the actor through the current Host issuer, then independently checks project permission; the original packaged test remains unchanged. That original packaged suite plus all final R1 cases then passed441/422 backend skips. Original failed receipts remain preserved, and the final pushed head must receive its own complete CI and fixed-source test process.

Raw failing pytest output is intentionally preserved including its whitespace. Runtime, tests and authored Markdown pass whitespace checks; do not edit raw failure evidence to make a formatting check green.
