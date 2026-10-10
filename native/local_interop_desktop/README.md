# Callable Windows Named Pipe desktop boundary

`PoemSeed.LocalInterop.Pipes` is a .NET 8 Windows library referenced by the retained
legacy eight-check transport runner in Creative Studio and by the new acceptance executable. Desktop
adapters can reference its project or built DLL directly. Importing the assembly
never starts a listener, launches a program, or grants permissions. It is an
implemented transport boundary; real product wiring is **LOCAL_REQUIRED**.

## API and ownership

- `NamedPipeTransport.Start()` explicitly creates a random local endpoint.
- `AcceptAsync()` / `ConnectAsync(name)` establish **transport only**.
- `SendAsync(json)` / `ReceiveAsync()` frame canonical V1 JSON without translating it.
- `AttestAsync(claims, verifier)` binds HELLO claims to OS-observed peer evidence.
- `DisconnectAsync()` / `StopAsync()` / `ShutdownAsync()` close handles and invalidate
  the connection; `ReconnectAsync(name)` creates a fresh connection ID and no trust.
- `Health`, `PeerIdentity`, and bounded `ObserveStateAsync()` expose transport facts.

The product-neutral `local_interop_desktop` core owns `request`, protocol `cancel`,
`subscribe`, `unsubscribe`, handshake, negotiation, session binding, permission
checks and response freshness. Calling the transport does not establish these.
The adapter must separately track transport connected, handshake complete, peer
authenticated, session established and capabilities negotiated. Never infer READY
from `TRANSPORT_CONNECTED` or use `PeerAuthenticated` as content permission.

```csharp
// A desktop adapter references the library; no demo process is required.
await using var transport = new NamedPipeTransport();
await transport.ConnectAsync(discoveredOpaquePipeName, cancellationToken);
await transport.SendAsync(canonicalHelloJson, cancellationToken);
var helloReplyJson = await transport.ReceiveAsync(cancellationToken);
// Validate the frozen V1 HELLO DTO, then attach its claimed product fields.
var result = await transport.AttestAsync(validatedClaims, localPlatformVerifier,
    cancellationToken);
// Only the existing core can negotiate capabilities and establish authorization.
```

These are local method arguments, not new wire fields. Protocol files are unchanged.
The retained reference command in Creative Studio remains:

```
dotnet run --project interop-reference/PoemSeed.LocalInterop.Pipes -c Release
```

## Security and bounded resources

- Opaque allowlisted pipe name; fixed local machine `.`; no arbitrary path API.
- Protected current-SID DACL, explicit network-logon deny, remote clients rejected
  by `PIPE_REJECT_REMOTE_CLIENTS`; first-instance creation and kernel limit **1**.
- Server/client handles are non-inheritable. OS peer PID is obtained from the pipe,
  process token SID must equal the caller SID, executable path is hashed locally.
  Anonymous/unobservable peers fail closed. A process handle pins the observation.
- Frame is unchanged V1: unsigned little-endian 32-bit byte length, UTF-8 JSON
  object, maximum 1 MiB, depth 24. Malformed UTF-8/JSON, duplicate members,
  oversized/zero lengths and truncation fail closed. Canonical schema validation
  remains the core's job.
- At most one reader, one writer, one in-flight write and 8 queued frames by default
  (configurable 1–64). Full queues reject with local `PipeBackpressureException`;
  there is no hidden unbounded queue or unbounded population of enqueue waiters.
- Frame/connect deadlines, cancellation, bounded 2-second writer drain, close on
  partial/cancelled I/O. A damaged stream is never reused. Cancelling before a
  queued write starts skips that write. Cancellation after it starts closes the
  connection because a partial frame cannot safely be resumed.
- Platform attestation runs at most once per transport (including across reconnects),
  with a process-wide ceiling of four outstanding operations. Timeout/disconnect
  never releases an uncooperative hook's slot; only actual completion does. Later
  calls fail with `PeerAttestationBusyException`, without queuing additional work.
- The observer channel retains at most 32 non-content snapshots and drops oldest
  when slow. Poll `Health` for current truth. No application callback can block exit.
- Error receipts expose type/code only, never raw exceptions, full paths or content.

## Peer identity and attestation integration

`PeerIdentity` carries OS PID, SID, executable-path hash and separate, untrusted
product ID / instance ID / product version claims. Frozen V1 character patterns and
length bounds are checked before any claim is retained in identity or diagnostics;
invalid claims are rejected without copying their strings. Recognizable API-key,
GitHub-token, Slack-token, AWS-key and JWT shapes are also rejected before retention.
This conservative guard does not claim to identify arbitrary hidden secrets. A path hash is **not** a binary
hash, signature, publisher proof or authentication credential. PID/SID/process
path alone attest only `SAME_USER`. The library never hardcodes a trusted product ID.

