using System.ComponentModel;
using System.IO.Pipes;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Security.Principal;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.Win32.SafeHandles;

namespace PoemSeed.LocalInterop.Pipes;

public enum AttestationState { UNVERIFIED, SAME_USER, KNOWN_PRODUCT, SIGNED_PRODUCT, TRUSTED_INSTALLATION, REJECTED }

/// <summary>Product fields are peer claims; OS-observed fields are never accepted from wire JSON.</summary>
public sealed record PeerIdentity
{
    public uint ProcessId { get; internal init; }
    public string UserSid { get; internal init; } = "";
    public string ExecutablePathHash { get; internal init; } = "";
    public string? ProductId { get; internal init; }
    public string? InstanceId { get; internal init; }
    public string? ProductVersion { get; internal init; }
    public AttestationState AttestationState { get; internal init; }
    internal PeerIdentity() { }
}

public sealed record PeerClaims(string ProductId, string InstanceId, string ProductVersion, string ProtocolVersion)
{
    // Exact character sets and bounds from frozen V1 ProductDescriptor. Absolute
    // anchors also reject terminal newlines; validation precedes identity retention.
    private static readonly Regex Product = new(@"\A[a-z][a-z0-9]*(?:[.-][a-z0-9]+)+\z", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Instance = new(@"\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\z", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    private static readonly Regex Version = new(@"\A[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\z", RegexOptions.CultureInvariant | RegexOptions.NonBacktracking);
    public bool IsWellFormed() => ProductId is { Length: >= 3 and <= 128 } && Product.IsMatch(ProductId) && !IdentityMetadata.HasCredentialShape(ProductId) &&
        InstanceId is { Length: >= 1 and <= 128 } && Instance.IsMatch(InstanceId) && !IdentityMetadata.HasCredentialShape(InstanceId) &&
        ProductVersion is { Length: >= 1 and <= 64 } && Version.IsMatch(ProductVersion) && !IdentityMetadata.HasCredentialShape(ProductVersion) && ProtocolVersion == "1.0";
}

/// <summary>Only pass to local verification hooks. Never serialize this object or log its private path.</summary>
public sealed class PeerVerificationTarget
{
    public PeerIdentity Identity { get; }
    public string ExecutablePath { get; }
    internal PeerVerificationTarget(PeerIdentity identity, string path) => (Identity, ExecutablePath) = (identity, path);
    public override string ToString() => $"PeerVerificationTarget(PID={Identity.ProcessId}, path=REDACTED)";
}

internal sealed class ObservedPeer : IDisposable
{
    private readonly SafeProcessHandle process;
    public PeerVerificationTarget Target { get; }
    private ObservedPeer(SafeProcessHandle process, PeerVerificationTarget target) => (this.process, Target) = (process, target);
    public void Dispose() => process.Dispose();

    public static ObservedPeer Capture(PipeStream pipe)
    {
        uint pid;
        bool success = pipe is NamedPipeServerStream
            ? GetNamedPipeClientProcessId(pipe.SafePipeHandle, out pid)
            : GetNamedPipeServerProcessId(pipe.SafePipeHandle, out pid);
        if (!success || pid == 0) throw new UnauthorizedAccessException("OS peer process identity unavailable.");
        var process = OpenProcess(0x1000, false, pid); // PROCESS_QUERY_LIMITED_INFORMATION; never inherited.
        if (process.IsInvalid) { process.Dispose(); throw new UnauthorizedAccessException("Peer process cannot be verified."); }
        try
        {
            if (!OpenProcessToken(process, 0x0008, out var token))
                throw new UnauthorizedAccessException("Peer token cannot be verified.");
            string? sid;
            using (token)
            using (var identity = new WindowsIdentity(token.DangerousGetHandle())) sid = identity.User?.Value;
            using var current = WindowsIdentity.GetCurrent();
            if (sid is null || sid != current.User?.Value)
                throw new UnauthorizedAccessException("Peer is not the current Windows user.");
            var path = new StringBuilder(32_768);
            int size = path.Capacity;
            if (!QueryFullProcessImageNameW(process, 0, path, ref size))
                throw new UnauthorizedAccessException("Peer executable cannot be verified.");
            uint confirmed;
            success = pipe is NamedPipeServerStream
                ? GetNamedPipeClientProcessId(pipe.SafePipeHandle, out confirmed)
                : GetNamedPipeServerProcessId(pipe.SafePipeHandle, out confirmed);
            if (!success || confirmed != pid)
                throw new UnauthorizedAccessException("Peer identity changed during observation.");
            string privatePath = Path.GetFullPath(path.ToString());
            string hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(privatePath.ToUpperInvariant()))).ToLowerInvariant();
            return new ObservedPeer(process, new PeerVerificationTarget(new PeerIdentity
            {
                ProcessId = pid, UserSid = sid, ExecutablePathHash = hash,
                AttestationState = AttestationState.SAME_USER,
            }, privatePath));
        }
        catch { process.Dispose(); throw; }
    }

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetNamedPipeClientProcessId(SafePipeHandle pipe, out uint processId);
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetNamedPipeServerProcessId(SafePipeHandle pipe, out uint processId);
    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern SafeProcessHandle OpenProcess(uint access, [MarshalAs(UnmanagedType.Bool)] bool inherit, uint processId);
    [DllImport("advapi32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool OpenProcessToken(SafeProcessHandle process, uint access, out SafeAccessTokenHandle token);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool QueryFullProcessImageNameW(SafeProcessHandle process, uint flags, StringBuilder name, ref int size);
}
