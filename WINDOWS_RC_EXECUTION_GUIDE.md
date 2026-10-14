# WINDOWS_RC_EXECUTION_GUIDE — Phase12 P3

**Nature:** the execution guide for running the Windows release-candidate acceptance on a
**clean** machine. This document prepares and specifies the run; it does **not** perform it.
Every execution item below is therefore `NOT_RUN` unless it is explicitly marked as already
verified on this development host.

**Baseline:** `82d1282` (`feature/v2-narrative-platform`, PR #47 OPEN/draft).

**Status vocabulary:** `PASS` · `PARTIAL` · `BLOCKED` · `NOT_RUN`, plus `BLOCKED_EXTERNAL` for a
failure caused by the host environment rather than by the product.

**Non-negotiable rules**

1. A **cloud or remote-provider** result never fills a local-result cell.
2. A **mock** (`MOCK_PROVIDER=true`) output never counts as real generation.
3. An **environment** failure is recorded as `BLOCKED_EXTERNAL`; it is never made green by
   editing an assertion, adding a skip or deleting a case.
4. Un-run stays `NOT_RUN`. Nothing is inferred forward from a passing unit test.

---

## 1. Verified preconditions on the development host

Measured in Phase11/Phase12; they describe the machine the guide was written on, not a guarantee
for the clean machine.

| Fact | Value |
| --- | --- |
| OS / CPU / RAM | Windows 11 Pro `10.0.26100` build 26100, Intel Core Ultra 7 265KF (20 logical), 63.6 GiB |
| GPU | **1 × RTX 5080**, driver `591.74`, **15 977 MiB** usable VRAM (16 303 MiB total), compute `12.0` |
| Python | `C:\Users\admin\AppData\Local\Programs\Python\Python311\python.exe` (3.11); Strata uses a separate 3.12 |
| Node | `v22.14.0`; pnpm via `corepack` |
| PostgreSQL | reusable portable cluster **16.15** (no system service installed) |
| Tools | `ffmpeg`/`ffprobe` present (`D:\ffmpeg\…`); **`bash` absent** |
| GPU identity | fixed in `82d1282` — DXGI aliased one GPU as two adapters, which had reduced the host to no GPU capability at all |

**Port constraints that decide most of this guide**

* **8000 is unusable** — Windows excluded port range, held by PID 4.
* **8100 is occupied** by the unrelated ASUS `GearLink_KBService.exe` (do not reuse the Phase9 port).
* **8080** serves the local **Strata** model server (not an AI-Novel-Studio runtime).
* Verified free and used for acceptance: **8110** (backend), **5173** (Vite, IPv4 when
  `--host 127.0.0.1` is passed).

---

## 2. Clean Windows: install, uninstall, first start

Run on a freshly imaged machine with **no** prior config, cache or service.

| Step | Command / action | Expected evidence | Status |
| --- | --- | --- | --- |
| 2.1 Install | run the installer (none produced yet) | installer exit code, installed tree, no console window left behind | `NOT_RUN` |
| 2.2 First start | launch once with no pre-existing config | app reaches its start surface; a blank project can be created; no crash dialog | `NOT_RUN` |
| 2.3 Storage bootstrap | first start creates the schema | `app/packaging/database_bootstrap.py` + `app/packaging/postgres_migrations.py` applied all migrations; database empty before migration | `NOT_RUN` |
| 2.4 Service hygiene | inspect after first start | no orphan service, no listening port other than the configured ones, no leftover temp dirs | `NOT_RUN` |
| 2.5 Uninstall | uninstall, then re-image check | program files removed; **user data policy stated explicitly**; no orphan service or registry entry | `NOT_RUN` |

Evidence to capture per step: a screenshot-free machine transcript, the installer log, the
listening-port table, and the migration list with hashes.

---

## 3. Path tests

Each variant is a full first-start + save + reopen cycle in the same session.

| Variant | Example path | What it actually exercises | Status |
| --- | --- | --- | --- |
| Chinese path | `D:\小说工程\AI 小说工作室` | UTF-8 handling end to end: data dir, SQLite/file store, export names, log encoding | `NOT_RUN` |
| Space path | `D:\AI Novel Studio\data` | argument quoting in launcher, PG service args, subprocess invocations, script paths | `NOT_RUN` |
| Long path | a nested path exceeding 260 chars | whether the `\\?\` long-path opt-in is honoured: manifest/`LongPathsEnabled`, and every native call that takes a path | `NOT_RUN` |
| Combined | Chinese + spaces + long | the realistic worst case; report which layer fails first if any | `NOT_RUN` |

**Expected failure signature to watch for:** path truncation, `OEM`/`mbcs` mojibake in logs, or
`[WinError 3]`/`[WinError 206]` (filename too long). A long-path failure is a real defect, not an
environment quirk, unless the OS long-path policy itself is off — which must be stated explicitly
in the record.

---

## 4. Runtime chain

| Stage | Owner | Verify | Status |
| --- | --- | --- | --- |
| Launcher | `app/packaging/packaged_launcher.py`, `launch_profiles.py`, `paths.py` | resolves the backend, applies the launch profile, reports a machine-readable failure instead of exiting silently | `NOT_RUN` |
| Backend | `app/main.py` (`uvicorn app.main:app`) | starts on a supported port, `/docs` 200, refuses an excluded port clearly | `PASS` **(dev invocation only)** — started on `127.0.0.1:8110`, `/docs` returned 200, stopped cleanly (Phase11 P1). The **packaged** backend is `NOT_RUN` |
| Storage | `app/packaging/database_bootstrap.py`, `scripts/run_v2_postgres_checks.py` | fresh DB, empty-before-migrations proof, all 20 migrations, clean stop | `PASS` **(portable cluster)** — Phase10 `phase10-a1-r4`. Installed-service and clean-machine variants are `NOT_RUN` |
| DesktopHost | `app/packaging/packaged_desktop_host.py`, `host_uplink.py`, `control_pipe.py`, `local_session_bootstrap.py` | host uplink + control pipe + trusted session under the packaged runtime | `NOT_RUN` — `ENABLE_PACKAGED_RUNTIME=false` in the verified environment, so the packaged path has never been exercised |
| Frontend | Vite / packaged static frontend (`app/packaging/static_frontend.py`) | dev Vite serves the shell; the packaged build serves it **without** Vite | `NOT_RUN` for packaged; the dev path is `PASS` (Phase11 8/8 browser acceptance) |

PostgreSQL runner syntax that actually works (four traps; see `docs/troubleshooting.md`):

```powershell
python scripts/run_v2_postgres_checks.py --pg-bin <portable PG bin> --data <cluster data> `
  --port 55433 --database v2_<new name> --fresh-database <label> `
  -- <absolute python> -m pytest <files> -q --basetemp <existing dir> -p no:cacheprovider
```

`--user` is the **connect role** (default `postgres`), the label is **positional**, `--basetemp`
must **already exist**, and the interpreter must be an **absolute path**.

---

## 5. Recovery

| Scenario | How to provoke it | Expected behaviour | Status |
| --- | --- | --- | --- |
| Restart | stop the backend, restart it | saved work reopens at the same revision; no duplicate assets; version counters continue | `NOT_RUN` |
| Crash recovery | kill the backend process mid-write | no half-written artefact; the interrupted operation is reported unknown rather than silently retried | `NOT_RUN` |
| Cache recovery | delete the local cache, restart | rebuilds without data loss; never presents stale facts as current | `NOT_RUN` |
| Autosave | leave unsaved edits, kill the process | `app/autosave/*` (`dirty_state`, `durable`, `coordinator`, `scheduler`) preserves or explicitly refuses the unsaved state | `NOT_RUN` |
| Backup / restore | `scripts/backup.ps1` then `scripts/restore.ps1 -BackupPath …` | checksum manifest verified; restore refuses to overwrite an existing novel by default (`app/backup_restore.py`) | `NOT_RUN` |
| Migration 4060→5080 | `scripts/migrate.ps1 -Destination …` | model blobs not copied; only the profile and model re-install are needed | `NOT_RUN` |

**Evidence per scenario:** before/after directory listing, the receipt or its explicit absence,
and the exact user-visible string. A silent retry is a defect even when the final state looks right.

---

## 6. GPU (RTX 5080)

| Step | Verify | Status |
| --- | --- | --- |
| 6.1 GPU identity | the physical count is 1 and capability is not lost — regression-tested by `tests/test_v2_gpu_physical_identity.py` (two live acceptance tests) | `PASS` **(unit + live on this host)** |
| 6.2 VRAM | record **free** VRAM at run time, not the nominal total: 15 977 MiB usable here, and ~4.9 GiB was already held by the separate Strata server | `PASS` for measurement; load-time behaviour `NOT_RUN` |
| 6.3 CUDA | a real kernel-backed inference, not a detected component — the app's own verdict must stay `COMPONENT_FOUND_NOT_VERIFIED` until then | `NOT_RUN` |
| 6.4 Model load | load a real local model through Model Center; observe load, unload and failure paths | `NOT_RUN` |
| 6.5 Image generation | one real image with artefact, digest and version recorded | `NOT_RUN` |
| 6.6 Video generation | one real video with duration, codec, digest and version recorded | `NOT_RUN` |

**Never attribute another product's GPU usage to this app.** Strata holds VRAM on this machine; its
usage is not evidence about AI-Novel-Studio and must not be counted in any VRAM headroom figure.

---

## 7. Completion criteria

1. Sections 2, 3, 4, 5 and 6.3–6.6 all executed on a clean machine, with the failure paths
   exercised and not only the happy path.
2. Every row carries either a real artefact/receipt or an explicit `NOT_RUN`/`BLOCKED_EXTERNAL`.
3. No cell is filled from a cloud, mock or synthetic result.
4. A clean-machine run is the only thing that can move install/uninstall, launcher, DesktopHost
   and packaged-storage off `NOT_RUN`.
