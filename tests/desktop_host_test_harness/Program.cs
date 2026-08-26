using System.Reflection;
using System.Text;

var assembly = Assembly.Load("AI-Novel-Studio.DesktopHost");
var program = assembly.GetType("AINovelStudio.DesktopHost.Program", throwOnError: true)!;
var exactOrigin = program.GetMethod("ExactLoopbackOrigin", BindingFlags.Static | BindingFlags.NonPublic)!;
var accepted = (bool)exactOrigin.Invoke(null, new object[] { "http://127.0.0.1:43123/" })!;
var rejected = (bool)exactOrigin.Invoke(null, new object[] { "http://localhost:43123/" })!;
if (!accepted || rejected) return 1;
var handleIndex = Array.IndexOf(args, "--observer-handle");
var scenarioIndex = Array.IndexOf(args, "--scenario");
var dataHandleIndex = Array.IndexOf(args, "--credential-data-handle");
var scenario = scenarioIndex >= 0 && scenarioIndex + 1 < args.Length ? args[scenarioIndex + 1] : "controlled-valid-ping";
if (scenario is not ("controlled-valid-ping" or "no-webview" or "invalid-message" or "credential-set" or "credential-clear")) return 1;
if (handleIndex >= 0 && handleIndex + 1 < args.Length && nint.TryParse(args[handleIndex + 1], out var handle))
{
    using var stream = new FileStream(new Microsoft.Win32.SafeHandles.SafeFileHandle(handle, ownsHandle: false), FileAccess.Write);
    void Observe(string stage) { var bytes = Encoding.ASCII.GetBytes("AI_NOVEL_TEST_ATTRIBUTION_V1\t" + stage + "\n"); stream.Write(bytes, 0, bytes.Length); stream.Flush(); }
    if (scenarioIndex < 0)
    {
        var synthetic = Encoding.ASCII.GetBytes("AI_NOVEL_TEST_OBSERVER_V1\tHOST_OBSERVER_TEST\n");
        stream.Write(synthetic, 0, synthetic.Length); stream.Flush();
    }
    var output = new StringWriter();
    var runtime = new AINovelStudio.DesktopHost.HostControlRuntime("http://127.0.0.1:43123", "test-runtime", output, Observe, startupPingEnabled: false);
    runtime.EmitStartupPing();
    if (output.GetStringBuilder().Length != 0) return 1;
    if (scenario == "credential-set")
    {
        var value = Console.In.ReadLine();
        if (value is null || !runtime.EmitProviderCredential("deepseek", value)) return 1;
        if (!WriteCredentialFrame(output.ToString())) return 1;
    }
    else if (scenario == "credential-clear")
    {
        if (!runtime.ClearProviderCredential("deepseek")) return 1;
        if (!WriteCredentialFrame(output.ToString())) return 1;
    }
    if (scenario == "controlled-valid-ping" &&
        !runtime.HandleWebMessage("http://127.0.0.1:43123/", "{\"protocol\":\"ai-novel-webview/v1\",\"type\":\"PING\"}")) return 1;
    if (scenario == "invalid-message" &&
        runtime.HandleWebMessage("http://127.0.0.1:43123/", "{\"protocol\":\"ai-novel-webview/v1\",\"type\":\"UNKNOWN\"}")) return 1;
    if (scenario is "controlled-valid-ping" or "invalid-message" or "no-webview") Console.Write(output.ToString());

    bool WriteCredentialFrame(string frame)
    {
        if (dataHandleIndex < 0 || dataHandleIndex + 1 >= args.Length || !nint.TryParse(args[dataHandleIndex + 1], out var dataHandle)) return false;
        var payload = Encoding.UTF8.GetBytes(frame);
        if (payload.Length > 4096) return false;
        using var data = new FileStream(new Microsoft.Win32.SafeHandles.SafeFileHandle(dataHandle, ownsHandle: false), FileAccess.Write);
        data.Write(BitConverter.GetBytes(payload.Length)); data.Write(payload); data.Flush(); return true;
    }
}
Console.WriteLine("TEST_HOST_START=PASS");
Console.WriteLine("TEST_HOST_EXIT=PASS");
return 0;
