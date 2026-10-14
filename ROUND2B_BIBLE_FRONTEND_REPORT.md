# ROUND2B_BIBLE_FRONTEND_REPORT — Character & Scene Bible Frontend Surface

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline:** `4560dc0` (Round 2 backend; local = remote at round start).
**`main` = `fed2404c`, never touched.** **PR #47:** `OPEN` / `isDraft: true`. No merge, no release, no tag.

**Status vocabulary:** `IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.

---

## 1. 完成内容 (what was delivered)

`GET /api/projects/{nid}/studio/bible` became a usable, **strictly read-only** Studio workspace.
**No backend code was changed in this round** — the frontend consumes the Round 2 projection as-is.

| Deliverable | Status | Detail |
| --- | --- | --- |
| Character Bible Panel | **IMPLEMENTED** | One card per character, all **six** required dimensions: identity, appearance, clothing, reference, behaviour, relationship |
| Scene Bible Panel | **IMPLEMENTED** | One card per location, all **seven** required dimensions: location, architecture, material, lighting, weather, time, mood |
| Reference assets | **IMPLEMENTED** | Each declared asset id rendered individually with `RESOLVED` / `UNRESOLVED`; an audit note states when no index was supplied so nothing can be assumed found |
| Behaviour / Relationship | **IMPLEMENTED** | Rendered from the existing `WorldService` `PSYCHOLOGY` / `RELATIONSHIP` records; relationships are **never** inferred — an empty set says the original document recorded none |
| `UNKNOWN` as a state | **IMPLEMENTED** | Unauthored dimensions render the **literal `UNKNOWN`** plus "未作者化", with a dashed neutral treatment, and are tagged `data-state="UNKNOWN"` |
| `DRAFT` is not canon | **IMPLEMENTED** | A non-approved world record renders `DRAFT（非 canon）` with a warning accent; only approved values render `CANON · APPROVED`. Field-level and entry-level both shown |
| Read-only interaction | **IMPLEMENTED** | The panel has **no** edit, save, create or delete control and no textbox/combobox anywhere; a test asserts this |
| Source traceability | **IMPLEMENTED** | Every dimension shows the exact owner path it was read from (e.g. `world_records.CHARACTER_VISUAL.appearance`) |
| `used_in` | **IMPLEMENTED** | Where a character/location actually appears, built only from authored references on real scenes/shots |

**Architecture:** new `frontend/src/bible/` (12 files). The client injects the **existing** transport and
reads exactly one endpoint; no second Character/Scene/Asset system, no data duplication — the UI only
renders the projection. Mounted **on demand** through the existing `StoryboardWorkspacePanel` via a new
button, so no protected surface (`AppShell`, `ModuleSwitcher`, `ContextBar`, `StatusBar`, tokens,
primitives) was touched and every existing consumer is unaffected.

### 1.1 真实性规则 (the honesty rules, and where they are enforced)

The three rules are enforced in the **decoder**, not merely in prose, so a drifting backend cannot
silently produce a dishonest UI:

| Rule | Enforcement |
| --- | --- |
| 未知是状态，不是空白 | `state === 'UNKNOWN'` **requires** `value === 'UNKNOWN'` and `authored === false`; a blank or whitespace value throws. Conversely `AUTHORED` requires a non-empty value |
| Draft 不是 Canon | `authored` must agree with `state`; canon is derived from the owner's own record status, and only `APPROVED` becomes `authoritative` |
| Asset 没有 index 就 UNRESOLVED | `unresolved_references` must equal exactly the `UNRESOLVED` entries; `NO_INDEX_SUPPLIED` may not contain any `RESOLVED` reference |

Plus: unknown keys rejected at every level (per-dimension allowed-key sets are frozen per field),
required-field tables compared exactly **including order**, and counts must equal entry counts.

---

## 2. 测试结果 (test results — all five legs run, none skipped)

| Leg | Command | Result |
| --- | --- | --- |
| **Frontend tests** | `round2b-frontend-r1`: `vitest run src` (365 files) | **4002 passed, 6 skipped, exit 0** |
| **TypeScript** | `round2b-types-r1`: `tsc --noEmit` | **PASS** |
| **Build** | `round2b-build-r1`: `vite build frontend` | **PASS** |
| **Backend — File** | `round2b-backend-file-r1`: bible + director + camera + world + creative-workflow suites | **190 passed, 69 skipped, exit 0** |
| **Backend — PostgreSQL** | `round2b-backend-postgres`: fresh `v2_round2b`, 20 migrations, disposable loopback cluster stopped cleanly | **140 passed, 69 skipped, exit 0** |

New tests: `bibleContract.test.ts` (17) · `BibleWorkspace.test.tsx` (12) = **29 new cases**.
The host panel's own 24 tests still pass, confirming the additive mount broke nothing.

The decoder tests specifically cover the rules this round exists to guarantee: unknown-shown-as-blank
rejected, `authored`/`state` mismatch rejected, inconsistent unresolved-reference lists rejected,
`NO_INDEX_SUPPLIED` with a resolved reference rejected, required-field and dimension-order drift
rejected, and unknown dimension keys rejected.

### 2.1 一处需要更正的记录 (a correction to a previously reported claim)

Reviewing the design-token guard (`scripts/check_ui_design_tokens.mjs`) while writing this round showed
that it **only walks `frontend/src/ui`**:

```js
walk(path.join(root,'frontend','src','ui'));
```

So `UI token guard PASS (52 files)` has **never** covered new CSS under `src/director/` or `src/bible/`.
The Phase14-A report cited that pass alongside its new CSS without stating this scope, which over-implied
coverage. To correct it, this round verified its own stylesheet **directly**:

* no raw hex / `rgb()` / `hsl()` colours — clean;
* no arbitrary `px` for `padding` / `margin` / `gap` / `border-radius` outside `var(--…)` — clean.

The Phase14-A stylesheet was re-checked the same way and is also clean, so the *conclusion* there still
holds — but it was reached by this check, not by the guard. **The guard's narrow scope is itself worth a
decision** by the Root/Design System Owner (see §4).

---

## 3. 未完成内容 (what was NOT done)

| Item | Status | Boundary |
| --- | --- | --- |
| Identity split into name / age / role / status rows | `PARTIAL` | The projection supplies one joined identity value plus the entry `name`. The UI shows both and labels the owner source; it does **not** parse the joined string, because splitting it in the view would be inventing structure. Exposing it as a structured `detail` on the projection is the clean fix — **deliberately not done** because this round was scoped frontend-only. |
| Authoring a visual profile from any Studio surface | `NOT_RUN` | The owner route accepts `CHARACTER_VISUAL` / `SCENE_VISUAL` today with review and CAS; no authoring UI exists, and this round was explicitly forbidden from adding write controls. |
| Bible-driven generation (Image / Video / Storyboard) | `NOT_RUN` | `used_in` is *reported*, but no generation path consumes the bible yet. That is Round 3 territory. |
| Browser / visual acceptance (Playwright) | `NOT_RUN` | Component-level (jsdom) evidence only. The stylesheet was verified by token/geometry inspection, not by screenshot. |
| `location` id lower-casing asymmetry | RECORDED | The existing location owner lower-cases ids (`"L1"` → `l1`) while character ids are preserved. The UI displays whatever the owner stored; not changed. |
| Style verification coverage | RECORDED | As in §2.1 — the repo's token guard does not scan these directories. |

---

## 4. 下一阶段依赖 (dependencies for the next stage)

1. **Round 3 (Prompt Intelligence)** depends on the bible's **stable field vocabulary**
   (`CHARACTER_BIBLE_FIELDS`, `SCENE_BIBLE_FIELDS`) and on the `character_id` / `location_id`
   identity keys, to bind prompt assets to characters and scenes. All three are frozen and tested.
   See `ROUND2B_HANDOFF.md` for the exact contract.
2. **A structured identity `detail`** would let a prompt template reference `character.name` /
   `age` / `role` without parsing a joined string. Small, additive, backend-side.
3. **Reference asset rendering** currently shows ids; Round 3+ will want a thumbnail via the existing
   asset download route. This must reuse the asset owner — no new lookup, no filesystem search.
4. **Style-verification gap (decision needed):** the token guard's scope is `frontend/src/ui` only.
   Either widen it to `frontend/src/**/*.css` or add a per-module check. This is a Design System Owner
   decision; it was **not** taken unilaterally. Until then, each module must self-verify (as done here).
5. **Round 2 residual:** the frontend never exercises a real backend end-to-end in a browser. Browser
   acceptance of both the Director Workspace and the Bible remains `NOT_RUN` and is the largest honest
   verification gap across Rounds 1–2.

---

## 5. 状态矩阵 (status matrix)

| Component | Frontend | Backend | File | PostgreSQL | Browser | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| Character Bible Panel | `IMPLEMENTED` | `IMPLEMENTED` | PASS | PASS | `NOT_RUN` | 6 dimensions, read-only |
| Scene Bible Panel | `IMPLEMENTED` | `IMPLEMENTED` | PASS | PASS | `NOT_RUN` | 7 dimensions, read-only |
| Reference assets | `IMPLEMENTED` | `IMPLEMENTED` | PASS | PASS | `NOT_RUN` | RESOLVED / UNRESOLVED per id |
| Behaviour / Relationship | `IMPLEMENTED` | `IMPLEMENTED` | PASS | PASS | `NOT_RUN` | from existing WorldService records |
| `UNKNOWN` state | `IMPLEMENTED` | `IMPLEMENTED` | PASS | PASS | `NOT_RUN` | literal, decoder-enforced |
| `DRAFT` vs `CANON` | `IMPLEMENTED` | `IMPLEMENTED` | PASS | PASS | `NOT_RUN` | owner status carried through |
| Read-only guarantee | `IMPLEMENTED` | `IMPLEMENTED` | PASS | PASS | `NOT_RUN` | no write control; asserted |
| Identity field breakdown | `PARTIAL` | `PARTIAL` | PASS | PASS | `NOT_RUN` | joined value shown, not parsed |
| Profile authoring UI | `NOT_RUN` | `IMPLEMENTED` (owner route) | PASS | PASS | `NOT_RUN` | out of scope this round |
| Bible-driven generation | `NOT_RUN` | `NOT_RUN` | — | — | — | Round 3+ |
| Browser / visual acceptance | `NOT_RUN` | — | — | — | `NOT_RUN` | largest open gap |
| Release candidate | — | — | — | — | — | **`NOT ESTABLISHED`** (unchanged) |
| `CONTENT_POLICY_FRAMEWORK` | — | `RESERVED` | — | — | — | unchanged |

**Standing rules re-affirmed:** no new Character/Scene/Asset system; the UI only renders the
projection; `main` untouched; PR #47 Draft; no release; QingJian untouched; the protected untracked
baseline files untouched; intermediate work committed as produced.

---

## 6. Files in this round

**Added — frontend (12, all under `frontend/src/bible/`)**
`bibleTypes.ts` · `bibleContract.ts` · `bibleClient.ts` · `useBible.ts` ·
`BibleDimensionRow.tsx` · `CharacterBiblePanel.tsx` · `SceneBiblePanel.tsx` · `BibleWorkspace.tsx` ·
`bibleWorkspace.css` · `bibleFixtures.testFixture.ts` · `bibleContract.test.ts` · `BibleWorkspace.test.tsx`

**Modified (1)**
`frontend/src/storyboard/StoryboardWorkspacePanel.tsx` (additive on-demand mount)

**Backend:** none — this round changed no backend file.

**Evidence**
`docs/delivery/v2-development/round2b-{frontend,types,build,backend-file,backend-postgres}-r*.json` + logs
