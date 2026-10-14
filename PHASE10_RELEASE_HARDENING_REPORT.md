# Phase 10 — Release-candidate hardening and real-environment validation preparation

**Date:** 2026-10-14 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline at phase start:** `55f67ea` (local = remote). `main` = `fed2404c`, never touched.
**PR #47:** `OPEN` / `isDraft: true` / `MERGEABLE`, `headRefOid` `55f67ea0f0af9affafd043be67251551d1a3d000`
at verification time. No merge, no release, no tag.

**Status vocabulary in this report — only these five values are used:**
`IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.
No status was upgraded because an earlier report exists. A prior PASS is not evidence
for a later claim and is cited as history, not re-used as proof.

> This phase is **not** a release and does not assert release readiness. Its only product
> is current, reproducible evidence plus the documents that carry it.

---

## 1. Baseline verification (commands and observed results)

Nothing below is taken from a prior description; each line is a command run in this session.

| Check | Command | Result |
| --- | --- | --- |
| Local HEAD | `git rev-parse --short HEAD` | `55f67ea` |
| Branch | `git rev-parse --abbrev-ref HEAD` | `feature/v2-narrative-platform` |
| Remote heads | `git ls-remote <origin> refs/heads/feature/... refs/heads/main` | `55f67ea0f0af9…` and `fed2404c8e30b…` |
| PR state | `gh pr view 47 --json state,isDraft,headRefOid,baseRefName,mergeable` | `OPEN`, draft, base `main`, `MERGEABLE` |
| Pending change | `git diff --numstat -- tests/test_v2_creative_graph_contracts.py` | `142 0` (append-only) |
| Untracked at start | `git status --porcelain` | 69 entries |

`main` is unchanged and was never checked out, merged or written in this phase.
The protected untracked baseline families (`docs/delivery/v2-development/phase6-*`,
`catalog-f19d*.json`, `.graphflow-cache/`, `graphflow-out/`, `frontend/test-results/`)
were neither committed nor deleted. Every commit below used explicit paths
(`git add -- <path...>`); `git add -A` / `git add .` were never used, and no
`reset --hard`, `clean`, or force push was performed.

---

## 2. Solidified work: the pending graph-contract additions and their receipts

**Commit `37051ec`** — `tests/test_v2_creative_graph_contracts.py` (**+142 / −0**) plus 30
Phase10 evidence receipts.

The diff is two hunks only — an import at line 12 and 140 new lines after line 525 — with
**zero deletions**, so no pre-existing assertion was relaxed, skipped or removed. It was
re-verified independently before commit rather than trusting the handover figure:

```
scripts/run_v2_checks.py phase10-graph-lead-verify-r2 -- \
  python -m pytest tests/test_v2_creative_graph_contracts.py -q \
  --basetemp .runtime/v2-checks/phase10-graph-lead-verify-r2/pytest -p no:cacheprovider
