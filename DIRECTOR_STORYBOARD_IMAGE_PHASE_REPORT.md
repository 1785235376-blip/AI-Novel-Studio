# Production Expansion Phase 2 — Image, Director and Storyboard

Date: 2026-10-14 (Asia/Shanghai). Baseline: `a79b7f9d6fbacfd112ac42f2082798b2cd7f9233`.
Repository: `1785235376-blip/AI-Novel-Studio`; branch: `feature/v2-narrative-platform`.
PR #47 remains Draft. This is a bounded development increment, not release or M5 acceptance.

## Implemented source

### Image

- Optional authored reference purpose (`character`, `outfit`, `environment`, `style`, `composition`) and source note accompany the original exact Asset ID/version/SHA and weight. Unset additions do not change old request identities. Purpose is provenance metadata; existing multi-reference conditioning remains normalized pixel initialization, without a learned identity guarantee.
- Explicit schema-4 `image_style` preserves references and document evidence while composing bounded style/atmosphere/color instructions. Original schemas 1/2/3 and default catalogs remain unchanged; the preceding image catalog retains its IDs/capabilities/defaults while adding optional reference metadata schemas.
- Independent `image_upscale` and standalone `m5.image.upscale` now dispatch through the original ImageJob, private candidate, explicit human review and Asset version owners. Only an explicitly enabled local Model Center Comfy registration with positively validated loader/node/component schemas is admitted. Real-ESRGAN, SwinIR and other compatible declared models use the same fixed recipe. Providers never download models.
- Upscale uses the installed model followed by a fixed Lanczos resize to the requested 2×/4× target, not a claim about the native model's scale or quality. Source side <=2048; target side <=4096; <=16,777,216 pixels; PNG <=25 MiB. Actual decoded dimensions, source/output SHA, size and scale are validated and persist in the original receipt. Wrong dimensions, stale source, revoked registration and corrupt proof cannot promote a candidate.
- Model-agnostic Depth/Pose/Edge/Mask/Layout Control inputs are bounded typed reservations: `NOT_CONFIGURED`, execution unavailable. Existing authored inpaint is unchanged; reserved control types do not confer execution authority.

### Director and Storyboard

- Original Creative documents accept an opt-in visual target: style, atmosphere, reference works, color and rhythm. Director notes add shot suggestion, composition, lens, character state and typed character/action/expression/state suggestions. Original source evidence, scope/incarnation, CAS, history, archive, restore and review remain authoritative.
- Storyboard shots add explicit characters and emotion, alongside existing stable shot ID/number, scene, camera, lens, composition, movement, duration, action, dialogue and sound. Independently authored Director/Storyboard documents require no novel chapter. They retain their own scenes and are never forced to derive from a novel.
- Explicit `DIRECTOR_NOTES` derivation creates one shot per ordered director note, copies the authored target and suggestions, and binds the original document version/digest. The existing default scene derivation remains compatible. Derivation creates an editable draft with `HUMAN_REVIEW_REQUIRED`; it does not rewrite the source or attest visual quality.
- The original optional Director model coordinator receives rich goals/output schema only when explicitly provided. Goal changes invalidate the exact preview/output/review identity. That model path still requires its existing chapter anchor; scene-free Director model execution is not implemented by this increment.

### Graph and frontend

- An explicit production catalog adds `director_plan` → `storyboard_plan` → `storyboard_prompt` → `image_style` → existing `image_generate` → original `media_review` → formal Asset, and the independent Upscale→Review path. Planning nodes read already saved original documents; they do not accept suggestions or mutate user content.
- `DIRECTOR_PLAN`, `STORYBOARD_DATA`, `IMAGE_PROMPT`, `MEDIA_CANDIDATE` and `ASSET_REF` are finite typed outputs. Exact document versions/digests and recursive original source/privacy checks are repeated on reads, admission, execution, publication and recovery. The original raw scope→Asset→Project order is retained. Selected shot and Director ancestry are checked before run admission; original 64 KiB node-output and graph capacity limits still apply.
- `/studio/graphs/planning-documents` is a passive, Host-protected bounded picker over the original Creative owner. It returns ID/title/mode/version/digest, not another document registry.
- Original Canvas/Inspector/controllers add target and performance editing, shot cards/list/preview, pinned document selection, style/upscale controls and strict server receipt decoding. Complex fields are expandable. Shared tokens/shell/components, parent mutation exclusion, Host/scope retirement, CAS, dirty/UNKNOWN and explicit private-candidate review remain Opus's protected boundary.
- Storyboard data and the original explicit Production derivation remain reusable for later consumers. A Video Graph consumer and Video execution are not added here.

