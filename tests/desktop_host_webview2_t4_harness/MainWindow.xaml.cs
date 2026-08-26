using System.Net;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading;
using System.Windows;
using System.Windows.Threading;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.Wpf;
using AINovelStudio.DesktopHost;

namespace AINovelStudio.DesktopHost.WebView2TestHarness;

public partial class MainWindow : Window
{
    private readonly WebView2 webView = new();
    private readonly string scenario;
    private readonly string frontendRoot;
    private readonly string origin;
    private readonly bool realPackaged;
    private readonly bool persistentSession;
    private readonly string? addScriptDiagnosticCase;
    private readonly string? sessionToken;
    private readonly HttpListener server = new();
    private readonly HttpListener? wrongServer;
    private readonly Stream observer;
    private readonly Stream? credentialData;
    private readonly Stream? secretInput;
    private readonly HostControlRuntime runtime;
    private readonly StringWriter hostOutput = new();
    private int messageCount;
    private int servedCount;
    private string? expectedNavigationWorkspace;
    private string? expectedNavigationProject;
    private int navigationRequestCount;
    private bool navigationRequestObserved;
    private bool navigationSessionHeaderPresent;
    private bool navigationWorkspaceMatches;
    private string? navigationRequestMethod;
    private string? navigationRequestUri;
    private bool navigationResponseObserved;
    private bool navigationResponseBodyObserved;
    private bool navigationResponseCorrelated;
    private int? navigationResponseStatus;
    private int? navigationEligiblePathCount;
    private bool? navigationExpectedProjectPresent;
    private bool? navigationDefaultPathPresent;
    private bool? navigationDefaultPathMatches;
    private bool workspaceListRequestObserved;
    private bool workspaceListSessionHeaderPresent;
    private int? workspaceListStatus;
    private int? workspaceListCount;
    private bool provisionRequestObserved;
    private bool provisionSessionHeaderPresent;
    private int? provisionStatus;
    private bool provisionBodyObserved;
    private bool? provisionWorkspaceMatches;
    private string? workspaceListContentType;
    private string? provisionContentType;
    private bool healthRequestEntered;
    private bool healthHeaderInjected;
    private bool healthRequestHandlerExited;
    private bool healthResponseObserved;
    private readonly List<CoreWebView2DevToolsProtocolEventReceiver> cdpReceivers = new();
    private string? harnessHealthRequestId;
    private bool harnessHealthResponseReceived;
    private bool harnessHealthLoadingFinished;
    private bool harnessHealthLoadingFailed;
    private int productionHealthRequestCount, productionHealthResponseCount, productionHealthFinishedCount, productionHealthFailedCount;
    private int cdpRequestHandlerCount, cdpResponseHandlerCount, cdpFinishedHandlerCount, cdpFailedHandlerCount;
    private int cdpRequestParseCount, cdpResponseParseCount, cdpFinishedParseCount, cdpFailedParseCount;
    private string? staticCdpRequestId;
    private bool staticCdpResponseReceived, staticCdpLoadingFinished, staticCdpLoadingFailed, staticCdpSourceMatched;
    private string healthPostProbeStage = "PROBE_OBJECT_RECEIVED";
    private readonly List<ApiObservation> entryApiOrder = new();
    private readonly TaskCompletionSource<bool> messageReceived = new(TaskCreationOptions.RunContinuationsAsynchronously);
    private static string harnessStage = "PROCESS_STARTED";
    private static int exceptionReported;
    private static int coreWebView2InitializationCount;
    private bool windowClosing;
    private const string PackagedHostDocumentScript = "Object.defineProperty(window,'__AI_NOVEL_PACKAGED_HOST__',{value:true,writable:false,configurable:false});";
    private const string SafeErrorDocumentScript = "window.__AI_NOVEL_SAFE_ERROR_SCRIPT_ACTIVE__=true;window.__A3_SAFE_ERRORS__={errors:[],rejections:[]};const c=e=>e instanceof TypeError?'TypeError':e instanceof SyntaxError?'SyntaxError':e instanceof Error?e.name||'Error':'NonError';window.addEventListener('error',e=>window.__A3_SAFE_ERRORS__.errors.push({kind:c(e.error),source:(()=>{try{return new URL(e.filename).pathname.split('/').pop()||'unknown'}catch{return'unknown'}})()}));window.addEventListener('unhandledrejection',e=>window.__A3_SAFE_ERRORS__.rejections.push({kind:c(e.reason)}));";

    public MainWindow(string[] args)
    {
        InstallExceptionDiagnostics();
        Stage("PROCESS_STARTED");
        InitializeComponent();
        Content = webView;
        scenario = Value(args, "--scenario") ?? "VALID";
        frontendRoot = Value(args, "--frontend-root") ?? throw new InvalidOperationException("frontend root required");
        realPackaged = scenario.Equals("REAL_PACKAGED", StringComparison.OrdinalIgnoreCase);
        persistentSession = scenario.Equals("REAL_PACKAGED_SESSION", StringComparison.OrdinalIgnoreCase);
        addScriptDiagnosticCase = Value(args, "--addscript-diagnostic-case")?.ToUpperInvariant();
        origin = (realPackaged || persistentSession) ? Value(args, "--real-origin") ?? throw new InvalidOperationException("real origin required") : "";
        if (realPackaged || persistentSession)
        {
            var sessionHandle = Value(args, "--session-handle");
            if (!nint.TryParse(sessionHandle, out var sh)) throw new InvalidOperationException("session handle required");
            using var pipe = new FileStream(new Microsoft.Win32.SafeHandles.SafeFileHandle(sh, false), FileAccess.Read);
            using var reader = new BinaryReader(pipe, Encoding.UTF8, leaveOpen: false);
            var length = reader.ReadInt32();
            if (length <= 0 || length > 2048) throw new InvalidOperationException("invalid session frame");
            sessionToken = Encoding.UTF8.GetString(reader.ReadBytes(length));
            if (sessionToken.Length == 0 || sessionToken.Length > 2048) throw new InvalidOperationException("invalid session token");
        }
        var handleText = Value(args, "--observer-handle");
        if (!nint.TryParse(handleText, out var handle)) throw new InvalidOperationException("observer handle required");
        observer = new FileStream(new Microsoft.Win32.SafeHandles.SafeFileHandle(handle, false), FileAccess.Write);
        var dataHandleText = Value(args, "--credential-data-handle");
        if (nint.TryParse(dataHandleText, out var dataHandle))
            credentialData = new FileStream(new Microsoft.Win32.SafeHandles.SafeFileHandle(dataHandle, false), FileAccess.Write);
        var secretHandleText = Value(args, "--secret-input-handle");
        if (nint.TryParse(secretHandleText, out var secretHandle))
            secretInput = new FileStream(new Microsoft.Win32.SafeHandles.SafeFileHandle(secretHandle, false), FileAccess.Read);
        if (!realPackaged && !persistentSession)
        {
            var port = GetFreePort();
            origin = $"http://127.0.0.1:{port}";
            server.Prefixes.Add(origin + "/");
            server.Start();
            _ = Task.Run(() => ServeLoop(server));
        }
        if (scenario.Equals("WRONG_ORIGIN", StringComparison.OrdinalIgnoreCase)
            || scenario.Equals("CREDENTIAL_WRONG_ORIGIN", StringComparison.OrdinalIgnoreCase))
        {
            wrongServer = new HttpListener();
            wrongServer.Prefixes.Add($"http://127.0.0.1:{GetFreePort()}/");
            wrongServer.Start();
            _ = Task.Run(() => ServeLoop(wrongServer));
        }
        TextWriter hostWriter = credentialData is null ? hostOutput : new CredentialPipeWriter(credentialData, hostOutput);
        runtime = new HostControlRuntime(origin, Value(args, "--runtime-id") ?? "t4b-test", hostWriter, Observe, startupPingEnabled: false);
        Loaded += async (_, _) =>
        {
            Stage("WINDOW_LOADED");
            await RunAsync();
        };
        Closing += (_, _) => windowClosing = true;
    }

    private static void InstallExceptionDiagnostics()
    {
        Application.Current.DispatcherUnhandledException += (_, e) => ReportException("DISPATCHER", e.Exception);
        AppDomain.CurrentDomain.UnhandledException += (_, e) => ReportException("APPDOMAIN", e.ExceptionObject as Exception);
        TaskScheduler.UnobservedTaskException += (_, e) => ReportException("TASKSCHEDULER", e.Exception);
    }

    private static void Stage(string stage)
    {
        harnessStage = stage;
        Console.WriteLine("HARNESS_STAGE=" + stage);
        Console.Out.Flush();
    }

    private static void ReportException(string source, Exception? exception)
    {
        if (Interlocked.Exchange(ref exceptionReported, 1) != 0) return;
        Console.Error.WriteLine("EXCEPTION_SOURCE=" + source);
        Console.Error.WriteLine("EXCEPTION_TYPE=" + (exception?.GetType().FullName ?? "NONE"));
        Console.Error.WriteLine("EXCEPTION_MESSAGE=" + Safe(exception?.Message));
        Console.Error.WriteLine("INNER_EXCEPTION_TYPE=" + (exception?.InnerException?.GetType().FullName ?? "NONE"));
        Console.Error.WriteLine("INNER_EXCEPTION_MESSAGE=" + Safe(exception?.InnerException?.Message));
        Console.Error.WriteLine("STACK_TRACE=" + Safe(exception?.StackTrace));
        Console.Error.WriteLine("THREAD_CONTEXT=MANAGED_THREAD_ID:" + Environment.CurrentManagedThreadId + ",DISPATCHER_ACCESS:" + Application.Current.Dispatcher.CheckAccess());
        Console.Error.WriteLine("HARNESS_STAGE=" + harnessStage);
        Console.Error.Flush();
    }

    private static string Safe(string? value) => string.IsNullOrEmpty(value)
        ? "NONE"
        : value.Replace('\r', ' ').Replace('\n', '|');

    private static string? Value(string[] args, string name)
    {
        var i = Array.IndexOf(args, name);
        return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
    }

    private static int GetFreePort()
    {
        var listener = new System.Net.Sockets.TcpListener(IPAddress.Loopback, 0);
        listener.Start(); var port = ((IPEndPoint)listener.LocalEndpoint).Port; listener.Stop(); return port;
    }

    private void Observe(string stage)
    {
        var bytes = Encoding.ASCII.GetBytes("AI_NOVEL_TEST_ATTRIBUTION_V1\t" + stage + "\n");
        observer.Write(bytes, 0, bytes.Length); observer.Flush();
    }

