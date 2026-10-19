# Explicit multi-shot video graph starter

Integrated product: 2a9082b3344bf9f830fd0294609b94d9688c39c4. Source prerequisite: f1b33b3122109e7bc25c64dab45701b93750c8b1.
2026-10-19 03:29 UTC. Partial Graph/Director authoring progress, not release acceptance.

## User-visible change

Users explicitly choose 1–4 shots from one verified approved Storyboard, see ordered exact shot pins and the proposed branch count, then apply once to an empty v5 graph. A shared Storyboard node feeds a shot→video candidate→private review branch per selection. Four shots use 13 nodes and 12 edges, within existing limits. More than four is rejected; larger source Storyboards require a user-chosen subset, never silent truncation.

Original single-shot entry remains compatible. Original controller change/history supplies one undo/redo. Provider/model remain blank, LOCAL_ONLY remains default, and configuration, Save, execution and review are still explicit. No provider call, automatic save, approval, second engine or runtime capacity increase. Parallel branches describe graph structure, not verified simultaneous GPU execution.

Source/selection/authority lifetimes, retained callbacks, DOM selection drift, duplicate/unknown IDs, node/edge collisions and double application are guarded. Original source documents and source approvals are not changed.

## Evidence

- Worker and independent reviewer: 27 focused frontend tests, including 9 unchanged single-shot cases; type/token checks passed.
- Root integrated frontend: 102 tests / 7 suites, TypeScript build, Vite production build and token guard PASS.
- Worker original-owner File checks: 19 passed, 9 PG deselected.
- Root real PostgreSQL: 2 targeted original-owner cases passed, 2 File cases deselected. Configured four-branch graph saved/reopened unchanged; fifth generator rejected by unchanged owner capacity. No media dispatch. Exact 14-table before/after hashes match; server stopped.
- Backend tests construct the equivalent graph in Python. They are separate from TS builder tests and do not prove a TS→backend end-to-end handoff.
- Both root source receipts match all 3212 recorded paths. Original PUBLIC6/wheel evidence reused because all 542 app paths and packaging inputs remain unchanged; frontend build is new.
- Existing large-chunk build warning remains. Browser attempt was blocked before rendering by missing Chromium; no install/fallback or visual acceptance claim.

## Recovery and limitations

Development resumed normally in the same existing task following the user's continuation request. The earlier explicit preview-limit interruption remains historical evidence, not a claim of uninterrupted work or a general quota reset. No paid model/service switch.

Clean tracked documentation was removed from completed/active sparse worktree materialization to free storage; Git objects, uncommitted source and raw evidence were preserved. No unique source was deleted.

Initial test-fixture and sparse-input failures are retained in the worker report/evidence. No assertions were weakened. No live video generation, browser geometry, Windows/GPU or full intelligent Director/V2 completion is claimed. Public private-content exclusion and Prompt Adoption closure remain unchanged. Only the existing authorized archive branch is a publication destination.