## Verification

Final selected results and input/hash mapping are recorded in the companion JSON. Counts for overlapping selections or File/PostgreSQL runs must not be added. Collection is inventory, not execution.

Final code/test input tree: `f37fd76f6c07fdc4f0e405ab708dc1c485dff288`; source map SHA256: `a9e6dd08c5a92a0af404894722b1e4ea5c1799293353d5808bd64cdb4d0d8821` (1942 files). [Measured JSON](docs/v2/production-expansion-phase2-20261014.json) provides the 56 changed code/test hashes and receipt hashes. All final checks below preserve the same frozen source.

| Check | Actual result |
|---|---|
| Six new backend modules, File | 119 passed / 67 profile applicability skipped / 0 failed |
| Same new modules, fresh real PostgreSQL | 117 passed / 2 failed / 67 applicability skipped |
| Complete frontend | 3000 passed / 8 unchanged skipped / 0 failed |
| TypeScript / Vite / design tokens | PASS / PASS / 52-file check PASS |
| Original visual regression | 3 shell snapshots + 4 geometry PASS; no baseline update |
| Original metadata selection, Windows | 44 passed / 2 WinError1314 symlink-privilege fixture failures |
| The same two original symlink assertions, existing Linux runtime | 2 passed separately; Windows failures remain failures |
| Original catalog / coverage generators | 2221 operations, none removed; 13813 collected nodes; all 9151 frozen nodes retained |

Earlier related 14-module runs are retained: File343 passed/205 skipped; PG323 passed/20 failed/205 skipped. They preceded the final contract corrections and do not replace the frozen final results.

The two final PG failures are `test_original_synthetic_director_executor_carries_goal_rich_notes_and_review[postgres-/api]` and its `/api/v1` alias, both at the unchanged 5-second Broker ledger settlement deadline. A single paired diagnostic of an unchanged original invalid-JSON case fails on both a79 and current source: raw generation5750ms current vs5844ms baseline, with no observed database lock waits. This demonstrates an existing finite execution/polling limit for that representative case; it does not attribute every other failure or convert any FAIL to PASS. The Director PG gate remains BLOCKED. Assertions/deadlines were not modified and tests were not rerun until green.

No complete CI/Windows/GPU/model acceptance is claimed. Private raw logs/databases/observer details are retained outside the published summary; owned PG servers are stopped, and the Linux runtime returned to its previous stopped state.

Actual File/PostgreSQL stores, original Host API test sessions, real PNG decoding and synthetic provider HTTP are used. No installed model, GPU inference or final Windows application acceptance is claimed.

All unsuccessful attempts remain private evidence: newly authored fixture/default assumptions; the initially missing Graph upscale proof projection; and the reproduced malformed document-version reader defect, followed by the strict integer fix. Original assertions, fixtures, skips, frozen baseline, generators and prior failed receipts are retained.

## Remaining limits and gates

- Image/Director/Storyboard whole-module status: `PARTIAL`; bounded new source: `IMPLEMENTED`; real model/Windows/GPU acceptance: `LOCAL_REQUIRED` / `NOT_RUN`.
- No Control inference, native learned multi-reference identity assurance, scene-free Director model coordinator, new Video consumer, full UI/UX redesign or whole-product completion is claimed.
- Full milestone CI and original M4→M9 acceptance gates remain. Hosted runner failures without executed steps are infrastructure receipts, not product test outcomes. Historical PG timeout/failed-call, incomplete File/strict-summary gates, F00 INTEGRATED + 39 PARTIAL and independent review BLOCKED remain unchanged.
- No main merge, Release, V1/frozen evidence/Local Interop semantics change, QingJian work, model download/launch or paid API call.
- Publication SHA and passive hosted status are recorded from the actual remote receipt in PR #47, after normal push; this report does not invent a self-referential commit hash.
