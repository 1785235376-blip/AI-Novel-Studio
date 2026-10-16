# Explicit Windows V2 packaged profile

This is an opt-in composition of the existing packaged runtime, not a second
authentication system or a claim of completed native Windows acceptance.

## Entry and build

Build the current application with the existing pinned workflow in
[`R2_WINDOWS_BASE_INPUTS.md`](../R2_WINDOWS_BASE_INPUTS.md). The full package uses
SDK 8.0.424 and the original WebView2 Host, bundled Python 3.12 and PostgreSQL 16.
WebView2 Evergreen and the VC++ x64 runtime remain machine prerequisites.

After verifying a fresh package, use its existing launcher with an explicit
profile and separately chosen test roots, for example:

```powershell
& 'D:\VerifiedPackage\Application\Launcher\Launch-AI-Novel-Studio.ps1' `
  -ApplicationRoot 'D:\VerifiedPackage\Application' `
  -LocalAppDataRoot 'D:\OwnedV2Check\Local' `
  -UserProfileRoot 'D:\OwnedV2Check\Profile' `
  -LaunchProfile v2
```

`-Profile v2` is an alias for `-LaunchProfile v2`. The corresponding bundled
Python entry is `app.packaging.packaged_desktop_launcher --profile v2`; its
existing application/data arguments are unchanged. Omitting the selector, or
using `default`, retains the original package profile. Unknown profiles fail
before runtime creation. Ordinary inherited feature flags do not select V2.

No provider/model is configured, registered, licensed, enabled, started or
dispatched by this profile. Real local-model work still requires the existing
Model Center scope confirmation, validation, registration and explicit model
review/dispatch flow. Do not run a development-token utility to authenticate it.

## Existing owners and boundaries

- The original launcher owns PostgreSQL, backend and DesktopHost lifetimes.
  Bootstrap still travels once through inherited pipes; the real C# Host alone
  holds and injects its session. No tokens are written to browser storage,
  command-line arguments, user configuration or this profile.
- V2 selects exactly `branch_manuscript_v1`, `narrative_production_v2`,
  `ai_execution_v2`, `model_broker_v2`, and `author_context_inspector_v2`.
  Server-owned dependency checks remain authoritative. The existing
  `V1_ACCEPTANCE_MODE` value is passed to the backend unchanged and overrides all
  experimental features off, without switching V2 data or credentials to V1.
- Cloud routing and fallback are disabled, the creation profile is local-only,
  and the profile does not enable mock generation.
- Each supplied/default base receives the fixed `AI-Novel-Studio-V2` container.
  Existing `WindowsPackagingPaths` then owns all data, PostgreSQL, logs,
  runtime metadata, WebView cache and backups below it. This deliberately keeps
  the original final `AI-Novel-Studio/Cache/WebView2` shape required by C#.
- The existing stable-identity owner receives the V2 local-data base. Existing
  asset/audio/worker configuration owners receive explicit V2 configuration
  paths. User home remains available to the existing explicitly consented model
  discovery flow; this is not a general-purpose home-directory sandbox.
- Windows credentials use only `AI-Novel-Studio-V2/provider/<provider>`.
  Default targets remain `AI-Novel-Studio/provider/<provider>`. A missing V2
  credential is missing: there is no V1 read-through, enumeration, migration,
  deletion or fallback. V2 requires the real Windows backend and rejects memory,
  keyring, injected backends and memory fallback before backend access.
- The profile marker is an internal finite backend configuration, not HTTP
  authentication. The default launcher removes an inherited marker; only its
  explicit selection sets the child's V2 marker. Pure launcher framing imports
  do not initialize a vault before that selection.
- The V2 Host child receives its exact owned `WEBVIEW2_USER_DATA_FOLDER` and
  clears inherited WebView2 overrides. Default Host environment behavior is
  unchanged. Native verification must still confirm the actual selected folder.

## Filesystem checks and limits

Before V2 process starts, owner paths and existing V2 tree entries are checked
for symlinks, Windows reparse points and multiply linked regular files. Reads
of the original user data are not used to establish V2 ownership. Each full
validation streams at most 100,000 entries across the two V2 roots, with a
maximum depth of 64 and elapsed-time checks at ten seconds. Exceeding a limit
fails closed with `PACKAGED_V2_STATE_SCAN_LIMIT`; an individual blocked OS call
cannot be interrupted by this synchronous check.

The sole link exception preserves the original Unicode-install workaround:
`Runtime/PostgreSQL-<exact target digest>` may be a Windows junction only to the
selected application's exact PostgreSQL executable distribution. Its type,
name and resolved target must all match; it is not traversed as user data.
Wrong targets, digests, names, symbolic links and state-root junctions fail.
Application binaries remain trusted installation inputs, distinct from
mutable user state. This does not certify a modified Application distribution.

These are fail-closed checks of observed paths, not an atomic filesystem
sandbox. Another process with the same Windows identity could race pathname
checks or modify that identity's credentials. No stronger same-user/TOCTOU
security guarantee is claimed; OS account and Application integrity remain
prerequisites. No global Windows security setting is changed.

## Verification and native handoff

New tests are `test_v2_packaged_launch_profile.py`,
`test_v2_packaged_launch_isolation.py`, and
`test_v2_windows_vault_namespace.py`. Existing tests are unmodified. Coverage
includes exact default parity, poisoned/unknown selectors, V1 flag precedence,
state aliases/limits, isolated identity/sidecars, exact Unicode-junction rules,
vault-free launcher imports, WebView environment propagation, original
close/restart behavior, and real ctypes records routed through fake Windows
functions. Such mocks do not prove native ABI or credential-store operation.

Native acceptance must use the exact reviewed revision and fresh payload:
verify bootstrap readiness, actual V2 paths/vault targets, untouched V1 state,
Chinese-path startup, controlled close/restart and session invalidation before
claiming the integration works. Then validate the approved local model through
the ordinary UI, review one request and its durable result receipt. PowerShell,
WebView2, Windows vault, PostgreSQL and real-model acceptance are separate from
cloud tests. Neither a Host build nor API fixtures substitute for those results.
