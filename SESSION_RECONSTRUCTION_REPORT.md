# SESSION_RECONSTRUCTION_REPORT — AI-Novel-Studio V2 session bootstrap

**Date:** 2026-10-15 · **Purpose:** PART 0 SESSION BOOTSTRAP. This report restores engineering context only.
**It writes no product code, changes no source, and reclassifies nothing.**

**Status vocabulary:** `IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.
Nothing reserved, mocked, planned or merely collected is reported as complete.

---

## 0. The single most important finding: two clones exist, and only one is the development repo

| Path | What it actually is | Role |
| --- | --- | --- |
| `D:\PoemSeed` | **not a git repository.** A workspace container (Builds, Cache, Worktrees, Documents, Handoffs, LocalTakeover-*, QingJian, Runtime, Tools, Models, scripts). | session CWD only; **not** a dev directory |
| `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` | full clone, **412 commits**, branch `feature/v2-narrative-platform`, HEAD `a0dc246`, in sync with origin | **canonical development directory** |
| `D:\PoemSeed\AI-Novel-Studio` | **shallow snapshot clone: `rev-list --count HEAD` = 1**, no parent commit, **`git show-ref` = 0 refs** (`refs/heads` and `refs/tags` are empty directories; `.git/HEAD` holds a raw SHA), detached at `5af9bfc`. `.git` is 61 MB, so objects exist but no ref does. | **PROTECTED archive, not a work target** |

The Phase14 report names `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` as its worktree, and every recent
phase report lives at that clone's root. All further work is scoped there.

**PROTECTED — do not repair, reset, clean or re-clone `D:\PoemSeed\AI-Novel-Studio`.** Its missing refs are most
likely an artifact of the ACL-recovery event evidenced by `D:\PoemSeed-dsh-acl-recovery\` and `D:\PoemSeed\.runtime\dsh-acl-recovery\`.
Reconstructing refs is a destructive-risk action and is not authorized by this bootstrap.

---

## 1. Current HEAD / branch / remote / PR

| Check | Value |
| --- | --- |
| Dev directory | `D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014` |
| Branch | `feature/v2-narrative-platform` (upstream `origin/feature/v2-narrative-platform`, ahead 0 / behind 0) |
| **HEAD** | `a0dc246f4afb864d1b986e1c7c8e027afaae3ff3` — `docs(v2): Phase14 report and matrix append with honest per-priority statuses` |
| `origin/feature/v2-narrative-platform` | `a0dc246…` (identical to HEAD) |
| **`main` (remote)** | `fed2404c8e30b44061b7139dced45b7f3301601c` — **frozen, untouched**. Not present as a local ref in the dev clone (only the feature branch is fetched) — verified by `git ls-remote --heads`. |
| **PR #47** | `OPEN`, **`isDraft: true`**, base `main` ← head `feature/v2-narrative-platform`, head OID `a0dc246…` (= local HEAD), `mergeable: MERGEABLE`, `mergeStateStatus: UNSTABLE`, url https://github.com/1785235376-blip/AI-Novel-Studio/pull/47 |
| Tags | none |
| Stashes | none |
| Tracked dirty files | **0** |
| Untracked in dev clone | **39** — all baseline families: `docs/delivery/v2-development/phase6-*` receipts/logs (36 files), `.graphflow-cache/`, `graphflow-out/`. **PROTECTED, not cleaned, not committed.** |
| GitHub auth | `gh` authenticated as `1785235376-blip`, scopes `gist, read:org, repo, workflow` |

`main` is frozen and was never modified. PR #47 stays Draft. Nothing was merged, tagged, released or deployed.

---

## 2. Environment re-confirmation (`0.1`, `0.3`)

| Component | State | Evidence |
| --- | --- | --- |
| Git | `2.55.0.windows.2` | OK |
| Python | **3.11.9** — `C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe` | `fastapi, uvicorn, psycopg, sqlalchemy, httpx, pydantic_settings, reportlab, pypdf, jsonschema, pytest` **all import OK** |
| Second interpreter | `C:\AI-Novel-Studio-Python312\` exists (3.12 install, owns the running `pythonw.exe`) | present, not the dev interpreter |
| Backend import | `python -c "import app.main"` → **OK** | from the dev clone |
| Test collection | **14 502 tests collected in 16.75 s** | `python -m pytest --collect-only -q` |
| Backend baseline re-run | `tests/test_v2_camera_language.py` + `tests/test_phase8_shots.py` → **51 passed** in 2.83 s | re-run this session, not cited from a receipt |
| Node | `v22.14.0` | OK |
| pnpm | `12.4.2` | OK |
| Frontend deps | `frontend/node_modules` present, pnpm layout (`.pnpm`, `.modules.yaml`), lockfile `frontend/pnpm-lock.yaml` | **not reinstalled, lockfile untouched** |
| TypeScript | `pnpm exec tsc -b --force` → **exit 0** | run this session |
| .NET SDK | **8.0.424** = exact `global.json` pin (`rollForward: disable`) | match, no upgrade |
| PostgreSQL | **no Windows service, no `C:\Program Files\PostgreSQL`.** Binaries only at `D:\PoemSeed\Builds\studio-v2-host-5ed1cbee-20261011\Base\PostgreSQL\bin` (`postgres.exe`, `pg_ctl.exe`, …), **no data directory** | real-PG runs need an `initdb` of a separate cluster, as Phase10's portable-cluster path did |

**No dependency was upgraded, installed or removed. No lock file was changed.**

### 2.1 Host constraints that later phases must respect (verified now)

| Constraint | Fact |
| --- | --- |
| Port **8080** | held by pid **16292** `pythonw.exe` (`C:\AI-Novel-Studio-Python312\pythonw.exe`) — this is the **Strata local model server** observed/verified in Phase11–12. **Never stop or reconfigure it.** |
| Port **8100** | held by pid **11640** (unrelated ASUS `GearLink_KBService`) → the dev backend must bind **8110** |
| Port 8110 | free |
| Port 5432 | nothing listening |
| `bash` | **absent** → known `BLOCKED_EXTERNAL` test (`subprocess.run(["bash","-n"])`); must not be counted as a product defect |
| `ffmpeg` / `ffprobe` | present at `D:\ffmpeg\ffmpeg-8.1.2-essentials_build\bin` |
| GPU | 1 × RTX 5080, 16 303 MiB VRAM (15 977 MiB usable); the ~4.9 GiB in use belongs to the **separate** Strata server and must never be attributed to this app |
| Hosted CI | **`BLOCKED_ACCOUNT_PLATFORM`** — GitHub Actions billing lock, jobs start 0 steps. Never count as passing. |

---

## 3. Workspace protection (`0.4`) — PROTECTED register

**Nothing was cleaned, deleted, reset, checked out or moved.** `reset`, `clean`, `checkout main` were not run.

**Dev clone**: tracked dirty `0`; untracked `39` (baseline receipts/logs + graphflow caches) → **PROTECTED**.

**Other clones — observed only, never altered** (13 other clones under `D:\PoemSeed\Worktrees\`, each with its own
`.git`; they are independent clones, **not** registered git worktrees — `git worktree list` in each shows only itself):

| Clone | Branch | HEAD | Untracked |
| --- | --- | --- | --- |
| studio-v2-audio-editing-20261014 | `feature/v2-narrative-platform` | `a0dc246` | 39 |
| studio-v2-current-catalog-20261011 | `work/v2-current-catalog-20261011` | `4534bed` | 38 |
| studio-v2-director-storyboard-20261014 | `feature/v2-narrative-platform` | `c67a3c3` | 70 |
| studio-v2-host-manual-20261011 | `manual/v2-host-profile-20261011` | `5ed1cbe` | 0 |
| studio-v2-image-runtime-20261013 | `feature/v2-narrative-platform` | `a79b7f9` | 79 |
| studio-v2-native-diagnostics-20261011 | `work/v2-native-launch-diagnostics-20261011` | `5ed1cbe` | 2 |
| studio-v2-nonwav-20261013 | `feature/v2-narrative-platform` | `7276597` | 75 |
| studio-v2-phase3-pg-baseline-20261014 | `feature/v2-narrative-platform` | `a79b7f9` | 3 |
| studio-v2-phase4-backend-checks-20261014 | `feature/v2-narrative-platform` | `c67a3c3` | 39 |
| studio-v2-phase5-backend-checks-20261014 | `feature/v2-narrative-platform` | `8e4f028` | 28 |
| studio-v2-phase6-backend-checks-20261014 | `feature/v2-narrative-platform` | `a590bad` | 13 |
| studio-v2-production-expansion-20261013 | `feature/v2-narrative-platform` | `c911e54` | 28 |
| studio-v2-storyboard-video-20261014 | `feature/v2-narrative-platform` | `8e4f028` | 87 |
| studio-v2-video-pipeline-20261014 | `feature/v2-narrative-platform` | `a590bad` | 39 |

**QingJian**: `D:\PoemSeed\QingJian\QingJian-V1-Cloud-current-20261011`, branch `work/v1-stabilization-20261010`,
HEAD `a36231e`, **clean (0 dirty)**. **Read-only — no modification, no Interop development, no linkage.**

**Snapshot clone** `D:\PoemSeed\AI-Novel-Studio`: detached `5af9bfc`, no refs, untracked `build/` → **PROTECTED.**

**Stray artifact at the workspace root** (not in any repo): `D:\PoemSeed\productionDashboardMount.test.tsx`, **0 bytes**.
Recorded only; not touched. (An empty file, so it proves nothing about that test — the real test is
`frontend/src/production/productionDashboardMount.test.tsx`.)

---

## 4. Long-term governance rules restored (`0.5`)

1. **`main` is permanently frozen.** Verified still `fed2404c`. Do not merge, push or check out `main`.
2. **PR #47 stays Draft.** Verified `OPEN` / `isDraft: true`. No ready-for-review, no merge, no tag, no release, no deploy.
3. **No publication.**
4. **V1 frozen content is not modified.**
5. **QingJian stays paused** (read-only).
6. **`CONTENT_POLICY_FRAMEWORK` remains `RESERVED`** — no NSFW/Mature mode, no UI entry point, no content filter, no
   adult-model entry point. A policy is never a way to bypass a safety limit.
7. **Interfaces, mocks, plans and collected-test counts are never written up as completed capability.** Only the five
   status values above; `NOT_RUN` and `LOCAL_REQUIRED` are used rather than upgraded.
8. **Reuse the existing owners.** No second asset/project/task/model registry, no parallel scheduler, no forked DAG.
9. **PROTECTED files above are neither cleaned nor committed.**

---

## 5. Product identity (PART 1) and the production chain

The target is **not** a chat tool and **not** a simple AI generator. It is an AI-driven professional multimedia
narrative production workbench. The chain is:

**Text → Director → Storyboard → Image → Video → Audio → Timeline → Export**

Where that chain actually stands today: the **model-free segment is real and was executed end-to-end**; the
**model-dependent segment is blocked by missing local runtimes**. No mock or cloud result was substituted anywhere.

---

## 6. `IMPLEMENTED` — real, current, evidence-backed capability

| Capability | Evidence |
| --- | --- |
| **Real model-free production chain (Phase12, one real run)** | Through the app's own HTTP API against a real backend (`STORAGE_BACKEND=file`, `MOCK_PROVIDER=false`): Text (chapter `phase12:1` v1, `sha256 e7f4164a…`, Draft) → Director/Screenplay (revision 1, `edit_version 1→2`, scene pinned to source chapter v1, `DRAFT → APPROVED`) → shot plan (`edit_version 3→4`, `shot_revision 1`, APPROVED) → storyboard (`edit_version 4→5`, APPROVED) → approval (`edit_version 5→6`) → Export (job `51155d19-…`, `snapshot_id 935c5c78-…`, succeeded at 100, **real artefact 1 930 bytes**, `sha256 92ad87bc…`). Commit `f9cad2a`. |
| **Model Center runtime observation ladder ⓪–⑤** | `app/model_center/runtime_observation.py` — **observation-only**: no launch, install, download or child process (bounded TCP connect, owned process handle, Windows OS TCP table + `QueryFullProcessImageNameW` via `ctypes`). `NOT_OBSERVED → DISCOVERED → RUNTIME_AVAILABLE → REACHABLE → CAPABILITY_UNKNOWN → READY`; `READY` is unreachable from observation alone. An exhaustive test walks all 32 evidence combinations, another poisons `subprocess.Popen`, a third scans the module for child-process APIs. Commit `a9f03bb`. |
| **Runtime level ⑤ `READY` (Phase12, first time)** | One **real inference** against the already-running Strata server on 8080: `/health` → `service: strata`, model `qwen3.8-flash-next-iq3_xxs`, `max_context 131072`, no API key; capability `text→text` ⇒ `TEXT`; `/v1/models` answered; then one inference — **53.7 s**, `usage: prompt 57 / completion 8 / total 65`, `finish_reason: length` ⇒ level 5 with `inference_verified: true`. Caveats recorded: it is the **DSH-provided** server, was **already running**, and `content_preview` was empty (8-token cap). **Registration was not performed.** Commit `4e89f27`. |
| **GPU physical identity fix (Phase12)** | `host_hardware()` counted the single RTX 5080 **twice** (DXGI split one physical GPU into two adapters with different LUIDs because a virtual display adapter is attached). `_gpu_capability` fails closed unless it sees exactly one device, so the host reported **no GPU capability at all** (`gpu_vendor_id=None, vram_mib=0`) — which feeds VRAM budgets, hardware profiles and runtime admission. Fix collapses adapters **only** when the passive present-device inventory proves exactly one started device (the inventory returns a **tuple, not a set**, so two identical real GPUs stay two). No threshold lowered, nothing hardcoded. Live: GPUs **2 → 1**, capability **`(None, 0)` → `(NVIDIA uuid, 15 977 MiB)`**. Commit `82d1282`; `tests/test_v2_gpu_physical_identity.py`. |
| **Graph `schema_version` gate (Phase13)** | `validate_output_ports(..., schema_version=None)` audited: the default is a **deliberate legacy compatibility default** and it is **fail-closed**, so omitting the version can never grant a newer schema. The genuine gap: an **illegal** version never raised — `0`, `6`, `-1`, `99`, `1.0`, `"4"`, `True`, `object()` were silently validated as v1. `normalise_schema_version()` maps `None` → explicit `LEGACY_SCHEMA_VERSION` (1) and refuses any non-exact `int` outside `SUPPORTED_SCHEMA_VERSIONS = {1,2,3,4,5}` (`CREATIVE_GRAPH_SCHEMA_VERSION_INVALID`); the type check is exact because `True == 1`. `validate_output_ports` otherwise unchanged → old rows stay readable, nothing force-upgraded. Commit `5c100e9`; `tests/test_v2_graph_schema_version_gate.py`; **442 passed, 35 skipped, exit 0**. |
| **Camera-language vocabulary (Phase14 P1 core)** | `app/creative/camera_language.py` (commit `0e10c5d`) over the **existing** `DirectorNote` fields: shot sizes `EXTREME_WIDE · WIDE · MEDIUM · CLOSE_UP · EXTREME_CLOSE_UP`; movements `STATIC · PAN · TILT · DOLLY · TRACKING · CRANE · HANDHELD`; lenses `WIDE · NORMAL · TELEPHOTO · MACRO`; compositions `RULE_OF_THIRDS · CENTER · SYMMETRY · LEADING_LINES` + documented aliases. Values are **classified, never coerced** (`CANONICAL` / `LEGACY_PASSTHROUGH` preserved verbatim / `EMPTY`). `require_canonical()` is the strict gate and is **deliberately not wired** into the legacy write path. `project_camera()` is read-only. Re-run this session: **51 passed**. |
| **Authored shot-continuity contract (Phase14 P2 core)** | `continuity_warnings()` over **authored** `ShotContinuity`: `CONTINUITY_OUTFIT_CHANGED` / `CONTINUITY_CHARACTERS_CHANGED` / `CONTINUITY_ENVIRONMENT_CHANGED`. Obeys the owner's rule (**never inferred**): a value authored on one side only is *unknown*, not a break. A camera change is deliberately **not** a warning. Comparison ignores case and surrounding whitespace but not internal spacing. |
| **Custom-HTTP local registration descriptor (Phase11)** | `custom_http_local_registration()` only **prepares** a descriptor for the existing owner-declared route. Fail-closed: `user_confirmed` must be literally `True`, endpoint must be numeric loopback, observation must already be `REACHABLE`, capability must be one of the ten real values. States `generates_tasks=false` / `auto_enabled=false`. Nothing registered, enabled, launched or scheduled. Commit `2be9e42`. |
| **Capability vocabularies pinned as invariants (Phase11)** | Task vocabulary (`TEXT_GENERATION`/`IMAGE_GENERATION`/`VIDEO_GENERATION`) is **disjoint** from the ten model capabilities and maps one-directionally; `ASR` is in neither (only Whisper's graph node binding); Whisper = runtime `WHISPER_CPP` / capability `AUDIO`; FLUX = `IMAGE` under `COMFYUI`. Recorded conflation hazard: `ProviderFamily` and `RuntimeType` share exactly two spellings (`COMFYUI`, `LLAMA_CPP`) while `LM_STUDIO` has no runtime type. Commit `2be9e42`. |
| **Real-browser acceptance 8/8 (Phase11, re-executed)** | System Microsoft Edge (`channel msedge`, nothing downloaded), real `uvicorn app.main:app` (`STORAGE_BACKEND=file`, `narrative_production_v2`) on 8110, real Vite on `http://127.0.0.1:5173`, Playwright: **8 passed (14.4 s), exit 0, retries 0** — START, TASKS, ASSETS, PRODUCTION, MODEL CENTER, DELIVERY, zh-CN smoke, keyboard focus. Both services stopped afterwards. Commit `0c5128b`. |
| **UX-PRODUCT batches 1–5 (frontend source)** | 9 UX directories, **125 new files**: `onboarding/`, `taskcenter/`, `assetbrowser/`, `canvasops/`, `storyboard/`, `nle/`, `modelcenter/`, `guide/`, `delivery/`. Mounted incrementally into the existing shell (`START`/`TASKS`/`ASSETS` views, canvas toolbar, shot workspace, `StudioTimelineEditor`, studio `PRODUCTION`). Verification is **component/contract level** (`frontend` 268 tests; `ux-product-{types,build,tokens,seam}-r4` PASS ×4, build 2 130 modules; File 48 passed/42 skipped; real-PG 14 passed/8 skipped). `docs/v2/ux-product/STATUS.md` |
| **`CONTENT_POLICY_FRAMEWORK`** | **`RESERVED`** — `app/creative/content_policy.py`, fields/interfaces/compatibility tests only, dual-backend (File + real PG). Unchanged. |
| **Frozen boundaries** | V1 freeze intact; `F00 INTEGRATED` + **39 PARTIAL** and the independent-review `BLOCKED` classification unchanged; M4 `PARTIAL`; M5–M9 `LOCAL_REQUIRED`; PoemSeed Local Interop 1.0 protocol semantics retained. |

