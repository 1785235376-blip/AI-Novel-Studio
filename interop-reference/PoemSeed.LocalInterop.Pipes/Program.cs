using System.Buffers.Binary;
using System.Diagnostics;
using System.Reflection;
using PoemSeed.LocalInterop.Pipes;

if (!OperatingSystem.IsWindows())
    throw new PlatformNotSupportedException("This acceptance reference runs only on Windows.");

using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(30));
if (args is ["--synthetic-client", var pipeName])
{
    await using var client = CurrentUserPipe.CreateClient(pipeName);
    await client.ConnectAsync(deadline.Token);
    await CurrentUserPipe.WriteJsonAsync(client,
        "{\"protocol_name\":\"PoemSeed Local Interop\",\"protocol_version\":\"1.0\",\"boundary\":\"MOCK_ONLY\"}",
        deadline.Token);
    var answer = await CurrentUserPipe.ReadJsonAsync(client, deadline.Token);
    if (answer != "{\"transport\":\"NAMED_PIPE\",\"status\":\"MOCK_ONLY\"}")
        throw new InvalidDataException("Unexpected synthetic transport answer.");
    return;
}
if (args.Length != 0) throw new ArgumentException("Only the smoke test CLI is supported.");

int checks = 0;
var name = CurrentUserPipe.NewPipeName();
await using (var server = CurrentUserPipe.CreateServer(name))
{
    var start = new ProcessStartInfo("dotnet") { UseShellExecute = false };
    start.ArgumentList.Add(Assembly.GetExecutingAssembly().Location);
    start.ArgumentList.Add("--synthetic-client");
    start.ArgumentList.Add(name);
    using var child = Process.Start(start) ?? throw new InvalidOperationException("Synthetic client failed to start.");
    try
    {
        await server.WaitForConnectionAsync(deadline.Token);
        var frame = await CurrentUserPipe.ReadJsonAsync(server, deadline.Token);
        // Impersonation uses the security context of a message already read.
        CurrentUserPipe.VerifyPeerUser(server);
        checks++;
        if (!frame.Contains("\"boundary\":\"MOCK_ONLY\"", StringComparison.Ordinal))
            throw new InvalidDataException("Missing synthetic boundary.");
        await CurrentUserPipe.WriteJsonAsync(server,
            "{\"transport\":\"NAMED_PIPE\",\"status\":\"MOCK_ONLY\"}", deadline.Token);
        await child.WaitForExitAsync(deadline.Token);
        if (child.ExitCode != 0) throw new InvalidOperationException("Synthetic client failed.");
        checks++;
    }
    finally { if (!child.HasExited) child.Kill(entireProcessTree: true); }
}

byte[] prefix = new byte[4];
BinaryPrimitives.WriteInt32LittleEndian(prefix, CurrentUserPipe.MaximumFrameBytes + 1);
await Expect<InvalidDataException>(() => CurrentUserPipe.ReadJsonAsync(new MemoryStream(prefix), deadline.Token));
await Expect<EndOfStreamException>(() => CurrentUserPipe.ReadJsonAsync(new MemoryStream(new byte[] { 0, 0 }), deadline.Token));
await Expect<InvalidDataException>(() => CurrentUserPipe.WriteJsonAsync(new MemoryStream(), "[]", deadline.Token));
await Expect<InvalidDataException>(() => CurrentUserPipe.WriteJsonAsync(new MemoryStream(), "{\"x\":\"" + new string('x', CurrentUserPipe.MaximumFrameBytes) + "\"}", deadline.Token));
checks += 4;
try { CurrentUserPipe.CreateClient(@"\\remote\pipe\anything"); throw new Exception("Remote name accepted."); }
catch (ArgumentException) { checks++; }
await using (var cancelled = CurrentUserPipe.CreateServer(CurrentUserPipe.NewPipeName()))
{
    using var stop = new CancellationTokenSource(TimeSpan.FromMilliseconds(100));
    await Expect<OperationCanceledException>(() => cancelled.WaitForConnectionAsync(stop.Token));
    checks++;
}
Console.WriteLine($"{{\"status\":\"CONTRACT_VERIFIED\",\"scope\":\"WINDOWS_TRANSPORT_REFERENCE_ONLY\",\"checks\":{checks},\"counterparty\":\"MOCK_ONLY\",\"desktop_integration\":\"LOCAL_REQUIRED\",\"cross_user_attempt\":\"NOT_RUN\"}}");

static async Task Expect<T>(Func<Task> action) where T : Exception
{
    try { await action(); }
    catch (T) { return; }
    throw new InvalidOperationException($"Expected {typeof(T).Name}.");
}