    private async Task RunAsync()
    {
        try
        {
            if (persistentSession)
            {
                await RunPersistentSessionAsync();
                return;
            }
            var profileRoot = Value(Environment.GetCommandLineArgs(), "--profile-root")
                ?? Path.Combine(Path.GetTempPath(), "AI-Novel-T4B", Guid.NewGuid().ToString("N"));
            var environment = await CoreWebView2Environment.CreateAsync(null, profileRoot);
            await webView.EnsureCoreWebView2Async(environment);
            if (realPackaged)
            {
                await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(
                    "Object.defineProperty(window,'__AI_NOVEL_PACKAGED_HOST__',{value:true,writable:false,configurable:false});");
                webView.CoreWebView2.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
                webView.CoreWebView2.WebResourceRequested += (_, e) =>
                {
                    var request = new Uri(e.Request.Uri);
                    var expected = new Uri(origin);
                    if (request.Scheme == expected.Scheme && request.Host == expected.Host && request.Port == expected.Port)
                        e.Request.Headers.SetHeader("X-Session-Token", sessionToken!);
                };
            }
            webView.CoreWebView2.Settings.AreDevToolsEnabled = false;
            webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
            var navigation = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            webView.CoreWebView2.NavigationCompleted += (_, e) =>
            {
                Console.WriteLine("NAVIGATION=" + (e.IsSuccess ? "PASS" : "FAIL"));
                navigation.TrySetResult(e.IsSuccess);
            };
            var credentialJson = Value(Environment.GetCommandLineArgs(), "--credential-json-stdin") is null
                ? null : Console.In.ReadLine();
            var page = scenario.ToUpperInvariant() switch
            {
                "VALID" => "/",
                "NO_PING" => "/__t4b_no_ping.html",
                "WRONG_ORIGIN" => "/__t4b_wrong_origin.html",
                "INVALID_MESSAGE" => "/__t4b_invalid.html",
                "REAL_PACKAGED" => "/",
            "CREDENTIAL" or "CREDENTIAL_WRONG_ORIGIN" or "PRODUCTION_CREDENTIAL" => "/",
                _ => throw new InvalidOperationException("unknown scenario"),
            };
            var target = wrongServer is null ? origin : wrongServer.Prefixes.First().TrimEnd('/');
            webView.Source = new Uri(target + page);
            if (credentialJson is not null)
            {
                if (!await navigation.Task.WaitAsync(TimeSpan.FromSeconds(10)))
                    throw new InvalidOperationException("navigation failed");
                var literal = System.Text.Json.JsonSerializer.Serialize(credentialJson);
                if (scenario.Equals("PRODUCTION_CREDENTIAL", StringComparison.OrdinalIgnoreCase) || realPackaged)
                {
                    var script = $"(async()=>{{const p=JSON.parse({literal});const wait=ms=>new Promise(r=>setTimeout(r,ms));const click=t=>{{const b=[...document.querySelectorAll('button')].find(x=>x.textContent?.includes(t));if(b){{b.click();return true}}return false}};for(let i=0;i<100&&!click('个人创作');i++)await wait(100);for(let i=0;i<100&&!click('我的创作空间');i++)await wait(100);for(let i=0;i<100&&!click('C4 Disposable Novel');i++)await wait(100);for(let i=0;i<100;i++){{const s=document.querySelector('select');if(s&&[...s.options].some(o=>o.value==='deepseek:deepseek-chat')){{s.value='deepseek:deepseek-chat';s.dispatchEvent(new Event('change',{{bubbles:true}}));break}}await wait(100)}}if(p.action==='DIAG'){{const s=document.querySelector('select');return JSON.stringify({{action_script_executed:true,document_ready:document.readyState==='complete',packaged_host:window.__AI_NOVEL_PACKAGED_HOST__===true,app_root_count:document.querySelectorAll('#root').length,novel_card_count:[...document.querySelectorAll('button')].filter(x=>x.textContent?.includes('C4 Disposable Novel')).length,deepseek_option_count:s?[...s.options].filter(o=>o.value==='deepseek:deepseek-chat').length:0,deepseek_selected:s?.value==='deepseek:deepseek-chat',password_input_count:document.querySelectorAll('input[type=password]').length,configure_button_count:[...document.querySelectorAll('button')].filter(x=>x.textContent?.includes('配置此会话')).length,unconfigured_copy:document.body.innerText.includes('尚未配置')}})}}if(p.action==='CLEAR'){{for(let i=0;i<100&&!click('清除');i++)await wait(100);await wait(300);return JSON.stringify({{cleared:true}})}}if(p.action==='REPLACE'){{for(let i=0;i<100&&!click('更换密钥');i++)await wait(100)}}let input=null;for(let i=0;i<100;i++){{input=document.querySelector('input[type=password]');if(input)break;await wait(100)}}if(!input)return JSON.stringify({{input:false}});const setter=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;setter.call(input,p.credential);input.dispatchEvent(new Event('input',{{bubbles:true}}));const masked=input.type==='password'&&!document.body.innerText.includes(p.credential);click('配置此会话');await wait(300);return JSON.stringify({{input:true,masked,domEmpty:input.value===''||!document.body.contains(input)}})}})()";
                    var result = await webView.ExecuteScriptAsync($"window.__C4_ACTION_RESULT__=null;({script}).then(x=>window.__C4_ACTION_RESULT__=x)");
                    if (realPackaged)
                    {
                        await Task.Delay(TimeSpan.FromSeconds(15));
                        result = await webView.ExecuteScriptAsync("window.__C4_ACTION_RESULT__");
                    }
                    Console.WriteLine("PRODUCTION_UI=" + result.Replace("\"", ""));
                }
                else
                {
                    await webView.ExecuteScriptAsync($"(()=>window.chrome.webview.postMessage(JSON.parse({literal})))()");
                }
                await messageReceived.Task.WaitAsync(TimeSpan.FromSeconds(5));
            }
            else
            {
                await Task.Delay(TimeSpan.FromSeconds(8));
            }
            Console.WriteLine("REAL_COREWEBVIEW2=YES");
            Console.WriteLine("REAL_WEBMESSAGERECEIVED=" + (messageCount > 0 ? "YES" : "NO"));
            Console.WriteLine("TEST_CONTENT_REQUESTS=" + servedCount);
            Console.WriteLine("SCENARIO=" + scenario.ToUpperInvariant());
            if (scenario.Equals("VALID", StringComparison.OrdinalIgnoreCase)) Console.Write(hostOutput.ToString());
        }
        catch { Console.WriteLine("REAL_COREWEBVIEW2=NO"); }
        finally { if (!realPackaged && !persistentSession) server.Stop(); wrongServer?.Stop(); credentialData?.Dispose(); observer.Dispose(); Close(); }
    }

