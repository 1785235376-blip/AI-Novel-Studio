using System.IO.Pipes;
using System.Threading.Channels;

namespace PoemSeed.LocalInterop.Pipes;

public enum PipeTransportState { STOPPED, LISTENING, CONNECTING, TRANSPORT_CONNECTED, DISCONNECTING, FAILED }
public sealed record PipeTransportHealth(PipeTransportState State, Guid? ConnectionId, bool PeerAuthenticated,
    int QueuedMessages, int ConnectionLimit, string? LastErrorCode);
public sealed class PipeBackpressureException() : IOException("Outbound transport queue is full.");

public sealed record NamedPipeTransportOptions
{
    public int OutboundQueueCapacity { get; init; } = 8;
    public TimeSpan ConnectTimeout { get; init; } = TimeSpan.FromSeconds(5);
    public TimeSpan FrameTimeout { get; init; } = TimeSpan.FromSeconds(10);
    public TimeSpan ShutdownTimeout { get; init; } = TimeSpan.FromSeconds(2);
    internal void Validate()
    {
        if (OutboundQueueCapacity is < 1 or > 64) throw new ArgumentOutOfRangeException(nameof(OutboundQueueCapacity));
        foreach (var timeout in new[] { ConnectTimeout, FrameTimeout, ShutdownTimeout })
            if (timeout <= TimeSpan.Zero || timeout > TimeSpan.FromMinutes(2)) throw new ArgumentOutOfRangeException(nameof(timeout));
    }
}

/// <summary>
/// Local, explicit-start, single-peer Windows boundary. Connected is never session-ready.
/// Canonical V1 request routing, cancellation messages, subscriptions, grant checks and
/// DTO validation stay in the product-neutral core. This class does not invent wire fields.
/// </summary>
public sealed class NamedPipeTransport : IAsyncDisposable
{
    private readonly NamedPipeTransportOptions options;
    private readonly object gate = new();
    private readonly AttestationWorkLimiter attestationWork = new();
    private NamedPipeServerStream? listener;
    private PipeStream? connecting;
    private Connection? connection;
    private PipeTransportState state;
    private string? errorCode;
    private long generation;
    private bool disposed;
    public string? PipeName { get; private set; }
    private readonly Channel<PipeTransportHealth> stateChanges = Channel.CreateBounded<PipeTransportHealth>(
        new BoundedChannelOptions(32) { FullMode = BoundedChannelFullMode.DropOldest, SingleWriter = false, SingleReader = false });
    // Bounded, nonblocking observation. Health is authoritative when an observer falls behind.
    public IAsyncEnumerable<PipeTransportHealth> ObserveStateAsync(CancellationToken cancellationToken = default) =>
        stateChanges.Reader.ReadAllAsync(cancellationToken);

    public NamedPipeTransport(NamedPipeTransportOptions? options = null)
    {
        this.options = options ?? new();
        this.options.Validate();
    }

    public PipeTransportHealth Health
    {
        get { lock (gate) return new(state, connection?.Id, connection?.Authenticated ?? false,
            connection?.QueuedMessages ?? 0, 1, errorCode); }
    }
    public PeerIdentity? PeerIdentity { get { lock (gate) return connection?.Identity; } }

    public string Start(string? pipeName = null)
    {
        string name;
        lock (gate)
        {
            EnsureStopped();
            name = pipeName ?? CurrentUserPipe.NewPipeName();
            listener = CurrentUserPipe.CreateServer(name);
            PipeName = name;
            generation++;
            state = PipeTransportState.LISTENING;
            errorCode = null;
        }
        Notify();
        return name;
    }

    public async Task AcceptAsync(CancellationToken cancellationToken = default)
    {
        NamedPipeServerStream server;
        long attempt;
        lock (gate)
        {
            if (state != PipeTransportState.LISTENING || listener is null) throw new InvalidOperationException("Not listening.");
            server = listener;
            listener = null;
            connecting = server;
            state = PipeTransportState.CONNECTING;
            attempt = generation;
        }
        Notify();
        try
        {
            using var deadline = PipeFrames.Deadline(options.ConnectTimeout, cancellationToken);
            await server.WaitForConnectionAsync(deadline.Token).ConfigureAwait(false);
            Install(server, attempt);
        }
        catch { FailAttempt(server, attempt); throw; }
    }

    public async Task ConnectAsync(string pipeName, CancellationToken cancellationToken = default)
    {
        NamedPipeClientStream client;
        long attempt;
        lock (gate)
        {
            EnsureStopped();
            client = CurrentUserPipe.CreateClient(pipeName);
            connecting = client;
            PipeName = pipeName;
            state = PipeTransportState.CONNECTING;
            errorCode = null;
            attempt = ++generation;
        }
        Notify();
        try
        {
            using var deadline = PipeFrames.Deadline(options.ConnectTimeout, cancellationToken);
            await client.ConnectAsync(deadline.Token).ConfigureAwait(false);
            Install(client, attempt);
        }
        catch { FailAttempt(client, attempt); throw; }
    }