---

## 7. `PARTIAL` — real implementation exists, named boundary remains

**Baseline marker set (M0, unchanged):** `F00 INTEGRATED` + **39 PARTIAL** rows on the audited `4350a61` inventory;
independent review **BLOCKED**. Milestone gates: `GATE-M1` PARTIAL, `GATE-M3` PARTIAL, **`GATE-M4` PARTIAL**,
`GATE-M5`–`GATE-M7` PARTIAL, `GATE-M8` PARTIAL, `GATE-M10` PARTIAL; `GATE-M0` EXISTS, `GATE-M2`/`GATE-M9`/`GATE-M11` MISSING.

The highest-value `PARTIAL` rows, with their exact remaining boundary:

| Item | Remaining boundary |
| --- | --- |
| **`GATE-M4` / M4** — text, source-aware adaptation, generic scripts | Actual **model-dependent** gates remain `LOCAL_REQUIRED`/`NOT_RUN`. The model-free chain is real (§6); the real-model quality/memory benchmark is not. |
| **`CORE-01` §1.1** neutral Studio entry | Project/entry UX is still novel-oriented; blank neutral image path is M1. Phase7 added a **read-only** workflow projection (`entry_kind` always `NEUTRAL_STUDIO`, `start_action` → existing `POST /api/experimental/projects`, `requires_original_host_session=true`) that reports honestly and grants nothing. Full neutral entry UX + browser acceptance **PENDING**. |
| **`CORE-03`/`CORE-04`** mutable creative intent, editable preset | Phase7 added `POST /api/projects/{nid}/studio/production/workflow/intent` reusing the original CAS and retained history (cap 200), with `409 PRODUCTION_WORKFLOW_INTENT_CONFLICT` / `422 PRODUCTION_WORKFLOW_INTENT_INVALID`. Intent/preset stay **display preferences** (`intent_is_permission=false`). Free intent→layout mapping still MISSING; browser acceptance PENDING. |
| **`CORE-20`/`CORE-21`** relationship taxonomy | Existing parent DAG + provenance cover derivation; the full named relation taxonomy (with reason/status) is not implemented. |
| **Phase13 P0 gap 1 — frontend port-table duplication** | Audited precisely and **not migrated**. The duplication is **deliberate cross-pinning, not drift**: `app/creative/graph_models.py:753` already emits schema-resolved ports (backend is already authoritative), while `frontend/src/creative/studioGraphClient.ts:57-86` re-derives them and `graphDraft.ts:8-10` patches the same three cases, and `catalogDefinition` (`studioGraphClient.ts:421`) cross-checks the server against its own table — which is why drift surfaces as a whole-catalog load failure. The correct convergence (one frontend projection preferring server ports, keeping every structural check) was **not implemented**; the phase rule "do not delete port validation" rules out just deleting it. |
| **Real media pipeline** | `PARTIAL`, unchanged from Phase12. Image / Video / Audio are `BLOCKED_LOCAL_RUNTIME` (no listener on ComfyUI 8188 or the others; Whisper host not configured); Timeline depends on their assets. Nothing substituted. |
| **Phase14 P1 — Advanced Director Studio** | Vocabulary core delivered; **not done:** the Director Workspace surface (Story Goal / Visual Direction / Mood / Genre / Reference → *Director Intent*), scene- and performance-direction projections, any frontend exposure, write-path enforcement, legacy value-migration decision. |
| **Phase14 P2 — Storyboard Pro** | `continuity_warnings()` delivered; **not done:** the Shot Card (shot number, duration, camera, lens, movement, character, action, emotion, lighting, audio), storyboard sequence preview, approval-surface integration. |
| **Windows RC preparation** | `WINDOWS_RC_EXECUTION_GUIDE.md` completeness matrix **IMPLEMENTED (preparation)**; **execution `NOT_RUN`**. Only the dev backend invocation (`PASS`, 8110, `/docs` 200, cleanly stopped) and the Phase10 portable-cluster PG path (`PASS`, `phase10-a1-r4`) are verified; `ENABLE_PACKAGED_RUNTIME=false`, so the packaged path was never exercised. |
| **Release documentation** | README Phase11 block, `docs/troubleshooting.md` (8 verified entries), `WINDOWS_RC_EXECUTION_GUIDE.md`, `MEDIA_PIPELINE_RC_CHECKLIST.md`. Install/uninstall and installer documentation **do not exist** and are not claimed. |
| **Media-chain contract preflight** | `86 passed, 79 skipped, 1 failed` — the single failure is `BLOCKED_EXTERNAL` (`bash` absent on this host), not a product defect. The 79 skips are **not** counted as passes. |
| **Browser/visual acceptance of the 4 new UX surfaces** | Component-level (jsdom) only for the newest surfaces; Playwright visual/geometry checks remain **`NOT_RUN`**. |
| **UX-PRODUCT second status table** | `STATUS.md` §2 still lists UX-05…UX-09 as `NOT_STARTED`/`NOT_RUN` in that *historical* table while §1 records all five batches complete — the two tables are from different points in time. The live frontend tree is authoritative; the stale table must be corrected in a later docs pass, not silently rewritten. |

