# ROUND3_PROMPT_REPORT — Prompt Intelligence System

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline:** `558acea` · **`main` = `fed2404c`, never touched** · **PR #47:** `OPEN`, `isDraft: true`.

> ## Scope of this increment
>
> Round 3's **audit and backend are complete and verified on both backends.** The **Prompt
> Workspace UI (Round3-C) and its strict decoder are `NOT_RUN`**, and there is **no HTTP authoring
> route for prompt assets** — both are stated plainly below and neither is claimed as done.

---

## 1. Round 3 §4 — the mandatory audit came first

`ROUND3_PROMPT_SOURCE_AUDIT.md` was produced **before any design**, and it is a read-only scan that
**changed and deleted nothing**. It identified **15 prompt sources**:

* **S1** `prompts/<agent>/system.md` × 12 — deploy-time agent configuration read by
  `app/agents.py::PromptLibrary`. **Explicitly excluded from Round 3**: these are not user creative
  content, and versioning them would silently change agent behaviour.
* **S2–S14** — `ImagePromptParameters` / `ImagePromptPort` / `StoryboardPromptParameters`
  (`graph_models.py`), `ShotCard.frame_prompt` (`models.py:148`), screenplay transition
  `prompt`/`motion_prompt`, production-contract `prompt`/`negative_prompt`, media request/brief
  prompts, provider-invocation prompts and their parameter whitelists, the legacy
  `ImageGenerateIn`, graph media execution, `VisionAnalyzeIn`, and the hard-coded fallback negative
  prompt `'low quality, blurry, artifacts'`.
* **S15** transport-level agent/provider prompts (interface, not authored content).

**Eight problems were documented**, the material ones being: no identity anywhere (a prompt is a bare
string on whatever row holds it), incompatible bounds across owners (`8000` / `10000` / `12000` /
`16000` / `20000` for the same kind of text), no version/history, no binding to Round 2's
Character/Scene Bible, no provenance as a unit, and a **deliberate redaction precedent**
(`production_lineage.py:289` stores only a `negative_prompt_digest`).

---

## 2. Round 3-A — the Prompt Asset, built by reusing not adding

The audit's decisive finding was what the **existing asset owner already provides**, verified by
reading `app/services/asset_library_service.py` rather than assuming:

| Prompt Asset property | Existing owner field | Owner change needed |
| --- | --- | --- |
| identity | the asset id | none |
| prompt text | the asset's bytes, `kind="prompt"` (`kind` is free-form `str(kind)[:40]`) | none |
| negative prompt, model, parameters, seed, purpose, origin, change note/reason | `parameters` — an **already allow-listed** dict field | none |
| character / scene binding | `character_id` / `scene_id` — **already allow-listed** metadata fields | none |
| reference outputs | `source_asset_ids` | none |
| version | asset `version` + `expected_version` CAS | none |
| version chain | `annotate_lineage`, which already retains `history` with `asset_version` | none |
| review | `promote_owned` | none |
| history retention | bytes are immutable; `delete` keeps bytes and identity | none |

**`app/services/asset_library_service.py` was not modified. No new collection, table, database,
asset system, version system or review system was created.** Because bytes are immutable, a revised
prompt is a *new asset in the same family* (`family_id` stable, `revision` 1→2→3, predecessor linked
through the existing lineage) — so every prior revision stays physically readable and history cannot
be lost.

**Metadata (§6):** `purpose ∈ {IMAGE, VIDEO, AUDIO, TEXT}`, `origin ∈ {MANUAL, AI_GENERATED,
IMPORTED}`, bindings to `CHARACTER | SCENE | SHOT | ASSET` — all frozen vocabularies, all validated
by the payload builder.

**Redaction (§ audited precedent):** a prompt may be authored `redacted: true`, in which case the
projection emits digests for the prompt text and negative prompt instead of the text.

---

## 3. Round 3-B — binding is a reference, never a copy

Bindings are **ids only**. The projection resolves each declared id against the live bible/asset
index and reports `KNOWN` or `UNKNOWN` per target:

* a target that exists → `KNOWN`;
* a target that does not → **`UNKNOWN`**, listed in `unresolved_bindings`, **never dropped and never
  assumed present** (Round 3 §7: "真实存在才显示；不存在 UNKNOWN");
* when no index was supplied → every binding is `UNKNOWN` with `verification: NO_INDEX_SUPPLIED`,
  so the surface can say *why* rather than implying the target is missing.

No prompt text is copied out of the Character or Scene Bible, and **no bible field is written by this
round** — a bible edit is visible to the prompt library on the next read, which is exactly the
"Prompt 读取最新授权版本" behaviour required.

---

## 4. Round 3-D — context assembly that refuses to compose the prompt

`project_prompt_context` reports **sources**, not text: Character Bible dimensions, Scene Bible
dimensions, Director Intent fields and Shot Card dimensions, each with `authored`/`state`/`source`,
plus an `unauthored` list of what is still missing.

It returns **`composes_prompt_text: false`** and **`requires_user_confirmation: true`** as contract
fields. Auto-composing a final prompt is precisely the "AI 自动覆盖用户 Prompt" behaviour Round 3
§10 forbids, so the module has no code path that could do it.

---

## 5. Verification

