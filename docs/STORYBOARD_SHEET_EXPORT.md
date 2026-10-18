# Source-pinned Storyboard shot-list CSV

2026-10-18. Saved planning handoff through the existing Creative owner.

A clean saved Storyboard can explicitly export a UTF-8 BOM CSV containing ordered
shots, saved document identity/version/digest/status, scene labels, durations,
framing/camera/composition, image prompt, action/dialogue, sound and authored
continuity/director references. Nested authored fields are JSON cells. This is a
planning list, not rendered frames, a video, an NLE project or approval evidence.

The additive storyboard-sheet-export GET uses original domain.read authorization
and CreativeService._export_saved: encode outside the transaction, reauthorize,
re-read the exact version/digest and reauthorize again before returning bytes.
The new response is no-store. The original document/shot schema and CSV cell
escaping are reused; no owner, executor or storage schema is added. Capacity is
2,000,000 output bytes, with full refusal rather than a truncated partial export.
Potential spreadsheet formulas receive the existing leading-quote mitigation;
application/re-save behavior is not universally certified, and JSON remains the
full-fidelity original record.

The original CreativeWorkspace mounts the existing guarded sheet-download control
for a clean saved STORYBOARD. It reuses the captured original client/session,
explicit GET, version/digest/hash headers and actual byte hash validation. Dirty,
busy, blocked, revoked and replaced document contexts cannot silently export a
newer or different draft. The existing Director sheet control and route remain
compatible, with their original tests unchanged.

Evidence:
- storyboard-sheet-export-file-ui-r1: 24 File-side checks, 11 PG deselections;
  33 UI checks plus TypeScript and Vite build passed.
- Final backend after explicit no-store header: storyboard-sheet-export-file-r2,
  24 passed, 11 deselected. Frontend bytes unchanged from the successful r1 build.
- storyboard-sheet-export-pg-r1: 11 passed, 24 deselected on real PostgreSQL 17.11,
  retained database v2_director_pending_green_20261018, OID 31303. Explicit reuse,
  not a fresh migration. The owned server was stopped successfully afterward.
- Tests inspect reopened original documents and unchanged persisted scope state,
  ordered Unicode/quoted fields, permission/version/capacity refusals, mounted
  read authorization and download receipt hashes. UI transport is mocked/jsdom;
  backend mounted requests use TestClient, not product browser E2E.

No real spreadsheet/NLE/browser/Windows/model acceptance, full API-inventory
regeneration or V2 release completion is claimed. Existing global catalog snapshots
remain source-bound historical artifacts until their dedicated reconciliation.
The original public allowlist already includes the reused encoder/service/router;
no new module, private backend or dependency was added.