→ 260 passed in 2.47s, exit 0
→ docs/delivery/v2-development/phase10-graph-lead-verify-r2.json  (status PASS)
```

The receipts landed as produced, including the ones that are **supposed** to be red:

- `c1-mutation-probe.*` — deliberately mutates the contract to prove the new pin really
  fails when the contract is broken. Its failure is the *point*; it is not a product failure.
- `c1-c2-graph-suites.*`, `c1-graph-suites-r2.*` — two FAILs caused by command-line
  mistakes on that line (a non-existent test file, and a missing `--basetemp`).
- `phase10-a1-runtime-levels-pg.*` — a setup ERROR, examined in §5.6 and shown **not** to be
  a PostgreSQL check at all.

Fixing these artifacts to look green would have destroyed the evidence, so they were
committed verbatim.

---

## 3. Work line C — graph contract and asset audit (conclusion carried forward)

The audit was completed before this session and was **not redone**. Its recorded conclusion:

- **C1 node contract** — node identity, ports, port types, `required`, caps, parameter models
  and the schema-version gate are **backend-authoritative**
  (`app/creative/graph_models.py` `DEFINITIONS` 463–508, `port()` 459, `NodeInstance`
  530–550, `parse_graph` 676–679; `graph.py:373-375` required rule; `validate_output_ports`
  765–830). Gaps: `capabilities`, parameter JSON-schema, `blockers` and `default_parameters`
  are display-only; the frontend keeps a second port table (`studioGraphClient.ts:57-86`,
  `graphDraft.ts:8-10`), so drift surfaces as a catalog load failure rather than as server
  truth; `validate_output_ports` defaults to `schema_version=None`, so a caller that omits it
  validates as v1.
- **C2 asset relationships** — the owner declares seven relationship kinds
  (`SOURCE_OF`, `DERIVED_FROM`, `REFERENCES`, `USED_IN`, `ALTERNATE_VERSION`, `APPROVED_FOR`,
  `LINKED_CONTEXT`); only `SOURCE_OF` and `DERIVED_FROM` have producers and are gated by
  lineage; **no consumer guesses an undeclared relationship** — anything unknown is reported
  as 未核实 (D13). Gap: the `/relationships` graph projection drops
  `semantics: DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION` (the per-asset projection keeps
  it), but adding the key breaks strict decoding in `assetbrowser`, so it is recorded only.
- **C3 snapshots** — graph definition + version + node state + run history are persisted
  (`creative_graph_definitions_v2`, `creative_graph_runs_v2`); the edit-version `history` is
  appended on every write but is exposed by no DTO or route; canvas grouping/annotation/
  collapse and editor draft/selection/undo are **session-only** (D12) and must not be
  described as persisted.
- **Graph status: `PARTIAL`** — contracts and snapshots are implemented and backend-authoritative;
  what remains is display-level and session-scoped.

---

## 4. Work line B — release validation checklists (landed in `55f67ea`)

`WINDOWS_RC_VALIDATION_CHECKLIST.md` and `MEDIA_PIPELINE_RC_VALIDATION.md` are committed and
**every item in them is `NOT_RUN`**. They were not re-executed in this phase, and nothing in
them was upgraded to a real result. Mock or synthetic results are not recorded there as real
validation.

---

## 5. Work line A — Model Center real capability convergence

### 5.1 The five levels, judged against the source

The discovery stack in `app/model_center/` is a **real local probe stack**, not a stub, and it
already keeps discovery separate from runnability. Level by level:

| Level | What observes it | Status |
| --- | --- | --- |
| ① file existence | `executable_metadata()` → `executable_exists` / `executable_size`; GGUF `file_exists`, `size`, `header_valid` | `IMPLEMENTED` |
| ② runtime existence | **nothing at process level** — never probed, only inferred from ① plus a silent endpoint | **not implemented** (see 5.2) |
| ③ runtime connectable | bounded loopback HTTP probe; `status` becomes `RUNNING` on a well-formed answer, otherwise `DISCOVERED` + `EXTERNAL_RUNTIME_NOT_RUNNING` | `IMPLEMENTED` |
| ④ model recognisable | GGUF header/`general.architecture`/`tensor_count`; provider model lists; ComfyUI loader-node bindings | `IMPLEMENTED` |
| ⑤ model executable | never claimed — `INFERENCE_NOT_RUN`, `EXECUTABLE_NOT_EXECUTED`, `verified: false`, `enable_eligible: false` | `NOT_RUN` **by design** |

The decisive property holds: at level ④ the capability can be verified while executability is
still refused. Observed in the probe receipt — `verified_capabilities: ["TEXT"]` together with
`verified: false`, `enable_eligible: false`, `enable_blockers: ["RUNTIME_MODEL_UNVERIFIED",
"LICENSE_VALIDATION_REQUIRED"]`, `local: false`, `source_locality: "NOT_VERIFIED"`.
**Discovery is not runnability, and the report says so itself.**

### 5.2 Level ② is the honest gap — and it is now pinned

No discovery code path observes whether a runtime process exists. `RuntimeInstance.process_alive`
/ `http_reachable` live on the lifecycle object (`app/model_center/service.py`), which discovery
never consults; the scan report carries no process fact at all. `DISCOVERED` therefore means
"the endpoint did not answer", **not** "no process exists".

**Commit `6a466c4`** adds `tests/test_v2_discovery_runtime_levels.py` (which had no prior test
asserting the scan-time report shape) plus one additive pin,
`test_runtime_existence_is_never_probed_at_process_level`, so a later change cannot start
presenting an inferred level-② fact as measured evidence. The new pin asserts the report
contains no `process_alive` / `process_id` / `pid` / `running` / `state` / `http_reachable`
key, that `DISCOVERED` here is connectivity-derived, and that the lifecycle is never called.
Nothing in the file weakens an existing assertion, and no other test was touched.

### 5.3 Per-source judgement

| Source | Reach | ① file | ② process | ③ connect | ④ recognise | ⑤ execute |
| --- | --- | --- | --- | --- | --- | --- |
| Ollama (11434) | `OLLAMA` → `OllamaProvider.list_models(strict=True)`, `/api/version`, `/api/show` | via scan roots | not probed | yes | name + `details` + capability list; `completion`→`TEXT`, `vision`→`VISION`, `embedding`→`EMBEDDING` (flag-gated) | never |
| LM Studio (1234) | **no `RuntimeType`**; `ProviderFamily` `LM_STUDIO` with `runtime_type` `OPENAI_COMPATIBLE_LOCAL` (`model_provider_contracts.py:22,304-305`); seeded at `discovery.py:226` | model dirs `~/.lmstudio/models`, `~/.cache/lm-studio/models` (`discovery_environment.py:103`) | not probed | yes | model `id` list only → `CAPABILITY_UNVERIFIED` | never |
| ComfyUI (8188) | `COMFYUI` → `/system_stats` + `/object_info` | loader filenames (`ckpt_name`, `unet_name`, `model_name`, …) | not probed | yes | loader-node bindings + `nodes_fingerprint` + recipes | never (`generation_verified: false`, `workflow_status: NOT_CONFIGURED`; best case `STRUCTURE_VALIDATED_NOT_GENERATED`) |
| llama.cpp | `LLAMA_CPP` → `/v1/models` | `executable_exists` + GGUF header | not probed | yes | GGUF header/arch | never (`EXECUTABLE_NOT_EXECUTED`) |
| Local model directories | `scan_environment_files` + `scan_gguf_roots`, `MAX_FILES 2000`, `MAX_DEPTH 3`, `MAX_ENTRIES 5000` | yes | n/a | n/a | GGUF metadata / filename family | n/a |

`LOCAL_TYPES` (`discovery_types.py:11`) is
`OLLAMA · LLAMA_CPP · COMFYUI · AUTOMATIC1111 · OPENAI_COMPATIBLE_LOCAL · CUSTOM_HTTP` —
**`WHISPER_CPP` is not discoverable**; the Whisper host is configured through an explicit pinned
path, never scanned.

### 5.4 Registry fields and capability mapping — two claims corrected

The registry fields you named are all present: `ModelDefinition` carries
`id`/`display_name`/`family`/`variant`/`version`/**`capabilities`**/**`runtime_type`**/
`model_format`/`quantization`/`precision`/`source`/`license`/**`local_paths`**/**`status`**/
`components`/`hardware_profiles`/`compatibility`/`identity_id`, and VRAM lives on
`HardwareProfile` (`vram_required`, `vram_recommended`, `ram_required`, `ram_recommended`,
`context`, `resolution`, `frames`, `fps`, `offload_mode`, `tested`). `Capability` has ten
values: `TEXT · IMAGE · VIDEO · VISION · TTS · AUDIO · EMBEDDING · RERANK · RESTORATION ·
INTERPOLATION`.

Two of the mappings in the brief needed correction:

- **FLUX → `IMAGE_GENERATION`: true only at the task layer.** In Model Center, FLUX is
  registered as `Capability.IMAGE` (`service.py:629-630`, `RuntimeType.COMFYUI`), and filename
  inference maps `flux → FLUX / IMAGE` (`discovery_probes.py:91`). `IMAGE_GENERATION` is a
  `TaskType` that resolves down to `IMAGE` via
  `TASK_CAPABILITY = {"TEXT_GENERATION": "TEXT", "IMAGE_GENERATION": "IMAGE", "VIDEO_GENERATION": "VIDEO"}`
  (`model_provider_contracts.py:21-24`).
- **Whisper → `ASR`: not a registry capability.** There is **no `ASR` value in `Capability`.**
  Whisper's model is `(Capability.AUDIO,)` with family `"WHISPER"` (`whisper_runtime.py:233-234`);
  `ASR` appears only as a **graph node binding** name (`whisper_runtime.py:535`). Recording
  "Whisper→ASR capability" would be inaccurate.

### 5.5 Host reality on this machine

- No listener is bound on 11434, 1234, 8188 or 19992 (confirmed in this session), consistent
  with Phase9's refused-connection result. No `ollama`/`llama-server`/`llama-cli` on PATH.
- **Port 8080's identity — unproven in Phase9 — is now proven.** `GET /health` returns
  `{"status":"ok","max_context":131072,"model":"qwen3.8-flash-next-iq3_xxs","images":false,"api_key":false,"loaded":false,"service":"strata"}`
  and `/v1/models` is OpenAI-compatible; the owning process is `pythonw.exe` from
  `C:\AI-Novel-Studio-Python312`. It is the **Strata local model server** (a separate Python
  3.12 installation), **not** an AI-Novel-Studio runtime and not a V1 component. It is
  nevertheless a *reachable local OpenAI-compatible endpoint*, so the Phase9 statement that
  nothing local is reachable should be read as "nothing the app's own discovery configures is
  reachable" — this endpoint is not registered in Model Center and nothing here claims the app
  uses it. Read-only observation only; nothing was started, loaded or modified.
- **Port 8100 is occupied** by an unrelated vendor service
  (`C:\Program Files (x86)\ASUS\Gear Link\KB\GearLink_KBService\GearLink_KBService.exe`).
  The Phase9 browser-acceptance configuration used 8100; a future re-run must choose another
  free port (8000 stays unusable — it is in a Windows excluded range, held by PID 4).
  That service was **recorded, not stopped**: it is not ours.
- Work line A left **no** running service: nothing listens on 8102 or 55432.

### 5.6 Real-PostgreSQL verification, and a runner-syntax correction

The pre-existing `phase10-a1-runtime-levels-pg` receipt is **not** a PostgreSQL check. Its
recorded command was a bare `pytest tests/test_v2_discovery_runtime_levels.py -q` with no
`--basetemp`, run through the ordinary check runner rather than through
`run_v2_postgres_checks.py`; no schema was ever created, so all three tests errored with
`UndefinedTable: relation "generation_jobs" does not exist`. The 20 migrations *do* create that
table (`database/migrations/002_runtime_jobs.sql`). That receipt is evidence of a
command-line mistake, so real-PostgreSQL coverage was `NOT_RUN` and has now been done properly.

Documented invocation, corrected against the actual `argparse` contract:

```
run_v2_postgres_checks.py --pg-bin <portable PG bin> --data <cluster data> \
    --port 55433 --database v2_phase10a1f --fresh-database <label> \
    -- <absolute python> -m pytest <files> -q --basetemp <dir that already exists> \
       -p no:cacheprovider