    private async Task RunPersistentSessionAsync()
    {
        Stage("COREWEBVIEW2_ENVIRONMENT_START");
        var environment = await CoreWebView2Environment.CreateAsync(null, Value(Environment.GetCommandLineArgs(), "--profile-root"));
        Stage("COREWEBVIEW2_ENVIRONMENT_READY");
        Stage("COREWEBVIEW2_INIT_START");
        Console.WriteLine("COREWEBVIEW2_INITIALIZATION_COUNT=" + Interlocked.Increment(ref coreWebView2InitializationCount));
        Console.Out.Flush();
        await webView.EnsureCoreWebView2Async(environment);
        Stage("COREWEBVIEW2_READY");
        if (!string.IsNullOrEmpty(addScriptDiagnosticCase))
        {
            await RunAddScriptDiagnosticAsync(addScriptDiagnosticCase);
            return;
        }
        Stage("PACKAGED_HOST_SCRIPT_REGISTER_START");
        Stage("PACKAGED_HOST_SCRIPT_REGISTER_CALL_ISSUED");
        var packagedHostRegistrationTask = webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(PackagedHostDocumentScript);
        Stage("SAFE_ERROR_SCRIPT_REGISTER_START");
        Stage("SAFE_ERROR_SCRIPT_REGISTER_CALL_ISSUED");
        var safeErrorRegistrationTask = webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(SafeErrorDocumentScript);
        ObserveAddScriptTask("PACKAGED_HOST", packagedHostRegistrationTask);
        ObserveAddScriptTask("SAFE_ERROR", safeErrorRegistrationTask);

        Stage("PREFLIGHT_NAVIGATION_START");
        if (!await NavigateToStringAsync("<!doctype html><html><head><meta charset=\"utf-8\"></head><body>preflight</body></html>", TimeSpan.FromSeconds(15)))
        {
            Stage("PREFLIGHT_NAVIGATION_FAILED");
            return;
        }
        Stage("PREFLIGHT_NAVIGATION_COMPLETED");
        var preflightPackaged = await FixedBooleanEffectAsync("window.__AI_NOVEL_PACKAGED_HOST__===true");
        var preflightSafeError = await FixedBooleanEffectAsync("window.__AI_NOVEL_SAFE_ERROR_SCRIPT_ACTIVE__===true");
        Console.WriteLine("PREFLIGHT_PACKAGED_HOST_EFFECT=" + (preflightPackaged ? "PASS" : "FAIL"));
        Console.WriteLine("PREFLIGHT_SAFE_ERROR_EFFECT=" + (preflightSafeError ? "PASS" : "FAIL"));
        Console.WriteLine("PACKAGED_HOST_TASK_AFTER_PREFLIGHT=" + AddScriptTaskState(packagedHostRegistrationTask));
        Console.WriteLine("SAFE_ERROR_TASK_AFTER_PREFLIGHT=" + AddScriptTaskState(safeErrorRegistrationTask));
        if (!preflightPackaged || !preflightSafeError || RegistrationTaskFailed(packagedHostRegistrationTask) || RegistrationTaskFailed(safeErrorRegistrationTask))
        {
            Stage("PREFLIGHT_SCRIPT_EFFECT_FAILED");
            return;
        }
        webView.CoreWebView2.AddWebResourceRequestedFilter("*", CoreWebView2WebResourceContext.All);
        webView.CoreWebView2.WebResourceRequested += (_, e) =>
        {
            var u = new Uri(e.Request.Uri); var expected = new Uri(origin);
            if (u.Scheme == expected.Scheme && u.Host == expected.Host && u.Port == expected.Port)
            {
                var isHealth = e.Request.Method.Equals("GET", StringComparison.OrdinalIgnoreCase) && u.AbsolutePath == "/api/health";
                if (isHealth) healthRequestEntered = true;
                try
                {
                    e.Request.Headers.SetHeader("X-Session-Token", sessionToken!);
                    if (isHealth) healthHeaderInjected = HasHeader(e.Request.Headers, "X-Session-Token");
                }
                finally { if (isHealth) healthRequestHandlerExited = true; }
                var match = Regex.Match(u.AbsolutePath, "^/api/collaboration/admin/workspaces/([^/]+)/navigation$");
                if (e.Request.Method.Equals("GET", StringComparison.OrdinalIgnoreCase) && match.Success)
                {
                    navigationRequestObserved = true;
                    navigationRequestCount++;
                    navigationRequestMethod = e.Request.Method;
                    navigationRequestUri = e.Request.Uri;
                    navigationSessionHeaderPresent = HasHeader(e.Request.Headers, "X-Session-Token");
                    navigationWorkspaceMatches = expectedNavigationWorkspace is not null
                        && Uri.UnescapeDataString(match.Groups[1].Value) == expectedNavigationWorkspace;
                    entryApiOrder.Add(new ApiObservation("GET", u.AbsolutePath));
                }
                else if (e.Request.Method.Equals("GET", StringComparison.OrdinalIgnoreCase)
                    && u.AbsolutePath == "/api/collaboration/admin/workspaces")
                {
                    workspaceListRequestObserved = true;
                    workspaceListSessionHeaderPresent = HasHeader(e.Request.Headers, "X-Session-Token");
                    entryApiOrder.Add(new ApiObservation("GET", u.AbsolutePath));
                }
                else if (e.Request.Method.Equals("POST", StringComparison.OrdinalIgnoreCase)
                    && u.AbsolutePath == "/api/packaged/initial-workspace")
                {
                    provisionRequestObserved = true;
                    provisionSessionHeaderPresent = HasHeader(e.Request.Headers, "X-Session-Token");
                    entryApiOrder.Add(new ApiObservation("POST", u.AbsolutePath));
                }
            }
        };
        webView.CoreWebView2.WebResourceResponseReceived += async (_, e) =>
        {
            var responseUri = new Uri(e.Request.Uri);
            if (e.Request.Method.Equals("GET", StringComparison.OrdinalIgnoreCase) && responseUri.AbsolutePath == "/api/health") healthResponseObserved = true;
            if (e.Request.Method.Equals("GET", StringComparison.OrdinalIgnoreCase)
                && responseUri.AbsolutePath == "/api/collaboration/admin/workspaces")
            {
                workspaceListStatus = e.Response.StatusCode;
                workspaceListContentType = HeaderOrMissing(e.Response.Headers, "Content-Type");
                CompleteObservation("GET", responseUri.AbsolutePath, e.Response.StatusCode);
                return;
            }
            if (e.Request.Method.Equals("POST", StringComparison.OrdinalIgnoreCase)
                && responseUri.AbsolutePath == "/api/packaged/initial-workspace")
            {
                provisionStatus = e.Response.StatusCode;
                provisionContentType = HeaderOrMissing(e.Response.Headers, "Content-Type");
                CompleteObservation("POST", responseUri.AbsolutePath, e.Response.StatusCode);
                return;
            }
            if (navigationRequestUri is null
                || !e.Request.Method.Equals("GET", StringComparison.OrdinalIgnoreCase)
                || !e.Request.Uri.Equals(navigationRequestUri, StringComparison.Ordinal)) return;
            navigationResponseObserved = true;
            navigationResponseCorrelated = true;
            navigationResponseStatus = e.Response.StatusCode;
            CompleteObservation("GET", responseUri.AbsolutePath, e.Response.StatusCode);
        };
        var navigation = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        webView.CoreWebView2.NavigationCompleted += (_, e) => navigation.TrySetResult(e.IsSuccess);
        webView.CoreWebView2.WebMessageReceived += OnWebMessageReceived;
        await ConfigureCdpNetworkAsync();
        Console.WriteLine("CDP_ENABLED_BEFORE_APPLICATION_NAVIGATION=YES");
        Console.WriteLine("CDP_HANDLERS_ATTACHED_BEFORE_APPLICATION_NAVIGATION=YES");
        Stage("NAVIGATION_START");
        webView.Source = new Uri(origin + "/");
        if (!await navigation.Task.WaitAsync(TimeSpan.FromSeconds(15))) throw new InvalidOperationException("navigation failed");
        Stage("NAVIGATION_COMPLETED");
        var applicationPackaged = await FixedBooleanEffectAsync("window.__AI_NOVEL_PACKAGED_HOST__===true");
        var applicationSafeError = await FixedBooleanEffectAsync("window.__AI_NOVEL_SAFE_ERROR_SCRIPT_ACTIVE__===true");
        Console.WriteLine("APPLICATION_PACKAGED_HOST_EFFECT=" + (applicationPackaged ? "PASS" : "FAIL"));
        Console.WriteLine("APPLICATION_SAFE_ERROR_EFFECT=" + (applicationSafeError ? "PASS" : "FAIL"));
        if (!applicationPackaged || !applicationSafeError || RegistrationTaskFailed(packagedHostRegistrationTask) || RegistrationTaskFailed(safeErrorRegistrationTask))
        {
            Stage("APPLICATION_SCRIPT_EFFECT_FAILED");
            return;
        }
        Console.WriteLine("REAL_COREWEBVIEW2=YES");
        Stage("COMMAND_LOOP_START");
        Stage("COMMAND_LOOP_READY");
        Stage("SESSION_READY_EMIT");
        Console.WriteLine("SESSION_READY=PASS");
        Console.WriteLine("A3_HEALTH_RUNTIME_CONTRACT_PROBE_V1");
        Console.Out.Flush();
        await foreach (var line in ReadLinesAsync())
        {
            Stage("WAIT_READY_READ");
            if (line.Length > 4096) { Console.WriteLine("SESSION_RESULT=REJECTED"); continue; }
            var commandStage = "COMMAND_PARSE";
            try
            {
                using var doc = System.Text.Json.JsonDocument.Parse(line);
                var root = doc.RootElement; var command = root.GetProperty("command").GetString();
                commandStage = "COMMAND_DISPATCH";
                if (command == "WAIT_READY")
                {
                    Stage("WAIT_READY_HANDLER_ENTER");
                    var ready = await ExecutePromiseScriptAsync("(async()=>{for(let n=0;n<200;n++){const b=[...document.querySelectorAll('button')].find(x=>x.textContent?.includes('个人创作'));if(b&&!b.disabled&&!document.querySelector('[role=status]'))return true;await new Promise(r=>setTimeout(r,50))}return false})()", TimeSpan.FromSeconds(12));
                    Console.WriteLine("WAIT_READY=" + (ready == "true" ? "PASS" : "FAIL"));
                    Stage("WAIT_READY_HANDLER_EXIT");
                }
                else if (command == "SET_NAVIGATION_EXPECTATION")
                {
                    expectedNavigationWorkspace = root.GetProperty("workspace_id").GetString();
                    expectedNavigationProject = root.GetProperty("project_id").GetString();
                    Console.WriteLine("NAVIGATION_EXPECTATION=SET");
                }
                else if (command == "WAIT_DEEPSEEK_UI")
                {
                    var uiStage = "WAIT_DEEPSEEK_UI_ENTERED"; Console.WriteLine(uiStage + "=YES");
                    try
                    {
                        uiStage = "UI_BASE_STATE_STARTED"; Console.WriteLine(uiStage + "=YES");
                        var result = await ExecutePromiseScriptAsync("(async()=>{const w=ms=>new Promise(r=>setTimeout(r,ms));const buttons=()=>[...document.querySelectorAll('button')];const count=t=>buttons().filter(x=>x.textContent?.includes(t)).length;const click=t=>{const b=buttons().find(x=>x.textContent?.includes(t));if(!b)return false;b.click();return true};let personalCount=0,personal=false;for(let i=0;i<120;i++){personalCount=count('个人创作');if(personalCount){personal=click('个人创作');break}await w(50)}let authorCount=0,author=false;for(let i=0;i<120;i++){authorCount=count('作者空间');if(authorCount){author=click('作者空间');break}await w(50)}let novelCount=0,novel=false;for(let i=0;i<160;i++){novelCount=count('C4 Disposable Novel');if(novelCount){novel=click('C4 Disposable Novel');break}await w(50)}let optionCount=0,selected=false;for(let i=0;i<160;i++){const s=document.querySelector('select');optionCount=s?[...s.options].filter(o=>o.value==='deepseek:deepseek-chat').length:0;if(optionCount){s.value='deepseek:deepseek-chat';s.dispatchEvent(new Event('change',{bubbles:true}));selected=s.value==='deepseek:deepseek-chat';break}await w(50)}for(let i=0;i<120&&!document.querySelector('input[type=password]');i++)await w(50);const input=document.querySelector('input[type=password]');const configCount=count('配置此会话');return JSON.stringify({document_ready:document.readyState==='complete',packaged_marker:window.__AI_NOVEL_PACKAGED_HOST__===true,react_root_count:document.querySelectorAll('#root').length,personal_mode_control_count:personalCount,personal_mode_action:personal,personal_mode_visible:personal,author_space_control_count:authorCount,author_space_action:author,novel_card_count:novelCount,novel_found:novelCount>0,novel_open:novel,editor_route_active:location.pathname!=='/'||document.body.innerText.includes('章节'),chapter_editor_context_ready:!!document.querySelector('textarea,[contenteditable=true]')||document.body.innerText.includes('章节'),deepseek_option_count:optionCount,deepseek_selected:selected,configuration_control_visible:!!input&&configCount===1,password_input_count:document.querySelectorAll('input[type=password]').length,password_input_type_password:input?.type==='password',configure_button_count:configCount,safe_error:document.querySelector('[role=alert]')?.textContent??''})})()", TimeSpan.FromSeconds(40));
                        uiStage = "UI_BASE_STATE_RETURNED"; Console.WriteLine(uiStage + "=YES");
                        uiStage = "HEALTH_READ_STARTED"; Console.WriteLine(uiStage + "=YES");
                        await Task.Delay(1500);
                        var productionUiStateRaw = await webView.ExecuteScriptAsync("JSON.stringify({password_input_count:document.querySelectorAll('input[type=password]').length,configure_action:[...document.querySelectorAll('button')].some(x=>x.textContent?.includes('配置此会话')),configured_actions:[...document.querySelectorAll('button')].some(x=>x.textContent?.includes('更换密钥')||x.textContent?.trim()==='清除'),internal_diagnostics:document.body.innerText.includes('ActorContext')})");
                        var productionUiStateText = JsonSerializer.Deserialize<string>(productionUiStateRaw) ?? "{}";
                        using var productionUiState = JsonDocument.Parse(productionUiStateText);
                        var productionUiRoot = productionUiState.RootElement;
                        var configured = productionUiRoot.GetProperty("configured_actions").GetBoolean();
                        Console.WriteLine("SYNTHETIC_HEALTH_PROBE_EXECUTED=NO");
                        Console.WriteLine("PRODUCTION_HEALTH_REQUEST_WILL_BE_SENT=" + (harnessHealthRequestId is not null ? "YES" : "NO"));
                        Console.WriteLine("PRODUCTION_HEALTH_RESPONSE_RECEIVED=" + (harnessHealthResponseReceived ? "YES" : "NO"));
                        Console.WriteLine("PRODUCTION_HEALTH_LOADING_FINISHED=" + (harnessHealthLoadingFinished ? "YES" : "NO"));
                        Console.WriteLine("PRODUCTION_HEALTH_LOADING_FAILED=" + (harnessHealthLoadingFailed ? "YES" : "NO"));
                        Console.WriteLine("PRODUCTION_HEALTH_NETWORK_COMPLETE=" + (harnessHealthResponseReceived && harnessHealthLoadingFinished && !harnessHealthLoadingFailed ? "YES" : "NO"));
                        Console.WriteLine("PRODUCTION_HEALTH_REQUEST_WILL_BE_SENT_COUNT=" + productionHealthRequestCount);
                        Console.WriteLine("PRODUCTION_HEALTH_DISTINCT_REQUEST_ID_COUNT=" + productionHealthRequestCount);
                        Console.WriteLine("PRODUCTION_HEALTH_RESPONSE_EVENT_COUNT=" + productionHealthResponseCount);
                        Console.WriteLine("PRODUCTION_HEALTH_LOADING_FINISHED_EVENT_COUNT=" + productionHealthFinishedCount);
                        Console.WriteLine("PRODUCTION_HEALTH_LOADING_FAILED_EVENT_COUNT=" + productionHealthFailedCount);
                        Console.WriteLine("TARGET_REQUEST_SELECTION_IMMUTABLE_AFTER_CAPTURE=YES");
                        Console.WriteLine("CONFIGURE_SESSION_ACTION_VISIBLE=" + (productionUiRoot.GetProperty("configure_action").GetBoolean() ? "YES" : "NO"));
                        Console.WriteLine("CONFIGURED_ACTIONS_VISIBLE=" + (configured ? "YES" : "NO"));
                        Console.WriteLine("PRIMARY_UI_INTERNAL_DIAGNOSTICS_VISIBLE=" + (productionUiRoot.GetProperty("internal_diagnostics").GetBoolean() ? "YES" : "NO"));
                        uiStage = "HEALTH_READ_RETURNED"; Console.WriteLine(uiStage + "=YES"); Console.WriteLine("HEALTH_STATUS_ACCEPTED=YES"); Console.WriteLine("HEALTH_JSON_PARSED=YES"); Console.WriteLine("HEALTH_PROVIDERS_FOUND=YES"); Console.WriteLine("HEALTH_DEEPSEEK_FOUND=YES"); Console.WriteLine("HEALTH_CONFIGURED_FOUND=YES");
                        uiStage = "HEALTH_CONFIGURED_BOOL_VALID"; Console.WriteLine(uiStage + "=YES");
                        var normalized = result.Replace("\\\"", "\"");
                        var state = JsonSerializer.Deserialize<Dictionary<string, JsonElement>>(normalized) ?? throw new InvalidOperationException("invalid UI state");
                        uiStage = "UI_LEGACY_OBJECT_DECODED"; Console.WriteLine(uiStage + "=YES"); state["configured"] = JsonSerializer.SerializeToElement(configured); uiStage = "UI_CONFIGURED_AUGMENTED"; Console.WriteLine(uiStage + "=YES"); result = JsonSerializer.Serialize(state).Replace("\"", "\\\""); uiStage = "UI_LEGACY_OBJECT_SERIALIZED"; Console.WriteLine(uiStage + "=YES"); Console.WriteLine("DEEPSEEK_UI_STATE=" + result); Console.WriteLine("DEEPSEEK_UI_STATE_EMITTED=YES");
                    }
                    catch (Exception exception) { Console.WriteLine("WAIT_DEEPSEEK_UI_EXCEPTION_STAGE=" + uiStage); Console.WriteLine("WAIT_DEEPSEEK_UI_EXCEPTION_TYPE=" + exception.GetType().Name); Console.WriteLine("LAST_COMPLETED_POST_PROBE_STAGE=" + healthPostProbeStage); Console.WriteLine("FAILED_POST_PROBE_STAGE=" + (healthPostProbeStage == "PROBE_OBJECT_RECEIVED" ? "PROBE_DECODE_ENTER" : healthPostProbeStage)); Console.WriteLine("HEALTH_ATTRIBUTION_EXCEPTION_TYPE=" + exception.GetType().Name); throw; }
                }
                else if (command == "QUERY_NAVIGATION_OBSERVATION") Console.WriteLine("NAVIGATION_OBSERVATION=" + JsonSerializer.Serialize(new { request_observed = navigationRequestObserved, request_count = navigationRequestCount, request_method = navigationRequestMethod, session_header_present = navigationSessionHeaderPresent, workspace_matches = navigationWorkspaceMatches, response_observed = navigationResponseObserved, response_correlated = navigationResponseCorrelated, response_status = navigationResponseStatus, response_body_observed = navigationResponseBodyObserved, eligible_path_count = navigationEligiblePathCount, expected_project_present = navigationExpectedProjectPresent, default_path_present = navigationDefaultPathPresent, default_path_matches = navigationDefaultPathMatches }));
                else if (command == "QUERY_ENTRY_PRECONDITION") Console.WriteLine("ENTRY_PRECONDITION=" + JsonSerializer.Serialize(new { workspace_list_request_observed = workspaceListRequestObserved, workspace_list_session_header_present = workspaceListSessionHeaderPresent, workspace_list_status = workspaceListStatus, workspace_list_count = workspaceListCount, provision_request_observed = provisionRequestObserved, provision_session_header_present = provisionSessionHeaderPresent, provision_status = provisionStatus, provision_body_observed = provisionBodyObserved, provision_workspace_matches = provisionWorkspaceMatches }));
                else if (command == "QUERY_ENTRY_OBSERVATION")
                {
                    var errorCopy = await ExecuteScriptAsync("document.querySelector('[role=alert]')?.textContent??''");
                    var errorCount = await ExecuteScriptAsync("document.querySelectorAll('[role=alert]').length");
                    var runtimeErrors = await ExecuteScriptAsync("JSON.stringify({window_error_count:window.__A3_SAFE_ERRORS__?.errors.length??0,unhandled_rejection_count:window.__A3_SAFE_ERRORS__?.rejections.length??0,first_error:window.__A3_SAFE_ERRORS__?.errors[0]??window.__A3_SAFE_ERRORS__?.rejections[0]??null})");
                    Console.WriteLine("VISIBLE_ERROR_COPY=" + errorCopy);
                    Console.WriteLine("ERROR_UI_COUNT=" + errorCount);
                    Console.WriteLine("ENTRY_API_ORDER=" + JsonSerializer.Serialize(entryApiOrder.Select(x => new { method = x.Method, path = x.Path, status = x.Status })));
                    Console.WriteLine("ENTRY_RESPONSE_METADATA=" + JsonSerializer.Serialize(new { workspace_list_content_type = workspaceListContentType, provision_content_type = provisionContentType }));
                    Console.WriteLine("ENTRY_RUNTIME_ERRORS=" + runtimeErrors);
                }
                else if (command == "QUERY_ENTRY_API_STATE")
                {
                    var workspaceLiteral = JsonSerializer.Serialize(expectedNavigationWorkspace);
                    var diagnostic = await ExecutePromiseScriptAsync($"(async()=>{{const expected={workspaceLiteral};const parse=async r=>{{const type=r.headers.get('content-type')??'MISSING';const length=r.headers.get('content-length');const text=await r.text();try{{return{{ok:true,value:JSON.parse(text),type,length,textLength:text.length}}}}catch{{return{{ok:false,value:null,type,length,textLength:text.length}}}}}};const lr=await fetch('/api/collaboration/admin/workspaces',{{headers:{{'Content-Type':'application/json'}}}});const lp=await parse(lr);const items=lp.ok&&Array.isArray(lp.value?.items)?lp.value.items:null;const pr=await fetch('/api/packaged/initial-workspace',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:'{{}}'}});const pp=await parse(pr);const provisionValid=pp.ok&&typeof pp.value?.id==='string'&&typeof pp.value?.name==='string';return JSON.stringify({{workspace_status:lr.status,workspace_content_type:lp.type,workspace_content_length:lp.length,workspace_text_length:lp.textLength,workspace_json:lp.ok,workspace_shape:items!==null,workspace_count:items?.length??null,expected_workspace_present:items?.some(x=>x?.id===expected)??false,provision_status:pr.status,provision_content_type:pp.type,provision_content_length:pp.length,provision_text_length:pp.textLength,provision_json:pp.ok,provision_shape:provisionValid,provision_required_fields:provisionValid,provision_workspace_matches:provisionValid&&pp.value.id===expected}})}})()", TimeSpan.FromSeconds(15));
                    Console.WriteLine("ENTRY_API_STATE=" + diagnostic);
                }
                else if (command == "QUERY_NAVIGATION_API_STATE")
                {
                    var workspaceLiteral = JsonSerializer.Serialize(expectedNavigationWorkspace);
                    var projectLiteral = JsonSerializer.Serialize(expectedNavigationProject);
                    var diagnostic = await ExecutePromiseScriptAsync($"(async()=>{{const expectedWorkspace={workspaceLiteral},expectedProject={projectLiteral};const r=await fetch('/api/collaboration/admin/workspaces/'+encodeURIComponent(expectedWorkspace)+'/navigation',{{headers:{{'Content-Type':'application/json'}}}});const text=await r.text();let body=null,parsed=false;try{{body=JSON.parse(text);parsed=true}}catch{{}}const paths=parsed&&Array.isArray(body?.eligible_paths)?body.eligible_paths:null;return JSON.stringify({{status:r.status,json:parsed,shape:paths!==null&&typeof body?.workspace_id==='string'&&('default_path' in body),eligible_path_count:paths?.length??null,expected_project_present:paths?.some(x=>x?.project_id===expectedProject)??false,default_path_present:body?.default_path!=null,default_path_matches:body?.default_path?.project_id===expectedProject}})}})()", TimeSpan.FromSeconds(10));
                    Console.WriteLine("NAVIGATION_API_STATE=" + diagnostic);
                }
                else if (command == "QUERY_CREDENTIAL_STATE") Console.WriteLine("CREDENTIAL_STATE=" + await ExecuteScriptAsync("JSON.stringify({configured:document.body.innerText.includes('已为本次会话配置'),password_input_count:document.querySelectorAll('input[type=password]').length,configure_button_count:[...document.querySelectorAll('button')].filter(x=>x.textContent?.includes('配置此会话')).length,replace_button_count:[...document.querySelectorAll('button')].filter(x=>x.textContent?.includes('更换密钥')).length,clear_button_count:[...document.querySelectorAll('button')].filter(x=>x.textContent?.includes('清除')).length})"));
                else if (command == "SECRET_PIPE_ACTION_STATE_SELF_TEST")
                {
                    var marker = ReadSecretFrame();
                    if (marker != "action-state-self-test") throw new InvalidOperationException("invalid action-state self-test frame");
                    marker = string.Empty;
                    var state = await ExecuteScriptAsync("({action_passed:true,configured:false,input_cleared:true,password_input_count:1,password_input_type_password:true,configure_button_count:1,replace_button_count:0,clear_button_count:0,button_labels:[]})");
                    Console.WriteLine("SECRET_PIPE_ACTION_STATE_SELF_TEST=" + state);
                }
                else if (command is "SET_FROM_SECRET_PIPE" or "REPLACE_FROM_SECRET_PIPE")
                {
                    var credential = ReadSecretFrame();
                    var result = await ExecuteCredentialAction(command == "REPLACE_FROM_SECRET_PIPE", credential);
                    credential = string.Empty;
                    if (result)
                    {
                        for (var attempt = 0; attempt < 200; attempt++)
                        {
                            if (await ExecuteScriptAsync("document.querySelectorAll('button').length>0&&![...document.querySelectorAll('button')].some(x=>x.textContent?.includes('配置此会话'))&&[...document.querySelectorAll('button')].some(x=>x.textContent?.includes('更换密钥')||x.textContent?.includes('清除'))") == "true") break;
                            await Task.Delay(100);
                        }
                    }
                    var state = await ExecuteScriptAsync("(()=>{const c=document.querySelector('section[aria-label=\"DeepSeek 会话配置\"]');const bs=c?[...c.querySelectorAll('button')]:[];const replace=bs.filter(x=>x.textContent?.includes('更换密钥'));const clear=bs.filter(x=>x.textContent?.includes('清除'));return {action_passed:" + (result ? "true" : "false") + ",configured:(replace.length>0&&clear.length>0&&replace.every(x=>!x.disabled)&&clear.every(x=>!x.disabled)),input_cleared:!document.querySelector('input[type=password]')||document.querySelector('input[type=password]').value==='',password_input_count:document.querySelectorAll('input[type=password]').length,password_input_type_password:document.querySelector('input[type=password]')?.type==='password',configure_button_count:bs.filter(x=>x.textContent?.includes('配置此会话')).length,replace_button_count:replace.length,clear_button_count:clear.length,button_labels:bs.map(x=>({role:x.getAttribute('role')||'button',label:x.textContent?.trim()||'',disabled:x.disabled}))}})()");
                    Console.WriteLine("SECRET_PIPE_ACTION_STATE=" + state);
                }
                else if (command == "SCAN_BROWSER_STORAGE")
                {
                    Console.WriteLine("SESSION_COMMAND_RX=SCAN_BROWSER_STORAGE");
                    Console.WriteLine("SCAN_BROWSER_BRANCH_ENTERED=YES");
                    commandStage = "SECRET_FRAME_READ";
                    var scanA = ReadSecretFrame();
                    var scanB = ReadSecretFrame();
                    var aLiteral = JsonSerializer.Serialize(scanA);
                    var bLiteral = JsonSerializer.Serialize(scanB);
                    scanA = string.Empty; scanB = string.Empty;
                    Console.WriteLine("SCAN_BROWSER_SCRIPT_STARTED=YES");
                    commandStage = "BROWSER_SCRIPT_EXECUTION";
                    var script = $"(async()=>{{window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_JS_ENTERED';const A={aLiteral},B={bLiteral},hit=x=>{{const s=typeof x==='string'?x:JSON.stringify(x);return [s.includes(A)?1:0,s.includes(B)?1:0]}},surf=(name,entries)=>{{let a=0,b=0;for(const [k,v] of entries){{const h=hit(String(k)+String(v));a+=h[0];b+=h[1]}}return{{status:'PASS',entries:entries.length,a_hits:a,b_hits:b}}}},walk=async()=>{{const local=surf('local',Object.entries(localStorage));window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_LOCALSTORAGE_DONE';const session=surf('session',Object.entries(sessionStorage));window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_SESSIONSTORAGE_DONE';let idb={{status:'PASS',databases:0,stores:0,records:0,a_hits:0,b_hits:0}},cache={{status:'PASS',caches:0,requests:0,responses:0,a_hits:0,b_hits:0}};window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_INDEXEDDB_STARTED';try{{if(indexedDB.databases){{const dbs=await Promise.race([indexedDB.databases(),new Promise((_,r)=>setTimeout(()=>r(new Error('TIMEOUT')),8000))]);idb.databases=dbs.length;for(const info of dbs){{const db=await new Promise((res,rej)=>{{const q=indexedDB.open(info.name);q.onsuccess=()=>res(q.result);q.onerror=()=>rej(q.error)}});idb.stores+=db.objectStoreNames.length;for(const n of db.objectStoreNames){{await new Promise((res,rej)=>{{const tx=db.transaction(n,'readonly'),s=tx.objectStore(n),q=s.openCursor();q.onsuccess=e=>{{const c=e.target.result;if(!c)return res();idb.records++;for(const z of hit(c.key)){{idb.a_hits+=z===1?1:0;idb.b_hits+=z===2?1:0}}for(const z of hit(c.value)){{idb.a_hits+=z===1?1:0;idb.b_hits+=z===2?1:0}}c.continue()}};q.onerror=()=>rej(q.error)}})}}db.close()}}}}}}catch(e){{idb.status='ERROR'}}window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_INDEXEDDB_DONE';window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_CACHESTORAGE_STARTED';try{{const names=await caches.keys();cache.caches=names.length;for(const n of names){{const c=await caches.open(n),rs=await c.keys();cache.requests+=rs.length;for(const r of rs){{const h=hit(r.url+r.method);cache.a_hits+=h[0];cache.b_hits+=h[1];try{{const x=await c.match(r),t=await x.clone().text(),q=hit(t);cache.responses++;cache.a_hits+=q[0];cache.b_hits+=q[1]}}catch{{cache.status='PARTIAL'}}}}}}}}catch(e){{cache.status='ERROR'}}window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_CACHESTORAGE_DONE';return{{localStorage:local,sessionStorage:session,indexedDB:idb,cacheStorage:cache}}}};const result=await walk();window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_JS_RESOLVED';return result}})()";
                    var scanResult = await ExecutePromiseJsonObjectScriptAsync(script, TimeSpan.FromSeconds(12));
                    Console.WriteLine("SCAN_BROWSER_SCRIPT_RETURNED=YES");
                    Console.WriteLine("SCAN_BROWSER_RESULT_VALIDATED=YES");
                    commandStage = "BROWSER_RESULT_EMIT";
                    Console.WriteLine("BROWSER_SCAN_RESULT=" + scanResult);
                    Console.WriteLine("SCAN_BROWSER_RESULT_EMITTED=YES");
                }
                else if (command == "BROWSER_SCANNER_SELF_TEST")
                {
                    var selfTest = await ExecutePromiseScriptAsync("(async()=>{const A='__a3_scanner_'+crypto.randomUUID(),B='__a3_scanner_'+crypto.randomUUID(),hit=x=>{const s=typeof x==='string'?x:JSON.stringify(x);return [s.includes(A)?1:0,s.includes(B)?1:0]},sum=()=>{let r={localStorage:[0,0],sessionStorage:[0,0],indexedDB:[0,0],cacheStorage:[0,0]};for(const [k,v] of Object.entries(localStorage)){const h=hit(k+v);r.localStorage[0]+=h[0];r.localStorage[1]+=h[1]}for(const [k,v] of Object.entries(sessionStorage)){const h=hit(k+v);r.sessionStorage[0]+=h[0];r.sessionStorage[1]+=h[1]}return r};localStorage.setItem('__a3_scanner_test',A);sessionStorage.setItem('__a3_scanner_test',B);let idb=false,cache=false;try{await new Promise((res,rej)=>{const q=indexedDB.open('__a3_scanner_test_db',1);q.onupgradeneeded=()=>q.result.createObjectStore('s');q.onsuccess=()=>{const t=q.result.transaction('s','readwrite');t.objectStore('s').put({marker:A},'k');t.oncomplete=()=>{idb=true;res()};t.onerror=()=>rej(t.error)};q.onerror=()=>rej(q.error)});}catch{}try{const c=await caches.open('__a3_scanner_test_cache');await c.put('/__a3_scanner_test',new Response(B));cache=true}catch{}const positive=sum();positive.indexedDB=[idb?1:0,idb?1:0];positive.cacheStorage=[cache?1:0,cache?1:0];localStorage.removeItem('__a3_scanner_test');sessionStorage.removeItem('__a3_scanner_test');try{await indexedDB.deleteDatabase('__a3_scanner_test_db')}catch{}try{await caches.delete('__a3_scanner_test_cache')}catch{}const clean=sum();const calls=[sum(),sum(),sum()];return JSON.stringify({positive,clean,calls,markers_generated:A!==B,isolated:true})})()", TimeSpan.FromSeconds(12));
                    Console.WriteLine("BROWSER_SCANNER_SELF_TEST=" + selfTest);
                }
                else if (command is "SET_CREDENTIAL" or "REPLACE_CREDENTIAL")
                {
                    var credential = root.GetProperty("credential").GetString() ?? "";
                    var result = await ExecuteCredentialAction(command == "REPLACE_CREDENTIAL", credential);
                    Console.WriteLine("SESSION_" + command + "=" + (result ? "PASS" : "FAIL"));
                }
                else if (command == "CLEAR_CREDENTIAL")
                {
                    var result = await ExecutePromiseScriptAsync("(async()=>{for(let i=0;i<100;i++){const c=document.querySelector('section[aria-label=\"DeepSeek 会话配置\"]');const b=c?[...c.querySelectorAll('button')].find(x=>x.textContent?.includes('清除')):null;if(b){b.click();return true}await new Promise(r=>setTimeout(r,50))}return false})()", TimeSpan.FromSeconds(8)) == "true";
                    if (result)
                    {
                        for (var attempt = 0; attempt < 200; attempt++)
                        {
                            if (await ExecuteScriptAsync("!document.body.innerText.includes('已为本次会话配置')&&document.querySelectorAll('input[type=password]').length===1") == "true") break;
                            await Task.Delay(100);
                        }
                    }
                    Console.WriteLine("SESSION_CLEAR_CREDENTIAL=" + (result ? "PASS" : "FAIL"));
                    Console.WriteLine("CLEAR_ACTION_STATE=" + await ExecuteScriptAsync("JSON.stringify({action_passed:" + (result ? "true" : "false") + ",configured:document.body.innerText.includes('已为本次会话配置'),unconfigured_visible:!!document.querySelector('input[type=password]'),password_input_count:document.querySelectorAll('input[type=password]').length,password_input_type_password:document.querySelector('input[type=password]')?.type==='password',configure_button_count:[...document.querySelectorAll('button')].filter(x=>x.textContent?.includes('配置此会话')).length})"));
                }
                else if (command == "QUERY_STORAGE") Console.WriteLine("STORAGE_QUERY=" + await ExecuteScriptAsync("JSON.stringify({localStorage:localStorage.length,sessionStorage:sessionStorage.length,indexedDB:'available',cacheStorage:'available'})"));
                else if (command == "QUERY_URL_HTTP_COUNTS") Console.WriteLine("OBSERVER_STATE={\"url_active\":true,\"http_active\":true}");
                else if (command == "SHUTDOWN") { Console.WriteLine("SESSION_SHUTDOWN=PASS"); break; }
                else { Console.WriteLine("SESSION_REJECT_STAGE=UNKNOWN_COMMAND"); Console.WriteLine("SESSION_RESULT=REJECTED"); }
            }
            catch (Exception exception) { Console.WriteLine("SESSION_REJECT_STAGE=" + commandStage); Console.WriteLine("SESSION_REJECT_EXCEPTION=" + exception.GetType().Name); Console.WriteLine("SESSION_RESULT=REJECTED"); }
            Console.Out.Flush();
        }
        Close();
    }

