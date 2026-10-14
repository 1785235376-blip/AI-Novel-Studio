# PHASE11_RC_GATE_CLOSURE_REPORT — Render Candidate Gate Closure

**Date:** 2026-10-14 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline:** `5179e56` (local = remote at phase start). `main` = `fed2404c`, never touched.
**PR #47:** `OPEN` / `isDraft: true`. No merge, no release, no tag.

**Status vocabulary — only these five values are used in §7:**
`IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.
`BLOCKED_EXTERNAL` is used in prose for a host-caused failure that is demonstrably not a product
defect. Nothing was upgraded because a previous report existed.

> Phase11 is a **validation and boundary-closure** phase, not a feature phase. Its product is
> evidence, two checklists and report. It did not attempt to raise the feature count.

---

## 1. Baseline re-verified by command

| Check | Result |
| --- | --- |
| `git rev-parse --short HEAD` | `5179e56`, branch `feature/v2-narrative-platform` |
| `git ls-remote origin …` | feature `5179e56cf1f2…`, **main `fed2404c`** (untouched) |
| `gh pr view 47 --json state,isDraft,headRefOid` | `OPEN`, draft, `5179e56cf1f2…` |
| tracked files dirty | `0` |
| untracked | `39` — all protected baseline families (`phase6-*`, `catalog-f19d*`, `.graphflow-cache/`, `graphflow-out/`) |

Per §二 the reports and documents were re-read rather than trusted: the matrix, the Phase10 and
Phase9 reports, the README and `docs/v2/`. Where a Phase9 statement had since been overtaken —
the identity of the service on 8080 — it is corrected in §2 and in `docs/troubleshooting.md`,
with the original statement left in place as history.

**Also recorded:** `hindsight_search_knowledge_pages` failed with an API error throughout this
phase, so no memory-page evidence informed these conclusions; everything below rests on
first-hand execution.

---

## 2. P0 — Model runtime validation (brief §4–§7)

### 2.1 Level ② now exists, and that is the phase's real closure

Phase10 established that discovery observed levels ① (file exists), ③ (endpoint answers) and ④
(model recognisable), refused ⑤ by design, and **never observed level ② (does a runtime process
exist)** — so `DISCOVERED` only ever meant "the endpoint did not answer".

`app/model_center/runtime_observation.py` (commit `a9f03bb`) closes that gap as an
**observation-only** surface. It launches nothing, installs nothing, downloads nothing and
creates no child process. Its channels are a bounded TCP connect, the app's own owned process
handle, and — on Windows — a read of the OS TCP table plus `QueryFullProcessImageNameW` through
`ctypes` (syscalls in this process, not a subprocess).

The ladder is monotonic and fail-closed:

| Level | Status | Evidence required |
| --- | --- | --- |
| 0 | `NOT_OBSERVED` | nothing at all — added to the five named statuses so an absent runtime is not dressed up as `DISCOVERED` |
| 1 | `DISCOVERED` | a model artifact / configured file exists |
| 2 | `RUNTIME_AVAILABLE` | an owned process handle is alive **or** something owns the configured loopback port |
| 3 | `REACHABLE` | the endpoint answered our protocol probe (a handshake is only level ②) |
| 4 | `CAPABILITY_UNKNOWN` | a model was recognised but its capability is not verified |
| 5 | `READY` | **real inference verified elsewhere** — unreachable from observation |

Three tests hold that boundary: an exhaustive walk of all 32 combinations of observable evidence
asserting `READY` is never produced; a test driving the real code path with `subprocess.Popen`
poisoned; and a scan asserting the module references no child-process API. A fourth asserts an
absent runtime reports `NOT_OBSERVED`, not `DISCOVERED`.

**Level ② deliberately does not touch the scan report.** The Phase10 pin
(`tests/test_v2_discovery_runtime_levels.py`) asserts that report carries no process fact, so
observation returns its own immutable `RuntimeObservation` instead of mutating discovery state.

### 2.2 Live result on this host

Real probes, no simulation (`phase11-live-observation.json`):

| Target | Result |
| --- | --- |
| Ollama `127.0.0.1:11434` | **`NOT_OBSERVED` (level 0)** — no listener at all |
| LM Studio `127.0.0.1:1234` | **`NOT_OBSERVED` (level 0)** — no listener at all |
| ComfyUI `127.0.0.1:8188` | **`NOT_OBSERVED` (level 0)** — no listener at all |
| custom HTTP local `127.0.0.1:8080` | **`CAPABILITY_UNKNOWN` (level 4)** |

For 8080 the layer resolved, in one pass: listener present; **owner identified as pid `16292`,
image `C:\AI-Novel-Studio-Python312\pythonw.exe`, `identity_verified: true`**; protocol answered
on `/v1/models`; model `qwen3.8-flash-next-iq3_xxs` recognised; **inference not observed** — so
level 4, never `READY`. This is the level-② evidence that Phase9 could not produce, and it
independently reproduces (through our own code, not PowerShell) the identity Phase10 inferred.

**Strata was observed, never bound and never registered.** Per brief §6 the custom-HTTP local
path is gated: `custom_http_local_registration()` only *prepares* a descriptor for the existing
owner-declared route, refuses unless `user_confirmed` is literally `True`, requires a numeric
loopback endpoint, requires the observation to be at least `REACHABLE`, and accepts a capability
name only from the ten real `Capability` values. The descriptor records endpoint, model and
capability and states `generates_tasks=False`, `auto_enabled=False`; it holds no center,
lifecycle, task or job reference and no `start()`.

### 2.3 Capability corrections (brief §7)

Verified against source and now pinned by invariants (`tests/test_v2_capability_vocabulary_layers.py`):

- The **task vocabulary** (`TEXT_GENERATION` / `IMAGE_GENERATION` / `VIDEO_GENERATION`) is
  **disjoint** from the ten model capabilities and maps down onto them one-directionally
  (`TASK_CAPABILITY`). `IMAGE_GENERATION` is a task name; FLUX is registered as `Capability.IMAGE`.
- **`ASR` belongs to neither vocabulary.** It is only Whisper's graph node binding
  (`whisper_runtime.py`); Whisper is runtime `WHISPER_CPP` with model capability `AUDIO`, and
  `domain.py` contains no `ASR` at all.
- A **new finding** recorded while writing the invariants: `ProviderFamily` and `RuntimeType` are
  different vocabularies that nevertheless share **exactly two** spellings — `COMFYUI` and
  `LLAMA_CPP` — while `LM_STUDIO` deliberately has no runtime type because it is reached as
  `OPENAI_COMPATIBLE_LOCAL`. The test asserts the overlap is exactly those two, so a future shared
  name becomes a deliberate decision rather than an accident.

Evidence: `phase11-runtime-observation.json` (**50 passed**, exit 0);
`phase11-observation-and-capability-r2.json` (**70 passed**, exit 0). The intermediate FAIL
receipt `phase11-observation-and-capability.json` is committed unchanged: the failure was **my
own incorrect assumption** that only `COMFYUI` was a shared spelling — corrected to assert the
true two-name overlap, not papered over.

---

## 3. P1 — Browser / backend acceptance (brief §8)

Phase9's 8/8 was carried as history through Phase10 without re-execution. This phase **re-ran it
on the current head** (commit `0c5128b`):

```
corepack pnpm exec playwright test --config playwright.studio-release.config.ts
→ 8 passed (14.4s), exit 0, retries 0
```

| Aspect | Value |
| --- | --- |
| Browser | system **Microsoft Edge** via `channel: msedge` — nothing downloaded, no `playwright install` |
| Backend | real `uvicorn app.main:app`, `STORAGE_BACKEND=file`, `EXPERIMENTAL_FEATURES=narrative_production_v2`, `MOCK_PROVIDER=true`, `CREDENTIAL_VAULT_BACKEND=memory` |
| Frontend | real Vite with `V061_API_URL=http://127.0.0.1:8110` |
| DOM | the real browser — **not** jsdom |
| Covered | START, TASKS, ASSETS, PRODUCTION, MODEL CENTER (on demand), DELIVERY (on demand), zh-CN smoke, keyboard focus |

