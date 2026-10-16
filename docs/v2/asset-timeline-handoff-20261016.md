# Exact asset reference → original timeline draft — 2026-10-16

Baseline `97ae193694dab8e01bc86951fa6f576d9945a522`; containing commit identifies this local slice. This closes one bounded independent-module handoff, not unified output/export completion.

## Audit and actual workflow

The previous AssetBrowser TIMELINE callback only showed a notice. The mounted original browser now carries a transient exact asset ID/version/digest through the existing dirty-navigation decision into StudioTimelineEditor. No module is executed by sending a reference.

1. Explicitly choose TIMELINE in the asset browser and generate the reference. Unsaved input keeps the existing continue/discard decision.
2. At the target, explicitly read current metadata through the captured original `studioClient.asset` and guarded identity/scope transport. A changed/deleted/missing source is rejected; the latest version is never substituted.
3. Choose an existing compatible, unlocked track. Legacy video/audio and explicit v2 image support retain the original timeline schema rules. Track creation/schema upgrade remains an explicit original-editor action.
4. Explicit acceptance rereads that exact source. It checks current owner, original-controller operation/draft generation, target track, unchanged draft, compatibility, deletion, clip budget and available timeline duration. Intervening edit→undo, busy→ready, target adoption, client replacement or cancellation invalidates a pending approval.
5. One original `change` appends a pinned clip with the existing insertion defaults and one undo step. Existing authored clips/effects, captions, canvas/audio settings remain intact. Explicit original Save/read/adopt reopens the draft; CAS and UNKNOWN behavior remain authoritative. No automatic save, render, download, review, model/provider call or external dispatch.

The handoff is session-only and clears on scope/identity/target lifetime changes. Cancelling removes its ability to apply. A consumed request cannot add a duplicate, including after undo; a new deliberate send is required. Source actuality can still change after the read, so original save/preflight remains authoritative.

## Unified delivery is still blocked

`IndependentStudioWorkspace` mounts `DeliveryCenterPanel` without items or entitlements. No authoritative production `DeliveryEntitlements` producer was found. `manual_export` is a general capability, not an identity-specific grant with formats/kinds/limits. The delivery default-deny behavior is unchanged; no grants, entitlement APIs, permission gates, delivery formats or owners were synthesized. `ItemExportPanel` remains an inspection surface and receipts remain read-only. Original AssetLibrary original-file download is untouched. IMAGE/VIDEO/STORYBOARD reference handoffs remain outside this slice.

## Verification and limits

Final selected checks: 110 mocked UI tests, one original nonsecurity File exact-reference save/reopen/CAS test, and 30 PUBLIC contracts. TypeScript, Vite build, test discovery, token guard and 487-file PUBLIC source closure are checked separately.

Exact commands, timestamps, exit codes and source fingerprints are in the adjacent JSON and retained local verification receipts. Exploratory failures were test-only matcher/label/fixture-type mismatches, corrected before final checks. Independent review identified the metadata-read ABA race; the original-controller generation fence and mounted regressions address it.

No browser/visual/native input/assistive-technology acceptance, GPU/provider/Windows/user-computer, PostgreSQL/P0 lifecycle/security, hosted CI or full RC was attempted. The canonical image-workspace reference and DS-v1.0 were inspected; shared shell/primitives/tokens are unchanged. Existing Vite large-chunk and Starlette deprecation warnings are not acceptance claims.

P0 stays BLOCKED, R3-GATE HOLD, production Prompt Adoption writes disabled. No new store, queue, backend contract, permission or execution budget. No push/hosted CI because cost remains unknown; no main merge/tag/release. Parent independent review precedes any next tracked slice. Remaining independent module handoffs and unified-delivery owner-contract work remain PARTIAL/BLOCKED as described above.
