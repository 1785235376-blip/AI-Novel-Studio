from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROGRAM = ROOT / "desktop-host" / "AI.NovelStudio.DesktopHost" / "Program.cs"
PROJECT = ROOT / "desktop-host" / "AI.NovelStudio.DesktopHost" / "AI.NovelStudio.DesktopHost.csproj"


def test_authorized_host_is_minimal_webview2_evergreen_only():
    project = PROJECT.read_text(encoding="utf-8")
    source = PROGRAM.read_text(encoding="utf-8")
    assert "Microsoft.Web.WebView2" in project
    assert "WebView2" in source
    assert "GetAvailableBrowserVersionString" in source
    assert all(name not in (project + source).casefold() for name in ("electron", "tauri", "downloadfile", "webclient"))


def test_handoff_uses_inherited_memory_pipe_and_never_url_or_persistent_storage():
    source = PROGRAM.read_text(encoding="utf-8")
    assert "Console.In.ReadLine" in source
    assert "PostAsJsonAsync(\"/api/packaged/bootstrap\"" in source
    assert "X-Session-Token" in source
    assert "AddWebResourceRequestedFilter" in source
    assert "__AI_NOVEL_PACKAGED_HOST__" in source
    forbidden = (
        "Environment.GetCommandLineArgs", "localStorage", "sessionStorage", "indexedDB",
        "Registry.", "bootstrap_secret=", "?bootstrap", "#bootstrap",
    )
    assert all(value not in source for value in forbidden)


def test_host_has_exact_origin_lock_no_wildcard_and_bounded_chinese_failures():
    source = PROGRAM.read_text(encoding="utf-8")
    assert 'uri.Host == "127.0.0.1"' in source
    assert "NavigationStarting" in source
    assert "args.Cancel = true" in source
    assert "AllowAnyOrigin" not in source
    assert 'frontend_origin + "/api/*"' in source
    assert "应用窗口启动失败，请重新启动 AI-Novel-Studio。" in source
    assert "本地安全会话初始化失败，请关闭程序后重新打开。" in source
    assert "需要 Windows WebView2 运行组件" in source


def test_frontend_packaged_mode_has_no_auth_persistence_adapter():
    helper = (ROOT / "frontend" / "src" / "packagedHost.ts").read_text(encoding="utf-8")
    store = (ROOT / "frontend" / "src" / "store.ts").read_text(encoding="utf-8")
    assert "return packaged ? undefined : storage" in helper
    assert "browserPersistenceForMode(packagedHost" in store
    assert "bootstrap_secret" not in helper + store
    assert "runtime_instance_id" not in helper + store