---

## 8. `LOCAL_REQUIRED` — cannot be substituted by cloud or mock evidence

| Item | Why it needs this host |
| --- | --- |
| `MODEL-18` §6.2 | 8 GB / 12 GB / RTX 5080 16 GB + 64 GB performance evidence — cloud/mock cannot validate the target devices |
| `GATE-M12`, `WIN-01`…`WIN-07` | clean install/start/uninstall/upgrade/IME; trusted discovery on the 16 GB GPU; 8/12/16 GB resource limits; native recovery & multi-track reopen; two-application QingJian window behaviour; package SHA verification |
| **Live local runtime end-to-end (app-native)** | Verification is `IMPLEMENTED` (level ⑤ reached with real inference), but **no app-native runtime is registered**, so the app cannot route work to one. Deliberately **not** upgraded. |
| M5–M9 acceptance | original ordered M4 → M9 gate sequence |

---

## 9. `BLOCKED` — do not execute merely to improve a status

| Item | Blocking condition |
| --- | --- |
| **Local runtime registration closure** | `POST /api/model-center/local-ai/runtimes` → **HTTP 401 `SESSION_REQUIRED`** against a real backend. `app/model_center/discovery_api.py:50-68`: `require_session` is a **router-level dependency** raising unless the injected host authority reports `can_mutate`. This is an **intentional security control, not a defect** — obtaining or fabricating the session is a bypass and is forbidden. Receipt `docs/delivery/v2-development/phase13-runtime-registration-probe.json`. |
| **Task routing to a local runtime** | `NOT_RUN` — depends on registration. |
| **Hosted CI** | `BLOCKED_ACCOUNT_PLATFORM` — Actions billing lock, jobs start 0 steps. Never counted as passing. |
| **`DOC-03`** final exact-source RC candidate / install-upgrade / package manifest | Not ready before the applicable implementation and acceptance; release needs separate approval. |
| **Appendix A expansions** | `BLOCKED`/deferred: distributed remote rendering, model-quality ranking fleets, advanced realtime coauthoring, professional pixel compositing, complex automatic cinematography, complete 3D camera simulation, Resolve-class grading/VFX, full DCC, advanced active research, enterprise sync, automatic online submission. Not to be implemented as a parallel core. |
| **Independent review** | historical `BLOCKED`, untouched. |
| **`bash`-dependent check** | `BLOCKED_EXTERNAL` on this host. |