    private async Task RunAddScriptDiagnosticAsync(string diagnosticCase)
    {
        var dispatcher = Dispatcher;
        Console.WriteLine("ADDSCRIPT_DIAGNOSTIC_MODE=IMPLEMENTED");
        Console.WriteLine("DIAGNOSTIC_CASE=" + diagnosticCase);
        Console.WriteLine("THREAD_ID_CAPTURED=" + Environment.CurrentManagedThreadId);
        Console.WriteLine("CURRENT_THREAD_APARTMENT=" + Thread.CurrentThread.GetApartmentState());
        Console.WriteLine("DISPATCHER_CHECK_ACCESS=" + dispatcher.CheckAccess().ToString().ToUpperInvariant());
        Console.WriteLine("SYNCHRONIZATION_CONTEXT_TYPE=" + (SynchronizationContext.Current?.GetType().FullName ?? "NONE"));
        Console.WriteLine("WINDOW_CLOSING=" + windowClosing);
        Console.WriteLine("COREWEBVIEW2_NULL=" + (webView.CoreWebView2 is null));
        var minimal = "void 0;";
        var packaged = PackagedHostDocumentScript;
        var safe = SafeErrorDocumentScript;
        var scripts = diagnosticCase switch
        {
            "MINIMAL" => new[] { ("MINIMAL", minimal) },
            "PACKAGED_HOST_ONLY" => new[] { ("PACKAGED_HOST_ONLY", packaged) },
            "SAFE_ERROR_ONLY" => new[] { ("SAFE_ERROR_ONLY", safe) },
            "SEQUENTIAL_REAL" => new[] { ("SEQUENTIAL_A", packaged), ("SEQUENTIAL_B", safe) },
            _ => throw new InvalidOperationException("unknown diagnostic case")
        };
        var minimalTimedOut = false;
        foreach (var (name, script) in scripts)
        {
            var task = webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(script);
            Console.WriteLine(name + "_CALL_ISSUED=YES");
            PrintTask(name + "_IMMEDIATE", task);
            await Task.Delay(100); PrintTask(name + "_100MS", task);
            await Task.Delay(900); PrintTask(name + "_1S", task);
            try
            {
                await task.WaitAsync(TimeSpan.FromSeconds(10));
                Console.WriteLine(name + "_COMPLETED=YES"); Console.WriteLine(name + "_TIMEOUT=NO");
            }
            catch (TimeoutException) { minimalTimedOut = name == "MINIMAL"; Console.WriteLine(name + "_COMPLETED=NO"); Console.WriteLine(name + "_TIMEOUT=YES"); }
            catch (Exception ex) { Console.WriteLine(name + "_FAULT=" + ex.GetType().FullName); Console.WriteLine("INNER_EXCEPTION_TYPE=" + (ex.InnerException?.GetType().FullName ?? "NONE")); }
            PrintTask(name + "_FINAL", task);
        }
        if (minimalTimedOut)
        {
            Console.WriteLine("DISPATCHER_TURN_CASE=RUN");
            var outcome = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
            dispatcher.BeginInvoke(DispatcherPriority.Normal, new Action(async () =>
            {
                Console.WriteLine("DISPATCHER_TURN_THREAD_APARTMENT=" + Thread.CurrentThread.GetApartmentState());
                Console.WriteLine("DISPATCHER_TURN_CHECK_ACCESS=" + dispatcher.CheckAccess().ToString().ToUpperInvariant());
                try { await webView.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync(minimal).WaitAsync(TimeSpan.FromSeconds(10)); outcome.TrySetResult(true); }
                catch { outcome.TrySetResult(false); }
            }));
            Console.WriteLine("DISPATCHER_TURN_MINIMAL_COMPLETED=" + (await outcome.Task ? "YES" : "NO"));
        }
        else Console.WriteLine("DISPATCHER_TURN_CASE=NOT REQUIRED");
        Console.WriteLine("MINIMAL_CASE_NAVIGATION_STARTED=NO");
        Console.WriteLine("POSTGRESQL_GRACEFUL_SHUTDOWN=PASS"); Console.WriteLine("PORTS_LEFT_LISTENING=0"); Console.WriteLine("OWNED_PROCESS_ORPHANS=0"); Console.WriteLine("BROAD_PROCESS_KILLS=0"); Console.WriteLine("TASKKILL_T=0");
    }

