# ACCEPTANCE_MATRIX — M1 — [HERMIA-FE-20261023 M1]

> [HERMIA-FE-20261023 M1] Branch `work/hermia-unified-workspace-20261023` · base 6ba25ad7a47ed7677c32483b5234b656a3c0c2ed (tree 4193b3c22c49647dfc6e52241b5ff459f0064654) · M1 code commit 5aa20a4a75b28203702f8fac4056eed545e5ea4e (tree 32562dbfb206b6b5094c27ea78c665d7bbd8762b). Model: cannot be verified from inside the bot.

Level: U = unit (pure), C = component (RTL/jsdom, mocked geometry). PASS here means passing at that level only — not in a real browser. Test names carry the IDs. Mapping of IDs to behaviours is Hermia's reading of the spec.

| ID | behaviour | level | status |
|---|---|---|---|
| M1-01 | panel drag / float move, stays in viewport | U+C | PARTIAL (float move OK; docked drag = zone drop, no precise reorder) |
| M1-02 | resize with min/max, pointer + keyboard | U+C | PASS |
| M1-03 | drag to dock zone | C | PASS |
| M1-04 | redock, old relation removed | U+C | PASS |
| M1-05 | collapse/expand keeps state | U+C | PASS |
| M1-06 | close / reopen | U+C | PASS |
| M1-07 | split switch | U+C | PASS |
| M1-08 | reset default with confirm, content kept | U+C | PASS |
| M1-09 | persist + restore after reload (remount) | U+C | PASS |
| M1-10 | save failure status; focus/z-order | U+C | PASS |
| M1-11 | migrate old formats (workbench v2/v1, AppShell keys) | U | PASS |
| M1-12 | missing fields → defaults, extra fields kept | U | PASS |
| M1-13 | unknown panels preserved | U | PASS |
| M1-14 | corrupt data → default + warning + backup | U+C | PASS |
| M1-15 | invalid size/dock repaired | U | PASS |
| M1-16 | idempotent repeated migration | U | PASS |
| M1-17 | migration interrupted → raw intact | U | PASS |
| M1-18 | reset only touches layout key | U | PASS |
| M1-19 | repeated close/reopen no duplicates | C | PASS |
| M1-20 | dirty close → save & close after real save | C | PASS |
| M1-21 | dirty close → cancel keeps draft | C | PASS |
| M1-22 | discard only this panel | C | PASS |
| M1-23 | no duplicates / listener cleanup | U+C | PASS |
| M1-24 | late async results ignored (cancel/unmount) | C | PASS |
| M1-25 | save failure keeps panel, real error | C | PASS |
| VIEWPORT | real viewport sizes (1280/1440/1920, small) | browser | NOT_RUN |
| ZOOM | browser zoom 80–200% | browser | NOT_RUN |
| E2E | end-to-end in the app | browser | NOT_RUN (module not wired) |

Counts: PASS 24 · PARTIAL 1 · FAIL 0 · NOT_RUN 3.
