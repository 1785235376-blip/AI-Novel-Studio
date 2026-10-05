# R2 fresh Windows acceptance inputs

## Scope and truthful status

The package no longer requires a historical `BaseApplication` copied from a user's machine.
`scripts/prepare_windows_base.py` assembles fresh CPython, application wheels, and PostgreSQL files
from `packaging/windows-runtime-inputs.json`. No user database, manuscript, account, environment file,
or credential is copied. Downloads are restricted to reviewed HTTPS origins and exact lengths/SHA256s.
Archive paths, links, Windows reserved names and case collisions are rejected before extraction.
The output must be fresh; caches are hash-rechecked and never silently trusted.

A successful materialization is **input assembly**, not Windows execution. On 2026-10-05 the actual
locked downloads were materialized on Linux: 4,876 files, no Windows executable run. The associated
native smoke must run on hosted Windows and its exact-revision receipt determines native status.
Neither that smoke nor a successful Host build is interactive DesktopHost/IME/user acceptance.

The full existing `package_windows_acceptance.ps1` path builds the Host with `--self-contained true`;
it therefore includes the .NET 8 application runtime. Restore explicitly matches this with
`-p:SelfContained=true`, because .NET 8 no longer infers that property from the runtime identifier. The standalone compile-only CI job uses
`--self-contained false` and is **not** the complete package. `global.json` now pins SDK 8.0.424 with
roll-forward disabled, preventing an installed SDK 10 from silently taking precedence.
Full licenses are copied from the exact restored .NET runtime/WindowsDesktop/WebView2 packages;
.NETCore 8.0.30 also supplies `THIRD-PARTY-NOTICES.TXT`, retained in full. Official WindowsDesktop
8.0.30 supplies `LICENSE` only, and WebView2 1.0.3537.50 supplies `LICENSE.txt`; no nonexistent
third-party-notice file is invented. Their source paths, package versions and digests are recorded.

## External system prerequisites

This is an internal application payload, **not a fully offline, self-sufficient Windows distribution**:

- Microsoft Edge WebView2 **Evergreen Runtime** must already be installed. The SDK DLL/loader is not
  the browser runtime. The Host retains its Evergreen contract and reports `DESKTOP_WEBVIEW_UNAVAILABLE`
  when the actual SDK throws for a missing runtime. No new Runtime EULA is accepted automatically.
- Microsoft Visual C++ 2015–2022 **x64 Redistributable** must be installed. EDB's ICU binaries require
  `MSVCP140.dll` and its core executables require `VCRUNTIME140.dll`; these are not in the EDB ZIP.
  Native smoke uses a sanitized PATH and records actual application-local/System32 CRT hashes, so
  a hosted runner's installed CRT is explicitly a prerequisite, not hidden evidence of bundling.
- An optional `--vc-redist-directory` can vendor unmodified release DLLs from the documented installed
  Visual Studio 2022 `VC/Redist/MSVC/<version>/x64/Microsoft.VC143.CRT` tree **only after the caller has
  independently established redistribution eligibility under its existing license**. Merely having
  Visual Studio on a runner does not establish that eligibility. The default never finds/copies these
  automatically, runs a redistributable installer, accepts terms, or copies arbitrary System32 files.

Official prerequisite and license guidance:

