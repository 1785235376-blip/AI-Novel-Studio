# Plugin Runtime — Phase 2B Windows AppContainer Sandbox Prototype

Status: **Windows AppContainer prototype, fail-closed, not production-ready.**

This is **not** third-party plugin execution.

| Claim | Value |
|---|---|
| WINDOWS APPCONTAINER PROTOTYPE | IMPLEMENTED (ctypes, fail-closed) |
| WORKER TOKEN IS APPCONTAINER | **REQUIRED / NOT RUN** on this Linux isolation host |
| APPCONTAINER PROTOTYPE gate | **BLOCKED** until a real `win32` host proves `TokenIsAppContainer=true` |
| LPAC | NOT IMPLEMENTED |
| Job Object | IMPLEMENTED as **resource / process containment only** |
| Job Object role | `KILL_ON_JOB_CLOSE` + `ActiveProcessLimit=1` + optional 512 MiB process memory. **Not a security sandbox.** |
| Sandbox fallback to normal process | **NONE** (fail-closed) |
| Third-party plugin Worker | NOT IMPLEMENTED |
| Third-party plugin code execution | DISABLED |
| Plugin package code loading | 0 |
| `execution_supported` | `false` |
| Isolation | `DENY_ALL` |
| OS sandbox ready for third-party execution | `false` |
| `os_sandbox_ready` | `false` / `NOT_CONFIGURED` |
| Capability Broker runtime | NOT IMPLEMENTED |
| Credential resolver | NOT IMPLEMENTED |
| Signature verification | NOT IMPLEMENTED |
| Provider / Blender / ComfyUI plugins | NOT IMPLEMENTED |
| Marketplace | NOT IMPLEMENTED |
| Public execute API | none |
| Run Plugin UI | none |
| Database schema / migrations | 0 |
| Frontend production changes | 0 |
| Dependency changes | 0 (ctypes / stdlib only; no pywin32) |
| Release claim | `0.7.0 Beta` (unchanged) |

Phase 2B proves (when a real Windows host is available) that the **Host-owned Test Worker** can be launched inside a real Windows security boundary that denies Host resources by default, and that failure never falls back to unsandboxed execution.

It does **not** run plugin packages. Shipping these modules does not enable production plugin execution.

Related: [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md), [plugin_runtime_foundation_phase1.md](plugin_runtime_foundation_phase1.md), [plugin_security_model.md](plugin_security_model.md), [plugin_worker_runtime_design.md](plugin_worker_runtime_design.md).

## First gate: real Windows Phase 2A

The Phase 2B pass bar requires a real Windows host (`sys.platform == "win32"`, not a mock) to first prove Phase 2A spawn / handshake / PING / timeout / cancel / crash / hostile `PYTHONPATH` isolation.

| Field | Value |
|---|---|
| WINDOWS REAL PHASE2A BASELINE | **REQUIRED / NOT RUN** |
| WINDOWS VERSION | not collected (this builder is Linux) |
| WINDOWS BUILD | not collected |
| ARCH | not collected |
| PYTHON VERSION | Linux CPython 3.11 used for cross-platform tests only |

This Linux isolation host cannot satisfy that gate. `APPCONTAINER PROTOTYPE = PASS` is therefore **BLOCKED**. The ctypes prototype is still landed so a Windows reviewer can run the real tests without first inventing the adapter.

## Implemented

| Surface | Module |
|---|---|
| Stable sandbox reason codes | `app/plugin_worker_sandbox_errors.py` |
| Win32 ctypes (AppContainer, Job Object, ACL, pipes) | `app/plugin_worker_windows_api.py` |
| Per-run staging + AppContainer launcher | `app/plugin_worker_windows_sandbox.py` |
| Frozen spawn | `spawn_sandboxed_host_test_worker()` (no executable/args/env/cwd) |
| Supervisor entry | `HostTestWorkerSupervisor.start_sandboxed_test_worker()` |
| Fixed probes | `PROBE_ALLOWED_READ/WRITE`, `PROBE_FORBIDDEN_HOST_READ/WRITE`, `PROBE_NETWORK`, `PROBE_CHILD_PROCESS`, `PROBE_TOKEN_IDENTITY` |

`GET /api/plugins/runtime-status` is unchanged: `execution_supported=false`, `sandbox=NOT_CONFIGURED`, `isolation=DENY_ALL`. Production startup (`app.main`) does **not** import or spawn the sandbox worker.

## What this sandbox is

A Host-owned AppContainer around the existing Host-owned Test Worker:

