using System.Buffers.Binary;
using System.ComponentModel;
using System.Diagnostics;
using System.IO.Pipes;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Security.Principal;
using System.Text;
using System.Text.Json;
using Microsoft.Win32.SafeHandles;
using PoemSeed.LocalInterop.Pipes;

return await Acceptance.RunAsync(args);

internal static class Acceptance
{
    private static readonly TimeSpan Deadline = TimeSpan.FromSeconds(5);
    private static readonly List<string> Passed = [];
    private static readonly string Hello = "{\"boundary\":\"MOCK_ONLY\",\"protocol_version\":\"1.0\"}";

    public static async Task<int> RunAsync(string[] args)
    {
        try
        {
            if (args is ["--child", var mode, var name]) return await ChildAsync(mode, name);
            if (args is ["--cross-user-server"]) return await CrossUserServerAsync();
            if (args is ["--cross-user-client", var pipe, var sid]) return await CrossUserClientAsync(pipe, sid);
            if (args.Length > 0 && args is not ["--portable"]) throw new ArgumentException("Unsupported harness mode.");
            await FrameChecksAsync();
            if (OperatingSystem.IsWindows() && args.Length == 0) await WindowsChecksAsync();
            Console.WriteLine(JsonSerializer.Serialize(new
            {
                status = "CONTRACT_VERIFIED", scope = "CALLABLE_NATIVE_BOUNDARY", checks = Passed.Count,
                passed = Passed, windows_transport = OperatingSystem.IsWindows() && args.Length == 0 ? "CONTRACT_VERIFIED" : "NOT_RUN",
                counterparty = "MOCK_ONLY", real_signed_binary_trust = "LOCAL_REQUIRED",
                actual_install_registration = "LOCAL_REQUIRED", cross_user_attempt = "NOT_RUN", desktop_integration = "LOCAL_REQUIRED",
            }));
            return 0;
        }
        catch (Exception ex)
        {
            // Exception messages may contain paths. Keep receipts non-content and path-free.
            Console.Error.WriteLine(JsonSerializer.Serialize(new { status = "FAILED", error_type = ex.GetType().Name, passed = Passed }));
            return 1;
        }
    }

    private static async Task Check(string name, Func<Task> body)
    {
        await body(); Passed.Add(name);
    }
    private static void Require(bool value) { if (!value) throw new InvalidOperationException("Assertion failed."); }
    private static async Task Expect<T>(Func<Task> body) where T : Exception
    {
        try { await body(); } catch (T) { return; }
        throw new InvalidOperationException($"Expected {typeof(T).Name}.");
    }
    private static byte[] Frame(byte[] body)
    {
        byte[] result = new byte[4 + body.Length];
        BinaryPrimitives.WriteUInt32LittleEndian(result, (uint)body.Length); body.CopyTo(result, 4); return result;
    }

