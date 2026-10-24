# M4 usability — slice M4-s1 [HERMIA-FE-20261024 M4-s1]

Branch `work/hermia-uw-m4-20261024` (from 3520d679). Scope: `?uw=1` DockLayout only (frontend/src/workspace/**) + tests. No model calls, no network writes.

## Changes
- Skip link 「跳到主区域」: first Tab stop, hidden until focused (visible + focus ring), moves focus to main zone (`role=main`, `aria-label=主区域`, `tabIndex=-1`).
- Main-panel tabs: `role=tablist`/`role=tab`, `aria-selected`, `aria-controls`, roving tabindex; ←/→/↑/↓/Home/End move focus and activate. (Tests that read `aria-pressed` updated to `aria-selected` — same strength.)
- Splitters: `aria-valuemax` (effective limit incl. main 320×200 rule), `aria-controls`, `aria-valuetext`; Shift+arrow = 64px; Home/End = min/max. Esc during pointer resize restores the starting size.
- Panels: stable `id`, collapse button `aria-controls`.
- CSS: generic `:focus-visible` ring inside layout, panel/main focus rings, `overflow:hidden` on layout root, toolbar items shrink/wrap, status text wraps, panel headers wrap, `.uw-main` min 320×200, reduced-motion.
- Shared-file patch (not applied): `patches/m4-s1-commandsearch-initial-focus.patch` — workbench/CommandSearch focuses its trigger on mount, stealing initial focus from the skip link; patch only refocuses after the palette closes.

## Tests (Node 22.14, targeted only)
- `vitest run src/workspace src/workbench src/rebuild`: 42 files, 286/286 PASS (new `layout/m4s1.test.tsx`, 5 tests). Full suite NOT_RUN (combined run by Hermia main).
- `tsc --noEmit`: 6 errors (baseline).
- jsdom prints a pre-existing "Not implemented: navigation" console error; not a failure.

## Browser (real Chrome, vite :4310, logs/m4s1-browser.mjs → .json)
- 1366/1440/1920 × zoom 80/100/125/150/200 (15 configs): no horizontal overflow, main ≥320×200 (min seen 320×200 at 1366/1440 @200%), toolbar children within viewport (wraps to 92px at ≥150%), 0 non-GET requests, 0 page errors — PASS.
- @100% on all widths: Shift+Tab from initial focus → skip link (visible, outline solid); Enter → `#uw-main`; tab ArrowRight execution→creative, selected; splitter →→ 248→280, End=valuemax, Home=180; pointer resize to 258 then Esc → 180 restored — PASS.
- Screenshots: `screenshots/m4s1_<w>_z<zoom>.png`, `m4s1_<w>_skipfocus.png`, `m4s1_<w>_splitterfocus.png`.

## Known / not done
- Initial page focus lands on the command-search trigger until the patch above is applied (PARTIAL for "skip link first").
- Toolbar wraps rather than collapsing into an overflow menu (spec allows either).
- Native `<select>` menus close on Esc by browser default; no custom menus in DockLayout.
- Zoom simulated as CSS viewport = width/zoom with DPR = zoom (equivalent to Chrome page zoom for layout).
