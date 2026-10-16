# ROUND3_PROMPT_SOURCE_AUDIT — every existing prompt source

**Date:** 2026-10-15 · **Baseline:** `558acea` (`feature/v2-narrative-platform`)
**Scope:** Round 3 §4 requires this scan **before** any design. This document is a read-only audit.
**It changes nothing and deletes nothing.**

Method: repository-wide search for prompt-bearing fields, DTOs, ports and recipe parameter
whitelists, plus a filesystem scan of `prompts/**`. Every row below was read from source.

---

## 1. Sources found

| # | Source | Owner (file:line) | Purpose | Shape |
| --- | --- | --- | --- | --- |
| S1 | `prompts/<agent>/system.md` — **12 files**: archivist, character_keeper, context_builder, continuity_reviewer, director, editor, memory_agent, plot_planner, timeline_keeper, verifier, world_keeper, writer | `app/agents.py::PromptLibrary` reading `settings.prompt_path` (`app/config.py`, env `PROMPT_PATH`, default `prompts`) | agent role instructions | static Markdown on disk, 274–658 bytes each |
| S2 | `ImagePromptParameters.prompt` | `app/creative/graph_models.py:122` | image-prompt **graph node** parameters | `str`, max 8000 |
| S3 | `ImagePromptPort.prompt` | `app/creative/graph_models.py:126` | image-prompt **graph port** contract | `str`, min 1, max 16000 |
| S4 | `StoryboardPromptParameters.prompt` / `StoryboardShotParameters` | `app/creative/graph_models.py:~210`, `:269` | storyboard graph node parameters | `str`, max 16000 |
| S5 | `ShotCard.frame_prompt` | `app/creative/models.py:148` | the storyboard shot's authored frame description | `str`, max 16000 |
| S6 | screenplay transition `prompt` + `motion_prompt` | `app/api.py:268` (`TransitionIn.prompt`), `app/api.py:2233` (`MotionPromptIn.motion_prompt`, max 10000), `app/services/screenplay_service.py:279-302` | I2V motion prompt per transition | `str` on the transition row |
| S7 | production contract `prompt` + `negative_prompt` | `app/creative/production_contracts.py:159-160` | declared production-operation contract | `str`, max 16000 / 8000 |
| S8 | media request/brief `prompt` | `app/experimental/media.py:99` (max 20000), `:160`, `:170` (max 12000) | media generation request + video brief | `str` |
| S9 | provider request `prompt` + `negative_prompt` | `app/asset_providers.py:41,60,112,291`; `app/services/studio_image_provider_recipes.py:117,125,148`; `app/services/studio_video_provider_recipes.py:27,43,73,101` | actual provider invocation | `str` + parameter whitelists |
| S10 | `ImageGenerateIn.prompt` (+ `constraints`, `parameters`, `character_id`, `scene_id`) | `app/api.py:161` | legacy V1 image-generation endpoint | `str`, min 1 |
| S11 | `MediaNodeRequest`/dispatch prompts | `app/creative/graph_media_execution.py`, `app/creative/production_execution_models.py:30,125` | graph media execution | `str` + `negative_prompt` |
| S12 | negative-prompt **digest only** | `app/experimental/production_lineage.py:289-290` | lineage recording | `negative_prompt_digest`, **the text is deliberately not stored** |
| S13 | hard-coded default negative prompt | `app/services/studio_image_provider_recipes.py:148` — `'low quality, blurry, artifacts'` when the recipe is `comfy-sd-checkpoint-v1` | provider fallback | string literal in code |
| S14 | `VisionAnalyzeIn.prompt` | `app/api.py:160` | vision analysis request | `str` |
| S15 | agent runtime prompts | `app/router.py:12`, `app/providers.py:23-28`, `app/model_runtime.py:74`, `app/experimental/model_benchmark.py:26` | provider/agent call interface | `str` (transport-level, not authored content) |

---

## 2. Current problems

**P1 — No identity.** Not one of S2–S12 carries a stable prompt id. A prompt is a bare string on
whatever row happens to hold it, so it cannot be referenced, reused, liked, deprecated or versioned.
Reuse today means copy-paste, and the copies then drift independently.

**P2 — Scattered across ≥10 owners with incompatible bounds.** `prompt` is `max 8000` in S2, `16000`
in S3/S4/S5/S7, `12000` in S8, `20000` in S8's first field, `10000` for `motion_prompt`. The same
creative sentence is legal in one owner and rejected in another, with no shared vocabulary.

**P3 — No version and no history.** Editing `ShotCard.frame_prompt` or a graph parameter overwrites
the previous value. The only recovery is the creative document's own version history (which exists
for documents, not for graph parameters). "Prompt v1 → v2, and why" is not representable.

**P4 — No binding to creative knowledge.** Nothing links a prompt to a character, a scene, a shot or
an asset as a first-class reference. Round 2's Character/Scene Bible ids (`character_id`,
`location_id`) are not referenced by any prompt field, so consistency material cannot reach a prompt.