    private static async Task FrameChecksAsync()
    {
        await Check("frame_roundtrip", async () =>
        {
            var stream = new MemoryStream(); await PipeFrames.WriteAsync(stream, Hello, Deadline); stream.Position = 0;
            Require(await PipeFrames.ReadAsync(stream, Deadline) == Hello);
        });
        await Check("fragmented_frame", async () => Require(await PipeFrames.ReadAsync(new FragmentedStream(Frame(Encoding.UTF8.GetBytes(Hello))), Deadline) == Hello));
        await Check("coalesced_frames", async () =>
        {
            var stream = new MemoryStream(); await PipeFrames.WriteAsync(stream, Hello, Deadline); await PipeFrames.WriteAsync(stream, "{}", Deadline);
            stream.Position = 0; Require(await PipeFrames.ReadAsync(stream, Deadline) == Hello); Require(await PipeFrames.ReadAsync(stream, Deadline) == "{}");
        });
        foreach (var size in new uint[] { 0, PipeFrames.MaximumFrameBytes + 1, uint.MaxValue })
            await Check($"frame_length_reject_{size}", async () =>
            {
                byte[] prefix = new byte[4]; BinaryPrimitives.WriteUInt32LittleEndian(prefix, size);
                await Expect<InvalidDataException>(() => PipeFrames.ReadAsync(new MemoryStream(prefix), Deadline));
            });
        await Check("truncated_prefix", () => Expect<EndOfStreamException>(() => PipeFrames.ReadAsync(new MemoryStream([1, 0]), Deadline)));
        await Check("truncated_body", () => Expect<EndOfStreamException>(() => PipeFrames.ReadAsync(new MemoryStream([4, 0, 0, 0, 123]), Deadline)));
        await Check("invalid_utf8", () => Expect<DecoderFallbackException>(() => PipeFrames.ReadAsync(new MemoryStream(Frame([123, 255, 125])), Deadline)));
        await Check("non_object", () => Expect<InvalidDataException>(() => PipeFrames.WriteAsync(new MemoryStream(), "[]", Deadline)));
        await Check("duplicate_members", () => Expect<InvalidDataException>(() => PipeFrames.WriteAsync(new MemoryStream(), "{\"x\":1,\"x\":2}", Deadline)));
        await Check("invalid_json", () => Expect<JsonException>(() => PipeFrames.WriteAsync(new MemoryStream(), "{", Deadline)));
        await Check("excessive_depth", () => Expect<JsonException>(() => PipeFrames.WriteAsync(new MemoryStream(), string.Concat(Enumerable.Repeat("{\"x\":", 26)) + "1" + new string('}', 26), Deadline)));
        await Check("multibyte_size_limit", () => Expect<InvalidDataException>(() => PipeFrames.WriteAsync(new MemoryStream(), "{\"x\":\"" + new string('\u4e2d', 400_000) + "\"}", Deadline)));
        await Check("frame_timeout", () => Expect<OperationCanceledException>(() => PipeFrames.ReadAsync(new NeverReadStream(), TimeSpan.FromMilliseconds(30))));
        await Check("frame_cancellation", async () =>
        {
            using var stop = new CancellationTokenSource(); stop.Cancel();
            await Expect<OperationCanceledException>(() => PipeFrames.ReadAsync(new NeverReadStream(), Deadline, stop.Token));
        });
        await Check("queue_config_bound", () => Expect<ArgumentOutOfRangeException>(() => Task.FromResult(new NamedPipeTransport(new() { OutboundQueueCapacity = 65 }))));
        await Check("identity_claims_and_required_loaded_image_proof", async () =>
        {
            Require(new PeerClaims("poemseed.tutor.desktop", "instance:MOCK_ONLY-1", "1.0.0-beta+2", "1.0").IsWellFormed());
            var target = new PeerVerificationTarget(new PeerIdentity
            {
                ProcessId = 123, UserSid = "MOCK_ONLY", ExecutablePathHash = new string('0', 64),
                AttestationState = AttestationState.SAME_USER,
            }, @"C:\MOCK_ONLY\peer.exe");
            foreach (var bad in new[]
            {
                new PeerClaims(@"C:\Users\example\private.txt", "instance", "1.0", "1.0"),
                new PeerClaims("poemseed.tutor.desktop", "provider secret=MOCK_ONLY", "1.0", "1.0"),
                new PeerClaims("poemseed.tutor.desktop", "instance", "https://private.invalid/version", "1.0"),
                new PeerClaims("poemseed.tutor.desktop\n", "instance", "1.0", "1.0"),
                new PeerClaims("poemseed.tutor.desktop", new string('x', 129), "1.0", "1.0"),
                new PeerClaims("poemseed.tutor.desktop", "instance", new string('1', 65), "1.0"),
                new PeerClaims("sk-" + new string('a', 24), "instance", "1.0", "1.0"),
                new PeerClaims("poemseed.tutor.desktop", "ghp_" + new string('b', 24), "1.0", "1.0"),
                new PeerClaims("poemseed.tutor.desktop", "instance", "sk-proj-" + new string('a', 24), "1.0"),
                new PeerClaims("poemseed.tutor.desktop", "api_key:MOCK_ONLY", "1.0", "1.0"),
                new PeerClaims("poemseed.tutor.desktop", "Bearer:" + new string('b', 16), "1.0", "1.0"),
            })
            {
                Require(!bad.IsWellFormed());
                var result = await new InteropPeerAttestation().VerifyAsync(target, bad);
                Require(result.Identity.AttestationState == AttestationState.REJECTED && result.Identity.ProductId is null &&
                    result.Identity.InstanceId is null && result.Identity.ProductVersion is null);
            }
            var valid = new PeerClaims("poemseed.tutor.desktop", "MOCK_ONLY", "1.0", "1.0");
            var install = new MockInstall(); var signature = new MockSignature();
            var attestation = new InteropPeerAttestation(install, signature);
            Require((await attestation.VerifyAsync(target, valid)).Authenticated); // Synthetic proof only.
            install.ConnectedImageVerified = false;
            var missingInstallBinding = await attestation.VerifyAsync(target, valid);
            Require(!missingInstallBinding.Authenticated && missingInstallBinding.EvidenceStatus == "LOCAL_REQUIRED");
            install.ConnectedImageVerified = true; signature.ConnectedImageVerified = false;
            var missingSignatureBinding = await attestation.VerifyAsync(target, valid);
            Require(!missingSignatureBinding.Authenticated && missingSignatureBinding.EvidenceStatus == "LOCAL_REQUIRED");
            signature.ConnectedImageVerified = true; signature.Publisher = "sk-" + new string('a', 24);
            Require((await attestation.VerifyAsync(target, valid)).Reason == "INVALID_PUBLISHER_IDENTITY_METADATA");
            Require(!IdentityMetadata.SafeOpaque(@"C:\private\install", 128) &&
                !IdentityMetadata.SafeOpaque("github_pat_" + new string('b', 24), 256));
        });
        await Check("attestation_timeout_retains_bounded_outstanding_slot", async () =>
        {
            var limiter = new AttestationWorkLimiter();
            var started = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            var release = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
            using var cancel = new CancellationTokenSource();
            int invoked = 0;
            var operation = limiter.Start(async () =>
            {
                Interlocked.Increment(ref invoked); started.TrySetResult();
                return await release.Task; // Deliberately ignores cancellation, like an uncooperative platform hook.
            }, cancel.Token);
            try
            {
                await started.Task.WaitAsync(Deadline); cancel.CancelAfter(TimeSpan.FromMilliseconds(20));
                await Expect<OperationCanceledException>(() => operation.WaitAsync(cancel.Token));
                for (int i = 0; i < 128; i++)
                    await Expect<PeerAttestationBusyException>(() => limiter.Start(() => Task.FromResult(99), CancellationToken.None));
                Require(invoked == 1);
            }
            finally { release.TrySetResult(7); await operation.WaitAsync(Deadline); }
            Require(await limiter.Start(() => Task.FromResult(8), CancellationToken.None) == 8);
            var releaseAll = new TaskCompletionSource<int>(TaskCreationOptions.RunContinuationsAsynchronously);
            var occupied = new List<Task<int>>();
            try
            {
                for (int i = 0; i < 4; i++) occupied.Add(new AttestationWorkLimiter().Start(() => releaseAll.Task, CancellationToken.None));
                await Expect<PeerAttestationBusyException>(() => new AttestationWorkLimiter().Start(() => Task.FromResult(9), CancellationToken.None));
            }
            finally { releaseAll.TrySetResult(1); await Task.WhenAll(occupied).WaitAsync(Deadline); }
        });
    }