---

## 10. `NOT_RUN` — Phase14's unfinished priorities (the next capability backlog)

Phase14 asked for seven priorities. **Two cores were delivered; five priorities and the UX mode split are `NOT_RUN`:**

| Priority | Status | What is absent |
| --- | --- | --- |
| P3 Prompt Studio | `NOT_RUN` | No prompt asset owner, no prompt version chain (`v1`/`v2`), no parameters block (negative prompt, model, sampler, seed, references, output), no Prompt↔Asset/Shot/Character/Scene binding. Nothing was created. |
| P4 Character / Scene Consistency | `NOT_RUN` | No character profile (appearance, age range, wardrobe, palette, traits, references), no scene profile (environment, building, material, lighting, weather), no generation-time reference injection. |
| P5 Asset Relationship Graph | `NOT_RUN` | The read-only relationship surface is unchanged from the Phase10 audit (seven declared kinds). The full-chain projection Character → Images → Shots → Videos → Timeline Clips with `USED_IN`/`DERIVED_FROM`/`REFERENCES`/`VERSION_OF` was **not** added. |
| P6 Timeline professional layer | `NOT_RUN` | No colour-adjustment parameter layer (brightness/contrast/exposure/saturation/white balance/LUT), no clip inspector, no markers, no trim/slip/ripple/transition preparation. Per the brief these are parameter systems only — nothing was faked. |
| P7 Audio professional layer | `NOT_RUN` | No track/clip/volume/fade/sync layer, no voice/music/SFX reservation. |
| Professional vs simplified UX mode | `NOT_RUN` | No mode split, so complex parameters are not yet hidden from ordinary users. |