**P5 — No provenance as a unit.** Prompt text, negative prompt, model, parameters, seed, references
and output live in different rows owned by different services. Reproducing a result means
reconstructing the combination by hand from job records.

**P6 — Silent hidden defaults.** S13's hard-coded `'low quality, blurry, artifacts'` is applied only
for one recipe; a user cannot see or override it as an authored decision.

**P7 — A deliberate redaction precedent.** S12 stores only a **digest** of the negative prompt. Any
prompt-asset design must respect that precedent rather than casually recording full prompt text where
the project deliberately chose not to.

**P8 — S1 is a different kind of thing.** The 12 `system.md` files are **deploy-time agent
configuration**, not user creative content. They are read from disk by `PromptLibrary` and must not
be turned into assets, versioned by users, or overwritten — that would silently change agent
behaviour.

---

## 3. Audit consequence for the design

The audit establishes three constraints the design must honour:

1. **Prompts must become assets with identity — reusing the existing asset owner**, per Round 3 §3.
   No second asset/version/review store.
2. **All 15 sources must keep working unchanged.** This is an **adopt, never migrate** operation:
   adoption *reads* an existing value and creates a new prompt asset from it; it never rewrites the
   originating field. S1 is explicitly out of scope (deploy-time configuration, not user content).
3. **P7 must constrain the payload.** Where the project already redacts prompt text in lineage, the
   prompt asset must make redaction an explicit, selectable property rather than recording everything
   by default.

---

## 4. What was verified about the reuse target (so the design rests on facts)

Read from `app/services/asset_library_service.py`:

| Property | Finding | Consequence |
| --- | --- | --- |
| `create(..., kind=...)` | `kind` is free-form: `str(kind or "file")[:40]` | a `prompt` kind needs **no owner change** |
| asset bytes | written once in `create`; `_bin_path`/`_meta_path` are per-asset files; no path replaces bytes | **bytes are immutable** → a changed prompt is a new asset, and every old version stays readable forever |
| `update_metadata` | allow-listed fields `{source_job_id, provider_id, model_id, parameters, approved_at, character_id, scene_id, source_asset_ids}`; bumps `version` with `expected_version` CAS; **retains no history** | `parameters` (a dict) is the sanctioned home for structured prompt data; `character_id`/`scene_id` are **already** binding hooks; version CAS is the existing version owner |
| `annotate_lineage` | keeps a `history` list with `asset_version` inside `parameters.asset_lineage_v2`; measures parent version+digest **under the write lock** so digests cannot be fabricated | the existing version-chain mechanism for "this asset is a new version of that one" |
| `promote_owned` | existing review with CAS | the existing review owner for prompt approval |
| `delete`/`restore` | soft delete; **keeps original bytes and identity**; existing reads 404 | history is never destroyed |
| `TEXT_RESULT_PROVENANCE_IMMUTABLE` | an asset created via `create_text_result` may **never** have `parameters` changed | prompt assets must be created through plain `create(...)`, **not** `create_text_result` |

---

## 5. Migration plan (non-destructive)

| Step | Action | Reversible? |
| --- | --- | --- |
| M1 | Define a **Prompt Asset** as an existing `text` asset with `kind="prompt"`; bytes = prompt text; structured payload under `parameters.prompt`; references via `source_asset_ids`; bible binding via the existing `character_id`/`scene_id` metadata fields. **No asset-owner change.** | n/a (additive) |
| M2 | Express versions as an **asset chain**: v(n) is a new asset whose `source_asset_ids` includes v(n-1), annotated through the existing `annotate_lineage`. Old versions are immutable and retained. | fully reversible (new assets only) |
| M3 | Provide **adoption** for S2–S12: read the existing value, create a prompt asset, and record the source as `{owner, field, digest}` in the new asset's payload. **The originating field is never modified.** | fully reversible |
| M4 | Leave **S1 untouched and out of scope** (deploy-time agent configuration). | n/a |
| M5 | Respect **P7**: the payload records prompt text only when the author chooses to; a `redacted` mode records digests instead, matching the existing lineage behaviour. | n/a |
| M6 | A later increment may add an **optional** `prompt_asset_id` reference beside legacy fields so existing owners can point at a library entry. Legacy strings remain authoritative until then. | optional, additive |

**No old source is deleted, rewritten or migrated in Round 3.** After M1–M5 the system gains a
library that *adopts* existing work while every legacy path keeps behaving exactly as it does today.

---

## 6. Status of this audit

| Item | Status |
| --- | --- |
| Scan completed and read from source | `IMPLEMENTED` (this document) |
| 15 sources identified, S1 excluded with reason | `IMPLEMENTED` |
| Reuse target verified against implementation, not assumption | `IMPLEMENTED` (§4) |
| Migration plan defined, non-destructive | `IMPLEMENTED` (§5) |
| Any migration executed | `NOT_RUN` — deliberately: Round 3 adopts, it does not migrate |
| `prompts/**` modified | `NOT_RUN` — and must never be, by this round |
