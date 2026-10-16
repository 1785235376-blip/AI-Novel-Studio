# ROUND2B_HANDOFF — Character & Scene Bible → Prompt Studio

**Purpose:** the exact, verified interface the Character/Scene Bible exposes, so **Round 3 (Prompt
Intelligence System)** can bind prompt assets to characters and scenes without re-deriving anything
or duplicating data.

**Baseline:** `feature/v2-narrative-platform`. The bible backend landed in Round 2; the frontend
surface in Round 2-B. **This document describes code that exists and is test-covered** — every field
name below was read off a real projection response, not from a design sketch.

---

## 1. Bible 数据结构 (data structure)

### 1.1 Where the data actually lives (one owner per fact — do not copy)

| Fact | Authoritative owner | Written by |
| --- | --- | --- |
| character identity (`name`, `age`, `role`, `status`) | the project's `characters` records | pre-existing `upsert_character` |
| location identity (`name`) | the project's `locations` records | pre-existing `upsert_location` |
| character behaviour (state, motivation, arc) | `WorldService` record kind `PSYCHOLOGY` | `WorldService` record route |
| character relationships | `WorldService` record kind `RELATIONSHIP` | `WorldService` record route |
| location geographic relations | `WorldService` record kind `GEOGRAPHY` | `WorldService` record route |
| **character visual** (appearance, clothing, distinguishing, references) | `WorldService` record kind **`CHARACTER_VISUAL`** | `WorldService` record route |
| **scene visual** (architecture, material, lighting, weather, mood, time-of-day, references) | `WorldService` record kind **`SCENE_VISUAL`** | `WorldService` record route |
| asset bytes | the existing asset library | existing asset routes |
| where a character/scene is used | the existing creative documents (scenes/shots) | existing creative document route |

The bible is a **projection** over these. There is no bible table, no bible row, and nothing to keep
in sync. Round 3 must bind to the **ids** (`character_id`, `location_id`) and read content through
this projection — not copy text into a prompt record.

### 1.2 The two new authored record kinds (the only new storage)

```python
# app/experimental/world.py — registered in DATA_MODELS and WorldRecordIn.kind
class CharacterVisualData(StrictModel):
    character_id: str            # must already exist as a character record
    appearance: str = ""
    clothing: str = ""
    distinguishing: str = ""
    reference_asset_ids: list[str] = []

class SceneVisualData(StrictModel):
    location_id: str             # must already exist as a location record
    architecture: str = ""
    material: str = ""
    lighting: str = ""
    weather: str = ""
    mood: str = ""
    time_of_day: str = ""
    reference_asset_ids: list[str] = []
```

Notes that matter for Round 3:

* They inherit `WorldService`'s existing versioning, CAS, review/approval, history and source
  fencing. **A value is only `authoritative` when the record's `status == 'APPROVED'`.**
* They deliberately do **not** require a `chapter_id` (a visual profile is project-level).
* The owner **validates the reference**: a `CHARACTER_VISUAL` naming a non-existent character, or a
  `SCENE_VISUAL` naming a non-existent location, is refused. Ids are never invented.
* `character_id` is preserved verbatim; **`location_id` is lower-cased by the location owner**
  (`upsert_location(nid,"L1",…)` stores `l1`). Round 3 must use the **stored** form as returned by
  the projection.

---

## 2. API 契约 (the exact contract)

### 2.1 Endpoint

```
GET /api/projects/{nid}/studio/bible
Headers: x-session-token, x-branch-id   (same studio invoker as every other Studio route)
```

* Permission: `domain.read`. GET only — the admission allow-list does not admit POST/PUT/DELETE or
  any trailing segment (asserted by test).
* **There is no write route.** Authoring goes through the existing `WorldService` record route.
* Errors: `403` authority; `404` unknown/archived project (`EXPERIMENTAL_NOT_FOUND`);
  `409` stale source; `422` invalid.

### 2.2 Response envelope (top level — 17 keys, all required)

```
contract                  "studio-bible/1"        (exact)
schema_version            1                        (exact)
advisory_only             true                     (exact)
execution_authority       false                    (exact)
auto_modify               false                    (exact)
unknown_is_explicit       true                     (exact)
required_character_fields ["identity","appearance","clothing","reference","behavior","relationship"]
required_scene_fields     ["location","architecture","material","lighting","weather","time","mood"]
character_bible           { … }                    (see 2.3)
scene_bible               { … }                    (see 2.4)
gaps                      { characters: [...], scenes: [...] }
project_id                string
scope                     { mode, novel_id, … }
generated_at              ISO-8601 string
project_context           { title, genre, inherited_not_authored: true }
visual_owner              string
world_owner_available     boolean
```

