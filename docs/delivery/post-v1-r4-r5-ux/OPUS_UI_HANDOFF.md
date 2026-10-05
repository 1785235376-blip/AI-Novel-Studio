# Opus functional handoff — R4/R5/UX experimental continuation

Target: Draft PR39, `work/post-v1-r4-r5-ux`, stacked on frozen R3 `d712ab81e9d87bfd5902d0a6bbd47c4edaccac5b`. This supplements the original root-level handoff; it does not alter the frozen PR37 acceptance package.

Read AGENTS.md, the repository UI skill and DS-v1.0. Keep one AppShell, original TipTap editor, shared tokens/primitives and captured collaboration context. This handoff is for later visual polish; it is not authority to redesign the shell or weaken business behavior.

## Current real entry points

- App editor: visible draft/save/recovery states, explicit archived conflict resolution, composition-safe updates, focus/reference rail, exact selection and paragraph AI locks.
- Existing experimental workbench: resume/search/tasks/diagnostics, workflow inspection, graph/character viewpoint, model route/benchmark, asset lineage/replay, style/judge, selective change refresh, bounded simulator, research library and partial revision panels.
- Original writing inspector: shared actual request preview and final dispatch authority, explicit character viewpoint, style choice and trusted partial-only generation binding.
- Existing history and Draft/Diff/Accept remain the final action surfaces. The new revision panel uses the same document CAS path; it cannot silently accept an entire generation.

Each panel has current loading, empty, missing-dependency, error and review states. Preserve source versions, actor/scope-bound clients, abort/late-response fences, expected-version tokens and pending/accepted distinctions. Do not replace disabled explanations with empty buttons.

## Layout and accessibility constraints

The feature-OFF editor wrapper uses `display: contents`; focus split alone creates a grid. This prevents an invisible editor row from intercepting legacy panel actions. Preserve keyboard names, focus return, status live regions, IME composition buffers and manual-merge cache monotonicity. Reference content remains read-only.

New functional panels are intentionally dense and may need spacing, grouping and navigation polish within the design system. The number of experimental tabs is a known discoverability cost; later grouping should retain searchable, testable feature access rather than add top-level menus.

## Evidence and outstanding checks

WAVE_2_3_CHECKPOINT.md records exact local source and tests. Hosted browser checks run `playwright.r4.config.ts` with synthetic isolated projects and exact flags; actual model quality and native desktop interaction are separate. U13's backend performance receipt is scoped to its recorded older source/method and is not a browser latency claim. Raw browser measurements are now explicitly written into compact CI artifacts.

The blocked second-slice independent review is documented in SECOND_SLICE_REVIEW_STATUS.md. Functional tests do not imply audit closure or user acceptance. No new visual goldens were accepted merely to make tests pass.