**Ports had to move, and this is a durable correction:** 8000 remains in a Windows excluded range
(held by PID 4) and **8100 — the port Phase9 used — is now occupied by the unrelated ASUS
`GearLink_KBService.exe`**, so the backend ran on `8110`. Vite bound IPv4 because `--host
127.0.0.1` was passed, which is why the base URL is `http://127.0.0.1:5173` rather than the
`localhost` form Phase9 needed; the binding was verified before the run. Both services were
stopped afterwards and 5173/8110 are free.

Receipt: `docs/delivery/v2-development/phase11-browser-acceptance.{json,log}`.

**Honest limit:** the eight assertions cover surface landmarks, authored Chinese copy and keyboard
reachability — **not** full data round-trips. A PostgreSQL-backed browser run remains
`BLOCKED_EXTERNAL` (the repository's `frontend/playwright.config.ts` hardcodes a missing
`../.venv` interpreter and port 8000).

---

## 4. P2 — Media pipeline validation preparation (brief §9)

**No generation, render or export was run.** `MEDIA_PIPELINE_RC_CHECKLIST.md` (commit `3f97b34`)
is the executable companion to the two documents that already existed — the Phase9 plan owns
scope, the Phase10 record table owns the checks, and this checklist adds the real owner module per
step, the real identity fields, the exact command and verified environment facts. Every execution
row is `NOT_RUN`.