Both `required_*_fields` arrays are compared **exactly, in order**, by the frontend decoder — a
backend reorder or rename is a hard failure, not a silent UI change. **Round 3 must treat these two
lists as the frozen vocabulary.**

### 2.3 `character_bible`

```
contract        "studio-character-bible/1"
schema_version  1
required_fields [same six, same order]
character_count == entries.length
entries[]:
  character_id            string
  name                    string
  dimensions[]            exactly six, in the required order
  used_in[]               { document_id, mode, role, scene_id?, shot_id? }
  visual_record_status    "APPROVED" | "DRAFT" | … | null
  visual_authoritative    boolean
```

### 2.4 `scene_bible`

```
contract        "studio-scene-bible/1"
schema_version  1
required_fields [same seven, same order]
location_count  == entries.length
entries[]:
  location_id             string          (the owner's stored, lower-cased form)
  name                    string
  dimensions[]            exactly seven, in the required order
  reference_asset_ids[]   string[]        (declared; top-level convenience mirror)
  used_in[]               as above
  visual_record_status    "APPROVED" | "DRAFT" | … | null
  visual_authoritative    boolean
```

### 2.5 A `dimension` — the unit Round 3 will bind to

Base keys, **always present**:

```
field    string    one of the frozen vocabulary
label    string    Chinese display label
source   string    the exact owner path, e.g. "world_records.CHARACTER_VISUAL.appearance"
value    string    the authored value, or the literal "UNKNOWN"
authored boolean
state    "AUTHORED" | "UNKNOWN"
```

Per-field **extra** keys (frozen; the decoder rejects anything else):

| `field` | extra keys |
| --- | --- |
| `appearance`, `clothing`, `architecture`, `material`, `lighting`, `weather`, `time`, `mood` | `authoritative: boolean`, `record_status: string \| null` |
| `reference` | `references: [{asset_id, resolution: "RESOLVED"\|"UNRESOLVED"}]`, `unresolved_references: string[]`, `verification: "INDEX_SUPPLIED"\|"NO_INDEX_SUPPLIED"` |
| `relationship` | `relationships: [{target_character_id, state, authoritative}]` |
| `location` | `geography_records: number` |
| `identity`, `behavior` | *(none)* |

### 2.6 Invariants Round 3 may rely on (enforced on both sides, test-covered)

1. `state === "UNKNOWN"` ⟺ `value === "UNKNOWN"` ⟺ `authored === false`.
   **An unauthored dimension is never a blank string** — so a prompt builder can distinguish
   "not authored" from "authored as empty" and must not emit a prompt clause from an `UNKNOWN`.
2. `record_status === "APPROVED"` and `authoritative === true` are the **only** signal that a visual
   value is canon. A `DRAFT` value is present and displayable but **must not** be promoted into a
   prompt template as settled setting.
3. `unresolved_references` equals exactly the `UNRESOLVED` entries of `references`; with
   `NO_INDEX_SUPPLIED` no reference can be `RESOLVED`.
4. `gaps` enumerates exactly the unauthored `(character_id | location_id, field)` pairs — the
   cheapest "what is missing before I can build a prompt?" query.
5. `used_in[].role ∈ {SCENE_CAST, SHOT_CAST, SHOT_CONTINUITY, SCENE_LOCATION}` and is built only
   from authored references on real documents — never by name matching.

---

## 3. 前端消费方式 (how the frontend consumes it)

**Files (all under `frontend/src/bible/`)** — copy this pattern for the Prompt Studio; do not invent a
new one:

| File | Role |
| --- | --- |
| `bibleTypes.ts` | presentation types + the frozen field lists + `canonState()` |
| `bibleContract.ts` | `bibleProjection(value, expectedProjectId)` — the **only** entry point; throws `ApiError` with `STUDIO_RESPONSE_INVALID` / `STUDIO_BIBLE_SCOPE_MISMATCH` |
| `bibleClient.ts` | `createBibleClient(projectId, transport, scope)` → `{ readBible(signal) }`; clones scope at construction and refuses a foreign project **before** sending |
| `useBible.ts` | controller: `IDLE/LOADING/READY/EMPTY/DENIED/FAILED`; failures keep their machine code and are never rendered as "no content" |
| `BibleDimensionRow.tsx` | the per-dimension renderer: literal `UNKNOWN` + 未作者化, `CANON · APPROVED` vs `DRAFT（非 canon）`, per-reference `RESOLVED`/`UNRESOLVED` |
| `CharacterBiblePanel.tsx` / `SceneBiblePanel.tsx` | one card per entry; each dimension tagged `data-field` / `data-state` / `data-canon` |
| `BibleWorkspace.tsx` | composition + surface states; **no write control at all** |

