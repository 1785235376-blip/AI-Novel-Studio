# Hosted V2 browser findings at head 99e3c63

Actual PR artifact **11602858790**, run **37902141902**, job **113726946074**. Artifact revision receipt identifies tested merge checkout **42d8355c00eb545d40ab503c4429315bb7eef74e**, associated branch head **99e3c636bc59f45f5faa4b7af84b80981f1ec2e5**. Exact archive, file and source digests are in [source-identity.json](source-identity.json).

## Genuine results

- Live File/backend/Chromium suite: **5 passed, 2 failed**, 7 total, no skips.
- Mocked workbench suite: **5 passed**, including geometry at 1366×768, 1440×900 and 1920×1080. Mocked geometry is not backend integration proof.
- Successful screenshots establish progression through saved screenplay, explicitly reviewed Director, and saved Production v2. The authoring scenario subsequently fails during reopening after restore/reload; it is not a completed browser pass.
- Both reopen failures visibly retain the saved document in the asset list while displaying an unnamed empty draft in the canvas. Production shows saved **v3 / 2 scenes** in the sidebar but an empty title and 0 timeline segments centrally; Screenplay shows **v1 / 2 scenes** in the sidebar but an empty central draft. This supports a frontend selection/hydration mismatch; screenshots alone do not prove its exact internal cause.
- The passed stale-write scenario visibly preserves the local draft, locks conflicting writes, and exposes an explicit server-version check. The cancellation screenshot preserves unsaved text before the later reopen failure.
- Additional visual observation: after the timeline has scrolled to notes, reorder-arrow controls visibly paint across its sticky header (over/near “Production Timeline”) in the Production screenshots at all three sizes. This is a recorded finding, not a repaired or accepted layout.

## Evidence

- [Production reopen failure](screenshots/failure-production-reopen.png)
- [Screenplay reopen failure](screenshots/failure-screenplay-reopen.png)
- [Saved screenplay](screenshots/live-screenplay-saved.png) and [reviewed Director](screenshots/live-director-reviewed.png)
- Saved Production at [1366×768](screenshots/live-production-1366x768.png), [1440×900](screenshots/live-production-1440x900.png), [1920×1080](screenshots/live-production-1920x1080.png)
- [Preserved conflicting draft](screenshots/live-stale-write-preserved-draft.png)
- Original failed logs, JUnit XML, JSON results and revision receipt are under [receipts](receipts/).

The original 24,361,394-byte ZIP was materialized via the canonical file download and safely extracted with path-traversal/symlink checks and explicit size/count bounds. Raw trace ZIPs remain only in the runtime artifact directory; their paths and digests are preserved in the identity manifest. No private signed download URLs are included. No source edits, test reruns, PostgreSQL changes, real model calls, paid provider execution, or Windows acceptance were performed for this inspection.

## Pixel-level inspection notes

Coordinates below refer to the original unmodified screenshot pixels (approximate bounding regions, origin at top-left).

- **Production reopen failure, 1920×1080**: left sidebar region x32–240 / y278–334 visibly contains the saved production title and `v3 · 2场景`. Central region x298–1530 / y276–402 instead contains `未命名创作文档`, `新草稿`, and an empty title field. The timeline badge around x874–925 / y807–830 reads `0 段 · 0s`. Together these show saved asset visibility alongside an unselected empty canvas.
- **Screenplay reopen failure, 1440×900**: left sidebar x32–240 / y278–334 shows `云港 · 合成剧本` and `v1 · 2场景`; central x298–1050 / y276–402 shows the unnamed new draft and blank title. The right queue still shows the cancelled proposal.
- **Timeline overlap, saved Production 1440×900**: header spans approximately x285–1063 / y603–671. Left reorder control x298–324 / y604–638 overlays the English header text; right reorder control x624–650 / y604–638 also paints in the sticky header band.
- **Timeline overlap at 1366×768**: same controls are around x298–324 and x624–650 / y472–506, within header y472–540.
- **Timeline overlap at 1920×1080**: same controls are around x298–324 and x624–650 / y784–818, within header y784–852.

These observations identify the affected pixels without cropping, editing, replacing, or re-rendering any evidence image.