Also `NOT_RUN`: Windows clean-machine execution, packaged DesktopHost, GPU CUDA execution / model load / image /
video generation through the app, export packaging, and any full CI run.

**`IMPORTANT`:** the Phase14 report itself concludes the phase was **not completed** and recommends re-running it as
**per-priority phases** rather than compressing seven phase-sized bodies of work into one pass. That recommendation
matches the directive's Phase14-A…F split.

---

## 11. Release-candidate conclusion (unchanged)

**`NOT ESTABLISHED`.** One pre-release engineering gap is fixed and tested; the other is precisely audited but not
migrated; registration is blocked by an intentional authority gate; the media chain's model-dependent steps are
blocked by missing local runtimes; and install/uninstall, the packaged DesktopHost trusted session, export packaging,
a full CI run and a clean-machine pass all remain `NOT_RUN`.

**Phase13 and Phase14 both left this conclusion unchanged.**

---

## 12. Next-phase plan

### 12.1 Binding constraints before any Phase14-A work starts

1. **Frontend work must follow `docs/ui/design_system.md`** and the **ModuleWorkspace / AppShell** contract; reuse
   design tokens and existing primitives; invent no colours or spacing; duplicate no component; preserve the shared
   NOVEL / IMAGE / VIDEO shell and V0.5.7 collaboration/conflict/revision/fail-closed behaviour. Protected surfaces are
   listed in `docs/ui/protected_ui_surfaces.md`; any system-level change needs a `DESIGN SYSTEM CHANGE REQUEST`.
   (`AGENTS.md` requires loading the `$ai-novel-studio-ui` skill; **that skill is not present in this session's skill
   catalog**, so the design-system documents must be read directly instead — verify the real docs rather than assume.)