The identity fields are read from `app/creative/production_execution_models.py`, not invented:
`StoryboardShotPin.shot_version`/`.shot_digest`, `StoryboardDocumentSnapshot.version`/`.digest`,
`MediaCreate.reviewed_preview_digest`, `MediaJobAction.expected_version`/`.expected_request_digest`,
the `expected_version` + `reviewed_*_digest` pairs on `TimelineRender`/`TimelineEdit`/
`TimelineExport`/restore, and `TimelineAssetSnapshot.version`/`.digest`. A row may only be `PASS`
when the recorded digest and version match what the request carried — "the file exists" is not the
check.

A **contract preflight** was run so that a later execution failure can be attributed to execution
rather than to a missing contract:

```
86 passed, 79 skipped, 1 failed in 78.87s, exit 1
receipt: docs/delivery/v2-development/phase11-media-chain-contract-preflight.json
```

The single failure is **`BLOCKED_EXTERNAL`, not a product defect**:
`test_media_job_is_explicit_bounded_and_has_real_official_prerequisites` runs
`subprocess.run(["bash", "-n"])` and this host has **no `bash`** (`Get-Command bash` → not on
PATH), producing `FileNotFoundError [WinError 2]`. It is the same POSIX-only class as the
pre-existing `tests/test_v2_media_prerequisites.py` failures. **`ffmpeg` and `ffprobe` are
present** (`D:\ffmpeg\ffmpeg-8.1.2-essentials_build\bin`), so the media tooling prerequisite is
satisfied even though this test cannot run here. The 79 skips are recorded as skips and are **not**
counted as passes.

---

## 5. P3 — Windows / GPU RC preparation (brief §10)

`WINDOWS_GPU_RC_CHECKLIST.md` (commit `2066f13`) records measured facts rather than assumptions
(receipt `phase11-host-inventory.json`):

| Fact | Value |
| --- | --- |
| OS / CPU / RAM | Windows 11 Pro `10.0.26100` build 26100, AMD64, 20 logical CPUs, 63.6 GiB |
| GPU | **1 × NVIDIA GeForce RTX 5080** (`GPU-b277f34d-…`), driver `591.74`, compute `12.0` |
| VRAM | **16 303 MiB total, 4 923 MiB in use** at measurement |
| App CUDA / DirectML verdict | `COMPONENT_FOUND_NOT_VERIFIED`, `inference_verified: false` |
| Toolchain | node `v22.14.0`, pnpm via corepack, portable PostgreSQL `16.15`, `ffmpeg`/`ffprobe` present, **`bash` absent** |

