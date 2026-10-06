# Local Interop V1 lifecycle and acknowledgement limits

This development bridge is OFF by default. Its transport peer identity remains
self-declared, not authenticated installed-product/current-OS-user identity.
The following limits are part of the review boundary, not production-readiness
or real Tutor Desktop claims.

## Expiry and liveness

- The shared SessionDescriptor accepts a positive fixed lifetime of at most
  **86,400 seconds (24 hours)**. The Studio Host checks the negotiated expires_at
  at each authorization gate and rejects an expired session.
- The shipped public Synthetic Tutor chooses **10 minutes**. The private HTTP
  reference chooses **15 minutes**. Its separate Synthetic Studio unit fixture
  uses 30 minutes; that is not the HTTP reference default.
- Event or heartbeat acknowledgements **never extend the original expiry**.
- The Host pump defaults to a **250 ms** interval (constructor minimum 50 ms).
  It rechecks live authorization each iteration.
- It sends a heartbeat after **10 seconds without a successful event or heartbeat
  acknowledgement**. The first idle iteration can send one immediately because
  the initial last-peer-success timestamp is zero.
- HTTP operations default to **4-second** timeouts; the transport constructor
  bounds that setting to 50 ms–10 seconds. Foreground Host operations have a
  **15-second overall** deadline. These do not constitute a guaranteed 14-second
  failure-detection bound: event-loop blocking and per-read timeout semantics
  matter. A detected pump transport, identity, acknowledgement or authority
  failure revokes that session.

## Three distinct actions

**Explicit Stop / master OFF:** a successfully acknowledged stop revokes the
scoped grant. A successful master OFF additionally removes the owner's enabled
gate and clears sessions, previews, grants, queues and pending event dispatch/
requests before acknowledgement. Failure or an uncertain receipt cannot prove
revocation and must remain UNKNOWN in the UI. Local cancellation still discards
late responses; that is distinct from proving the Host received a revocation.

**Closing a panel or browser UI:** the close-and-disconnect control waits for a
matching acknowledgement. If it fails, the panel remains UNKNOWN and offers an
explicit “close panel, revocation unconfirmed” choice. Browser/window removal
remains best-effort. Failed or unacknowledged disconnect is never displayed as
completed revocation.
There is no browser pagehide/keepalive revocation hook or UI-liveness lease in V1.
If a still-running Host and Tutor can communicate but the UI cannot reach the
Host, an already explicitly approved grant can continue until actual stop,
authority/session revocation or its original negotiated expiry. This is a
**PARTIAL development lifecycle boundary**. Closing or losing a UI alone is not
proof of software exit or revocation.

**Graceful Studio API/application shutdown:** the app lifespan awaits
LocalInteropHost.shutdown(), revokes its sessions, cancels/gathers pumps and
clears in-memory state. A dead Host process cannot send further events. A restart
has a new instance identity, is OFF by default and does not inherit a grant.
Real desktop process/window lifecycle composition remains LOCAL_REQUIRED.

Bytes already received by a peer cannot be recalled. Preparing diagnostics
pauses ongoing event sharing before presenting the minimized diagnostic; it never
resumes that sharing automatically. Ordinary one-shot preview and a separately
visible standing grant remain distinct permissions.

## Response isolation

The frontend's epoch, AbortController, alive check and captured request/session
receipt checks prevent an old response from rendering after local cancellation,
identity/scope change, disconnect or a newer session. This local display guarantee
must not be confused with remote revocation acknowledgement.
