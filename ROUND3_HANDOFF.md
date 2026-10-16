# ROUND3_HANDOFF — Prompt Intelligence → Asset Intelligence Graph

**Purpose:** the exact, verified interface Round 3 exposes, so **Round 4 (Asset Intelligence Graph)**
can build the Character → Image → Shot → Video → Timeline chain without re-deriving anything, and so
the unfinished **Round3-C Prompt Workspace UI** can be built from a frozen contract.

**Baseline:** `feature/v2-narrative-platform` (`558acea` + Round 3).
Everything below was read off running code and is test-covered.

---

## 1. Prompt 数据结构 (data structure)

### 1.1 There is no prompt table — a prompt is an existing asset

| Prompt concept | Where it physically lives | Owner |
| --- | --- | --- |
| identity | the asset id | `AssetLibraryService` |
| prompt text | the asset's **bytes** (`kind="prompt"`, `media_type="text/plain"`) | `AssetLibraryService` |
| negative prompt, model reference, parameters, seed, purpose, origin, change note, change reason, family id, revision | `parameters.prompt` (a dict inside the asset's allow-listed `parameters`) | `AssetLibraryService.update_metadata` |
| character / scene binding | the asset's `character_id` / `scene_id` metadata fields (lists are held in the payload) | `AssetLibraryService.update_metadata` |
| reference / output assets | `source_asset_ids` (references, never copies) | `AssetLibraryService.update_metadata` / `annotate_lineage` |
| version | asset `version` + `expected_version` CAS | `AssetLibraryService` |
| version chain | `parameters.asset_lineage_v2` history, written by `annotate_lineage` | `AssetLibraryService` |
| review | `approved_at` / `_owner_actor_id` via `promote_owned` | `AssetLibraryService` |

### 1.2 The payload contract (`parameters.prompt`)

Built **only** by `app/creative/prompt_asset.py::build_payload`:

```
contract          "prompt-asset/1"     (required; anything else = unreadable)
family_id         string               (required, stable across revisions)
revision          int >= 1             (required)
purpose           "IMAGE"|"VIDEO"|"AUDIO"|"TEXT"     (required)
origin            "MANUAL"|"AI_GENERATED"|"IMPORTED" (required)
negative_prompt   string   ("" = not authored)
model_reference   string   ("" = not authored)
parameters        object   ({} = not authored)
seed              int >= 0 | null      (null = not authored)
reference_asset_ids  string[]
output_asset_ids     string[]
character_ids        string[]          (binds to Character Bible ids)
scene_ids            string[]          (binds to Scene Bible location_ids)
shot_ids             string[]          (binds to creative shot ids)
change_note       string               (what changed on this revision)
change_reason     string               (why)
redacted          boolean              (true ⇒ project digests, not text)
previous_asset_id string  (optional)   (the immediately preceding revision)
adopted_from      object  (optional)   {owner, field, digest} when adopted from a legacy source
```

**Invariants (test-asserted):** `purpose`/`origin` are validated against the frozen tuples; `revision`
must be an exact `int ≥ 1`; `family_id` is required — a payload missing it is reported in
`malformed`, never silently treated as its own family; an unrecognised `contract` makes the payload
unreadable and the asset is reported, not guessed at.

---

## 2. API 契約 (the exact contract)

All three are **GET only**, permission `domain.read`, on the shared studio invoker. **None writes.**

```
GET /api/projects/{nid}/studio/prompts                 → studio-prompt-library/1
GET /api/projects/{nid}/studio/prompts/context         → studio-prompt-context/1
GET /api/projects/{nid}/studio/prompts/{family_id}     → studio-prompt-detail/1
```

`/prompts/context` is registered **before** `/prompts/{family_id}`, so `context` is a reserved family
name. Query parameters for the context route: `character_id` (repeatable), `location_id`
(repeatable), `document_id` (optional, a creative document id).

### 2.1 `studio-prompt-library/1`

```
contract "studio-prompt-library/1"; schema_version 1
advisory_only true; execution_authority false; auto_modify false; unknown_is_explicit true
required_fields  [text, negative_prompt, model_reference, parameters, seed,
                  reference_assets, output_assets, purpose, origin, binding, version]
purposes [IMAGE, VIDEO, AUDIO, TEXT]; origins [MANUAL, AI_GENERATED, IMPORTED]
binding_kinds [CHARACTER, SCENE, SHOT, ASSET]
prompt_count     == entries.length
revision_count   == total revisions across all families
bible_index_supplied boolean
malformed  [ { asset_id, family_id, reason: "PROMPT_PAYLOAD_UNREADABLE" } ]
entries []:
  family_id, head_asset_id, revision, asset_version,
  purpose, origin, review_status ("APPROVED" if the owner stamped approved_at, else "DRAFT"),
  approved, redacted, unresolved_bindings [],
  reference_asset_ids [], output_asset_ids [],
  bindings { characters [], scenes [], shots [], assets [], verification },
  versions [ { asset_id, revision, asset_version, change_note, change_reason,
               previous_asset_id, redacted } ],     # oldest → newest, all retained
  fields   [ { field, label, value, authored, state } ],   # the 11 required fields
  used_by  []
```

Every binding row is `{ kind, id, resolution: "KNOWN"|"UNKNOWN", verification:
"INDEX_SUPPLIED"|"NO_INDEX_SUPPLIED" }`.

### 2.2 `studio-prompt-detail/1`

The single family entry above plus `history_complete: true`. Unknown family → **404**.

### 2.3 `studio-prompt-context/1`

```
contract; schema_version; advisory_only true; execution_authority false; auto_modify false
composes_prompt_text false            # ← the point: it never writes the prompt
requires_user_confirmation true
sources []: { kind: CHARACTER_BIBLE|SCENE_BIBLE|DIRECTOR_INTENT|SHOT_CARD,
              id, resolution, dimensions: [{field, value, authored, state, source}] }
unauthored []: { kind, id, field }
unknown_is_explicit true
```

---

## 3. UI 消費方式 (how a UI must consume it)

**Not yet built.** The following is the frozen pattern the other three Studio surfaces already use —
copy it; do not invent a fourth.

1. `promptTypes.ts` — mirror the field lists above and freeze them.
2. `promptContract.ts` — a strict decoder as the **only** entry point: reject unknown keys; require
   `state === 'UNKNOWN' ⟺ value === 'UNKNOWN' ⟺ authored === false`; compare `required_fields`
   exactly **including order**; require `prompt_count === entries.length`; require
   `revision_count === Σ versions.length`; accept only `KNOWN`/`UNKNOWN` and
   `INDEX_SUPPLIED`/`NO_INDEX_SUPPLIED`; reject a `purpose`/`origin` outside the frozen tuples.
3. `promptClient.ts` — inject the existing `StudioGraphTransport`, clone scope at construction,
   refuse a foreign project **before** sending.
4. `usePrompts.ts` — `IDLE/LOADING/READY/EMPTY/DENIED/FAILED`; failures keep their machine code and
   are never rendered as "no content".
5. Panels — **Prompt Library** (entries, search/filter by purpose/origin/binding, revision count),
   **Prompt Detail** (the 11 fields + `used_by`), **Version View** (`versions[]` with change note and
   reason; every revision links to its `asset_id`), **Binding View** (per-target `KNOWN`/`UNKNOWN`,
   with `unresolved_bindings` surfaced explicitly).
6. Mount on demand through the existing host panel (as Round 2-B did) via an additive button — no
   protected surface change.
7. **No write control anywhere.** Round 3 §10 forbids a UI that could overwrite a prompt, bump a
   version or delete history, and the API has no such route either.

**UI obligations:** show `UNKNOWN` as a visible state (never blank); label `review_status` DRAFT vs
APPROVED from the owner's stamp; show `redacted` as such; and state that `context` assembles
*sources*, not a finished prompt.

---

## 4. What Round 4 (Asset Intelligence Graph) needs from here

Round 4 must project `Character → Image → Shot → Video → Timeline` with `USED_IN`,
`DERIVED_FROM`, `REFERENCE`, `VERSION_OF`, never guessing, `UNKNOWN` otherwise.

| Round 4 need | Where it already is | Note |
| --- | --- | --- |
| Character node | `bible_projection` `character_bible.entries[].character_id` | Round 2 |
| Scene node | `bible_projection` `scene_bible.entries[].location_id` | **stored lower-cased** by the location owner |
| Shot node | creative document shots; `used_in[].shot_id` | Round 1/2 |
| Image / Video / Audio nodes | `asset_index` rows (`kind ∈ image|video|audio|text`) | asset ids |
| Prompt node | **new**: `prompt_library.entries[].family_id` and `head_asset_id` | Round 3 |
| `REFERENCE` edge | prompt `reference_asset_ids`, and the asset owner's `source_asset_ids` | Round 3 + existing |
| `DERIVED_FROM` edge | asset owner's lineage (`parameters.asset_lineage_v2.parents`) — measured under the write lock | **existing**; digests cannot be fabricated |
| `VERSION_OF` edge | prompt `versions[].previous_asset_id`; asset lineage history | Round 3 + existing |
| `USED_IN` edge | `used_in[]` (built only from authored references on real documents) | Round 2 |
| Review state | asset `approved_at`; world record `status` | existing |
| **Do not** build a fourth relationship store | `app/creative/workspace_relationships.py` already owns `asset_relationships_v2` with 7 declared kinds and an explicit "consumers must not guess undeclared ones" rule | reuse it |

**Two traps Round 4 must avoid**

1. **`asset_index` excludes `parameters`** — it is a deliberately bounded projection. Anything needing
   a prompt payload (or any asset's `parameters`) must read the owner's `list`/`get` under the
   project-binding asset lease, exactly as `PromptWorkspaceService._read_prompts` does.
2. **Asset visibility requires the binding lease.** An asset created outside
   `IndependentWorkspaceService._asset_scope` is invisible to studio reads.

---

## 5. Open items carried into Round 4

1. **No HTTP authoring route for prompt assets** — `ManualAssetImport.kind` is
   `Literal["image","video","audio"]`, so `POST /studio/assets` cannot create a text/prompt asset.
   A prompt can only be authored by a service holding the asset owner. This needs a decision
   (widen the DTO, or add a dedicated prompt-asset route reusing `update_metadata`).
2. **Round3-C Prompt Workspace UI** — `NOT_RUN`.
3. **Adoption of legacy sources (M3 in the audit)** — designed, not executed. `build_payload` already
   accepts `adopted_from={owner, field, digest}`.
4. **Browser/visual acceptance** — still `NOT_RUN` across Rounds 1–3; the largest honest gap.
5. **`check_ui_design_tokens.mjs` scope** — scans `frontend/src/ui` only; each new module must
   self-verify its CSS (recorded in Round 2-B §2.1).