2. **Reuse the existing owners.** `DirectorNote` (`app/creative/models.py:62`) already carries `shot_size`,
   `camera_angle`, `camera_motion`, `composition`, `lens`, `lighting`, `color_palette`, `material`, `transition`,
   `emotion`, `pacing`, `performance`, `blocking`, `character_state`, `performances`, `duration_seconds`;
   `ShotContinuity` (`models.py:111`) already carries `previous_shot_id`, `next_shot_id`, `characters`, `outfit`,
   `environment`, `camera`. Extend these; fork nothing.
3. **Backward compatibility is binding:** classify, never coerce. Old rows and old clients keep working; no enforcement
   wired into a legacy write path.
4. **Verify per phase**, not per batch: File + real PostgreSQL (requires an `initdb` cluster from the packaged binaries)
   + frontend vitest + `tsc -b` + build, with source-bound receipts and `sources_changed_during_check=false`.
5. **Do not disturb the running Strata server on 8080**; use port 8110 for the dev backend; 8100 is taken.

### 12.2 The directive's Phase14-A…F mapped onto the actual backlog

| Directive phase | Backlog it closes | Builds on |
| --- | --- | --- |
| **Phase14-A Professional Director System** (Director Workspace: Visual Goal, Mood, Genre, Camera Language, Lighting, Color Direction, Performance Direction; Shot Card: shot ID, duration, camera, lens, movement, composition, lighting, character, action, emotion, audio; Continuity Panel: costume/character/scene/time — **warn only, never auto-modify**) | Phase14 P1 finish **+** P2 finish | `app/creative/camera_language.py`, `continuity_warnings()`, `DirectorNote`, `ShotContinuity`, `productionWorkflow` frontend contract |
| Phase14-B Character & Scene Bible | Phase14 P4 | asset owner, `DirectorNote`, existing character/scene context |
| Phase14-C Prompt Studio | Phase14 P3 | existing asset/version owner |
| Phase14-D Asset Intelligence Graph | Phase14 P5 | Phase10 seven declared relationship kinds, `ProductionLineageService` |
| Phase14-E Professional Timeline (Inspector, colour parameters as a **parameter system only** — no fabricated GPU grading, markers) | Phase14 P6 | `VideoAssemblyService`, `SubtitleTimelineService`, `ProductionTimeline` |
| Phase14-F Audio Professional Layer | Phase14 P7 | `audio_providers`, `audio_production_store`, `AudiobookService`, `voice_direction` |

