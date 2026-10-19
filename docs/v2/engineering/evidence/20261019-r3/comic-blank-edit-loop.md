# Comic blank-page edit loop — real execution evidence (round 3)

SPEC binding: `SPEC-2026.10.19-r1` sha256 `a681eb0f1deff156bbb2a7db437e19cabc11f290d28416f9f0c8fe8bd07785ac`
(requirements IMAGE-COMIC-01/02/04/09/13/15/18 subset).

Owner reused (no new Comic Studio, no second asset database):
`app/experimental/comic_layouts.py` + `app/experimental/comic_layouts_api.py` on the original
ExperimentalStore CAS, `AssetLibraryService`, trusted-session/role authorization, review flow and
export path.

New behaviour in this round:
- `source_mode = STANDALONE` page records: no screenplay/chapter prerequisite, no shot id required;
- optional page metadata (`page_number`, `reading_direction`) and stable page ordering in `/records`;
- single-record `GET /records/{rid}` reopen endpoint;
- export manifest now records `source_mode` and the page identity;
- existing SCREENPLAY mode remains default and its B06 suites still pass.

Test command (executed on Windows, file backend, offline):

```
python -m pytest -q -p no:cacheprovider -m "not postgres_backend_only" \\
  tests/test_v2_comic_blank_edit_loop.py tests/test_r5_comic_layouts.py tests/test_r5_comic_mounted.py
```

Result: **41 passed, 1 skipped** (the skipped item is the documented real-PostgreSQL parameter; no
model, provider, GPU or network was used).

Verified closed loop in `tests/test_v2_comic_blank_edit_loop.py`:
create blank page with no screenplay → reopen by id/list → empty-panel blocker → import an existing
approved Image asset → attach panel image + bubble → CAS save v2 → text-only edit v3 with the image
asset version/sha256 and preview bytes unchanged → preflight → approve → export ZIP segments +
manifest (STANDALONE, page 1, LTR) → unreviewed edit cannot export → second page → page ordering →
catalog declares no model requirement → viewer/other-branch/unknown-asset/revoked-authority fences
(passed with the real collaboration stack; the file-backend test also exercises the mounted `/api/v1`
prefix).

Honest gaps vs SPEC (why these rows are IMPLEMENTED/PARTIAL and not ACCEPTED):
- no manuscript→comic proposal (IMAGE-COMIC-03), no volume/chapter tree above pages,
- bubbles are plain text objects (no vector tail/orientation/kerning controls),
- panels use the existing bounded geometry (no drag/template/bleed tooling),
- no ORA layered interchange, no CBZ/PDF/EPUB export, no animation hand-off,
- no AI generation was used or claimed; model-based panel generation remains a separate task.
