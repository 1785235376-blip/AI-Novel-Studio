# Windows portable development entry

`AI-Novel-Studio-Portable.cmd` is a fixed Windows entry point for a verified
staged `Application` directory. It is intentionally **not an installer**, a
release package, an updater, or an uninstaller, and it does not claim that
V1.0 has been released.

Expected layout when copied next to a staged application:

```text
<portable-root>/
  AI-Novel-Studio-Portable.cmd
  Application/
    Backend/app/packaging/packaged_desktop_launcher.py
    DesktopHost/AI-Novel-Studio.DesktopHost.exe
    Frontend/dist/index.html
    Runtime/Python/python.exe
    PostgreSQL/bin/{postgres.exe,initdb.exe}
    release/version.json
```

The wrapper checks the required components, changes into the staged Backend
directory, and runs the bundled Python in isolated mode:

```text
python.exe -I -m app.packaging.packaged_desktop_launcher --application-root <Application>
```

The launcher owns loopback ports, the local PostgreSQL process, the backend,
DesktopHost, the disposable WebView2 profile, and graceful shutdown. The
wrapper does not read `.env`, provider credentials, URLs, or API keys. Provider
credentials are entered only through the DesktopHost runtime channel and are
kept in memory for the current process.

Use `scripts/build_windows_application.ps1` to produce a provenance-checked
staging tree when the approved .NET SDK and bundled runtimes are available.
That process is separate from this entry point. A signed installer, package,
auto-update channel, and final V1.0 release still require a later release gate.