### 12.3 Recommended immediate next phase — **Phase14-A**

Rationale: it is the highest-value open capability, it is already half-built (vocabulary + continuity contract are
delivered and tested), and the directive's production chain (**Text → Director → Storyboard → …**) has the Director
stage as its first professional gap. Scope is deliberately one phase:

- **Backend**: Director Intent contract over the existing `DirectorNote` fields (visual goal, mood, genre, lighting,
  colour direction, performance direction) — additive, read-only projections first, with an **opt-in** strict gate for
  new professional writes only; plus a **Shot Card** projection using fields that already exist.
- **Backend**: surface `continuity_warnings()` through a bounded read-only endpoint (costume / character / scene / time)
  that **only warns** and mutates nothing.
- **Frontend**: one Director Workspace surface + Shot Card + Continuity Panel, consuming existing tokens/AppShell/
  ModuleWorkspace per the design system; professional-vs-simplified parameter visibility honours the existing UX-mode owner.
- **Verification**: File + real PG + vitest + `tsc -b` + build, source-bound receipts; legacy suites re-run as the
  no-regression evidence (`test_phase8_shots`, `test_r4_director`, `test_v2_creative_workflows`,
  `test_v2_camera_language`).
- **Then**: Phase Report + Feature Matrix append-only section + commit + push; `main` untouched, PR #47 stays Draft.

