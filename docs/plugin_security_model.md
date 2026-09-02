# Plugin Security Model (Declarative v1)

Plugin code execution is **disabled**. The host scans, validates, and stores metadata. It does not run third-party code.

## Current enforcement

| Control | Value |
|---|---|
| Execution | denied (`execution_supported = false`) |
| Sandbox | `NOT_CONFIGURED` |
| Isolation | `DENY_ALL` |
| Default permission policy | deny |
| Publisher field | unverified metadata |
| Plugin runtime (release readiness) | `DEFERRED` |

Activation of a manifest is not execution. Reviewing permissions does not grant a runtime.

## Discovery boundary

- Scan only the host-controlled plugins root (`<data_path>/plugins/*/manifest.json`)
- One invalid package must not block other packages
- Do not read `.env`, Credential Vault, or novel project text
- Do not fetch URLs found inside JSON
- Do not import, eval, or execute strings inside JSON

## Path and integrity guards

Resource `relative_path` values must stay inside the plugin directory:

- Relative POSIX-style paths only (`resources/foo.json`)
- Absolute paths, Windows drives, and UNC paths are rejected
- `..`, `.`, backslash, and percent-encoded traversal variants are rejected
- After `resolve()`, the file must still be inside the plugin root
- Symlink / reparse points that escape the plugin root are rejected
- Resource files themselves may not be symlinks
- SHA-256 must match the bytes on disk
- JSON must parse as an object or array; strings inside it are data, not code

## API disclosure

`GET /plugins/discover` returns a **relative** plugin directory identifier, never:

- Absolute filesystem paths
- User names or drive letters
- Stack traces
- File contents
- Raw `str(exception)`

Stable error codes:

- `PLUGIN_MANIFEST_INVALID`
- `PLUGIN_MANIFEST_UNSUPPORTED_VERSION`
- `PLUGIN_MANIFEST_DRIFT`
- `PLUGIN_ID_DUPLICATE`
- `PLUGIN_RESOURCE_PATH_INVALID`
- `PLUGIN_RESOURCE_TYPE_UNSUPPORTED`
- `PLUGIN_RESOURCE_TOO_LARGE`
- `PLUGIN_RESOURCE_HASH_MISMATCH`
- `PLUGIN_RESOURCE_INVALID_JSON`
- `PLUGIN_RESOURCE_SYMLINK_REJECTED`

Duplicate plugin IDs fail closed on **discovery, registration, activation, and catalog reads**. Registration preflight runs before any sidecar, audit, or idempotency write: two or more live packages with the same `id` return HTTP 409 `PLUGIN_ID_DUPLICATE` and leave storage unchanged. The submitted manifest must match the unique on-disk canonical identity (`plugin_version`, `manifest_sha256`, capabilities, requested permissions, resources); a mismatch returns HTTP 409 `PLUGIN_MANIFEST_DRIFT` with no sidecar mutation.

## Catalog re-verification

`GET /plugins/{plugin_id}/resources` is not a cache. Every read:

- Resolves the plugin package by live scan of the plugins root
- Requires the registered plugin to be `MANIFEST_ACTIVE`
- Re-validates each resource path, type, size and SHA-256
- Treats **package budget** (more than 100 resources, any file over 1 MiB, or more than 10 MiB **actual bytes read**) as a whole-package `BUDGET` failure before JSON is parsed. `stat` size is a fast reject only; the security boundary is a read-once snapshot. Hash-mismatched and invalid JSON payloads still count toward the 10 MiB total; missing, path, and symlink faults do not.
- Treats a single missing file, path error, symlink/reparse, hash mismatch, or invalid JSON as a **per-resource** failure: siblings that still verify remain listed (`PARTIAL`), and a valid resource detail is not failed because an unrelated resource is missing
- Returns nothing for a missing directory, duplicate id, or drifted identity
- Never writes plugin files, fetches URLs, or follows escaped symlinks

HTML and script-like strings in JSON are treated as plain data. Summary fields strip tags; the host never renders them as markup.


## Publisher trust

`publisher` is optional display metadata. The host always treats it as unverified. Absence of a signature is not displayed as “signed”.

## Still out of scope

Isolated third-party worker, capability broker runtime, plugin signatures, marketplace, Provider plugins, and any third-party code execution remain unimplemented. Phase 1 added typed execution contracts and a pure fail-closed policy evaluator. Phase 2A added a host-owned **test** worker (not a plugin). Independent review showed the first spawn inherited `PYTHONPATH` and could execute attacker `sitecustomize` / stdlib shadows; a correction now uses `python -I -S -u <host-owned-bootstrap>` and an environment allowlist. That is Python startup isolation, not an OS sandbox. Phase 2B adds a **fail-closed Windows AppContainer prototype** around that same Host-owned test worker (ctypes, staged runtime copy, no unsandboxed fallback). Real Windows `TokenIsAppContainer` proof is **REQUIRED / NOT RUN** on Linux isolation hosts. Job Object is resource containment only and is not the sandbox. `execution_supported` stays `false`. `os_sandbox_ready` stays `false`. See [plugin_runtime_foundation_phase1.md](plugin_runtime_foundation_phase1.md), [plugin_runtime_phase2a_test_worker.md](plugin_runtime_phase2a_test_worker.md), [plugin_runtime_phase2b_windows_sandbox.md](plugin_runtime_phase2b_windows_sandbox.md), and [plugin_worker_runtime_design.md](plugin_worker_runtime_design.md).