**Mount pattern:** `StoryboardWorkspacePanel` already receives `projectId` / `transport` / `scope`, so
the bible is mounted there with an additive on-demand button — no new props, no protected-surface
change:

```tsx
const bibleClient = useMemo(
  () => createBibleClient(props.projectId, props.transport, props.scope),
  [props.projectId, props.transport, props.scope]);
…
{bibleOpen && <BibleWorkspace client={bibleClient} active={props.active} />}
```

**Rules any new Studio surface must follow** (established across Rounds 1, 2, 2-B):

* strict decoder that rejects unknown keys and refuses contract drift;
* a real `ApiError` with a stable machine code on failure — never an empty state;
* `UNKNOWN` / `DRAFT` / `UNRESOLVED` rendered as **visible states**, never blanks;
* DS-v1.0 tokens only — and **self-verify your own CSS**, because `check_ui_design_tokens.mjs` only
  scans `frontend/src/ui` (see the Round 2-B report §2.1);
* no write control in a read-only surface; authoring stays on the owner route.

---

## 4. Prompt Studio 需要绑定的数据 (what Round 3 must bind to)

For each prompt asset, the binding targets that already exist — **bind by id, read by projection**:

| Prompt Studio need | Bind to | How to read it |
| --- | --- | --- |
| which character(s) a prompt is for | `character_id` | `character_bible.entries[].character_id`; existence is validated by `CHARACTER_VISUAL` references |
| which scene/location a prompt is for | `location_id` | `scene_bible.entries[].location_id` (**stored lower-cased form**) |
| which shot a prompt is for | shot `id` | `used_in[].shot_id` and the existing creative document |
| reference material for an image prompt | `reference_asset_ids` → `asset_id` | the existing asset library; resolution status from the `reference` dimension |
| consistency clauses (appearance/clothing) | `appearance`, `clothing`, `distinguishing` | `CHARACTER_VISUAL`, **only when `authoritative`** |
| consistency clauses (environment) | `architecture`, `material`, `lighting`, `weather`, `mood`, `time_of_day` | `SCENE_VISUAL`, **only when `authoritative`** |
| behavioural/performance context | `PSYCHOLOGY.state` / `motivation`, `RELATIONSHIP.state` | the `behavior` / `relationship` dimensions |
| "what is still missing" before generating | `gaps` | `gaps.characters[]` / `gaps.scenes[]` |

**Hard constraints for Round 3:**

1. **Do not copy bible text into a prompt record as the source of truth.** Store the ids and, if a
   snapshot is needed, the id + version + digest — the pattern the repo already uses for
   `source_documents` / `source_versions` / `shot_digest`.
2. **Never build a prompt clause from an `UNKNOWN` dimension.** Skip it, or surface it as a
   "尚未 authoring" gap — an inventive prompt would silently fabricate setting.
3. **Never build from a `DRAFT` record as though it were canon.** Use only `authoritative: true`,
   or carry the draft explicitly as a non-canon suggestion.
4. **Never resolve a character or scene by name similarity.** Only ids returned by the projection.
5. **No second prompt/asset/version store.** Prompts must extend the existing asset/version owner,
   the same way `CHARACTER_VISUAL` extended `WorldService`.

---

## 5. Ready-to-use facts for Round 3

* Frozen vocabularies: `CHARACTER_BIBLE_FIELDS` (6) and `SCENE_BIBLE_FIELDS` (7), exported from both
  `app/creative/bible_projection.py` and `frontend/src/bible/bibleTypes.ts`, and asserted equal in
  order by the decoder.
* New record kinds: `CHARACTER_VISUAL`, `SCENE_VISUAL` — registered, validated, review-gated.
* Endpoint: `GET /api/projects/{nid}/studio/bible` (read-only; `domain.read`).
* Frontend client: `createBibleClient(projectId, transport, scope)`; controller `useBible(client)`.
* Cheapest gap query: `gaps.characters` / `gaps.scenes`.

**Open items that would help Round 3 and are deliberately not done yet:** a structured identity
`detail` (`name`/`age`/`role`/`status` as separate keys) so a template can reference them without
parsing a joined string; and asset thumbnails via the existing asset download route.