### 12.4 Tracked separately (RC gates, not capability)

Recorded from Phase13 §11 and Phase12 §5 so they are not lost:

1. Land the **frontend port projection** (single source, prefer server-resolved ports, keep every structural check),
   verified with `pnpm exec tsc -b --force` plus the frontend graph tests.
2. Register a runtime **the supported way** — through the host-session authority that `SESSION_REQUIRED` protects. This
   is the only route that moves "live local runtime end-to-end" off `LOCAL_REQUIRED`.
3. Close the Phase12 client gap: **no readable screenplay `edit_version`** (`GET` of one screenplay → 404;
   `GET …/shots` → 405), forcing clients to read it from an export job's `source_versions`.
4. Run the media chain's model-dependent steps once an image/video/audio runtime exists, filling the
   `BLOCKED_LOCAL_RUNTIME` rows with real artefacts and digests.
5. Clean-machine Windows pass → export packaging → full-CI attempt or an explicit decision to stay
   `BLOCKED_ACCOUNT_PLATFORM`.

---

## 13. Bootstrap exit criteria

| Requirement | State |
| --- | --- |
| Environment re-confirmed (`0.1`) | **DONE** — §2, §2.1 |
| Repo read in the mandated order (`0.2`) | **DONE** — Feature Matrix (1 541 lines, incl. §23–29 gates, §30 evidence catalogue, Phase10–14 appends), Phase12, Phase13, Phase14 reports, Architecture (608 lines, incl. the authority map), `docs/v2/` (60 files) + `docs/v2/README.md` + `ux-product/STATUS.md`, PR #47 |
| Session reconstruction report (`0.2`) | **this file** |
| Engineering environment recovered (`0.3`) | **DONE** — no upgrade, no lock-file change, no reinstall |
| Workspace protected and recorded (`0.4`) | **DONE** — §3; nothing cleaned, reset or moved |
| Long-term rules restored (`0.5`) | **DONE** — §4 |
| No code written | **TRUE** — no product source, test or config file was created or modified by this bootstrap |

**Awaiting the go-ahead to start Phase14-A.** No development was performed.