Windows items: **W3 dev backend = `PASS`** (started, `/docs` 200, stopped cleanly) and **W5
portable-cluster PostgreSQL = `PASS`** (Phase10 `phase10-a1-r4`: fresh DB, empty before
migrations, all 20 migrations applied, `server_stop: stopped`). **W1 clean install, W2 launcher,
W4 DesktopHost and W6 recovery are `NOT_RUN`** — `ENABLE_PACKAGED_RUNTIME=false` in the verified
runner environment, so the packaged path was never exercised.

GPU items: **G2 VRAM measurement = measured**, but **G1 CUDA execution, G3 model load, G4 image
generation and G5 video generation are all `NOT_RUN`**.

### Findings recorded and deliberately not changed

**F1 — the passive inventory double-counts the GPU.** `nvidia-smi -L` reports exactly **one**
RTX 5080, but `host_hardware()` returns **two** entries with identical vendor, name and
`dedicated_vram_bytes` (`16 753 098 752` each), so any GPU count or VRAM sum would double. Left
unchanged on purpose: hardware reporting feeds hardware profiles and VRAM checks, and altering it
is a functional change that needs a decision plus a test. Phase11 is a validation phase.

**F2 — the app's CUDA verdict is honest and must stay that way.** `COMPONENT_FOUND_NOT_VERIFIED`
with `inference_verified: false` correctly refuses to convert a detected component into a working
capability, matching the level-4-is-not-level-5 discipline of §2.

**F3 — VRAM is not free VRAM.** The 4 923 MiB in use belongs to the **separate** Strata server and
must never be attributed to this app; GPU acceptance must record free VRAM at run time.

---

## 6. P4 — Documentation cleanup (brief §13)

- `docs/troubleshooting.md` — eight verified operational entries appended: 8100 occupied by the
  ASUS service; 8080's identity now proven as Strata; `bash` absent (with the note that
  `ffmpeg`/`ffprobe` *are* present); the four PostgreSQL-runner traps; Vite IPv4-vs-IPv6 binding;
  "file exists ≠ runtime ready"; the duplicate GPU count; and VRAM already partly in use.
- `README.md` — a verified Phase11 block: the level-② observation layer and its ladder, the live
  host results, the user-confirmation gate, the re-run browser acceptance, the two checklists, and
  the RC conclusion.
- `AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md` — an append-only Phase11 section; **no historical row,
  status or evidence ID was edited**.
- Install/uninstall, packaging and the installer flow remain `NOT_RUN` and are **not** described
  as existing anywhere.

---

## 7. Status table

