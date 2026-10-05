"""Source contracts for Evergreen failure handling and WinForms-only references.

These portable checks do not replace publishing and launching on Windows.
"""
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "desktop-host" / "AI.NovelStudio.DesktopHost"


def test_winforms_host_removes_only_unused_webview_wpf_before_resolution():
    project = ET.parse(HOST / "AI.NovelStudio.DesktopHost.csproj").getroot()
    assert project.findtext("PropertyGroup/UseWindowsForms") == "true"
    package = project.find("ItemGroup/PackageReference[@Include='Microsoft.Web.WebView2']")
    assert package is not None and package.get("Version") == "1.0.3537.50"
    target = project.find("Target[@Name='RemoveUnusedWebView2WpfReference']")
    assert target is not None
    assert target.get("BeforeTargets") == "ResolveAssemblyReferences"
    assert target.get("Condition") == "'$(UseWPF)' != 'true'"
    removals = target.findall("ItemGroup/Reference")
    assert len(removals) == 1
    assert removals[0].attrib == {
        "Remove": "@(Reference)",
        "Condition": "'%(Reference.Filename)' == 'Microsoft.Web.WebView2.Wpf'",
    }
    assert project.find(".//NoWarn") is None
    assert project.find(".//WarningsNotAsErrors") is None
    assert package.find("ExcludeAssets") is None


def test_missing_evergreen_is_handled_inside_async_initialization():
    source = (HOST / "Program.cs").read_text(encoding="utf-8")
    initialize = source.split("private async Task InitializeAsync()", 1)[1].split(
        "private async Task ExchangeBootstrapAsync()", 1
    )[0]
    missing_catch = (
        "catch (Exception exception) when (exception is "
        "WebView2RuntimeNotFoundException or WebViewRuntimeUnavailable)"
    )
    assert missing_catch in initialize
    handler = initialize.split(missing_catch, 1)[1].split("catch (Exception exception)", 1)[0]
    assert 'WriteStatus("DESKTOP_WEBVIEW_UNAVAILABLE")' in handler
    assert 'Console.Out.WriteLine("DESKTOP_WEBVIEW_UNAVAILABLE")' in handler
    assert "Console.Out.Flush()" in handler
    assert "需要 Windows WebView2 运行组件" in handler
    assert "MessageBoxIcon.Warning" in handler
    assert "Close()" in handler
    assert "throw;" not in handler
    assert 'WriteStatus("DESKTOP_BOOTSTRAP_FAILED")' not in handler
    assert 'WriteStatus("DESKTOP_BOOTSTRAP_FAILED")' in initialize


def test_evergreen_remains_an_external_prerequisite():
    source = (HOST / "Program.cs").read_text(encoding="utf-8")
    assert "GetAvailableBrowserVersionString()" in source
    assert "EnsureCoreWebView2Async()" in source
    assert "BrowserExecutableFolder" not in source
    assert all(name not in source for name in (
        "MicrosoftEdgeWebview2Setup", "MicrosoftEdgeWebView2RuntimeInstaller",
        "/silent /install", "DownloadFile",
    ))