- [WebView2 distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)
- [WebView2 user-controlled download](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)
- [Supported Visual C++ Redistributable](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-vc-redist)
- [Visual Studio 2022 redistribution list and conditions](https://learn.microsoft.com/en-us/visualstudio/releases/2022/redistribution)

## Origin and license provenance

- CPython 3.12.9 Windows x64 embedded ZIP comes from the exact [Python release page](https://www.python.org/downloads/release/python-3129/).
  Observed official HTTPS SHA256: `615861fb801e8b04c847598db4e1e46e4b046295017caa37cb5486dde72b5865`.
  Its bytes also match that page's published MD5 `f34996cc1f44c98729ef6ce92d05e41c`.
  SHA256 here is an origin-observed pin, not a claim that a signature was verified. CPython's complete
  `LICENSE.txt` is retained. This version matches the existing tested 3.12.9 CI baseline; it is not
  claimed to be the latest security-patched Python. Updating the supported Python runtime remains a
  separate release-security decision (the 3.12 series now has later source-only security releases).
- [PostgreSQL.org](https://www.postgresql.org/download/windows/) explicitly points to EDB's binary ZIPs
  for application installers. The live [EDB binary page](https://www.enterprisedb.com/download-postgresql-binaries)
  Windows 16.15 link `https://sbp.enterprisedb.com/getfile.jsp?fileid=1260623` resolved to the exact
  `https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64-binaries.zip` (373,254,386 bytes).
  Observed SHA256: `43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281`.
  This is an **origin-pinned** digest, not vendor-published or vendor-signed checksum verification.
  `bin`, `lib`, `share`, `doc` and all root license notices are retained byte-for-byte, including the
  complete `server_license.txt` and `commandlinetools_3rd_party_licenses.txt` (not all notices are UTF-8).
  pgAdmin and the separate StackBuilder application trees are omitted. All server binaries/extensions
  and CLI tools remain; optional PL/Perl, PL/Python and PL/Tcl require additional runtimes and are not
  product capabilities. Current migrations use pgcrypto, whose OpenSSL, zlib, ICU and other core
  supporting libraries are included in EDB's binary tree.
- Each of 27 Windows CPython 3.12-compatible wheels has an exact official PyPI file URL, length and
  PyPI-published SHA256 recorded in the input manifest. Full `.dist-info` licenses/notices remain in
  the payload. The hash-required Windows lock now includes ReportLab/Pillow and Windows tzdata.
  Only wheels are unpacked, no source builds or package setup hooks run. The embedded interpreter
  has no pip and uses a relative, isolated `python312._pth` for vendored dependencies and Backend.
  See [CPython embedding guidance](https://docs.python.org/3.12/using/windows.html#the-embeddable-package).

## Hosted Windows build commands

Use an isolated checkout, Python 3.12.9, Node 22.14.0, pnpm 10.6.5 and .NET SDK 8.0.424. Run frontend
`pnpm install --frozen-lockfile`, install `.[fontbuild]` under the existing CI constraints, then in pwsh:

```powershell
if ((dotnet --version).Trim() -ne '8.0.424') { throw 'Wrong .NET SDK' }
$base = Join-Path $env:RUNNER_TEMP 'r2-fresh-base'
$cache = Join-Path $env:RUNNER_TEMP 'r2-windows-inputs'
$fonts = Join-Path $env:RUNNER_TEMP 'r2-package-fonts'
$output = Join-Path $env:RUNNER_TEMP 'r2-acceptance-package'
$publish = Join-Path $env:RUNNER_TEMP 'r2-self-contained-host'
python scripts/prepare_windows_base.py --output $base --cache $cache
if ($LASTEXITCODE -ne 0) { throw 'Fresh base assembly failed' }
python scripts/prepare_pdf_font.py --output $fonts
if ($LASTEXITCODE -ne 0) { throw 'Font preparation failed' }
./scripts/package_windows_acceptance.ps1 -BaseApplication $base -OutputRoot $output `
  -HostPublishDirectory $publish -DotnetPath (Get-Command dotnet).Source `
  -NodePath (Get-Command node).Source `
  -ViteCliPath (Join-Path $PWD 'frontend/node_modules/vite/bin/vite.js') `
  -VerifiedFontDirectory $fonts -SkipIExpress
python scripts/verify_windows_base.py --base (Join-Path $output 'Application') `
  --work-root (Join-Path $env:RUNNER_TEMP 'r2-native-base-smoke')
if ($LASTEXITCODE -ne 0) { throw 'Native base smoke failed' }
```

`-SkipIExpress` produces the real acceptance ZIP and PowerShell installer without claiming a signed
setup EXE. IExpress creation, signatures, install/upgrade/uninstall and interactive acceptance are
separate checks. Keep the output in internal CI artifacts; do not create a formal Release.

Expected evidence/output:

- `<base>/base-input-provenance.json`: exact input URLs/digests/licenses and complete staged file inventory
- `<output>/application-provenance.json` and same-run DesktopHost source/publish manifests
- `<output>/acceptance-package-manifest.json`
- `<output>/AI-Novel-Studio-Windows-DesktopHost-acceptance.zip`
- `<smoke>/native-base-smoke.json`: Python ABI/import/isolation, actual CRT files, PostgreSQL 16.15,
  pgcrypto, UTF-8 text, custom-format dump/restore and owned shutdown; mock/no external provider boundary
- Exact checkout SHA and selected SDK/runtime versions from CI, with all logs tied to that run

Native smoke refuses non-Windows execution and any existing work directory. It creates a loopback-only
synthetic cluster, never reuses a user cluster, and stops only its own fresh directory. Failure remains
failure; missing runtimes cannot be replaced with a mock pass. A Windows hosted success still does not
prove clean-Windows prerequisite installation, WebView2 UI, IME, signing or user acceptance.

## Why not a minimal PostgreSQL source build?

A source-only fallback is technically possible with the vendor-published 16.15 source digest, Visual
Studio and Strawberry Perl. However, default MSVC configuration omits OpenSSL/pgcrypto, while migration
001 explicitly creates pgcrypto; zlib is also needed for the existing custom-format backup workflow.
It therefore requires an additional reviewed OpenSSL/zlib build chain. Using the exact official EDB
redistribution input closes the current gap without silently weakening those application contracts.
