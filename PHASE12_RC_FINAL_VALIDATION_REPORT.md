# PHASE12_RC_FINAL_VALIDATION_REPORT — RC Final Validation

**Date:** 2026-10-15 · **Branch:** `feature/v2-narrative-platform` · **Worktree:**
`D:\PoemSeed\Worktrees\studio-v2-audio-editing-20261014`

**Baseline:** `4e98afc` (local = remote at phase start). `main` = `fed2404c`, never touched.
**PR #47:** `OPEN` / `isDraft: true`. No merge, no release, no tag.

**Status vocabulary — only these five values are used in §8:**
`IMPLEMENTED` · `PARTIAL` · `BLOCKED` · `LOCAL_REQUIRED` · `NOT_RUN`.
`BLOCKED_EXTERNAL` is used in prose for a host-caused failure that is demonstrably not a product
defect. Nothing was upgraded because a previous report existed.

> Phase12 is a validation phase: no architecture was redesigned and no large module was added. It
> fixed one real hardware-inventory defect, reached runtime level ⑤ for the first time, and ran one
> real model-free media chain.

---

## 1. Baseline re-verified, and the prior reports re-read

| Check | Result |
| --- | --- |
| `git rev-parse --short HEAD` | `4e98afc`, branch `feature/v2-narrative-platform` |
| `git ls-remote origin …` | feature `4e98afc…`, **main `fed2404c`** (untouched) |
| `gh pr view 47 --json state,isDraft,headRefOid` | `OPEN`, draft, `4e98afc…` |
| tracked dirty / untracked | `0` / `39` (all protected baseline families) |

Per §二 the matrix, the Phase10 and Phase11 reports, the README and `docs/v2/` were re-read rather
than trusted. Where a prior statement had been overtaken, it is **superseded in the Phase12 append
section with the original row left intact** — notably the Phase11 sentence "`READY` has never been
reached for any runtime", which §3 now falsifies.

**Also recorded:** the Hindsight memory API errored throughout Phase11 and was not relied on here;
every conclusion below rests on first-hand execution.

---

## 2. P0 — GPU hardware identity (the real defect)

### 2.1 Consequence, not cosmetics

`host_hardware()` reported the RTX 5080 **twice**. The damage was worse than a duplicated row:
`_gpu_capability` deliberately fails closed unless it sees **exactly one** device
(`provider_runtime_v2_host_hardware_inventory.py:100-101`), so the host reported
`gpu_vendor_id=None, vram_mib=0` — **no GPU capability at all**. That value feeds VRAM budgets,
hardware profiles and runtime admission, exactly the blast radius the brief anticipated.

### 2.2 Cause, established from the raw enumeration

| idx | Description | Vendor/Device | SubSys/Rev | VRAM | AdapterLuid | Flags |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | RTX 5080 | `10DE`/`2C02` | `209610DE`/`A1` | 16 753 098 752 | `0:68850` | 0 |
| 1 | RTX 5080 | `10DE`/`2C02` | `209610DE`/`A1` | 16 753 098 752 | `0:112158` | 0 |
| 2 | Microsoft Basic Render Driver | `1414`/`8C` | — | 0 | `0:77580` | **2 (software)** |
| 3 | `DXGI_ERROR_NOT_FOUND` | | | | | |

So DXGI really does expose **two adapter instances for one physical GPU**, with *different* Luids and
identical device identity. Windows PnP shows exactly one present RTX 5080
(`PCI\VEN_10DE&DEV_2C02&SUBSYS_209610DE&REV_A1`), a non-present GTX 1050 ghost, and a
`GameViewer Virtual Display Adapter` — an indirect display attached to the GPU, which is why the
adapter is aliased. The software adapter is correctly filtered by the existing flag check.

### 2.3 Fix, and how it respects the four required principles

1. **One physical GPU appears once** — adapters are grouped by device signature and collapsed only
   when the OS proves one present device.
2. **No blind de-duplication** — the collapse requires *proof* from the present-device inventory, and
   every collapse is disclosed through `gpu_enumeration` (`raw_adapter_count`,
   `physical_device_count`, `aliased_adapter_count`, `present_device_counts`,
   `unresolved_signatures`, `adapter_luids`).
3. **Identity preserved** — `device_id`, `subsystem_id`, `revision`, `adapter_luid` and a derived PnP
   `hardware_id` are carried on every fact.