    private void Install(PipeStream stream, long attempt)
    {
        var observed = ObservedPeer.Capture(stream);
        lock (gate)
        {
            if (generation != attempt || state != PipeTransportState.CONNECTING)
            { observed.Dispose(); throw new OperationCanceledException("Connection attempt was invalidated."); }
            connecting = null;
            connection = new Connection(stream, observed, options, attestationWork, Faulted);
            state = PipeTransportState.TRANSPORT_CONNECTED;
        }
        Notify();
    }

    private void FailAttempt(PipeStream stream, long attempt)
    {
        stream.Dispose();
        lock (gate)
        {
            if (generation != attempt) return;
            connecting = null;
            state = PipeTransportState.FAILED;
            errorCode = "PIPE_CONNECT_FAILED";
        }
        Notify();
    }

    public Task SendAsync(string json, CancellationToken cancellationToken = default) => Active().SendAsync(json, cancellationToken);
    public Task<string> ReceiveAsync(CancellationToken cancellationToken = default) => Active().ReceiveAsync(cancellationToken);

    /// <summary>Reverify on trust/version changes; a downgrade immediately clears native authenticated status.</summary>
    public async Task<AttestationResult> AttestAsync(PeerClaims claims, InteropPeerAttestation attestation, CancellationToken cancellationToken = default)
    {
        var operation = Active().AttestAsync(claims, attestation, cancellationToken);
        Notify();
        try { return await operation.ConfigureAwait(false); }
        finally { Notify(); }
    }

    /// <summary>A new connection identity requires a new handshake, session and grants in the core.</summary>
    public async Task ReconnectAsync(string pipeName, CancellationToken cancellationToken = default)
    {
        await DisconnectAsync().ConfigureAwait(false);
        await ConnectAsync(pipeName, cancellationToken).ConfigureAwait(false);
    }

    public async Task DisconnectAsync()
    {
        Connection? prior;
        long stoppingGeneration;
        lock (gate)
        {
            stoppingGeneration = ++generation;
            state = PipeTransportState.DISCONNECTING;
            prior = connection;
            connection = null;
            listener?.Dispose(); listener = null;
            connecting?.Dispose(); connecting = null;
            PipeName = null;
        }
        Notify();
        if (prior is not null) await prior.CloseAsync().ConfigureAwait(false);
        lock (gate)
            if (generation == stoppingGeneration) state = PipeTransportState.STOPPED;
        Notify();
    }
    public Task StopAsync() => DisconnectAsync();
    public Task ShutdownAsync() => DisconnectAsync();
    public async ValueTask DisposeAsync()
    {
        lock (gate)
        {
            if (disposed) return;
            disposed = true;
        }
        await DisconnectAsync().ConfigureAwait(false);
        stateChanges.Writer.TryComplete();
    }

