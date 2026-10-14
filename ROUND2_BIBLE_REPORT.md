# ROUND2_BIBLE_REPORT — Character & Scene Bible

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline:** `e951dbe` (session bootstrap; local = remote at round start).
**`main` = `fed2404c`, never touched.** **PR #47:** `OPEN` / `isDraft: true`. No merge, no release, no tag.

**Status vocabulary:** `IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.

> ## Scope of this increment
>
> The **backend half of Round 2 is `IMPLEMENTED` and verified on both backends.** The
> **frontend Bible surface is `NOT_RUN`** — it is the next increment, and it is *not* claimed here.
> Nothing below describes an interface as a finished experience.

---

## 1. Reconnaissance that shaped the work

Round 2 asks for a Character Bible (identity, appearance, clothing, reference, behaviour,
relationship) and a Scene Bible (location, architecture, material, lighting, weather, time, mood).
Before writing anything, every one of those dimensions was traced to an owner — and **most already
had one**:

| Bible dimension | Existing owner found | Had it? |
| --- | --- | --- |
| character identity | the project's `characters` records (`name`/`age`/`role`/`status`), written by the pre-existing `upsert_character` | **yes** |
| character behaviour | `WorldService` `PSYCHOLOGY` records (`state`, `motivation`, arc) | **yes** |
| character relationship | `WorldService` `RELATIONSHIP` records (directed pair, state) | **yes** |
| character appearance / clothing / reference | — | **no** |
| scene location | the project's `locations` records + `WorldService` `GEOGRAPHY` | **yes** |
| story time | `WorldService` `HISTORY` records (`time`, `end_time`, `calendar`) | **yes** (story events, not scene look) |
| scene architecture / material / lighting / weather / mood | — | **no** |

So the genuine gap was exactly one thing: the **authored visual half** — how a character *looks* and
what a location *looks like*. Everything else is a **join**, and `V1_SCOPE_FREEZE.md` contains no
mention of characters, locations, lore or world, so none of this is frozen V1 surface.

**Decision: extend the existing `WorldService` typed-record system with two new kinds instead of
creating any new owner.** That owner already carries versioning, CAS, review/approval, history,
source fencing and typed `data` validation for its eight existing kinds; the visual profile inherits
all of it. The alternative — bolting visual fields onto the V1 novel repository — would have touched
`CharacterModel`, the File and PostgreSQL novel repositories and the migration path, and would have
had no versioning or review.

---

## 2. What was built

### 2.1 Two new typed kinds on the existing `WorldService` (no new owner)

`app/experimental/world.py`:

* `CharacterVisualData` — `character_id`, `appearance`, `clothing`, `distinguishing`,
  `reference_asset_ids`
* `SceneVisualData` — `location_id`, `architecture`, `material`, `lighting`, `weather`, `mood`,
  `time_of_day`, `reference_asset_ids`

Both are registered in `DATA_MODELS` and in the `WorldRecordIn.kind` literal, so they are validated,
versioned, reviewable and reference-checked by the owner's existing machinery. They deliberately do
**not** require a `chapter_id`: a visual profile is project-level, not chapter-level.

The reference dispatch (`WorldService._references`) gained explicit `CHARACTER_VISUAL` /
`SCENE_VISUAL` branches, the previously-implicit `CHARACTER_EVENT` fallback was made explicit, and
the final `else` now **raises** (`unhandled world record kind`) instead of silently treating a new
kind as whichever one happened to be last. That is a fail-closed improvement, and a test pins it.

### 2.2 `app/creative/bible_projection.py` — the pure projection (new, no owner)

Takes plain mappings and returns JSON-shaped data; imports no application model, and a test asserts
it defines no `Character`/`Scene`/`Location`/`Project`/`Asset`/`Task` model and exposes no
`create/update/write/save/commit/delete`. It **joins** the character/location records, the
`WorldService` records, the asset index and the creative documents into:

* a **Character Bible** with the six required dimensions;
* a **Scene Bible** with the seven required dimensions;
* `gaps` — the literal list of dimensions still unauthored, so "what is missing?" is answered
  without inference;
* `used_in` per entry — where the character/scene actually appears, built **only** from authored
  references on real scenes and shots (`SCENE_CAST`, `SHOT_CAST`, `SHOT_CONTINUITY`,
  `SCENE_LOCATION`). A test asserts it never links by name similarity.

Three honesty rules are structural, not commentary:

| Rule | How it is enforced |
| --- | --- |
| **Unknown is a value** | an unauthored dimension is the literal `UNKNOWN` with `authored: false` — never an empty string that could read as "nothing to say" |
| **Draft is not canon** | the owner's own `status` is carried through; only `APPROVED` is `authoritative`, a `DRAFT` is reported as a draft (and an approved record wins over a draft for the same subject) |
| **Declared is not verified** | an asset reference is `RESOLVED` only against an index the caller actually supplied; with no index every id is `UNRESOLVED` with `verification: NO_INDEX_SUPPLIED` |

### 2.3 One closed read route

`GET /api/projects/{nid}/studio/bible` via `BibleWorkspaceService` +
`create_bible_router`, added to the closed admission allow-list in `workspace_api.py` (POST/PUT/
DELETE and any trailing segment are **not** admitted; asserted by test). `BibleWorkspaceService`
reads the project's records through the existing owners, filters by branch, and passes the **real**
workspace asset index so references are genuinely resolved rather than assumed. It writes nothing;
authoring a visual profile still goes through the existing `WorldService` record route with its own
review and CAS contract. The service is wired in `app/experimental/api.py` by passing the **existing**
`world_service` instance — not a second one.

---

## 3. Verification actually run

| Check | Command | Result |
| --- | --- | --- |
| Backend, Round 2 + reused-owner + Round 1 regression | `round2-bible-r3` on `test_round2_bible.py`, `test_r3_world.py`, `test_world_rule_payload.py`, `test_r4_story_graph.py`, `test_phase4_world_summary.py`, `test_v2_director_workspace.py`, `test_v2_camera_language.py` | **173 passed, 27 skipped, exit 0** |
| **Real PostgreSQL** | `round2-bible-postgres` (fresh `v2_round2`, 20 migrations, loopback-only disposable cluster, stopped cleanly) | **80 passed, 9 skipped, exit 0** |
| New test suite | `tests/test_round2_bible.py` | 34 cases (incl. 3 route integration tests over a real File store + real studio router) |
| Wiring | `import app.main` | **OK** |
| Route admission | `is_independent_studio_route` | `GET /studio/bible` → `True`; `POST`, `PUT`, `DELETE`, `…/bible/extra` → `False` |

The tests that matter most pin the round's own rules: unknown-is-explicit, draft-is-not-canon,
declared-is-not-verified, usage-never-guessed, no-second-system, no-write-path, and the fail-closed
reference dispatch.

### 3.1 Intermediate FAIL runs are committed as produced

`round2-bible-r1`, `round2-bible-r2` and `round2-bible-probe` are committed exactly as produced.
`r1` and `r2` failed on **my own** rig mistake, not the product, and the failure is informative:

* I referenced location `L1` in a `SCENE_VISUAL` record without creating that location. The owner
  **correctly refused it** (`unknown locations reference: L1`) — which is the reference validation
  working exactly as designed.

Investigating it produced a real, previously-unrecorded fact about an existing owner:

> **The project's location owner lower-cases the location id** (`upsert_location(nid, "L1", …)`
> stores id `l1`), while a **character id is preserved verbatim** (`c1` stays `c1`). The bible
> projection reads whatever the owner stores, so `location_id` values in the Scene Bible are the
> owner's stored form. This was verified directly and is now asserted in the rig.

No product assertion was weakened to reach green.

---

## 4. Honest limits

| Item | Status | Boundary |
| --- | --- | --- |
| **Frontend Bible surface** | **`NOT_RUN`** | No Character/Scene Bible UI exists yet. This is the next increment; the projection and route it will consume are done and verified. |
| Authoring a visual profile from a Studio surface | `NOT_RUN` | The owner route accepts the two new kinds today with review and CAS; no Studio authoring UI was added. |
| Reference resolution | `IMPLEMENTED` | Resolved against the real workspace asset index; an id not in the index is `UNRESOLVED`, never assumed. |
| Genre/id naming asymmetry | `RECORDED` (existing owner behaviour) | Location ids are lower-cased by the owner, character ids are not. Not changed — it is existing behaviour outside this round's scope, and changing it would be a migration. |
| Image / Video consumption of the bible | `NOT_RUN` | Round 2 asks for the bible to be *used by* Image/Video/Storyboard. The projection reports `used_in` from real documents, but no generation path consumes the bible yet — that is Round 3 (Prompt Intelligence) territory. |
| Browser / visual acceptance | `NOT_RUN` | No Playwright run; and with no new UI in this increment there is nothing new to accept visually. |
| PostgreSQL | **`IMPLEMENTED`** | 80 passed, exit 0 on a fresh database. |

**Pre-existing conditions observed and deliberately not "fixed":** the `pnpm test` / `frontend/e2e`
collection gap (unchanged, still the Root/Design System Owner's call), the Windows symlink
`WinError 1314` test (deselected, not counted as a pass), and Hindsight being unavailable (HTTP 401,
no API key).

---

## 5. Standing rules re-affirmed

* **No duplicate system** — no new character, location, asset, project or task owner; the visual
  profile extends the existing `WorldService` typed-record system, and the rest is a join.
* **AI assists, does not replace** — this is a read-only projection of *authored* data. Nothing is
  inferred from prose, nothing is auto-filled, and the round added no AI behaviour at all.
* **Truth first** — the frontend half is `NOT_RUN` and is labelled as such; no interface is written
  up as a finished experience.
* **`main` untouched · PR #47 Draft · no merge/tag/release** · QingJian untouched · the 39 protected
  untracked files untouched.

---

## 6. Files in this round

**Modified (3)**
`app/experimental/world.py` · `app/creative/workspace_api.py` · `app/experimental/api.py`

**Added — backend (3)**
`app/creative/bible_projection.py` · `app/creative/bible_workspace.py` · `app/creative/bible_api.py`

**Added — tests (1)**
`tests/test_round2_bible.py`

**Evidence**
`docs/delivery/v2-development/round2-bible-{r1,r2,r3,probe}.json` + `.log`,
`round2-bible-postgres.json`, `round2-bible-postgres-postgres-runtime.json`

---

## 7. Next increment

**Round 2 continued — the Character/Scene Bible frontend surface**, consuming
`GET /api/projects/{nid}/studio/bible`. It should follow the Phase14-A surface pattern that is
already established and design-system compliant: a strict decoder that fails on contract drift, a
read-only panel that renders `UNKNOWN` as an explicit "not authored" state (never as blank), shows
which owner each dimension came from, distinguishes a draft from canon, marks unresolved references,
and offers **no** write path — authoring stays on the existing `WorldService` route.

After that, **Round 3 (Prompt Intelligence System)** becomes the next open priority; the bible is
precisely the reference material that round needs to bind prompts to characters and scenes.