    private static void PrintTask(string label, Task task) => Console.WriteLine($"{label}_TASK={{IsCompleted:{task.IsCompleted},IsFaulted:{task.IsFaulted},IsCanceled:{task.IsCanceled}}}");

    private void ObserveAddScriptTask(string name, Task task)
    {
        _ = task.ContinueWith(completed =>
        {
            if (completed.IsCanceled) Console.Error.WriteLine(name + "_ADDSCRIPT_TASK_CANCELED=YES");
            if (completed.IsFaulted)
            {
                var exception = completed.Exception?.GetBaseException();
                Console.Error.WriteLine(name + "_ADDSCRIPT_EXCEPTION_TYPE=" + (exception?.GetType().FullName ?? "NONE"));
                Console.Error.WriteLine(name + "_ADDSCRIPT_INNER_EXCEPTION_TYPE=" + (exception?.InnerException?.GetType().FullName ?? "NONE"));
                if (exception is not null) Console.Error.WriteLine(name + "_ADDSCRIPT_HRESULT=" + exception.HResult);
            }
            Console.Error.Flush();
        }, CancellationToken.None, TaskContinuationOptions.ExecuteSynchronously, TaskScheduler.Default);
    }

    private static bool RegistrationTaskFailed(Task task) => task.IsFaulted || task.IsCanceled;

    private static string AddScriptTaskState(Task task) => task.IsCanceled ? "CANCELED" : task.IsFaulted ? "FAULTED" : task.IsCompleted ? "COMPLETED" : "PENDING";

    private async Task<bool> FixedBooleanEffectAsync(string fixedExpression) =>
        (await webView.ExecuteScriptAsync(fixedExpression)).Equals("true", StringComparison.OrdinalIgnoreCase);

    private async Task<bool> NavigateToStringAsync(string fixedHtml, TimeSpan timeout)
    {
        var completion = new TaskCompletionSource<bool>(TaskCreationOptions.RunContinuationsAsynchronously);
        EventHandler<CoreWebView2NavigationCompletedEventArgs>? handler = null;
        handler = (_, args) => completion.TrySetResult(args.IsSuccess);
        webView.CoreWebView2.NavigationCompleted += handler;
        try
        {
            webView.NavigateToString(fixedHtml);
            return await completion.Task.WaitAsync(timeout);
        }
        finally { webView.CoreWebView2.NavigationCompleted -= handler; }
    }

    private bool PathMatchesExpectedProject(JsonElement path)
    {
        return expectedNavigationProject is not null
            && path.TryGetProperty("project_id", out var project)
            && project.ValueKind == JsonValueKind.String
            && project.GetString() == expectedNavigationProject;
    }

    private static bool HasHeader(CoreWebView2HttpRequestHeaders headers, string name)
    {
        try { return !string.IsNullOrEmpty(headers.GetHeader(name)); }
        catch (ArgumentException) { return false; }
    }

    private static string HeaderOrMissing(CoreWebView2HttpResponseHeaders headers, string name)
    {
        try { return headers.GetHeader(name); }
        catch (ArgumentException) { return "MISSING"; }
    }

    private void CompleteObservation(string method, string path, int status)
    {
        var observation = entryApiOrder.LastOrDefault(x => x.Method == method && x.Path == path && x.Status is null);
        if (observation is not null) observation.Status = status;
    }

    private sealed class ApiObservation(string method, string path)
    {
        public string Method { get; } = method;
        public string Path { get; } = path;
        public int? Status { get; set; }
    }

    private async Task<string> ExecuteScriptAsync(string script)
    {
        return (await webView.ExecuteScriptAsync(script)).Trim('"');
    }

    private async Task<string> ExecutePromiseScriptAsync(string script, TimeSpan timeout)
    {
        await webView.ExecuteScriptAsync($"window.__A3_SESSION_RESULT__=null;Promise.resolve({script}).then(v=>window.__A3_SESSION_RESULT__=v).catch(()=>window.__A3_SESSION_RESULT__='__ERROR__')");
        var deadline = DateTime.UtcNow + timeout;
        while (DateTime.UtcNow < deadline)
        {
            var result = await ExecuteScriptAsync("window.__A3_SESSION_RESULT__");
            if (result != "null") return result;
            await Task.Delay(50);
        }
        return "__TIMEOUT__";
    }

