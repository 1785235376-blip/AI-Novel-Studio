namespace PoemSeed.LocalInterop.Pipes;

public sealed class PeerAttestationBusyException() : IOException("Peer attestation capacity is full.");

/// <summary>
/// One outstanding platform verification per transport, including across reconnects;
/// at most four across this process. Caller timeout never releases unfinished work.
/// </summary>
internal sealed class AttestationWorkLimiter
{
    private static readonly SemaphoreSlim ProcessSlots = new(4, 4);
    private readonly SemaphoreSlim slot = new(1, 1);

    public Task<T> Start<T>(Func<Task<T>> operation, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        if (!slot.Wait(0)) throw new PeerAttestationBusyException();
        if (!ProcessSlots.Wait(0)) { slot.Release(); throw new PeerAttestationBusyException(); }
        // Do not pass cancellation to Task.Run: an unscheduled canceled task would
        // skip finally and leak its slot. The delegate checks before invoking the hook.
        return Task.Run(async () =>
        {
            try
            {
                cancellationToken.ThrowIfCancellationRequested();
                return await operation().ConfigureAwait(false);
            }
            finally { ProcessSlots.Release(); slot.Release(); }
        });
    }
}
