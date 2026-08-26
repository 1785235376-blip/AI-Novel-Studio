using System.Net.Http.Json;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;
[assembly: System.Runtime.CompilerServices.InternalsVisibleTo("AI-Novel-Studio.DesktopHost.TestHarness")]

namespace AINovelStudio.DesktopHost;

internal sealed class LaunchEnvelope
{
    public string frontend_origin { get; set; } = "";
    public string backend_origin { get; set; } = "";
    public string runtime_instance_id { get; set; } = "";
    public string bootstrap_secret { get; set; } = "";
    public string webview_profile_directory { get; set; } = "";
}

internal sealed record BootstrapResponse(string session_token);
internal sealed record HostControlPing(string protocol, string type, string runtime_instance_id);

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        // The Python packaged launcher writes the inherited control envelope as
        // UTF-8.  Replace redirected streams explicitly so Chinese Windows
        // system code pages cannot corrupt paths before JSON validation.  A
        // GUI process may not have a console handle when launched manually, so
        // this setup is intentionally best-effort and never blocks startup.
        ConfigureUtf8Pipes();
        ApplicationConfiguration.Initialize();
        var statusFile = Environment.GetEnvironmentVariable("PACKAGED_HOST_STATUS_FILE");
        try
        {
            var envelope = ReadOneShotEnvelope();
            Application.Run(new DesktopWindow(envelope));
        }
        catch (WebViewRuntimeUnavailable)
        {
            if (!string.IsNullOrWhiteSpace(statusFile)) File.WriteAllText(statusFile, "DESKTOP_WEBVIEW_UNAVAILABLE");
            MessageBox.Show(
                "AI-Novel-Studio 需要 Windows WebView2 运行组件。请完成运行组件安装后重新启动应用。",
                "AI-Novel-Studio", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
        catch (Exception exception)
        {
            WriteFailure(statusFile, "DESKTOP_ENVELOPE_FAILED");
            if (!string.IsNullOrWhiteSpace(statusFile))
            {
                try
                {
                    var directory = Path.GetDirectoryName(statusFile);
                    var trace = Path.Combine(directory ?? ".", "host.trace");
                    File.AppendAllText(trace, $"ENVELOPE_EXCEPTION={exception.GetType().Name}\n");
                    if (!string.IsNullOrWhiteSpace(exception.Message))
                        File.AppendAllText(trace, $"ENVELOPE_REASON={exception.Message}\n");
                }
                catch { }
            }
            MessageBox.Show(
                "应用窗口启动失败，请重新启动 AI-Novel-Studio。",
                "AI-Novel-Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }

    private static void ConfigureUtf8Pipes()
    {
        try
        {
            Console.SetIn(new StreamReader(
                Console.OpenStandardInput(), new UTF8Encoding(false),
                detectEncodingFromByteOrderMarks: false, bufferSize: 4096, leaveOpen: true));
        }
        catch { }
        try
        {
            Console.SetOut(new StreamWriter(
                Console.OpenStandardOutput(), new UTF8Encoding(false),
                bufferSize: 4096, leaveOpen: true) { AutoFlush = true });
        }
        catch { }
    }

    private static void WriteFailure(string? statusFile, string status)
    {
        if (string.IsNullOrWhiteSpace(statusFile)) return;
        try
        {
            var directory = Path.GetDirectoryName(statusFile);
            if (!string.IsNullOrWhiteSpace(directory)) Directory.CreateDirectory(directory);
            File.WriteAllText(statusFile, status);
            // Keep diagnostics deliberately structural: no origins, tokens, or
            // envelope payloads are ever written to disk or stdout.
            var trace = Path.Combine(directory ?? ".", "host.trace");
            File.AppendAllText(trace, "ENVELOPE_FAILURE\n");
        }
        catch { /* The launcher still receives the bounded status code. */ }
    }

    private static LaunchEnvelope ReadOneShotEnvelope()
    {
        // The launcher writes once through the inherited stdin pipe. Nothing is
        // accepted from command line, environment, URL, registry, or disk.
        var line = Console.In.ReadLine() ?? throw new InvalidOperationException();
        var value = JsonSerializer.Deserialize<LaunchEnvelope>(line) ?? throw new InvalidOperationException();
        if (!ExactLoopbackOrigin(value.frontend_origin))
            throw new InvalidOperationException("frontend-origin");
        if (!ExactLoopbackOrigin(value.backend_origin))
            throw new InvalidOperationException("backend-origin");
        if (string.IsNullOrWhiteSpace(value.bootstrap_secret))
            throw new InvalidOperationException("bootstrap-missing");
        if (string.IsNullOrWhiteSpace(value.runtime_instance_id))
            throw new InvalidOperationException("runtime-id-missing");
        ValidateDisposableProfile(value.webview_profile_directory);
        return value;
    }

    internal static bool ExactLoopbackOrigin(string value) =>
        Uri.TryCreate(value, UriKind.Absolute, out var uri)
        && uri.Scheme == Uri.UriSchemeHttp && uri.Host == "127.0.0.1"
        && !uri.IsDefaultPort && uri.AbsolutePath == "/" && string.IsNullOrEmpty(uri.Query)
        && string.IsNullOrEmpty(uri.Fragment) && string.IsNullOrEmpty(uri.UserInfo);

    private static void ValidateDisposableProfile(string value)
    {
        var full = Path.GetFullPath(value);
        var configuredRoot = Environment.GetEnvironmentVariable("PACKAGED_HOST_WEBVIEW_ROOT");
        var root = string.IsNullOrWhiteSpace(configuredRoot)
            ? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "AI-Novel-Studio", "Cache", "WebView2")
            : configuredRoot;
        var allowed = Path.GetFullPath(root).TrimEnd(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar)
            + Path.DirectorySeparatorChar;
        // The explicit root is supplied only by the packaged launcher and must
        // still have the product's expected cache shape.  This keeps the
        // disposable profile boundary narrow while allowing isolated tests.
        var normalized = allowed.TrimEnd(Path.DirectorySeparatorChar);
        if (!normalized.EndsWith(
                Path.Combine("AI-Novel-Studio", "Cache", "WebView2"),
                StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException();
        if (!full.StartsWith(allowed, StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException();
    }
}

internal sealed class DesktopWindow : Form
{
    private readonly LaunchEnvelope launch;
    private readonly WebView2 webView = new() { Dock = DockStyle.Fill };
    private string? sessionToken;
    private bool ready;
    private readonly HostControlRuntime controlRuntime;

    private string StatusFile => Environment.GetEnvironmentVariable("PACKAGED_HOST_STATUS_FILE")
        ?? Path.Combine(launch.webview_profile_directory, "host.status");
    private string TraceFile => Path.Combine(launch.webview_profile_directory, "host.trace");

    private void WriteStatus(string value) => File.WriteAllText(StatusFile, value);
    private void Trace(string value) => File.AppendAllText(TraceFile, value + Environment.NewLine);

    internal DesktopWindow(LaunchEnvelope launch, bool emitStartupControlPing = true)
    {
        this.launch = launch;
        controlRuntime = new HostControlRuntime(launch.frontend_origin, launch.runtime_instance_id, Console.Out,
            observer: null, startupPingEnabled: emitStartupControlPing);
        Text = "AI-Novel-Studio";
        Width = 1440; Height = 900; MinimumSize = new Size(1024, 720);
        Controls.Add(webView);
        Shown += async (_, _) => await InitializeAsync();
        Shown += (_, _) => _ = Task.Run(WaitForCloseCommandAsync);
        FormClosing += (_, _) => { sessionToken = null; ready = false; };
    }

    private async Task WaitForCloseCommandAsync()
    {
        var command = await Console.In.ReadLineAsync();
        if (command == "CLOSE" && !IsDisposed) BeginInvoke(Close);
    }

    private async Task InitializeAsync()
    {
        try
        {
            var version = CoreWebView2Environment.GetAvailableBrowserVersionString();
            if (string.IsNullOrWhiteSpace(version)) throw new WebViewRuntimeUnavailable();
            Trace("WEBVIEW_RUNTIME_FOUND");
            Trace("WEBVIEW_RUNTIME_VERSION=" + version);
            Trace("HOST_PROCESS_ARCH=" + (Environment.Is64BitProcess ? "X64" : "X86"));
            Directory.CreateDirectory(launch.webview_profile_directory);
            webView.CreationProperties = new CoreWebView2CreationProperties
            {
                UserDataFolder = launch.webview_profile_directory,
            };
            await webView.EnsureCoreWebView2Async().WaitAsync(TimeSpan.FromSeconds(30));
            Trace("WEBVIEW_CORE_READY");
            await ExchangeBootstrapAsync();
            Trace("BOOTSTRAP_READY");
            ConfigureLockedWebView();
            webView.Source = new Uri(launch.frontend_origin);
            Trace("NAVIGATION_STARTED");
        }
        catch (WebViewRuntimeUnavailable) { throw; }
        catch (Exception exception)
        {
            Trace($"WEBVIEW_EXCEPTION={exception.GetType().Name}");
            Trace($"WEBVIEW_HRESULT=0x{exception.HResult:X8}");
            WriteStatus("DESKTOP_BOOTSTRAP_FAILED");
            Console.Out.WriteLine("DESKTOP_BOOTSTRAP_FAILED");
            Console.Out.Flush();
            MessageBox.Show(
                "本地安全会话初始化失败，请关闭程序后重新打开。",
                "AI-Novel-Studio", MessageBoxButtons.OK, MessageBoxIcon.Error);
            Close();
        }
    }

    private async Task ExchangeBootstrapAsync()
    {
        using var client = new HttpClient { BaseAddress = new Uri(launch.backend_origin) };
        client.DefaultRequestHeaders.Add("Origin", launch.frontend_origin);
        using var response = await client.PostAsJsonAsync("/api/packaged/bootstrap", new
        {
            bootstrap_secret = launch.bootstrap_secret,
            runtime_instance_id = launch.runtime_instance_id,
        });
        Trace($"BOOTSTRAP_HTTP_{(int)response.StatusCode}");
        if (!response.IsSuccessStatusCode) throw new InvalidOperationException();
        var body = await response.Content.ReadFromJsonAsync<BootstrapResponse>() ?? throw new InvalidOperationException();
        sessionToken = body.session_token;
        launch.bootstrap_secret = "";
    }

    private void ConfigureLockedWebView()
    {
        var core = webView.CoreWebView2;
        core.Settings.AreDevToolsEnabled = false;
        core.Settings.AreDefaultContextMenusEnabled = false;
        core.Settings.IsPasswordAutosaveEnabled = false;
        core.Settings.IsGeneralAutofillEnabled = false;
        core.AddScriptToExecuteOnDocumentCreatedAsync(
            "Object.defineProperty(window,'__AI_NOVEL_PACKAGED_HOST__',{value:true,writable:false,configurable:false});");
        // Browser API calls are same-origin requests to the owned frontend/proxy.
        // The proxy forwards this host-injected header to the loopback backend.
        core.AddWebResourceRequestedFilter(launch.frontend_origin + "/api/*", CoreWebView2WebResourceContext.All);
        core.WebResourceRequested += (_, args) =>
        {
            if (sessionToken is null) { args.Response = core.Environment.CreateWebResourceResponse(null, 401, "Unauthorized", ""); return; }
            var target = new Uri(args.Request.Uri);
            var frontend = new Uri(launch.frontend_origin);
            if (target.Scheme != frontend.Scheme || target.Host != frontend.Host || target.Port != frontend.Port) return;
            args.Request.Headers.SetHeader("X-Session-Token", sessionToken);
        };
        core.NavigationStarting += (_, args) =>
        {
            var target = new Uri(args.Uri);
            var expected = new Uri(launch.frontend_origin);
            if (target.Scheme != expected.Scheme || target.Host != expected.Host || target.Port != expected.Port)
                args.Cancel = true;
        };
        core.FrameCreated += (_, args) =>
        {
            args.Frame.NavigationStarting += (_, frameArgs) => frameArgs.Cancel = true;
        };
        core.NewWindowRequested += (_, args) => args.Handled = true;
        core.WebMessageReceived += (_, args) => HandleWebMessage(args);
        core.NavigationCompleted += async (_, args) =>
        {
            Trace(args.IsSuccess ? "NAVIGATION_COMPLETED" : "NAVIGATION_FAILED");
            if (!args.IsSuccess || ready) return;
            using var client = new HttpClient { BaseAddress = new Uri(launch.backend_origin) };
            client.DefaultRequestHeaders.Add("X-Session-Token", sessionToken);
            using var probe = await client.GetAsync("/api/collaboration/admin/workspaces");
            if (!probe.IsSuccessStatusCode)
            {
                WriteStatus($"DESKTOP_PROTECTED_REQUEST_FAILED:{(int)probe.StatusCode}");
                Console.Out.WriteLine($"DESKTOP_PROTECTED_REQUEST_FAILED:{(int)probe.StatusCode}");
                Console.Out.Flush();
                Close();
                return;
            }
            ready = true;
            WriteStatus("DESKTOP_SESSION_READY");
            Console.Out.WriteLine("DESKTOP_SESSION_READY");
            Console.Out.Flush();
            controlRuntime.EmitStartupPing();
        };
    }

    private void HandleWebMessage(CoreWebView2WebMessageReceivedEventArgs args)
    {
        string json;
        try { json = args.WebMessageAsJson; } catch { return; }
        if (!controlRuntime.HandleWebMessage(args.Source, json))
            controlRuntime.HandleWebCredentialMessage(args.Source, json);
    }
}

internal sealed class WebViewRuntimeUnavailable : Exception { }