    private static async Task WindowsChecksAsync()
    {
        await Check("same_user_separate_process_identity_and_echo", async () =>
        {
            await using var server = new NamedPipeTransport(); string name = server.Start();
            using var child = Spawn("echo", name);
            try
            {
                await server.AcceptAsync();
                var peer = server.PeerIdentity!;
                using var current = WindowsIdentity.GetCurrent();
                Require(peer.ProcessId == child.Id && peer.ProcessId != Environment.ProcessId && peer.UserSid == current.User!.Value);
                Require(peer.ExecutablePathHash.Length == 64 && peer.AttestationState == AttestationState.SAME_USER && !server.Health.PeerAuthenticated);
                Require(await server.ReceiveAsync() == Hello); await server.SendAsync("{}"); await ChildSucceeded(child);
            }
            finally { Kill(child); }
        });
        await Check("server_handle_not_inheritable", () =>
        {
            using var pipe = CurrentUserPipe.CreateServer(CurrentUserPipe.NewPipeName());
            Require(GetHandleInformation(pipe.SafePipeHandle, out uint flags) && (flags & 1) == 0); return Task.CompletedTask;
        });
        await Check("remote_and_arbitrary_name_rejected", async () =>
        {
            await Expect<ArgumentException>(() => Task.FromResult(CurrentUserPipe.CreateClient(@"\\remote\pipe\x")));
            await Expect<ArgumentException>(() => Task.FromResult(CurrentUserPipe.CreateServer("arbitrary")));
        });
        await Check("first_instance_collision_rejected", async () =>
        {
            string name = CurrentUserPipe.NewPipeName(); using var first = CurrentUserPipe.CreateServer(name);
            await Expect<Win32Exception>(() => Task.FromResult(CurrentUserPipe.CreateServer(name)));
        });
        await Check("accept_cancel_and_shutdown", async () =>
        {
            await using var server = new NamedPipeTransport(); server.Start();
            using var stop = new CancellationTokenSource(TimeSpan.FromMilliseconds(50));
            await Expect<OperationCanceledException>(() => server.AcceptAsync(stop.Token));
            await server.ShutdownAsync().WaitAsync(TimeSpan.FromSeconds(2)); Require(server.Health.State == PipeTransportState.STOPPED);
        });
        await Check("missing_endpoint_connect_timeout", async () =>
        {
            await using var client = new NamedPipeTransport(new() { ConnectTimeout = TimeSpan.FromMilliseconds(60) });
            await Expect<OperationCanceledException>(() => client.ConnectAsync(CurrentUserPipe.NewPipeName()));
        });
        await Check("receive_cancel_invalidates_stream", async () =>
        {
            await WithIdlePeer(async server =>
            {
                using var stop = new CancellationTokenSource(TimeSpan.FromMilliseconds(50));
                await Expect<OperationCanceledException>(() => server.ReceiveAsync(stop.Token));
                Require(server.Health.State == PipeTransportState.FAILED && !server.Health.PeerAuthenticated);
            });
        });
        await Check("malformed_peer_frame_closes_connection", async () =>
        {
            await using var server = new NamedPipeTransport(); string name = server.Start(); using var child = Spawn("malformed", name);
            try { await server.AcceptAsync(); await Expect<InvalidDataException>(() => server.ReceiveAsync()); Require(server.Health.State == PipeTransportState.FAILED); await ChildSucceeded(child); }
            finally { Kill(child); }
        });
        await Check("single_active_connection_limit", async () =>
        {
            await WithIdlePeer(async server =>
            {
                await using var extra = CurrentUserPipe.CreateClient(server.PipeName!);
                using var stop = new CancellationTokenSource(TimeSpan.FromMilliseconds(80));
                await Expect<OperationCanceledException>(() => extra.ConnectAsync(stop.Token));
                Require(server.Health.ConnectionLimit == 1);
            });
        });
        await Check("queue_backpressure_and_bounded_shutdown", async () =>
        {
            await WithIdlePeer(async server =>
            {
                var pending = new List<Task>(); bool rejected = false;
                string body = "{\"x\":\"" + new string('x', 900_000) + "\"}";
                for (int i = 0; i < 40; i++)
                    try { pending.Add(server.SendAsync(body)); } catch (PipeBackpressureException) { rejected = true; break; }
                Require(rejected && server.Health.QueuedMessages <= 8);
                var watch = Stopwatch.StartNew(); await server.ShutdownAsync(); Require(watch.Elapsed < TimeSpan.FromSeconds(3));
                foreach (var pendingWrite in pending) try { await pendingWrite; } catch (IOException) { } catch (OperationCanceledException) { } catch (ObjectDisposedException) { }
            });
        });
        await Check("fake_product_id_rejected_without_installation", async () =>
        {
            await WithIdlePeer(async server =>
            {
                var result = await server.AttestAsync(new("poemseed.tutor.desktop", "malicious-claim", "1.0", "1.0"), new());
                Require(!result.Authenticated && result.Identity.AttestationState == AttestationState.REJECTED && result.EvidenceStatus == "LOCAL_REQUIRED");
            });
        });
        await Check("mock_attestation_requires_registration_publisher_and_approval", async () =>
        {
            await WithIdlePeer(async server =>
            {
                var claims = new PeerClaims("poemseed.tutor.desktop", "MOCK_ONLY", "1.0", "1.0");
                var registration = new MockInstall(); var signed = new MockSignature();
                var verifier = new InteropPeerAttestation(registration, signed);
                Require((await server.AttestAsync(claims, verifier)).Authenticated);
                signed.Publisher = "different-publisher";
                Require(!(await server.AttestAsync(claims, verifier)).Authenticated && !server.Health.PeerAuthenticated);
                signed.Publisher = "MOCK_ONLY"; registration.Approved = false;
                Require((await server.AttestAsync(claims, verifier)).Identity.AttestationState == AttestationState.SIGNED_PRODUCT);
                registration.Approved = true; registration.Revoked = true;
                Require((await server.AttestAsync(claims, verifier)).Identity.AttestationState == AttestationState.REJECTED);
            });
        });
        await Check("timed_out_attestation_backpressure_survives_reconnect", async () =>
        {
            await using var server = new NamedPipeTransport();
            await using var client = new NamedPipeTransport(new() { ConnectTimeout = TimeSpan.FromMilliseconds(250) });
            string name = server.Start(); await Task.WhenAll(server.AcceptAsync(), client.ConnectAsync(name));
            var slow = new UncooperativeInstall();
            var claims = new PeerClaims("poemseed.tutor.desktop", "MOCK_ONLY", "1.0", "1.0");
            try
            {
                await Expect<OperationCanceledException>(() => client.AttestAsync(claims, new(slow, new MockSignature())));
                Require(slow.Invoked == 1 && !client.Health.PeerAuthenticated);
                for (int i = 0; i < 32; i++)
                    await Expect<PeerAttestationBusyException>(() => client.AttestAsync(claims, new(slow, new MockSignature())));
                await server.DisconnectAsync(); string next = server.Start();
                await Task.WhenAll(server.AcceptAsync(), client.ReconnectAsync(next));
                await Expect<PeerAttestationBusyException>(() => client.AttestAsync(claims, new(slow, new MockSignature())));
                Require(slow.Invoked == 1 && !client.Health.PeerAuthenticated);
            }
            finally { slow.Release.TrySetResult(null); }
        });
        await Check("reconnect_has_new_identity_and_no_trust", async () =>
        {
            await using var server = new NamedPipeTransport(); await using var client = new NamedPipeTransport();
            string name = server.Start(); await Task.WhenAll(server.AcceptAsync(), client.ConnectAsync(name));
            Guid? previous = client.Health.ConnectionId;
            await client.AttestAsync(new("poemseed.tutor.desktop", "MOCK_ONLY", "1.0", "1.0"), new(new MockInstall(), new MockSignature()));
            Require(client.Health.PeerAuthenticated); await server.DisconnectAsync(); string restartedName = server.Start();
            await Task.WhenAll(server.AcceptAsync(), client.ReconnectAsync(restartedName));
            Require(client.Health.ConnectionId != previous && !client.Health.PeerAuthenticated && client.PeerIdentity!.AttestationState == AttestationState.SAME_USER);
        });
    }

