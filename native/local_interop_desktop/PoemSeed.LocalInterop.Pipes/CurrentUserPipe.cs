using System.ComponentModel;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text.RegularExpressions;
using Microsoft.Win32.SafeHandles;

namespace PoemSeed.LocalInterop.Pipes;

/// <summary>
/// Explicit-start, Windows-only callable transport boundary. It is deliberately NOT wired
/// into either desktop application. Callers must run canonical DTO validation,
/// HELLO -> negotiation -> session authorization and live revocation at every
/// delivery. A pipe connection alone NEVER grants protocol capabilities.
/// </summary>
public static class CurrentUserPipe
{
    public const int MaximumFrameBytes = PipeFrames.MaximumFrameBytes;
    public const uint RejectRemoteClients = 0x00000008;
    private const uint Duplex = 0x00000003;
    private const uint Overlapped = 0x40000000;
    private const uint FirstInstance = 0x00080000;

    public static string NewPipeName() => "poemseed-interop-v1-" + Guid.NewGuid().ToString("N");

    public static void CheckName(string name)
    {
        if (!OperatingSystem.IsWindows())
            throw new PlatformNotSupportedException("Windows named pipe transport only.");
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
            TokenImpersonationLevel.Identification, HandleInheritability.None);
    }

    public static void VerifyPeerUser(NamedPipeServerStream pipe)
    {
        var ownSid = WindowsIdentity.GetCurrent().User?.Value;
        string? peerSid = null;
        pipe.RunAsClient(() => peerSid = WindowsIdentity.GetCurrent(true)?.User?.Value);
        if (ownSid is null || peerSid != ownSid)
            throw new UnauthorizedAccessException("Pipe peer is not the current user.");
    }

    public static Task<string> ReadJsonAsync(Stream stream, CancellationToken cancellationToken) =>
        PipeFrames.ReadAsync(stream, TimeSpan.FromSeconds(10), cancellationToken);

    public static Task WriteJsonAsync(Stream stream, string json, CancellationToken cancellationToken) =>
        PipeFrames.WriteAsync(stream, json, TimeSpan.FromSeconds(10), cancellationToken);

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