```

Four points the earlier attempts got wrong, all now recorded for Phase11:

1. `<label>` is a **positional** argument (`[a-z0-9-]+`) and is required; it is **not** `--user`.
2. `--user` is the **PostgreSQL connect role** (default `postgres`) — passing a label there
   fails with `role "…" does not exist`.
3. `--basetemp`'s directory must **already exist**, or every test errors at setup with
   `FileNotFoundError`.
4. The interpreter must be an **absolute path**; a bare `python` fails in `CreateProcess`
   with `[WinError 2]`.

Result on a real disposable PostgreSQL cluster:

```
phase10-a1-r4   → 4 passed, exit 0        (docs/delivery/v2-development/phase10-a1-r4.json)
migration_status applied — all 20 database/migrations/*.sql, database proven empty beforehand
server_stop      stopped / cleanup completed / no leftover listener
PostgreSQL 16.15, 127.0.0.1:55433, database v2_phase10a1f, role postgres
```

File-backend result for the same file: `3 passed` (`…-file-r2.json`) then `4 passed`
(`…-file-r3.json`, with the new level-② pin). The failed attempts `r2` and `r3` are retained
unchanged as the failures they were, alongside each run's `-postgres-runtime.json`.

### 5.7 Environment-level failures — recorded, never masked

Running the broader Model Center discovery suites produced
`9 failed, 539 passed, 1 skipped`, and **none of the nine is a product defect**:

- 4 × `OSError [WinError 1314]` creating symlinks — the account lacks
  `SeCreateSymbolicLinkPrivilege` (POSIX-only assumption);
- 1 × `AttributeError: module 'os' has no attribute 'sysconf'` — POSIX-only;
- 4 × `PermissionError [WinError 10013]` / `ValueError: PORT_IN_USE` binding
  54321/54323/54325/54327 — Windows excluded port ranges.

These are additional to the two environment-level failures already known from the handover
(`tests/test_v2_media_prerequisites.py` 10 failed — POSIX-only shim;
`tests/test_v2_audio_wav_controls.py` 2 failed — 96 kHz boundary). **No assertion, skip or
test case was changed to hide any of them**, and none was re-run in this phase, so their
handed-over numbers are cited as history rather than re-claimed.

---

## 6. Status table

| Item | Status | Evidence / remaining boundary |
| --- | --- | --- |
| Baseline integrity (`55f67ea`, `main` `fed2404c`, PR #47 draft) | `IMPLEMENTED` | §1 commands; nothing merged, released or tagged |
| Creative-graph contract pins (+142/−0) | `IMPLEMENTED` | `37051ec`; 260 passed, exit 0 (`phase10-graph-lead-verify-r2.json`) |
| Graph contract & snapshot authority | `PARTIAL` | §3 — backend-authoritative; gaps are display-level + session-scoped (D12/D13) |
| Model Center five-level distinction | `PARTIAL` | Levels ①③④ `IMPLEMENTED`, ⑤ refused by design, **② not implemented** — only inferred, and now pinned |
| Model Center registry fields & capability map | `IMPLEMENTED` | §5.4; `Capability` 10 values, `RuntimeType` 7 |
| Discovery runtime levels on file backend | `IMPLEMENTED` | 4 passed, exit 0 (`phase10-a1-runtime-levels-file-r3.json`) |
| Discovery runtime levels on real PostgreSQL | `IMPLEMENTED` | 4 passed, exit 0; 20 migrations; clean stop (`phase10-a1-r4.json`) |
| Live local runtime end-to-end (a real model actually generating) | `LOCAL_REQUIRED` | No app-configured runtime is reachable on this host; 8080 is the Strata server, not an app runtime |
| Ollama / LM Studio / ComfyUI / llama.cpp live probes | `NOT_RUN` | Ports refuse connections; nothing installed or downloaded |
| Windows RC checklist & media pipeline checklist | `NOT_RUN` | Committed in `55f67ea`; every item still `NOT_RUN` |
| Browser acceptance re-run | `NOT_RUN` | Phase9's 8/8 is history; port 8100 is now taken (§5.5) |
| Release documentation | `PARTIAL` | `README.md` was 41 lines, `docs/installation.md` a 3-line stub; partly closed in §7 |
| Hosted CI | `BLOCKED` | `BLOCKED_ACCOUNT_PLATFORM` — billing lock; never started, never counted as passing |
| `CONTENT_POLICY_FRAMEWORK` | `RESERVED` | Unchanged. No NSFW/Mature capability, no UI entry point, no model filter |

---

## 7. Documentation closed in this phase

Only verified content was added; no future capability is described as existing.

- `docs/installation.md` — the historical 3-line stub is retained verbatim and a verified
  section was appended: the actual interpreter, the two runners with the *working* invocations
  (including the PostgreSQL syntax corrected in §5.6), the acceptance configuration, and the
  explicit boundary that packaging/install/uninstall is `NOT_RUN`.
- `README.md` — expanded from 41 lines with verified entry points and the same status
  vocabulary; it points at this report rather than restating unverified claims.
- `AI_NOVEL_STUDIO_V2_FEATURE_MATRIX.md` — an append-only Phase 10 section; no historical row
  or status was edited.

---

## 8. Release-candidate conclusion

**`NOT ESTABLISHED`.** This phase hardened evidence; it did not validate a candidate.

Still `NOT_RUN` / `BLOCKED` / `LOCAL_REQUIRED`: Windows install and uninstall, Chinese and
space-containing paths, long paths, restart recovery, DesktopHost launcher/backend/PostgreSQL
trusted session, GPU work and real model execution, the real media pipeline,
Text→Image→Video→Audio→Timeline→Export end to end, export packaging, the browser acceptance
re-run, pixel-level visual regression, and a full-CI run. Hosted CI remains
`BLOCKED_ACCOUNT_PLATFORM`. `M4` stays `PARTIAL`, `M5–M9` `LOCAL_REQUIRED`, the V1 freeze and
F00 INTEGRATED + 39 PARTIAL markers are unchanged, and `CONTENT_POLICY_FRAMEWORK` remains
`RESERVED`.

Nothing in the QingJian repository was read-modify-written, no adapter was developed, and no
dual-product integration was attempted. No other worktree or other agent's traces were
disturbed; observations only.

---

## 9. Limits of this report

- Phase8 and Phase9 figures (File 56/43, PG 8/1, browser 8/8, harness r13 643 tests, `tsc -b
  --force` 0) are **cited from the handover as history** and were not re-executed here; only
  the graph-contract and discovery-level suites were re-run first-hand.
- Two pre-existing host-level failures are recorded, not resolved.
- The port-8080 identification in §5.5 is a read-only HTTP and process observation; it
  proves what serves port 8080, not that the application should use it.

## 10. Commits in this phase

| Commit | Content |
| --- | --- |
| `37051ec` | graph-contract pins +142/−0 and 30 Phase10 receipts |
| `6a466c4` | `tests/test_v2_discovery_runtime_levels.py` with the level-② gap pin |
| `20924f5` | real-PostgreSQL verification receipts (`r2`/`r3` failures and `r4` pass) |
