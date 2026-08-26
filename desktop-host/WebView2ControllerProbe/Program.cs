using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

namespace AINovelStudio.WebView2ControllerProbe;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        var status = Environment.GetEnvironmentVariable("WEBVIEW2_PROBE_STATUS");

        try
        {
            if (string.IsNullOrWhiteSpace(status))
            {
                throw new InvalidOperationException("probe status path is required");
            }

            var statusDirectory = Path.GetDirectoryName(Path.GetFullPath(status));
            if (!string.IsNullOrEmpty(statusDirectory))
            {
                Directory.CreateDirectory(statusDirectory);
            }

            ApplicationConfiguration.Initialize();
            Application.Run(new ProbeWindow(status));
        }
        catch (Exception exception)
        {
            if (!string.IsNullOrWhiteSpace(status))
            {
                File.AppendAllText(
                    status,
                    "MAIN_EXCEPTION=" + exception.GetType().Name + Environment.NewLine
                    + $"MAIN_HRESULT=0x{exception.HResult:X8}" + Environment.NewLine
                    + "RESULT=FAIL" + Environment.NewLine);
            }
        }
    }
}

internal sealed class ProbeWindow : Form
{
    private readonly WebView2 webView = new() { Dock = DockStyle.Fill };
    private readonly string status;
    private readonly string profile = Environment.GetEnvironmentVariable("WEBVIEW2_PROBE_PROFILE")
        ?? throw new InvalidOperationException("probe profile path is required");

    internal ProbeWindow(string statusPath)
    {
        status = statusPath;
        Controls.Add(webView);
        Shown += async (_, _) => await RunAsync();
        var stdinMode = Environment.GetEnvironmentVariable("WEBVIEW2_PROBE_STDIN_READER");
        if (stdinMode == "1")
        {
            Shown += async (_, _) => await Console.In.ReadLineAsync();
        }
        else if (stdinMode == "background")
        {
            Shown += (_, _) => _ = Task.Run(async () => await Console.In.ReadLineAsync());
        }
    }

    private void Trace(string value) => File.AppendAllText(status, value + Environment.NewLine);

    private async Task RunAsync()
    {
        try
        {
            Trace("STA=" + (Thread.CurrentThread.GetApartmentState() == ApartmentState.STA));
            Trace("UI_THREAD=" + Environment.CurrentManagedThreadId);
            Trace("HANDLE_CREATED=" + IsHandleCreated);
            Trace("SYNC_CONTEXT=" + SynchronizationContext.Current?.GetType().Name);
            var version = CoreWebView2Environment.GetAvailableBrowserVersionString();
            Trace("RUNTIME=" + version);
            Directory.CreateDirectory(profile);
            if (Environment.GetEnvironmentVariable("WEBVIEW2_PROBE_IMPLICIT") == "1")
            {
                webView.CreationProperties = new CoreWebView2CreationProperties
                {
                    UserDataFolder = profile,
                };
                Trace("ENVIRONMENT=IMPLICIT");
                await webView.EnsureCoreWebView2Async().WaitAsync(TimeSpan.FromSeconds(30));
                Trace("CONTROLLER=PASS");
                Trace("RESULT=PASS");
                return;
            }
            var environment = await CoreWebView2Environment.CreateAsync(null, profile)
                .WaitAsync(TimeSpan.FromSeconds(30));
            Trace("ENVIRONMENT=PASS");
            await webView.EnsureCoreWebView2Async(environment).WaitAsync(TimeSpan.FromSeconds(30));
            Trace("CONTROLLER=PASS");
            Trace("RESULT=PASS");
        }
        catch (Exception exception)
        {
            Trace("EXCEPTION=" + exception.GetType().Name);
            Trace($"HRESULT=0x{exception.HResult:X8}");
            Trace("RESULT=FAIL");
        }
        finally
        {
            Close();
        }
    }
}