| Leg | Command | Result |
| --- | --- | --- |
| **Backend — File** | `round3-prompt-r4`: Round 3 suite + bible + director + world + asset library + creative workflows | **177 passed, 69 skipped, exit 0** |
| **Backend — real PostgreSQL** | `round3-prompt-postgres`: fresh `v2_round3`, 20 migrations, disposable loopback cluster stopped cleanly | **108 passed, exit 0** |
| New suite | `tests/test_round3_prompt.py` | 33 cases (incl. 5 route integration tests on the real router, real File store and real asset owner) |
| §12 old-project safety | a project with **no prompt assets** projects cleanly: `prompt_count 0`, `entries []`, no `malformed` | asserted |
| §12 old-graph safety | the projection ignores non-prompt kinds; `graph_models.py` was **not touched** | asserted |
| §12 unknown fields | payload readability gate rejects a wrong contract / purpose / non-int revision | asserted |
| §12 versions | every revision retained with its change note **and** reason; predecessor linked; families never merged | asserted |
| §12 bindings | `KNOWN` only when the target really exists; otherwise `UNKNOWN` | asserted |
| **Frontend / TypeScript / Build** | — | **`NOT_RUN`** — no frontend work in this increment |

### 5.1 Intermediate FAIL runs are committed as produced

`round3-prompt-r1..r3` and `round3-probe-*` are committed exactly as produced. They failed on **my**
mistakes, and one of them was genuinely informative:

* `r1` referenced a probe asset without the project-binding lease, so it was invisible;
* diagnosing it produced a real, previously-unrecorded fact: **`asset_index` is a deliberately
  bounded projection that excludes `parameters`**, so a prompt's payload cannot be read from it. The
  service now reads the owner's own `list`/`content` under the same asset lease — a fix the probe
  forced, not a guess.
* `r3` failed on a signature mismatch I introduced while fixing the above.

No product assertion was weakened to reach green.

### 5.2 Two further findings worth recording

1. **`ManualAssetImport.kind` is `Literal["image","video","audio"]`** (`workspace_models.py:53`), so
   the existing `POST /studio/assets` route **cannot create a text or prompt asset**. Authoring a
   prompt today requires a service holding the asset owner (as the test rig does). This is the
   largest functional gap in Round 3 and is why the round cannot be called complete.
2. **Asset visibility requires the project-binding lease** (`IndependentWorkspaceService._asset_scope`).
   An asset created outside it is correctly invisible to studio reads.

---

## 6. Status matrix

| Component | Status | Boundary |
| --- | --- | --- |
| Prompt source audit (§4) | **IMPLEMENTED** | 15 sources, 8 problems, non-destructive plan |
| Prompt Asset identity & payload | **IMPLEMENTED** | existing `kind="prompt"` asset + `parameters.prompt`; **no owner change** |
| Version + change note/reason | **IMPLEMENTED** | immutable revisions in a family; predecessor via existing lineage |
| Binding (Character/Scene/Shot/Asset) | **IMPLEMENTED (read-only)** | ids only; `KNOWN`/`UNKNOWN` per target |
| Prompt Library projection (§8 data) | **IMPLEMENTED** | contract `studio-prompt-library/1` |
| Prompt Detail / version view (§8 data) | **IMPLEMENTED** | contract `studio-prompt-detail/1` |
| Prompt generation context (§9) | **IMPLEMENTED** | `composes_prompt_text: false` |
| AI must not overwrite / auto-version / delete history (§10) | **IMPLEMENTED** | the projection module and all three routes have **no write path at all** |
| Review reuse | **IMPLEMENTED (reused)** | `promote_owned`; the projection only reports `approved_at` |
| **Prompt Workspace UI (Round3-C)** | **`NOT_RUN`** | no Prompt Library / Detail / Version / Binding surface exists |
| **Frontend decoder / vitest / tsc / build** | **`NOT_RUN`** | nothing frontend changed this round |
| **HTTP authoring route for prompt assets** | **`NOT_RUN`** | `ManualAssetImport.kind` excludes text/prompt — needs a decision |
| Migration of legacy prompt sources | **`NOT_RUN`** (by design) | Round 3 **adopts**; nothing was migrated, rewritten or deleted |
| `prompts/**` modified | **`NOT_RUN`** | and must not be |
| Browser / visual acceptance | **`NOT_RUN`** | unchanged |
| Release candidate | **`NOT ESTABLISHED`** | unchanged |
| `CONTENT_POLICY_FRAMEWORK` | **`RESERVED`** | unchanged |

**Standing rules re-affirmed:** no second asset/version/review system; `main` untouched; PR #47
Draft; no release; no QingJian linkage; no NSFW; protected untracked baseline untouched.

---

## 7. Files in this round

**Added — backend (4)**
`app/creative/prompt_asset.py` · `app/creative/prompt_workspace.py` · `app/creative/prompt_api.py`
**Modified — backend (2)** `app/creative/workspace_api.py` (admission + router include) ·
`app/experimental/api.py` (service wiring, reusing the existing bible service)
**Added — tests (1)** `tests/test_round3_prompt.py`
**Added — docs (3)** `ROUND3_PROMPT_SOURCE_AUDIT.md` · `ROUND3_PROMPT_REPORT.md` · `ROUND3_HANDOFF.md`
**The asset owner was not modified.**

**Evidence** `docs/delivery/v2-development/round3-prompt-{r1..r4,postgres}.json|.log`,
`round3-probe-*`
