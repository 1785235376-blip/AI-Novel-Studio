# WINDOWS_GPU_RC_CHECKLIST — Phase11 P3

**Nature:** the operator checklist for Windows install/launch/recovery and for RTX 5080 GPU
validation at release-candidate level. This is preparation: **no installer was produced, no
packaged runtime was launched, and no image or video was generated for it.**

**Baseline:** `3f97b34` (`feature/v2-narrative-platform`, PR #47 OPEN/draft).

**Status vocabulary:** `PASS` · `PARTIAL` · `BLOCKED` · `NOT_RUN`, plus `BLOCKED_EXTERNAL` for
a host-caused failure that is not a product defect.

**Iron rule:** a **cloud** or remote-provider result may never be recorded as a local result.
`MOCK_PROVIDER` output may never be recorded as real generation. An unexecuted item stays
`NOT_RUN`.

---

## 1. Measured host facts (this machine, this phase — not assumed)

| Fact | Value | How measured |
| --- | --- | --- |
| OS | Microsoft Windows 11 专业版, version `10.0.26100`, build `26100` | `Get-CimInstance Win32_OperatingSystem` |
| Architecture | AMD64 | passive inventory |
| CPU | 20 logical processors | `Get-CimInstance Win32_Processor` |
| RAM | 63.6 GiB (`68 291 530 752` bytes) | `Win32_ComputerSystem` / passive inventory |
| **GPU** | **1 × NVIDIA GeForce RTX 5080**, UUID `GPU-b277f34d-a119-3743-8465-3dc06aa151bc` | `nvidia-smi -L` |
| Driver | `591.74` | `nvidia-smi --query-gpu=driver_version` |
| **VRAM total** | **16 303 MiB** | `nvidia-smi --query-gpu=memory.total` |
| VRAM in use (at measurement) | 4 923 MiB | `nvidia-smi --query-gpu=memory.used` |
| Compute capability | 12.0 | `nvidia-smi --query-gpu=compute_cap` |
| App's own CUDA / DirectML verdict | `COMPONENT_FOUND_NOT_VERIFIED`, `inference_verified: false` | `windows_acceleration_components()` |
| Python | `C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe` | verified |
| Node / pnpm | node `v22.14.0`; pnpm via `corepack` | verified |
| Portable PostgreSQL | `16.15` (reusable cluster; no system service installed) | Phase10 `phase10-a1-r4-postgres-runtime.json` |
| ffmpeg / ffprobe | present at `D:\ffmpeg\ffmpeg-8.1.2-essentials_build\bin` | `Get-Command` |
| `bash` | **absent** | `Get-Command bash` |

Receipts: `docs/delivery/v2-development/phase11-host-inventory.json`,
`phase11-browser-acceptance.json`.

---

## 2. Windows checklist

| # | Item | What to verify | Owner | Status |
| --- | --- | --- | --- | --- |
| W1 | **Clean install** | On a clean Windows machine: install, first start, no pre-existing config, Chinese and space-containing paths, long paths, uninstall leaves no orphan service or directory | `app/packaging/*`, installer (none produced yet) | `NOT_RUN` |
| W2 | **Launcher** | The launcher resolves the backend, applies the launch profile and reports a machine-readable failure instead of a silent exit | `app/packaging/packaged_launcher.py`, `launch_profiles.py`, `paths.py` | `NOT_RUN` |
| W3 | **Backend** | Starts and serves on a supported port; refuses an excluded port clearly | `app/main.py` (`uvicorn app.main:app`) | `PASS` **for the dev invocation only** — started on `127.0.0.1:8110` with `STORAGE_BACKEND=file` and the `narrative_production_v2` opt-in, `/docs` returned 200, then stopped cleanly (Phase11 P1). The **packaged** backend remains `NOT_RUN`. |
| W4 | **DesktopHost** | Host uplink, control pipe, bootstrap and trusted session behave under the packaged runtime | `app/packaging/packaged_desktop_host.py`, `host_uplink.py`, `control_pipe.py`, `local_session_bootstrap.py` | `NOT_RUN` — `ENABLE_PACKAGED_RUNTIME=false` in the verified runner environment; the packaged path was never exercised |
| W5 | **PostgreSQL** | Fresh database, all migrations applied, database empty before migration, clean stop, retained evidence | `scripts/run_v2_postgres_checks.py`, `database/migrations/*.sql` | `PASS` **for the portable cluster** — Phase10 `phase10-a1-r4` verified a fresh DB, empty-before-migrations, all 20 migrations applied and `server_stop: stopped`. **Installed-service** and clean-machine variants remain `NOT_RUN`. |
| W6 | **Recovery** | Restart recovery after a killed backend; backup and restore round-trip; an interrupted write leaves no half-written artefact | `scripts/backup.ps1`, `scripts/restore.ps1`, autosave (`app/autosave/*`) | `NOT_RUN` |

### Port facts that decide W1–W3

* **8000 is unusable** — Windows excluded port range, held by PID 4.
* **8100 is now occupied** by the unrelated ASUS `GearLink_KBService.exe`; do not reuse the
  Phase9 port.
* 8110 was verified free and used for the Phase11 browser acceptance.

---

## 3. GPU checklist (RTX 5080)

| # | Item | What to verify | Status |
| --- | --- | --- | --- |
| G1 | **CUDA stack** | The app can actually execute a kernel-backed inference path — not merely that a component exists | `NOT_RUN` — the app reports `COMPONENT_FOUND_NOT_VERIFIED` and `inference_verified: false`, which is the honest verdict; the driver advertises compute capability 12.0 but no app inference has been run |
| G2 | **VRAM** | Total VRAM and **headroom at load time**; behaviour when a model exceeds available VRAM | `PASS` for measurement (16 303 MiB total, 4 923 MiB in use, measured), `NOT_RUN` for load-time behaviour |
| G3 | **Model load** | Load a real local model through the app's own Model Center and observe load, unload and failure paths | `NOT_RUN` — no app-native model has been loaded on this host |
| G4 | **Image generation** | One real image through the Image step, with artefact, digest and version recorded | `NOT_RUN` |
| G5 | **Video generation** | One real video through the Video step, with artefact, duration, codec, digest and version recorded | `NOT_RUN` |

**G2 caveat that must not be misread:** 4 923 MiB of the 16 303 MiB was already in use at
measurement time because a **separate** local model server (Strata, on `127.0.0.1:8080`) was
holding a model. That usage belongs to another product, must not be attributed to
AI-Novel-Studio, and means GPU acceptance must record free VRAM at the moment of the run rather
than the nominal total.

---

## 4. Findings requiring a decision (recorded, not silently changed)

**F1 — the passive inventory double-counts the GPU.** `nvidia-smi -L` reports exactly **one**
RTX 5080, but `host_hardware()` returns **two** entries with identical vendor, name and
`dedicated_vram_bytes` (`16 753 098 752` each). Any consumer that counts GPUs or sums VRAM
would therefore double both. This was left as-is on purpose: changing hardware reporting is a
functional change to a surface that feeds hardware profiles and VRAM checks, and Phase11 is a
validation phase. **Recommended next step:** decide whether the probe should de-duplicate
identical records, and cover it with a test before the change.

**F2 — the app's CUDA verdict is honest and must stay that way.** `COMPONENT_FOUND_NOT_VERIFIED`
with `inference_verified: false` is the correct shape; a "CUDA available" claim requires a real
executed inference, not a detected component. Phase11's runtime observation layer keeps the same
discipline (level 4 `CAPABILITY_UNKNOWN` is not level 5 `READY`).

**F3 — no local runtime the app can use has been found on this host.** Ollama 11434, LM Studio
1234 and ComfyUI 8188 have no listener at all (Phase11 live observation, level 0
`NOT_OBSERVED`). GPU items G3–G5 therefore cannot pass until either an app-native runtime is
installed or an observed endpoint is deliberately registered.

---

## 5. Completion criteria

1. W1–W6 each executed on a **clean** Windows machine, with the failing paths exercised, not
   only the happy path.
2. G1–G5 each executed **locally**, with real artefacts, digests and versions recorded.
3. No cloud or mock result occupies a local-result cell.
4. Free VRAM is recorded at run time, and Strata's separate GPU usage is never counted as the
   app's.
5. Environment-only failures are labelled `BLOCKED_EXTERNAL` and are never made green by
   editing an assertion, adding a skip, or deleting a case.
