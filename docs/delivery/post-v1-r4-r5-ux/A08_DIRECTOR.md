# A08 · Camera grammar over existing shots

## Deduplication and authority

EXTEND: `ScreenplayService` and the existing screenplay repository already own scenes, shots, storyboard, transitions, generation tasks, `edit_version`, and history. This package adds no parallel shot database, editor, media generator, or approval authority.

`DirectorService` stores actor-private alternative proposals in the existing isolated `ExperimentalStore`. Its HTTP surface is `/novels/{nid}/experimental/director` on the mounted `/api` and `/api/v1` routers, guarded by exact `ai_director_v2` and existing actor/project/branch permissions. Default OFF and V1 acceptance force OFF are server-side, including direct routes.

## User journey

1. Create/approve a screenplay and plan shots in the original screenplay workspace.
2. In Experimental → 镜头导演, select that existing screenplay version. Set framing, camera angle/motion, integer estimated duration (1–600 seconds), scene purpose, viewpoint, screen direction, and optional spatial evidence.
3. Save one or more named candidate drafts. Original shots stay untouched.
4. Select up to four drafts from the same original version and compare the original fields, candidate fields, and checks.
5. Explicitly acknowledge the effect on downstream work. Apply exactly one compared proposal as a new existing screenplay version with `shot_status=DRAFT`.
6. Return to the original screenplay approval/planning controls. The director does not approve shots or generate any media automatically.

## Spatial claims and limits

Geometry is declared 2D world space, x right/y up, with a named common coordinate system, two existing character IDs at fixed positions, and explicit camera positions. Exact `Fraction` cross products determine same-side/crossing only for adjacent shots in the same scene with the same oriented axis and positions. Missing, different, degenerate, or on-axis geometry yields `INSUFFICIENT_EVIDENCE`. Text does not establish geometry.

Horizontal screen direction is recomputed only with an explicit movement vector and the declared camera looking toward the axis midpoint. This is a bounded geometric convention, not real-image understanding or a general 3D camera solver. A reported crossing is a suggestion. Intentional crossing, long take, and jump cut can carry an explicit reason; no aesthetic rule blocks adoption.

The UI supports authored alternatives and deterministic checks. No model-generated direction or model-quality claim is made. Automatic multi-shot creation, 3D camera/occlusion, moving-axis inference, and real-image spatial validation are not implemented.

## Versions, privacy, recovery

- Every proposal binds the original screenplay CAS version, source chapter versions/digests/current privacy, selected character hashes, scope, and creating actor. No character secrets are copied into the proposal.
- Stale proposals hide derived shot/geometry details. Missing or newly out-of-scope sources hide the whole proposal, without leaking IDs/counts.
- Apply rechecks current authority, current proposal decision/version, source evidence, and screenplay CAS. The existing repository performs version history writes.
- The prior approved version remains in original history. Active downstream storyboard/transition/asset/motion task arrays are removed from active execution. Their bytes and IDs remain only in the existing prior screenplay version, with an internal `STALE_PENDING_REVIEW` version-pointer receipt. Current records do not duplicate archived asset references. Generic public history/conflict projections hide downstream arrays for invalidated shot revisions and show a stale-review marker; the original bytes remain in repository history. Reapproval cannot silently reactivate old callbacks or media.
- A screenplay-side application marker permits receipt-write failure recovery without writing the screenplay twice. This is a checkpoint across existing stores, not a claimed distributed transaction.
- Ordinary existing shot edits preserve director metadata. Legacy public screenplay results/history/conflicts strip internal director markers/archives, hide director metadata when OFF/V1, and check current source/character evidence before returning it when enabled.
- Input is kept on same-scope errors and version conflicts; scope replacement unmounts private state. Duplicate submits, stale comparisons, and late unmounted callbacks are fenced.

## Verification

Implemented service/API/frontend, deterministic rule tests, actual File persistence/history/restart tests, dual-prefix mounted API tests using native authorization, and frontend behavior tests. Real PostgreSQL-parametrized cases are authored; no local server/DSN was available, so local PG is NOT_RUN. Hosted CI must return its own result.

The authored browser journey is `frontend/tests/e2e/r4-director-exchange.spec.ts`; it uses actual API/UI and synthetic content. Local browser execution/screenshots/visual geometry remain NOT_RUN because Chromium launch was already verified blocked by EPERM. No repeated launch or alternative audit route was attempted. Real Windows IME, accessibility assistive technology, GPU/model quality, and user creative acceptance remain NOT_RUN.

Tests: `tests/test_r4_director.py`, `tests/test_r4_director_exchange_mounted.py`, `frontend/src/experimental/DirectorPanel.test.tsx`; original screenplay/shot/CAS/history/branch regression suites remain required. Design tokens and shared UI primitives are reused; no AppShell or design-system changes.