Implement `IInstalledProductVerifier` against the product-owned, approved install
registration and `ISignedExecutableVerifier` against verified executable signature /
publisher evidence. Both hooks must bind evidence to the **connected process's loaded
product image/payload**, not merely verify a file currently found at the same path.
Replacement between load, observation and verification is a TOCTOU risk. The current
PID/token/path observation does not prove loaded-image bytes. Real loaded-image
binding and replacement-race defenses remain **LOCAL_REQUIRED**; a provider lacking
that proof must return unavailable/no verified installation and must not mint trusted
evidence. Evidence records default `ConnectedImageVerified` to false; the policy
refuses trusted status without the explicit, independently obtained process-image
binding on both registration and signature evidence. This is an internal proof hook,
not a new protocol field. Installation IDs and publisher identities must be bounded
opaque IDs (for example a registered publisher ID or certificate thumbprint), not
paths, free-form subjects or credentials. No disk scan, process-content enumeration, auto-launch or
install-registry assumption is made here. Hooks receive the OS-observed executable
path only for local verification; never log or serialize that private path.

`InteropPeerAttestation` requires matching product, installation, path hash, version,
protocol, non-revoked registration, valid publisher signature and explicit install
approval for `TRUSTED_INSTALLATION`. Missing install proof rejects a fake claimed
`poemseed.tutor.desktop` just like any other claim. Missing signature proof can reach
only `KNOWN_PRODUCT`; valid signature without approval only `SIGNED_PRODUCT`.
Missing real integrations report `LOCAL_REQUIRED`. Reverification clears the prior
native authenticated bit before checking; caller core must suspend sensitive grants
and invalidate sessions on a downgrade. No grants are stored in this library.

Do not approve `dotnet.exe`, a script host, path hash or shared unsigned loader as
proof of a product payload. Reference tests use a host executable and explicitly
MOCK_ONLY hook evidence; they prove hook policy, never signed-product trust. Real
verification must bind the running product executable/payload, publisher, expected
installation and registration, handle updates and reject mismatches. Actual signed
binary verification, real installation records and real two-product processes are
**LOCAL_REQUIRED**, not supplied by a mock provider or a successful build.

## Acceptance commands and honest evidence

```
dotnet build native/local_interop_desktop/PoemSeed.LocalInterop.Pipes -c Release
dotnet run --project native/local_interop_desktop/PoemSeed.LocalInterop.Pipes.Acceptance -c Release
```

Run the second command on Windows for actual named-pipe tests, synthetic separate
process PID/SID identity and echo, non-inheritance, first-instance collision,
local-only names, connection limit, timeout/cancel, malformed close, backpressure,
bounded shutdown, explicit reconnect and fake-identity/attestation hook tests.
`-- --portable` runs only framing/resource-config tests (also on Linux). Its receipt
explicitly says `windows_transport=NOT_RUN`. Hosted Windows execution is synthetic
**CONTRACT_VERIFIED**, not Desktop acceptance. The legacy eight checks remain a
separate mandatory command; do not silently replace them with the new runner.

## A21 real hostile different-user test

Use two **existing distinct Windows account sessions** on the same machine. Build
the acceptance project first; both accounts need ordinary read/execute access to
that build and read access to the operator-selected metadata receipt location.
This harness does not provision users, handle passwords, runas, or change ACLs.

In account A's PowerShell (keep it running for its 120-second window):

```
./native/local_interop_desktop/scripts/Invoke-CrossUserPipeAcceptance.ps1 -Mode Server -ServerReceipt <server.jsonl>
```

In account B's PowerShell, while A is listening:

```
./native/local_interop_desktop/scripts/Invoke-CrossUserPipeAcceptance.ps1 -Mode Client -ServerReceipt <server.jsonl> -ClientReceipt <client.jsonl>
```

After A's window ends, combine the receipts:

```
./native/local_interop_desktop/scripts/Invoke-CrossUserPipeAcceptance.ps1 -Mode Verify -ServerReceipt <server.jsonl> -ClientReceipt <client.jsonl> -OutputReceipt <A21.json>
```

The hostile client deliberately omits `CurrentUserOnly`, so the server ACL is the
boundary under test. Same SID, timeout, absent live server evidence or unmatched
receipts are **NOT_RUN**, never PASS. A PASS requires actual access denied from a
distinct OS SID, matching opaque pipe/server identity and an attempt inside the
verified listening interval. Unexpected connection is failure. This must be run
separately from same-user CI; its status remains **NOT_RUN** until such evidence
exists. It is new implementation acceptance, not a replacement for prior audits.

Microsoft API references:
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createnamedpipew
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeclientprocessid
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-getnamedpipeserverprocessid
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-queryfullprocessimagenamew
