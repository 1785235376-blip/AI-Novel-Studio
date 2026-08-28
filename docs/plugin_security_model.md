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
- `PLUGIN_RESOURCE_PATH_INVALID`
- `PLUGIN_RESOURCE_TYPE_UNSUPPORTED`
- `PLUGIN_RESOURCE_TOO_LARGE`
- `PLUGIN_RESOURCE_HASH_MISMATCH`
- `PLUGIN_RESOURCE_INVALID_JSON`
- `PLUGIN_RESOURCE_SYMLINK_REJECTED`

Messages are author-safe and user-readable. They do not include the failed path.

## Publisher trust

`publisher` is optional display metadata. The host always treats it as unverified. Absence of a signature is not displayed as “signed”.

## Still out of scope

Isolated worker, capability broker, plugin signatures, marketplace, Provider plugins, and any third-party code execution remain unimplemented. See the deferred worker design document in a later phase.
