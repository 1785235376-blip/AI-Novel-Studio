using System.Buffers.Binary;
using System.ComponentModel;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.Win32.SafeHandles;

namespace PoemSeed.LocalInterop.Pipes;

/// <summary>
/// Explicit-start, Windows-only transport reference. It is deliberately NOT wired
/// into either desktop application. Callers must run canonical DTO validation,
/// HELLO -> negotiation -> session authorization and live revocation at every
/// delivery. A pipe connection alone NEVER grants protocol capabilities.
/// </summary>
public static class CurrentUserPipe
{
    public const int MaximumFrameBytes = 1_048_576;
    public const uint RejectRemoteClients = 0x00000008;
    private const uint Duplex = 0x00000003;
    private const uint Overlapped = 0x40000000;
    private const uint FirstInstance = 0x00080000;
    private static readonly UTF8Encoding StrictUtf8 = new(false, true);

    public static string NewPipeName() => "poemseed-interop-v1-" + Guid.NewGuid().ToString("N");

    private static void CheckName(string name)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("Windows named pipe reference only.");
        if (!Regex.IsMatch(name, "\\Apoemseed-interop-v1-[a-f0-9]{32}\\z",
                RegexOptions.CultureInvariant))
            throw new ArgumentException("Invalid opaque pipe instance name.", nameof(name));
    }

    public static NamedPipeServerStream CreateServer(string name)
    {
        CheckName(name);
        var sid = WindowsIdentity.GetCurrent().User?.Value
            ?? throw new UnauthorizedAccessException("Current user identity unavailable.");
        // Network logons are explicitly denied; only this user's SID is allowed.
        // PIPE_REJECT_REMOTE_CLIENTS provides a second, independent LAN boundary.
        var descriptorText = $"D:P(D;;GA;;;NU)(A;;GA;;;{sid})";
        if (!ConvertStringSecurityDescriptorToSecurityDescriptorW(descriptorText, 1,
                out var descriptor, out _))
            throw new Win32Exception(Marshal.GetLastWin32Error());
        try
        {
            var security = new SecurityAttributes
            {
                Length = Marshal.SizeOf<SecurityAttributes>(),
                SecurityDescriptor = descriptor,
                InheritHandle = 0,
            };
            var handle = CreateNamedPipeW(@"\\.\pipe\" + name,
                Duplex | Overlapped | FirstInstance, RejectRemoteClients,
                1, MaximumFrameBytes + 4, MaximumFrameBytes + 4, 0, ref security);
            if (handle.IsInvalid)
            {
                var error = Marshal.GetLastWin32Error();
                handle.Dispose();
                throw new Win32Exception(error);
            }
            try
            {
                return new NamedPipeServerStream(PipeDirection.InOut, true, false, handle);
            }
            catch { handle.Dispose(); throw; }
        }
        finally { LocalFree(descriptor); }
    }

    public static NamedPipeClientStream CreateClient(string name)
    {
        CheckName(name);
        // Server name is fixed. There is no API accepting a remote machine.
        return new NamedPipeClientStream(".", name, PipeDirection.InOut,
            PipeOptions.Asynchronous | PipeOptions.CurrentUserOnly,
            TokenImpersonationLevel.Identification);
    }

    public static void VerifyPeerUser(NamedPipeServerStream pipe)
    {
        var ownSid = WindowsIdentity.GetCurrent().User?.Value;
        string? peerSid = null;
        pipe.RunAsClient(() => peerSid = WindowsIdentity.GetCurrent(true)?.User?.Value);
        if (ownSid is null || peerSid != ownSid)
            throw new UnauthorizedAccessException("Pipe peer is not the current user.");
    }

    public static async Task<string> ReadJsonAsync(Stream stream, CancellationToken cancellationToken)
    {
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        deadline.CancelAfter(TimeSpan.FromSeconds(10));
        byte[] prefix = new byte[4];
        await stream.ReadExactlyAsync(prefix, deadline.Token);
        int size = BinaryPrimitives.ReadInt32LittleEndian(prefix);
        if (size is <= 0 or > MaximumFrameBytes)
            throw new InvalidDataException("Frame exceeds the bounded transport contract.");
        byte[] buffer = new byte[size];
        await stream.ReadExactlyAsync(buffer, deadline.Token);
        string json = StrictUtf8.GetString(buffer);
        ValidateObject(json);
        return json;
    }

    public static async Task WriteJsonAsync(Stream stream, string json, CancellationToken cancellationToken)
    {
        ValidateObject(json);
        byte[] buffer = StrictUtf8.GetBytes(json);
        if (buffer.Length is <= 0 or > MaximumFrameBytes)
            throw new InvalidDataException("Frame exceeds the bounded transport contract.");
        using var deadline = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        deadline.CancelAfter(TimeSpan.FromSeconds(10));
        byte[] prefix = new byte[4];
        BinaryPrimitives.WriteInt32LittleEndian(prefix, buffer.Length);
        await stream.WriteAsync(prefix, deadline.Token);
        await stream.WriteAsync(buffer, deadline.Token);
        await stream.FlushAsync(deadline.Token);
    }

    private static void ValidateObject(string json)
    {
        using var parsed = JsonDocument.Parse(json, new JsonDocumentOptions { MaxDepth = 24 });
        if (parsed.RootElement.ValueKind != JsonValueKind.Object)
            throw new InvalidDataException("Protocol frame must be a JSON object.");
        // No schema/authority inference here: use the canonical versioned DTOs.
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct SecurityAttributes
    {
        public int Length;
        public IntPtr SecurityDescriptor;
        public int InheritHandle;
    }

    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool ConvertStringSecurityDescriptorToSecurityDescriptorW(
        string descriptor, uint revision, out IntPtr securityDescriptor, out uint size);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern SafePipeHandle CreateNamedPipeW(string name, uint openMode,
        uint pipeMode, uint maxInstances, uint outBufferSize, uint inBufferSize,
        uint defaultTimeout, ref SecurityAttributes securityAttributes);

    [DllImport("kernel32.dll")]
    private static extern IntPtr LocalFree(IntPtr memory);
}