    private static async Task WithIdlePeer(Func<NamedPipeTransport, Task> action)
    {
        await using var server = new NamedPipeTransport(); string name = server.Start(); using var child = Spawn("idle", name);
        try { await server.AcceptAsync(); Require(await server.ReceiveAsync() == Hello); await action(server); }
        finally { Kill(child); }
    }
    private static Process Spawn(string mode, string pipe)
    {
        var start = new ProcessStartInfo("dotnet") { UseShellExecute = false };
        start.ArgumentList.Add(Assembly.GetExecutingAssembly().Location); start.ArgumentList.Add("--child"); start.ArgumentList.Add(mode); start.ArgumentList.Add(pipe);
        return Process.Start(start) ?? throw new InvalidOperationException("Synthetic child could not start.");
    }
    private static async Task ChildSucceeded(Process child)
    {
        await child.WaitForExitAsync().WaitAsync(Deadline); Require(child.ExitCode == 0);
    }
    private static void Kill(Process child) { if (!child.HasExited) { child.Kill(entireProcessTree: true); child.WaitForExit(5000); } }
    private static async Task<int> ChildAsync(string mode, string name)
    {
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        await using var client = CurrentUserPipe.CreateClient(name); await client.ConnectAsync(deadline.Token);
        Require(GetHandleInformation(client.SafePipeHandle, out uint flags) && (flags & 1) == 0);
        if (mode == "malformed")
        {
            await client.WriteAsync(new byte[] { 0, 0, 0, 0 }, deadline.Token); await client.FlushAsync(deadline.Token);
            // Stay alive until the server observes this process and rejects the malformed frame.
            try { await client.ReadAsync(new byte[1], deadline.Token); } catch (IOException) { }
            return 0;
        }
        await PipeFrames.WriteAsync(client, Hello, Deadline, deadline.Token);
        if (mode == "echo") { Require(await PipeFrames.ReadAsync(client, Deadline, deadline.Token) == "{}"); return 0; }
        if (mode == "idle") { await Task.Delay(TimeSpan.FromSeconds(25), deadline.Token); return 0; }
        throw new ArgumentException("Unknown synthetic mode.");
    }

