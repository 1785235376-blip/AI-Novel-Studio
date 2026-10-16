# PHASE14A_DIRECTOR_REPORT — Professional Director System

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline:** `c939b9b` (session-bootstrap report; local = remote at phase start).
**`main` = `fed2404c`, never touched.** **PR #47:** `OPEN` / `isDraft: true`. No merge, no release, no tag.

**Status vocabulary:** `IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.
Nothing reserved, mocked or merely collected is written as complete.

> ## No new Director / Shot / Scene / Project / Asset model was created
>
> The phase's binding constraint was reuse. Reconnaissance showed the owners already held
> almost everything: `DirectorVisualTarget`, `ShotCard`, `ShotContinuity` and the
> `camera_language` vocabulary all exist. What was missing was **structure over them** and
> a **surface**. So the deliverable is a read-only projection plus an additive UI, and a test
> asserts the projection module defines no model and imports no application model.

---

## 1. Reconnaissance that shaped the work

Before writing anything, the owners were audited (the brief forbids a second system):

| Existing owner | What it already carried |
| --- | --- |
| `ShotCard` (`app/creative/models.py:122`) | `id`, `number`, `scene_id`, `duration_seconds`, `shot_size`, `camera_angle`, `camera_motion`, `composition`, `lens`, `lighting`, `environment`, `sound`, `sound_effect`, `dialogue`, `action`, `emotion`, `characters`, `continuity`, `director_note_ids` |
| `DirectorVisualTarget` (`models.py:41`) | `style`, `atmosphere`, `reference_works`, `color`, `rhythm` |
| `DirectorNote` (`models.py:62`) + `DirectorSceneNote` (`:91`) | `shot_size`, `camera_angle`, `camera_motion`, `composition`, `lens`, `lighting`, `color_palette`, `duration_seconds`, `emotion`, `pacing`, `performance`, `blocking`, `character_state`, `performances` |
| `ShotContinuity` (`models.py:111`) | `previous_shot_id`, `next_shot_id`, `characters`, `outfit`, `environment`, `camera` |
| `camera_language.py` (Phase14) | the authoritative vocabulary + `continuity_warnings()` over 3 dimensions |
| `frontend/src/storyboard/` (UX-05) | an existing `DirectorGoalPanel`, `ShotCard`, `ShotList`, `StoryboardWorkspacePanel`, `studio-storyboard` contracts |

**Two consequences the brief did not anticipate, both verified against source:**

1. **All eleven required Shot Card fields already existed** on `ShotCard`. The real gap was that
   the UI exposed only four of them, and that nothing projected them as one contract.
2. **Continuity covered three of the five required dimensions.** Time and lighting had no
   authored home in the continuity block — lighting was already authored on the shot card.

That is what this phase targets: vocabulary, projection and surface **on top of the existing
owners**, changing no existing field's meaning and wiring no enforcement into any legacy path.

---

## 2. What was built

### 2.1 Additive, opt-in owner extensions (no new models)

Two existing owners gained optional fields, using the repository's own established
`OptionalProductionFields` omit-unset mechanism, so **an unset field does not appear in
serialization at all** and no stored document changes shape or digest:

| Owner | Added | Why it is needed |
| --- | --- | --- |
| `DirectorVisualTarget` | `genre` (opt-in; the class now extends `OptionalProductionFields`) | the brief requires **Genre** as a Director Intent dimension, and no owner field carried it |
| `ShotContinuity` | `time`, `lighting` (opt-in) | the brief requires **Time** and **Lighting** continuity; `time` had no shot-level home at all |

Evidence that this is genuinely backward compatible (asserted by tests, not asserted in prose):
`ShotContinuity.model_dump()` for a legacy value is still exactly
`{"characters": …, "outfit": …, "environment": "", "camera": ""}`, and
`DirectorVisualTarget.model_dump()` for a legacy value is still exactly the five original keys.

### 2.2 `app/creative/camera_language.py` — continuity extended to the five required dimensions

`CONTINUITY_FIELDS` is now `characters · outfit · environment · time · lighting`, each with a
declared authored source list in `CONTINUITY_SOURCES`:

* the continuity block (`ShotContinuity`) **or** the shot's own authored field
  (`ShotCard.lighting`, `ShotCard.characters`, `ShotCard.environment`).

This precedence exists so the panel stays a **hint, not a form**: the director is never asked to
retype a lighting or cast decision the shot already carries. Resolving an authored value is not
inferring one — a dimension authored on only one side of a cut remains **unknown**, never a break.
`camera` remains deliberately excluded (moving the camera between shots is direction).
`authored_continuity_values()` is exposed so a panel can report its own coverage honestly.

### 2.3 `app/creative/director_intent.py` — the pure projection (new, no owner)

A deliberately pure module: it takes a stored creative-document row and returns JSON-shaped data.
It imports **no application model**, so the "no second system" rule is a property of the code.
It publishes:

* **Director Intent** — the seven required dimensions, each traced to the owner field it came from,
  and each carrying `kind` + `authored_scope`:
  * `DOCUMENT_AUTHORED` — visual goal (`visual_target.style`, plus `rhythm`/`reference_works` detail),
    mood (`atmosphere`), genre, colour direction (`color`);
  * `PER_SHOT_MEASURED` — camera language, lighting, performance direction. These have **no
    document-level home**, so they are reported as a measurement with `authored: false`,
    `authored_scope: PER_SHOT` and an explicit usage block. A surface therefore cannot present an
    aggregate as a decision the director made.
* **Camera Language binding source** — the owner's `VOCABULARIES` and `ALIASES` are published
  verbatim (alias keys in the same folded form `normalise` matches), so the UI renders its selects
  from the backend and **cannot drift** from the authoritative word list.
* **Shot Card** — all eleven required fields, each with `authored` and its owner source; unset
  fields are `EMPTY` with an empty value, never defaulted into something plausible.
* **Continuity Panel** — the five dimensions, `warning_only: true`, `auto_modify: false`, plus
  per-dimension `compared_pairs` / `unknown_pairs` coverage so **silence is never presented as
  agreement**.

### 2.4 `app/creative/director_workspace.py` + `director_workspace_api.py` — one closed read route

`GET /api/projects/{nid}/studio/director/workspace/{rid}` — GET only, added to the closed
admission allow-list in `workspace_api.py` (so `POST`/`PUT`/`DELETE`, the bare path and any
trailing segment are **not** admitted; asserted by test). It resolves authority through the shared
studio invoker and reads through the existing `CreativeService.get`, so project incarnation, scope
and source fencing stay the owner's job.

**No write route was added.** Authoring a Director Intent continues to use the pre-existing
creative document update endpoint, which already writes `visual_target` and `director_notes`.
Adding `genre` to `DirectorVisualTarget` makes it authorable through that endpoint **without any
API change**.

### 2.5 Frontend — `frontend/src/director/` (new) + one additive mount

| File | Role |
| --- | --- |
| `directorWorkspaceTypes.ts` | presentation types + the frozen required-field lists |
| `directorWorkspaceContract.ts` | strict decoder: rejects unknown keys, bounds strings, refuses control characters, and **fails loudly if the backend's declared required-field tables drift** |
| `directorWorkspaceClient.ts` | read-only client over the existing transport, with a construction-time scope clone |
| `useDirectorWorkspace.ts` | controller: `IDLE/LOADING/READY/EMPTY/DENIED/FAILED`; failures keep their machine code and are never rendered as "no content" |
| `DirectorIntentPanel.tsx` | the seven dimensions, with authored vs measured visibly separated |
| `ShotCardPanel.tsx` | the eleven fields, each tagged `data-field` so the claim is testable |
| `CameraLanguageControl.tsx` | the vocabulary-bound control; legacy text is preserved verbatim and labelled |
| `ContinuityPanel.tsx` | five dimensions, coverage table, warnings — **no write control at all** |
| `DirectorWorkspace.tsx` | composition + surface states |
| `directorWorkspace.css` | DS-v1.0 tokens only; no raw colour, no arbitrary spacing |

**Mount:** `StoryboardWorkspacePanel` gained an on-demand `按需打开导演工作台` entry plus an
**optional** `directorDocumentId` prop. The panel was the right host: it already receives
`projectId`/`transport`/`scope` and is already mounted for `DIRECTOR`/`STORYBOARD` modes.
This avoided touching the frozen one-line `AppShell` composition in `CreativeWorkspace.tsx`, and
the new prop is optional so every existing consumer and test is unaffected.

**Design governance:** `docs/ui/design_system.md` and `docs/ui/protected_ui_surfaces.md` were read
first. No protected surface (GlobalHeader, ModuleSwitcher, ContextBar, AppShell, sidebars,
StatusBar, tokens, core primitives) was touched, so **no DESIGN SYSTEM CHANGE REQUEST was
required**. The repo's own guard `pnpm run lint` (`check_ui_design_tokens.mjs`) passes:
`UI token guard PASS (52 files)`.

---

## 3. Verification actually run

| Check | Command | Result |
| --- | --- | --- |
| Backend, Phase14-A + legacy suites | `run_v2_checks.py phase14a-director-r4` on `test_v2_director_workspace.py`, `test_v2_camera_language.py`, `test_phase8_shots.py`, `test_r4_director.py`, `test_v2_creative_workflows.py` | **159 passed, 70 skipped, exit 0** — receipt `phase14a-director-r4.json` |
| Backend regression on touched owners + route admission | `phase14a-director-regression-r2`: production workflow (+API), model requirements API, creative foundation, creative project lifecycle, screenplay CAS history, storyboard workspace | **127 passed, 109 skipped, 1 deselected, exit 0** |
| Frontend unit suite | `phase14a-director-frontend-r2`: `vitest run src` (363 files) | **3973 passed, 6 skipped, exit 0** |
| TypeScript | `phase14a-director-types-r1`: `tsc --project frontend/tsconfig.json --noEmit` | **PASS** |
| Production build | `phase14a-director-build-r1`: `vite build frontend` | **PASS** |
| Design tokens | `pnpm run lint` | **PASS** (52 files) |
| New backend tests | `tests/test_v2_director_workspace.py` | 60 cases (incl. 3 route integration tests over a real File store + real studio router) |
| New frontend tests | `directorWorkspaceContract.test.ts` (15) + `DirectorWorkspace.test.tsx` (12) | **27 passed** |

The three route integration tests run against the **real** studio router and the **real** File
store with only authority resolution stubbed, so the permission string, scope admission, 404
mapping and the contract itself are exercised end to end. They are gated on the isolated runner
(`PROJECT_ROOT`) and `skip` rather than report a pass they did not earn.

**The tests that matter most** are the ones pinning the phase's own rules:

* the projection module defines no `Shot`/`Scene`/`Project`/`Asset`/`Task`/`ShotCard`/`DirectorNote`
  model and imports no `app` model;
* the decoder refuses a backend whose required-field table has drifted, and refuses a
  `PER_SHOT_MEASURED` dimension that claims `authored_scope: DOCUMENT`;
* the continuity panel refuses `auto_modify: true` and refuses a warning severity other than
  `WARNING`;
* `ShotContinuity`/`DirectorVisualTarget` legacy serialization is byte-shape unchanged, and an
  unknown extra field is still refused.

### 3.1 Intermediate FAIL runs are committed as produced

`phase14a-director-r1..r3`, `phase14a-creativewf-probe` and `phase14a-director-frontend-r1` are
committed exactly as produced. Three of them failed on **my own** mistakes, not the product:

* `r1` omitted `--basetemp`, so the harness's `tmp_path` assertion errored 20 legacy tests;
* `r1`–`r3` failed on my own wrong expectations (an alias key case, an `angle` vs `camera_angle`
  key name, and a route-table assertion that did not match how the minimal app mounts routers);
* `creativewf-probe` was the diagnostic run that identified the `--basetemp` cause;
* `phase14a-director-frontend-r1` used `--root frontend` from the repo root, which changed
  cwd-relative resolution and made an unrelated spec fail.

No product assertion was weakened to reach green, and no test was edited to accommodate a
product defect.

---

## 4. Honest limits — what this phase did **not** do

| Item | Status | Boundary |
| --- | --- | --- |
| Director Intent **write-back from this surface** | `NOT_RUN` (by design) | The workbench is read-only. Camera-language edits are held as a **local session draft** and are visibly labelled as unwritten. Authoring still happens in the original document interface. |
| Genre authoring through the UI | `PARTIAL` | The owner field exists and is writable through the **existing** document update endpoint; this phase added no write control for it. |
| PostgreSQL backend coverage | `NOT_RUN` | This host has **no PostgreSQL cluster** (no service; binaries only inside a packaged build, with no data directory). All evidence above is the File backend. The owner change is schema-additive and backend-agnostic, but that is an argument, not evidence. |
| Browser / visual acceptance | `NOT_RUN` | No Playwright run. Component-level (jsdom) evidence only. |
| Legacy camera-value migration | `NOT_RUN` (deliberate) | Non-canonical text is still preserved verbatim and reported as non-canonical. Migrating it is a product decision that was not taken. |
| Write-path enforcement (`require_canonical`) | `NOT_RUN` (deliberate, unchanged from Phase14) | Still not wired into any legacy path. |
| Professional vs simplified mode split | `NOT_RUN` | No mode split, unchanged. |

### 4.1 Pre-existing conditions observed, not caused, and deliberately not "fixed"

* **`pnpm test` is red before this phase.** The project's vitest config excludes `tests/e2e/**`
  but not the frontend-local `e2e/`, so vitest collects the Playwright spec
  `frontend/e2e/studio-release-acceptance.spec.ts` and reports
  *"Playwright Test did not expect test.describe() to be called here"*. **4007 tests pass; that one
  suite fails.** `frontend/e2e/` and `frontend/vite.config.ts` are **unmodified by this phase**
  (verified with `git status`). It was **not** fixed, because editing the test configuration to make
  a receipt green is exactly the failure mode this project's rules forbid. Phase evidence therefore
  cites the unit suite `vitest run src`, with the pre-existing gap stated here.
* **One symlink test cannot run on this host.** `test_v2_creative_project_lifecycle.py::…[symlink]`
  fails with `OSError [WinError 1314]` — creating a symlink requires a Windows privilege this
  account lacks. It is `BLOCKED_EXTERNAL` (already documented in `docs/v2/README.md` as the known
  Windows symlink-permission condition), it is unrelated to this phase, and it was deselected —
  **not** counted as a pass.
* **Hindsight memory is unavailable** in this session: `hindsight_capture_initiative` returned
  **HTTP 401** (*"API key required"*, no token configured). Memory was therefore neither used nor
  relied on. Phase13 recorded the same limitation.
* **The `$ai-novel-studio-ui` skill is not registered in this session's skill catalog.** It is
  **not missing from the repository**: it exists at `.codex/skills/ai-novel-studio-ui/` with
  `SKILL.md` and four references. It was read **directly from disk** and its required workflow was
  followed. Recorded as a harness wiring gap, not as an absent skill, and nothing was assumed.

---

## 5. Standing rules re-affirmed

* **No second system** — no new Director/Shot/Scene/Project/Asset/Task model; enforced by a test.
* **Old projects stay readable** — opt-in fields are omitted while unset; unrecognised text is
  preserved verbatim and reported as non-canonical; no enforcement was wired into any legacy path.
* **Hint, never correction** — the continuity panel has no write path, `auto_modify` is `false` in
  the contract, and a test refuses a contract that claims otherwise.
* **Measured ≠ authored** — per-shot dimensions are structurally incapable of being reported as
  document-level decisions.
* **Content policy** — `CONTENT_POLICY_FRAMEWORK` remains **`RESERVED`**; no NSFW/Mature mode, no
  adult-model entry point, no content filter.
* **Reserved is not complete** — every row above carries its true status.
* **`main` untouched, PR #47 Draft, no merge/tag/release**, QingJian untouched, other worktrees
  observed only.

---

## 6. Files in this phase

**Modified (4)**
`app/creative/camera_language.py` · `app/creative/models.py` · `app/creative/workspace_api.py` ·
`frontend/src/storyboard/StoryboardWorkspacePanel.tsx`

**Added — backend (3)**
`app/creative/director_intent.py` · `app/creative/director_workspace.py` ·
`app/creative/director_workspace_api.py`

**Added — backend tests (1)**
`tests/test_v2_director_workspace.py`

**Added — frontend (13, all under `frontend/src/director/`)**
`directorWorkspaceTypes.ts` · `directorWorkspaceContract.ts` · `directorWorkspaceClient.ts` ·
`useDirectorWorkspace.ts` · `DirectorIntentPanel.tsx` · `ShotCardPanel.tsx` ·
`CameraLanguageControl.tsx` · `ContinuityPanel.tsx` · `DirectorWorkspace.tsx` ·
`directorWorkspace.css` · `directorWorkspaceFixtures.testFixture.ts` ·
`directorWorkspaceContract.test.ts` · `DirectorWorkspace.test.tsx`

**Evidence**
`docs/delivery/v2-development/phase14a-director-{r1…r4,regression-r1,r2,frontend-r1,r2,types-r1,
build-r1}.json` + `.log`, `phase14a-creativewf-probe.{json,log}`

---

## 7. Recommendation for the next phase

**Phase14-B (Character & Scene Bible)** is the next open priority, and the seam is already
identified: `ShotCard.characters` / `ShotCard.environment` / `DirectorNote.character_state` /
`performances` exist, so the work is an authored profile owner extension plus a read-only
consistency surface — the same shape as this phase, and it can reuse
`projects/studio/director/workspace` patterns directly.

Before that, three things this phase could not close should be weighed:

1. **PostgreSQL evidence** for the additive owner fields. Without a cluster on this host that row
   stays `NOT_RUN`; initializing one from the packaged binaries would move it.
2. **Browser/visual acceptance** of the new surface (Playwright), which is the honest remaining gap
   for any UI-only claim.
3. **The pre-existing `pnpm test` / `frontend/e2e` collection gap** — a one-line config decision for
   the Root/Design System Owner, deliberately left to them rather than taken unilaterally here.

RC conclusion is unchanged from Phase13 and Phase14: **`NOT ESTABLISHED`**. This phase added
capability; it did not move a release gate.
