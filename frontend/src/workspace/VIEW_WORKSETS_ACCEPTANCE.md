# [HERMIA-FE-20261024 VW-M5] View prefs / worksets / viewport / panel focus — acceptance ledger

Status words: PASS / FAIL / PARTIAL / BLOCKED / NOT_RUN. Columns: IMPLEMENTED · protocol test (jsdom/unit) · real host wiring · browser · owner block.
Environment: Node 22.14 (repo engines satisfied); independent verify used Node 24.19 — not equivalent. No browser run this round.

| Item | Impl | Protocol test | Real host wiring | Browser | Owner block |
|---|---|---|---|---|---|
| M1 adapter: scoped key, whitelist fields, placeholder/no-scope ⇒ session, corrupt/future kept, read/write failure, lease | YES | PASS (viewPreferences.vw.test.ts, 8) | PARTIAL: preview wired session-only (scope=null) | NOT_RUN | Host/session owner: real user/project/instance scope + persist policy |
| M1 zero writes without legal scope | YES | PASS (adapter + host test: no `viewprefs` key) | PASS in preview | NOT_RUN | — |
| M2 named worksets save/apply/rename/delete via ActionRegistry; name/limit/size checks | YES | PASS (vw.m2m4.test.tsx) | YES (toolbar 视图, Ctrl/⌘+Alt+V, command search) | NOT_RUN | — |
| M2 apply blocked when it would close a dirty panel (no change, draft kept) | YES | PASS (DockLayout api test) | YES | NOT_RUN | — |
| M2 persistent worksets | NO (session only, labelled "仅本次会话") | PASS (wording) | BLOCKED | NOT_RUN | Host/session owner |
| M2 dirty chapter + node title across switch/redock/fail (full matrix) | PARTIAL | PARTIAL (generic dirty editor only) | — | NOT_RUN | — |
| M3 viewport via adapter, per novel × canvas, late callback rejected by lease | YES | PASS (adapter) / PASS host remount keeps pan | YES (session) | NOT_RUN | — |
| M3 explicit per-canvas reset (only that pref) | YES | PASS (host test) | YES | NOT_RUN | — |
| M3 product cold reopen (same scope after reload) | protocol only | PASS (adapter cold re-create) | BLOCKED (no real scope in preview) | NOT_RUN | Host/session owner |
| M4 next/prev/return-to-last panel commands, conflict-checked shortcuts (Ctrl/⌘+Alt+N/B/L) | YES | PASS | YES | NOT_RUN | — |
| M4 no focus steal on mount / prefs load | YES | PASS (host test) | YES | NOT_RUN | — |
| M4 stable inner-control identity restore | NO (returns to panel region) | — | — | NOT_RUN | — |
| M4 reduced-motion / full a11y audit of new dialog | PARTIAL (labels, Escape, focus return) | PARTIAL | — | NOT_RUN | — |
| M5 TasksPanel token | unchanged: unavailable | — | — | — | Auth/task owner |
| Existing DockLayout v3 layout still writes under placeholder `local/preview/preview` | pre-existing, unchanged | — | — | — | Host/session owner (open item) |