4. **Single-GPU → 1; multi-GPU → several real devices** — two identical present GPUs stay two devices,
   which is why the inventory returns a **tuple, not a set** (a set would have silently hidden a real
   second GPU — a flaw found and fixed in my own first draft).

Additionally: `_gpu_capability` was **not modified**, so no threshold was lowered and the
fail-closed rule for genuinely multiple devices still holds; nothing vendor-, model- or
VRAM-specific is hardcoded; and the `gpus[]` payload shape in `host_hardware()` is untouched because
an existing test pins it exactly (identity is exposed in a new `gpu_enumeration` key instead).

### 2.4 Live before/after on this host

| | before | after |
| --- | --- | --- |
| physical GPUs | 2 | **1** |
| `_gpu_capability` | `(None, 0)` | **`(NVIDIA uuid, 15977 MiB)`** |
| diagnostics | — | `aliased_adapter_count: 1`, `presence_verified: True`, `unresolved_signatures: []` |

### 2.5 Two of my own bugs the new tests caught

Both were fixed rather than worked around: `present >= len(group)` was wrongly listed as
*unresolved* (making a resolved multi-GPU case look ambiguous), and `SPDRP_HARDWAREID` was used as
`0x0` when it is **`0x1`** (`0x0` is `SPDRP_DEVICEDESC`), so the probe read device *descriptions*
and matched no PCI hardware ID. A third, `found.add(...)` on a list, aborted the probe silently
inside its own exception handler.

Evidence: `tests/test_v2_gpu_physical_identity.py` (new; includes two real-Windows acceptance tests)
with the adjacent suites — **237 passed, 1 skipped, 3 failed**. All three failures are pre-existing
`BLOCKED_EXTERNAL` environment limits, unchanged from Phase10/11: two symlink cases (`WinError 1314`,
the account lacks `SeCreateSymbolicLinkPrivilege`) and one POSIX-only `os.sysconf` case. **No
assertion was weakened, skipped or removed.**

---

## 3. P1 — one real local runtime reached `READY`

The brief's flow was followed in order, against the already-running local Strata server on 8080.

| Stage | Evidence |
| --- | --- |
| Detection | loopback listener present; owner identified as pid **16292**, `C:\AI-Novel-Studio-Python312\pythonw.exe`, `identity_verified: true` |
| Identity | `/health` → `service: strata`, model `qwen3.8-flash-next-iq3_xxs`, `max_context 131072`, `api_key: false`, `loaded: false` |
| Capability mapping | advertised modalities `text → text`, so model capability **`TEXT`**; task layer reported separately (`TEXT_GENERATION`→`TEXT`, `IMAGE_GENERATION`→`IMAGE`) so the vocabularies are not confused |
| Connectivity | `/v1/models` answered with the advertised model |
| Confirmation | the brief names this runtime as the preferred candidate; **no registration was performed** |
| **One real inference** | **ok**, latency **53.7 s** (the first request loads the model), `usage: prompt 57 / completion 8 / total 65`, `finish_reason: length` |

With that evidence the observation escalated to **level ⑤ `READY`** with `inference_verified: true`
— the first time any runtime has reached level ⑤, which until now was only ever "refused by design".

**Honest caveats, all recorded:** the runtime is the **DSH-provided Strata server, not an
app-native runtime**; it was **already running** (started outside this session, so it was never
stopped or reconfigured); and `content_preview` is empty because the 8-token cap was hit, so the
proof of inference is the token usage and a valid `choices` payload rather than visible text.

**Registration was not performed.** A descriptor was prepared with `confirmed_by_user: true`,
`capability_status: DECLARED_BY_USER`, `generates_tasks: false` and `auto_enabled: false` — it
carries no center, lifecycle, task or job reference, so nothing was bound, enabled or scheduled.

---

## 4. P2 — one real model-free media chain

Run against a **real running backend** (`uvicorn app.main:app`, `STORAGE_BACKEND=file`,
`EXPERIMENTAL_FEATURES=narrative_production_v2`, `MOCK_PROVIDER=false`) through the app's own HTTP
API in a sandbox data directory.