| Item | Status | Evidence |
| --- | --- | --- |
| Baseline integrity (`5179e56`, `main` `fed2404c`, PR #47 draft) | `IMPLEMENTED` | §1 commands; nothing merged, released or tagged |
| Model Center level ② observation layer | `IMPLEMENTED` | `a9f03bb`; 50 passed + 70 passed, exit 0 |
| Capability vocabulary separation | `IMPLEMENTED` | `2be9e42`; invariant tests incl. the two-name overlap finding |
| Custom HTTP local registration gate | `IMPLEMENTED` | `2be9e42`; user-confirmed only, prepares but never registers |
| Real browser acceptance on current head | `IMPLEMENTED` | `0c5128b`; **8 passed / 14.4 s / exit 0** in system Edge |
| Media pipeline real execution | `NOT_RUN` | contract preflight 86/79/1 (`BLOCKED_EXTERNAL`); artefacts never produced |
| Windows clean install / packaged runtime / recovery | `NOT_RUN` | `WINDOWS_GPU_RC_CHECKLIST.md` W1/W2/W4/W6 |
| Dev backend start & portable PostgreSQL | `IMPLEMENTED` | `/docs` 200 and stopped cleanly; Phase10 `phase10-a1-r4` |
| GPU CUDA execution / model load / image / video | `NOT_RUN` | G1/G3/G4/G5 |
| GPU VRAM measurement | `PARTIAL` | measured (16 303 / 4 923 MiB) but no load-time behaviour; F1 duplicate record open |
| Live local runtime end-to-end | `LOCAL_REQUIRED` | no app-usable local runtime exists; `READY` never reached |
| Release documentation | `PARTIAL` | README + troubleshooting updated; install docs still absent |
| Hosted CI | `BLOCKED` | `BLOCKED_ACCOUNT_PLATFORM` — billing lock, never started, never counted as passing |
| `CONTENT_POLICY_FRAMEWORK` | `RESERVED` | unchanged; no NSFW/Mature, no UI entry, no model filter |

---

## 8. Release-candidate conclusion

**`NOT ESTABLISHED`.** Phase11 closed the level-② gap and re-verifed the browser acceptance on the
current head, but a release candidate requires: a real install and uninstall on a clean Windows
machine, the packaged DesktopHost trusted session, a real local model loaded and executed through
the app, one real media chain end to end with artefacts and digests, export packaging, and a full
CI run. None of those happened. Hosted CI remains `BLOCKED_ACCOUNT_PLATFORM`.

`M4` stays `PARTIAL`, `M5–M9` `LOCAL_REQUIRED`, the V1 freeze and F00 INTEGRATED + 39 PARTIAL
markers are unchanged, and `CONTENT_POLICY_FRAMEWORK` remains `RESERVED`.

QingJian stayed read-only: no modification, no adapter development, no dual-product integration.
Other worktrees and other agents' traces were observed only, never cleaned or altered.

---

## 9. Commits in this phase

| Commit | Content |
| --- | --- |
| `a9f03bb` | level-② passive runtime observation layer + 50 tests + live sweep receipt |
| `2be9e42` | user-confirmed custom-HTTP registration gate + capability vocabulary invariants |
| `0c5128b` | real-browser acceptance re-run on the current head (8/8) |
| `3f97b34` | `MEDIA_PIPELINE_RC_CHECKLIST.md` + media chain contract preflight |
| `2066f13` | `WINDOWS_GPU_RC_CHECKLIST.md` + measured host inventory |

End state: HEAD = remote; PR #47 `OPEN`/draft; `main` untouched; no tracked file left dirty; the
39 remaining untracked entries are all protected baseline families; no service started by this
phase is still running (5173/8110 free, zero `postgres` processes).

---

## 10. Limits and recommended next steps

**Limits of this report.** Hindsight memory was unavailable (API error), so no memory page was
consulted. Phase8/Phase9 figures are cited as history and were not re-executed except the browser
suite. Only the browser acceptance and the contract preflight were run end to end; nothing was
generated, installed or packaged.

**Recommended order for the next phase:**

1. **Decide F1** (duplicate GPU record) and cover the fix with a test — the only open defect-like
   finding from this phase, and cheap to close.
2. **Reach `READY` once, honestly.** Either install an app-native runtime, or deliberately register
   an observed loopback endpoint through the gated path, then run one real inference and record the
   receipt. Until `READY` is reached once, level ⑤ is only ever "refused by design".
3. **Run the media chain for real**, step by step, filling the checklist rows with real Asset IDs,
   versions and digests; exercise the seven failure scenarios, including the `bash`-absent one
   already evidenced as `BLOCKED_EXTERNAL`.
4. **Clean-machine Windows pass** (W1/W2/W4/W6) — the largest remaining blocker and the only way to
   move install/packaging off `NOT_RUN`.
5. **Export packaging**, then a full-CI attempt (or an explicit decision that hosted CI stays
   `BLOCKED_ACCOUNT_PLATFORM`).
6. **Optional hardening surfaced by this phase:** the frontend's duplicate port table (Phase10 C1)
   and `validate_output_ports`'s `schema_version=None` default remain the two known contract-drift
   risks.