    // Operators must run these modes in two existing, distinct Windows account sessions.
    // The harness never creates users, transmits passwords, changes ACLs, or invokes runas.
    private static async Task<int> CrossUserServerAsync()
    {
        using var current = WindowsIdentity.GetCurrent();
        string name = CurrentUserPipe.NewPipeName(); await using var pipe = CurrentUserPipe.CreateServer(name);
        Console.WriteLine(JsonSerializer.Serialize(new { state = "LISTENING", pipe_name = name, server_sid = current.User!.Value, server_pid = Environment.ProcessId, started_at = DateTimeOffset.UtcNow, window_seconds = 120 }));
        using var deadline = new CancellationTokenSource(TimeSpan.FromSeconds(120));
        try
        {
            await pipe.WaitForConnectionAsync(deadline.Token);
            Console.WriteLine("{\"status\":\"FAILED\",\"reason\":\"UNEXPECTED_CONNECTION_REQUIRES_REVIEW\"}"); return 1;
        }
        catch (OperationCanceledException)
        {
            Console.WriteLine(JsonSerializer.Serialize(new { status = "NOT_RUN", reason = "PAIR_WITH_DISTINCT_USER_ACCESS_DENIED_RECEIPT", pipe_name = name, server_sid = current.User!.Value, ended_at = DateTimeOffset.UtcNow })); return 2;
        }
    }
    private static async Task<int> CrossUserClientAsync(string name, string serverSid)
    {
        CurrentUserPipe.CheckName(name);
        using var current = WindowsIdentity.GetCurrent(); string clientSid = current.User!.Value;
        if (serverSid == clientSid || !new SecurityIdentifier(serverSid).IsAccountSid())
        {
            Console.WriteLine("{\"status\":\"NOT_RUN\",\"reason\":\"DISTINCT_OS_USER_REQUIRED\"}"); return 2;
        }
        // Deliberately omit CurrentUserOnly: this must test the server's ACL, not a cooperative client's guard.
        using var client = new NamedPipeClientStream(".", name, PipeDirection.InOut, PipeOptions.Asynchronous,
            TokenImpersonationLevel.Identification, HandleInheritability.None);
        try
        {
            await client.ConnectAsync(5000);
            Console.WriteLine(JsonSerializer.Serialize(new { status = "FAILED", reason = "HOSTILE_CROSS_USER_CONNECTED", pipe_name = name, server_sid = serverSid, client_sid = clientSid })); return 1;
        }
        catch (UnauthorizedAccessException)
        {
            Console.WriteLine(JsonSerializer.Serialize(new { status = "ACCESS_DENIED", scope = "HOSTILE_CROSS_USER_CANDIDATE", pipe_name = name, server_sid = serverSid, client_sid = clientSid, client_pid = Environment.ProcessId, attempted_at = DateTimeOffset.UtcNow, requires_matching_live_server_receipt = true })); return 0;
        }
        catch (TimeoutException)
        {
            Console.WriteLine("{\"status\":\"NOT_RUN\",\"reason\":\"NO_LIVE_PIPE_OR_INCONCLUSIVE_TIMEOUT\"}"); return 2;
        }
    }