| # | Step | Asset ID | Version | Digest (sha256) | Review state | Result |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Text | `phase12:1` | `1` | `e7f4164a…` | `Draft` | **PASS** |
| 2 | Director / Screenplay | `a15f7d00-…` | `revision 1`, `edit_version 1→2` | `78954981…` | `DRAFT → APPROVED` | **PASS** |
| 3 | Shot plan | same | `edit_version 3→4`, `shot_revision 1` | `deebe0ce…` | `APPROVED` | **PASS** |
| 4 | Storyboard | same | `edit_version 4→5`, `storyboard_revision 1` | `60079fa5…` | `APPROVED` | **PASS** |
| 5 | Export | job `51155d19-…` | `snapshot_id 935c5c78-…` | artefact **1930 B** `92ad87bc…` | `succeeded` (100 %) | **PASS** |
| 6–9 | Image / Video / Audio / Timeline | — | — | — | — | **BLOCKED** |

The screenplay's scene pins the real source chapter (`source_chapter_id: phase12:1`,
`source_version: 1`), so the Director step genuinely derives from the Text step rather than
referencing it loosely. **No generative model was involved in any PASS row** — they are real product
operations with real ids, versions, review transitions and digests.

### Real gates discovered (product behaviour, not defects)

1. **Approvals are review-gated**: `400 screenplay must be approved before shot planning`, and
   `400 shot plan must be approved before storyboard`. The chain went **through** the gates.
2. **Every approval is an optimistic-concurrency write**: omitting the precondition returns
   `428 PRECONDITION_REQUIRED`, a stale value returns `409 VERSION_CONFLICT`, and `expected_version`
   is the screenplay **`edit_version`** — not the per-artefact revision.
3. **A client gap worth recording:** the current `edit_version` is only readable *indirectly*
   (no `GET` for one screenplay → `404`; `GET …/shots` → `405`), so it must be read from an export
   job's `source_versions`.

**Why steps 6–9 are blocked, not failed:** Image, Video and Audio each require a local runtime that
this host does not have (ComfyUI 8188 and the others have no listener; the Whisper host is not
configured), and Timeline depends on their assets. **Nothing mock or cloud was substituted.**

---

## 5. P3 — Windows RC execution guide

`WINDOWS_RC_EXECUTION_GUIDE.md` (commit `4e89f27`) specifies the clean-machine run: install /
uninstall / first start, Chinese + space + long paths, launcher / backend / DesktopHost /
PostgreSQL, restart + crash + cache recovery, and the RTX 5080 CUDA / VRAM / model-load checks —
each with its real owner, the port constraints (8000 excluded, 8100 held by `GearLink_KBService`,
8080 is Strata, 8110 free) and the rule that cloud or mock results never fill a local cell. It marks
what is already verified on this host and leaves the rest `NOT_RUN`. **No clean-machine execution
was performed.**

---

## 6. Model Center state — 发现 ≠ 可运行, preserved

The distinction is intact and now has a live positive case as well as live negative ones:

| Status | Meaning | This host |
| --- | --- | --- |
| `NOT_OBSERVED` (0) | no evidence at all | — |
| `DISCOVERED` (1) | a file/artifact exists | — |
| `RUNTIME_AVAILABLE` (2) | a process/handle owns the port | — |
| `REACHABLE` (3) | the endpoint answered our protocol | — |
| `CAPABILITY_UNKNOWN` (4) | a model was recognised, capability unverified | — |
| **`READY` (5)** | **real inference verified** | **Strata 8080 (verified this phase)** |
| — | no listener | Ollama 11434, LM Studio 1234, ComfyUI 8188 → `NOT_OBSERVED` |

A scanned model is still never presented as executable: `READY` requires inference evidence supplied
from outside the observation layer, and observation alone is provably capped at level 4.

---

## 7. Content policy

`CONTENT_POLICY_FRAMEWORK` remains **`RESERVED`**. No NSFW/Mature mode, no UI entry point, no
model-filtering system, no content-filter system. Only fields, compatibility and their tests. A
policy is never a way to bypass a safety limit.

---

## 8. Status table

