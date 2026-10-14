# SESSION_RECONSTRUCTION_REPORT — AI-Novel-Studio V2

**Supersedes** the reconstruction report committed at `c939b9b` (written for the earlier Phase14
directive). That version remains in Git history; this one reflects the current HEAD and the
**Round 1–10** master roadmap.

**Date:** 2026-10-15 · **Purpose:** §0 SESSION BOOTSTRAP. This report restores engineering context
only. **It writes no product code and reclassifies nothing.**

**Status vocabulary:** `IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.

---

## 0. The one thing to know first

**Round 1 of this master directive is already complete.** Its required scope —
Director Workspace (Visual Goal · Mood · Genre · Camera Language · Lighting · Color · Performance),
Shot Card (11 fields), Continuity Panel (Character · Costume · Scene · Time · Lighting, prompt-only) —
is exactly what was delivered as **Phase14-A** in this same working session and pushed as commit
`4a97f8f`. §2 below verifies it requirement by requirement rather than re-doing it.

The correct next action is therefore **Round 2 (Character & Scene Bible)**.

---

## 1. Repository and environment verification (§0.1, §0.3)

| Check | Value |
| --- | --- |
| Repository | `1785235376-blip/AI-Novel-Studio` |
| Development directory | `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` |
| Branch | `feature/v2-narrative-platform`, **upstream ahead 0 / behind 0** |
| **HEAD** | `4a97f8f6d17539d2e1ad73fd82739272af7278de` — *feat(v2): Phase14-A professional director system* |
| **`main`** | `fed2404c8e30b44061b7139dced45b7f3301601c` — **frozen, untouched** |
| **PR #47** | `OPEN`, **`isDraft: true`**, base `main` ← head `feature/v2-narrative-platform`, head OID = HEAD |
| Tracked dirty | **0** |
| Untracked | **39** — protected baseline families (receipts/caches). Not cleaned, not committed. |
| Forbidden actions | `reset` / `clean` / `force push` / `checkout main` were **not** run |

| Component | State |
| --- | --- |
| Python | **3.11.9** — `fastapi/uvicorn/psycopg/sqlalchemy/httpx/pydantic_settings/reportlab/pypdf/jsonschema/pytest` all import; `import app.main` **OK** |
| Node / pnpm | `v22.14.0` / `12.4.2`; `frontend/node_modules` present (pnpm layout); lockfile untouched |
| .NET | **8.0.424** = exact `global.json` pin (`rollForward: disable`) |
| Git / gh | `2.55.0` / authenticated as `1785235376-blip` |
| **Database** | **PostgreSQL 16.15 now working** — see §1.1 |
| Forbidden actions | No dependency upgraded, installed or removed; no lock file changed |

### 1.1 Database — the previous `NOT_RUN` is now closed

This host had **no PostgreSQL cluster** (no service; binaries only inside a packaged build). §0.3
requires checking the Database, and every later round touches owner models whose verification
convention is dual-backend. So a **disposable, loopback-only cluster owned by this checkout** was
created under `.runtime` (gitignored) using the repo's own sanctioned pattern from
`scripts/verify_windows_base.py`:

```
initdb -D .runtime/pgdata-v2-phase14a -U novel_ci --encoding=UTF8 --locale=C --auth=trust
```

The repo's `scripts/run_v2_postgres_checks.py` then took exclusive ownership, started the server,
created a fresh database from the **20 sorted migrations**, ran the checks on **real PostgreSQL**,
and stopped the cluster cleanly.

**Result:** Phase14-A suites on PostgreSQL — **147 passed, 60 skipped, exit 0**.
Receipts: `phase14a-director-postgres.json`, `phase14a-director-postgres-postgres-runtime.json`.
Cluster confirmed stopped afterwards (`pg_ctl status` → *no server running*).

**This removes a permanent `NOT_RUN` from every remaining round** rather than from one row only.

**Host constraints that still hold (verified live):** port `8080` = the running Strata model server
(pid 16292) — never stop it; port `8100` taken by an unrelated service → dev backend uses `8110`;
`bash` absent (one known `BLOCKED_EXTERNAL` check); `ffmpeg` at
`D:\ffmpeg\ffmpeg-8.1.2-essentials_build\bin`; symlink creation lacks a Windows privilege
(`WinError 1314`); hosted CI is `BLOCKED_ACCOUNT_PLATFORM`.

---

## 2. Round 1 acceptance — verified, not assumed

| Round 1 requirement | Status | Evidence |
| --- | --- | --- |
| Director Workspace: Visual Goal · Mood · Genre · Camera Language · Lighting · Color · Performance | **IMPLEMENTED** | `app/creative/director_intent.py` projects all seven as `DIRECTOR_INTENT_FIELDS`; `frontend/src/director/DirectorIntentPanel.tsx` renders each with `data-field`. Camera language, lighting and performance are `PER_SHOT_MEASURED` — structurally unable to be shown as a director decision. |
| Shot Card: Shot ID · Duration · Camera · Lens · Movement · Composition · Lighting · Character · Action · Emotion · Audio | **IMPLEMENTED** | `SHOT_CARD_FIELDS` (11) projected from the existing `ShotCard` owner; `ShotCardPanel.tsx` renders all 11, each tagged so "all eleven render" is asserted by test. |
| Continuity Panel: Character · Costume · Scene · Time · Lighting | **IMPLEMENTED** | `camera_language.CONTINUITY_FIELDS` extended to exactly these five, each with declared *authored* sources. |
| Rule: prompt only, never auto-modify | **IMPLEMENTED** | `warning_only: true` / `auto_modify: false` are **contract fields**; the decoder refuses a payload claiming otherwise, a test asserts no write control exists, and the module exposes no `create/update/write/save/commit/delete`. |
| No duplicate system | **IMPLEMENTED** | A test asserts the projection defines no `Shot/Scene/Project/Asset/Task` model and imports no application model. Only two additive **opt-in** fields were added to existing owners (`DirectorVisualTarget.genre`, `ShotContinuity.time`/`lighting`), which are omitted from serialization while unset so existing documents keep their exact shape and digest. |
| Verification | **IMPLEMENTED** | File backend **159 passed / 70 skipped / exit 0**; regression **127 passed / exit 0**; **PostgreSQL 147 passed / 60 skipped / exit 0**; `tsc` PASS; `vite build` PASS; `vitest run src` **3973 passed / exit 0**; design-token guard PASS (52 files). |

**Round 1 residual gaps (recorded, not hidden — they do not block the Round 1 scope above):**

* **Write-back authoring from the workbench: `NOT_RUN` by design.** The workbench is read-only;
  camera-language edits stay a labelled local session draft. Authoring still uses the pre-existing
  creative document update endpoint, which now also accepts `genre` with no API change.
* **Genre authoring UI: `PARTIAL`** — the field is writable through that existing endpoint; no new
  write control was added.
* **Browser / visual acceptance: `NOT_RUN`** — component-level (jsdom) evidence only.

---

## 3. Current capability state

### 3.1 `IMPLEMENTED` — real, evidence-backed

* **Real model-free production chain** (Phase12): Text → Director/Screenplay → shot plan →
  storyboard → approval → Export, every step a real product operation with real ids/versions/
  digests, real 1 930-byte artefact.
* **Model Center runtime observation ladder ⓪–⑤** — observation-only, no child process; level ⑤
  `READY` reached once with one real inference (53.7 s, 65 tokens) against the Strata server.
* **GPU physical identity fix** (`82d1282`) — DXGI double-count collapsed only on passive
  present-device proof; capability `(None, 0)` → `(NVIDIA uuid, 15 977 MiB)`.
* **Graph `schema_version` gate fix** (`5c100e9`) — illegal versions now refused; legacy default
  made explicit, nothing force-upgraded.
* **Camera language vocabulary** (`0e10c5d`) + **Phase14-A director system** (`4a97f8f`) as in §2.
* **UX-PRODUCT batches 1–5** — nine frontend UX directories, component/contract level.
* **`CONTENT_POLICY_FRAMEWORK` = `RESERVED`** (unchanged), V1 freeze intact.

### 3.2 `PARTIAL`

Baseline markers unchanged: `F00 INTEGRATED` + **39 PARTIAL** rows, independent review `BLOCKED`,
`M4` PARTIAL, `GATE-M2`/`M9`/`M11` MISSING. Most `CORE-*`, `START-*`, `STORE-*`, `MODEL-*` rows are
PARTIAL. Named open items carried forward: the **frontend port-table duplication** (audited, not
migrated — deliberate cross-pinning, not drift); the **real media pipeline** (model-free segment
real, model-dependent steps blocked); **Windows RC preparation** (prep done, execution not).

### 3.3 `BLOCKED`

* **Local runtime registration** — `POST /api/model-center/local-ai/runtimes` → **401
  `SESSION_REQUIRED`**; an intentional authority gate, not a defect. Task routing therefore `NOT_RUN`.
* **Hosted CI** — `BLOCKED_ACCOUNT_PLATFORM`.
* **`DOC-03`** final RC candidate/manifest; **Appendix A** expansions; the historical independent
  review.
* **Windows symlink test** — `BLOCKED_EXTERNAL` (`WinError 1314`).

### 3.4 `LOCAL_REQUIRED`

`MODEL-18` (8/12/16 GB performance evidence), `GATE-M12`, `WIN-01`…`WIN-07`, **live local runtime
end-to-end (app-native)**, `M5–M9` acceptance. No cloud or mock result substitutes.

### 3.5 `NOT_RUN`

Phase14 leftovers: **P3 Prompt Studio · P4 Character/Scene profiles · P5 Asset relationship
projection · P6 Timeline parameter layer · P7 Audio layer · professional-vs-simplified mode**.
Also `NOT_RUN`: Windows clean-machine execution, packaged DesktopHost, GPU CUDA execution through
the app, export packaging, any full CI run, browser/visual acceptance.

**Release-candidate conclusion: `NOT ESTABLISHED`** — unchanged by Phase13, Phase14 and Phase14-A.

---

## 4. Roadmap mapping (master directive Round 1–10)

| Round | Scope | State |
| --- | --- | --- |
| **1** | **Professional Director System** | ✅ **COMPLETE** (Phase14-A, `4a97f8f`) — §2 |
| **2** | **Character & Scene Bible** | **NEXT** — basic `ShotCard.characters`/`environment` and `DirectorNote.character_state`/`performances` exist, but no authored profile owner |
| 3 | Prompt Intelligence System | `NOT_RUN` (was Phase14 P3) |
| 4 | Asset Intelligence Graph | `NOT_RUN` (Phase10 declares 7 relationship kinds; no full-chain projection) |
| 5 | Professional Timeline | `NOT_RUN` (was Phase14 P6) |
| 6 | Audio Professional Layer | `NOT_RUN` (was Phase14 P7) |
| 7 | Workflow Intelligence (Project Assistant) | `NOT_RUN` — note: **not** QingJian, no long-term persona |
| 8 | Model Ecosystem (Model Center) | `PARTIAL` — discovery/observation exist; capability mapping and hardware matching are partial |
| 9 | Professional UX Polish (novice/pro mode) | `NOT_RUN` (was Phase14 mode split) |
| 10 | Product Maturity Audit | not started |

---

## 5. Engineering rules restored (§2, §7 of the directive)

1. **No duplicate system** — reuse Asset / Project / Workflow / Graph / Review / Version / Model
   Center. No second asset, task or project system. Enforced by test wherever a new module is added.
2. **Truth first** — interface ≠ done, mock ≠ real, plan ≠ implementation, test count ≠ experience.
   Only the five status values; `NOT_RUN` is used rather than upgraded.
3. **Human workflow fit** — every feature must answer why the user needs it and whether it reduces
   work or learning cost; if it cannot, it is not built.
4. **AI assists, does not replace** — AI suggests / analyses / warns; the user decides, confirms,
   modifies. Directly why continuity is prompt-only.
5. **`main` frozen · no release · no history deletion · no fake tests · no lowered standard · no
   QingJian linkage · no NSFW** (Content Policy stays `RESERVED`).
6. **Permanent PROTECTED**: the 39 untracked baseline files, the 13 sibling clones, the shallow
   snapshot clone `D:\PoemSeed\AI-Novel-Studio`, and QingJian — observed only, never altered.

---

## 6. Next action

**Round 2 — Character & Scene Bible.** The directive's own rule is *"完成：进入 Round 2"*, and
Round 1 is verified complete above. Round 2 will follow the established loop (audit → highest-value
gap → minimal design → implement → test → docs → commit/push), reusing the owners rather than
creating a second system, with **File + real PostgreSQL + frontend tests + `tsc` + build** as the
verification bar now that the PG harness exists.