```
Host → Supervisor → CreateAppContainerProfile
                 → staged runtime + worker
                 → CreateProcess(SECURITY_CAPABILITIES, CapabilityCount=0)
                 → Job Object (resource containment)
                 → TokenIsAppContainer must be true or abort
                 → handshake / fixed probes
```

Host-owned still means:

1. Host chooses the executable (staged copy of the Host interpreter, never a plugin binary)
2. Host chooses the bootstrap file
3. Host controls the import path (`-I -S -u` + staged `app/` only)
4. Host places that process in a real Windows AppContainer

Python `-I -S` is **not** an OS sandbox. A Job Object is **not** a security sandbox.

## Fail-closed

Any of these aborts the launch and **must not** call `spawn_host_test_worker()`:

- non-Windows (`WINDOWS_SANDBOX_UNAVAILABLE`)
- profile create / SID derive failure
- ACL failure
- attribute-list / `CreateProcess` failure
- Job assignment failure
- `TokenIsAppContainer == 0` (`SANDBOX_TOKEN_VERIFICATION_FAILED`)
- Python runtime cannot be copied into staging (`PYTHON_APPCONTAINER_COMPATIBILITY_BLOCKED`)

There is no “Job Object only” fallback. If AppContainer cannot start, `OS SANDBOX READY = FALSE`.

## Profile lifecycle

Each test run uses a Host-owned unique profile:

```
AI-Novel-Studio.TestWorker.<16 hex chars>
```

Create → derive SID → launch → cleanup/delete. Plugin code cannot choose the name. Tests assert leftover profiles and staging directories return to zero after shutdown.

## Staging

Sandbox does not run the whole repo. Per-run tree:

```
.runtime/plugin-sandbox/<run_id>/
  staging/
    app/          # bootstrap, worker, protocol, __init__.py   READ+EXECUTE
    runtime/      # copied python.exe + stdlib/DLLs            READ+EXECUTE
    in/           # Host-written input.txt                     READ
    out/          # Worker output                              WRITE
    tmp/          # Worker TEMP/TMP                            WRITE
  host/           # forbidden sentinels; no AppContainer ACL
```

Allowlisted staged worker files:

- `plugin_test_worker_bootstrap.py`
- `plugin_test_worker.py`
- `plugin_worker_protocol.py`

Not copied: `.env`, database, Vault, credentials, plugin packages, user documents, the rest of `app/`, the repo.

`SANDBOX STAGED FILE COUNT` / `SANDBOX STAGED BYTES` are recorded on `SandboxLaunch` and printed by Windows tests. They are **not** claimed here because this host never staged a Windows runtime.

### Why the runtime is copied

AppContainer needs execute access to `python.exe` and the stdlib. Granting that ACL on the real Python installation would mutate a shared system directory. **Hardlinks are forbidden** for the same reason: ACLing a hardlink ACLs the original file.

Phase 2B therefore `shutil.copy2`s a per-run runtime into staging and ACLs **only** that copy. This is a prototype packaging strategy, not a committed binary runtime. Do not check tens of MB of CPython into git.

If a given Windows Python distribution still cannot start inside AppContainer without ACLing `Program Files`, the user profile, or the repo root: **STOP**. `PYTHON APPCONTAINER COMPATIBILITY = BLOCKED`. Future work is a Host-owned packaged/embedded Worker Runtime, not a wider ACL.

## ACL policy

AppContainer SID is granted:

| Path | Access |
|---|---|
| `staging/` | traverse / read |
| `staging/app`, `staging/runtime` | read + execute |
| `staging/in` | read |
| `staging/out`, `staging/tmp` | write (+ delete) |
| Host user on those paths | `FILE_ALL_ACCESS` (so Host can clean up) |

Not granted: repo root, user home, arbitrary drives, Python installation, `host/` sentinels.

DACLs are protected (no inherited parent ACEs) and exist only on the staging tree. Cleanup `rmtree`s the per-run directory.

## Fixed probes (not a generic runner)

Probe operations take **no path, URL, command, or executable** in the IPC payload. Extra fields are rejected (`UNKNOWN_FIELD`). The Host sets sentinel locations via environment variables it controls (`ANS_SANDBOX_IN/OUT/TMP`, `ANS_PROBE_FORBIDDEN_READ/WRITE`, `ANS_PROBE_LOOPBACK_PORT`).