| Item | Status | Evidence |
| --- | --- | --- |
| Baseline integrity (`4e98afc`, `main` `fed2404c`, PR draft) | `IMPLEMENTED` | §1; nothing merged, released or tagged |
| GPU physical identity defect | **`IMPLEMENTED` (fixed)** | `82d1282`; live 2 → 1 GPU, `(None,0)` → `(uuid, 15977 MiB)`; 237 passed |
| Runtime level ⑤ `READY` | **`IMPLEMENTED`** | `4e89f27`; one real inference, 53.7 s, 65 tokens |
| Runtime registration (custom-HTTP gate) | `IMPLEMENTED` (gated, not performed) | descriptor prepared with `performed: false` |
| Real model-free media chain | `PARTIAL` | `f9cad2a`; Text→Director→Shots→Storyboard→Export real; Image/Video/Audio/Timeline blocked |
| Windows / GPU clean-machine execution | `NOT_RUN` | guide produced, nothing executed on a clean machine |
| Clean install / uninstall / packaged DesktopHost | `NOT_RUN` | `ENABLE_PACKAGED_RUNTIME=false`; path never exercised |
| GPU CUDA execution / model load / image / video | `NOT_RUN` | VRAM measured only; app verdict stays `COMPONENT_FOUND_NOT_VERIFIED` |
| Live local runtime end-to-end (app-native) | `LOCAL_REQUIRED` | Strata verified but deliberately not registered |
| Release documentation | `PARTIAL` | Windows guide + media checklist record added; installer docs still absent |
| Hosted CI | `BLOCKED` | `BLOCKED_ACCOUNT_PLATFORM` — billing lock; never counted as passing |
| `CONTENT_POLICY_FRAMEWORK` | `RESERVED` | unchanged |

---

## 9. Release-candidate conclusion

**`NOT ESTABLISHED`.** Phase12 removed a real defect and produced two firsts — level ⑤ reached with
real inference, and one real model-free chain end to end — but a release candidate still requires:
install and uninstall on a clean Windows machine, the packaged DesktopHost trusted session, a real
local model loaded and executed **through the app**, the media chain's model-dependent steps, export
packaging, and a full CI run. None of those happened. Hosted CI remains
`BLOCKED_ACCOUNT_PLATFORM`.

`M4` stays `PARTIAL`, `M5–M9` `LOCAL_REQUIRED`, the V1 freeze and F00 INTEGRATED + 39 PARTIAL
markers are unchanged, and `CONTENT_POLICY_FRAMEWORK` remains `RESERVED`.

QingJian stayed read-only: no modification, no Interop development, no dual-product acceptance.
Other worktrees and other agents' traces were observed only, never altered.

---

## 10. Commits in this phase

| Commit | Content |
| --- | --- |
| `82d1282` | GPU physical-identity fix + `tests/test_v2_gpu_physical_identity.py` |
| `4e89f27` | real local inference reaching `READY` + `WINDOWS_RC_EXECUTION_GUIDE.md` |
| `f9cad2a` | real model-free media chain + checklist execution record |
| final docs commit | this report + the Phase12 matrix append |

End state: HEAD = remote; PR #47 `OPEN`/draft; `main` untouched; no tracked file dirty; the 39
untracked entries are all protected; and no service started by this phase is still running
(5173/8110 free, zero `postgres` processes; the user's Strata server was never stopped).

---

## 11. Limits and recommended next steps

**Limits.** The READY result uses a **non-app-native** runtime, so it proves the *verification path*,
not that the app can serve work locally. The media chain covers only the model-free steps. The GPU
fix is validated on one machine with one aliasing topology; the identical-GPU branch is covered by
unit tests, not by a second physical GPU. Hindsight memory was unavailable.

**Recommended order for the next phase:**

1. **Register an observed runtime deliberately and route one real task through it** — this is the
   single change that moves "live local runtime end-to-end" off `LOCAL_REQUIRED`, and the gated
   descriptor already exists.
2. **Close the client gap found in §4** (no readable `edit_version`) — small, and it blocks any scripted
   client from completing the chain without an export round-trip.
3. **Run the media chain's model-dependent steps** once an image/video/audio runtime exists, filling
   the `BLOCKED` rows with real artefacts and digests.
4. **Clean-machine Windows pass** (install / launcher / DesktopHost / recovery) — the largest
   remaining blocker.
5. **Export packaging**, then a full-CI attempt or an explicit decision to stay
   `BLOCKED_ACCOUNT_PLATFORM`.
6. **Optional hardening surfaced earlier and still open:** the frontend's duplicate port table
   (Phase10 C1) and `validate_output_ports`'s `schema_version=None` default.