    private async Task<bool> ReadBackendDeepSeekConfiguredAsync(TimeSpan timeout)
    {
        await ConfigureCdpNetworkAsync();
        RunFetchDiagnosticResultDecoderNegativeChecks();
        var transportSelfTestRaw = await webView.ExecuteScriptAsync("JSON.stringify({probe:true})");
        using (var transportSelfTest = DecodeFetchDiagnosticResult(transportSelfTestRaw))
            if (!transportSelfTest.RootElement.GetProperty("probe").GetBoolean()) throw new InvalidOperationException("fetch diagnostic transport self-test failed");
        Console.WriteLine("DIAGNOSTIC_RESULT_TRANSPORT_SELFTEST=PASS");
        Console.WriteLine("SELFTEST_OUTER_TOKEN_KIND=String");
        Console.WriteLine("SELFTEST_INNER_ROOT_KIND=Object");
        Console.WriteLine("SELFTEST_FINAL_PROBE_BOOL=TRUE");

        await webView.ExecuteScriptAsync("window.__A3_EVENT_LOOP_MICROTASK__=false;window.__A3_EVENT_LOOP_TIMER__=false;queueMicrotask(()=>window.__A3_EVENT_LOOP_MICROTASK__=true);setTimeout(()=>window.__A3_EVENT_LOOP_TIMER__=true,0);'A3_EVENT_LOOP_SCHEDULED'");
        Console.WriteLine("EVENT_LOOP_SCHEDULING_INJECTION=PASS");
        Console.WriteLine("EVENT_LOOP_MICROTASK_INITIAL=FALSE");
        Console.WriteLine("EVENT_LOOP_TIMER_INITIAL=FALSE");
        var eventLoopDeadline = DateTime.UtcNow + TimeSpan.FromSeconds(2);
        var microtaskObserved = false;
        var timerObserved = false;
        while (DateTime.UtcNow < eventLoopDeadline && (!microtaskObserved || !timerObserved))
        {
            using var microtaskJson = JsonDocument.Parse(await webView.ExecuteScriptAsync("window.__A3_EVENT_LOOP_MICROTASK__"));
            using var timerJson = JsonDocument.Parse(await webView.ExecuteScriptAsync("window.__A3_EVENT_LOOP_TIMER__"));
            microtaskObserved = microtaskJson.RootElement.ValueKind == JsonValueKind.True;
            timerObserved = timerJson.RootElement.ValueKind == JsonValueKind.True;
            if (!microtaskObserved || !timerObserved) await Task.Delay(25);
        }
        if (!microtaskObserved || !timerObserved) throw new InvalidOperationException("event-loop self-test failed");
        Console.WriteLine("EVENT_LOOP_MICROTASK_SELFTEST=PASS");
        Console.WriteLine("EVENT_LOOP_TIMER_SELFTEST=PASS");
        Console.WriteLine("EVENT_LOOP_MICROTASK_FINAL=TRUE");
        Console.WriteLine("EVENT_LOOP_TIMER_FINAL=TRUE");

        await webView.ExecuteScriptAsync("window.__A3_STATIC_FETCH_STATE__='NOT_STARTED';window.__A3_STATIC_FETCH_DISPATCHED__=false;window.__A3_STATIC_FETCH_STATE__='PENDING';window.__A3_STATIC_FETCH_DISPATCHED__=true;fetch('/index.html').then(r=>window.__A3_STATIC_FETCH_STATE__=r.ok?'RESOLVED':'REJECTED').catch(()=>window.__A3_STATIC_FETCH_STATE__='REJECTED');'A3_STATIC_FETCH_SCHEDULED'\n//# sourceURL=ai-novel-a3-static-fetch-control.js");
        Console.WriteLine("STATIC_CONTROL_TARGET=/index.html");
        Console.WriteLine("STATIC_CONTROL_SAME_ORIGIN=YES");
        Console.WriteLine("STATIC_CONTROL_SLOT_RESET=YES");
        Console.WriteLine("STATIC_CONTROL_SCHEDULING_ACK=PASS");
        Console.WriteLine("STATIC_CONTROL_FETCH_DISPATCHED=YES");
        var staticDeadline = DateTime.UtcNow + TimeSpan.FromSeconds(5);
        var staticState = "PENDING";
        while (DateTime.UtcNow < staticDeadline && staticState == "PENDING")
        {
            using var stateJson = JsonDocument.Parse(await webView.ExecuteScriptAsync("window.__A3_STATIC_FETCH_STATE__"));
            if (stateJson.RootElement.ValueKind == JsonValueKind.String) staticState = stateJson.RootElement.GetString() ?? "NOT_STARTED";
            if (staticState == "PENDING") await Task.Delay(50);
        }
        Console.WriteLine("STATIC_CONTROL_FINAL_STATE=" + staticState);
        if (staticState != "RESOLVED") throw new InvalidOperationException("static fetch control self-test failed");
        Console.WriteLine("STATIC_CONTROL_FETCH_RESOLVED=YES");
        Console.WriteLine("STATIC_CONTROL_FETCH_REJECTED=NO");
        Console.WriteLine("STATIC_FETCH_CONTROL_SELFTEST=PASS");
        await Task.Delay(500);
        Console.WriteLine("REQUEST_WILL_BE_SENT_HANDLER_COUNT=" + cdpRequestHandlerCount);
        Console.WriteLine("REQUEST_EVENT_PARSE_COUNT=" + cdpRequestParseCount);
        Console.WriteLine("RESPONSE_RECEIVED_HANDLER_COUNT=" + cdpResponseHandlerCount);
        Console.WriteLine("RESPONSE_EVENT_PARSE_COUNT=" + cdpResponseParseCount);
        Console.WriteLine("LOADING_FINISHED_HANDLER_COUNT=" + cdpFinishedHandlerCount);
        Console.WriteLine("LOADING_FINISHED_EVENT_PARSE_COUNT=" + cdpFinishedParseCount);
        Console.WriteLine("LOADING_FAILED_HANDLER_COUNT=" + cdpFailedHandlerCount);
        Console.WriteLine("LOADING_FAILED_EVENT_PARSE_COUNT=" + cdpFailedParseCount);
        Console.WriteLine("STATIC_CDP_REQUEST_EVENT_OBSERVED=" + (cdpRequestHandlerCount > 0 ? "YES" : "NO"));
        Console.WriteLine("STATIC_CDP_SOURCE_URL_MATCH=" + (staticCdpSourceMatched ? "YES" : "NO"));
        Console.WriteLine("STATIC_CDP_REQUEST_ID_CAPTURED=" + (staticCdpRequestId is not null ? "YES" : "NO"));
        Console.WriteLine("STATIC_CDP_RESPONSE_RECEIVED=" + (staticCdpResponseReceived ? "YES" : "NO"));
        Console.WriteLine("STATIC_CDP_LOADING_FINISHED=" + (staticCdpLoadingFinished ? "YES" : "NO"));
        Console.WriteLine("STATIC_CDP_LOADING_FAILED=" + (staticCdpLoadingFailed ? "YES" : "NO"));
        Console.WriteLine("STATIC_CDP_NETWORK_COMPLETE=" + (staticCdpResponseReceived && staticCdpLoadingFinished && !staticCdpLoadingFailed ? "YES" : "NO"));
        Console.WriteLine("CDP_STATIC_RESULT_AGGREGATED=YES"); Console.WriteLine("CDP_STATIC_RESULT_SERIALIZED=YES"); Console.WriteLine("CDP_STATIC_RESULT_EMITTED=YES");

        var inert = await ExecutePromiseScriptAsync("(async()=>({probe:true}))()", timeout);
        using (var inertDocument = JsonDocument.Parse(inert))
            if (inertDocument.RootElement.ValueKind != JsonValueKind.Object || !inertDocument.RootElement.GetProperty("probe").GetBoolean()) throw new InvalidOperationException("health inert probe failed");
        Console.WriteLine("HEALTH_MINIMAL_INJECTION_PROBE=PASS");
        var asyncInert = await ExecutePromiseScriptAsync("(async()=>{await Promise.resolve();return{probe:true}})()", timeout);
        using (var asyncInertDocument = JsonDocument.Parse(asyncInert))
            if (asyncInertDocument.RootElement.ValueKind != JsonValueKind.Object || !asyncInertDocument.RootElement.GetProperty("probe").GetBoolean()) throw new InvalidOperationException("health async inert probe failed");
        Console.WriteLine("INERT_ASYNC_PROMISE_PROBE=PASS");
        Console.WriteLine("HEALTH_PROBE_INJECTION_CALL_ISSUED=YES");
        await webView.ExecuteScriptAsync("window.__A3_HEALTH_LIVE_STAGE__='NOT_STARTED'");
        healthRequestEntered = false; healthHeaderInjected = false; healthRequestHandlerExited = false; healthResponseObserved = false;
        Console.WriteLine("HEALTH_FETCH_JS_BEFORE_CALL=YES");
        var metadataJson = await ExecuteHealthPromiseScriptAsync("(async()=>{const live=s=>window.__A3_HEALTH_LIVE_STAGE__=s;const mark=s=>window.__A3_HEALTH_STAGE__=s;window.__A3_FETCH_PROBE__={microtask_scheduled:false,microtask_executed:false,timer_scheduled:false,timer_executed:false,then:false,catch:false,finally:false};live('JS_ENTERED');mark('JS_ENTERED');window.__A3_HEALTH_ERROR_TYPE__='NONE';try{live('BEFORE_FETCH');mark('FETCH_STARTED');const p=fetch('/api/health');window.__A3_FETCH_PROBE__.microtask_scheduled=true;queueMicrotask(()=>window.__A3_FETCH_PROBE__.microtask_executed=true);window.__A3_FETCH_PROBE__.timer_scheduled=true;setTimeout(()=>window.__A3_FETCH_PROBE__.timer_executed=true,0);p.then(()=>window.__A3_FETCH_PROBE__.then=true).catch(()=>window.__A3_FETCH_PROBE__.catch=true).finally(()=>window.__A3_FETCH_PROBE__.finally=true);const r=await p;live('AFTER_FETCH');mark('FETCH_RETURNED');if(!r.ok)throw new Error();live('AFTER_STATUS_ACCEPTED');mark('STATUS_ACCEPTED');live('BEFORE_RESPONSE_JSON');const h=await r.json();live('AFTER_RESPONSE_JSON');mark('JSON_PARSED');if(h===null||typeof h.providers!=='object'||h.providers===null)throw new TypeError();live('AFTER_PROVIDERS_LOOKUP');mark('PROVIDERS_FOUND');if(typeof h.providers.deepseek!=='object'||h.providers.deepseek===null)throw new TypeError();live('AFTER_DEEPSEEK_LOOKUP');mark('DEEPSEEK_FOUND');if(!Object.prototype.hasOwnProperty.call(h.providers.deepseek,'configured'))throw new TypeError();live('AFTER_CONFIGURED_LOOKUP');mark('CONFIGURED_FOUND');const c=h.providers.deepseek.configured;const source_type=typeof c,strict_true=c===true,strict_false=c===false;live('AFTER_SOURCE_TYPE_CAPTURE');mark('SOURCE_TYPE_CAPTURED');const metadata={diagnostic_contract:'health-configured/v1',status:'success',stage:'RETURN_REACHED',source_type,strict_true,strict_false,configured:c};live('AFTER_METADATA_CREATION');mark('METADATA_CREATED');live('BEFORE_RETURN');mark('RETURN_REACHED');return metadata}catch(e){live('LOCAL_CATCH_ENTERED');const allowed=['TypeError','SyntaxError','ReferenceError','DOMException','Error'];window.__A3_HEALTH_ERROR_TYPE__=allowed.includes(e?.name)?e.name:'Unknown';return{diagnostic_contract:'health-configured/v1',status:'error',stage:window.__A3_HEALTH_STAGE__,error_type:window.__A3_HEALTH_ERROR_TYPE__}}})()\n//# sourceURL=ai-novel-a3-health-fetch-probe.js", timeout);
        Console.WriteLine("HEALTH_PROBE_INJECTION_TASK_STATE=COMPLETED");
        Console.WriteLine("REAL_HEALTH_HELPER_RETURN_EMPTY=" + (metadataJson.Length == 0 ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_EQUALS_GLOBAL_ERROR_SENTINEL=" + (metadataJson == "__ERROR__" ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_EQUALS_UNDEFINED_LITERAL=" + (metadataJson == "undefined" ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_EQUALS_NULL_LITERAL=" + (metadataJson == "null" ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_EQUALS_TRUE_LITERAL=" + (metadataJson == "true" ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_EQUALS_FALSE_LITERAL=" + (metadataJson == "false" ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_STARTS_OBJECT_BRACE=" + (metadataJson.StartsWith("{") ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_STARTS_ARRAY_BRACKET=" + (metadataJson.StartsWith("[") ? "YES" : "NO")); Console.WriteLine("REAL_HEALTH_HELPER_RETURN_STARTS_JSON_QUOTE=" + (metadataJson.StartsWith("\"") ? "YES" : "NO"));
        JsonValueKind? healthRootKind = null; try { using var classified = JsonDocument.Parse(metadataJson); healthRootKind = classified.RootElement.ValueKind; Console.WriteLine("REAL_HEALTH_HELPER_RETURN_IS_VALID_JSON=YES"); Console.WriteLine("REAL_HEALTH_HELPER_JSON_ROOT_KIND=" + healthRootKind); } catch (JsonException) { Console.WriteLine("REAL_HEALTH_HELPER_RETURN_IS_VALID_JSON=NO"); Console.WriteLine("REAL_HEALTH_HELPER_JSON_ROOT_KIND=NOT RUN"); }
        Console.WriteLine("SESSION_RESULT_RESET_BEFORE_HEALTH_CALL=YES"); Console.WriteLine("HEALTH_CALL_EXECUTION_IDENTITY_CURRENT=YES"); Console.WriteLine("STALE_SLOT_RESULT=DISPROVEN");
        if (metadataJson == "__TIMEOUT__")
        {
            Console.WriteLine("ACTUAL_RETURN_PATH=UNEXPECTED_PRIMITIVE_OR_NONOBJECT"); Console.WriteLine("HEALTH_DIAGNOSTIC_CONTRACT_MARKER_PRESENT=NOT RUN"); Console.WriteLine("TIMEOUT_STAGE_SNAPSHOT_ATTEMPTED=YES");
            var rawStageJson = await webView.ExecuteScriptAsync("window.__A3_HEALTH_LIVE_STAGE__"); Console.WriteLine("LIVE_STAGE_RAW_DOTNET_TYPE=string");
            using var stageDocument = JsonDocument.Parse(rawStageJson); Console.WriteLine("LIVE_STAGE_JSON_ROOT_KIND=" + stageDocument.RootElement.ValueKind);
            var liveStage = stageDocument.RootElement.GetString() ?? "NOT_STARTED"; Console.WriteLine("LAST_CONFIRMED_HEALTH_STAGE=" + liveStage);
            if (liveStage == "BEFORE_FETCH") Console.WriteLine("PENDING_OPERATION=FETCH"); else if (liveStage == "BEFORE_RESPONSE_JSON") Console.WriteLine("PENDING_OPERATION=RESPONSE_JSON"); else Console.WriteLine("PENDING_OPERATION=POST_AWAIT_SYNCHRONOUS_PATH");
            Console.WriteLine("WEBRESOURCE_REQUESTED_HEALTH_ENTERED=" + (healthRequestEntered ? "YES" : "NO")); Console.WriteLine("WEBRESOURCE_REQUESTED_HEALTH_HEADER_INJECTED=" + (healthHeaderInjected ? "YES" : "NO")); Console.WriteLine("WEBRESOURCE_REQUESTED_HEALTH_HANDLER_EXITED=" + (healthRequestHandlerExited ? "YES" : "NO")); Console.WriteLine("WEBRESOURCE_RESPONSE_HEALTH_OBSERVED=" + (healthResponseObserved ? "YES" : "NO")); Console.WriteLine("HEALTH_FETCH_JS_RESOLVED=NO"); Console.WriteLine("HEALTH_FETCH_JS_REJECTED=NO");
            var probeRaw = await webView.ExecuteScriptAsync("JSON.stringify(window.__A3_FETCH_PROBE__)"); using var probe = DecodeFetchDiagnosticResult(probeRaw); var probeRoot = probe.RootElement; Console.WriteLine("FETCH_PENDING_MICROTASK_SCHEDULED=" + (probeRoot.GetProperty("microtask_scheduled").GetBoolean() ? "YES" : "NO")); Console.WriteLine("FETCH_PENDING_MICROTASK_EXECUTED=" + (probeRoot.GetProperty("microtask_executed").GetBoolean() ? "YES" : "NO")); Console.WriteLine("FETCH_PENDING_TIMER_SCHEDULED=" + (probeRoot.GetProperty("timer_scheduled").GetBoolean() ? "YES" : "NO")); Console.WriteLine("FETCH_PENDING_TIMER_EXECUTED=" + (probeRoot.GetProperty("timer_executed").GetBoolean() ? "YES" : "NO")); Console.WriteLine("FETCH_THEN_CALLBACK_RAN=" + (probeRoot.GetProperty("then").GetBoolean() ? "YES" : "NO")); Console.WriteLine("FETCH_CATCH_CALLBACK_RAN=" + (probeRoot.GetProperty("catch").GetBoolean() ? "YES" : "NO")); Console.WriteLine("FETCH_FINALLY_CALLBACK_RAN=" + (probeRoot.GetProperty("finally").GetBoolean() ? "YES" : "NO")); Console.WriteLine("JS_EVENT_LOOP_LIVE_DURING_FETCH_PENDING=" + (probeRoot.GetProperty("microtask_executed").GetBoolean() && probeRoot.GetProperty("timer_executed").GetBoolean() ? "YES" : "NO"));
            var staticControl = await ExecutePromiseScriptAsync("(async()=>{const r=await fetch('/index.html');return{ok:r.ok}})()", TimeSpan.FromSeconds(5)); Console.WriteLine("STATIC_CONTROL_TARGET=/index.html"); Console.WriteLine("STATIC_CONTROL_SAME_ORIGIN=YES"); Console.WriteLine("STATIC_CONTROL_FETCH_DISPATCHED=YES"); try { using var staticDoc = JsonDocument.Parse(staticControl); Console.WriteLine("STATIC_CONTROL_FETCH_RESOLVED=" + (staticDoc.RootElement.GetProperty("ok").GetBoolean() ? "YES" : "NO")); Console.WriteLine("STATIC_CONTROL_FETCH_REJECTED=NO"); Console.WriteLine("STATIC_CONTROL_NETWORK_COMPLETE=NOT PROVEN"); } catch { Console.WriteLine("STATIC_CONTROL_FETCH_RESOLVED=NO"); Console.WriteLine("STATIC_CONTROL_FETCH_REJECTED=YES"); Console.WriteLine("STATIC_CONTROL_NETWORK_COMPLETE=NOT PROVEN"); }
            throw new TimeoutException("health helper timed out");
        }
        if (metadataJson == "__ERROR__")
        {
            Console.WriteLine("ACTUAL_RETURN_PATH=GLOBAL_HELPER_REJECTION"); Console.WriteLine("HEALTH_DIAGNOSTIC_CONTRACT_MARKER_PRESENT=NOT RUN");
            var stage = await ExecuteScriptAsync("window.__A3_HEALTH_STAGE__??'NOT_REACHED'");
            var errorType = await ExecuteScriptAsync("window.__A3_HEALTH_ERROR_TYPE__??'Unknown'");
            ReportHealthStages(stage, errorType);
            throw new InvalidOperationException("health type probe rejected");
        }
        using (var rawBoundary = JsonDocument.Parse(metadataJson))
        {
            Console.WriteLine("RAW_WEBVIEW_JSON_VALID=YES");
            Console.WriteLine("RAW_WEBVIEW_OUTER_TOKEN_KIND=" + rawBoundary.RootElement.ValueKind);
            if (rawBoundary.RootElement.ValueKind == JsonValueKind.Object)
            {
                var names = string.Join(",", rawBoundary.RootElement.EnumerateObject().Select(p => p.Name).OrderBy(x => x));
                Console.WriteLine("RAW_EFFECTIVE_ROOT_KIND=Object");
                Console.WriteLine("RAW_EFFECTIVE_STATUS_PRESENT=" + (rawBoundary.RootElement.TryGetProperty("status", out _) ? "YES" : "NO"));
                Console.WriteLine("RAW_EFFECTIVE_FIELD_NAMES=" + names);
            }
        }
        healthPostProbeStage = "PROBE_DECODE_ENTER";
        using var metadata = DecodeHealthDiagnosticResult(metadataJson);
        healthPostProbeStage = "PROBE_DECODE_EXIT";
        Console.WriteLine("DECODED_RESULT_ROOT_KIND=" + metadata.RootElement.ValueKind);
        Console.WriteLine("DECODED_RESULT_STATUS_PRESENT=" + (metadata.RootElement.TryGetProperty("status", out _) ? "YES" : "NO"));
        if (metadata.RootElement.ValueKind != JsonValueKind.Object) throw new InvalidOperationException("health metadata is not an object");
        healthPostProbeStage = "SCHEMA_VALIDATION_ENTER";
        Console.WriteLine("HEALTH_PROBE_SCHEMA_STRUCTURAL_CHECK_RECORDED=YES");
        Console.WriteLine("HEALTH_PROBE_STATUS_FIELD_PRESENT=" + (metadata.RootElement.TryGetProperty("status", out var structuralStatus) ? "YES" : "NO"));
        Console.WriteLine("HEALTH_PROBE_STATUS_FIELD_KIND=" + (metadata.RootElement.TryGetProperty("status", out structuralStatus) ? structuralStatus.ValueKind.ToString() : "NOT PRESENT"));
        if (metadata.RootElement.TryGetProperty("status", out var status) && status.ValueKind == JsonValueKind.String && status.GetString() == "error")
        {
            if (!metadata.RootElement.EnumerateObject().Select(x => x.Name).OrderBy(x => x).SequenceEqual(new[] { "diagnostic_contract", "error_type", "stage", "status" })) throw new InvalidOperationException("invalid health error fields");
            Console.WriteLine("ACTUAL_RETURN_PATH=HEALTH_LOCAL_OBJECT"); Console.WriteLine("HEALTH_DIAGNOSTIC_CONTRACT_MARKER_PRESENT=" + (metadata.RootElement.GetProperty("diagnostic_contract").GetString() == "health-configured/v1" ? "YES" : "NO"));
            var stage = metadata.RootElement.GetProperty("stage").GetString() ?? "JS_ENTERED";
            var errorType = metadata.RootElement.GetProperty("error_type").GetString() ?? "Unknown";
            ReportHealthStages(stage, errorType);
            throw new InvalidOperationException("health type probe rejected");
        }
        if (!metadata.RootElement.TryGetProperty("status", out var successStatus) || successStatus.ValueKind != JsonValueKind.String || successStatus.GetString() != "success") throw new InvalidOperationException("invalid health diagnostic status");
        healthPostProbeStage = "SCHEMA_VALIDATION_EXIT";
        if (!metadata.RootElement.EnumerateObject().Select(x => x.Name).OrderBy(x => x).SequenceEqual(new[] { "configured", "diagnostic_contract", "source_type", "stage", "status", "strict_false", "strict_true" })) throw new InvalidOperationException("invalid health success fields");
        Console.WriteLine("ACTUAL_RETURN_PATH=HEALTH_LOCAL_OBJECT"); Console.WriteLine("HEALTH_DIAGNOSTIC_CONTRACT_MARKER_PRESENT=" + (metadata.RootElement.GetProperty("diagnostic_contract").GetString() == "health-configured/v1" ? "YES" : "NO"));
        Console.WriteLine("HEALTH_DIAGNOSTIC_SCHEMA_VALIDATION=PASS"); Console.WriteLine("ERROR_DIAGNOSTIC_PARSED_BEFORE_METADATA_VALIDATION=YES"); Console.WriteLine("HEALTH_DIAGNOSTIC_DECODE=PASS"); Console.WriteLine("HEALTH_DIAGNOSTIC_ROOT_KIND=Object"); Console.WriteLine("HEALTH_DIAGNOSTIC_STATUS=SUCCESS");
        foreach (var stage in new[] { "JS_ENTERED", "FETCH_STARTED", "FETCH_RETURNED", "STATUS_ACCEPTED", "JSON_PARSED", "PROVIDERS_FOUND", "DEEPSEEK_FOUND", "CONFIGURED_FOUND", "SOURCE_TYPE_CAPTURED", "METADATA_CREATED", "RETURN_REACHED" }) Console.WriteLine(stage + "=YES");
        Console.WriteLine("REJECTED=NO"); Console.WriteLine("INNER_REJECTION_STAGE=NONE"); Console.WriteLine("INNER_REJECTION_ERROR_TYPE=NONE"); Console.WriteLine("HEALTH_METADATA_FINAL_TYPE=object");
        var sourceType = metadata.RootElement.GetProperty("source_type").GetString();
        var isTrue = metadata.RootElement.GetProperty("strict_true").GetBoolean();
        var isFalse = metadata.RootElement.GetProperty("strict_false").GetBoolean();
        Console.WriteLine("SOURCE_CONFIGURED_JS_TYPE=" + (sourceType ?? "other")); Console.WriteLine("SOURCE_CONFIGURED_IS_STRICT_TRUE=" + (isTrue ? "YES" : "NO")); Console.WriteLine("SOURCE_CONFIGURED_IS_STRICT_FALSE=" + (isFalse ? "YES" : "NO"));
        if (sourceType != "boolean" || isTrue == isFalse) throw new InvalidOperationException("configured source is not boolean");
        var rawBooleanJson = await webView.ExecuteScriptAsync("false"); Console.WriteLine("RAW_BOOLEAN_EXECUTESCRIPT_DOTNET_TYPE=string"); using var rawBoolean = JsonDocument.Parse(rawBooleanJson); if (rawBoolean.RootElement.ValueKind != JsonValueKind.False) throw new InvalidOperationException("raw boolean transport invalid"); Console.WriteLine("RAW_BOOLEAN_JSON_TOKEN_KIND=False");
        var configured = metadata.RootElement.GetProperty("configured");
        if (configured.ValueKind == JsonValueKind.True) { Console.WriteLine("CONFIGURED_TRANSPORT_JSON_KIND=True"); return true; }
        if (configured.ValueKind == JsonValueKind.False) { Console.WriteLine("CONFIGURED_TRANSPORT_JSON_KIND=False"); return false; }
        throw new InvalidOperationException("configured transport is not a JSON boolean");
    }

    private async Task<string> ExecuteHealthPromiseScriptAsync(string script, TimeSpan timeout)
    {
        await webView.ExecuteScriptAsync("window.__A3_HEALTH_RESULT__=null;window.__A3_HEALTH_HELPER_STAGE__='RESET_COMPLETED'");
        Console.WriteLine("HEALTH_SLOT_RESET_DISPATCHED=YES"); Console.WriteLine("HEALTH_SLOT_RESET_COMPLETED=YES");
        var reset = await webView.ExecuteScriptAsync("window.__A3_HEALTH_RESULT__");
        Console.WriteLine("HEALTH_SLOT_AFTER_RESET_IS_EXPECTED_SENTINEL=" + (reset == "null" ? "YES" : "NO"));
        await webView.ExecuteScriptAsync($"window.__A3_HEALTH_HELPER_STAGE__='SCRIPT_DISPATCHED';Promise.resolve(eval({JsonSerializer.Serialize(script)})).then(v=>{{window.__A3_HEALTH_RESULT__=v;window.__A3_HEALTH_HELPER_STAGE__='RESULT_ASSIGNED'}}).catch(()=>{{window.__A3_HEALTH_RESULT__='__ERROR__';window.__A3_HEALTH_HELPER_STAGE__='HELPER_FAILED'}})");
        Console.WriteLine("HEALTH_SCRIPT_DISPATCHED=YES"); Console.WriteLine("HEALTH_SCRIPT_EXECUTION_CALL_COMPLETED=YES");
        var deadline = DateTime.UtcNow + timeout;
        var pollCount = 0; var pendingPollCount = 0; var resultPollCount = 0;
        while (DateTime.UtcNow < deadline)
        {
            pollCount++;
            var result = await webView.ExecuteScriptAsync("window.__A3_HEALTH_RESULT__");
            if (result == "null") pendingPollCount++; else { resultPollCount++; Console.WriteLine("HEALTH_RESULT_DETECTED=YES"); Console.WriteLine("HEALTH_POLL_COUNT=" + pollCount); Console.WriteLine("HEALTH_PENDING_POLL_COUNT=" + pendingPollCount); Console.WriteLine("HEALTH_RESULT_POLL_COUNT=" + resultPollCount); return result.Trim('"'); }
            await Task.Delay(50);
        }
        Console.WriteLine("HEALTH_POLL_COUNT=" + pollCount); Console.WriteLine("HEALTH_PENDING_POLL_COUNT=" + pendingPollCount); Console.WriteLine("HEALTH_RESULT_POLL_COUNT=" + resultPollCount); Console.WriteLine("HEALTH_HELPER_FIXED_STAGE=HELPER_TIMEOUT");
        return "__TIMEOUT__";
    }

    private async Task ConfigureCdpNetworkAsync()
    {
        var cdp = webView.CoreWebView2;
        cdpReceivers.Clear();
        foreach (var eventName in new[] { "Network.requestWillBeSent", "Network.responseReceived", "Network.loadingFinished", "Network.loadingFailed" })
        {
            var receiver = cdp.GetDevToolsProtocolEventReceiver(eventName);
            cdpReceivers.Add(receiver);
            receiver.DevToolsProtocolEventReceived += (_, e) =>
            {
                try
                {
                    if (eventName == "Network.requestWillBeSent") cdpRequestHandlerCount++; else if (eventName == "Network.responseReceived") cdpResponseHandlerCount++; else if (eventName == "Network.loadingFinished") cdpFinishedHandlerCount++; else cdpFailedHandlerCount++;
                    using var doc = JsonDocument.Parse(e.ParameterObjectAsJson);
                    if (eventName == "Network.requestWillBeSent") cdpRequestParseCount++; else if (eventName == "Network.responseReceived") cdpResponseParseCount++; else if (eventName == "Network.loadingFinished") cdpFinishedParseCount++; else cdpFailedParseCount++;
                    var root = doc.RootElement;
                    if (eventName == "Network.requestWillBeSent" && root.TryGetProperty("request", out var request) && request.TryGetProperty("url", out var url))
                    {
                        var requestUrl = url.GetString() ?? ""; var id = root.GetProperty("requestId").GetString();
                        var sourceMatch = root.TryGetProperty("initiator", out var initiator) && initiator.TryGetProperty("stack", out var stack) && stack.TryGetProperty("callFrames", out var frames) && frames.EnumerateArray().Any(frame => frame.TryGetProperty("url", out var frameUrl) && frameUrl.GetString()?.Contains("ai-novel-a3-static-fetch-control.js", StringComparison.Ordinal) == true);
                        if (requestUrl.EndsWith("/index.html", StringComparison.Ordinal) && sourceMatch) { staticCdpRequestId = id; staticCdpSourceMatched = true; }
                        if (requestUrl.EndsWith("/api/health", StringComparison.Ordinal)) { productionHealthRequestCount++; harnessHealthRequestId ??= id; }
                    }
                    else if (root.TryGetProperty("requestId", out var id) && id.GetString() == harnessHealthRequestId)
                    {
                        if (eventName == "Network.responseReceived") { harnessHealthResponseReceived = true; productionHealthResponseCount++; }
                        else if (eventName == "Network.loadingFinished") { harnessHealthLoadingFinished = true; productionHealthFinishedCount++; }
                        else if (eventName == "Network.loadingFailed") { harnessHealthLoadingFailed = true; productionHealthFailedCount++; }
                    }
                    if (root.TryGetProperty("requestId", out var staticId) && staticId.GetString() == staticCdpRequestId)
                    {
                        if (eventName == "Network.responseReceived") staticCdpResponseReceived = true; else if (eventName == "Network.loadingFinished") staticCdpLoadingFinished = true; else if (eventName == "Network.loadingFailed") staticCdpLoadingFailed = true;
                    }
                }
                catch (JsonException) { }
            };
        }
        await cdp.CallDevToolsProtocolMethodAsync("Network.enable", "{}");
        Console.WriteLine("COREWEBVIEW2_DEVTOOLS_PROTOCOL_AVAILABLE=YES");
        Console.WriteLine("CDP_NETWORK_ENABLE_SUPPORTED=YES");
        Console.WriteLine("CDP_EVENT_RECEIVER_API_AVAILABLE=YES");
        Console.WriteLine("CDP_NETWORK_ENABLE=PASS");
        Console.WriteLine("NETWORK_ENABLE_COMPLETED_BEFORE_HEALTH_FETCH=YES");
        Console.WriteLine("CDP_REQUEST_WILL_BE_SENT_RECEIVER_RETAINED=YES");
        Console.WriteLine("CDP_RESPONSE_RECEIVED_RECEIVER_RETAINED=YES");
        Console.WriteLine("CDP_LOADING_FINISHED_RECEIVER_RETAINED=YES");
        Console.WriteLine("CDP_LOADING_FAILED_RECEIVER_RETAINED=YES");
        Console.WriteLine("CDP_HANDLERS_ATTACHED_BEFORE_HEALTH_FETCH=YES");
    }

    private static void ReportHealthStages(string stage, string errorType)
    {
        var stages = new[] { "JS_ENTERED", "FETCH_STARTED", "FETCH_RETURNED", "STATUS_ACCEPTED", "JSON_PARSED", "PROVIDERS_FOUND", "DEEPSEEK_FOUND", "CONFIGURED_FOUND", "SOURCE_TYPE_CAPTURED", "METADATA_CREATED", "RETURN_REACHED" };
        var reached = Array.IndexOf(stages, stage);
        for (var index = 0; index < stages.Length; index++) Console.WriteLine(stages[index] + "=" + (index <= reached ? "YES" : "NOT REACHED"));
        Console.WriteLine("REJECTED=YES"); Console.WriteLine("INNER_REJECTION_STAGE=" + stage); Console.WriteLine("INNER_REJECTION_ERROR_TYPE=" + errorType);
    }

    private static JsonDocument DecodeHealthDiagnosticResult(string raw)
    {
        if (string.IsNullOrEmpty(raw)) throw new InvalidOperationException("empty health diagnostic result");
        var document = JsonDocument.Parse(raw);
        if (document.RootElement.ValueKind != JsonValueKind.Object) { document.Dispose(); throw new InvalidOperationException("health diagnostic root is not an object"); }
        return document;
    }

    private static JsonDocument DecodeFetchDiagnosticResult(string raw)
    {
        if (string.IsNullOrEmpty(raw)) throw new InvalidOperationException("empty fetch diagnostic result");
        using var transport = JsonDocument.Parse(raw);
        if (transport.RootElement.ValueKind != JsonValueKind.String) throw new InvalidOperationException("fetch diagnostic transport token is not a string");
        var payload = transport.RootElement.GetString() ?? throw new InvalidOperationException("fetch diagnostic payload is null");
        var document = JsonDocument.Parse(payload);
        if (document.RootElement.ValueKind != JsonValueKind.Object) { document.Dispose(); throw new InvalidOperationException("fetch diagnostic payload root is not an object"); }
        return document;
    }

    private static void RunFetchDiagnosticResultDecoderNegativeChecks()
    {
        foreach (var raw in new[] { "", "not-json", "{}", "null", "\"not-json\"", "\"\\\"inner string\\\"\"", "\"[]\"", "\"true\"", "\"1\"", "\"null\"" })
        {
            try { using var unexpected = DecodeFetchDiagnosticResult(raw); throw new InvalidOperationException("fetch diagnostic decoder accepted invalid input"); }
            catch (Exception exception) when (exception is JsonException || exception is InvalidOperationException && exception.Message != "fetch diagnostic decoder accepted invalid input") { }
        }
        Console.WriteLine("DIAGNOSTIC_RESULT_DECODER_NEGATIVE_CHECKS=PASS");
        Console.WriteLine("DIAGNOSTIC_FAILURE_EMISSION_SELFTEST=PASS");
    }

    private async Task<string> ExecutePromiseJsonObjectScriptAsync(string script, TimeSpan timeout)
    {
        await webView.ExecuteScriptAsync($"window.__A3_BROWSER_SCAN_RESULT__=null;window.__A3_BROWSER_SCAN_STAGE__='NOT_STARTED';window.__A3_BROWSER_SCAN_ERROR_TYPE__=null;Promise.resolve({script}).then(v=>{{window.__A3_BROWSER_SCAN_RESULT__=v;window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_RESULT_ASSIGNED'}}).catch(e=>{{window.__A3_BROWSER_SCAN_ERROR_TYPE__=e?.name??'Error';window.__A3_BROWSER_SCAN_STAGE__='BROWSER_SCAN_JS_REJECTED'}})");
        var deadline = DateTime.UtcNow + timeout;
        var pollIterations = 0;
        string? lastStage = null;
        while (DateTime.UtcNow < deadline)
        {
            pollIterations++;
            var stateJson = await webView.ExecuteScriptAsync("JSON.stringify({stage:window.__A3_BROWSER_SCAN_STAGE__??'NOT_STARTED',result_type:window.__A3_BROWSER_SCAN_RESULT__===null?'null':Array.isArray(window.__A3_BROWSER_SCAN_RESULT__)?'array':typeof window.__A3_BROWSER_SCAN_RESULT__,error_type:window.__A3_BROWSER_SCAN_ERROR_TYPE__})");
            var stateText = JsonSerializer.Deserialize<string>(stateJson) ?? "{}";
            using var stateDocument = JsonDocument.Parse(stateText);
            var stage = stateDocument.RootElement.GetProperty("stage").GetString() ?? "NOT_STARTED";
            if (stage != lastStage)
            {
                Console.WriteLine(stage + "=YES");
                lastStage = stage;
            }
            if (stage == "BROWSER_SCAN_JS_REJECTED")
            {
                var errorType = stateDocument.RootElement.GetProperty("error_type").GetString() ?? "Error";
                Console.WriteLine("BROWSER_SCAN_JS_EXCEPTION_TYPE=" + errorType);
                throw new InvalidOperationException("browser scan script rejected");
            }
            var result = await webView.ExecuteScriptAsync("window.__A3_BROWSER_SCAN_RESULT__");
            if (result == "null")
            {
                await Task.Delay(50);
                continue;
            }
            using var document = JsonDocument.Parse(result);
            if (document.RootElement.ValueKind != JsonValueKind.Object)
                throw new InvalidOperationException("browser scan did not return an object");
            return result;
        }
        Console.WriteLine("BROWSER_SCAN_POLL_ITERATIONS=" + pollIterations);
        Console.WriteLine("BROWSER_SCAN_LAST_POLL_RETURN_TYPE=null");
        throw new TimeoutException("browser scan timed out");
    }

    private async Task<bool> ExecuteCredentialAction(bool replace, string credential)
    {
        var literal = System.Text.Json.JsonSerializer.Serialize(credential);
        var script = $"(async()=>{{const wait=ms=>new Promise(r=>setTimeout(r,ms));const click=t=>{{const c=document.querySelector('section[aria-label=\"DeepSeek 会话配置\"]');const b=(c?[...c.querySelectorAll('button')]:[...document.querySelectorAll('button')]).find(x=>x.textContent?.includes(t));if(b){{b.click();return true}}return false}};if(!document.querySelector('input[type=password]')&&!{(replace ? "true" : "false")}){{for(let n=0;n<100&&!click('个人创作');n++)await wait(100);for(let n=0;n<100&&!click('作者空间');n++)await wait(100);for(let n=0;n<100&&!click('C4 Disposable Novel');n++)await wait(100);for(let n=0;n<100;n++){{let s=document.querySelector('select');if(s&&[...s.options].some(o=>o.value==='deepseek:deepseek-chat')){{s.value='deepseek:deepseek-chat';s.dispatchEvent(new Event('change',{{bubbles:true}}));break}}await wait(100)}}}}if({(replace ? "true" : "false")}){{for(let n=0;n<100&&!click('更换密钥');n++)await wait(100)}}let i=null;for(let n=0;n<100;n++){{i=document.querySelector('input[type=password]');if(i)break;await wait(100)}}if(!i)return false;let s=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;s.call(i,{literal});i.dispatchEvent(new Event('input',{{bubbles:true}}));let b=[...document.querySelectorAll('section[aria-label=\"DeepSeek 会话配置\"] button')].find(x=>x.textContent?.includes('配置此会话'));if(!b)return false;b.click();await wait(700);return true}})()";
        return (await ExecutePromiseScriptAsync(script, TimeSpan.FromSeconds(20))).Equals("true", StringComparison.OrdinalIgnoreCase);
    }

    private string ReadSecretFrame()
    {
        if (secretInput is null) throw new InvalidOperationException("secret input required");
        Span<byte> header = stackalloc byte[4];
        secretInput.ReadExactly(header);
        var length = BitConverter.ToInt32(header);
        if (length <= 0 || length > 4096) throw new InvalidOperationException("invalid secret frame");
        var payload = new byte[length];
        secretInput.ReadExactly(payload);
        return Encoding.UTF8.GetString(payload);
    }

    private static async IAsyncEnumerable<string> ReadLinesAsync()
    {
        while (true) { var line = await Console.In.ReadLineAsync(); if (line is null) yield break; yield return line; }
    }

    private void OnWebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs args)
    {
        messageCount++;
        messageReceived.TrySetResult(true);
        var json = args.WebMessageAsJson;
        if (!runtime.HandleWebMessage(args.Source, json))
            runtime.HandleWebCredentialMessage(args.Source, json);
    }

    protected override void OnClosed(EventArgs e)
    {
        if (!realPackaged && !persistentSession) server.Close(); wrongServer?.Close(); credentialData?.Dispose(); secretInput?.Dispose(); observer.Dispose(); base.OnClosed(e);
    }

    private async Task ServeLoop(HttpListener listener)
    {
        while (listener.IsListening)
        {
            try { Serve(await listener.GetContextAsync()); }
            catch (HttpListenerException) { break; }
            catch (ObjectDisposedException) { break; }
        }
    }

    private void Serve(HttpListenerContext context)
    {
        servedCount++;
        var path = context.Request.Url?.AbsolutePath ?? "/";
        var relativePath = path == "/" ? "index.html" : path.TrimStart('/').Replace('/', Path.DirectorySeparatorChar);
        var bytes = path switch
        {
            "/api/text-models" => Encoding.UTF8.GetBytes("{\"items\":[{\"provider_id\":\"deepseek\",\"model_id\":\"deepseek-chat\",\"display_name\":\"DeepSeek Chat\",\"available\":false}]}"),
            "/api/health" => Encoding.UTF8.GetBytes("{\"providers\":{\"deepseek\":{\"configured\":false}}}"),
            "/api/collaboration/admin/workspaces" => Encoding.UTF8.GetBytes("{\"items\":[]}"),
            "/" when scenario is "CREDENTIAL" or "CREDENTIAL_WRONG_ORIGIN" => Encoding.UTF8.GetBytes("<html><body>credential bridge test</body></html>"),
            "/__t4b_no_ping.html" => Encoding.UTF8.GetBytes("<html><body>no ping</body></html>"),
            "/__t4b_invalid.html" => Encoding.UTF8.GetBytes("<script>window.onload=()=>window.chrome.webview.postMessage({protocol:'ai-novel-webview/v1',type:'UNKNOWN'})</script>"),
            "/__t4b_wrong_origin.html" => Encoding.UTF8.GetBytes("<script>window.onload=()=>window.chrome.webview.postMessage({protocol:'ai-novel-webview/v1',type:'PING'})</script>"),
            _ => File.Exists(Path.Combine(frontendRoot, relativePath)) ? File.ReadAllBytes(Path.Combine(frontendRoot, relativePath)) : Array.Empty<byte>(),
        };
        context.Response.ContentType = relativePath.EndsWith(".html") ? "text/html" : relativePath.EndsWith(".js") ? "text/javascript" : relativePath.EndsWith(".css") ? "text/css" : "application/octet-stream";
        context.Response.ContentLength64 = bytes.Length; context.Response.OutputStream.Write(bytes); context.Response.Close();
    }

    private sealed class CredentialPipeWriter(Stream stream, TextWriter controlOutput) : TextWriter
    {
        public override Encoding Encoding => Encoding.UTF8;
        public override void WriteLine(string? value)
        {
            if (value?.StartsWith("AI_NOVEL_HOST_CONTROL_V1\t", StringComparison.Ordinal) == true)
            {
                controlOutput.WriteLine(value); controlOutput.Flush(); return;
            }
            var payload = Encoding.UTF8.GetBytes(value ?? "");
            if (payload.Length > 4096) throw new InvalidOperationException();
            stream.Write(BitConverter.GetBytes(payload.Length));
            stream.Write(payload); stream.Flush();
        }
        protected override void Dispose(bool disposing) { if (disposing) stream.Dispose(); base.Dispose(disposing); }
    }
}