| Probe | Expected on a passing Windows host |
|---|---|
| `PROBE_ALLOWED_READ` | can read `in/input.txt` |
| `PROBE_ALLOWED_WRITE` | can write `out/` and `tmp/`; write to `in/` denied |
| `PROBE_FORBIDDEN_HOST_READ` | denied; secret must not leak |
| `PROBE_FORBIDDEN_HOST_WRITE` | denied; Host file unchanged |
| `PROBE_NETWORK` | loopback connect denied (no network capabilities, no loopback exemption) |
| `PROBE_CHILD_PROCESS` | denied or job-killed (`ActiveProcessLimit=1`); reported honestly |
| `PROBE_TOKEN_IDENTITY` | `is_appcontainer=true`, SID present |

Forbidden: `PROBE_FILE(path)`, `PROBE_NETWORK(host, port)`, `RUN(command)`, generic `spawn_sandboxed(executable, args, env, cwd)`.

The worker still must not `import subprocess`. Child-process probe uses `os.spawnv` only.

## Network

`SECURITY_CAPABILITIES.CapabilityCount = 0`. No `internetClient`, `internetClientServer`, `privateNetworkClientServer`. No `CheckNetIsolation` loopback exemption. Host may bind a local loopback listener for the probe; the Worker must not connect. External network requests = 0.

## Job Object (not the sandbox)

Job Object wraps the AppContainer process for:

- `KILL_ON_JOB_CLOSE`
- `ActiveProcessLimit = 1`
- process memory 512 MiB when `SetInformationJobObject` accepts `JOB_OBJECT_LIMIT_PROCESS_MEMORY`

If the memory limit cannot be set on a given Windows build, launch still proceeds with process-limit + kill-on-close, and `memory_limit_ready=false`. That is **OS MEMORY LIMIT = NOT READY**, not a Phase 2B merge blocker, and not a substitute for AppContainer.

Closing the Job Object must kill the worker.

## Token proof

The launcher calls `GetTokenInformation(TokenIsAppContainer=19)` on the **created process token** while the thread is still suspended. If it is not an AppContainer, the process is terminated and the launch raises `SANDBOX_TOKEN_VERIFICATION_FAILED`. A boolean flag in Python is not proof.

LPAC is **not** implemented in this phase.

## Non-Windows

Phase 2A continues to work on Linux/macOS. Phase 2B APIs raise `WINDOWS_SANDBOX_UNAVAILABLE` and do not spawn a normal worker.

## Production reachability

| Path | Sandbox spawn |
|---|---|
| `app.main` / FastAPI / catalog / UI / DesktopHost | 0 |
| `start_test_worker()` | unsandboxed Phase 2A worker only (tests) |
| `start_sandboxed_test_worker()` | tests only; fail-closed off Windows |

## Not implemented

- Capability Broker runtime, scoped Host APIs, credential handle resolver
- Signing / publisher trust / revocation
- Third-party plugin execution, official pack execution, Python/JS/Blender/ComfyUI/Provider plugins
- `POST /api/plugins/.../execute`, Run Plugin UI, Worker Console
- LPAC
- CPU rate control
- Claiming `os_sandbox_ready=true` or `execution_supported=true`

Phase 3 (not this PR) would be Capability Broker runtime + scoped Host APIs + credential handle resolver, coordinated with Issue #18. This PR does not close Issue #15 or #18.

## Pass bar (not met on this host)

`APPCONTAINER PROTOTYPE = PASS` only if a real Windows run proves:

- `WORKER TOKEN IS APPCONTAINER = TRUE`
- forbidden Host read/write denied
- sandbox input read pass, input write denied, output write pass
- network denied, no fallback, profile/handle cleanup pass

Otherwise **BLOCKED / FAIL**. Meeting that bar still leaves:

- `OS SANDBOX READY FOR THIRD-PARTY EXECUTION = FALSE`
- `EXECUTION_SUPPORTED = FALSE`

## Tests

- Cross-platform: `tests/test_plugin_runtime_phase2b_windows_sandbox.py` (fail-closed, no fallback, production startup, protocol probes, source policy)
- Windows-only (`skipif sys.platform != "win32"`; **must run on Windows**, no xfail): token, ACL probes, network, child containment, timeout/cancel/crash/IPC, job-close kill, 20× lifecycle cleanup
- Phase 2A tests remain required and must not be weakened

## Verification on this Linux host

Windows real AppContainer proof: **NOT RUN**. Targeted Linux tests must stay green. Known product baseline failures (visual continuity, user preference, world-rule payload) stay classified separately and must not be “fixed” here.