    private sealed class UncooperativeInstall : IInstalledProductVerifier
    {
        public int Invoked;
        public TaskCompletionSource<InstallationEvidence?> Release { get; } = new(TaskCreationOptions.RunContinuationsAsynchronously);
        public async ValueTask<InstallationEvidence?> VerifyAsync(PeerVerificationTarget target, PeerClaims claims, CancellationToken cancellationToken)
        {
            Interlocked.Increment(ref Invoked);
            return await Release.Task; // Intentionally ignores cancellation for negative coverage only.
        }
    }
    private sealed class MockInstall : IInstalledProductVerifier
    {
        public bool Approved { get; set; } = true;
        public bool ConnectedImageVerified { get; set; } = true;
        public bool Revoked { get; set; }
        public ValueTask<InstallationEvidence?> VerifyAsync(PeerVerificationTarget target, PeerClaims claims, CancellationToken cancellationToken) =>
            ValueTask.FromResult<InstallationEvidence?>(new(claims.ProductId, "MOCK_ONLY-install", target.Identity.ExecutablePathHash,
                "MOCK_ONLY", claims.ProductVersion, claims.ProtocolVersion, Approved, Revoked, ConnectedImageVerified: ConnectedImageVerified));
    }
    private sealed class MockSignature : ISignedExecutableVerifier
    {
        public string Publisher { get; set; } = "MOCK_ONLY";
        public bool ConnectedImageVerified { get; set; } = true;
        public ValueTask<SignatureEvidence> VerifyAsync(PeerVerificationTarget target, CancellationToken cancellationToken) =>
            ValueTask.FromResult(new SignatureEvidence(SignatureStatus.VALID, Publisher, ConnectedImageVerified: ConnectedImageVerified));
    }
    private sealed class FragmentedStream(byte[] bytes) : MemoryStream(bytes)
    {
        public override ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default) => base.ReadAsync(buffer[..Math.Min(1, buffer.Length)], cancellationToken);
    }
    private sealed class NeverReadStream : Stream
    {
        public override bool CanRead => true; public override bool CanWrite => false; public override bool CanSeek => false;
        public override long Length => throw new NotSupportedException(); public override long Position { get => throw new NotSupportedException(); set => throw new NotSupportedException(); }
        public override void Flush() => throw new NotSupportedException(); public override int Read(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override long Seek(long offset, SeekOrigin origin) => throw new NotSupportedException(); public override void SetLength(long value) => throw new NotSupportedException();
        public override void Write(byte[] buffer, int offset, int count) => throw new NotSupportedException();
        public override async ValueTask<int> ReadAsync(Memory<byte> buffer, CancellationToken cancellationToken = default) { await Task.Delay(Timeout.Infinite, cancellationToken); return 0; }
    }
    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetHandleInformation(SafePipeHandle handle, out uint flags);
}