    private Connection Active()
    {
        lock (gate) return state == PipeTransportState.TRANSPORT_CONNECTED && connection is not null
            ? connection : throw new InvalidOperationException("No active transport connection.");
    }
    private void EnsureStopped()
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        if (state != PipeTransportState.STOPPED || connection is not null || listener is not null || connecting is not null)
            throw new InvalidOperationException("Disconnect before starting another endpoint. Connection limit is one.");
    }
    private void Faulted(Connection sender)
    {
        lock (gate)
        {
            if (!ReferenceEquals(connection, sender)) return;
            state = PipeTransportState.FAILED;
            errorCode = "PIPE_CONNECTION_CLOSED";
        }
        Notify();
    }
    private void Notify() => stateChanges.Writer.TryWrite(Health);

    private sealed class Connection
    {
        private sealed record Write(byte[] Body, CancellationToken Cancellation, TaskCompletionSource Completion);
        private readonly PipeStream stream;
        private readonly ObservedPeer observed;
        private readonly NamedPipeTransportOptions options;
        private readonly Action<Connection> faulted;
        private readonly CancellationTokenSource lifetime = new();
        private readonly Channel<Write> writes;
        private readonly Task writer;
        private readonly AttestationWorkLimiter attestationWork;
        private readonly object identityGate = new();
        private int closed;
        private int receiving;
        private int pending;
        private long attestationEpoch;
        private PeerIdentity identity;
        public Guid Id { get; } = Guid.NewGuid();
        public int QueuedMessages => Volatile.Read(ref pending);
        public PeerIdentity Identity => Volatile.Read(ref identity);
        public bool Authenticated => Volatile.Read(ref closed) == 0 && Identity.AttestationState == AttestationState.TRUSTED_INSTALLATION;

        public Connection(PipeStream stream, ObservedPeer observed, NamedPipeTransportOptions options, AttestationWorkLimiter attestationWork, Action<Connection> faulted)
        {
            (this.stream, this.observed, this.options, this.attestationWork, this.faulted) = (stream, observed, options, attestationWork, faulted);
            identity = observed.Target.Identity;
            writes = Channel.CreateBounded<Write>(new BoundedChannelOptions(options.OutboundQueueCapacity)
            { FullMode = BoundedChannelFullMode.Wait, SingleReader = true, SingleWriter = false, AllowSynchronousContinuations = false });
            writer = WriterAsync();
        }

        public Task SendAsync(string json, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            EnsureOpen();
            byte[] body = PipeFrames.Encode(json);
            var completion = new TaskCompletionSource(TaskCreationOptions.RunContinuationsAsynchronously);
            Interlocked.Increment(ref pending);
            if (!writes.Writer.TryWrite(new Write(body, cancellationToken, completion)))
            {
                Interlocked.Decrement(ref pending);
                EnsureOpen();
                throw new PipeBackpressureException();
            }
            return completion.Task.WaitAsync(cancellationToken);
        }

        private async Task WriterAsync()
        {
            try
            {
                await foreach (var write in writes.Reader.ReadAllAsync(lifetime.Token).ConfigureAwait(false))
                {
                    Interlocked.Decrement(ref pending);
                    if (write.Cancellation.IsCancellationRequested)
                    { write.Completion.TrySetCanceled(write.Cancellation); continue; }
                    try
                    {
                        using var token = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token, write.Cancellation);
                        await PipeFrames.WriteEncodedAsync(stream, write.Body, options.FrameTimeout, token.Token).ConfigureAwait(false);
                        write.Completion.TrySetResult();
                    }
                    catch (Exception ex)
                    {
                        write.Completion.TrySetException(ex);
                        // In-flight cancellation may have emitted part of a frame. Never reuse that stream.
                        Abort();
                        break;
                    }
                }
            }
            catch (OperationCanceledException) { }
            finally
            {
                while (writes.Reader.TryRead(out var item))
                {
                    Interlocked.Decrement(ref pending);
                    item.Completion.TrySetException(new IOException("Connection closed before delivery."));
                }
            }
        }

        public async Task<string> ReceiveAsync(CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            EnsureOpen();
            if (Interlocked.CompareExchange(ref receiving, 1, 0) != 0)
                throw new InvalidOperationException("Only one receive may be active.");
            try
            {
                using var token = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token, cancellationToken);
                var result = await PipeFrames.ReadAsync(stream, options.FrameTimeout, token.Token).ConfigureAwait(false);
                EnsureOpen();
                return result;
            }
            catch { Abort(); throw; }
            finally { Volatile.Write(ref receiving, 0); }
        }

        public async Task<AttestationResult> AttestAsync(PeerClaims claims, InteropPeerAttestation attestation, CancellationToken cancellationToken)
        {
            long epoch;
            lock (identityGate)
            {
                EnsureOpen();
                epoch = ++attestationEpoch;
                Volatile.Write(ref identity, Identity with { AttestationState = AttestationState.UNVERIFIED });
            }
            using var deadline = PipeFrames.Deadline(options.ConnectTimeout, cancellationToken);
            using var token = CancellationTokenSource.CreateLinkedTokenSource(lifetime.Token, deadline.Token);
            EnsureOpen();
            // Capacity remains occupied until the actual hook completes, even after
            // timeout, disconnect or reconnect. Later attempts fail with backpressure.
            var operation = attestationWork.Start(async () => await attestation.VerifyAsync(observed.Target, claims, token.Token).ConfigureAwait(false), token.Token);
            var result = await operation.WaitAsync(token.Token).ConfigureAwait(false);
            lock (identityGate)
            {
                EnsureOpen();
                if (epoch != attestationEpoch) throw new OperationCanceledException("A newer attestation superseded this result.");
                Volatile.Write(ref identity, result.Identity);
            }
            return result;
        }

        private void EnsureOpen()
        {
            if (Volatile.Read(ref closed) != 0) throw new IOException("Transport connection is closed.");
        }
        private void Abort()
        {
            lock (identityGate)
            {
                if (closed != 0) return;
                Volatile.Write(ref closed, 1);
                Volatile.Write(ref identity, Identity with { AttestationState = AttestationState.REJECTED });
            }
            writes.Writer.TryComplete();
            // Platform verification hooks may register callbacks. Do not let those block exit.
            var cancellation = lifetime.CancelAsync();
            _ = cancellation.ContinueWith(task => { _ = task.Exception; }, CancellationToken.None,
                TaskContinuationOptions.OnlyOnFaulted, TaskScheduler.Default);
            stream.Dispose();
            observed.Dispose();
            faulted(this);
        }
        public async Task CloseAsync()
        {
            Abort();
            try { await writer.WaitAsync(options.ShutdownTimeout).ConfigureAwait(false); }
            catch (TimeoutException) { /* handles already closed; caller shutdown remains bounded */ }
        }
    }
}
