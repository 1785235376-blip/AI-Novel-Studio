# Post-V1 R3 Feature Matrix

Baseline: PR #37 / `1ad947e458a1ebb4b0f74e06b4e0e3fb3322bab0`. Delivery: stacked Draft PR [#38](https://github.com/1785235376-blip/AI-Novel-Studio/pull/38). Every runtime feature below is server-owned, Experimental and default OFF. This matrix does not expand V1 acceptance.

`IMPLEMENTED` describes shipped engineering; verification labels describe the specific tested operation. `MOCK_ONLY` never proves literary, image or voice quality. See POST_V1_FEATURE_FORWARD_REPORT.md for the exact final test/CI revision and counts.

| Area | Implemented capability | Engineering status | Verification boundary / remaining gap |
|---|---|---|---|
| Foundation | Nine allowlisted flags; V1 acceptance override; existing API aliases | IMPLEMENTED | Default-off and enabled API contracts; no browser-side flag override |
| Foundation | Separate atomic scope documents, File OS locks and real PostgreSQL transactions | IMPLEMENTED | Additive migration 019; all 123 new PG parameters passed with zero skips at exact hosted implementation SHA |
| Foundation | CAS/history/source digest, scope isolation, fresh-process persistence and abrupt-exit rollback | IMPLEMENTED | Single Host, not distributed coordination |
| D05 planning | Project → Volume → Chapter → Scene hierarchy and editable structured fields | IMPLEMENTED | Source and ancestor versions fenced; arbitrary user theories supported |
| D05 planning | Three-act/escalation/alternative-ending templates plus custom templates | IMPLEMENTED | Templates are optional; no theory enforced as universal |
| D05 planning | Multi-proposal creation, comparison, approval, rejection, archive and historical restore | IMPLEMENTED | Approval changes experimental planning nodes only, never manuscript or legacy Canon |
| D05 planning | Structured adapter request/result schema and explicit Mock generation | IMPLEMENTED / MOCK_ONLY | Real local/remote planning provider and literary quality NOT_RUN |
| D06 import | Bounded resumable chunks; claims, pause/resume/cancel/retry/recover | IMPLEMENTED | Local heuristic adapter only; remote/unknown adapters fail closed |
| D06 import | Exact Unicode offsets, paragraph position, chapter version/hash and quoted evidence | IMPLEMENTED | Every approval rechecks evidence, including batch operations |
| D06 import | Cross-chunk deduplication, alias suggestions and conflicting attributes | IMPLEMENTED | Suggestions are not automatic identity confirmation; heuristic quality PARTIAL |
| D06 import | Characters, locations, timeline and foreshadowing checkpointed promotion | IMPLEMENTED | Original ImportApplyService owns writes; ambiguous interrupted writes require review |
| D06 import | Organization, world-rule and relationship candidate extraction/review | PARTIAL | Reviewable evidence exists; legacy promotion adapters are not configured |
| D06 import | 20-chapter / 320,475-character File pause/fresh-process resume | REAL_VERIFIED (File mechanics) | 80 chunks, 81 candidates, 1,080 verified evidence spans; synthetic local heuristic only |
| D06 import | Maximum-scale 12M characters / 12k chunks / 10k candidates | NOT_RUN | Bounds exist; production-scale performance and memory throughput not verified |
| D07 world | History/temporal relations, geography/ownership, civilization/faction, ability rules/use | IMPLEMENTED | Reviewed experimental Canon is separate from V1 Canon |
| D07 characters | Psychology snapshots/arcs, relationship evolution, chapter-state query | IMPLEMENTED | Narrative ordering and dependent-source changes invalidate stale state |
| D07 continuity | Dead-character reappearance, location ownership, ability limits/costs, temporal reversal | IMPLEMENTED / CONTRACT_VERIFIED | Deterministic checks, not unrestricted semantic reasoning |
| Unified Inbox | New planning/world/import/team/media/audio and eight legacy queue projections | IMPLEMENTED | Original-domain authority is preserved; inaccessible domains are explicitly unavailable |
| Unified Inbox | Filter/search/status/stale metadata, domain approval/rejection/reopen | IMPLEMENTED | Unversioned or detail-dependent legacy queues remain read-only with original-domain targets |
| Unified Inbox | Safe explicit batch operations and partial-result receipts | IMPLEMENTED | Only allowed reject operations across planning/world/import; not a cross-domain transaction |
| D13 teams | Eight role templates and four reusable human-approved recipes | IMPLEMENTED / CONTRACT_VERIFIED | Current executor produces contract artifacts; real model execution/quality NOT_RUN |
| D13 recovery | Atomic attempt/artifact receipt, host recovery, late callback/source/actor/scope fencing | IMPLEMENTED | Single Host recovery; no distributed scheduler |
| D10–D12 registry | 17 IMAGE/VIDEO/AUDIO input contracts; model identity separate from workflow | IMPLEMENTED / CONTRACT_VERIFIED | Discovery cannot register executable adapters |
| Media families | Qwen-Image, FLUX/FLUX.2, Z-Image, MiniMax H3, Wan, LTX, SeedVR2, RIFE definitions | PARTIAL / ADAPTER_REQUIRED | Definitions are not runnable workflows; GPU/model tests NOT_RUN |
| Cover/storyboard | Cover brief/safe areas, shot brief, generation tasks, compare/review, stable asset lineage | IMPLEMENTED / MOCK_ONLY | Explicit mock image adapter creates real decoded fixture PNGs; image quality NOT_RUN |
| Media review | Durable promotion intent, asset checkpoint, idempotent resume, stale reconciliation state | IMPLEMENTED | Cross-store promotion is checkpointed, not atomic; source changes may require manual reconciliation |
| Embeddings | Provider capability interface, vector schema, entity lineage, rebuild/invalidate/remove/query | IMPLEMENTED / CONTRACT_VERIFIED | Runtime defaults NOT_CONFIGURED; no lexical or fake-vector fallback |
| Embeddings | Explicit deterministic mock vector tests and provider/index/source fences | MOCK_ONLY | Real embedding provider quality/performance NOT_RUN |
| Audiobook | Dialogue attribution, NEEDS_REVIEW handling, profiles/mappings, emotion/style metadata | IMPLEMENTED / CONTRACT_VERIFIED | Real TTS quality and automatic semantic attribution NOT_RUN |
| Audiobook | Ordered segments, measured duration manifest, music/ambience/SFX slots, subtitles interface | IMPLEMENTED | Unmeasured segments remain unknown; no phoneme or lip-sync precision claim |
| Audiobook | Mixer interface and injectable local PCM16 WAV mixer; explicit mixed-asset review | IMPLEMENTED / CONTRACT_VERIFIED | Runtime mixer/TTS defaults NOT_CONFIGURED; non-PCM mixing needs another adapter |
| Collaboration | Exact project/workspace/storyline/branch metadata and review authorization | IMPLEMENTED | Source-free scoped metadata supported; base manuscript is never relabelled as branch evidence; branchless entities/legacy Canon remain project-level references |
| Collaboration | Branch-specific manuscript/entity source adapters | PARTIAL | Unsupported branch manuscript snapshots fail closed; shared project entity references are not branch-source parity |
| Optional profiles | Credential-free OS-vault-reference/profile/selection/revoke contracts | PARTIAL / CONTRACT_VERIFIED | No secret input/storage, no runtime write API or UI; OS-vault registrar not implemented |
| Optional governance | Existing V1 asset recovery/lineage preserved | MISSING (new R3 bulk tools) | No new bulk tags, replace/reimport or repair-proposal UI delivered in R3 |
| Inherited File lifecycle | Concurrent deletion and lazy document migration can resurrect a project | OPEN DEFECT | Deterministically reproduced; fixture quiescence is not a production fix; separate successor-branch remediation |
| V1 compatibility | Frozen PR/head/package/evidence unchanged; inherited CI retained | IMPLEMENTED | Full implementation push/PR CI passed; R3 Windows artifacts do not replace PR #37 acceptance |
| External verification | Real GPU/Qwen/H3/ComfyUI/TTS, paid APIs, interactive Windows acceptance | NOT_RUN | No private credentials, paid calls, signing, formal release, merge or deployment |

## Concrete implementation and test locations

- `app/experimental/{flags,store,common,api}.py`; `tests/test_r3_foundation.py`
- `app/experimental/{planning,world}.py` and corresponding routers; `tests/test_r3_{planning,world}.py`
- `app/experimental/{imports,teams}.py` and routers; `tests/test_r3_import_semantic.py`, `tests/test_r3_team_recipes.py`
- `app/experimental/{inbox,inbox_api,legacy_inbox}.py`; `tests/test_r3_inbox.py`, `tests/test_r3_mounted_contracts.py`
- `app/experimental/{media,embeddings,audiobook}.py` and routers; `tests/test_r3_{media_workflows,embedding_contracts,audiobook_preparation}.py`
- `app/experimental/provider_profiles.py`; `tests/test_r3_provider_profile_contracts.py`
- `frontend/src/experimental/`; `frontend/tests/e2e/r3-experimental.spec.ts`; `frontend/playwright.experimental.config.ts`
